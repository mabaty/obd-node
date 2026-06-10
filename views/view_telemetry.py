"""Telemetry view — BTI-style dense dual-column engine data.

If OBD2 is connected, shows live readings. Otherwise uses simulated values
so the display stays alive on a non-car Pi.

Layout at 128×128 (monospace 11pt data, 9pt labels):
  Row 0: header "TELEMETRY"
  Rows 1-6: dual-column data (label + value left, label + value right)
  Footer: IP address
"""
import random
import socket

from PIL import ImageFont

import config

try:
    import obd as _obd
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "TELEMETRY"
REFRESH_SEC = 1.0

_connection = None


def _connect():
    global _connection
    if _connection is not None:
        return _connection
    if not _OBD_AVAILABLE or config.OBD_DISABLED:
        return None
    try:
        if config.OBD_PORT:
            _connection = _obd.OBD(config.OBD_PORT, fast=False)
        else:
            _connection = _obd.OBD(fast=False)
        if not _connection.is_connected():
            _connection = None
    except Exception:
        _connection = None
    return _connection


def _query(cmd):
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
    cache = ctx.setdefault("_obd_cache", {})
    v = cache.get(key, random.uniform(lo, hi))
    v += random.uniform(-jitter, jitter)
    v = max(lo, min(hi, v))
    cache[key] = v
    return v


def _get_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return "?"
        finally:
            s.close()


def _thresh_color(val, warn, danger, normal=(255, 255, 255),
                  warn_color=(251, 191, 36), danger_color=(251, 113, 133)):
    if val is None:
        return normal
    if val >= danger:
        return danger_color
    if val >= warn:
        return warn_color
    return normal


