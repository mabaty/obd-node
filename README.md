# obd-node

Raspberry Pi multi-view display node with an optional OBD2 car-data view.

Drives a **GC9A01 240×240 round SPI display** and cycles between view
modules via a single tactile button. Comes with three views out of the box:

- **STATUS** — host stats: hostname, CPU temp, IP, uptime
- **OBD2** — speed / coolant / battery voltage / throttle (live via
  `python-OBD` if the optional dep is installed and a dongle is reachable,
  otherwise simulated)
- **RPM** — big-text RPM gauge with color-shifting arc (live or simulated)

Tested on Raspberry Pi 5 (Bookworm).

![demo placeholder — add a photo once you have one]()

## Hardware

### Display (GC9A01, 240×240 round, SPI)

| Display | Pi pin | GPIO | Notes |
|---|---|---|---|
| VCC | 1 | 3.3V | |
| GND | 6 | GND | |
| SCL/CLK | 23 | GPIO11 (SCLK) | |
| SDA/MOSI | 19 | GPIO10 | |
| RES | 22 | GPIO25 | |
| DC | 18 | GPIO24 | |
| CS | **40** | **GPIO21** | non-default — see boot config below |
| BL | 12 | GPIO18 | **100Ω resistor in series, mandatory** |

> The 100Ω BL series resistor isn't optional. Driving the backlight LEDs
> directly off 3.3V will cook the panel.

### Button

| Button leg | Pi pin | GPIO | Notes |
|---|---|---|---|
| One side | 36 | GPIO16 | input, pull-up (in software) |
| Other side | 34 | GND | |

Any momentary tactile switch works. With a 4-pin tactile switch, pick legs
on opposite sides of the long edge (the two pins on the same short edge
are shorted together internally).

Override `BUTTON_PIN` / `BUTTON_CHIP` in `config.py` to use a different
GPIO line.

### OBD2 (optional)

Any ELM327-compatible USB or Bluetooth dongle. Bluetooth dongles need to
be paired and bound to an `rfcomm` device before launch; set `OBD_PORT` in
`config.py` to point at the serial node (e.g. `/dev/rfcomm0`,
`/dev/ttyUSB0`).

## Install

On a fresh Pi (Raspberry Pi OS Bookworm or newer — tested on Debian 13 / Trixie):

> Note: `apt-packages.txt` lists `python3-libgpiod` (Trixie name). On older
> Bookworm installs the package may still be named `python3-gpiod` — edit
> the file accordingly before running `install.sh`.

```bash
git clone https://github.com/mabaty/obd-node.git ~/obd-node
cd ~/obd-node
./install.sh
sudo reboot   # only the first time (for the SPI overlay)
```

`install.sh` is idempotent and safe to re-run. Flags:

- `--no-optional` — skip the `python-OBD` pip install
- `--no-systemd` — don't install or enable the systemd unit

After reboot, the service comes up automatically. View logs:

```bash
sudo journalctl -u obd-node -f
```

## Update

```bash
cd ~/obd-node
./update.sh           # git pull + restart service
./update.sh --full    # also re-runs install.sh (apt + pip)
```

## Shell aliases

Quick management shortcuts (`obd-status`, `obd-logs`, `obd-restart`,
`obd-update`, `obd-debug`, `obd-cli`, ...). Source the file from your
`~/.bashrc`:

```bash
echo '[ -f "$HOME/obd-node/shell-aliases.sh" ] && source "$HOME/obd-node/shell-aliases.sh"' >> ~/.bashrc
source ~/.bashrc
```

See [shell-aliases.sh](shell-aliases.sh) for the full list.

## Customize

Edit `~/obd-node/config.py` (created from `config.example.py` on first
install — it's gitignored so your tweaks survive updates).

Common changes:

- **Different button pin:** set `BUTTON_PIN`
- **Different view order or subset:** edit `ENABLED_VIEWS`
- **Force-disable OBD2:** set `OBD_DISABLED = True` (uses simulated values
  even if the dongle is plugged in — useful for testing on the bench)
- **OBD2 port:** set `OBD_PORT = "/dev/rfcomm0"` (or similar)

Restart the service after editing config:

```bash
sudo systemctl restart obd-node
```

## Write your own view

Drop a new module in `views/`, e.g. `views/view_weather.py`:

```python
NAME = "WEATHER"
REFRESH_SEC = 60.0

def render(draw, ctx):
    f_lg = ctx["font_lg"]
    draw.text((120, 120), "72°F", font=f_lg, fill=(255, 255, 255), anchor="mm")
```

Then add `"view_weather"` to `ENABLED_VIEWS` in `config.py` and restart.

The `ctx` dict carries pre-loaded fonts (`font_xl`, `font_lg`, `font_md`,
`font_sm`) and is a safe place to cache per-view state across frames.

## Uninstall

```bash
sudo systemctl disable --now obd-node
sudo rm /etc/systemd/system/obd-node.service
sudo systemctl daemon-reload
rm -rf ~/obd-node
```

The boot config snippet stays in `/boot/firmware/config.txt` unless you
remove it by hand — harmless on its own.

## Known gotchas

See [findings/lenox-mobile-display.md](https://github.com/mabaty/lenox-docs/blob/main/findings/lenox-mobile-display.md)
in the lenox-docs repo for the full debugging story. Highlights:

- **`lgpio` defaults output pins to LOW** when claimed, even if you intend
  ACTIVE. Use `gpiod` 2.x instead. (Already done in this repo.)
- **GC9A01 clones often need SPI mode 3, not mode 0.**
- **Don't manually toggle CS** when the `spi0-1cs` overlay manages it.
- **Camera autodetect (`camera_auto_detect=1`)** claims GPIO 22/24/25/27
  at boot — collides with the display's RES/DC pins unless you disable
  the camera or pick different pins.

## License

[MIT](LICENSE). The GC9A01 init sequence is adapted from Waveshare's
BSD-3-licensed sample code — see [NOTICE](NOTICE).
