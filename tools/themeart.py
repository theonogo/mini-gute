"""Draw the generated illustrations the persona themes embed, and write them in.

Some theme art is too fiddly to hand-write as a data URI - a skyline with lit
windows, rain turning black inside a cone of light, a pie chart with an exploded
slice. It is drawn here instead, as flat 1-bit SVG (black and white fills and
strokes only - never a grey, never an opacity; the page threshold erases both),
and written into the stylesheets.

A theme marks each generated image with a comment right after it:

    background-image: url("data:image/svg+xml,...") /* art:noir-street */;

and `python tools/themeart.py` redraws every marked image in every theme. Edit
the drawing here, run the tool, re-render. Hand-drawn SVG in a theme has no
marker and is never touched.

    python tools/themeart.py            # rewrite every marked image
    python tools/themeart.py --check    # report markers with no drawing
"""

from __future__ import annotations

import math
import random
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
THEMES = ROOT / "personas" / "themes"

W = 576  # printer.base.WIDTH_DOTS - these are drawn at the page's native width


def svg(w: int, h: int, body: str) -> str:
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
            f"viewBox='0 0 {w} {h}'>{body}</svg>")


def encode(markup: str) -> str:
    return urllib.parse.quote(markup, safe="/:=' ,.-")


# --------------------------------------------------------------------------
# A drawn alphabet, 5x7, for lettering inside the art. A background SVG is its
# own document and cannot reach the page's embedded faces, so a <text> element
# in one falls back to whatever the machine happens to have - which is exactly
# the silent non-determinism the font pipeline exists to prevent. These letters
# are rectangles, so they print the same everywhere, and at scale 2 the strokes
# are 2px, which is the thinnest line the head reliably lays down.

_FONT5 = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x19, 0x15, 0x13, 0x13, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C),
    "/": (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    ":": (0x00, 0x0C, 0x0C, 0x00, 0x0C, 0x0C, 0x00),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
}


def pix(x: int, y: int, text: str, scale: int = 2, fill: str = "black") -> str:
    """One path of drawn letters. 6*scale to the character, 7*scale tall."""
    runs, cx = [], x
    for ch in text.upper():
        rows = _FONT5.get(ch)
        if rows is not None:
            for ry, bits in enumerate(rows):
                run = 0
                for col in range(5):
                    if bits & (1 << (4 - col)):
                        run += 1
                    elif run:
                        runs.append((cx + (col - run) * scale, y + ry * scale, run * scale))
                        run = 0
                if run:
                    runs.append((cx + (5 - run) * scale, y + ry * scale, run * scale))
        cx += 6 * scale
    d = "".join(f"M{rx} {ry}h{w}v{scale}h-{w}z" for rx, ry, w in runs)
    return f"<path d='{d}' fill='{fill}'/>"


def pix_w(text: str, scale: int = 2) -> int:
    return len(text) * 6 * scale


# --------------------------------------------------------------------------
# The Detective: three opening shots, 576x236. The title sits in the dark on
# the left, so nothing is drawn left of x=300.

_FEDORA = ("M376 70 Q392 62 410 60 L413 44 Q423 35 435 40 Q447 35 457 43 L460 60 "
           "Q480 58 490 63 Q486 69 474 68 L460 69 L457 90 Q476 98 484 118 L492 176 "
           "L488 236 L372 236 L378 176 L386 118 Q390 102 406 96 L409 92 L402 90 "
           "Q396 88 400 84 L396 80 L401 77 L394 73 L403 71 Q392 72 376 70 Z")


def noir_blind() -> str:
    """Light through a venetian blind, and the detective standing in it."""
    h = 236
    p = [f"<rect width='{W}' height='{h}' fill='black'/>"]
    starts = [342, 326, 318, 332, 314, 324, 336, 320, 328, 340, 348]
    for i, xs in enumerate(starts):
        y = -30 + i * 25
        t = 0.2 * (W - xs)
        p.append(f"<path d='M{xs} {y+t:.1f} L{W} {y} V{y+14} L{xs} {y+t+14:.1f} Z' fill='white'/>")
    p.append("<path d='M500 0 H512 L496 236 H484 Z' fill='black'/>")
    # Rim light: a white stroke under the black figure.
    p.append(f"<path d='{_FEDORA}' fill='none' stroke='white' stroke-width='4' stroke-linejoin='round'/>")
    p.append(f"<path d='{_FEDORA}' fill='black'/>")
    p.append("<path d='M384 80 L397 79' stroke='white' stroke-width='2.4' stroke-linecap='round'/>")
    p.append("<path d='M382 77 C368 71 378 57 364 49 C352 42 362 31 350 23 C342 18 348 10 340 5' "
             "fill='none' stroke='white' stroke-width='2' stroke-linecap='round'/>")
    return svg(W, h, "".join(p))


def noir_street() -> str:
    """Rain at night, one lamp, and a man waiting in its light."""
    h = 236
    rng = random.Random(7)
    cone = "M452 46 L480 46 L572 236 L360 236 Z"
    p = [f"<defs><clipPath id='cone'><path d='{cone}'/></clipPath>"
         "<clipPath id='right'><rect x='300' y='0' width='276' height='236'/></clipPath></defs>",
         f"<rect width='{W}' height='{h}' fill='black'/>"]
    rain = " ".join(
        f"M{x:.0f} {y:.0f} l{-l*0.3:.1f} {l:.1f}"
        for x, y, l in ((rng.uniform(290, 620), rng.uniform(-30, 236), rng.uniform(12, 24))
                        for _ in range(230)))
    p.append(f"<g clip-path='url(#right)'><path d='{rain}' stroke='white' stroke-width='1.3'/></g>")
    p.append(f"<path d='{cone}' fill='white'/>")
    p.append(f"<g clip-path='url(#cone)'><path d='{rain}' stroke='black' stroke-width='1.3'/></g>")
    for y in range(206, 236, 7):
        for x in range(304, 360, 15):
            p.append(f"<path d='M{x+rng.randint(0,5)} {y} h{rng.randint(6,12)}' stroke='white' stroke-width='1.6'/>")
    p.append("<path d='M442 34 L490 34 L480 46 L452 46 Z' fill='white'/>")
    p.append("<path d='M450 34 Q466 22 482 34 Z' fill='white'/>")
    p.append("<path d='M478 26 H548' stroke='white' stroke-width='3'/>")
    p.append("<rect x='545' y='24' width='6' height='212' fill='white'/>")
    p.append("<rect x='546.5' y='120' width='3' height='116' fill='black'/>")
    p.append(f"<g transform='translate(186 100) scale(0.58)'><path d='{_FEDORA}' fill='black'/></g>")
    p.append("<path d='M438 236 L372 228 L376 236 Z' fill='black'/>")
    return svg(W, h, "".join(p))


def _stroke_letters(x: float, y: float, step: float, glyphs: list[str],
                    width: float = 2.6, vertical: bool = True) -> str:
    out = []
    for i, d in enumerate(glyphs):
        tx, ty = (x, y + i * step) if vertical else (x + i * step, y)
        out.append(f"<g transform='translate({tx} {ty})'><path d='{d}' fill='none' stroke='white' "
                   f"stroke-width='{width}' stroke-linecap='round' stroke-linejoin='round'/></g>")
    return "".join(out)


_H = "M0 0 V16 M16 0 V16 M0 8 H16"
_O = "M8 0 C-2 0 -2 16 8 16 C18 16 18 0 8 0 Z"
_T = "M0 0 H16 M8 0 V16"
_E = "M16 0 H0 V16 H16 M0 8 H12"
_L = "M0 0 V16 H16"
_P = "M0 16 V0 H10 C18 0 18 9 10 9 H0"
_N = "M0 16 V0 L16 16 V0"
_A = "M0 16 L8 0 L16 16 M3 10 H13"


def noir_skyline() -> str:
    """The city from a high window: moon, rooftops, water tower, neon, a beam.

    Every building is rim-lit up both sides as well as along its roof, so each
    one visibly stands on the ground - lit along the top only, a roof reads as a
    line floating in the dark. Lines are 3px or more: thinner white on black
    fills in at the page threshold.
    """
    h = 236
    rng = random.Random(3)
    p = [f"<rect width='{W}' height='{h}' fill='black'/>",
         "<path d='M404 236 L566 0 L576 0 L576 10 L412 236 Z' fill='white'/>",
         "<circle cx='476' cy='74' r='48' fill='white'/>",
         "<circle cx='460' cy='62' r='9' fill='none' stroke='black' stroke-width='2.4'/>"
         "<circle cx='494' cy='90' r='6' fill='none' stroke='black' stroke-width='2.4'/>"
         "<circle cx='488' cy='56' r='3.5' fill='none' stroke='black' stroke-width='2'/>"]
    blocks = [(302, 34, 98), (338, 42, 132), (382, 36, 84), (420, 50, 150),
              (472, 34, 102), (508, 38, 122), (548, 28, 88)]
    for bx, bw, bh in blocks:
        top = h - bh
        p.append(f"<path d='M{bx} {h} V{top} H{bx+bw} V{h} Z' fill='black' stroke='white' "
                 f"stroke-width='3.2' stroke-linejoin='miter'/>")
        for wy in range(top + 12, h - 8, 15):
            for wx in range(bx + 7, bx + bw - 9, 11):
                if rng.random() < 0.22:
                    p.append(f"<rect x='{wx}' y='{wy}' width='6' height='8' fill='white'/>")
    # The water tower stands on the tall roof, in front of the moon. Its legs
    # and brace are drawn twice - a wide white stroke, then a black one inside
    # it - because a plain white line vanishes against the moon and a plain
    # black one vanishes against the sky; the pair reads on both.
    bx, bw, bh = blocks[3]
    roof = h - bh
    tx = bx + (bw - 36) // 2
    legs = (f"M{tx+4} {roof} L{tx+8} {roof-24} M{tx+32} {roof} L{tx+28} {roof-24} "
            f"M{tx+18} {roof} V{roof-24} M{tx+6} {roof-8} L{tx+30} {roof-20} "
            f"M{tx+30} {roof-8} L{tx+6} {roof-20}")
    p.append(f"<path d='{legs}' fill='none' stroke='white' stroke-width='6' stroke-linecap='round'/>")
    p.append(f"<path d='{legs}' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round'/>")
    p.append(f"<g stroke='white' stroke-width='3' fill='black' stroke-linejoin='round'>"
             f"<path d='M{tx} {roof-24} h36 v-26 h-36 Z'/>"
             f"<path d='M{tx-3} {roof-50} L{tx+18} {roof-64} L{tx+39} {roof-50} Z'/></g>")
    # The neon sign, bolted to the building beside it.
    p.append("<rect x='312' y='26' width='34' height='124' fill='black' stroke='white' stroke-width='3.5'/>")
    p.append("<path d='M346 60 H356 M346 120 H356' stroke='white' stroke-width='3'/>")
    p.append(_stroke_letters(321, 36, 22, [_H, _O, _T, _E, _L], width=3.6))
    return svg(W, h, "".join(p))


