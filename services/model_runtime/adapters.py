"""Real, lazy-loaded adapters for the four visual inference services."""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from services.shared.contracts import InferenceRequest


class AdapterUnavailable(RuntimeError):
    pass


def _device() -> str:
    return os.getenv("MODEL_DEVICE", "cpu")


def _model_dtype(torch: Any) -> Any:
    """Return the configured model precision, with a CPU-safe fallback.

    RTX 40-series cards efficiently run the visual models in FP16. CPU mode is
    deliberately fixed at FP32 because many CPU operator paths do not support
    half precision.
    """

    if not _device().startswith("cuda"):
        return torch.float32
    requested = os.getenv("MODEL_DTYPE", "float16").strip().lower()
    supported = {
        "float16": torch.float16, "fp16": torch.float16,
        "bfloat16": torch.bfloat16, "bf16": torch.bfloat16,
        "float32": torch.float32, "fp32": torch.float32,
    }
    try:
        return supported[requested]
    except KeyError as error:
        raise AdapterUnavailable(
            "MODEL_DTYPE must be float16, bfloat16, or float32"
        ) from error


def _validate_device(torch: Any) -> None:
    device = _device()
    if not device.startswith("cuda"):
        return
    if not torch.cuda.is_available():
        raise AdapterUnavailable(
            f"MODEL_DEVICE={device} requires CUDA, but PyTorch cannot see an NVIDIA GPU. "
            "Check the NVIDIA driver, NVIDIA Container Toolkit, and Docker GPU flags."
        )
    try:
        index = torch.device(device).index or 0
        properties = torch.cuda.get_device_properties(index)
    except (RuntimeError, ValueError) as error:
        raise AdapterUnavailable(f"MODEL_DEVICE={device} is not available: {error}") from error
    minimum_gb = float(os.getenv("MODEL_MIN_GPU_MEMORY_GB", "20"))
    memory_gb = properties.total_memory / 1024 ** 3
    if memory_gb < minimum_gb:
        raise AdapterUnavailable(
            f"MODEL_DEVICE={device} has {memory_gb:.1f}GB VRAM; this profile requires "
            f"at least {minimum_gb:.0f}GB."
        )


def _load_options(torch: Any) -> dict[str, Any]:
    _validate_device(torch)
    return {"torch_dtype": _model_dtype(torch)}


def _model_id(service: str, default: str) -> str:
    return os.getenv(f"{service.upper()}_MODEL", default)


def _image(request: InferenceRequest):
    try:
        from PIL import Image
    except ImportError as error:
        raise AdapterUnavailable("Pillow is required for real visual inference") from error
    encoded = request.payload.get("frame_jpeg_b64")
    if isinstance(encoded, str) and encoded:
        try:
            return Image.open(BytesIO(base64.b64decode(encoded, validate=True))).convert("RGB")
        except (ValueError, OSError) as error:
            raise ValueError("frame_jpeg_b64 is not a valid JPEG image") from error
    media = request.frame_ref or request.media_ref
    if media is None or not media.uri.startswith("file://"):
        raise ValueError("a local image URI or frame_jpeg_b64 is required")
    path = Path(unquote(urlparse(media.uri).path))
    if not path.is_file():
        raise ValueError(f"input image does not exist: {path}")
    return Image.open(path).convert("RGB")


def _move(inputs: Any, device: str, dtype: Any | None = None):
    if not hasattr(inputs, "to"):
        return inputs
    # Transformers BatchFeature preserves integer token IDs while casting image
    # tensors when a dtype is supplied.
    return inputs.to(device=device, dtype=dtype) if dtype is not None else inputs.to(device)


def _box(box: list[float], width: int, height: int) -> list[float]:
    left, top, right, bottom = box
    left, top = max(0.0, min(left, float(width))), max(0.0, min(top, float(height)))
    right, bottom = max(left, min(right, float(width))), max(top, min(bottom, float(height)))
    return [round(left / width, 6), round(top / height, 6), round((right - left) / width, 6), round((bottom - top) / height, 6)]


class ModelAdapter(ABC):
    def __init__(self, service: str) -> None:
        self.service, self.model, self.processor = service, None, None

    @property
    def model_version(self) -> str:
        return _model_id(self.service, "unknown")

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def infer(self, request: InferenceRequest) -> dict[str, Any]: ...


class FlorenceAdapter(ModelAdapter):
    def load(self) -> None:
        try:
            from transformers import AutoProcessor, Florence2ForConditionalGeneration
            import torch
        except ImportError as error:
            raise AdapterUnavailable("install torch and transformers to enable Florence") from error
        name = _model_id("florence", "florence-community/Florence-2-base")
        self.processor = AutoProcessor.from_pretrained(name)
        self.model, self.torch = Florence2ForConditionalGeneration.from_pretrained(
            name, **_load_options(torch)
        ).to(_device()).eval(), torch
        self.dtype = _model_dtype(torch)

    def infer(self, request: InferenceRequest) -> dict[str, Any]:
        image, task = _image(request), str(request.payload.get("task", "<OD>"))
        if task not in {"<OD>", "<CAPTION>", "<DETAILED_CAPTION>"}: task = "<OD>"
        inputs = _move(self.processor(text=task, images=image, return_tensors="pt"), _device(), self.dtype)
        with self.torch.no_grad(): ids = self.model.generate(**inputs, max_new_tokens=512, num_beams=3)
        parsed = self.processor.post_process_generation(self.processor.batch_decode(ids, skip_special_tokens=False)[0], task=task, image_size=image.size)
        value = parsed.get(task, parsed) if isinstance(parsed, dict) else parsed
        boxes, labels = (value.get("bboxes", []), value.get("labels", [])) if isinstance(value, dict) else ([], [])
        result: dict[str, Any] = {"detections": [{"label": str(label), "box": _box([float(x) for x in box], image.width, image.height), "confidence": 0.5} for label, box in zip(labels, boxes)], "task": task}
        if isinstance(value, str): result["caption"] = value
        return result


