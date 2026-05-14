#!/usr/bin/env bash
set -euo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${WORKDIR}/.venv"

sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git-lfs curl jq

git lfs install

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/pip" install --upgrade "huggingface_hub[cli]"

echo "Base tools installed in ${VENV_DIR}"