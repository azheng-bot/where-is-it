import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const read = (path) => readFileSync(resolve(root, path), "utf8");
const requireText = (path, fragments) => {
  const source = read(path);
  for (const fragment of fragments) {
    if (!source.includes(fragment)) throw new Error(`${path} is missing: ${fragment}`);
  }
  return source;
};

const streamer = requireText("deploy/video-streamer/docker-compose.yml", ["video-streamer:", "VISION_ROLE: pusher", "FRAME_INGEST_URL", "VISION_PUSH_TOKEN"]);
if (streamer.includes("DATABASE_PATH") || streamer.includes("ASR_SERVICE_URL")) throw new Error("video-streamer must not access database or ASR");

const gpu = requireText("deploy/gpu-inference-api/docker-compose.yml", ["api:", "vision-receiver:", "florence:", "grounding:", "sam:", "embedding:", "asr:", "VISION_ROLE: receiver", "ASR_SERVICE_URL: http://asr:8006"]);
for (const service of ["florence", "grounding", "sam", "embedding", "asr"]) {
  const start = gpu.indexOf(`  ${service}:`);
  const end = gpu.indexOf("\n  ", start + 3);
  const block = gpu.slice(start, end === -1 ? gpu.length : end);
  if (block.includes("ports:")) throw new Error(`${service} must not publish a host port`);
}

requireText("deploy/web/docker-compose.yml", ["web:", "VITE_API_BASE_URL", "PUBLIC_API_URL"]);
requireText("apps/web/Dockerfile", ["ARG VITE_API_BASE_URL", "ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}"]);
requireText("deploy/gpu-inference-api/.env.example", ["WEB_ALLOWED_ORIGINS", "VISION_PUSH_TOKEN", "PYTORCH_EXPECTED_VERSION=2.12.1", "PYTORCH_EXPECTED_CUDA=13.2", "GPU_DEVICE_INDEX=0"]);
requireText("deploy/gpu-inference-api/scripts/bootstrap-ubuntu-22.04.sh", ["nvidia-container-toolkit", "nvidia-ctk runtime configure", "--gpus all"]);
requireText("deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh", ["nvidia-smi", "docker compose"]);
requireText("deploy/gpu-inference-api/scripts/verify-deployment.sh", ["verify_gpu_runtime.py", "health/ready"]);
requireText("deploy/gpu-inference-api/docker-compose.cpu.yml", ["MODEL_MODE: mock", "ASR_MODE: mock", "devices: !reset []"]);
console.log("Three-service deployment topology is valid.");