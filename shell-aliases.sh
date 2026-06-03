# obd-node shell aliases.
#
# Source this file from your shell rc to get quick management commands.
# In ~/.bashrc add:
#   [ -f "$HOME/obd-node/shell-aliases.sh" ] && source "$HOME/obd-node/shell-aliases.sh"
# Then `source ~/.bashrc` (or open a new shell).
#
# Override OBD_NODE_DIR before sourcing if your checkout lives elsewhere.

: "${OBD_NODE_DIR:=$HOME/obd-node}"

# --- Service lifecycle -----------------------------------------------------
alias obd-status='sudo systemctl status obd-node.service --no-pager'
alias obd-start='sudo systemctl start obd-node.service'
alias obd-stop='sudo systemctl stop obd-node.service'
alias obd-restart='sudo systemctl restart obd-node.service'
alias obd-enable='sudo systemctl enable --now obd-node.service'
alias obd-disable='sudo systemctl disable --now obd-node.service'

# --- Logs ------------------------------------------------------------------
alias obd-logs='sudo journalctl -u obd-node.service -f'
alias obd-logs-since='sudo journalctl -u obd-node.service --since'   # e.g. obd-logs-since "1 hour ago"
alias obd-errors='sudo journalctl -u obd-node.service -p err --no-pager'

# --- App management --------------------------------------------------------
alias obd-update='cd "$OBD_NODE_DIR" && ./update.sh'
alias obd-update-full='cd "$OBD_NODE_DIR" && ./update.sh --full'
alias obd-config='${EDITOR:-nano} "$OBD_NODE_DIR/config.py"'
alias obd-cd='cd "$OBD_NODE_DIR"'

# --- Hardware / debug ------------------------------------------------------
# Run the app in the foreground (stops service first, useful for tracing
# crashes or seeing print output live).
obd-debug() {
  sudo systemctl stop obd-node.service
  trap 'sudo systemctl start obd-node.service' RETURN
  python3 "$OBD_NODE_DIR/obd_node.py"
}

# Show what GPIO line the button is bound to and read its current state.
alias obd-btn='python3 -c "import sys; sys.path.insert(0, \"$OBD_NODE_DIR\"); import config; print(f\"button: {config.BUTTON_CHIP} line {config.BUTTON_PIN}\")"'

# --- OBD2 (python-OBD CLI shortcuts; useful when the dongle arrives) -------
# `obd_cli` ships with python-OBD — interactive REPL for raw PID queries.
alias obd-cli='obd_cli'
alias obd-scan='python3 -c "import obd; c=obd.OBD(); print(\"connected:\", c.is_connected()); [print(\" \", cmd) for cmd in sorted(c.supported_commands, key=str)]"'