class GroundingAdapter(ModelAdapter):
    def load(self) -> None:
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
            import torch
        except ImportError as error:
            raise AdapterUnavailable("install torch and transformers to enable Grounding DINO") from error
        name = _model_id("grounding", "IDEA-Research/grounding-dino-tiny")
        self.processor = AutoProcessor.from_pretrained(name)
        self.model, self.torch = AutoModelForZeroShotObjectDetection.from_pretrained(
            name, **_load_options(torch)
        ).to(_device()).eval(), torch
        self.dtype = _model_dtype(torch)

    def infer(self, request: InferenceRequest) -> dict[str, Any]:
        image = _image(request)
        candidates = [str(item).strip() for item in request.payload.get("candidates", []) if str(item).strip()]
        if not candidates: return {"detections": [], "verified": True, "reason": "no candidates"}
        inputs = _move(self.processor(images=image, text=". ".join(candidates) + ".", return_tensors="pt"), _device(), self.dtype)
        with self.torch.no_grad(): outputs = self.model(**inputs)
        values = self.processor.post_process_grounded_object_detection(outputs, inputs.input_ids, threshold=float(request.payload.get("box_threshold", os.getenv("GROUNDING_BOX_THRESHOLD", "0.35"))), text_threshold=float(request.payload.get("text_threshold", os.getenv("GROUNDING_TEXT_THRESHOLD", "0.25"))), target_sizes=[image.size[::-1]])[0]
        return {"detections": [{"label": str(label), "box": _box([float(x) for x in box.tolist()], image.width, image.height), "confidence": round(float(score), 6)} for label, box, score in zip(values["labels"], values["boxes"], values["scores"])], "verified": True}


class SamAdapter(ModelAdapter):
    def load(self) -> None:
        try:
            from transformers import Sam2Model, Sam2Processor
            import torch
        except ImportError as error:
            raise AdapterUnavailable("install a recent transformers release to enable SAM 2") from error
        name = _model_id("sam", "facebook/sam2.1-hiera-tiny")
        self.processor = Sam2Processor.from_pretrained(name)
        self.model, self.torch = Sam2Model.from_pretrained(
            name, **_load_options(torch)
        ).to(_device()).eval(), torch
        self.dtype = _model_dtype(torch)

    def infer(self, request: InferenceRequest) -> dict[str, Any]:
        image = _image(request)
        detections = [item for item in request.payload.get("detections", []) if isinstance(item, dict) and isinstance(item.get("box"), list)]
        if not detections: return {"segments": []}
        boxes = []
        for item in detections:
            x, y, width, height = (float(value) for value in item["box"])
            boxes.append([x * image.width, y * image.height, (x + width) * image.width, (y + height) * image.height])
        inputs = _move(self.processor(images=image, input_boxes=[boxes], return_tensors="pt"), _device(), self.dtype)
        with self.torch.no_grad(): outputs = self.model(**inputs, multimask_output=False)
        masks = self.processor.post_process_masks(outputs.pred_masks.cpu(), inputs["original_sizes"])[0]
        return {"segments": [{"label": str(item.get("label", "object")), "box": item["box"], "mask_area": round(float(mask.to(dtype=self.torch.float32).mean().item()), 6), "confidence": item.get("confidence", 0.0)} for item, mask in zip(detections, masks)]}


class EmbeddingAdapter(ModelAdapter):
    def load(self) -> None:
        try:
            from transformers import AutoImageProcessor, AutoModel
            import torch
        except ImportError as error:
            raise AdapterUnavailable("install torch and transformers to enable DINOv2") from error
        name = _model_id("embedding", "facebook/dinov2-small")
        self.processor = AutoImageProcessor.from_pretrained(name)
        self.model, self.torch = AutoModel.from_pretrained(
            name, **_load_options(torch)
        ).to(_device()).eval(), torch
        self.dtype = _model_dtype(torch)

    def infer(self, request: InferenceRequest) -> dict[str, Any]:
        image = _image(request)
        detections = [item for item in request.payload.get("detections", []) if isinstance(item, dict)] or [{"label": "frame", "box": [0, 0, 1, 1]}]
        result = []
        for item in detections:
            x, y, width, height = (float(value) for value in item.get("box", [0, 0, 1, 1]))
            crop = image.crop((x * image.width, y * image.height, min(image.width, (x + width) * image.width), min(image.height, (y + height) * image.height)))
            inputs = _move(self.processor(images=crop, return_tensors="pt"), _device(), self.dtype)
            with self.torch.no_grad(): output = self.model(**inputs)
            vector = output.pooler_output[0] if getattr(output, "pooler_output", None) is not None else output.last_hidden_state[0, 0]
            vector = self.torch.nn.functional.normalize(vector, dim=0).detach().cpu().tolist()
            result.append({"label": str(item.get("label", "object")), "box": item.get("box", [0, 0, 1, 1]), "values": [round(float(value), 6) for value in vector], "dimensions": len(vector)})
        return {"embeddings": result}


def create_adapter(service: str) -> ModelAdapter:
    adapters = {"florence": FlorenceAdapter, "grounding": GroundingAdapter, "sam": SamAdapter, "embedding": EmbeddingAdapter}
    if service not in adapters: raise ValueError(f"unsupported model service: {service}")
    return adapters[service](service)
