#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PREBUILT_DIR="${PROJECT_ROOT}/thirdparty/prebuilt/starry/aarch64/lib"
NATIVE_BUILD_DIR="${PROJECT_ROOT}/src/native/uvc_camera/build"

mkdir -p "${PREBUILT_DIR}"

copy_lib() {
  local src="$1"
  local dst_dir="$2"
  local base
  base="$(basename "${src}")"

  cp -L "${src}" "${dst_dir}/${base}"
  if command -v readelf >/dev/null 2>&1; then
    local soname
    soname="$(readelf -d "${src}" 2>/dev/null | awk -F'[][]' '/SONAME/ {print $2; exit}')"
    if [[ -n "${soname}" && "${soname}" != "${base}" ]]; then
      ln -sf "${base}" "${dst_dir}/${soname}"
    fi
  fi
}

find_system_lib() {
  local pattern="$1"
  local path=""

  if command -v ldconfig >/dev/null 2>&1; then
    path="$(ldconfig -p 2>/dev/null | awk -v pat="${pattern}" '$1 ~ pat {print $NF; exit}')"
  fi

  if [[ -z "${path}" ]]; then
    path="$(find /usr/lib /lib -name "${pattern}" 2>/dev/null | head -n 1 || true)"
  fi

  printf '%s' "${path}"
}

if [[ ! -f "${NATIVE_BUILD_DIR}/libdw_uvc_camera.so" ]]; then
  echo "Missing ${NATIVE_BUILD_DIR}/libdw_uvc_camera.so"
  echo "Build it first, for example: cmake -S src/native/uvc_camera -B src/native/uvc_camera/build && cmake --build src/native/uvc_camera/build"
  exit 1
fi

copy_lib "${NATIVE_BUILD_DIR}/libdw_uvc_camera.so" "${PREBUILT_DIR}"

LIBUSB_PATH="$(find_system_lib 'libusb-1.0\\.so')"
if [[ -n "${LIBUSB_PATH}" ]]; then
  copy_lib "${LIBUSB_PATH}" "${PREBUILT_DIR}"
else
  echo "Warning: libusb-1.0.so was not found on this host."
fi

LIBUVC_PATH="$(find_system_lib 'libuvc\\.so')"
if [[ -n "${LIBUVC_PATH}" ]]; then
  copy_lib "${LIBUVC_PATH}" "${PREBUILT_DIR}"
else
  echo "Warning: libuvc.so was not found on this host."
fi

echo "Packaged Starry runtime libraries into ${PREBUILT_DIR}"
