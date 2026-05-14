#!/usr/bin/env bash
set -euo pipefail

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${WORKDIR}/.venv"

if [ ! -x "${VENV_DIR}/bin/pip" ]; then
  echo "Missing ${VENV_DIR}. Run scripts/01_install_base_tools.sh first." >&2
  exit 1
fi

"${VENV_DIR}/bin/pip" install --upgrade vllm

echo "vLLM installed in ${VENV_DIR}"
echo "Note: run this on the GPU host that will actually serve the model."