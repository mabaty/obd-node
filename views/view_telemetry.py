"""Telemetry view — full R53 OBD2 grid, 2 cols × 6 rows = 12 metrics.

Top rows = user priorities (BOOST, IAT, COOLANT, fuel trims).
Falls back to simulated values when OBD is disabled / unavailable so
the screen stays alive on the bench.
"""
import random
import time

import config


def _rpm_color(rpm):
    """Mirror view_rpm: white < 6500, red 6500-6999, flash red↔dim 7000+."""
    if rpm is None:
        return NORMAL
    if rpm >= 7000:
        phase = int(time.time() * 5) % 2
        return BAD if phase == 0 else (90, 30, 40)
    if rpm >= 6500:
        return BAD
    return NORMAL

try:
    import obd as _obd
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "TELEMETRY"
REFRESH_SEC = 0.5

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


# Real R53 (ISO 9141-2) USB ELM327 caps at ~12 PIDs/sec total. With 12
# metrics on this view, that's ~1 full refresh/sec. RPM is the priority
# PID so it gets a fast lane (~10 Hz).
_FAST_PIDS = {"rpm"}
_FAST_INTERVAL = 0.1   # 10 Hz
_SLOW_INTERVAL = 1.0   # 1 Hz (everything else)


def _fake(ctx, key, lo, hi, jitter=2):
    cache = ctx.setdefault("_obd_cache", {})
    stamps = ctx.setdefault("_obd_stamps", {})
    now = time.time()
    interval = _FAST_INTERVAL if key in _FAST_PIDS else _SLOW_INTERVAL
    last = stamps.get(key, 0)
    if key not in cache:
        cache[key] = random.uniform(lo, hi)
        stamps[key] = now
        return cache[key]
    if now - last < interval:
        return cache[key]
    v = cache[key] + random.uniform(-jitter, jitter)
    cache[key] = max(lo, min(hi, v))
    stamps[key] = now
    return cache[key]


def _gather(ctx, live):
    """Return dict of all 12 metrics, live or simulated."""
    if live:
        rpm      = _query(_obd.commands.RPM)
        iat_c    = _query(_obd.commands.INTAKE_TEMP)
        cool_c   = _query(_obd.commands.COOLANT_TEMP)
        map_kpa  = _query(_obd.commands.INTAKE_PRESSURE)
        stft     = _query(_obd.commands.SHORT_FUEL_TRIM_1)
        ltft     = _query(_obd.commands.LONG_FUEL_TRIM_1)
        speed_k  = _query(_obd.commands.SPEED)
        thr      = _query(_obd.commands.THROTTLE_POS)
        tim      = _query(_obd.commands.TIMING_ADVANCE)
        batt     = _query(_obd.commands.CONTROL_MODULE_VOLTAGE)
        load     = _query(_obd.commands.ENGINE_LOAD)
        dtcs     = _query(_obd.commands.GET_DTC)
        dtc_n    = len(dtcs) if isinstance(dtcs, list) else None
    else:
        rpm     = _fake(ctx, "rpm", 800, 7200, jitter=150)
        iat_c   = (_fake(ctx, "iat_f", 80, 165, jitter=2) - 32) * 5/9
        cool_c  = (_fake(ctx, "cool_f", 180, 215, jitter=1) - 32) * 5/9
        map_kpa = _fake(ctx, "map", 30, 165, jitter=3)  # 30 vac → 165 boost
        stft    = _fake(ctx, "stft", -6, 6, jitter=0.5)
        ltft    = _fake(ctx, "ltft", -4, 4, jitter=0.2)
        speed_k = _fake(ctx, "spd", 0, 110, jitter=5)
        thr     = _fake(ctx, "thr", 5, 60, jitter=4)
        tim     = _fake(ctx, "tim", 8, 22, jitter=1)
        batt    = _fake(ctx, "batt", 13.6, 14.4, jitter=0.05)
        load    = _fake(ctx, "load", 20, 80, jitter=3)
        dtc_n   = 0

    # Derived / converted
    boost_psi = (map_kpa / 6.895 - 14.7) if map_kpa is not None else None
    iat_f     = int(iat_c * 9/5 + 32) if iat_c is not None else None
    cool_f    = int(cool_c * 9/5 + 32) if cool_c is not None else None
    speed_mph = int(speed_k * 0.621371) if speed_k is not None else None

    return {
        "boost": boost_psi, "iat": iat_f, "cool": cool_f,
        "stft": stft, "ltft": ltft, "rpm": int(rpm) if rpm is not None else None,
        "spd": speed_mph, "thr": int(thr) if thr is not None else None,
        "tim": int(tim) if tim is not None else None, "batt": batt,
        "load": int(load) if load is not None else None, "dtc": dtc_n,
    }


# Color helpers ---------------------------------------------------------------
LABEL = (110, 108, 100)
NORMAL = (220, 220, 220)
GOOD   = (74, 222, 128)
WARN   = (251, 191, 36)
BAD    = (251, 113, 133)
INFO   = (96, 165, 250)


