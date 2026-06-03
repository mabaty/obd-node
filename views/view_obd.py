"""OBD2 / car data view.

If the optional `obd` Python library is installed AND a dongle is reachable,
shows live data. Otherwise falls back to simulated values so the view still
renders on a non-car Pi.
"""
import random

import config

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
        speed = _query(_obd.commands.SPEED)             # km/h
        coolant = _query(_obd.commands.COOLANT_TEMP)    # C
        voltage = _query(_obd.commands.CONTROL_MODULE_VOLTAGE)
        throttle = _query(_obd.commands.THROTTLE_POS)
        speed_mph = int(speed * 0.621371) if speed is not None else None
        coolant_f = int(coolant * 9 / 5 + 32) if coolant is not None else None
        subtitle = "live"
    else:
        speed_mph = int(_fake(ctx, "speed", 0, 75, jitter=3))
        coolant_f = int(_fake(ctx, "coolant", 180, 215, jitter=1))
        voltage = _fake(ctx, "voltage", 13.6, 14.4, jitter=0.05)
        throttle = int(_fake(ctx, "throttle", 5, 60, jitter=4))
        subtitle = "(simulated)"

    draw.ellipse([4, 4, 235, 235], outline=(60, 60, 80), width=3)

    draw.text((120, 30), "CAR DATA", font=f_lg, fill=(251, 191, 36), anchor="mm")
    draw.text((120, 56), subtitle, font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.line([30, 70, 210, 70], fill=(42, 42, 51), width=1)

    # Speed - left side, big
    draw.text((70, 92), "MPH", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((70, 122), f"{speed_mph if speed_mph is not None else '--'}",
              font=f_lg, fill=(96, 165, 250), anchor="mm")

    # Coolant - right side
    color = (74, 222, 128)
    if coolant_f is not None and coolant_f >= 210:
        color = (251, 113, 133)
    draw.text((170, 92), "COOLANT", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((170, 122),
              f"{coolant_f}\u00b0F" if coolant_f is not None else "--",
              font=f_md, fill=color, anchor="mm")

    draw.line([30, 158, 210, 158], fill=(42, 42, 51), width=1)

    # Voltage - bottom left
    draw.text((70, 178), "BATT", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((70, 204),
              f"{voltage:.1f}V" if voltage is not None else "--",
              font=f_md, fill=(74, 222, 128), anchor="mm")

    # Throttle - bottom right
    draw.text((170, 178), "THROTTLE", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((170, 204),
              f"{int(throttle)}%" if throttle is not None else "--",
              font=f_md, fill=(251, 191, 36), anchor="mm")
