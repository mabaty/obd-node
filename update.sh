#!/usr/bin/env bash
# obd-node updater. Pulls the latest commit and restarts the service.
#
# Exits non-zero (and prints clearly) if any step fails — especially the
# systemctl restart, which previously could fail silently when sudo
# couldn't prompt for a password.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

SERVICE_NAME="obd-node.service"

echo "==> git pull"
OLD_HEAD=$(git rev-parse HEAD)
git pull --ff-only
NEW_HEAD=$(git rev-parse HEAD)

if [[ "$OLD_HEAD" == "$NEW_HEAD" ]]; then
  echo "    (already at $NEW_HEAD — no new commits)"
else
  echo "    $OLD_HEAD -> $NEW_HEAD"
fi

if [[ "${1:-}" == "--full" ]]; then
  echo "==> re-running install.sh (--full)"
  exec ./install.sh
fi

# `systemctl cat` exits 0 if the unit exists, non-zero (with message on
# stderr) if not — more reliable than parsing list-unit-files in a pipe
# under set -e / pipefail.
if ! systemctl cat "$SERVICE_NAME" >/dev/null 2>&1; then
  echo "ERROR: ${SERVICE_NAME} is not installed. Run ./install.sh first." >&2
  exit 1
fi

PRE_PID=$(systemctl show -p MainPID --value "$SERVICE_NAME" || echo 0)
echo "==> sudo systemctl restart ${SERVICE_NAME}  (was PID ${PRE_PID})"

# -n makes sudo fail fast instead of trying to prompt when stdin isn't a TTY.
# If it fails, retry interactively so the user sees the password prompt.
if ! sudo -n systemctl restart "$SERVICE_NAME" 2>/dev/null; then
  echo "    (sudo needs your password)"
  sudo systemctl restart "$SERVICE_NAME"
fi

sleep 1
POST_PID=$(systemctl show -p MainPID --value "$SERVICE_NAME" || echo 0)
STATE=$(systemctl show -p ActiveState --value "$SERVICE_NAME" || echo unknown)

if [[ "$STATE" != "active" ]]; then
  echo "ERROR: ${SERVICE_NAME} is in state '${STATE}' after restart." >&2
  sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -20 >&2
  exit 2
fi

if [[ "$PRE_PID" == "$POST_PID" && "$PRE_PID" != "0" ]]; then
  echo "ERROR: PID did not change (${PRE_PID}). Restart may not have taken." >&2
  exit 3
fi

echo "==> ${SERVICE_NAME} active, new PID ${POST_PID}"
