"""Status view — combined Pi hardware + OS + OpenClaw node health.

12-cell grid (matches telemetry layout). At-a-glance: is the Pi healthy,
is the gateway link alive, are we throttled.

Cells (top to bottom, L | R):
  row 0:  NODE pi5-test           STATE ONLINE/OFFLINE
  row 1:  TEMP 46C                VOLT 0.77V
  row 2:  CPU  12%                RAM  5%
  row 3:  DISK 20%                UPTM 2h22
  row 4:  IP 192.168.15.62        (spans both cols)
  row 5:  footer: OC v2026.6.1    THR (throttle flag)
"""
import json
import os
import socket
import subprocess
import time

NAME = "STATUS"
REFRESH_SEC = 2.0

# Colors (match telemetry/rpm palette)
LABEL  = (110, 108, 100)
WHITE  = (220, 220, 220)
GOOD   = (74, 222, 128)
WARN   = (251, 191, 36)
BAD    = (251, 113, 133)
INFO   = (96, 165, 250)
# Neon variants for the big STATE indicator
NEON_GREEN = (57, 255, 20)
NEON_RED   = (255, 49, 49)

NODE_JSON = "/home/matt/.openclaw/node.json"
OC_PKG    = "/home/matt/.nvm/versions/node/v24.16.0/lib/node_modules/openclaw/package.json"


# ----- data collectors -------------------------------------------------------

_cache = {"node": None, "oc_ver": None, "ip": None}


def _node_info():
    if _cache["node"] is None:
        try:
            with open(NODE_JSON) as f:
                d = json.load(f)
            _cache["node"] = {
                "name": d.get("displayName", "?"),
                "gw_host": d.get("gateway", {}).get("host", "?"),
                "gw_port": d.get("gateway", {}).get("port", 0),
            }
        except Exception:
            _cache["node"] = {"name": "?", "gw_host": "?", "gw_port": 0}
    return _cache["node"]


def _oc_version():
    if _cache["oc_ver"] is None:
        try:
            with open(OC_PKG) as f:
                for line in f:
                    if '"version"' in line:
                        _cache["oc_ver"] = line.split('"')[3]
                        break
        except Exception:
            pass
        if _cache["oc_ver"] is None:
            _cache["oc_ver"] = "?"
    return _cache["oc_ver"]


def _gateway_link_up():
    """Check if openclaw-node has an ESTABLISHED tcp conn to the gateway.

    Reads /proc/net/tcp directly so we don't need to shell out to `ss` and
    don't need root.
    """
    info = _node_info()
    host = info.get("gw_host")
    port = info.get("gw_port", 0)
    if not host or not port:
        return False
    try:
        # Resolve gateway host once
        gw_ip = socket.gethostbyname(host)
    except Exception:
        return False

    # Hex-encode target ip:port (little-endian for IP)
    try:
        ip_parts = [int(x) for x in gw_ip.split(".")]
        ip_hex = "".join(f"{b:02X}" for b in reversed(ip_parts))
        port_hex = f"{port:04X}"
        target = f"{ip_hex}:{port_hex}"
    except Exception:
        return False

    try:
        with open("/proc/net/tcp") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) < 4:
                    continue
                # parts[2] = remote_address, parts[3] = state (01 = ESTABLISHED)
                if parts[2] == target and parts[3] == "01":
                    return True
    except Exception:
        return False
    return False


def _cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return None


def _core_volt():
    try:
        out = subprocess.check_output(
            ["vcgencmd", "measure_volts", "core"], timeout=1
        ).decode().strip()
        # "volt=0.7664V"
        return float(out.split("=")[1].rstrip("V"))
    except Exception:
        return None


def _throttle_flags():
    """Returns (flag_hex, ok_bool, short_label)."""
    try:
        out = subprocess.check_output(
            ["vcgencmd", "get_throttled"], timeout=1
        ).decode().strip()
        # "throttled=0x0"
        v = int(out.split("=")[1], 16)
        if v == 0:
            return v, True, "OK"
        # bit 0 = under-volt now, bit 1 = freq capped, bit 2 = throttled,
        # bit 3 = soft temp limit. Bits 16-19 = "has occurred"
        now = v & 0xF
        if now & 0x4:
            return v, False, "THRT"
        if now & 0x1:
            return v, False, "UVLT"
        if now & 0x2:
            return v, False, "CAP"
        if now & 0x8:
            return v, False, "TLMT"
        # only historical flags
        return v, True, "HIST"
    except Exception:
        return None, True, "?"


def _cpu_pct():
    """1-min load average as % of 4 cores."""
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
        return int(load1 / 4 * 100)
    except Exception:
        return None


def _ram_pct():
    try:
        with open("/proc/meminfo") as f:
            mi = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = mi.get("MemTotal", 1)
        avail = mi.get("MemAvailable", total)
        used_pct = int((total - avail) / total * 100)
        return used_pct
    except Exception:
        return None


