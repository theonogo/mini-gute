"""ESC/POS encoding.

We render whole receipts as bitmaps, so we need almost none of ESC/POS. Raster
image and paper feed cover it. Upside-down text, mirroring, double-width,
barcodes and QR codes are all pixels we produce ourselves in the renderer, which
means we do not depend on any of those command sets being implemented correctly
on a cheap printer.
"""

from PIL import Image

from .base import check_width

INIT = b"\x1b@"          # ESC @   reset to a known state
ALIGN_LEFT = b"\x1ba\x00"

# Rows per GS v 0 command. The spec allows up to 65535, but cheap printers have
# small input buffers and garble or drop tall images. Banding is free.
BAND_ROWS = 128


def feed(lines: int = 4) -> bytes:
    """ESC d n - feed n lines so the last text clears the tear bar."""
    return b"\x1bd" + bytes([max(0, min(255, lines))])


def cut(feed_dots: int = 100, partial: bool = True) -> bytes:
    """GS V - feed, then cut. Only on printers that have a cutter.

    The cutter sits above the print head (~14mm on a TM-T20II), so the paper
    must be fed past it first or the cut lands mid-content. `GS V 66 n` does the
    feed and the cut as one command, which is why it is preferred over feeding
    separately and hoping the timing works out.

    Partial cut leaves a small tab holding the receipt on, so it does not drop
    on the floor. Full cut separates it completely.
    """
    return b"V" + bytes([66 if partial else 65, max(0, min(255, feed_dots))])


def raster(img: Image.Image) -> bytes:
    """Encode an image as one or more GS v 0 raster commands.

    GS v 0 m xL xH yL yH d1..dk
      m  = 0 (normal density)
      x  = width in BYTES, little-endian
      y  = height in DOTS, little-endian
      d  = rows of packed bits, MSB first, 1 = black
    """
    check_width(img)

    # "1" mode: 0 is black, 255 is white. ESC/POS wants 1 for black, so invert.
    bw = img.convert("1")

    # PIL pads every row up to a whole number of bytes, so the stride is
    # ceil(width/8) - NOT width//8. Those agree only when the width is a
    # multiple of 8. Getting this wrong reads each row one byte short, the data
    # walks progressively, and the page prints as diagonal smear rather than as
    # an obvious error. Take the stride from the image, never from the nominal
    # width.
    width_bytes = (bw.width + 7) // 8
    packed = bw.tobytes()
    assert len(packed) == width_bytes * bw.height, (
        f"stride mismatch: {len(packed)} bytes for {bw.width}x{bw.height}, "
        f"expected {width_bytes * bw.height}")
    inverted = bytes(b ^ 0xFF for b in packed)

    out = bytearray()
    for top in range(0, bw.height, BAND_ROWS):
        rows = min(BAND_ROWS, bw.height - top)
        band = inverted[top * width_bytes : (top + rows) * width_bytes]
        out += b"\x1dv0\x00"
        out += bytes([width_bytes & 0xFF, width_bytes >> 8])
        out += bytes([rows & 0xFF, rows >> 8])
        out += band
    return bytes(out)


def receipt(img: Image.Image, feed_lines: int = 4, *,
            autocut: bool = False, partial: bool = True) -> bytes:
    """A complete job: reset, image, then either cut or feed clear of the bar.

    With a cutter, `GS V` does its own feed, so the manual line feed would just
    waste paper on top of it.
    """
    job = INIT + ALIGN_LEFT + raster(img)
    return job + (cut(partial=partial) if autocut else feed(feed_lines))
