"""Status view - host stats (temp, IP, hostname, uptime)."""
import socket
import subprocess

NAME = "STATUS"
REFRESH_SEC = 5.0


def _sh(cmd, default="?"):
    try:
        return subprocess.check_output(cmd, shell=True, timeout=3).decode().strip()
    except Exception:
        return default


def render(draw, ctx):
    f_lg = ctx["font_lg"]
    f_md = ctx["font_md"]
    f_sm = ctx["font_sm"]

    hostname = socket.gethostname()
    temp = _sh("cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'")
    ip = _sh("hostname -I | awk '{print $1}'")
    up = _sh("uptime -p | sed 's/up //'")

    draw.ellipse([4, 4, 235, 235], outline=(60, 60, 80), width=3)

    draw.text((120, 38), "OBD-NODE", font=f_lg, fill=(251, 113, 133), anchor="mm")
    draw.text((120, 70), hostname, font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.line([40, 86, 200, 86], fill=(42, 42, 51), width=1)

    draw.text((60, 110), "TEMP", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((60, 134), f"{temp}\u00b0C", font=f_md, fill=(251, 191, 36), anchor="mm")
    draw.text((180, 110), "STATUS", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((180, 134), "ONLINE", font=f_md, fill=(74, 222, 128), anchor="mm")

    draw.line([40, 154, 200, 154], fill=(42, 42, 51), width=1)
    draw.text((120, 174), "IP", font=f_sm, fill=(110, 108, 100), anchor="mm")
    draw.text((120, 196), ip, font=f_sm, fill=(96, 165, 250), anchor="mm")
    draw.text((120, 218), up, font=f_sm, fill=(110, 108, 100), anchor="mm")
