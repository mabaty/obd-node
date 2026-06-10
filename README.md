# obd-node

Multi-view car telemetry + node status display for Raspberry Pi, built around
a **Waveshare 1.5″ SSD1351 128×128 RGB OLED** and a physical button to cycle views.

Four views, inspired by BTI-style race gauges — dense, text-first, threshold-colored:

1. **Telemetry** — dual-column OBD2 data (RPM, IAT, coolant, battery, throttle, MAP)
2. **RPM** — big centered number, color-coded by threshold
3. **Status** — node health (hostname, CPU temp, IP, uptime, load, disk)
4. **Terminal** — tails `/tmp/obd-terminal.log` for remote troubleshooting

## Hardware

- Raspberry Pi 5 (8 GB recommended)
- Waveshare 1.5″ RGB OLED Module (SSD1351, 128×128, 65K color, 4-wire SPI)
- One momentary tactile button (view cycle)

### Wiring — SSD1351 OLED

| OLED Pin | Pi Board Pin | Pi GPIO | Notes |
|---|---|---|---|
| VCC | 1 | 3.3V | |
| GND | 6 | GND | |
| DIN | 19 | GPIO10 (MOSI) | |
| SCL | 23 | GPIO11 (SCLK) | |
| CS | 24 | GPIO8 (CE0) | Default SPI0 CE0 — kernel managed |
| DC | 22 | GPIO25 | |
| RST | 13 | GPIO27 | |

**No backlight pin** — OLED pixels are self-emissive.

⚠️ **If upgrading from the GC9A01 round display**, note these pin changes:
- **CS** moved from GPIO21 (pin 40) → GPIO8 (pin 24)
- **DC** moved from GPIO24 (pin 18) → GPIO25 (pin 22)
- **RST** moved from GPIO25 (pin 22) → GPIO27 (pin 13)
- **No backlight wire** (the GC9A01 had BL on GPIO18)
- Remove the old `dtoverlay=spi0-1cs,cs0_pin=21` from boot config

### Wiring — Button

| Button Leg | Pi Board Pin | GPIO | Notes |
|---|---|---|---|
| Side A | 36 | GPIO16 | Input, pull-up, falling-edge |
| Side B | 34 | GND | |

4-pin tactile switch — pick legs on opposite sides of the long edge.

## Install

```bash
git clone https://github.com/mabaty/obd-node.git ~/obd-node
cd ~/obd-node
sudo ./install.sh        # apt + boot config + pip + systemd
sudo reboot              # first time only (SPI enable)
```

Re-running `install.sh` is safe — every step is idempotent.

## Usage

The systemd service `obd-node` starts on boot:

```bash
sudo systemctl status obd-node
sudo systemctl restart obd-node
sudo journalctl -u obd-node -f
```

Press the button to cycle: Telemetry → RPM → Status → Terminal → Telemetry

### Terminal view

Pipe text to the log file from your phone or laptop:

```bash
ssh matt@192.168.15.62 "echo '> systemctl status obd-node' >> /tmp/obd-terminal.log"
ssh matt@192.168.15.62 "systemctl is-active obd-node >> /tmp/obd-terminal.log"
```

Lines starting with `>` render in yellow (commands), errors in red.

## Configure

Edit `~/obd-node/config.py` (gitignored, created from `config.example.py`):

- `BUTTON_PIN` — GPIO for the cycle button (default 16)
- `ENABLED_VIEWS` — ordered list of view modules
- `OBD_PORT` — serial device for ELM327 (e.g. `/dev/ttyUSB0`)
- `OBD_DISABLED` — force-disable OBD2 even if library is installed

## Update

```bash
cd ~/obd-node && ./update.sh
# or: obd-update (if shell aliases are sourced)
```

Pulls from GitHub and restarts the service. Fails loudly if the restart doesn't take.

## Development

Edit locally on lenox-alpha at `~/.openclaw/workspace/repos/obd-node/`, push to
GitHub, then `obd-update` on the Pi.

### Adding a view

1. Create `views/view_yourname.py` with `NAME`, `REFRESH_SEC`, and `render(draw, ctx)`
2. Add `"view_yourname"` to `config.ENABLED_VIEWS`
3. The `ctx` dict provides fonts: `font_xl` (36pt bold), `font_lg` (14pt bold),
   `font_md` (11pt mono), `font_sm` (9pt mono), `font_xs` (8pt mono)
4. Canvas is 128×128, background is always `(0, 0, 0)`

### Design language

- **Numbers first** — values are the star, labels are just context
- **High contrast** — white values on true-black OLED
- **Threshold coloring** — green (normal) → yellow (warning) → red (danger)
- **No decorative arcs or animations** — pure function
- **IP footer** on every view — always know where the Pi is

## Boot config

The installer appends to `/boot/firmware/config.txt`:

```
dtparam=spi=on
```

No custom SPI overlay needed — CS is on the default GPIO8/CE0.

## Rollback

To revert to the old GC9A01 display, switch to the `gc9a01` git branch or
use the old systemd units still on disk:

```bash
sudo systemctl disable --now obd-node
sudo systemctl enable --now lenox-display   # if still present
```

## License

MIT. SSD1351 init sequence derived from Waveshare demo code (BSD-3).
