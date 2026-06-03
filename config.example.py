"""obd-node user configuration.

Copy this file to `config.py` (which is gitignored) and edit values to match
your hardware. The install script does the copy for you on first run.
"""

# --- Button ----------------------------------------------------------------

# GPIO line for the view-cycle button (BCM numbering). Wired between this
# pin and GND, with internal pull-up enabled.
BUTTON_PIN = 16

# gpiod chip path. On the Pi 5 the header lines live on gpiochip0.
BUTTON_CHIP = "/dev/gpiochip0"

# Software debounce window for the button. 50 ms is solid for most tactile
# switches; raise to 100 ms if you see double-presses on a sloppy switch.
BUTTON_DEBOUNCE_MS = 50

# --- Views -----------------------------------------------------------------

# Ordered list of view module names (under views/) to cycle through.
# Comment out or reorder to customize. The button cycles top-to-bottom.
ENABLED_VIEWS = [
    "view_status",
    "view_obd",
    "view_rpm",
]

# --- OBD2 (optional) -------------------------------------------------------

# Serial port for the OBD2 adapter (Bluetooth or USB ELM327-style dongle).
# Set to None to auto-detect on first connect attempt.
# Examples: "/dev/rfcomm0" (BT), "/dev/ttyUSB0" (USB), "/dev/ttyACM0".
OBD_PORT = None

# Force-disable OBD2 even if the `obd` library is installed. Useful for
# testing the placeholder views on a non-car Pi without uninstalling the
# python package.
OBD_DISABLED = False
