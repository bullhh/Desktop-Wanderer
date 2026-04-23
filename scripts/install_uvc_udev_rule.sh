#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <vendor_id_hex> <product_id_hex> [group]"
  echo "Example: sudo $0 0ac8 0346 plugdev"
  exit 1
fi

VENDOR_ID="${1#0x}"
PRODUCT_ID="${2#0x}"
GROUP_NAME="${3:-plugdev}"
RULE_FILE="/etc/udev/rules.d/99-dw-uvc-camera.rules"

cat > "${RULE_FILE}" <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="${VENDOR_ID}", ATTR{idProduct}=="${PRODUCT_ID}", MODE="0660", GROUP="${GROUP_NAME}"
EOF

udevadm control --reload-rules
udevadm trigger

echo "Installed ${RULE_FILE}"
echo "Replug the USB camera, or run: sudo udevadm trigger --attr-match=idVendor=${VENDOR_ID} --attr-match=idProduct=${PRODUCT_ID}"
