#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1

python -m ticketbot.miniapp_server &
WEB_PID=$!

python bot.py &
BOT_PID=$!

cleanup() {
  kill "${WEB_PID}" "${BOT_PID}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait -n "${WEB_PID}" "${BOT_PID}"
STATUS=$?
cleanup
exit "${STATUS}"
