"""RPM view — big centered number, no decorative arcs.

Just the RPM value, large and color-coded by threshold.
Live via python-OBD if available; otherwise fake sweeping value.
"""
import time

import config

try:
    import obd as _obd
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "RPM"
REFRESH_SEC = 0.1

RPM_MAX = 7000

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
    f_xl = ctx["font_xl"]  # 36pt bold
    f_sm = ctx["font_sm"]   # 9pt mono
    f_xs = ctx["font_xs"]   # 8pt mono

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

    # Color by threshold
    if rpm < 5500:
        rpm_color = (255, 255, 255)
    elif rpm < 6500:
        rpm_color = (251, 191, 36)
    else:
        rpm_color = (251, 113, 133)

    # Label at top
    draw.text((64, 20), "RPM" if live else "RPM (sim)",
              font=f_sm, fill=(110, 108, 100), anchor="mt")

    # Big number centered
    draw.text((64, 68), f"{rpm}",
              font=f_xl, fill=rpm_color, anchor="mm")

    # Redline reference
    draw.text((64, 100), f"/ {RPM_MAX}",
              font=f_sm, fill=(110, 108, 100), anchor="mt")

    # Footer: IP
    ip = _get_ip_cached(ctx)
    draw.text((64, 119), ip, font=f_xs, fill=(96, 165, 250), anchor="mb")


def _get_ip_cached(ctx):
    """Get IP once per view cycle and cache in ctx."""
    if "_ip" not in ctx:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ctx["_ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            ctx["_ip"] = "?"
    return ctx["_ip"]
