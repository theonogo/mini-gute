"""Pick the page threshold, and prove reversed-out text needs weight not threshold.

An antialiased hairline serif lands as mid-grey. Below the threshold it becomes
pure white and the stroke vanishes, so the glyph reads as broken. Raising the
threshold rescues it: on text alone, 190 puts ~28% more ink down than 128.

The two problems pull opposite ways:
  * positive text (black on white) - thin strokes need a HIGHER threshold
  * reversed text (white on black) - more ink EATS the glyphs, so it needs
    weight instead

Safe for photographs at any value: they are dithered to pure 0/255 before
reaching the page, so `rendertest.py`'s byte-identical check holds regardless.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from printer import get_printer  # noqa: E402
from printer.base import WIDTH_DOTS  # noqa: E402
from render import Renderer  # noqa: E402
from render.fonts import face_css, sizes, stack  # noqa: E402

# Brackets the page threshold (170, render.page.DEFAULT_THRESHOLD) in both
# directions. Ink behaviour belongs to the printhead, so re-run this on any new
# printer rather than trusting the number.
CUTS = (160, 180, 200, 220)
FAMILY = "Libre Baskerville"
SAMPLE = ("Sphinx of black quartz, judge my vow. The afternoon intends to be "
          "wet, and a coat is therefore advised.")


def page(cut: int) -> str:
    body, small, tiny = sizes(FAMILY)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      {face_css(FAMILY)}
      html,body{{margin:0;padding:0;background:#fff}}
      body{{font-family:{stack(FAMILY)};font-size:{body}px;line-height:1.4}}
      .h{{background:#000;color:#fff;font-weight:700;padding:2px 6px;
          font-size:{small}px}}
      .p{{padding:4px 6px}}
      .inv{{background:#000;color:#fff;padding:3px 6px;margin-top:2px}}
      .invb{{background:#000;color:#fff;padding:3px 6px;font-weight:700}}
    </style></head><body>
      <div class="h">THRESHOLD {cut}</div>
      <div class="p">{SAMPLE}</div>
      <div class="inv">Reversed, regular weight</div>
      <div class="invb">Reversed, BOLD weight</div>
    </body></html>"""


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="to_paper", action="store_true")
    args = ap.parse_args()

    tiles = []
    with Renderer() as r:
        for cut in CUTS:
            tiles.append(r.render(page(cut), threshold=cut))

    gap = 5
    total = sum(t.height for t in tiles) + gap * (len(tiles) - 1)
    sheet = Image.new("1", (WIDTH_DOTS, total), 1)
    y = 0
    for i, t in enumerate(tiles):
        sheet.paste(t, (0, y))
        y += t.height
        if i < len(tiles) - 1:
            sheet.paste(Image.new("1", (WIDTH_DOTS, gap), 0), (0, y))
            y += gap

    print(f"{sheet.width}x{sheet.height}px ({sheet.height/8:.0f}mm)")
    if args.to_paper:
        get_printer("usb").print_image(sheet)
        print("sent to printer")
    else:
        get_printer("preview", path="out/thresholdtest.png", scale=2).print_image(sheet)


if __name__ == "__main__":
    main()
