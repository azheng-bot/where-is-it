#!/usr/bin/env bash
# Validates an already started GPU service package.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
compose_file="$repo_root/deploy/gpu-inference-api/docker-compose.yml"
env_file="${1:-$repo_root/deploy/gpu-inference-api/.env}"
timeout_seconds=${GPU_READY_TIMEOUT_SECONDS:-900}

compose=(docker compose --env-file "$env_file" -f "$compose_file")
for service in florence grounding sam embedding; do
  "${compose[@]}" exec -T "$service" python /app/services/model_runtime/verify_gpu_runtime.py
done

end=$((SECONDS + timeout_seconds))
until curl --fail --silent --show-error http://127.0.0.1:8000/health/ready >/dev/null; do
  if (( SECONDS >= end )); then
    echo "GPU API did not become ready within ${timeout_seconds}s." >&2
    exit 1
  fi
  sleep 5
done
curl --fail --silent --show-error http://127.0.0.1:8000/health/ready
curl --fail --silent --show-error http://127.0.0.1:8001/health/ready
echo
printf 'GPU inference API deployment verification passed.\n'