# --------------------------------------------------------------------------
# Accounts Receivable: the KPI tile's chart, 160x64, and the company mark.
# Invented data, drawn to look like it means something. The tile it sits in is
# stamped UNAUDITED, which is CLAUDE.md invariant 8 doing its job.

_HATCH = ("<defs><pattern id='h' width='4' height='4' patternUnits='userSpaceOnUse'>"
          "<path d='M-1 1 l2 -2 M0 4 l4 -4 M3 5 l2 -2' stroke='black' stroke-width='1'/>"
          "</pattern></defs>")


def ar_bars() -> str:
    """Seven quarters of growth, and then this one."""
    w, h = 160, 64
    heights = [18, 24, 22, 31, 38, 46, 12]
    p = [_HATCH, f"<path d='M4 {h-4} H{w-2}' stroke='black' stroke-width='2'/>"]
    for i, bh in enumerate(heights):
        x = 8 + i * 21
        fill = "black" if i == len(heights) - 1 else "url(#h)"
        p.append(f"<rect x='{x}' y='{h-4-bh}' width='14' height='{bh}' fill='{fill}' "
                 f"stroke='black' stroke-width='1.5'/>")
    return svg(w, h, "".join(p))


def ar_line() -> str:
    """A line that only goes down, with the arrow to prove it."""
    w, h = 160, 64
    pts = [(6, 20), (28, 14), (50, 24), (72, 18), (94, 34), (116, 30), (138, 50)]
    p = [f"<path d='M4 {h-4} H{w-2} M4 4 V{h-4}' stroke='black' stroke-width='1.5'/>"]
    for gy in (16, 32, 48):
        p.append(f"<path d='M6 {gy} H{w-4}' stroke='black' stroke-width='1' stroke-dasharray='1 4'/>")
    p.append("<polyline points='" + " ".join(f"{x},{y}" for x, y in pts)
             + "' fill='none' stroke='black' stroke-width='3' stroke-linejoin='round'/>")
    p.append("<path d='M138 50 L152 58 L140 60 Z M138 50 L152 58' fill='black' stroke='black' stroke-width='3'/>")
    return svg(w, h, "".join(p))


def ar_pie() -> str:
    """Where the morning went, with one slice pulled out for emphasis."""
    w, h = 160, 64
    cx, cy, r = 50, 32, 27
    def pt(a, rr=r, ox=0.0, oy=0.0):
        import math
        return cx + ox + rr * math.cos(math.radians(a)), cy + oy + rr * math.sin(math.radians(a))
    a0, a1 = pt(-90), pt(40)
    b1 = pt(160)
    p = [_HATCH]
    p.append(f"<path d='M{cx} {cy} L{a0[0]:.1f} {a0[1]:.1f} A{r} {r} 0 0 1 {a1[0]:.1f} {a1[1]:.1f} Z' "
             f"fill='white' stroke='black' stroke-width='2'/>")
    p.append(f"<path d='M{cx} {cy} L{a1[0]:.1f} {a1[1]:.1f} A{r} {r} 0 0 1 {b1[0]:.1f} {b1[1]:.1f} Z' "
             f"fill='black' stroke='black' stroke-width='2'/>")
    # The exploded slice, nudged out up and to the left.
    c0, c1 = pt(160, ox=-6, oy=-4), pt(270, ox=-6, oy=-4)
    p.append(f"<path d='M{cx-6} {cy-4} L{c0[0]:.1f} {c0[1]:.1f} A{r} {r} 0 0 1 {c1[0]:.1f} {c1[1]:.1f} Z' "
             f"fill='url(#h)' stroke='black' stroke-width='2'/>")
    for i, fill in enumerate(("white", "black", "url(#h)")):
        y = 14 + i * 16
        p.append(f"<rect x='96' y='{y}' width='10' height='10' fill='{fill}' stroke='black' stroke-width='1.5'/>"
                 f"<path d='M112 {y+5} H{150 - i*10}' stroke='black' stroke-width='2'/>")
    return svg(w, h, "".join(p))


def ar_logo() -> str:
    """A meaningless swoosh round a T."""
    w = h = 46
    p = ["<path d='M9 30 C2 12 26 -2 40 12' fill='none' stroke='black' stroke-width='5' stroke-linecap='round'/>",
         "<path d='M37 16 C44 34 20 48 6 34' fill='none' stroke='black' stroke-width='2.5' stroke-linecap='round'/>",
         "<path d='M15 14 H31 M23 14 V34' stroke='black' stroke-width='5' stroke-linecap='square'/>"]
    return svg(w, h, "".join(p))


def ar_swoosh() -> str:
    """The annual-report cover: fine concentric arcs sweeping off the top right
    of the letterhead, behind nothing but paper."""
    w, h = W, 60
    p = []
    for i in range(8):
        r = 60 + i * 14
        p.append(f"<circle cx='{W + 20}' cy='-50' r='{r}' fill='none' stroke='black' "
                 f"stroke-width='{3 if i == 3 else 1.2}'/>")
    return svg(w, h, "".join(p))


# --------------------------------------------------------------------------
# Dot's All-Nite Diner: the sign over the door, 576x150.

def _sparkle(x: float, y: float, r: float) -> str:
    """The four-point atomic-age star, solid black."""
    k = r * 0.22
    return (f"<path d='M{x} {y-r} L{x+k} {y-k} L{x+r} {y} L{x+k} {y+k} L{x} {y+r} "
            f"L{x-k} {y+k} L{x-r} {y} L{x-k} {y-k} Z' fill='black'/>")


def diner_logo() -> str:
    """The sign over the door: a black rounded board ringed with bulbs, for the
    name the stylesheet letters onto it, flanked by atomic-age sparkles."""
    import math
    h = 150
    x0, y0, x1, y1, r = 96, 6, 480, 132, 60
    p = [f"<rect x='{x0}' y='{y0}' width='{x1-x0}' height='{y1-y0}' rx='{r}' fill='black'/>",
         f"<rect x='{x0+7}' y='{y0+7}' width='{x1-x0-14}' height='{y1-y0-14}' rx='{r-7}' "
         "fill='none' stroke='white' stroke-width='1.6'/>"]
    # Bulbs, evenly spaced round the inset rounded rectangle.
    ix0, iy0, ix1, iy1, ir = x0 + 18, y0 + 18, x1 - 18, y1 - 18, r - 18
    straight_w, straight_h = ix1 - ix0 - 2 * ir, iy1 - iy0 - 2 * ir
    arc = math.pi * ir / 2
    total = 2 * straight_w + 2 * straight_h + 4 * arc
    n = 46
    for i in range(n):
        d = total * i / n
        segs = [("h", straight_w, (ix0 + ir, iy0)), ("a", arc, (ix1 - ir, iy0 + ir, -90)),
                ("v", straight_h, (ix1, iy0 + ir)), ("a", arc, (ix1 - ir, iy1 - ir, 0)),
                ("h-", straight_w, (ix1 - ir, iy1)), ("a", arc, (ix0 + ir, iy1 - ir, 90)),
                ("v-", straight_h, (ix0, iy1 - ir)), ("a", arc, (ix0 + ir, iy0 + ir, 180))]
        for kind, length, o in segs:
            if d <= length:
                if kind == "h":  x, y = o[0] + d, o[1]
                elif kind == "h-": x, y = o[0] - d, o[1]
                elif kind == "v":  x, y = o[0], o[1] + d
                elif kind == "v-": x, y = o[0], o[1] - d
                else:
                    t = math.radians(o[2]) + d / ir
                    x, y = o[0] + ir * math.cos(t), o[1] + ir * math.sin(t)
                p.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='white'/>")
                break
            d -= length
    # The pole and the stays, and the sparkles either side.
    p.append("<path d='M96 70 H70 M480 70 H506' stroke='black' stroke-width='3'/>")
    for x, y, rr in ((42, 44, 22), (70, 112, 11), (22, 92, 7), (534, 100, 22), (508, 30, 11), (556, 50, 7)):
        p.append(_sparkle(x, y, rr))
    return svg(W, h, "".join(p))


def diner_cups() -> str:
    """The punch card's ten cups, the first one punched through."""
    w, h = 520, 44
    p = []
    for i in range(10):
        x = 8 + i * 51
        p.append(f"<path d='M{x} 10 H{x+30} V26 C{x+30} 38 {x} 38 {x} 26 Z M{x+30} 14 C{x+40} 14 {x+40} 26 {x+30} 26' "
                 f"fill='white' stroke='black' stroke-width='2.4' stroke-linejoin='round'/>")
        if i == 0:
            p.append(f"<circle cx='{x+15}' cy='22' r='8' fill='black'/>")
    return svg(w, h, "".join(p))


# --------------------------------------------------------------------------
# The Monkey Astronaut: the view from the capsule, 576x210, in three versions.

def _stars(rng: random.Random, n: int, box=(0, 0, W, 210), avoid=None) -> str:
    out = []
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if avoid and avoid(x, y):
            continue
        if rng.random() < 0.12:
            out.append(f"<path d='M{x:.0f} {y-4:.0f} V{y+4:.0f} M{x-4:.0f} {y:.0f} H{x+4:.0f}' stroke='white' stroke-width='1.4'/>")
        else:
            out.append(f"<circle cx='{x:.0f}' cy='{y:.0f}' r='{rng.choice((1, 1, 1.4, 1.8))}' fill='white'/>")
    return "".join(out)


_BANANA = "M0 0 C10 18 34 22 48 8 C44 26 14 30 -4 6 Z"


def _banana(x: float, y: float, angle: float, scale: float = 1.0,
            fill: str = "white", line: str = "black") -> str:
    """A banana, not a smile: the body, a ridge along it, a stem, a dark tip."""
    return (f"<g transform='translate({x} {y}) rotate({angle}) scale({scale})'>"
            f"<path d='{_BANANA}' fill='{fill}'/>"
            f"<path d='M4 6 C14 18 32 20 42 12' fill='none' stroke='{line}' stroke-width='1.8'/>"
            f"<path d='M-4 6 L-11 -1 L-7 -4 L0 1 Z' fill='{fill}'/>"
            f"<path d='M45 9 L49 7 L48 12 Z' fill='{line}'/></g>")


