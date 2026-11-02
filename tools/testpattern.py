"""Printer test pattern.

One print that answers every question about the printer layer:

  1. Is the configured width really printable?   edge arrows + mm ruler
  2. What is the smallest legible type?          type ladder
  3. Do hairlines survive?                       1/2/3px rules, vertical gaps
  4. How dark is solid black?                    fill block, beside the ramp
  5. Does raster banding leave seams?            unbroken rule down the edge
  6. Does the threshold/dither split work?       pre-dithered ramp

**Drawn with PIL, deliberately - not through the HTML renderer.** This tests the
printer path: width, stride, banding, ink. Routing it through Chromium would mean
a renderer bug shows up here looking like a printer fault, which is exactly the
confusion this print exists to remove.

Laid out for the full width rather than stretched to it: comparisons that belong
side by side (1px vs 2px checkerboard, solid fill vs dithered ramp) sit in
columns, because judging them against each other is the whole point and stacking
them makes that harder.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from printer.base import DOTS_PER_MM, WIDTH_DOTS  # noqa: E402

WIDTH = WIDTH_DOTS   # never hardcode this; it has moved twice
DPMM = DOTS_PER_MM
BLACK, WHITE = 0, 255
PAD = 6
GUTTER = 10

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",   # Consolas - chunky, well hinted
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _ramp(width: int, height: int) -> Image.Image:
    """A grey ramp, dithered to 1-bit before it is pasted.

    Dithered here, in isolation, so the page-wide threshold later leaves it
    alone. That is the production rule under test.
    """
    ramp = Image.new("L", (width, height))
    px = ramp.load()
    for x in range(width):
        value = 255 - round(255 * x / max(1, width - 1))
        for y in range(height):
            px[x, y] = value
    return ramp.convert("1").convert("L")


class Sheet:
    """Small vertical layout helper, so sections do not hand-compute offsets."""

    def __init__(self, width: int, height: int = 1400):
        self.img = Image.new("L", (width, height), WHITE)
        self.d = ImageDraw.Draw(self.img)
        self.w = width
        self.y = 0

    def bar(self, title: str, subtitle: str = "") -> None:
        """A reversed-out section header, full bleed."""
        h = 26 if subtitle else 20
        self.d.rectangle([0, self.y, self.w - 1, self.y + h], fill=BLACK)
        self.d.text((PAD, self.y + 3), title, font=font(13), fill=WHITE)
        if subtitle:
            self.d.text((self.w - PAD, self.y + 5), subtitle,
                        font=font(10), fill=WHITE, anchor="ra")
        self.y += h + 5

    def note(self, text: str, size: int = 10) -> None:
        self.d.text((PAD, self.y), text, font=font(size), fill=BLACK)
        self.y += size + 5

    def rule(self, weight: int = 3, gap: int = 6) -> None:
        self.d.rectangle([0, self.y, self.w - 1, self.y + weight - 1], fill=BLACK)
        self.y += weight + gap

    def columns(self, n: int = 2) -> list[tuple[int, int]]:
        """(x, width) for n equal columns inside the padding."""
        inner = self.w - PAD * 2 - GUTTER * (n - 1)
        cw = inner // n
        return [(PAD + i * (cw + GUTTER), cw) for i in range(n)]

    def crop(self) -> Image.Image:
        return self.img.crop((0, 0, self.w, self.y))


def build() -> Image.Image:
    s = Sheet(WIDTH)
    d = s.d

    # --- masthead --------------------------------------------------------
    s.bar("QUICK-GUTHE  PRINTER TEST",
          f"{WIDTH} dots / {WIDTH // DPMM}mm / {DPMM} dots per mm")

    # --- full-width proof -------------------------------------------------
    # Arrowheads pinned to the outermost columns. If either is clipped or
    # floating, the configured width is wrong.
    d.polygon([(0, s.y), (12, s.y), (0, s.y + 12)], fill=BLACK)
    d.polygon([(WIDTH - 1, s.y), (WIDTH - 13, s.y), (WIDTH - 1, s.y + 12)],
              fill=BLACK)
    d.text((WIDTH // 2, s.y + 1), "both arrowheads must touch the printable edges",
           font=font(10), fill=BLACK, anchor="ma")
    s.y += 18

    # --- millimetre ruler -------------------------------------------------
    base = s.y + 15
    for mm in range(WIDTH // DPMM + 1):
        x = min(mm * DPMM, WIDTH - 1)
        length = 13 if mm % 10 == 0 else (8 if mm % 5 == 0 else 4)
        d.line([(x, base), (x, base - length)], fill=BLACK)
        if mm % 10 == 0 and mm:
            d.text((x, base - 24), str(mm), font=font(10), fill=BLACK, anchor="ma")
    d.line([(0, base), (WIDTH - 1, base)], fill=BLACK)
    s.y = base + 8

    # --- type ladder ------------------------------------------------------
    s.bar("TYPE LADDER", "smallest you can read = the floor")
    for size in (7, 8, 9, 10, 11, 12, 14, 16, 18, 20):
        d.text((PAD, s.y + 1), f"{size:>2}", font=font(9), fill=BLACK)
        d.text((PAD + 24, s.y), "Sphinx of black quartz, judge my vow 0123",
               font=font(size), fill=BLACK)
        s.y += max(size, 12) + 3
    s.y += 4

    # --- hairlines, full width -------------------------------------------
    s.bar("HAIRLINES", "all three must be distinct")
    for w in (1, 2, 3):
        d.rectangle([PAD, s.y, WIDTH - PAD - 1, s.y + w - 1], fill=BLACK)
        d.text((WIDTH - PAD, s.y - 3), f"{w}px", font=font(9), fill=BLACK,
               anchor="ra")
        s.y += w + 9

    # --- vertical gaps, spread across the width ---------------------------
    gaps = (2, 3, 4, 5, 6, 8)
    cols = s.columns(len(gaps))
    for (x, cw), gap in zip(cols, gaps):
        for gx in range(x, x + cw, gap):
            d.line([(gx, s.y), (gx, s.y + 26)], fill=BLACK)
        d.text((x + cw // 2, s.y + 29), f"{gap}px", font=font(9), fill=BLACK,
               anchor="ma")
    s.y += 44

    # --- checkerboards, side by side so they can be compared --------------
    s.bar("CHECKERBOARD", "1px left, 2px right")
    (lx, lw), (rx, rw) = s.columns(2)
    for (x, w), cell in (((lx, lw), 1), ((rx, rw), 2)):
        for cy in range(s.y, s.y + 30):
            for cx in range(x, x + w):
                if ((cx // cell) + (cy // cell)) % 2 == 0:
                    d.point((cx, cy), fill=BLACK)
    s.y += 36

    # --- density: solid fill against the dithered ramp --------------------
    s.bar("DENSITY", "solid left, dithered ramp right")
    (lx, lw), (rx, rw) = s.columns(2)
    d.rectangle([lx, s.y, lx + lw - 1, s.y + 44], fill=BLACK)
    d.text((lx + lw // 2, s.y + 15), "REVERSED", font=font(14), fill=WHITE,
           anchor="ma")
    s.img.paste(_ramp(rw, 45), (rx, s.y))
    s.y += 52

    # --- band seam check --------------------------------------------------
    # An unbroken rule down the extreme left edge, crossing every 128-row band
    # boundary. Any step or gap means the raster banding is stitching wrong.
    # It doubles as a second full-width edge indicator.
    d.rectangle([0, 40, 1, s.y + 16], fill=BLACK)
    s.bar("BAND SEAM", "left edge rule must be unbroken")
    s.note("If that rule steps or breaks, the raster stride is wrong.", 10)

    s.rule(3, 4)
    s.note("END OF PATTERN", 11)
    return s.crop()


def main() -> None:
    import argparse

    from printer import get_printer

    ap = argparse.ArgumentParser(description="Print the printer test pattern.")
    ap.add_argument("--print", dest="to_paper", action="store_true",
                    help="send to the real printer instead of a PNG")
    ap.add_argument("--out", default="out/testpattern.png")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    img = build()
    print(f"pattern: {img.width}x{img.height}px "
          f"({img.height / DPMM:.0f}mm of paper)")

    if args.to_paper:
        get_printer("usb").print_image(img)
        print("sent to printer")
    else:
        get_printer("preview", path=args.out, scale=args.scale).print_image(img)


if __name__ == "__main__":
    main()
