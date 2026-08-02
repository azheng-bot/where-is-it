#!/usr/bin/env bash
# Installs Docker Engine and NVIDIA Container Toolkit on an Ubuntu 22.04 GPU node.
# Run after installing a compatible NVIDIA driver and confirming `nvidia-smi` works.
set -euo pipefail

if [[ $(. /etc/os-release && printf '%s' "$ID:$VERSION_ID") != "ubuntu:22.04" ]]; then
  echo "This bootstrap script supports Ubuntu 22.04 only." >&2
  exit 1
fi
if ! command -v nvidia-smi >/dev/null; then
  echo "Install and validate a compatible NVIDIA driver before running this script." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
printf '%s\n' \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

nvidia-smi
docker run --rm --gpus all nvidia/cuda:13.2.0-base-ubuntu22.04 nvidia-smi
printf 'GPU container runtime is ready. Optionally run: sudo usermod -aG docker $USER\n'