def _earth(cx: float, cy: float, r: float) -> str:
    """Home: one big continent, an island, a band of cloud - nothing like eyes."""
    k = r / 30
    return (f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='white'/>"
            f"<g transform='translate({cx} {cy}) scale({k})'>"
            "<path d='M-24 -14 C-18 -24 -4 -26 2 -18 C8 -12 0 -6 4 2 C8 10 -2 20 -10 16 "
            "C-16 12 -12 4 -20 0 C-28 -4 -28 -8 -24 -14 Z' fill='black'/>"
            "<path d='M12 8 C18 4 24 8 22 14 C18 20 10 16 12 8 Z' fill='black'/>"
            "<path d='M-4 -26 C6 -22 16 -24 24 -16 M14 -6 C20 -8 26 -4 29 0' fill='none' stroke='black' stroke-width='2'/>"
            "</g>"
            f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='black' stroke-width='1.5'/>")


def monkey_porthole() -> str:
    """Through the porthole: Earth, very far away, and a banana drifting past."""
    h = 210
    rng = random.Random(11)
    cx, cy, r = 288, 105, 86
    p = [f"<defs><clipPath id='win'><circle cx='{cx}' cy='{cy}' r='{r}'/></clipPath></defs>",
         f"<rect width='{W}' height='{h}' fill='black'/>",
         # The capsule wall: panel seams and rivets, drawn in thin white.
         "<path d='M0 40 H170 M406 40 H576 M0 170 H170 M406 170 H576 M96 0 V210 M480 0 V210' stroke='white' stroke-width='1.2'/>"]
    for x in (20, 60, 132, 444, 516, 556):
        for y in (22, 188):
            p.append(f"<circle cx='{x}' cy='{y}' r='2.2' fill='white'/>")
    p.append(_stars(rng, 50, avoid=lambda x, y: (x-cx)**2 + (y-cy)**2 < (r+14)**2))
    inner = [_stars(rng, 40, (cx-r, cy-r, cx+r, cy+r)), _earth(cx + 30, cy + 26, 30),
             _banana(cx - 60, cy - 46, -18, 1.1)]
    p.append(f"<g clip-path='url(#win)'>{''.join(inner)}</g>")
    # The porthole ring and its bolts.
    p.append(f"<circle cx='{cx}' cy='{cy}' r='{r+6}' fill='none' stroke='white' stroke-width='11'/>")
    p.append(f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='none' stroke='black' stroke-width='2'/>")
    import math
    for a in range(0, 360, 30):
        x, y = cx + (r+6) * math.cos(math.radians(a)), cy + (r+6) * math.sin(math.radians(a))
        p.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.4' fill='black'/>")
    return svg(W, h, "".join(p))


def monkey_limb() -> str:
    """The capsule over Earth's horizon, a small monkey face in its window."""
    h = 210
    rng = random.Random(5)
    p = [f"<rect width='{W}' height='{h}' fill='black'/>",
         _stars(rng, 90, (0, 0, W, 150)),
         # Earth's limb, with weather on it.
         "<circle cx='288' cy='760' r='600' fill='white'/>"]
    for i in range(7):
        x = 40 + i * 78 + rng.randint(-10, 10)
        y = 186 + rng.randint(-4, 14)
        p.append(f"<path d='M{x} {y} q18 -8 36 0 t36 0' fill='none' stroke='black' stroke-width='2'/>")
    # The capsule: a cone, a heat shield, an antenna, a window with a face in it.
    p.append("<g transform='translate(288 92) rotate(-12)'>"
             "<path d='M-44 36 L-26 -30 H26 L44 36 Z' fill='black' stroke='white' stroke-width='2.4'/>"
             "<path d='M-50 36 H50 V46 H-50 Z' fill='white'/>"
             "<path d='M0 -30 V-58 M-8 -58 H8' stroke='white' stroke-width='2.4'/>"
             "<circle cx='0' cy='4' r='15' fill='white'/>"
             "<circle cx='0' cy='6' r='8' fill='black'/><circle cx='-9' cy='2' r='4' fill='black'/>"
             "<circle cx='9' cy='2' r='4' fill='black'/>"
             "<path d='M-26 -12 H26' stroke='white' stroke-width='1.2'/></g>")
    return svg(W, h, "".join(p))


def monkey_moon() -> str:
    """The Moon, a banana planted as a flag, and home rising over the edge."""
    h = 210
    rng = random.Random(9)
    p = [f"<rect width='{W}' height='{h}' fill='black'/>", _stars(rng, 80, (0, 0, W, 130)),
         _earth(452, 64, 34),
         # The ground, with craters in outline and footprints leading to the flag.
         "<path d='M0 150 C80 138 170 146 250 140 C340 134 460 150 576 142 V210 H0 Z' fill='white'/>"]
    for x, y, rx in ((72, 172, 26), (430, 184, 34), (520, 160, 14), (190, 196, 16)):
        p.append(f"<ellipse cx='{x}' cy='{y}' rx='{rx}' ry='{rx*0.32:.0f}' fill='none' stroke='black' stroke-width='2'/>")
    for i in range(6):
        p.append(f"<ellipse cx='{150 + i*22}' cy='{188 - i*6 + (i % 2)*5}' rx='4' ry='2.2' fill='black'/>")
    p.append("<path d='M290 144 V58' stroke='white' stroke-width='3'/>")
    p.append(_banana(300, 62, 0, 1.0))
    return svg(W, h, "".join(p))


def monkey_tree() -> str:
    """The big tree, in crayon, for the margin."""
    w, h = 52, 56
    p = ["<path d='M26 54 V30 M26 40 L16 32 M26 36 L36 28' stroke='black' stroke-width='3' stroke-linecap='round'/>",
         "<path d='M8 26 C0 14 12 2 22 6 C28 -2 44 2 44 12 C54 16 50 32 38 30 C32 38 16 36 8 26 Z' "
         "fill='none' stroke='black' stroke-width='2.6' stroke-linejoin='round'/>"]
    return svg(w, h, "".join(p))


def monkey_static() -> str:
    """LOSS OF SIGNAL: a band of pure static, 576x34, random 1-bit blocks."""
    w, h = W, 34
    rng = random.Random(21)
    p = [f"<rect width='{w}' height='{h}' fill='white'/>"]
    for y in range(0, h, 2):
        x = 0
        while x < w:
            run = rng.choice((1, 2, 2, 3, 5, 8))
            if rng.random() < 0.52:
                p.append(f"<rect x='{x}' y='{y}' width='{run}' height='2' fill='black'/>")
            x += run
    return svg(w, h, "".join(p))


def monkey_banana() -> str:
    """The ration card's banana."""
    w, h = 66, 40
    p = [_banana(14, 10, 0, 1.0, fill="black", line="white")]
    return svg(w, h, "".join(p))



# --------------------------------------------------------------------------
# The Stage Manager: the house curtain, and the ghost light.

_MIRROR = " transform='translate(576 0) scale(-1 1)'"


def stage_curtain() -> str:
    """The house curtain, open: a swagged valance with a fringe, and the drapes
    tied back to either side so the playbill stands in the opening."""
    h = 210
    p = []
    for side in (0, 1):
        g = [f"<g{_MIRROR if side else ''}>"]
        for i in range(7):
            x0, top, tie = i * 12, 40, 30 + i * 3
            g.append(f"<path d='M{x0} {top} L{x0+12} {top} C{x0+12} 110 {tie+8} 126 {tie+5} 150 "
                     f"C{tie+2} 172 {x0+16} 190 {x0+12} {h} L{x0} {h} C{x0+3} 190 {tie-5} 172 {tie-3} 150 "
                     f"C{tie-2} 126 {x0} 110 {x0} {top} Z' fill='black' stroke='white' stroke-width='1.2'/>")
        rope = "M4 146 C30 158 60 158 88 142"
        g.append(f"<path d='{rope}' fill='none' stroke='white' stroke-width='7'/>"
                 f"<path d='{rope}' fill='none' stroke='black' stroke-width='3' stroke-dasharray='4 2'/>"
                 "<path d='M82 146 L74 176 L92 176 Z' fill='black'/>"
                 "<path d='M76 170 H90' stroke='white' stroke-width='1.2'/></g>")
        p.append("".join(g))
    p.append("<rect x='0' y='0' width='576' height='26' fill='black'/>")
    for i in range(4):
        x0 = i * 144
        p.append(f"<path d='M{x0} 20 Q{x0+72} 78 {x0+144} 20 Z' fill='black' stroke='white' stroke-width='1.4'/>"
                 f"<path d='M{x0+20} 30 Q{x0+72} 62 {x0+124} 30' fill='none' stroke='white' stroke-width='1.2'/>")
        for k in range(1, 14):
            t = k / 14
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * (x0 + 72) + t ** 2 * (x0 + 144)
            y = (1 - t) ** 2 * 20 + 2 * (1 - t) * t * 78 + t ** 2 * 20
            p.append(f"<path d='M{x:.1f} {y-1:.1f} V{y+8:.1f}' stroke='black' stroke-width='2.6'/>")
    for i in range(1, 4):
        x = i * 144
        p.append(f"<circle cx='{x}' cy='22' r='7' fill='white' stroke='black' stroke-width='2.4'/>"
                 f"<path d='M{x-5} 28 L{x} 48 L{x+5} 28 Z' fill='black'/>")
    p.append("<path d='M0 6 H576' stroke='white' stroke-width='1.2'/>")
    return svg(W, h, "".join(p))


def stage_ghostlight() -> str:
    """The ghost light: one bare bulb in a cage on a stand, left on all night."""
    p = ["<path d='M35 50 V104 M35 104 L16 118 M35 104 L54 118 M35 104 V118' stroke='black' "
         "stroke-width='3' stroke-linecap='round'/>",
         "<rect x='29' y='40' width='12' height='12' fill='black'/>",
         "<path d='M35 6 C20 6 18 26 28 34 V40 H42 V34 C52 26 50 6 35 6 Z' fill='white' stroke='black' stroke-width='2.4'/>",
         "<path d='M31 30 C31 22 39 22 39 30' fill='none' stroke='black' stroke-width='1.4'/>",
         "<path d='M22 12 C14 22 16 34 26 40 M48 12 C56 22 54 34 44 40 M35 2 V40' fill='none' stroke='black' stroke-width='1.6'/>"]
    for x0, y0, x1, y1 in ((10, 18, 2, 14), (60, 18, 68, 14), (12, 32, 3, 34), (58, 32, 67, 34)):
        p.append(f"<path d='M{x0} {y0} L{x1} {y1}' stroke='black' stroke-width='2' stroke-linecap='round'/>")
    return svg(70, 120, "".join(p))



# --------------------------------------------------------------------------
# The Commentary Box: the pavilion roof over the scoreboard.

def cb_pavilion() -> str:
    """The scoreboard hut's roof: a boarded gable with a clock, and a
    weathervane of a batsman on top."""
    import math
    h = 96
    p = ["<path d='M16 96 L288 32 L560 96 Z' fill='white' stroke='black' stroke-width='4' stroke-linejoin='round'/>"]
    for i in range(1, 16):
        x = 16 + i * 34
        yt = 96 - 64 * (1 - abs(x - 288) / 272)
        p.append(f"<path d='M{x:.1f} {yt+5:.1f} V94' stroke='black' stroke-width='1.2'/>")
    p.append("<circle cx='288' cy='70' r='18' fill='white' stroke='black' stroke-width='3'/>")
    for k in range(12):
        a = math.radians(k * 30)
        p.append(f"<circle cx='{288 + 13.5*math.cos(a):.1f}' cy='{70 + 13.5*math.sin(a):.1f}' r='1.1' fill='black'/>")
    p.append("<path d='M288 70 V59 M288 70 L296 74' stroke='black' stroke-width='2.4' stroke-linecap='round'/>")
    p.append("<path d='M288 32 V10 M266 18 H310 M310 18 L303 13 M310 18 L303 23 M266 18 L262 13 M266 18 L262 23' "
             "stroke='black' stroke-width='2' stroke-linecap='round' fill='none'/>")
    p.append("<circle cx='294' cy='3' r='3.4' fill='black'/>"
             "<path d='M293 7 L290 10 M293 7 L298 10 M291 5 L302 -1' stroke='black' stroke-width='2.4' stroke-linecap='round'/>")
    return svg(W, h, "".join(p))



def cb_floodlights() -> str:
    """Football: two lattice floodlight pylons either side of the board, and the
    roof of the main stand between them."""
    h = 96
    p = []
    for x in (44, 532):
        # The lattice mast, tapering to the lamp bank.
        p.append(f"<path d='M{x-14} 96 L{x-4} 24 M{x+14} 96 L{x+4} 24' stroke='black' stroke-width='3'/>")
        for i in range(6):
            y0, y1 = 96 - i * 12, 96 - (i + 1) * 12
            w0, w1 = 14 - i * 1.6, 14 - (i + 1) * 1.6
            p.append(f"<path d='M{x-w0:.1f} {y0} L{x+w1:.1f} {y1} M{x+w0:.1f} {y0} L{x-w1:.1f} {y1}' "
                     "stroke='black' stroke-width='1.4'/>")
        p.append(f"<rect x='{x-26}' y='2' width='52' height='24' fill='black'/>")
        for r in range(2):
            for c in range(4):
                p.append(f"<circle cx='{x-18+c*12}' cy='{9+r*10}' r='3.6' fill='white'/>")
    # The stand roof: a long shallow cantilever with its trusses.
    p.append("<path d='M92 86 L288 66 L484 86 V96 H92 Z' fill='white' stroke='black' stroke-width='3' stroke-linejoin='round'/>")
    for i in range(1, 14):
        x = 92 + i * 28
        p.append(f"<path d='M{x} {86 - 20 * (1 - abs(x - 288) / 196):.1f} L{x+14} 96' stroke='black' stroke-width='1.2'/>")
    p.append("<path d='M288 66 V42 M288 42 H312 L306 48 L312 54 H288' stroke='black' stroke-width='2' fill='white'/>")
    return svg(W, h, "".join(p))


def cb_posts() -> str:
    """Rugby: the H of the posts either side of the board, padded at the foot,
    and the ball going over between them."""
    h = 96
    p = []
    for x in (40, 536):
        p.append(f"<path d='M{x-18} 0 V96 M{x+18} 0 V96' stroke='black' stroke-width='5'/>"
                 f"<path d='M{x-18} 58 H{x+18}' stroke='black' stroke-width='5'/>"
                 f"<rect x='{x-26}' y='80' width='52' height='16' fill='black'/>"
                 f"<path d='M{x-26} 88 H{x+26}' stroke='white' stroke-width='1.4'/>")
    # The kick: a dashed flight and the ball, turning end over end.
    p.append("<path d='M120 90 Q288 -30 456 60' fill='none' stroke='black' stroke-width='2' stroke-dasharray='6 5'/>")
    a = -18
    p.append(f"<g transform='translate(300 22) rotate({a})'>"
             "<ellipse cx='0' cy='0' rx='22' ry='13' fill='white' stroke='black' stroke-width='3'/>"
             "<path d='M-8 0 H8 M-4 -4 V4 M0 -4 V4 M4 -4 V4' stroke='black' stroke-width='1.6'/>"
             "<path d='M-22 0 C-14 -10 14 -10 22 0' fill='none' stroke='black' stroke-width='1.2'/></g>")
    for dx, dy in ((-34, 8), (-44, 14), (-52, 22)):
        p.append(f"<path d='M{300+dx} {22+dy} h-8' stroke='black' stroke-width='2' stroke-linecap='round'/>")
    return svg(W, h, "".join(p))


def cb_marquee() -> str:
    """The wildcard: a striped marquee nobody can explain, strung with bunting,
    a question mark on its flag. Whatever is played inside it, it is not on
    any calendar."""
    h = 96
    p = []
    # The tent: a peaked canopy, striped, over a scalloped valance.
    p.append("<defs><clipPath id='tent'><path d='M60 96 L96 56 L288 22 L480 56 L516 96 Z'/></clipPath></defs>")
    p.append("<path d='M60 96 L96 56 L288 22 L480 56 L516 96 Z' fill='white' stroke='black' stroke-width='3.5' stroke-linejoin='round'/>")
    stripes = "".join(f"<path d='M288 22 L{x} 96 L{x+36} 96 Z' fill='black'/>" for x in range(24, 552, 72))
    p.append(f"<g clip-path='url(#tent)'>{stripes}</g>")
    p.append("<path d='M288 22 V4' stroke='black' stroke-width='2.4'/>"
             "<path d='M288 4 H318 L310 11 L318 18 H288 Z' fill='white' stroke='black' stroke-width='2'/>"
             "<path d='M300 8 C300 5 306 5 306 8 C306 10 303 10 303 13 M303 15.5 V16' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round'/>")
    # Bunting from the peak down to the corner poles.
    for x0, x1 in ((8, 288), (568, 288)):
        p.append(f"<path d='M{x0} 50 Q{(x0+x1)/2} 58 {x1} 30' fill='none' stroke='black' stroke-width='1.4'/>")
        p.append(f"<path d='M{x0} 50 V96' stroke='black' stroke-width='3'/>")
        for i in range(1, 8):
            t = i / 8
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * ((x0 + x1) / 2) + t ** 2 * x1
            y = (1 - t) ** 2 * 50 + 2 * (1 - t) * t * 58 + t ** 2 * 30
            if 80 < x < 496 and y > 30:
                continue
            fill = "black" if i % 2 else "white"
            p.append(f"<path d='M{x-6:.1f} {y:.1f} L{x+6:.1f} {y:.1f} L{x:.1f} {y+12:.1f} Z' fill='{fill}' stroke='black' stroke-width='1.2'/>")
    return svg(W, h, "".join(p))



def cb_hoop() -> str:
    """Basketball: a backboard with its square and the rim and net, hung from the
    arena's truss, and the shot clock either side."""
    h = 96
    p = []
    # The truss across the roof of the arena.
    p.append("<path d='M0 6 H576 M0 20 H576' stroke='black' stroke-width='2.4'/>")
    for i in range(24):
        x = i * 24
        p.append(f"<path d='M{x} 6 L{x+12} 20 L{x+24} 6' fill='none' stroke='black' stroke-width='1.4'/>")
    # The backboard, its square, the rim and the net.
    p.append("<path d='M288 20 V30' stroke='black' stroke-width='4'/>")
    p.append("<rect x='230' y='30' width='116' height='46' fill='white' stroke='black' stroke-width='4'/>")
    p.append("<rect x='266' y='48' width='44' height='26' fill='none' stroke='black' stroke-width='3'/>")
    p.append("<ellipse cx='288' cy='80' rx='26' ry='5' fill='none' stroke='black' stroke-width='4'/>")
    net = "M262 80 L270 96 L278 82 L288 96 L298 82 L306 96 L314 80 M270 96 H306"
    p.append(f"<path d='{net}' fill='none' stroke='black' stroke-width='1.8'/>")
    # Shot clocks on their poles.
    for x in (70, 506):
        p.append(f"<rect x='{x-32}' y='34' width='64' height='40' fill='black'/>"
                 f"<path d='M{x} 20 V34' stroke='black' stroke-width='3'/>")
        # 24, in segment strokes.
        p.append(f"<path d='M{x-20} 44 H{x-6} V54 H{x-20} V64 H{x-6}' fill='none' stroke='white' stroke-width='3.4'/>"
                 f"<path d='M{x+4} 44 V54 H{x+18} M{x+16} 44 V64' fill='none' stroke='white' stroke-width='3.4'/>")
    return svg(W, h, "".join(p))



# --------------------------------------------------------------------------
# The Daily Roll: the furniture of a red-top front page.

def ds_flash() -> str:
    """The flash a tabloid punches its exclusives into: a scalloped roundel with
    a flat field in the middle, so the words sit straight and fit."""
    import math
    w = h = 128
    cx = cy = 64
    pts = []
    n = 26
    for i in range(n * 2):
        a = math.radians(i * 180 / n - 90)
        r = 62 if i % 2 == 0 else 53
        pts.append(f"{cx + r * math.cos(a):.1f},{cy + r * math.sin(a):.1f}")
    return svg(w, h, f"<polygon points='{' '.join(pts)}' fill='black'/>"
               f"<circle cx='{cx}' cy='{cy}' r='50' fill='black'/>")


def ds_star() -> str:
    """The five-pointed star the paper puts beside a STAR LETTER."""
    import math
    w = h = 34
    pts = []
    for i in range(10):
        a = math.radians(i * 36 - 90)
        r = 16 if i % 2 == 0 else 7
        pts.append(f"{17 + r * math.cos(a):.1f},{17 + r * math.sin(a):.1f}")
    return svg(w, h, f"<polygon points='{' '.join(pts)}' fill='black'/>")


def ds_poll() -> str:
    """The SHOCK POLL: four bars, hatched, with the winner solid."""
    w, h = 520, 132
    p = [_HATCH, f"<path d='M40 {h-18} H{w-8}' stroke='black' stroke-width='3'/>"]
    for i, (val, solid) in enumerate(((0.92, True), (0.55, False), (0.31, False), (0.06, False))):
        y = 6 + i * 27
        bar = int((w - 120) * val)
        fill = "black" if solid else "url(#h)"
        p.append(f"<rect x='40' y='{y}' width='{bar}' height='19' fill='{fill}' "
                 "stroke='black' stroke-width='2'/>")
        p.append(f"<rect x='8' y='{y}' width='24' height='19' fill='none' stroke='black' stroke-width='2'/>")
        if solid:
            p.append(f"<path d='M13 {y+10} L18 {y+15} L27 {y+4}' fill='none' stroke='black' stroke-width='3'/>")
    return svg(w, h, "".join(p))


# --------------------------------------------------------------------------
# The Machine: what a thermal printer prints when it tests itself.

def tm_selftest() -> str:
    """The self-test strip: eight density ramps ordered-dithered the way the
    head actually lays ink down, a checkerboard at four cell sizes, and the
    alignment ticks. Every cell is a real 1-bit pattern, never a grey."""
    w, h = W, 56
    bayer = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]
    p = [f"<rect width='{w}' height='{h}' fill='white'/>"]
    for i in range(8):
        x0 = 8 + i * 42
        level = (i + 1) * 2          # 2/16 .. 16/16 of the dots
        p.append(f"<rect x='{x0}' y='6' width='36' height='22' fill='none' stroke='black' stroke-width='1'/>")
        for row, yy in enumerate(range(8, 28, 2)):
            for col, xx in enumerate(range(x0 + 2, x0 + 36, 2)):
                if bayer[row % 4][col % 4] < level:
                    p.append(f"<rect x='{xx}' y='{yy}' width='2' height='2' fill='black'/>")
    for i, cell in enumerate((2, 3, 4, 6)):
        x0 = 8 + i * 42
        for yy in range(32, 50, cell):
            for xx in range(x0, x0 + 36, cell):
                if ((xx - x0) // cell + (yy - 32) // cell) % 2 == 0:
                    p.append(f"<rect x='{xx}' y='{yy}' width='{cell}' height='{cell}' fill='black'/>")
    p.append(f"<path d='M{W-160} 34 H{W-8} M{W-160} 48 H{W-8}' stroke='black' stroke-width='1'/>")
    for i in range(0, 152, 4):
        p.append(f"<rect x='{W-160+i}' y='38' width='2' height='6' fill='black'/>")
    p.append(f"<path d='M4 {h-3} H{W-4}' stroke='black' stroke-width='2'/>")
    return svg(w, h, "".join(p))



# --------------------------------------------------------------------------
# The Time Traveller: an interface from later, downgraded to run on paper.

def tt_glyphs() -> str:
    """A line of writing from a couple of centuries ahead. Drawn, not typed -
    no font we have contains it, which is the joke."""
    rng = random.Random(2231)
    w, h = W, 34
    p = []
    x = 10
    while x < W - 26:
        n = rng.randint(2, 4)
        top, bot = 7, 27
        d = []
        cx = x
        for i in range(n):
            style = rng.randint(0, 5)
            if style == 0:
                d.append(f"M{cx} {bot} V{top} M{cx} {top} L{cx+9} {top+8}")
            elif style == 1:
                d.append(f"M{cx} {top} H{cx+9} M{cx+4} {top} V{bot} M{cx} {bot} H{cx+9}")
            elif style == 2:
                d.append(f"M{cx} {bot} L{cx+5} {top} L{cx+10} {bot} M{cx+2} {top+12} H{cx+8}")
            elif style == 3:
                d.append(f"M{cx+9} {top} H{cx} V{top+9} H{cx+8} M{cx} {bot} H{cx+9}")
            elif style == 4:
                d.append(f"M{cx} {top+4} Q{cx+5} {top-4} {cx+10} {top+4} M{cx+5} {top+4} V{bot}")
            else:
                d.append(f"M{cx} {top} V{bot} M{cx+9} {top} V{bot} M{cx} {top+10} H{cx+9}")
            cx += 13
        p.append(f"<path d='{' '.join(d)}' fill='none' stroke='black' stroke-width='2.6' "
                 "stroke-linecap='round' stroke-linejoin='round'/>")
        if rng.random() < 0.3:
            p.append(f"<circle cx='{x + (n*13) - 4}' cy='{bot + 4}' r='1.8' fill='black'/>")
        x += n * 13 + 12
    return svg(w, h, "".join(p))


def tt_code() -> str:
    """The glyph grid on the coupon, which is very clearly not a QR code: it has
    the wrong number of corners and one of them has wandered."""
    rng = random.Random(77)
    cells, size = 11, 10
    w = h = cells * size + 8
    p = [f"<rect width='{w}' height='{h}' fill='white'/>"]
    for r in range(cells):
        for c in range(cells):
            if rng.random() < 0.42:
                p.append(f"<rect x='{4 + c*size}' y='{4 + r*size}' width='{size}' height='{size}' fill='black'/>")
    # Three corner markers, as any code has - and a fourth, which none has.
    def marker(cx, cy, r=3):
        s = size
        return (f"<rect x='{4+cx*s}' y='{4+cy*s}' width='{r*s}' height='{r*s}' fill='black'/>"
                f"<rect x='{4+cx*s+s*0.6:.0f}' y='{4+cy*s+s*0.6:.0f}' width='{r*s-s*1.2:.0f}' "
                f"height='{r*s-s*1.2:.0f}' fill='white'/>"
                f"<rect x='{4+cx*s+s*1.1:.0f}' y='{4+cy*s+s*1.1:.0f}' width='{r*s-s*2.2:.0f}' "
                f"height='{r*s-s*2.2:.0f}' fill='black'/>")
    p.append(marker(0, 0))
    p.append(marker(cells - 3, 0))
    p.append(marker(0, cells - 3))
    # The fourth marker, off the grid and at an angle. It should not be there.
    p.append(f"<g transform='translate({w-34} {h-30}) rotate(14)'>{marker(0, 0, 2)}</g>")
    return svg(w, h, "".join(p))


def tt_timeline() -> str:
    """The weather's timeline: all of it, with today a tick near the start."""
    w, h = 520, 46
    p = ["<path d='M6 24 H514' stroke='black' stroke-width='2.4'/>",
         "<path d='M506 18 L514 24 L506 30' fill='none' stroke='black' stroke-width='2.4'/>"]
    for i in range(1, 26):
        x = 6 + i * 19.5
        tall = i % 5 == 0
        p.append(f"<path d='M{x:.0f} {24 - (9 if tall else 5)} V24' stroke='black' stroke-width='{2 if tall else 1.2}'/>")
    # Today.
    p.append("<path d='M64 6 V24' stroke='black' stroke-width='3'/>"
             "<circle cx='64' cy='6' r='4' fill='black'/>")
    p.append("<path d='M64 30 V40' stroke='black' stroke-width='1.6' stroke-dasharray='3 3'/>")
    return svg(w, h, "".join(p))


# --------------------------------------------------------------------------
# The Bootleg Tape: three mastheads, rotated by date. Furniture only - a
# background SVG is its own document and cannot reach the page's embedded
# faces, so every word on these is written by the theme over the top.

def bt_cassette() -> str:
    """The tape itself, straight on: shell, label, window, both reels."""
    h = 286
    p = ["<g fill='none' stroke='black' stroke-width='5' stroke-linejoin='round'>",
         "<rect x='14' y='10' width='548' height='266' rx='16'/>",
         "<rect x='44' y='36' width='488' height='104' rx='4'/>",
         "<rect x='128' y='158' width='320' height='96' rx='6'/>", "</g>",
         "<g fill='none' stroke='black' stroke-width='3'>"]
    # The reels: tape wound off the left hub and onto the right.
    p += ["<circle cx='206' cy='206' r='44'/><circle cx='370' cy='206' r='44'/>",
          "<circle cx='206' cy='206' r='30'/><circle cx='370' cy='206' r='19'/>",
          "<path d='M128 206 H162 M414 206 H448'/>"]
    for cx, cy in ((46, 36), (530, 36), (46, 250), (530, 250)):   # the screws
        p.append(f"<circle cx='{cx}' cy='{cy}' r='7'/>"
                 f"<path d='M{cx-4} {cy-4} l8 8 M{cx+4} {cy-4} l-8 8'/>")
    p.append("</g>")
    p += ["<g fill='black'>",
          "<circle cx='206' cy='206' r='13'/><circle cx='370' cy='206' r='13'/>",
          "<rect x='268' y='258' width='40' height='14'/>",      # pressure pad
          "<rect x='78' y='260' width='30' height='10'/>",       # guide holes
          "<rect x='468' y='260' width='30' height='10'/>", "</g>"]
    # Hub teeth, so the reels read as driven rather than drawn.
    p.append("<g stroke='black' stroke-width='3'>"
             "<path d='M198 193 h16 M198 219 h16 M193 200 v12 M219 200 v12'/>"
             "<path d='M362 199 h16 M362 213 h16'/></g>")
    # The write-protect tabs, one of them punched out.
    p.append("<g fill='none' stroke='black' stroke-width='3'>"
             "<rect x='58' y='150' width='34' height='22'/>"
             "<rect x='484' y='150' width='34' height='22' fill='black'/></g>")
    # Drawn lettering: what a shell has moulded into it.
    p.append(pix(52, 15, "STEREO", 2))
    p.append(pix(166, 15, "LOW NOISE HIGH OUTPUT", 2))
    p.append(pix(440, 15, "DOLBY B", 2))
    return svg(W, h, "".join(p))


def _seven(x: int, y: int, text: str, scale: float = 1.0) -> str:
    """A seven-segment readout, drawn. 40px to the digit at scale 1."""
    seg = {"a": "M7 1 H29 L23 8 H13 Z", "b": "M31 3 V27 L24 22 V9 Z",
           "c": "M31 33 V57 L24 51 V38 Z", "d": "M7 59 H29 L23 52 H13 Z",
           "e": "M5 33 V57 L12 51 V38 Z", "f": "M5 3 V27 L12 22 V9 Z",
           "g": "M7 30 L13 25 H23 L29 30 L23 35 H13 Z"}
    lit = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
           "5": "afgcd", "6": "afgecd", "7": "abc", "8": "abcdefg",
           "9": "abfgcd", "-": "g"}
    out, dx = [], 0
    for ch in text:
        if ch == ":":
            out.append(f"<circle cx='{dx+8}' cy='20' r='4' fill='white'/>"
                       f"<circle cx='{dx+8}' cy='40' r='4' fill='white'/>")
            dx += 20
            continue
        out.append("".join(f"<path d='{seg[k]}' fill='white' "
                           f"transform='translate({dx} 0)'/>" for k in lit[ch]))
        dx += 40
    return (f"<g transform='translate({x} {y}) scale({scale})'>"
            + "".join(out) + "</g>")


def bt_player() -> str:
    """A media player skin of the late nineties: title bar, readout, analyser,
    a marquee waiting for its text, sliders, and a seek bar."""
    h = 244
    p = [f"<rect width='{W}' height='{h}' fill='black'/>",
         "<g fill='none' stroke='white' stroke-width='2'>",
         "<rect x='8' y='6' width='560' height='30'/>",          # title bar
         "<rect x='8' y='36' width='560' height='202'/>",        # the body
         "<rect x='212' y='44' width='348' height='54'/>",       # analyser
         "<rect x='16' y='120' width='544' height='30'/>",       # marquee
         "<rect x='66' y='160' width='300' height='16'/>",       # volume
         "<rect x='400' y='160' width='92' height='16'/>",       # balance
         "<rect x='500' y='158' width='28' height='20'/>",       # EQ
         "<rect x='532' y='158' width='28' height='20'/>",       # PL
         "<rect x='16' y='188' width='544' height='20'/>", "</g>"]   # seek
    for i, x in enumerate((16, 34, 52)):                         # window buttons
        p.append(f"<rect x='{x}' y='13' width='14' height='15' fill='none' "
                 f"stroke='white' stroke-width='2'/>")
    p.append("<rect x='524' y='13' width='14' height='15' fill='none' "
             "stroke='white' stroke-width='2'/>"
             "<rect x='544' y='13' width='14' height='15' fill='none' "
             "stroke='white' stroke-width='2'/>")
    p.append(_seven(22, 52, "-2:41", 0.92))
    # The analyser, with peak caps hanging above the bars.
    heights = [10, 26, 17, 40, 47, 31, 14, 35, 52, 21, 11, 29, 43, 24, 13, 33, 18]
    for i, v in enumerate(heights):
        x = 222 + i * 19
        v = max(6, int(v * 0.82))
        p.append(f"<rect x='{x}' y='{92 - v}' width='13' height='{v}' fill='white'/>")
        p.append(f"<rect x='{x}' y='{max(48, 92 - v - 8)}' width='13' height='3' fill='white'/>")
    p.append("<rect x='288' y='157' width='13' height='22' fill='white'/>")  # vol thumb
    p.append("<rect x='438' y='157' width='13' height='22' fill='white'/>")  # bal thumb
    p.append("<rect x='186' y='186' width='26' height='24' fill='white'/>")  # seek thumb
    # The switch legends along the foot of the panel.
    p.append(pix(20, 216, "SHUFFLE", 2, "white"))
    p.append(pix(128, 216, "REPEAT", 2, "white"))
    p.append(pix(250, 216, "0:00 / 45:00", 2, "white"))
    p.append(pix(410, 216, "OUT: LINE", 2, "white"))
    return svg(W, h, "".join(p))


def bt_disc() -> str:
    """A record on the left with the arm down on it, a waveform on the right."""
    h = 266
    cx, cy = 128, 126
    p = [f"<circle cx='{cx}' cy='{cy}' r='112' fill='black'/>",
         "<g fill='none' stroke='white' stroke-width='1.6'>"]
    p += [f"<circle cx='{cx}' cy='{cy}' r='{r}'/>" for r in range(48, 108, 7)]
    p += ["</g>", f"<circle cx='{cx}' cy='{cy}' r='42' fill='white'/>",
          "<g fill='none' stroke='black' stroke-width='2'>",
          f"<path d='M{cx} {cy-36} A36 36 0 0 1 {cx+28} {cy-22}'/>",
          f"<path d='M{cx} {cy+36} A36 36 0 0 1 {cx-28} {cy+22}'/></g>",
          f"<circle cx='{cx}' cy='{cy}' r='6' fill='black'/>"]
    # The arm, pivoted top right of the platter, stylus down on the outer groove.
    p += ["<g fill='none' stroke='black' stroke-width='5' stroke-linecap='round'>",
          "<path d='M262 30 L214 80'/><path d='M214 80 l-13 12'/></g>",
          "<circle cx='262' cy='30' r='15' fill='white' stroke='black' stroke-width='5'/>",
          "<circle cx='262' cy='30' r='4' fill='black'/>",
          "<rect x='190' y='86' width='24' height='15' fill='black' "
          "transform='rotate(-45 202 93)'/>"]
    # The waveform, under where the theme writes the title.
    wave = [7, 19, 10, 28, 36, 21, 32, 13, 26, 40, 16, 9, 24, 33, 12, 20, 29,
            10, 15, 35, 8, 22, 31, 14]
    for i, v in enumerate(wave):
        x = 286 + i * 11
        v = int(v * 0.9)
        p.append(f"<rect x='{x}' y='{224 - v}' width='6' height='{v}' fill='black'/>")
    p.append("<path d='M286 228 H558' stroke='black' stroke-width='2'/>")
    p.append("<rect x='500' y='14' width='60' height='26' fill='black'/>")
    p.append(pix(104, 116, "A", 2))
    p.append(pix(286, 234, "STEREO", 2))
    p.append(pix(390, 234, "LONG PLAY", 2))
    p.append(pix(44, 246, "HOME PRESSING", 2))
    return svg(W, h, "".join(p))



# --------------------------------------------------------------------------
# The Revolutionary. Intercepted material: a basement, a transmitter, and a
# woman who has not slept. Everything here is drawn rather than typed because
# it is the part of the page that is not language - noise, a thumb, a stamp.


def nj_static() -> str:
    """A band of radio static, 576x16, between transmissions."""
    rng = random.Random(4041)
    bars, x = [], 0
    while x < W:
        w = rng.choice((1, 1, 1, 2, 2, 3))
        h = rng.choice((2, 3, 4, 6, 9, 13, 16))
        y = rng.randrange(0, 16 - h + 1)
        bars.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}'/>")
        x += w + rng.choice((0, 1, 1, 1, 2, 2, 3, 5))
    return svg(W, 16, f"<g fill='black'>{''.join(bars)}</g>")


