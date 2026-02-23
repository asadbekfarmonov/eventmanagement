#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
exec python -m ticketbot.miniapp_server
