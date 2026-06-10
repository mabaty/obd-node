"""View modules for obd-node display.

Each view module must expose:
    NAME: str            - short label for logging
    REFRESH_SEC: float   - how often this view wants to re-render
    render(draw, ctx)    - draw to PIL ImageDraw on a 128x128 canvas

The shared `ctx` dict carries pre-loaded fonts (font_xl/lg/md/sm/xs) and is the
right place to cache per-view state across frames.
"""
