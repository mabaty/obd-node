#!/usr/bin/env bash
# obd-node installer. Fresh-Pi setup or repair.
#
# Usage:
#   ./install.sh              # full install (apt + pip + boot config + systemd)
#   ./install.sh --no-optional   # skip pip install (no live OBD2)
#   ./install.sh --no-systemd    # skip systemd unit (manual launch only)
#
# Re-running is safe — every step checks idempotency.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
BOOT_CONFIG="/boot/firmware/config.txt"
SERVICE_NAME="obd-node.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

DO_OPTIONAL=1
DO_SYSTEMD=1
for arg in "$@"; do
  case "$arg" in
    --no-optional) DO_OPTIONAL=0 ;;
    --no-systemd) DO_SYSTEMD=0 ;;
    -h|--help)
      sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

need_sudo() {
  if [[ $EUID -ne 0 ]]; then
    echo "This step needs sudo. Re-running with sudo for: $*"
    sudo "$@"
  else
    "$@"
  fi
}

echo "=== obd-node install ==="
echo "Repo dir : $REPO_DIR"
echo "User     : $RUN_USER"
echo

# --- 1. apt packages -------------------------------------------------------
echo "[1/5] Installing system packages..."
PKGS=$(grep -v '^\s*#' "$REPO_DIR/apt-packages.txt" | tr '\n' ' ')
need_sudo apt-get update -qq
# shellcheck disable=SC2086
need_sudo apt-get install -y --no-install-recommends $PKGS
echo

# --- 2. boot config --------------------------------------------------------
echo "[2/5] Checking $BOOT_CONFIG ..."
NEEDS_REBOOT=0
if [[ -f "$BOOT_CONFIG" ]]; then
  # Check for the actual functional line, not the marker comment, so we
  # don't duplicate config if the user already set SPI/CS up manually.
  if ! grep -qE '^\s*dtoverlay=spi0-1cs,cs0_pin=21' "$BOOT_CONFIG"; then
    echo "  Appending SPI + CS overlay lines."
    need_sudo bash -c "cat '$REPO_DIR/boot-config.snippet' >> '$BOOT_CONFIG'"
    NEEDS_REBOOT=1
  else
    echo "  Already configured. Skipping."
  fi
else
  echo "  WARN: $BOOT_CONFIG not found (not a Pi?). Skipping boot config."
fi
echo

# --- 3. user config --------------------------------------------------------
echo "[3/5] User config..."
if [[ ! -f "$REPO_DIR/config.py" ]]; then
  cp "$REPO_DIR/config.example.py" "$REPO_DIR/config.py"
  echo "  Created config.py from config.example.py."
else
  echo "  config.py exists. Not overwriting."
fi
echo

# --- 4. optional pip deps --------------------------------------------------
if [[ $DO_OPTIONAL -eq 1 ]]; then
  echo "[4/5] Installing optional Python deps (live OBD2)..."
  # Honor PEP 668 by using --break-system-packages on Pi OS Bookworm+.
  if pip3 install --help 2>&1 | grep -q break-system-packages; then
    pip3 install --user --break-system-packages -r "$REPO_DIR/requirements.txt"
  else
    pip3 install --user -r "$REPO_DIR/requirements.txt"
  fi
else
  echo "[4/5] Skipping optional Python deps (--no-optional)."
fi
echo

# --- 5. systemd ------------------------------------------------------------
if [[ $DO_SYSTEMD -eq 1 ]]; then
  echo "[5/5] Installing systemd unit..."
  TMP_UNIT=$(mktemp)
  sed \
    -e "s|__USER__|$RUN_USER|g" \
    -e "s|__REPO_DIR__|$REPO_DIR|g" \
    "$REPO_DIR/systemd/${SERVICE_NAME}" > "$TMP_UNIT"
  need_sudo install -m 0644 "$TMP_UNIT" "$SERVICE_DST"
  rm -f "$TMP_UNIT"
  need_sudo systemctl daemon-reload
  need_sudo systemctl enable "$SERVICE_NAME"

  if [[ $NEEDS_REBOOT -eq 1 ]]; then
    echo "  Boot config changed — start the service AFTER you reboot."
  else
    need_sudo systemctl restart "$SERVICE_NAME"
    echo "  Service started."
  fi
else
  echo "[5/5] Skipping systemd (--no-systemd)."
fi
echo

echo "=== Done ==="
if [[ $NEEDS_REBOOT -eq 1 ]]; then
  echo "!! Reboot required for SPI/overlay changes: sudo reboot"
fi
echo "Logs: sudo journalctl -u $SERVICE_NAME -f"
echo "Edit hardware config: $REPO_DIR/config.py"
