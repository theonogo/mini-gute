"""Render-path verification: HTML -> headless Chromium -> 1-bit.

Two checks.

  A. Fidelity (mechanical). Render a page containing nothing but a pre-dithered
     photograph, full bleed. The output must be *byte-identical* to the source
     dither. If it is not, the browser resampled or smoothed the image and every
     photo we ever print will be grey fuzz. This is the "threshold text, dither
     photos, never in the same pass" rule, tested rather than trusted.

  B. Appearance (visual). A realistic mixed page - dense type at several sizes,
     full-bleed rules and black bars, and the same photo - to look at on paper.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from printer import get_printer  # noqa: E402
from printer.base import WIDTH_DOTS  # noqa: E402
from render import Renderer, contrast_score, img_tag, prepare  # noqa: E402

FONT_STACK = "Consolas, 'DejaVu Sans Mono', monospace"


def synthetic_photo(width: int = WIDTH_DOTS, height: int = 260) -> Image.Image:
    """A lit sphere on a gradient - smooth tones are the hard case for dithering."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    bg = 40 + 150 * (yy / height)

    cx, cy, r = width * 0.5, height * 0.52, height * 0.36
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    inside = d < r
    z = np.sqrt(np.clip(r ** 2 - d ** 2, 0, None))
    lx, ly, lz = -0.5, -0.6, 0.62
    norm = np.stack([(xx - cx) / r, (yy - cy) / r, z / r])
    lam = np.clip(norm[0] * lx + norm[1] * ly + norm[2] * lz, 0, 1)
    sphere = 25 + 230 * lam ** 1.4

    img = np.where(inside, sphere, bg)
    rng = np.random.default_rng(7)
    img = np.clip(img + rng.normal(0, 3, img.shape), 0, 255)
    return Image.fromarray(img.astype(np.uint8), "L")


def page_photo_only(photo: Image.Image) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      html,body{{margin:0;padding:0;background:#fff}}
    </style></head><body>{img_tag(photo, "fidelity target")}</body></html>"""


def page_mixed(photo: Image.Image) -> str:
    ladder = "".join(
        f'<p style="font-size:{s}px;margin:0 0 3px">'
        f'<b>{s}px</b> Sphinx of black quartz, judge my vow 0123</p>'
        for s in (11, 12, 14, 16)
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body {{ font-family:{FONT_STACK}; font-size:12px; line-height:1.35; }}
      .bar  {{ background:#000; color:#fff; padding:5px 6px; }}
      .rule {{ height:3px; background:#000; margin:6px 0; }}
      .pad  {{ padding:0 6px; }}
      .fine {{ font-size:9px; }}
      table {{ width:100%; border-collapse:collapse; font-size:11px; }}
      td    {{ padding:1px 0; }}
      td.r  {{ text-align:right; }}
    </style></head><body>

      <div class="bar">
        <div style="font-size:15px;font-weight:bold">QUICK-GUTHE</div>
        <div style="font-size:11px">HTML RENDER TEST</div>
      </div>

      <div class="pad" style="padding-top:6px">{ladder}</div>
      <div class="rule"></div>

      <div class="pad">
        <table>
          <tr><td>TAROT CARD</td><td class="r">COMMON</td><td class="r">0.30</td></tr>
          <tr><td>NONOGRAM</td><td class="r">COMMON</td><td class="r">0.30</td></tr>
          <tr><td>CITY MAP TILE</td><td class="r">UNCOMMON</td><td class="r">1.20</td></tr>
        </table>
      </div>
      <div class="rule"></div>
      <div class="pad"><table>
        <tr><td><b>SUBTOTAL</b></td><td class="r"><b>1.80</b></td></tr>
        <tr><td>RARITY</td><td class="r">&#9733;&#9733;&#9734;&#9734;&#9734;</td></tr>
      </table></div>

      {img_tag(photo, "dithered photo")}

      <div class="pad fine" style="padding-top:6px">
        THE MANAGEMENT ACCEPTS NO LIABILITY FOR PROPHECIES FULFILLED IN SPIRIT
        BUT NOT IN LETTER.* NO REFUNDS ON WEDNESDAYS.<br>
        * OR IN ANY OTHER TENSE SUBSEQUENTLY DISCOVERED.
      </div>

      <div class="rule"></div>
      <div class="pad" style="font-size:11px">END OF TEST</div>
    </body></html>"""


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="to_paper", action="store_true")
    ap.add_argument("--out", default="out/rendertest.png")
    args = ap.parse_args()

    source = synthetic_photo()
    print(f"source photo contrast score: {contrast_score(source):.2f}")
    photo = prepare(source, WIDTH_DOTS)

    with Renderer() as r:
        # --- A. fidelity ------------------------------------------------
        got = r.render(page_photo_only(photo))
        exp = np.asarray(photo.convert("1"), dtype=bool)
        act = np.asarray(got.crop((0, 0, photo.width, photo.height)).convert("1"),
                         dtype=bool)
        if got.height < photo.height:
            print(f"FAIL  render is {got.height}px, photo is {photo.height}px")
            sys.exit(1)
        diff = int((exp != act).sum())
        total = exp.size
        if diff == 0:
            print(f"PASS  dither survived the browser byte-identical "
                  f"({total:,} px)")
        else:
            print(f"FAIL  {diff:,}/{total:,} pixels changed "
                  f"({100 * diff / total:.2f}%) - the browser resampled it")

        # --- B. appearance ----------------------------------------------
        img = r.render(page_mixed(photo))

    print(f"mixed page: {img.width}x{img.height}px ({img.height / 8:.0f}mm)")
    if args.to_paper:
        get_printer("usb").print_image(img)
        print("sent to printer")
    else:
        get_printer("preview", path=args.out, scale=2).print_image(img)


if __name__ == "__main__":
    main()
