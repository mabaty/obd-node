#!/usr/bin/env bash
# obd-node updater. Pulls the latest commit and restarts the service.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "Pulling latest..."
git pull --ff-only

# Re-run install in case apt-packages.txt or requirements.txt changed. This
# is idempotent and skips the boot-config step if already applied.
if [[ "${1:-}" == "--full" ]]; then
  ./install.sh
else
  echo "Restarting service..."
  if systemctl list-unit-files | grep -q '^obd-node.service'; then
    sudo systemctl restart obd-node.service
    sudo systemctl status obd-node.service --no-pager -l | head -15
  else
    echo "  obd-node.service not installed — run ./install.sh first."
  fi
fi
