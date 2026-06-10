#!/usr/bin/env python3
"""obd-node multi-view display app.

Cycles between view modules in views/ on button press. Built for
SSD1351 128x128 RGB OLED (replaces GC9A01 240x240 round display).

Views: Telemetry (BTI-style) → RPM (big number) → Status → Terminal
"""
import importlib
import sys
import os
import time
import signal
import threading
import datetime as dt

# Run from the repo root so relative imports of `views` work, regardless of
# whether systemd or a human launched us.
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)

try:
    import config  # user config (gitignored)
except ImportError:
    print("[obd-node] config.py not found, copying from config.example.py", flush=True)
    import shutil
    shutil.copy(os.path.join(REPO_DIR, "config.example.py"),
                os.path.join(REPO_DIR, "config.py"))
    import config  # noqa: F401

from ssd1351 import SSD1351
from PIL import Image, ImageDraw, ImageFont

import gpiod
from gpiod.line import Direction, Bias, Edge

# Display dimensions — SSD1351 128x128
DISPLAY_W = 128
DISPLAY_H = 128


def _load_views():
    """Import each module named in config.ENABLED_VIEWS, in order."""
    mods = []
    for name in config.ENABLED_VIEWS:
        try:
            mods.append(importlib.import_module(f"views.{name}"))
        except Exception as e:
            print(f"[obd-node] failed to load view {name!r}: {e!r}", flush=True)
    if not mods:
        raise RuntimeError("no views could be loaded — check config.ENABLED_VIEWS")
    return mods


def load_fonts():
    """Load DejaVu Sans + Sans Mono fonts sized for 128x128 display."""
    base_sans = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    base_sans_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    base_mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    base_mono_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

    sizes = {
        # Big number for RPM view
        "font_xl": (base_sans_bold, 36),
        # Large values and section headers
        "font_lg": (base_sans_bold, 14),
        # Primary data font for telemetry rows
        "font_md": (base_mono, 11),
        # Labels and small text
        "font_sm": (base_mono, 9),
        # Tiny footer text
        "font_xs": (base_mono, 8),
    }
    out = {}
    for key, (fname, size) in sizes.items():
        try:
            out[key] = ImageFont.truetype(fname, size)
        except OSError as e:
            print(f"[fonts] FAILED to load {fname}: {e}. "
                  f"Install fonts-dejavu (apt install fonts-dejavu) "
                  f"and restart. Falling back to bitmap default for {key}.",
                  flush=True)
            out[key] = ImageFont.load_default()
    return out


class ButtonListener(threading.Thread):
    """Watches the configured GPIO line for falling edges. On press, advances
    state['idx'] and sets wake_event so the render loop redraws immediately."""

    def __init__(self, state, wake_event, view_count):
        super().__init__(daemon=True)
        self.state = state
        self.wake_event = wake_event
        self.view_count = view_count
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            with gpiod.request_lines(
                config.BUTTON_CHIP,
                consumer="obd-node-btn",
                config={config.BUTTON_PIN: gpiod.LineSettings(
                    direction=Direction.INPUT,
                    bias=Bias.PULL_UP,
                    edge_detection=Edge.FALLING,
                    debounce_period=dt.timedelta(milliseconds=config.BUTTON_DEBOUNCE_MS),
                )},
            ) as req:
                print(f"[button] listening on GPIO{config.BUTTON_PIN}", flush=True)
                while not self._stop.is_set():
                    if req.wait_edge_events(timeout=0.5):
                        for _ in req.read_edge_events():
                            self.state["idx"] = (self.state["idx"] + 1) % self.view_count
                            self.wake_event.set()
        except Exception as e:
            print(f"[button] listener failed: {e!r} (continuing without button)", flush=True)


def main():
    print("[obd-node] starting", flush=True)
    views = _load_views()
    print(f"[obd-node] loaded {len(views)} view(s): {[v.NAME for v in views]}", flush=True)

    d = SSD1351()
    fonts = load_fonts()
    ctx = dict(fonts)

    state = {"idx": 0}
    wake = threading.Event()

    btn = ButtonListener(state, wake, len(views))
    btn.start()

    stop_flag = {"stop": False}

    def handle_sig(*_):
        stop_flag["stop"] = True
        wake.set()

    signal.signal(signal.SIGTERM, handle_sig)
    signal.signal(signal.SIGINT, handle_sig)

    try:
        while not stop_flag["stop"]:
            view = views[state["idx"]]
            img = Image.new("RGB", (DISPLAY_W, DISPLAY_H), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            try:
                view.render(draw, ctx)
            except Exception as e:
                draw.text((64, 64), f"ERR:{view.NAME}",
                          font=fonts["font_sm"], fill=(251, 80, 80), anchor="mm")
                print(f"[render] {view.NAME} raised: {e!r}", flush=True)
            d.show(img)

            wake.wait(timeout=view.REFRESH_SEC)
            wake.clear()
    finally:
        print("[obd-node] stopping, clearing display", flush=True)
        try:
            d.clear()
        except Exception:
            pass
        btn.stop()


if __name__ == "__main__":
    main()
