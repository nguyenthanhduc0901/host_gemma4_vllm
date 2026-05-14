#!/usr/bin/env bash
set -euo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${WORKDIR}/.venv"

export VLLM_TARGET_DEVICE="cuda"
export VLLM_ENABLE_RESPONSES_API_STORE="1"

if [ ! -x "${VENV_DIR}/bin/vllm" ]; then
  echo "Missing ${VENV_DIR}/bin/vllm. Run scripts/03_install_vllm.sh first." >&2
  exit 1
fi

has_nvidia_pci_gpu() {
  command -v lspci >/dev/null 2>&1 && lspci | grep -qi 'NVIDIA'
}

gpu_runtime_ready() {
  "${VENV_DIR}/bin/python" - <<'PY'
import sys
import torch
sys.exit(0 if torch.cuda.is_available() and torch.cuda.device_count() > 0 else 1)
PY
}

if ! gpu_runtime_ready; then
  if has_nvidia_pci_gpu; then
    echo "NVIDIA GPU detected on PCI bus, but CUDA runtime is not usable." >&2
    echo "Likely missing NVIDIA driver, /dev/nvidia* device nodes, or container/VM GPU passthrough setup." >&2
    echo "This host currently cannot run vLLM yet even though an NVIDIA L4 is attached." >&2
  else
    echo "No usable CUDA GPU runtime detected for vLLM." >&2
  fi
  exit 1
fi

MODEL_PATH="${WORKDIR}/models/google/gemma-4-E4B-it"
if [ ! -d "${MODEL_PATH}" ]; then
  echo "Missing local model at ${MODEL_PATH}. Run scripts/02_download_model.sh first." >&2
  exit 1
fi
MODEL_TARGET="${MODEL_PATH}"

HOST="0.0.0.0"
PORT="8000"
SERVED_MODEL_NAME="gemma-4-e4b-it"
VLLM_DTYPE="auto"
MAX_MODEL_LEN="2048"
TENSOR_PARALLEL_SIZE="1"
GPU_MEMORY_UTILIZATION="0.90"
LANGUAGE_MODEL_ONLY="1"
VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS="0"

export VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS

cmd=(
  "${VENV_DIR}/bin/vllm" serve "${MODEL_TARGET}"
  --host "${HOST}"
  --port "${PORT}"
  --served-model-name "${SERVED_MODEL_NAME}"
  --dtype "${VLLM_DTYPE}"
  --tensor-parallel-size "${TENSOR_PARALLEL_SIZE}"
  --max-model-len "${MAX_MODEL_LEN}"
  --generation-config vllm
  --enable-prefix-caching
  --enable-request-id-headers
  --disable-access-log-for-endpoints "/health,/metrics,/ping"
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}"
)

if [ "${LANGUAGE_MODEL_ONLY}" = "1" ]; then
  cmd+=(--language-model-only)
fi

exec "${cmd[@]}"