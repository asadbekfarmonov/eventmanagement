#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/eventmanagement"
DB_PATH="${APP_DIR}/data/bot.db"
BACKUP_DIR="${APP_DIR}/backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "DB not found: ${DB_PATH}"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${BACKUP_DIR}/bot_${STAMP}.sqlite3"

auto_sqlite3() {
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${DB_PATH}" ".backup '${OUT_FILE}'"
  else
    cp "${DB_PATH}" "${OUT_FILE}"
  fi
}

auto_sqlite3

gzip -f "${OUT_FILE}"

find "${BACKUP_DIR}" -type f -name "bot_*.sqlite3.gz" -mtime +"${RETENTION_DAYS}" -delete

echo "Backup completed: ${OUT_FILE}.gz"
