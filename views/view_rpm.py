"""RPM gauge view.

Live RPM via python-OBD if available; otherwise a sweeping fake value so
the gauge animation remains visible on a non-car Pi.
"""
import time

import config

try:
    import obd as _obd
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "RPM"
REFRESH_SEC = 0.1  # gauge should feel live

RPM_MAX = 7000  # tune per-vehicle

_connection = None


def _connect():
    global _connection
    if _connection is not None:
        return _connection
    if not _OBD_AVAILABLE or config.OBD_DISABLED:
        return None
    try:
        if config.OBD_PORT:
            _connection = _obd.OBD(config.OBD_PORT, fast=True)
        else:
            _connection = _obd.OBD(fast=True)
        if not _connection.is_connected():
            _connection = None
    except Exception:
        _connection = None
    return _connection


def _fake_rpm():
    """Sweep 800 -> 6500 -> 800 over ~6 seconds."""
    period = 6.0
    t = (time.time() % period) / period
    tri = 2 * t if t < 0.5 else 2 * (1 - t)
    return int(800 + tri * (6500 - 800))


def render(draw, ctx):
    f_sm = ctx["font_sm"]
    f_xl = ctx["font_xl"]

    conn = _connect()
    rpm = None
    if conn is not None:
        try:
            r = conn.query(_obd.commands.RPM)
            if not r.is_null():
                rpm = int(r.value.magnitude)
        except Exception:
            rpm = None
    if rpm is None:
        rpm = _fake_rpm()
        live = False
    else:
        live = True

    # Outer ring + gauge track
    draw.ellipse([2, 2, 237, 237], outline=(60, 60, 80), width=2)
    draw.arc([8, 8, 231, 231], start=150, end=30, fill=(42, 42, 51), width=22)

    frac = min(1.0, max(0.0, rpm / RPM_MAX))
    sweep_deg = 240 * frac
    end_angle = (150 + sweep_deg) % 360
    if frac < 0.6:
        fill = (74, 222, 128)
    elif frac < 0.85:
        fill = (251, 191, 36)
    else:
        fill = (251, 113, 133)
    if sweep_deg > 1:
        draw.arc([8, 8, 231, 231], start=150, end=end_angle, fill=fill, width=22)

    # Labels: small "RPM" up top, big number center, redline reference bottom
    draw.text((120, 70), "RPM" if live else "RPM (sim)",
              font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((120, 132), f"{rpm}", font=f_xl, fill=(255, 255, 255), anchor="mm")
    draw.text((120, 188), f"/ {RPM_MAX}", font=f_sm, fill=(110, 108, 100), anchor="mm")
