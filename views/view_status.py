"""Status view - host stats (hostname, temp, IP, uptime)."""
import socket
import subprocess

from PIL import ImageFont

# Title font sized 1 step below font_md (22pt) per Matt's iterative tuning.
# Loaded once at module import.
try:
    _TITLE_FONT = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20
    )
except OSError:
    _TITLE_FONT = None  # fall back to ctx['font_md'] at render time

NAME = "STATUS"
REFRESH_SEC = 5.0


def _sh(cmd, default="?"):
    try:
        return subprocess.check_output(cmd, shell=True, timeout=3).decode().strip()
    except Exception:
        return default


def _short_uptime():
    """Return a compact uptime like '3d 5h 12m' that fits the narrow bottom
    of a round display. Falls back to raw output if /proc/uptime is missing."""
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        d, rem = divmod(int(secs), 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        if d:
            return f"{d}d {h}h {m}m"
        if h:
            return f"{h}h {m}m"
        return f"{m}m"
    except Exception:
        return _sh("uptime -p | sed 's/up //'")


def render(draw, ctx):
    f_md = ctx["font_md"]
    f_sm = ctx["font_sm"]

    hostname = socket.gethostname()
    temp = _sh("cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'")
    ip = _sh("hostname -I | awk '{print $1}'")
    up = _short_uptime()

    draw.ellipse([4, 4, 235, 235], outline=(60, 60, 80), width=3)

    # Title shows live hostname at 20pt bold (another ~10% smaller than the
    # previous font_md). Pulled down to y=58 so longer hostnames have chord
    # room (the circle widens further from the pole).
    title_font = _TITLE_FONT or f_md
    draw.text((120, 58), hostname, font=title_font, fill=(251, 113, 133), anchor="mm")
    draw.line([45, 78, 195, 78], fill=(42, 42, 51), width=1)

    # Temp + status row
    draw.text((70, 100), "TEMP", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((70, 124), f"{temp}\u00b0C", font=f_md, fill=(251, 191, 36), anchor="mm")
    draw.text((170, 100), "STATUS", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((170, 124), "ONLINE", font=f_md, fill=(74, 222, 128), anchor="mm")

    draw.line([45, 150, 195, 150], fill=(42, 42, 51), width=1)

    # IP and uptime - safe widths because they're short
    draw.text((120, 170), "IP", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((120, 190), ip, font=f_sm, fill=(96, 165, 250), anchor="mm")
    draw.text((120, 212), up, font=f_sm, fill=(110, 108, 100), anchor="mm")
