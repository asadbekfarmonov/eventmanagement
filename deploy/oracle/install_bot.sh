#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-}"
APP_DIR="/opt/eventmanagement"
RUN_USER="ubuntu"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

id -u "${RUN_USER}" >/dev/null 2>&1 || {
  echo "User '${RUN_USER}' not found."
  exit 1
}

if [[ ! -d "${APP_DIR}" ]]; then
  if [[ -z "${REPO_URL}" ]]; then
    echo "Usage: $0 <git_repo_url>"
    exit 1
  fi
  git clone "${REPO_URL}" "${APP_DIR}"
elif [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "${APP_DIR} exists but is not a git repository."
  echo "Move it away manually, then rerun this script."
  exit 1
fi

chown -R "${RUN_USER}:${RUN_USER}" "${APP_DIR}"

sudo -u "${RUN_USER}" bash -lc "
  set -euo pipefail
  cd '${APP_DIR}'
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  mkdir -p data backups
"

if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chown "${RUN_USER}:${RUN_USER}" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env. Edit it before starting the service."
fi

echo "Bot files and virtualenv are ready at ${APP_DIR}."
