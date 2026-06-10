"""SSD1351 128x128 RGB OLED driver for Raspberry Pi.

4-wire SPI interface using spidev + gpiod 2.x (NOT lgpio — see
findings/lenox-mobile-display.md gotcha #2). Based on the Waveshare
1.5inch RGB OLED Module init sequence.

Pin assignments (BCM numbering):
    DC  = GPIO25  (pin 22)
    RST = GPIO27  (pin 13)
    CS  = GPIO8   (pin 24) — default SPI0 CE0, kernel-managed

No backlight pin — OLED is self-emissive.

SPI mode 0, 9 MHz baseline.
"""

import spidev
import gpiod
from gpiod.line import Direction, Value
import time

# Pin assignments (BCM numbering)
DC_PIN  = 25
RST_PIN = 27
# CS handled by kernel SPI driver on default CE0 (GPIO8, pin 24)
# No backlight pin on SSD1351 OLED

SPI_BUS = 0
SPI_DEV = 0

WIDTH  = 128
HEIGHT = 128

# SSD1351 command constants
CMD_SETCOLUMN       = 0x15
CMD_SETROW          = 0x75
CMD_WRITERAM        = 0x5C
CMD_READRAM         = 0x5D
CMD_SETREMAP        = 0xA0
CMD_STARTLINE       = 0xA1
CMD_DISPLAYOFFSET   = 0xA2
CMD_DISPLAYALLOFF   = 0xA4
CMD_DISPLAYALLON    = 0xA5
CMD_NORMALDISPLAY   = 0xA6
CMD_INVERTDISPLAY   = 0xA7
CMD_FUNCTIONSELECT  = 0xAB
CMD_DISPLAYOFF      = 0xAE
CMD_DISPLAYON       = 0xAF
CMD_PRECHARGE       = 0xB1
CMD_DISPLAYENHANCE  = 0xB2
CMD_CLOCKDIV        = 0xB3
CMD_SETVSL          = 0xB4
CMD_SETGPIO         = 0xB5
CMD_PRECHARGE2      = 0xB6
CMD_SETGRAY         = 0xB8
CMD_USELUT          = 0xB9
CMD_PRECHARGELEVEL  = 0xBB
CMD_VCOMH           = 0xBE
CMD_CONTRASTABC     = 0xC1
CMD_CONTRASTMASTER  = 0xC7
CMD_MUXRATIO        = 0xCA
CMD_COMMANDLOCK     = 0xFD


