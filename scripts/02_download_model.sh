#!/usr/bin/env bash
set -euo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${WORKDIR}/.venv"
MODEL_ID="${MODEL_ID:-google/gemma-4-E4B-it}"
MODEL_DIR="${MODEL_DIR:-${WORKDIR}/models/google/gemma-4-E4B-it}"
HF_HOME="${HF_HOME:-${WORKDIR}/.hf-home}"

if [ ! -x "${VENV_DIR}/bin/hf" ]; then
  echo "Missing ${VENV_DIR}/bin/hf. Run scripts/01_install_base_tools.sh first." >&2
  exit 1
fi

mkdir -p "${MODEL_DIR}" "${HF_HOME}"

export HF_HOME

if [ -n "${HF_TOKEN:-}" ]; then
  export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
fi

"${VENV_DIR}/bin/hf" download "${MODEL_ID}" \
  --local-dir "${MODEL_DIR}" \
  --repo-type model

echo "Model downloaded to ${MODEL_DIR}"