def _color(val, warn, danger, normal=NORMAL):
    if val is None:
        return LABEL
    if val >= danger:
        return BAD
    if val >= warn:
        return WARN
    return normal


def _fmt(val, fmt, dash="--"):
    return fmt.format(val) if val is not None else dash


def render(draw, ctx):
    f_md = ctx["font_md"]   # 11pt mono — data
    f_sm = ctx["font_sm"]   # 9pt mono  — labels
    f_xs = ctx["font_xs"]   # 8pt mono  — footer
    f_lg = ctx["font_lg"]   # 14pt bold — header

    live = _OBD_AVAILABLE and not config.OBD_DISABLED and _connect() is not None
    d = _gather(ctx, live)

    # --- Header (compact, frees rows for data) ---
    draw.text((64, 0), "TELEMETRY", font=f_sm, fill=WARN, anchor="mt")
    draw.line([(2, 11), (125, 11)], fill=(42, 42, 51), width=1)

    # --- 6 rows × 2 cols grid ---
    # 11pt mono ≈ 6.5px/char. "+18.5" = 5 chars = ~33px. Cells: label col + value col.
    # x positions
    L_LBL, L_VAL = 2, 28
    R_LBL, R_VAL = 66, 92
    # y positions — 6 rows centered between header line (y=11) and
    # footer line (y=116). 6 rows × 15px = 90px tall block, ~7px padding.
    Y0 = 21
    DY = 15

    def cell(x_lbl, x_val, y, lbl, val_str, val_color):
        draw.text((x_lbl, y), lbl, font=f_sm, fill=LABEL)
        draw.text((x_val, y), val_str, font=f_md, fill=val_color)

    # Row 1: BOOST | IAT
    boost = d["boost"]
    boost_str = _fmt(boost, "{:+.1f}") if boost is not None else "--"
    # White in vacuum, green any positive boost.
    boost_color = NORMAL
    if boost is not None and boost > 0:
        boost_color = GOOD
    cell(L_LBL, L_VAL, Y0 + 0*DY, "BST", boost_str, boost_color)

    cell(R_LBL, R_VAL, Y0 + 0*DY, "IAT", _fmt(d["iat"], "{}"), NORMAL)

    # Row 2: H2O (coolant) | LOAD
    # White < 200F, yellow 200-209, red 210+.
    cool = d["cool"]
    if cool is None:
        cool_color = NORMAL
    elif cool >= 210:
        cool_color = BAD
    elif cool >= 200:
        cool_color = WARN
    else:
        cool_color = NORMAL
    cell(L_LBL, L_VAL, Y0 + 1*DY, "H2O", _fmt(cool, "{}"), cool_color)

    cell(R_LBL, R_VAL, Y0 + 1*DY, "LOD", _fmt(d["load"], "{}%"), NORMAL)

    # Row 3: STFT | LTFT
    cell(L_LBL, L_VAL, Y0 + 2*DY, "STF", _fmt(d["stft"], "{:+.0f}%"), NORMAL)
    cell(R_LBL, R_VAL, Y0 + 2*DY, "LTF", _fmt(d["ltft"], "{:+.0f}%"), NORMAL)

    # Row 4: RPM | SPD
    # Mirrors view_rpm color logic, including 7000+ flash.
    rpm = d["rpm"]
    cell(L_LBL, L_VAL, Y0 + 3*DY, "RPM", _fmt(rpm, "{}"), _rpm_color(rpm))
    cell(R_LBL, R_VAL, Y0 + 3*DY, "SPD", _fmt(d["spd"], "{}"), NORMAL)

    # Row 5: THR | TIM
    cell(L_LBL, L_VAL, Y0 + 4*DY, "THR", _fmt(d["thr"], "{}%"), NORMAL)
    cell(R_LBL, R_VAL, Y0 + 4*DY, "TIM", _fmt(d["tim"], "{}"), NORMAL)

    # Row 6: BATT | DTC
    cell(L_LBL, L_VAL, Y0 + 5*DY, "BAT", _fmt(d["batt"], "{:.1f}"), NORMAL)
    # White default, red if any code.
    dtc_color = BAD if (d["dtc"] is not None and d["dtc"] > 0) else NORMAL
    cell(R_LBL, R_VAL, Y0 + 5*DY, "DTC", _fmt(d["dtc"], "{}"), dtc_color)

    # --- Footer: time + OBD status ---
    now = time.strftime("%H:%M")
    status = "LIVE" if live else "SIM"
    status_color = GOOD if live else LABEL
    draw.line([(2, 116), (125, 116)], fill=(42, 42, 51), width=1)
    draw.text((2, 119), now, font=f_xs, fill=LABEL)
    draw.text((125, 119), status, font=f_xs, fill=status_color, anchor="ra")