def render(draw, ctx):
    f_md = ctx["font_md"]   # 11pt mono — primary data
    f_sm = ctx["font_sm"]   # 9pt mono — labels
    f_xs = ctx["font_xs"]   # 8pt mono — footer

    live = _OBD_AVAILABLE and not config.OBD_DISABLED and _connect() is not None

    if live:
        rpm = int(_query(_obd.commands.RPM) or 0)
        iat = _query(_obd.commands.INTAKE_TEMP)
        coolant = _query(_obd.commands.COOLANT_TEMP)
        voltage = _query(_obd.commands.CONTROL_MODULE_VOLTAGE)
        throttle = _query(_obd.commands.THROTTLE_POS)
        map_val = _query(_obd.commands.MAF)  # or MAP if available
        iat_f = int(iat * 9 / 5 + 32) if iat is not None else None
        coolant_f = int(coolant * 9 / 5 + 32) if coolant is not None else None
    else:
        rpm = int(_fake(ctx, "rpm", 800, 6500, jitter=150))
        iat_f = int(_fake(ctx, "iat", 80, 165, jitter=2))
        coolant_f = int(_fake(ctx, "coolant", 180, 215, jitter=1))
        voltage = _fake(ctx, "voltage", 13.6, 14.4, jitter=0.05)
        throttle = int(_fake(ctx, "throttle", 5, 60, jitter=4))
        map_val = int(_fake(ctx, "map", -8, 32, jitter=2))

    # Layout constants
    L_MARGIN = 2       # left edge
    R_COL = 66         # right column x-start
    ROW_H = 16         # vertical step per data row
    HDR_Y = 2          # header top
    DATA_START = 18    # first data row y
    FOOTER_Y = 119     # footer baseline

    # --- Header ---
    draw.text((64, HDR_Y), "TELEMETRY", font=ctx["font_lg"],
              fill=(251, 191, 36), anchor="mt")
    draw.line([(2, 15), (125, 15)], fill=(42, 42, 51), width=1)

    # --- Data rows (left column / right column) ---

    def row(y, l_label, l_val, l_fmt, r_label, r_val, r_fmt,
            l_warn=None, l_danger=None, r_warn=None, r_danger=None):
        # Left
        draw.text((L_MARGIN, y), l_label, font=f_sm, fill=(110, 108, 100))
        l_color = (255, 255, 255)
        if l_warn is not None and l_val is not None:
            l_color = _thresh_color(l_val, l_warn, l_danger or 9999)
        l_text = l_fmt.format(l_val) if l_val is not None else "--"
        draw.text((L_MARGIN + 30, y), l_text, font=f_md, fill=l_color)
        # Right
        draw.text((R_COL, y), r_label, font=f_sm, fill=(110, 108, 100))
        r_color = (255, 255, 255)
        if r_warn is not None and r_val is not None:
            r_color = _thresh_color(r_val, r_warn, r_danger or 9999)
        r_text = r_fmt.format(r_val) if r_val is not None else "--"
        draw.text((R_COL + 30, y), r_text, font=f_md, fill=r_color)

    y = DATA_START

    # Row 1: RPM (left) / IAT (right)
    rpm_color = _thresh_color(rpm, 5500, 6500)
    draw.text((L_MARGIN, y), "RPM", font=f_sm, fill=(110, 108, 100))
    draw.text((L_MARGIN + 30, y), f"{rpm}", font=f_md, fill=rpm_color)
    iat_color = _thresh_color(iat_f, 140, 160) if iat_f is not None else (255, 255, 255)
    draw.text((R_COL, y), "IAT", font=f_sm, fill=(110, 108, 100))
    draw.text((R_COL + 30, y),
              f"{iat_f}F" if iat_f is not None else "--",
              font=f_md, fill=iat_color)

    y += ROW_H
    # Row 2: COOLANT (left) / BATT (right)
    cool_color = _thresh_color(coolant_f, 210, 225) if coolant_f is not None else (255, 255, 255)
    draw.text((L_MARGIN, y), "COOL", font=f_sm, fill=(110, 108, 100))
    draw.text((L_MARGIN + 30, y),
              f"{coolant_f}F" if coolant_f is not None else "--",
              font=f_md, fill=cool_color)
    batt_color = (74, 222, 128) if voltage is not None and voltage >= 13.0 else (251, 113, 133)
    draw.text((R_COL, y), "BATT", font=f_sm, fill=(110, 108, 100))
    draw.text((R_COL + 30, y),
              f"{voltage:.1f}V" if voltage is not None else "--",
              font=f_md, fill=batt_color)

    y += ROW_H
    # Row 3: THROTTLE (left) / MAP (right)
    draw.text((L_MARGIN, y), "THR", font=f_sm, fill=(110, 108, 100))
    draw.text((L_MARGIN + 30, y),
              f"{int(throttle)}%" if throttle is not None else "--",
              font=f_md, fill=(251, 191, 36))
    draw.text((R_COL, y), "MAP", font=f_sm, fill=(110, 108, 100))
    draw.text((R_COL + 30, y),
              f"{map_val}" if map_val is not None else "--",
              font=f_md, fill=(255, 255, 255))

    y += ROW_H
    # Row 4: AFR placeholder (left) / status (right)
    draw.text((L_MARGIN, y), "AFR", font=f_sm, fill=(110, 108, 100))
    draw.text((L_MARGIN + 30, y), "--", font=f_md, fill=(110, 108, 100))
    draw.text((R_COL, y), "OBD2", font=f_sm, fill=(110, 108, 100))
    obd_status = "LIVE" if live else "SIM"
    obd_color = (74, 222, 128) if live else (110, 108, 100)
    draw.text((R_COL + 30, y), obd_status, font=f_md, fill=obd_color)

    # --- Separator ---
    draw.line([(2, y + ROW_H + 2), (125, y + ROW_H + 2)], fill=(42, 42, 51), width=1)

    # --- Footer: IP ---
    ip = _get_ip()
    draw.text((64, FOOTER_Y), ip, font=f_xs, fill=(96, 165, 250), anchor="mb")
