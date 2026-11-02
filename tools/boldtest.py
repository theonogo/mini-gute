"""Measure what bold actually costs, per family, at the page threshold.

Bold reads as bleedy on paper and the question is whether that is the printer or
the render. This measures the render half, because there is a specific and very
plausible culprit in it.

**Several embedded families ship only one weight.** `assets/fonts/` carries a
400 and a 700 for Libre Baskerville, Inter, JetBrains Mono and others - and for
VT323 and Special Elite a 400 alone, because Google Fonts publishes nothing else
for either. Asked for `font-weight:
700` on those, the browser does not decline. It SYNTHESISES a bold by smearing
each glyph sideways, which is a fake thickening with soft edges rather than a
drawn heavier face. Soft edges are exactly what a threshold turns into extra
ink, and the page threshold of 170 is already biased towards more ink because it
was chosen to rescue thin strokes.

So the metrics are:

  ink      proportion of the sample that prints black
  stroke   mean horizontal run of black pixels - the real stroke width

A real bold should raise both modestly and in proportion. Synthetic bold should
raise ink sharply while barely changing the drawn shape, and should get worse as
the threshold rises. The third column tests `font-synthesis: none`, which is the
one-line fix if the diagnosis holds.

    python tools/boldtest.py            measure
    python tools/boldtest.py --card     render a printable comparison card
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from render import Renderer  # noqa: E402
from render.fonts import face_css, manifest, sizes  # noqa: E402
from render.page import DEFAULT_THRESHOLD  # noqa: E402

SAMPLE = "Handgloves 0123 MIXED"

PAGE = """<!doctype html><meta charset="utf-8"><style>
{faces}
html,body{{margin:0;padding:0;background:#fff}}
.s{{font-family:'{family}',sans-serif;font-size:{size}px;line-height:1.3;
    padding:2px 0;white-space:nowrap}}
.w400{{font-weight:400}}
.w700{{font-weight:700}}
.nosyn{{font-weight:700;font-synthesis:none;font-synthesis-weight:none}}
</style><body><div class="s {cls}">{text}</div></body>"""


def has_real_bold(family: str) -> bool:
    return any("700" in name for name in manifest().get(family, []))


def measure(img) -> tuple[float, float]:
    """(ink fraction, mean horizontal black run length)."""
    arr = np.asarray(img.convert("L")) < 128
    ink = float(arr.mean())

    runs: list[int] = []
    for row in arr:
        length = 0
        for pixel in row:
            if pixel:
                length += 1
            elif length:
                runs.append(length)
                length = 0
        if length:
            runs.append(length)
    return ink, (float(np.mean(runs)) if runs else 0.0)


def render(renderer: Renderer, family: str, cls: str, threshold: int):
    size = sizes(family)[0]
    html = PAGE.format(faces=face_css(family), family=family, size=size,
                       cls=cls, text=SAMPLE)
    return renderer.render(html, threshold=threshold)


def main() -> int:
    card = "--card" in sys.argv
    families = sorted(manifest())

    with Renderer() as renderer:
        if card:
            return write_card(renderer, families)

        print(f"Sample {SAMPLE!r} at the page threshold ({DEFAULT_THRESHOLD}).\n")
        print(f"{'family':<20}{'bold face':>10}"
              f"{'ink 400':>9}{'ink 700':>9}{'+ink':>7}"
              f"{'str 400':>9}{'str 700':>9}{'+str':>7}")
        for family in families:
            real = has_real_bold(family)
            ink4, str4 = measure(render(renderer, family, "w400",
                                        DEFAULT_THRESHOLD))
            ink7, str7 = measure(render(renderer, family, "w700",
                                        DEFAULT_THRESHOLD))
            print(f"{family:<20}{('yes' if real else 'NO'):>10}"
                  f"{ink4:>9.3f}{ink7:>9.3f}{ink7 / max(ink4, 1e-6) - 1:>+6.0%}"
                  f"{str4:>9.2f}{str7:>9.2f}{str7 / max(str4, 1e-6) - 1:>+6.0%}")

        print("\nDoes font-synthesis:none change anything? (only single-weight "
              "families should move)")
        print(f"{'family':<20}{'ink 700':>9}{'ink nosyn':>11}{'change':>9}")
        for family in families:
            ink7, _ = measure(render(renderer, family, "w700",
                                     DEFAULT_THRESHOLD))
            inkn, _ = measure(render(renderer, family, "nosyn",
                                     DEFAULT_THRESHOLD))
            flag = "" if abs(inkn - ink7) < 1e-4 else "   <-- synthesised"
            print(f"{family:<20}{ink7:>9.3f}{inkn:>11.3f}"
                  f"{inkn / max(ink7, 1e-6) - 1:>+8.0%}{flag}")
    return 0


CARD = """<!doctype html><meta charset="utf-8"><style>
{faces}
html,body{{margin:0;padding:0;background:#fff;font-family:'Inter',sans-serif}}
.lbl{{font-size:13px;padding:6px 0 1px}}
.row{{white-space:nowrap;padding:1px 0}}
.bar{{background:#000;color:#fff;padding:3px 6px}}
hr{{border:0;border-top:3px solid #000;margin:8px 0}}
</style><body>{blocks}</body>"""


def write_card(renderer: Renderer, families: list[str]) -> int:
    """A printable card. Paper is the only real arbiter of 'bleedy'."""
    blocks = []
    faces = "".join(face_css(f) for f in families)
    for family in families:
        size = sizes(family)[0]
        real = "real bold" if has_real_bold(family) else "NO BOLD FACE"
        style = f"font-family:'{family}';font-size:{size}px"
        blocks.append(
            f'<div class="lbl">{family} &middot; {real}</div>'
            f'<div class="row" style="{style};font-weight:400">'
            f'400 {SAMPLE}</div>'
            f'<div class="row" style="{style};font-weight:700">'
            f'700 {SAMPLE}</div>'
            f'<div class="row" style="{style};font-weight:700;'
            f'font-synthesis:none">NS_ {SAMPLE}</div>'
            f'<div class="row bar" style="{style};font-weight:700">'
            f'INV {SAMPLE}</div>'
            f'<div class="row bar" style="{style};font-weight:400;'
            f'font-synthesis:none">IN4 {SAMPLE}</div><hr>')

    img = renderer.render(CARD.format(faces=faces, blocks="".join(blocks)))
    out = Path("out/boldtest.png")
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print(f"{img.width}x{img.height} ({img.height / 8:.0f}mm) -> {out}")
    print("Rows: 400 normal / 700 bold / NS_ bold with synthesis off / "
          "INV reversed bold / IN4 reversed normal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
