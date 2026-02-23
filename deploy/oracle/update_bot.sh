#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/eventmanagement"
SERVICE_NAME="eventbot.service"
BRANCH="${1:-main}"
RUN_USER="ubuntu"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

sudo -u "${RUN_USER}" bash -lc "
  set -euo pipefail
  cd '${APP_DIR}'
  git fetch --all --prune
  git checkout '${BRANCH}'
  git pull --ff-only origin '${BRANCH}'
  source .venv/bin/activate
  pip install -r requirements.txt
"

systemctl restart "${SERVICE_NAME}"
echo "Updated code and restarted ${SERVICE_NAME}."
