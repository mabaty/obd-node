"""RPM view — huge centered number, throttle in header, speed in footer.

Color logic mirrors telemetry view: white default, red at 6500+.
At 7000+ (rev limiter zone) the number flashes red/black at ~5 Hz.
"""
import time

import config

from PIL import ImageFont

try:
    import obd as _obd
    _OBD_AVAILABLE = True
except ImportError:
    _OBD_AVAILABLE = False

NAME = "RPM"
REFRESH_SEC = 0.1

# Custom XL font — bigger than ctx['font_xl'] (36pt) but small enough
# that 4-digit RPM fits inside 128px with edge padding. 46pt DejaVu Sans
# Bold lands a 4-digit value around ~118px wide.
try:
    _RPM_FONT = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42
    )
except OSError:
    _RPM_FONT = None  # fall back to ctx['font_xl']

# Bold mono for THROTTLE / MPH VALUES.
try:
    _HF_BOLD = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 11
    )
except OSError:
    _HF_BOLD = None
# Regular mono for THROTTLE / MPH LABELS.
try:
    _HF_REG = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11
    )
except OSError:
    _HF_REG = None

# Colors
WHITE = (255, 255, 255)
RED = (251, 113, 133)
LABEL = (110, 108, 100)
INFO = (96, 165, 250)
WARN = (251, 191, 36)

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


def _fake_rpm():
    """Sweep 800 -> 7200 -> 800, but hang at 7200 for ~3s so the rev-limiter
    flash is easy to verify on the bench. Total period ~10s."""
    period = 10.0
    hang = 3.0  # seconds spent pinned at 7200
    sweep = period - hang
    t = time.time() % period
    if t < sweep / 2:
        # Ramp up 800 -> 7200
        return int(800 + (t / (sweep / 2)) * (7200 - 800))
    if t < sweep / 2 + hang:
        # Hang at limiter
        return 7200
    # Ramp down 7200 -> 800
    rem = t - (sweep / 2 + hang)
    return int(7200 - (rem / (sweep / 2)) * (7200 - 800))


def render(draw, ctx):
    f_md = ctx["font_md"]   # 11pt mono
    rpm_font = _RPM_FONT or ctx["font_xl"]
    hf_bold = _HF_BOLD or f_md
    hf_reg = _HF_REG or f_md

    live = _OBD_AVAILABLE and not config.OBD_DISABLED and _connect() is not None

    if live:
        rpm = _query(_obd.commands.RPM)
        rpm = int(rpm) if rpm is not None else None
        thr = _query(_obd.commands.THROTTLE_POS)
        spd_kph = _query(_obd.commands.SPEED)
        spd = int(spd_kph * 0.621371) if spd_kph is not None else None
    else:
        rpm = _fake_rpm()
        # Throttle correlates loosely with RPM in the sim
        thr = int(min(100, max(0, (rpm - 800) / (6400) * 100)))
        spd = int((rpm - 800) / 6400 * 90)  # 0-90 mph sweep

    # --- Header: throttle (label grey regular, value white bold) ---
    thr_val = f"{int(thr)}%" if thr is not None else "--"
    # Measure value width to place label flush-left of it.
    val_w = draw.textlength(thr_val, font=hf_bold)
    lbl_w = draw.textlength("THROTTLE ", font=hf_reg)
    total = lbl_w + val_w
    x_left = 64 - total / 2
    draw.text((x_left, 2), "THROTTLE ", font=hf_reg, fill=LABEL, anchor="lt")
    draw.text((x_left + lbl_w, 2), thr_val, font=hf_bold, fill=WHITE, anchor="lt")

    # --- Big RPM number ---
    rpm_display = rpm if rpm is not None else 0
    # Color logic
    if rpm_display >= 7000:
        # Flash at ~5Hz: alternate red / dim red so the number stays
        # readable but is obviously flashing.
        phase = int(time.time() * 5) % 2
        color = RED if phase == 0 else (90, 30, 40)
    elif rpm_display >= 6500:
        color = RED
    else:
        color = WHITE

    rpm_str = f"{rpm_display}" if rpm is not None else "----"
    # Center vertically between throttle (y≈13) and footer (y≈115) → ~64.
    draw.text((64, 64), rpm_str, font=rpm_font, fill=color, anchor="mm")

    # --- Footer: speed (value white bold, MPH label grey regular) ---
    spd_val = f"{spd}" if spd is not None else "--"
    val_w = draw.textlength(spd_val, font=hf_bold)
    lbl_w = draw.textlength(" MPH", font=hf_reg)
    total = val_w + lbl_w
    x_left = 64 - total / 2
    draw.text((x_left, 125), spd_val, font=hf_bold, fill=WHITE, anchor="lb")
    draw.text((x_left + val_w, 125), " MPH", font=hf_reg, fill=LABEL, anchor="lb")
