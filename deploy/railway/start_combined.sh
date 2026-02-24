#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1

python - <<'PY'
import os
from pathlib import Path
from datetime import datetime, timezone

raw = os.getenv("DATABASE_PATH", "data/bot.db")
p = Path(raw)
resolved = p.resolve()
parent = resolved.parent
parent.mkdir(parents=True, exist_ok=True)

probe = parent / ".db_probe"
ts = datetime.now(timezone.utc).isoformat()
with probe.open("a", encoding="utf-8") as f:
    f.write(ts + "\n")

print(f"[DB_DIAG] raw_DATABASE_PATH={raw!r}")
print(f"[DB_DIAG] resolved_DATABASE_PATH={str(resolved)!r}")
print(f"[DB_DIAG] parent_exists={parent.exists()} parent_is_dir={parent.is_dir()} parent_writable={os.access(parent, os.W_OK)}")
print(f"[DB_DIAG] db_exists={resolved.exists()} db_size_bytes={(resolved.stat().st_size if resolved.exists() else 0)}")
print(f"[DB_DIAG] probe_path={str(probe)!r} probe_size_bytes={probe.stat().st_size}")
PY

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
