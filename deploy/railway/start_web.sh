#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1

python - <<'PY'
import os
from pathlib import Path

raw = os.getenv("DATABASE_PATH", "data/bot.db")
p = Path(raw).resolve()
print(f"[DB_DIAG] raw_DATABASE_PATH={raw!r}")
print(f"[DB_DIAG] resolved_DATABASE_PATH={str(p)!r}")
print(f"[DB_DIAG] parent={str(p.parent)!r} parent_writable={os.access(p.parent, os.W_OK)}")
PY

exec python -m ticketbot.miniapp_server
