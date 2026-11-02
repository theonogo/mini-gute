"""Empirically find the printer's true printable width.

Four bars are sent, each declaring a different raster width. Whichever come out
the same width as the narrowest have been clipped; the widest bar that is
genuinely wider is real headroom.

Worth re-running after any paper or printer change. Whatever it finds, the width
the page uses must also be a multiple of 8 (`printer/base.py`).

Each bar is solid at its extreme left and right edges, with N notches in the
middle so the bars can be told apart on paper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

# Common thermal widths: 384 dots on a 58mm head, 420 for a TM-T20II on a
# 58mm roll, 576 on 80mm. Anything clipped to the same width as its
# neighbours tells us where the real limit is.
WIDTHS = [384, 420, 512, 576]
BAR_H = 26
GAP_H = 10


def bar(width: int, notches: int) -> Image.Image:
    """A full-width bar for `width` dots, tagged with `notches` marks."""
    img = Image.new("1", (width, BAR_H), 1)  # 1 = white in mode "1"
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width - 1, 2], fill=0)              # top rule, full width
    d.rectangle([0, BAR_H - 3, width - 1, BAR_H - 1], fill=0)
    d.rectangle([0, 0, 7, BAR_H - 1], fill=0)              # left edge block
    d.rectangle([width - 8, 0, width - 1, BAR_H - 1], fill=0)
    for i in range(notches):                                # centre notches
        x = width // 2 - (notches * 12) // 2 + i * 12
        d.rectangle([x, 6, x + 5, BAR_H - 7], fill=0)
    return img


def raster_bytes(img: Image.Image) -> bytes:
    """GS v 0 for an image of any width - deliberately bypasses check_width."""
    bw = img.convert("1")
    width_bytes = (bw.width + 7) // 8
    packed = bytes(b ^ 0xFF for b in bw.tobytes())
    out = bytearray()
    out += b"\x1dv0\x00"
    out += bytes([width_bytes & 0xFF, width_bytes >> 8])
    out += bytes([bw.height & 0xFF, bw.height >> 8])
    out += packed
    return bytes(out)


def main() -> None:
    from printer.usbwin import find_device
    import win32con
    import win32file

    data = bytearray(b"\x1b@\x1ba\x00")
    for i, w in enumerate(WIDTHS, start=1):
        data += raster_bytes(bar(w, i))
        data += raster_bytes(Image.new("1", (min(WIDTHS), GAP_H), 1))
    data += b"\x1bd\x04"

    path = find_device()
    if path is None:
        raise SystemExit("no printer found - is it plugged in?")

    handle = win32file.CreateFile(path, win32con.GENERIC_WRITE, 0, None,
                                 win32con.OPEN_EXISTING, 0, None)
    try:
        win32file.WriteFile(handle, bytes(data))
    finally:
        win32file.CloseHandle(handle)

    print("sent 4 bars, top to bottom:")
    for i, w in enumerate(WIDTHS, start=1):
        print(f"  {i} notch(es) = {w} dots ({w / 8:.0f}mm)")
    print("\nBars printing the SAME width as bar 1 were clipped to it.")


if __name__ == "__main__":
    main()
