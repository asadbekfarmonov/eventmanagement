#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git rsync cron

# Optional but recommended firewall for SSH only (adjust if needed)
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH || true
  ufw --force enable || true
fi

echo "VM bootstrap complete."
