"""Status view — node operational health.

Shows hostname, CPU temp, status, IP, uptime, CPU load, disk usage.
Rectangular layout for 128×128 display.
"""
import socket
import subprocess

import config

NAME = "STATUS"
REFRESH_SEC = 5.0


def _sh(cmd, default="?"):
    try:
        return subprocess.check_output(cmd, shell=True, timeout=3).decode().strip()
    except Exception:
        return default


def _short_uptime():
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


def _cpu_load():
    """Return 1-minute load average as percentage of 400% (4 cores on Pi 5)."""
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        return int(load1 / 4 * 100)
    except Exception:
        return -1


def _disk_pct():
    try:
        out = subprocess.check_output(
            ["df", "--output=pcent", "/"], timeout=3).decode()
        return out.strip().split("\n")[1].strip().replace("%", "")
    except Exception:
        return "?"


def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "?"


def render(draw, ctx):
    f_md = ctx["font_md"]   # 11pt mono
    f_sm = ctx["font_sm"]   # 9pt mono
    f_xs = ctx["font_xs"]   # 8pt mono
    f_lg = ctx["font_lg"]   # 14pt bold

    hostname = socket.gethostname()
    temp = _sh("cat /sys/class/thermal/thermal_zone0/temp | awk '{printf \"%.0f\", $1/1000}'")
    ip = _get_ip()
    up = _short_uptime()
    cpu = _cpu_load()
    disk = _disk_pct()

    # Layout
    L = 2
    R_COL = 66
    HDR_Y = 2
    DATA_START = 18
    ROW_H = 14
    FOOTER_Y = 119

    # Header — hostname
    draw.text((64, HDR_Y), hostname, font=f_lg,
              fill=(251, 113, 133), anchor="mt")
    draw.line([(2, 15), (125, 15)], fill=(42, 42, 51), width=1)

    y = DATA_START

    # TEMP (left) / STATUS (right)
    temp_color = (74, 222, 128)
    try:
        if int(temp) >= 75:
            temp_color = (251, 191, 36)
        if int(temp) >= 80:
            temp_color = (251, 113, 133)
    except ValueError:
        pass
    draw.text((L, y), "TEMP", font=f_sm, fill=(110, 108, 100))
    draw.text((L + 30, y), f"{temp}C", font=f_md, fill=temp_color)
    draw.text((R_COL, y), "STATUS", font=f_sm, fill=(110, 108, 100))
    draw.text((R_COL + 30, y), "ONLINE", font=f_md, fill=(74, 222, 128))

    y += ROW_H
    # CPU (left) / DISK (right)
    cpu_color = (255, 255, 255)
    if cpu >= 0:
        if cpu >= 80:
            cpu_color = (251, 113, 133)
        elif cpu >= 50:
            cpu_color = (251, 191, 36)
        draw.text((L, y), "CPU", font=f_sm, fill=(110, 108, 100))
        draw.text((L + 30, y), f"{cpu}%", font=f_md, fill=cpu_color)
    else:
        draw.text((L, y), "CPU", font=f_sm, fill=(110, 108, 100))
        draw.text((L + 30, y), "--", font=f_md, fill=(110, 108, 100))
    draw.text((R_COL, y), "DISK", font=f_sm, fill=(110, 108, 100))
    draw.text((R_COL + 30, y), f"{disk}%", font=f_md, fill=(255, 255, 255))

    y += ROW_H
    # Separator
    draw.line([(2, y), (125, y)], fill=(42, 42, 51), width=1)
    y += 3

    # IP
    draw.text((L, y), "IP", font=f_sm, fill=(110, 108, 100))
    draw.text((L + 30, y), ip, font=f_md, fill=(96, 165, 250))

    y += ROW_H
    # UPTIME
    draw.text((L, y), "UP", font=f_sm, fill=(110, 108, 100))
    draw.text((L + 30, y), up, font=f_md, fill=(255, 255, 255))

    # Footer
    draw.text((64, FOOTER_Y), ip, font=f_xs, fill=(96, 165, 250), anchor="mb")
