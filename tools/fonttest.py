"""Every font at the sizes it actually ships, at the real page threshold.

Not a size sweep - `render/fonts.py` already fixes the three tiers per family.
This prints exactly what a persona would print, so the question it answers is
"does this family work at its assigned sizes", not "what size should it be".

Each family gets its body, small and tiny tiers in positive, then a reversed-out
line at small weight. Reversed is included because it fails in the opposite
direction to positive text: the page threshold rescues thin positive strokes and
eats white-on-black ones, so a threshold that suits one can ruin the other. Both
have to survive the same number.

    python tools/fonttest.py --print
    python tools/fonttest.py --threshold 190 --print   # try another cut
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from printer import get_printer  # noqa: E402
from render import Renderer  # noqa: E402
from render.page import DEFAULT_THRESHOLD  # noqa: E402
from render.fonts import face_css, families, sizes, stack  # noqa: E402

SAMPLE = "Sphinx of black quartz, judge my vow 0123"
TIERS = ("body", "small", "tiny")


def build(cut: int) -> str:
    blocks = []
    for fam in families():
        px = sizes(fam)
        rows = "".join(
            f'<div class="row"><span class="tag">{tier} {p}</span>'
            f'<span style="font-size:{p}px">{SAMPLE}</span></div>'
            for tier, p in zip(TIERS, px)
        )
        # Reversed at the small tier, bold - the shipping combination.
        rows += (f'<div class="inv"><span class="tag inv-tag">rev {px[1]}</span>'
                 f'<span style="font-size:{px[1]}px">{SAMPLE}</span></div>')
        blocks.append(
            f'<section style="font-family:{stack(fam)}">'
            f'<div class="fam">{fam}<span class="px">'
            f'{px[0]}/{px[1]}/{px[2]}</span></div>{rows}</section>')

    css = "".join(face_css(f) for f in families())
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      {css}
      html,body{{margin:0;padding:0;background:#fff}}
      body {{ font-family:'JetBrains Mono',monospace; }}
      .hd  {{ background:#000;color:#fff;font-weight:700;padding:6px 10px;
              font-size:16px;display:flex;justify-content:space-between }}
      .hd small {{ font-weight:400;font-size:13px }}
      .fam {{ background:#000;color:#fff;font-size:14px;font-weight:700;
              padding:3px 10px;margin-top:9px;
              display:flex;justify-content:space-between;
              font-family:'JetBrains Mono',monospace }}
      .px  {{ font-weight:400 }}
      .row {{ padding:2px 10px 3px; display:flex; align-items:baseline;
              gap:10px }}
      .inv {{ padding:3px 10px 4px; display:flex; align-items:baseline;
              gap:10px; background:#000; color:#fff; font-weight:700;
              margin-top:3px }}
      .tag {{ font-family:'JetBrains Mono',monospace; font-size:12px;
              width:64px; flex:none; font-weight:400 }}
      .inv-tag {{ color:#fff; font-weight:700 }}
      .note{{ font-size:14px; padding:8px 10px; border-top:3px solid #000;
              margin-top:10px }}
    </style></head><body>
      <div class="hd"><span>FONT CHECK</span>
        <small>threshold {cut} &middot; shipping sizes</small></div>
      {"".join(blocks)}
      <div class="note">Positive text should be crisp, not blobbed. Reversed
      text should stay open, not filled in. Both at the same threshold.</div>
    </body></html>"""


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="to_paper", action="store_true")
    ap.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    ap.add_argument("--out", default="out/fonttest.png")
    args = ap.parse_args()

    with Renderer() as r:
        img = r.render(build(args.threshold), threshold=args.threshold)

    print(f"{img.width}x{img.height}px ({img.height / 8:.0f}mm), "
          f"{len(families())} families at threshold {args.threshold}")
    if args.to_paper:
        get_printer("usb").print_image(img)
        print("sent to printer")
    else:
        get_printer("preview", path=args.out, scale=1).print_image(img)


if __name__ == "__main__":
    main()