def _disk_pct():
    try:
        out = subprocess.check_output(
            ["df", "--output=pcent", "/"], timeout=2
        ).decode().strip().split("\n")[1]
        return int(out.strip().rstrip("%"))
    except Exception:
        return None


def _uptime_short():
    try:
        with open("/proc/uptime") as f:
            s = int(float(f.read().split()[0]))
        d, rem = divmod(s, 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        if d:
            return f"{d}d{h}h"
        if h:
            return f"{h}h{m:02d}"
        return f"{m}m"
    except Exception:
        return "?"


def _ip():
    if _cache["ip"] is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            _cache["ip"] = s.getsockname()[0]
            s.close()
        except Exception:
            _cache["ip"] = "?"
    return _cache["ip"]


# ----- render ----------------------------------------------------------------

def render(draw, ctx):
    f_lg = ctx["font_lg"]   # 14pt bold
    f_md = ctx["font_md"]   # 11pt mono
    f_sm = ctx["font_sm"]   # 9pt mono
    f_xs = ctx["font_xs"]   # 8pt mono

    # Collect link status early for header
    link_up = _gateway_link_up()

    # --- Header: STATUS (left, yellow) | ONLINE/OFFLINE (right, neon) ---
    draw.text((2, 0), "STATUS", font=f_sm, fill=WARN, anchor="lt")
    state_str = "ONLINE" if link_up else "OFFLINE"
    state_color = NEON_GREEN if link_up else NEON_RED
    draw.text((125, 0), state_str, font=f_sm, fill=state_color, anchor="rt")
    draw.line([(2, 11), (125, 11)], fill=(42, 42, 51), width=1)

    # Collect data
    node = _node_info()
    temp = _cpu_temp()
    volt = _core_volt()
    cpu = _cpu_pct()
    ram = _ram_pct()
    disk = _disk_pct()
    up = _uptime_short()
    ip = _ip()
    thr_v, thr_ok, thr_label = _throttle_flags()

    # --- 5-row grid centered between header line (y=11) and footer line
    # (y=116). 5 rows × 15px = 75px tall block, ~15px padding top/bottom.
    L_LBL, L_VAL = 2, 28
    R_LBL, R_VAL = 66, 92
    Y0 = 26
    DY = 15

    def cell(x_lbl, x_val, y, lbl, val_str, val_color, val_font=f_md):
        draw.text((x_lbl, y), lbl, font=f_sm, fill=LABEL)
        draw.text((x_val, y), val_str, font=val_font, fill=val_color)

    # Row 0: NODE name (full width)
    name = node["name"][:9]
    cell(L_LBL, L_VAL, Y0 + 0*DY, "NOD", name, WHITE)

    # Row 1: TMP | VLT
    if temp is None:
        temp_str, temp_color = "--", LABEL
    else:
        temp_str = f"{int(temp)}C"
        temp_color = GOOD if temp < 65 else WARN if temp < 75 else BAD
    cell(L_LBL, L_VAL, Y0 + 1*DY, "TMP", temp_str, temp_color)

    volt_str = f"{volt:.2f}" if volt is not None else "--"
    cell(R_LBL, R_VAL, Y0 + 1*DY, "VLT", volt_str, WHITE)

    # Row 2: CPU | RAM
    cpu_str = f"{cpu}%" if cpu is not None else "--"
    cpu_color = GOOD if (cpu or 0) < 50 else WARN if (cpu or 0) < 80 else BAD
    cell(L_LBL, L_VAL, Y0 + 2*DY, "CPU", cpu_str, cpu_color)

    ram_str = f"{ram}%" if ram is not None else "--"
    ram_color = GOOD if (ram or 0) < 60 else WARN if (ram or 0) < 85 else BAD
    cell(R_LBL, R_VAL, Y0 + 2*DY, "RAM", ram_str, ram_color)

    # Row 3: DSK | UPT
    disk_str = f"{disk}%" if disk is not None else "--"
    disk_color = GOOD if (disk or 0) < 75 else WARN if (disk or 0) < 90 else BAD
    cell(L_LBL, L_VAL, Y0 + 3*DY, "DSK", disk_str, disk_color)
    cell(R_LBL, R_VAL, Y0 + 3*DY, "UPT", up, WHITE)

    # Row 4: IP (full width)
    cell(L_LBL, L_VAL, Y0 + 4*DY, "IP", ip, INFO)

    # --- Footer: OC version (left) | throttle flag (right) ---
    draw.line([(2, 116), (125, 116)], fill=(42, 42, 51), width=1)
    draw.text((2, 119), f"OC {_oc_version()}", font=f_xs, fill=LABEL)
    thr_color = GOOD if thr_ok else BAD
    draw.text((125, 119), thr_label, font=f_xs, fill=thr_color, anchor="ra")
