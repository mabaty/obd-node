"""OBD2 / car data view.

If the optional `obd` Python library is installed AND a dongle is reachable,
shows live data. Otherwise falls back to simulated values so the view still
renders on a non-car Pi.
"""
import random

from PIL import ImageFont

import config

# Title font sized 25% smaller than the previous font_lg (32pt) per Matt's
# tuning. Loaded once at module import.
try:
    _TITLE_FONT = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24
    )
except OSError:
    _TITLE_FONT = None  # fall back to ctx['font_lg'] at render time

try:
    import obd as _obd  # python-OBD
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "OBD2"
REFRESH_SEC = 1.0

_connection = None  # cached OBD connection


def _connect():
    """Try to open the OBD connection once. Returns None on failure."""
    global _connection
    if _connection is not None:
        return _connection
    if not _OBD_AVAILABLE or config.OBD_DISABLED:
        return None
    try:
        if config.OBD_PORT:
            _connection = _obd.OBD(config.OBD_PORT, fast=False)
        else:
            _connection = _obd.OBD(fast=False)  # auto-detect
        if not _connection.is_connected():
            _connection = None
    except Exception:
        _connection = None
    return _connection


def _query(cmd):
    """Read one PID via the python-OBD API; returns the magnitude or None."""
    conn = _connect()
    if conn is None:
        return None
    try:
        r = conn.query(cmd)
        if r.is_null():
            return None
        return r.value.magnitude
    except Exception:
        return None


def _fake(ctx, key, lo, hi, jitter=2):
    """Slow-walking fake value so the screen looks alive when no OBD."""
    cache = ctx.setdefault("_obd_cache", {})
    v = cache.get(key, random.uniform(lo, hi))
    v += random.uniform(-jitter, jitter)
    v = max(lo, min(hi, v))
    cache[key] = v
    return v


def render(draw, ctx):
    f_lg = ctx["font_lg"]
    f_md = ctx["font_md"]
    f_sm = ctx["font_sm"]

    live = _OBD_AVAILABLE and not config.OBD_DISABLED and _connect() is not None

    if live:
        iat = _query(_obd.commands.INTAKE_TEMP)         # C
        coolant = _query(_obd.commands.COOLANT_TEMP)    # C
        voltage = _query(_obd.commands.CONTROL_MODULE_VOLTAGE)
        throttle = _query(_obd.commands.THROTTLE_POS)
        iat_f = int(iat * 9 / 5 + 32) if iat is not None else None
        coolant_f = int(coolant * 9 / 5 + 32) if coolant is not None else None
        subtitle = "live"
    else:
        # Supercharged R53: IAT swings from ambient (~75 F) to 140-170 F
        # under sustained boost. Wider band makes the placeholder feel real.
        iat_f = int(_fake(ctx, "iat", 80, 165, jitter=2))
        coolant_f = int(_fake(ctx, "coolant", 180, 215, jitter=1))
        voltage = _fake(ctx, "voltage", 13.6, 14.4, jitter=0.05)
        throttle = int(_fake(ctx, "throttle", 5, 60, jitter=4))
        subtitle = "(simulated)"

    # Title pulled down to y=52 so the glyphs sit inside the circle.
    # Dropping the (simulated/live) subtitle to reclaim vertical room.
    title_font = _TITLE_FONT or f_lg
    draw.text((120, 52), "Telemetry", font=title_font, fill=(251, 191, 36), anchor="mm")
    draw.line([45, 78, 195, 78], fill=(42, 42, 51), width=1)

    # Intake air temp - left side. Tints toward red as IAT climbs (heat
    # soak / sustained boost on a supercharged engine).
    iat_color = (96, 165, 250)
    if iat_f is not None and iat_f >= 140:
        iat_color = (251, 191, 36)
    if iat_f is not None and iat_f >= 160:
        iat_color = (251, 113, 133)
    draw.text((70, 100), "IAT", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((70, 124),
              f"{iat_f}\u00b0F" if iat_f is not None else "--",
              font=f_md, fill=iat_color, anchor="mm")

    # Coolant - right side
    color = (74, 222, 128)
    if coolant_f is not None and coolant_f >= 210:
        color = (251, 113, 133)
    draw.text((170, 100), "COOLANT", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((170, 124),
              f"{coolant_f}\u00b0F" if coolant_f is not None else "--",
              font=f_md, fill=color, anchor="mm")

    draw.line([45, 150, 195, 150], fill=(42, 42, 51), width=1)

    # Voltage - bottom left
    draw.text((70, 170), "BATT", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((70, 194),
              f"{voltage:.1f}V" if voltage is not None else "--",
              font=f_md, fill=(74, 222, 128), anchor="mm")

    # Throttle - bottom right
    draw.text((170, 170), "THROTTLE", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((170, 194),
              f"{int(throttle)}%" if throttle is not None else "--",
              font=f_md, fill=(251, 191, 36), anchor="mm")
