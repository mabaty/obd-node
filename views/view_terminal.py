"""Terminal view — tail /tmp/obd-terminal.log for remote troubleshooting.

Reads the last N lines from a log file and renders them. You pipe
commands and output into the file from your phone or laptop:

    ssh matt@192.168.15.62 "echo 'ping 8.8.8.8' >> /tmp/obd-terminal.log"
    ssh matt@192.168.15.62 "ping -c1 8.8.8.8 >> /tmp/obd-terminal.log"

When switching TO this view, the buffer is cleared so you start fresh.
No input mechanism on the Pi itself — this is a read-only tail display.
"""
import os

NAME = "TERM"
REFRESH_SEC = 0.5

TERMINAL_LOG = "/tmp/obd-terminal.log"
MAX_LINES = 12  # lines that fit at 9pt mono on 128px


def _read_tail(path, max_lines):
    """Read the last max_lines from the log file."""
    if not os.path.exists(path):
        return ["[no log file]"]
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        # Strip trailing newlines, limit to max_lines
        return [l.rstrip() for l in lines[-max_lines:]]
    except Exception as e:
        return [f"[read err: {e}]"]


def render(draw, ctx):
    f_sm = ctx["font_sm"]   # 9pt mono
    f_xs = ctx["font_xs"]   # 8pt mono
    f_lg = ctx["font_lg"]   # 14pt bold

    # Clear buffer on first render of this view
    first = ctx.setdefault("_term_first", True)
    if first:
        try:
            if os.path.exists(TERMINAL_LOG):
                open(TERMINAL_LOG, "w").close()
        except Exception:
            pass
        ctx["_term_first"] = False

    # Header
    draw.text((2, 2), "TERM", font=f_lg, fill=(251, 191, 36))
    draw.line([(2, 16), (125, 16)], fill=(42, 42, 51), width=1)

    # Read and render lines
    lines = _read_tail(TERMINAL_LOG, MAX_LINES)
    y = 20
    line_h = 10
    for line in lines:
        # Truncate to ~18 chars (9pt mono on 128px)
        display_line = line[:20] if len(line) > 20 else line
        if display_line.startswith(">"):
            # Command lines in yellow
            draw.text((2, y), display_line, font=f_xs, fill=(251, 191, 36))
        elif display_line.startswith("[") or display_line.startswith("ERR"):
            # Error/system lines in red
            draw.text((2, y), display_line, font=f_xs, fill=(251, 113, 133))
        else:
            # Output lines in white
            draw.text((2, y), display_line, font=f_xs, fill=(200, 200, 200))
        y += line_h
        if y > 112:
            break

    # Footer hint
    draw.text((64, 119), "BTN=cycle view", font=f_xs,
              fill=(110, 108, 100), anchor="mb")
