#!/usr/bin/env bash
# Read-only preflight for the GPU node. Run before building the service package.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
compose_file="$repo_root/deploy/gpu-inference-api/docker-compose.yml"
env_file="${1:-$repo_root/deploy/gpu-inference-api/.env}"

[[ -f "$env_file" ]] || { echo "Missing environment file: $env_file" >&2; exit 1; }
[[ $(. /etc/os-release && printf '%s' "$ID:$VERSION_ID") == "ubuntu:22.04" ]] || { echo "Ubuntu 22.04 is required." >&2; exit 1; }
command -v nvidia-smi >/dev/null || { echo "nvidia-smi is unavailable." >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is unavailable." >&2; exit 1; }
command -v nvidia-ctk >/dev/null || { echo "nvidia-ctk is unavailable." >&2; exit 1; }

echo 'Host GPU:'
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
printf '\nContainer GPU:\n'
docker run --rm --gpus all nvidia/cuda:13.2.0-base-ubuntu22.04 nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
docker compose --env-file "$env_file" -f "$compose_file" config -q
echo 'Preflight passed.'