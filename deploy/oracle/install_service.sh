#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/eventmanagement"
SERVICE_NAME="eventbot.service"
TEMPLATE_PATH="${APP_DIR}/deploy/oracle/bot.service"
TARGET_PATH="/etc/systemd/system/${SERVICE_NAME}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Missing service template: ${TEMPLATE_PATH}"
  exit 1
fi

cp "${TEMPLATE_PATH}" "${TARGET_PATH}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo "Installed ${SERVICE_NAME}."
echo "Start with: sudo systemctl start ${SERVICE_NAME}"
echo "Check logs: sudo journalctl -u ${SERVICE_NAME} -f"