class SSD1351:
    def __init__(self):
        # Claim DC and RST via gpiod 2.x — atomic output_value prevents
        # the lgpio "claim-then-set" glitch that killed a backlight once.
        self._req = gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="ssd1351",
            config={
                DC_PIN:  gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.INACTIVE),
                RST_PIN: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.ACTIVE),
            },
        )

        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEV)
        self.spi.max_speed_hz = 9_000_000
        self.spi.mode = 0b00  # SPI mode 0 — SSD1351 standard

        self.reset()
        self.init_display()
        print("[ssd1351] initialized OK", flush=True)

    def _set(self, pin, v):
        self._req.set_value(pin, Value.ACTIVE if v else Value.INACTIVE)

    def dc(self, v):   self._set(DC_PIN, v)
    def rst(self, v):  self._set(RST_PIN, v)

    def reset(self):
        self.rst(1); time.sleep(0.01)
        self.rst(0); time.sleep(0.10)
        self.rst(1); time.sleep(0.15)

    def cmd(self, c):
        """Send a single command byte (DC=LOW)."""
        self.dc(0)
        self.spi.writebytes([c])

    def data(self, d):
        """Send a single data byte (DC=HIGH)."""
        self.dc(1)
        if isinstance(d, int):
            self.spi.writebytes([d])
        else:
            self.spi.writebytes(list(d))

    def init_display(self):
        """Full Waveshare SSD1351 init sequence (verified working)."""
        self.cmd(CMD_COMMANDLOCK)    # 0xFD — command lock
        self.data(0x12)
        self.cmd(CMD_COMMANDLOCK)
        self.data(0xB1)              # unlock advanced commands

        self.cmd(CMD_DISPLAYOFF)     # 0xAE — display off during config

        self.cmd(CMD_DISPLAYALLOFF)  # 0xA4 — normal display mode

        # Set column address range 0–127
        self.cmd(CMD_SETCOLUMN)      # 0x15
        self.data(0x00)
        self.data(0x7F)

        # Set row address range 0–127
        self.cmd(CMD_SETROW)         # 0x75
        self.data(0x00)
        self.data(0x7F)

        # Clock divider
        self.cmd(CMD_CLOCKDIV)       # 0xB3
        self.data(0xF1)

        # Mux ratio
        self.cmd(CMD_MUXRATIO)       # 0xCA
        self.data(0x7F)

        # Set re-map & data format
        # 0x74 = horizontal increment, RGB, split-level enable, column swap
        self.cmd(CMD_SETREMAP)       # 0xA0
        self.data(0x74)

        # Start line
        self.cmd(CMD_STARTLINE)      # 0xA1
        self.data(0x00)

        # Display offset
        self.cmd(CMD_DISPLAYOFFSET)  # 0xA2
        self.data(0x00)

        # Function select (VDD internal)
        self.cmd(CMD_FUNCTIONSELECT) # 0xAB
        self.data(0x01)

        # VSL
        self.cmd(CMD_SETVSL)         # 0xB4
        self.data(0xA0)
        self.data(0xB5)
        self.data(0x55)

        # Contrast A/B/C
        self.cmd(CMD_CONTRASTABC)    # 0xC1
        self.data(0xC8)              # color A
        self.data(0x80)              # color B
        self.data(0xC0)              # color C

        # Master contrast
        self.cmd(CMD_CONTRASTMASTER) # 0xC7
        self.data(0x0F)

        # Pre-charge period
        self.cmd(CMD_PRECHARGE)      # 0xB1
        self.data(0x32)

        # Display enhancement
        self.cmd(CMD_DISPLAYENHANCE) # 0xB2
        self.data(0xA4)
        self.data(0x00)
        self.data(0x00)

        # Pre-charge voltage level
        self.cmd(CMD_PRECHARGELEVEL) # 0xBB
        self.data(0x17)

        # Second pre-charge
        self.cmd(CMD_PRECHARGE2)     # 0xB6
        self.data(0x01)

        # VCOMH voltage
        self.cmd(CMD_VCOMH)         # 0xBE
        self.data(0x05)

        # Normal display (non-inverted)
        self.cmd(CMD_NORMALDISPLAY)  # 0xA6

        # Clear the screen (fill with black)
        self.clear()

        # Turn display on
        self.cmd(CMD_DISPLAYON)     # 0xAF

    def clear(self):
        """Fill entire display with black."""
        self.cmd(CMD_SETCOLUMN)
        self.data(0x00)
        self.data(0x7F)
        self.cmd(CMD_SETROW)
        self.data(0x00)
        self.data(0x7F)
        self.cmd(CMD_WRITERAM)

        self.dc(1)
        # Send 128*128 pixels × 2 bytes each = 32768 bytes of 0x00
        # Write in chunks to avoid SPI buffer limits
        chunk = [0x00] * (WIDTH * 2)  # one row of black
        for _ in range(HEIGHT):
            self.spi.writebytes(chunk)

    def show(self, image):
        """Push a PIL RGB Image to the display.

        The SSD1351 expects 16-bit RGB565 pixel data in column-major order
        (due to the 0x74 re-map setting). We convert from PIL's row-major RGB
        and write row by row.
        """
        if image.size != (WIDTH, HEIGHT):
            print(f"[ssd1351] WARNING: image size {image.size} != ({WIDTH},{HEIGHT}), resizing",
                   flush=True)
            image = image.resize((WIDTH, HEIGHT))

        buf = image.load()

        # Set drawing window to full screen
        self.cmd(CMD_SETCOLUMN)
        self.data(0x00)
        self.data(0x7F)
        self.cmd(CMD_SETROW)
        self.data(0x00)
        self.data(0x7F)
        self.cmd(CMD_WRITERAM)

        self.dc(1)

        # Build and send one row at a time to keep memory reasonable
        row_buf = bytearray(WIDTH * 2)
        for y in range(HEIGHT):
            for x in range(WIDTH):
                r, g, b = buf[x, y][:3]
                # RGB565: RRRRRGGG GGGBBBBB
                hi = ((r & 0xF8) | (g >> 5))
                lo = (((g << 3) & 0xE0) | (b >> 3))
                row_buf[x * 2]     = hi
                row_buf[x * 2 + 1] = lo
            self.spi.writebytes(list(row_buf))
