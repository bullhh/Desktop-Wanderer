#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREBUILT_DIR="${DW_UVC_PREBUILT_DIR:-${PROJECT_ROOT}/thirdparty/prebuilt/starry/aarch64/lib}"

echo "Checking Starry runtime environment"
echo "Using prebuilt dir: ${PREBUILT_DIR}"

missing=0

check_file() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    echo "  OK  ${path}"
  else
    echo "  MISS ${path}"
    missing=1
  fi
}

check_glob() {
  local pattern="$1"
  shopt -s nullglob
  local matches=(${pattern})
  shopt -u nullglob
  if (( ${#matches[@]} > 0 )); then
    echo "  OK  ${pattern}"
  else
    echo "  MISS ${pattern}"
    missing=1
  fi
}

check_file "${PREBUILT_DIR}/libdw_uvc_camera.so"
check_glob "${PREBUILT_DIR}/libuvc.so*"
check_glob "${PREBUILT_DIR}/libusb-1.0.so*"
check_file "${PROJECT_ROOT}/src/yolov/models/tennis.rknn"

if command -v python >/dev/null 2>&1; then
  python - <<'PY'
import importlib.util
modules = ["numpy"]
for name in modules:
    print(f"  {'OK ' if importlib.util.find_spec(name) else 'MISS'} python module: {name}")
PY
else
  echo "  MISS python"
  missing=1
fi

if [[ "${missing}" -ne 0 ]]; then
  echo "Runtime environment is incomplete."
  exit 1
fi

echo "Runtime environment looks ready."
