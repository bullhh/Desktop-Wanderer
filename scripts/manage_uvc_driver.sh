#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <unbind|bind> <vendor_id_hex> <product_id_hex>"
  echo "Example: sudo $0 unbind 0ac8 0346"
  exit 1
fi

ACTION="$1"
VENDOR_ID="${2#0x}"
PRODUCT_ID="${3#0x}"

if [[ "${ACTION}" != "unbind" && "${ACTION}" != "bind" ]]; then
  echo "Unsupported action: ${ACTION}"
  exit 1
fi

case "${ACTION}" in
  unbind) DRIVER_FILE="/sys/bus/usb/drivers/uvcvideo/unbind" ;;
  bind) DRIVER_FILE="/sys/bus/usb/drivers/uvcvideo/bind" ;;
esac

if [[ ! -w "${DRIVER_FILE}" ]]; then
  echo "Need root permission to write ${DRIVER_FILE}"
  exit 1
fi

FOUND=0

for device_dir in /sys/bus/usb/devices/*; do
  [[ -f "${device_dir}/idVendor" && -f "${device_dir}/idProduct" ]] || continue

  if [[ "$(tr '[:upper:]' '[:lower:]' < "${device_dir}/idVendor")" != "${VENDOR_ID,,}" ]]; then
    continue
  fi
  if [[ "$(tr '[:upper:]' '[:lower:]' < "${device_dir}/idProduct")" != "${PRODUCT_ID,,}" ]]; then
    continue
  fi

  FOUND=1
  echo "Matched USB device: $(basename "${device_dir}")"

  for interface_dir in "${device_dir}":*; do
    [[ -d "${interface_dir}" ]] || continue
    interface_name="$(basename "${interface_dir}")"
    driver_link="${interface_dir}/driver"

    if [[ "${ACTION}" == "unbind" ]]; then
      if [[ -L "${driver_link}" ]] && [[ "$(basename "$(readlink -f "${driver_link}")")" == "uvcvideo" ]]; then
        echo "${interface_name}" > "${DRIVER_FILE}"
        echo "Unbound ${interface_name} from uvcvideo"
      fi
    else
      if [[ ! -L "${driver_link}" ]]; then
        echo "${interface_name}" > "${DRIVER_FILE}"
        echo "Bound ${interface_name} to uvcvideo"
      fi
    fi
  done
done

if [[ "${FOUND}" -eq 0 ]]; then
  echo "No USB device matched ${VENDOR_ID}:${PRODUCT_ID}"
  exit 1
fi
