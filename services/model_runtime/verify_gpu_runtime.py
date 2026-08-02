#!/usr/bin/env python3
"""Fail-fast preflight for the supported Ubuntu RTX 40-series GPU node."""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    errors: list[str] = []
    if sys.version_info[:2] != (3, 12):
        errors.append(f"Python 3.12 is required, found {sys.version.split()[0]}")
    try:
        import torch
    except ImportError as error:
        print(json.dumps({"ok": False, "errors": [f"torch import failed: {error}"]}))
        return 1

    torch_version = torch.__version__.split("+", 1)[0]
    expected_torch = os.getenv("PYTORCH_EXPECTED_VERSION", "2.12.1")
    expected_cuda = os.getenv("PYTORCH_EXPECTED_CUDA", "13.2")
    if torch_version != expected_torch:
        errors.append(f"PyTorch {expected_torch} is required, found {torch.__version__}")
    if not torch.cuda.is_available():
        errors.append("PyTorch cannot access CUDA")
        report = {
            "ok": False,
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "errors": errors,
        }
        print(json.dumps(report, ensure_ascii=False))
        return 1

    device = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(device)
    capability = f"{props.major}.{props.minor}"
    memory_gb = round(props.total_memory / 1024 ** 3, 1)
    if torch.version.cuda != expected_cuda:
        errors.append(f"CUDA {expected_cuda} PyTorch wheel is required, found CUDA {torch.version.cuda}")
    if (props.major, props.minor) != (8, 9):
        errors.append(f"RTX 40-series compute capability 8.9 is required, found {capability}")
    if memory_gb < 20:
        errors.append(f"at least 20GB usable VRAM is required, found {memory_gb}GB")

    report = {
        "ok": not errors,
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "gpu": props.name,
        "compute_capability": capability,
        "gpu_memory_gb": memory_gb,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