def nj_redacted() -> str:
    """A paragraph with every word blacked out, 548x104.

    Five lines of bars at word lengths. It says nothing, which is the joke: the
    censor has been through a page that did not need censoring.
    """
    rng = random.Random(1917)
    rows = []
    y = 4
    for line in range(5):
        x = 0
        limit = 548 if line < 4 else rng.randrange(230, 400)
        while x < limit - 20:
            w = min(rng.randrange(26, 96), limit - x)
            rows.append(f"<rect x='{x}' y='{y}' width='{w}' height='13'/>")
            x += w + rng.choice((7, 8, 9, 11))
        y += 20
    return svg(548, 104, f"<g fill='black'>{''.join(rows)}</g>")


def nj_thumb() -> str:
    """A thumbprint, 116x148. Ridges as broken arcs around a whorl."""
    rng = random.Random(77)
    cx, cy = 58, 76
    ridges = []
    for i in range(11):
        rx, ry = 6 + i * 4.6, 8 + i * 6.0
        # Each ridge is drawn as two arcs with a gap, so it reads as skin
        # rather than as a contour map.
        gap = rng.uniform(0.25, 0.75)
        a0 = rng.uniform(0, 6.283)
        for half in (0, 1):
            start = a0 + half * 3.1416 + (gap if half else 0)
            end = start + 3.1416 - gap
            x0, y0 = cx + rx * math.cos(start), cy + ry * math.sin(start)
            x1, y1 = cx + rx * math.cos(end), cy + ry * math.sin(end)
            big = 0
            ridges.append(f"<path d='M{x0:.1f} {y0:.1f}A{rx:.1f} {ry:.1f} 0 "
                          f"{big} 1 {x1:.1f} {y1:.1f}'/>")
    core = (f"<path d='M{cx - 5} {cy + 6}q5 -12 10 -2q4 8 -6 9q-11 1 -9 -12"
            f"q2 -12 15 -9'/>")
    return svg(116, 148,
               f"<g fill='none' stroke='black' stroke-width='2.4' "
               f"stroke-linecap='round'>{''.join(ridges)}{core}</g>")


