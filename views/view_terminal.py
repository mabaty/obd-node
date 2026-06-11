"""Terminal view — live mirror of the Pi's HDMI console (tty1).

Reads /dev/vcsa1 every refresh and renders a viewport of the active
text-mode console. This is what you'd see if you plugged an HDMI
monitor + USB keyboard into the Pi for emergency troubleshooting.

Required:
- User must be in the `tty` group (one-time: sudo usermod -aG tty matt)
- Console must be active on tty1 (default on Debian/Pi OS Lite)

The /dev/vcsa1 device exposes a 4-byte header (rows, cols, cur_x, cur_y)
followed by `rows*cols*2` bytes (one char byte + one attr byte per cell).
We follow the cursor: the visible window scrolls horizontally and
vertically so the prompt is always on screen.
"""
import os

NAME = "TERM"
REFRESH_SEC = 0.25  # 4 fps — feels live when typing

VCSA_PATH = "/dev/vcsa1"
VIEW_ROWS = 12   # how many text rows we render
VIEW_COLS = 22   # how many text cols fit in 128px at our font


def _read_console():
    """Return (rows, cols, cx, cy, lines[]) or (None, error_str)."""
    try:
        with open(VCSA_PATH, "rb") as f:
            hdr = f.read(4)
            if len(hdr) < 4:
                return None, "short header"
            rows, cols, cx, cy = hdr[0], hdr[1], hdr[2], hdr[3]
            body = f.read(rows * cols * 2)
    except PermissionError:
        return None, "perm denied (tty grp)"
    except FileNotFoundError:
        return None, "no /dev/vcsa1"
    except Exception as e:
        return None, f"err: {e}"

    if len(body) < rows * cols * 2:
        return None, "short body"

    lines = []
    for r in range(rows):
        row_bytes = bytearray()
        base = r * cols * 2
        for c in range(cols):
            ch = body[base + c * 2]
            # Keep printable ASCII; replace control bytes with space
            row_bytes.append(ch if 32 <= ch < 127 else 32)
        lines.append(row_bytes.decode("ascii", errors="replace").rstrip())
    return (rows, cols, cx, cy, lines), None


def _viewport(lines, rows, cols, cx, cy, view_rows, view_cols):
    """Pick view_rows x view_cols slice centered on cursor."""
    # Vertical: cursor near bottom of viewport (terminal-feel)
    bottom = max(view_rows - 1, min(rows - 1, cy + 2))
    top = max(0, bottom - view_rows + 1)
    bottom = min(rows - 1, top + view_rows - 1)

    # Horizontal: cursor 60% across the viewport, clamped
    target_cx_in_view = int(view_cols * 0.6)
    left = max(0, cx - target_cx_in_view)
    left = min(left, max(0, cols - view_cols))

    visible = []
    for r in range(top, bottom + 1):
        raw = lines[r]
        # Pad short lines so slicing is safe
        padded = raw.ljust(cols)
        visible.append(padded[left:left + view_cols].rstrip())

    cur_in_view_x = cx - left
    cur_in_view_y = cy - top
    return visible, cur_in_view_x, cur_in_view_y


def render(draw, ctx):
    f_xs = ctx["font_xs"]  # 8pt mono
    f_lg = ctx["font_lg"]  # 14pt bold

    # Header
    draw.text((2, 2), "TERM", font=f_lg, fill=(251, 191, 36))
    draw.line([(2, 16), (125, 16)], fill=(42, 42, 51), width=1)

    data, err = _read_console()
    if err:
        # Fallback: show why we can't read the console
        draw.text((2, 24), "Console mirror", font=f_xs, fill=(251, 113, 133))
        draw.text((2, 36), "unavailable:", font=f_xs, fill=(251, 113, 133))
        draw.text((2, 50), err, font=f_xs, fill=(200, 200, 200))
        draw.text((2, 74), "Fix: usermod -aG", font=f_xs, fill=(110, 108, 100))
        draw.text((2, 84), "  tty matt", font=f_xs, fill=(110, 108, 100))
        draw.text((2, 94), "then reboot", font=f_xs, fill=(110, 108, 100))
        return

    rows, cols, cx, cy, lines = data
    visible, vcx, vcy = _viewport(lines, rows, cols, cx, cy, VIEW_ROWS, VIEW_COLS)

    # Render text
    y0 = 20
    line_h = 9
    for i, line in enumerate(visible):
        y = y0 + i * line_h
        if y > 116:
            break
        draw.text((2, y), line, font=f_xs, fill=(200, 200, 200))

    # Render block cursor (yellow underscore) at cursor cell
    if 0 <= vcy < VIEW_ROWS and 0 <= vcx < VIEW_COLS:
        cur_x = 2 + vcx * 6  # ~6px per char at 8pt mono
        cur_y = y0 + vcy * line_h + line_h - 2
        draw.line([(cur_x, cur_y), (cur_x + 5, cur_y)],
                  fill=(251, 191, 36), width=1)

    # Footer: cursor pos + size, in dim grey
    info = f"{cx:02d},{cy:02d} {cols}x{rows}"
    draw.text((64, 119), info, font=f_xs, fill=(110, 108, 100), anchor="mb")
