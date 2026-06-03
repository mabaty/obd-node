import spidev
import gpiod
from gpiod.line import Direction, Value
import time

# Pin assignments (BCM numbering)
DC_PIN  = 24
RST_PIN = 25
BL_PIN  = 18
# CS handled by kernel SPI driver via dtoverlay (spi0-1cs,cs0_pin=21)

SPI_BUS = 0
SPI_DEV = 0

WIDTH  = 240
HEIGHT = 240

class GC9A01:
    def __init__(self):
        self._req = gpiod.request_lines(
            "/dev/gpiochip0",
            consumer="gc9a01",
            config={
                DC_PIN:  gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE),
                RST_PIN: gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
                BL_PIN:  gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.ACTIVE),
            },
        )

        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEV)
        self.spi.max_speed_hz = 10_000_000
        self.spi.mode = 3

        self.reset()
        self.init_display()
        self.backlight(True)

    def _set(self, pin, v):
        self._req.set_value(pin, Value.ACTIVE if v else Value.INACTIVE)

    def dc(self, v):   self._set(DC_PIN, v)
    def rst(self, v):  self._set(RST_PIN, v)
    def bl(self, v):   self._set(BL_PIN, v)
    def backlight(self, on): self.bl(1 if on else 0)

    def reset(self):
        self.rst(1); time.sleep(0.01)
        self.rst(0); time.sleep(0.05)
        self.rst(1); time.sleep(0.15)

    def cmd(self, c):
        self.dc(0)
        self.spi.writebytes([c])

    def data(self, d):
        self.dc(1)
        if isinstance(d, int):
            self.spi.writebytes([d])
        else:
            for i in range(0, len(d), 4096):
                self.spi.writebytes2(d[i:i+4096])

    def init_display(self):
        init_seq = [
            (0xEF, []),
            (0xEB, [0x14]),
            (0xFE, []), (0xEF, []),
            (0xEB, [0x14]),
            (0x84, [0x40]), (0x85, [0xFF]), (0x86, [0xFF]), (0x87, [0xFF]),
            (0x88, [0x0A]), (0x89, [0x21]), (0x8A, [0x00]), (0x8B, [0x80]),
            (0x8C, [0x01]), (0x8D, [0x01]), (0x8E, [0xFF]), (0x8F, [0xFF]),
            (0xB6, [0x00, 0x00]),
            (0x36, [0x48]),
            (0x3A, [0x05]),
            (0x90, [0x08, 0x08, 0x08, 0x08]),
            (0xBD, [0x06]), (0xBC, [0x00]),
            (0xFF, [0x60, 0x01, 0x04]),
            (0xC3, [0x13]), (0xC4, [0x13]),
            (0xC9, [0x22]),
            (0xBE, [0x11]),
            (0xE1, [0x10, 0x0E]),
            (0xDF, [0x21, 0x0C, 0x02]),
            (0xF0, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]),
            (0xF1, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
            (0xF2, [0x45, 0x09, 0x08, 0x08, 0x26, 0x2A]),
            (0xF3, [0x43, 0x70, 0x72, 0x36, 0x37, 0x6F]),
            (0xED, [0x1B, 0x0B]),
            (0xAE, [0x77]),
            (0xCD, [0x63]),
            (0x70, [0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03]),
            (0xE8, [0x34]),
            (0x62, [0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70]),
            (0x63, [0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70]),
            (0x64, [0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07]),
            (0x66, [0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00]),
            (0x67, [0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98]),
            (0x74, [0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00]),
            (0x98, [0x3E, 0x07]),
            (0x35, []), (0x21, []),
            (0x11, None),
            (0x29, None),
        ]
        for reg, val in init_seq:
            self.cmd(reg)
            if val is None:
                time.sleep(0.12)
            elif val:
                self.data(val)

    def set_window(self, x0, y0, x1, y1):
        self.cmd(0x2A); self.data([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self.cmd(0x2B); self.data([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self.cmd(0x2C)

    def show(self, img):
        rgb = img.convert("RGB")
        pixels = []
        for r, g, b in rgb.getdata():
            c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            pixels.append(c >> 8)
            pixels.append(c & 0xFF)
        self.set_window(0, 0, WIDTH-1, HEIGHT-1)
        self.data(pixels)

    def fill(self, color565):
        hi, lo = color565 >> 8, color565 & 0xFF
        buf = [hi, lo] * (WIDTH * HEIGHT)
        self.set_window(0, 0, WIDTH-1, HEIGHT-1)
        self.data(buf)

    def close(self):
        self.spi.close()
        self._req.release()