def nj_stamp() -> str:
    """A rubber stamp that did not take cleanly, 178x178.

    The smudge is white rectangles laid over the finished stamp - the ink is
    1-bit, so a gap in it is the only way a stamp can look badly pressed.
    """
    rng = random.Random(1848)
    cx = cy = 89
    parts = [f"<circle cx='{cx}' cy='{cy}' r='80' fill='none' stroke='black' "
             f"stroke-width='6'/>",
             f"<circle cx='{cx}' cy='{cy}' r='69' fill='none' stroke='black' "
             f"stroke-width='2.5'/>"]
    for i, line in enumerate(("NOT VALID", "FOR TRAVEL")):
        parts.append(pix(cx - pix_w(line, 2) // 2, cy - 36 + i * 20, line, 2))
    bar_w = pix_w("USE ANYWAY", 2) + 12
    parts.append(f"<rect x='{cx - bar_w // 2}' y='{cy + 2}' width='{bar_w}' "
                 f"height='18'/>")
    parts.append(pix(cx - pix_w("USE ANYWAY", 2) // 2, cy + 4,
                     "USE ANYWAY", 2, fill='white'))
    parts.append(pix(cx - pix_w("44-K", 2) // 2, cy + 30, "44-K", 2))
    smudge = []
    for _ in range(10):
        w, h = rng.randrange(9, 40), rng.randrange(3, 12)
        smudge.append(f"<rect x='{rng.randrange(0, 178 - w)}' "
                      f"y='{rng.randrange(0, 178 - h)}' width='{w}' "
                      f"height='{h}' fill='white'/>")
    return svg(178, 178, f"<g fill='black'>{''.join(parts)}</g>"
                         + "".join(smudge))



def nj_dial() -> str:
    """The set she is transmitting on, 548x74: a tuning scale with the needle
    parked on her frequency, the bands either side of it, and a signal meter.

    Drawn rather than typed because it is the one part of the head that is not
    language - a reader should know it is a radio before reading a word of it.
    """
    w, h = 548, 74
    parts = []

    # The dial window: a frame with the scale inside it.
    parts.append(f"<rect x='1.5' y='1.5' width='{w - 96}' height='{h - 3}' "
                 f"fill='none' stroke='black' stroke-width='3'/>")

    # The scale. Majors every 60px with a figure under them, minors between.
    base = 46
    x0, step = 26, 60
    parts.append(f"<path d='M{x0 - 8} {base}H{x0 + step * 7 + 8}' "
                 f"stroke='black' stroke-width='2'/>")
    for i in range(8):
        x = x0 + i * step
        parts.append(f"<path d='M{x} {base}V{base - 16}' stroke='black' "
                     f"stroke-width='3'/>")
        label = f"{4 + i}.0" if i % 2 == 0 else ""
        if label:
            parts.append(pix(x - pix_w(label, 1) // 2, base + 6, label, 1))
        for j in range(1, 5):
            mx = x + j * step / 5
            if mx < x0 + step * 7:
                parts.append(f"<path d='M{mx:.0f} {base}V{base - 8}' "
                             f"stroke='black' stroke-width='1.5'/>")

    # The bands, in the top of the window.
    for i, (label, bx) in enumerate((("LW", 24), ("MW", 96), ("SW", 200),
                                     ("VHF", 330))):
        bw = pix_w(label, 1) + 10
        parts.append(f"<rect x='{bx}' y='8' width='{bw}' height='14' "
                     f"fill='{'black' if label == 'SW' else 'none'}' "
                     f"stroke='black' stroke-width='2'/>")
        parts.append(pix(bx + 5, 12, label, 1,
                         fill="white" if label == "SW" else "black"))

    # The needle, parked just past 6.0 - which is where she is.
    nx = x0 + step * 2 + 14
    parts.append(f"<path d='M{nx} 4V{base + 14}' stroke='black' "
                 f"stroke-width='3'/>")
    parts.append(f"<path d='M{nx - 9} 4h18l-9 12Z' fill='black'/>")

    # Signal meter, right of the window: five bars, four of them lit.
    mx0 = w - 84
    parts.append(f"<rect x='{mx0 - 4}' y='1.5' width='{88}' height='{h - 3}' "
                 f"fill='none' stroke='black' stroke-width='3'/>")
    for i in range(5):
        bh = 10 + i * 9
        parts.append(f"<rect x='{mx0 + 6 + i * 15}' y='{52 - bh}' width='11' "
                     f"height='{bh}' fill='{'black' if i < 4 else 'none'}' "
                     f"stroke='black' stroke-width='2'/>")
    parts.append(pix(mx0 + 8, 58, "SIG 4/5", 1))

    return svg(w, h, "".join(parts))


# --------------------------------------------------------------------------
# The Mimic. Two drawings, and both of them are it getting something wrong in
# good faith.


# Half a human, down the right side: crown, head, neck, shoulder, out along the
# arm and back up its inside, down the flank, out along the leg and back up its
# inside to the crotch. Mirrored and smoothed into a closed contour, because a
# figure assembled out of sticks is a child's drawing and this creature believes
# it is producing a medical plate.
_HALF = [
    (0, 18), (16, 23), (21, 38), (18, 53), (11, 61),
    (29, 66), (46, 73),
    (54, 95), (58, 123), (55, 149),
    (60, 177), (57, 199), (63, 213),
    (49, 219), (43, 201), (41, 177),
    (37, 149), (34, 121), (30, 95),
    (28, 85),
    (31, 97), (35, 129), (29, 157), (26, 175),
    (34, 189), (38, 219), (35, 257), (32, 291),
    (36, 317), (21, 321),
    (15, 291), (12, 253), (9, 213),
    (0, 195),
]

_LABELS = (
    # (text, label x, label y, leader start, leader end/anchor)
    ("FORK HOLE", 380, 40, 374, 46, 300, 40),
    ("THE GRIEF ONE", 372, 96, 366, 102, 306, 104),
    ("SPARE", 392, 176, 386, 182, 346, 186),
    ("ELBOW", 74, 142, 158, 148, 233, 150),
    ("SECOND ELBOW", 34, 196, 160, 202, 231, 176),
    ("LEFT KNEE", 84, 258, 160, 264, 256, 258),
    ("OTHER LEFT KNEE", 330, 300, 324, 306, 318, 292),
)


def _chaikin(points: list[tuple[float, float]], passes: int = 3):
    """Corner-cutting on a closed polygon. Three passes is the difference
    between a shape that was drawn and a shape that was specified."""
    for _ in range(passes):
        out = []
        for i, (x0, y0) in enumerate(points):
            x1, y1 = points[(i + 1) % len(points)]
            out.append((x0 * 0.75 + x1 * 0.25, y0 * 0.75 + y1 * 0.25))
            out.append((x0 * 0.25 + x1 * 0.75, y0 * 0.25 + y1 * 0.75))
        points = out
    return points


def mimic_anatomy() -> str:
    """A human, drawn with great care and confidently mislabelled, 576x352."""
    cx = 288
    contour = ([(cx + dx, y) for dx, y in _HALF]
               + [(cx - dx, y) for dx, y in reversed(_HALF[1:-1])])
    pts = _chaikin(contour)
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"

    body = [f"<path d='{d}' fill='none' stroke='black' stroke-width='3'/>",
            # the plate's own marks: a centre line, and the neck and waist
            # the diagram measures from
            f"<path d='M{cx} 14V330' stroke='black' stroke-width='1.5' "
            f"stroke-dasharray='5 7'/>",
            f"<path d='M{cx - 30} 64h60M{cx - 30} 176h60' stroke='black' "
            f"stroke-width='1.5' stroke-dasharray='3 5'/>"]
    for _, _, _, x0, y0, x1, y1 in _LABELS:
        body.append(f"<path d='M{x0} {y0}L{x1} {y1}' stroke='black' "
                    f"stroke-width='2'/>")
        body.append(f"<circle cx='{x1}' cy='{y1}' r='4.5' fill='black'/>")
    for text, lx, ly, *_ in _LABELS:
        body.append(pix(lx, ly, text, 2))
    body.append(pix(16, 12, "FIG 1. A HUMAN", 2))
    body.append(pix(16, 30, "DRAWN CORRECTLY", 2))
    body.append(f"<path d='M14 48h{pix_w('DRAWN CORRECTLY', 2) + 4}' "
                f"stroke='black' stroke-width='2'/>")
    return svg(W, 352, "".join(body))


def mimic_hello() -> str:
    """A second barcode, made by the Mimic, 576x40.

    Real CODE39, so it really scans, and what it says is HELLO. Drawn from the
    module string rather than the image writer for the same reason the page's
    own barcode is (render/barcode.py): whole-pixel bars, no grey edges.
    """
    from render.barcode import QUIET_MODULES, modules
    bits = modules("HELLO")
    total = len(bits) + QUIET_MODULES * 2
    m = max(1, W // total)
    x = (W - total * m) // 2 + QUIET_MODULES * m
    bars = []
    for bit in bits:
        if bit == "1":
            bars.append(f"<rect x='{x}' y='0' width='{m}' height='34'/>")
        x += m
    caption = pix((W - pix_w("HELLO", 2)) // 2, 37, "HELLO", 2)
    return svg(W, 54, f"<g fill='black'>{''.join(bars)}</g>{caption}")



def mimic_hand() -> str:
    """A hand it has drawn from life, 136x162.

    Six fingers, because it counted. Nothing else on the page says out loud what
    is wearing the costume, and this does not say it either - it is simply a
    hand, drawn carefully, with one finger too many.

    Fingers, then the palm over their roots, then the thumb over the palm: each
    shape is filled white and stroked black, and the order is the order the parts
    sit in front of each other. On a 1-bit page that is the only way to get an
    overlap - there is no erasing, only painting white.
    """
    ink = "fill='white' stroke='black' stroke-width='3' stroke-linejoin='round'"
    parts = []
    # Six of them. The last one is shorter and sits where a hand does not have
    # one, which is the whole drawing.
    for x, top in ((26, 54), (43, 30), (60, 20), (77, 30), (94, 52), (111, 70)):
        parts.append(f"<path d='M{x} 120V{top + 9}q0-9 8-9t8 9V120Z' {ink}/>")
    # The palm, over the top of the fingers, tapering to a wrist.
    parts.append(f"<path d='M28 114q0-10 10-12h84q10 2 10 12v20q0 14-6 24"
                 f"l-5 16H39l-5-16q-6-10-6-24Z' {ink}/>")
    # The thumb LAST, because a thumb is in front of the palm rather than
    # behind it - drawn first, the palm simply painted over it.
    parts.append(f"<path d='M40 118L12 140q-9 8-3 17t18 2l26-19Z' {ink}/>")
    return svg(136, 162, "".join(parts))


# --------------------------------------------------------------------------
# The Clerk: engraved furniture. Everything here is line-work - a Victorian
# jobbing printer had rules, flowers and a seal and no way to print a tone at
# all, so his register is exactly the one the page threshold wants anyway.


def _spiral(cx: float, cy: float, r: float, turns: float = 1.55,
            start: float = 0.0, flip: int = 1) -> str:
    """One engraved scroll, drawn as a polyline winding inward."""
    pts = []
    steps = 44
    for i in range(steps + 1):
        t = i / steps
        a = start + flip * t * turns * 2 * math.pi
        rad = r * (1 - 0.78 * t)
        pts.append(f"{cx + rad * math.cos(a):.1f} {cy + rad * math.sin(a):.1f}")
    return "M" + " L".join(pts)


def _leaf(x: float, y: float, length: float, width: float,
          angle: float, flip: int = 1) -> str:
    """A pointed leaf, from its stem to its tip."""
    a = math.radians(angle)
    tx, ty = x + length * math.cos(a), y + length * math.sin(a)
    nx, ny = -math.sin(a) * width * flip, math.cos(a) * width * flip
    c1x, c1y = x + (tx - x) * 0.35 + nx, y + (ty - y) * 0.35 + ny
    c2x, c2y = x + (tx - x) * 0.72 + nx * 0.55, y + (ty - y) * 0.72 + ny * 0.55
    return (f"M{x:.1f} {y:.1f} C{c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} "
            f"{tx:.1f} {ty:.1f} C{c2x - nx * 1.7:.1f} {c2y - ny * 1.7:.1f} "
            f"{c1x - nx * 1.7:.1f} {c1y - ny * 1.7:.1f} {x:.1f} {y:.1f} Z")


def _rosette(cx: float, cy: float, r: float, petals: int = 6) -> str:
    """The flower in the middle of an ornament. Petals filled, centre left
    white inside a ring - engraved, not a blob."""
    out = []
    for i in range(petals):
        a = i * 360 / petals
        out.append(f"<path d='{_leaf(cx, cy, r, r * 0.42, a, 1)}' fill='black'/>")
        out.append(f"<path d='{_leaf(cx, cy, r, r * 0.42, a, -1)}' fill='black'/>")
    out.append(f"<circle cx='{cx}' cy='{cy}' r='{r * 0.34:.1f}' fill='white'/>")
    out.append(f"<circle cx='{cx}' cy='{cy}' r='{r * 0.34:.1f}' fill='none' "
               f"stroke='black' stroke-width='2'/>")
    out.append(f"<circle cx='{cx}' cy='{cy}' r='{r * 0.12:.1f}' fill='black'/>")
    return "".join(out)


def vc_headpiece() -> str:
    """The headpiece over the ledger: a printer's flower between two scrolls,
    with a hairline pair running out to both margins."""
    h = 66
    cy = h / 2
    p = [f"<path d='M0 {cy - 9} H176 M0 {cy + 9} H176 M400 {cy - 9} H576 "
         f"M400 {cy + 9} H576' stroke='black' stroke-width='2' fill='none'/>"]
    for side, flip in ((0, 1), (1, -1)):
        ox = 232 if side == 0 else 344
        p.append(f"<path d='{_spiral(ox, cy, 22, 1.5, math.pi if side else 0, flip)}' "
                 f"fill='none' stroke='black' stroke-width='2.6'/>")
        for a in (-34, 34):
            p.append("<path d='"
                     + _leaf(ox + (18 if side else -18), cy, 40, 8,
                             a if side else 180 - a)
                     + "' fill='black'/>")
        bx = 186 if side == 0 else 390
        p.append(f"<circle cx='{bx}' cy='{cy}' r='5' fill='black'/>")
        p.append(f"<path d='M{bx + (10 if side else -10)} {cy} "
                 f"h{14 if side else -14}' stroke='black' stroke-width='2.6'/>")
    p.append(_rosette(288, cy, 21))
    return svg(W, h, "".join(p))


def vc_swell() -> str:
    """A swelled rule - thick at the middle, tapering to nothing at each end,
    with a lozenge either side. The Victorian section break."""
    h = 13
    cy = h / 2
    # Thin. At 460px across, a centre band of 11px printed as a blot rather
    # than a rule - the swell has to read as a line that thickens, not a lens.
    body = (f"M88 {cy} C170 {cy - 2.6} 240 {cy - 3.4} 288 {cy - 3.4} "
            f"C336 {cy - 3.4} 406 {cy - 2.6} 488 {cy} "
            f"C406 {cy + 2.6} 336 {cy + 3.4} 288 {cy + 3.4} "
            f"C240 {cy + 3.4} 170 {cy + 2.6} 88 {cy} Z")
    p = [f"<path d='{body}' fill='black'/>"]
    for x in (70, 506):
        p.append(f"<path d='M{x} {cy - 4.4} L{x + 8} {cy} L{x} {cy + 4.4} "
                 f"L{x - 8} {cy} Z' fill='black'/>")
    return svg(W, h, "".join(p))


def vc_seal() -> str:
    """The office seal, impressed in wax: an irregular disc with the device of
    the desk - a quill crossed with a key - bitten out of it in white."""
    rng = random.Random(1851)
    cx = cy = 62
    pts = []
    for i in range(30):
        a = i / 30 * 2 * math.pi
        r = 54 + rng.uniform(-3.4, 3.4)
        pts.append(f"{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}")
    p = ["<path d='M" + " L".join(pts) + " Z' fill='black'/>",
         f"<circle cx='{cx}' cy='{cy}' r='45' fill='none' stroke='white' "
         f"stroke-width='2'/>"]
    for i in range(24):
        a = i / 24 * 2 * math.pi
        p.append(f"<circle cx='{cx + 45 * math.cos(a):.1f}' "
                 f"cy='{cy + 45 * math.sin(a):.1f}' r='1.8' fill='black'/>")
    p.append("<path d='M40 84 L82 40' stroke='white' stroke-width='3.4' "
             "stroke-linecap='round'/>")
    for i in range(7):
        t = 0.18 + i * 0.1
        x, y = 40 + 42 * t, 84 - 44 * t
        p.append(f"<path d='M{x:.1f} {y:.1f} l{7 - i * 0.5:.1f} -3.5' "
                 f"stroke='white' stroke-width='2'/>")
    p.append("<path d='M36 44 L74 82' stroke='white' stroke-width='3.4' "
             "stroke-linecap='round'/>"
             "<circle cx='33' cy='41' r='7' fill='none' stroke='white' "
             "stroke-width='3'/>"
             "<path d='M68 76 l7 -7 M62 70 l6 -6' stroke='white' "
             "stroke-width='3'/>")
    return svg(124, 124, "".join(p))


def vc_tailpiece() -> str:
    """The tailpiece under the last line: the mark an engraver puts where a
    page stops. A diamond in the middle, a leaf spray sweeping out either side,
    and a hairline tapering to a dot at each end."""
    w, h = 300, 54
    cx, cy = w / 2, h / 2
    p = []
    for flip in (1, -1):
        ox = cx + 46 * flip
        p.append(f"<path d='{_spiral(ox, cy + 2, 17, 1.4, -1.9 if flip > 0 else 1.25, -flip)}' "
                 f"fill='none' stroke='black' stroke-width='2.6'/>")
        # Three leaves off the scroll, fanning up and outward.
        for length, width, angle in ((46, 8, -24), (34, 6.5, -52), (30, 6, 4)):
            a = angle if flip > 0 else 180 - angle
            p.append("<path d='" + _leaf(ox + 6 * flip, cy - 2, length, width, a)
                     + "' fill='black'/>")
        p.append(f"<path d='M{cx + 96 * flip:.0f} {cy} H{cx + 132 * flip:.0f}' "
                 f"stroke='black' stroke-width='2'/>")
        p.append(f"<circle cx='{cx + 140 * flip:.0f}' cy='{cy}' r='3.6' "
                 f"fill='black'/>")
    p.append(f"<path d='M{cx} {cy - 11} L{cx + 9} {cy} L{cx} {cy + 11} "
             f"L{cx - 9} {cy} Z' fill='black'/>")
    p.append(f"<path d='M{cx} {cy - 5} L{cx + 4} {cy} L{cx} {cy + 5} "
             f"L{cx - 4} {cy} Z' fill='white'/>")
    return svg(w, h, "".join(p))


# --------------------------------------------------------------------------
# OPS: the furniture of a message form - the tape the signal came off, the
# scale down the edge of the sheet, and the stamp that releases it.


# Five-level teleprinter tape (ITA2, the alphabet half). Bit 1 is the top
# channel; the feed hole runs between channels 3 and 4, which is what makes a
# real tape read as two bands rather than one field of dots.
_ITA2 = {
    "A": 0b11000, "B": 0b10011, "C": 0b01110, "D": 0b10010, "E": 0b10000,
    "F": 0b10110, "G": 0b01011, "H": 0b00101, "I": 0b01100, "J": 0b11010,
    "K": 0b11110, "L": 0b01001, "M": 0b00111, "N": 0b00110, "O": 0b00011,
    "P": 0b01101, "Q": 0b11101, "R": 0b01010, "S": 0b10100, "T": 0b00001,
    "U": 0b11100, "V": 0b01111, "W": 0b11001, "X": 0b10111, "Y": 0b10101,
    "Z": 0b10001, " ": 0b00100,
}


def ops_tape() -> str:
    """Punched tape, as the signal came off the machine.

    Eight channels of random bits at this size is not tape - it is noise.
    This is five-level tape carrying real ITA2: sixteen characters at 12px, so
    the tile is exactly one turn of the phrase and the feed row runs unbroken
    across the seam.
    """
    text = "MORNING ORDERS  "          # 16 chars x 14px = one tile, seamless
    w, h = 224, 30
    rows = (5.5, 11, 16.5, 22.5, 27)   # channels 1-3, the feed, then 4-5
    p = [f"<rect x='0' y='0' width='{w}' height='{h}' fill='black'/>"]
    for i, ch in enumerate(text):
        x = i * 14 + 7
        bits = _ITA2.get(ch, _ITA2[" "])
        for bit in range(5):
            if bits & (1 << (4 - bit)):
                p.append(f"<circle cx='{x}' cy='{rows[bit]}' r='3' "
                         f"fill='white'/>")
        p.append(f"<circle cx='{x}' cy='19.5' r='1.3' fill='white'/>")
    # The edges of the tape, so it reads as a strip rather than a black band.
    p.append(f"<path d='M0 1.4 H{w} M0 {h - 1.4} H{w}' stroke='white' "
             f"stroke-width='1.6'/>")
    return svg(w, h, "".join(p))


def ops_scale() -> str:
    """The grid scale down the edge of the form: a tick every 10, a figure
    every 50. Tiles vertically, so the figures repeat - which is what a grid
    reference does anyway."""
    w, h = 40, 240
    p = [f"<rect x='0' y='0' width='2.5' height='{h}' fill='black'/>"]
    for i in range(h // 10 + 1):
        y = i * 10
        long_ = i % 5 == 0
        p.append(f"<path d='M2 {y} h{9 if long_ else 5}' stroke='black' "
                 f"stroke-width='{2 if long_ else 1.6}'/>")
    for i, label in enumerate(("00", "05", "10", "15")):
        p.append(pix(14, i * 60 + 2, label, 2))
    return svg(w, h, "".join(p))


def ops_stamp() -> str:
    """The release stamp on the authorisation.

    Big and empty: one word at scale, a rule, and the authority in small
    letters under it. A rubber stamp is read at a glance
    or not at all, so there is nothing else on it. The theme rotates it and
    lays it over the corner of the form; it is drawn square.
    """
    w, h = 300, 134
    p = [f"<rect x='4' y='4' width='{w - 8}' height='{h - 8}' fill='none' "
         f"stroke='black' stroke-width='6'/>",
         f"<rect x='15' y='15' width='{w - 30}' height='{h - 30}' fill='none' "
         f"stroke='black' stroke-width='2'/>"]
    word = "RELEASED"
    p.append(pix((w - pix_w(word, 5)) // 2, 28, word, 5))
    p.append(f"<path d='M40 78 H{w - 40}' stroke='black' stroke-width='2'/>")
    # At scale 2 the authority line printed as a grey smear under the word.
    # Nothing on a stamp may be small: it is read at a glance or not at all.
    sub = "DUTY OFFICER"
    p.append(pix((w - pix_w(sub, 3)) // 2, 92, sub, 3))
    return svg(w, h, "".join(p))


ART = {
    "noir-blind": noir_blind, "noir-street": noir_street, "noir-skyline": noir_skyline,
    "ar-bars": ar_bars, "ar-line": ar_line, "ar-pie": ar_pie, "ar-logo": ar_logo, "ar-swoosh": ar_swoosh,
    "diner-logo": diner_logo, "diner-cups": diner_cups,
    "monkey-porthole": monkey_porthole, "monkey-limb": monkey_limb, "monkey-moon": monkey_moon,
    "monkey-tree": monkey_tree, "monkey-static": monkey_static, "monkey-banana": monkey_banana,
    "tt-glyphs": tt_glyphs, "tt-code": tt_code, "tt-timeline": tt_timeline,
    "tm-selftest": tm_selftest,
    "ds-flash": ds_flash, "ds-star": ds_star, "ds-poll": ds_poll,
    "stage-curtain": stage_curtain, "stage-ghostlight": stage_ghostlight,
    "cb-pavilion": cb_pavilion, "cb-floodlights": cb_floodlights, "cb-posts": cb_posts, "cb-hoop": cb_hoop,
    "cb-marquee": cb_marquee,
    "bt-cassette": bt_cassette, "bt-player": bt_player, "bt-disc": bt_disc,
    "nj-static": nj_static, "nj-redacted": nj_redacted, "nj-thumb": nj_thumb,
    "nj-stamp": nj_stamp, "nj-dial": nj_dial,
    "vc-headpiece": vc_headpiece, "vc-swell": vc_swell,
    "vc-seal": vc_seal, "vc-tailpiece": vc_tailpiece,
    "ops-tape": ops_tape, "ops-scale": ops_scale, "ops-stamp": ops_stamp,
    "mimic-anatomy": mimic_anatomy, "mimic-hello": mimic_hello,
    "mimic-hand": mimic_hand,
}

MARKED = re.compile(r'url\("data:image/svg\+xml,[^"]*"\)(\s*/\*\s*art:([\w-]+)\s*\*/)')


def main() -> int:
    check = "--check" in sys.argv
    missing, written = [], 0
    for css in sorted(THEMES.glob("*.css")):
        text = css.read_text(encoding="utf-8")

        def swap(m: re.Match) -> str:
            nonlocal written
            name = m.group(2)
            if name not in ART:
                missing.append(f"{css.name}: art:{name}")
                return m.group(0)
            written += 1
            return f'url("data:image/svg+xml,{encode(ART[name]())}"){m.group(1)}'

        new = MARKED.sub(swap, text)
        if new != text and not check:
            css.write_text(new, encoding="utf-8")
    for m in missing:
        print("no drawing for", m)
    print(f"{written} marked image(s) {'found' if check else 'drawn'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
