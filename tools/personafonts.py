"""A type specimen for the persona pool: every face, in the role it plays.

`tools/fonttest.py` tests families. This tests *personas* - which is how the
faces will actually be met on paper. Each card shows:

  DISPLAY  the persona's own headers, at heading size, and its figures
  BODY     a line of its voice at body size, the weather figures in its bold,
           the small and tiny tiers, and a reversed-out bar at its heaviest
  ACCENT   its tear line and coupon header, at accent size

and labels each with the weights the face really ships and, for the body, the
characters per line measured in Chromium at 576px. The size it suggests is the
rule render/fonts.py was set by: the body size that brings the face to the house
measure of 65 characters at the 18px scale (where Libre Baskerville at 18 and
VT323 at 22 both measure 65), plus the 1px every face gets on top.
Suggestions only - nothing here changes render/fonts.py, and nothing is ever
suggested below the default body size.

(SYSTEM.md 1.2's "~53 at 18px" is what a monospace gives - JetBrains Mono measures
53.3 here - not a proportional face.)

    python tools/personafonts.py                     # out/personafonts.png
    python tools/personafonts.py oracle bootleg-tape # just these
    python tools/personafonts.py --print
"""

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as pipeline  # noqa: E402
from printer import get_printer  # noqa: E402
from printer.base import WIDTH_DOTS  # noqa: E402
from render import Renderer  # noqa: E402
from render.fonts import (DEFAULT_SIZES, face_css, has_bold, manifest,  # noqa: E402
                          mono_face_css, mono_stack, sizes, stack)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "personafonts.png"

TARGET_CPL = 65     # at 18px, before the house-wide +1px
BUMP_PX = 1
MEASURE = ("It will rain after lunch, so take a coat; the wind picks up by four "
           "and the evening turns cold and clear. Nobody told the pigeons, who "
           "are carrying on regardless, which is fair enough.")
FIGURES = "LOW 12°  HIGH 20°  Rain 13–17  31km/h  06:16"
# Short enough to stay on one line side by side, even in the widest monospace.
SMALL = "Small: Permit No. 14-A."
TINY = "Tiny: no refunds on Wednesdays."

CSS = """
* { font-synthesis: none; }
html, body { margin: 0; padding: 0; background: #fff; color: #000; }
body { font-family: var(--mono); font-size: 14px; line-height: 1.3; }

.sheet-head { background: #000; color: #fff; font-weight: 700; font-size: 16px;
              padding: 6px 12px 7px; letter-spacing: 0.06em; }
.sheet-sub  { padding: 4px 12px 8px; border-bottom: 3px solid #000; }

.card { padding: 10px 12px 12px; }
.card + .card { border-top: 3px dashed #000; }

.top  { display: flex; align-items: baseline; justify-content: space-between;
        gap: 10px; border-bottom: 3px solid #000; padding-bottom: 3px; }
.name { font-family: var(--d); font-weight: var(--dw); font-size: 34px;
        line-height: 1.05; min-width: 0;
        overflow-wrap: anywhere; }
.meta { text-align: right; white-space: nowrap; line-height: 1.2; }
.meta b { letter-spacing: 0.06em; }

/* One labelled row per role. The label is always the house mono, so the thing
   being judged is never also the thing doing the labelling. */
.role { display: flex; align-items: baseline; gap: 8px; margin: 8px 0 3px;
        flex-wrap: wrap; }
.tag  { background: #000; color: #fff; font-weight: 700; padding: 1px 6px 2px;
        letter-spacing: 0.1em; }
.face { font-weight: 700; }
.warn { font-weight: 700; text-decoration: underline; }

/* Heading size, as the placeholder theme sets headings. */
.disp { font-family: var(--d); font-size: calc(var(--b) * 1.4); line-height: 1.12;
        font-weight: var(--dw); }
.disp.figs { font-size: var(--b); margin-top: 1px; font-weight: var(--dbold); }
.body { font-family: var(--f); font-size: var(--b); line-height: 1.35; }
.bold { font-weight: var(--bold); }
.tiers { display: flex; align-items: baseline; gap: 18px; margin-top: 3px; }
.sm   { font-size: var(--s); }
.tn   { font-size: var(--t); }
/* Full bleed, as a reversed-out bar is on the receipt itself. Heaviest honest
   weight, because the threshold eats white strokes (SYSTEM.md 1.1). */
.inv  { background: #000; color: #fff; font-family: var(--f); font-size: var(--b);
        font-weight: var(--bold); margin: 6px -12px 0; padding: 4px 12px 5px; }
/* The accent at a size it can be judged by, and the tear line at the size it
   actually prints. */
.acc  { font-family: var(--a); font-size: calc(var(--b) * 1.3); line-height: 1.15; }
.acc.tear { font-size: var(--b); text-align: center; margin-top: 3px; }
"""


def personas() -> list[dict]:
    return list(pipeline.load_personas(auditions=True).values())


def voice_line(p: dict) -> str:
    """The persona's first example line, or its first sentence if it has none."""
    voice = p["voice"]
    if "Examples of the register" in voice:
        for line in voice.split("Examples of the register", 1)[1].splitlines()[1:]:
            m = re.match(r'^(?:[A-Z]+: )?"(.+)"$', line.strip())
            if m:
                return up_to(m.group(1), 95)
    return up_to(" ".join(voice.split()), 95)


def up_to(text: str, limit: int) -> str:
    """Whole sentences, as many as fit in `limit` characters - at least one.

    Two lines is enough to judge a face by and three is paper, but a single
    short sentence ("NIGHTJAR to SLEEPER.") is too little to judge anything.
    """
    out = ""
    for sentence in re.split(r"(?<=[.?!])\s", text):
        if out and len(out) + 1 + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
    return out


def weights(family: str) -> str:
    ws = sorted({f.rsplit("-", 1)[-1].split(".")[0] for f in manifest().get(family, [])})
    return " ".join(ws) + ("" if has_bold(family) else " - no bold")


def measure(r: Renderer, families: list[str]) -> dict[str, float]:
    """Characters per line at 18px across the full 576px, per family."""
    spans = "".join(
        f'<span data-fam="{html.escape(f)}" style="font-family:{html.escape(stack(f))};'
        f'font-size:18px;white-space:nowrap;position:absolute">{html.escape(MEASURE)}</span>'
        for f in families)
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>"
            + "".join(face_css(f) for f in families)
            + "</style></head><body>" + spans + "</body></html>")
    widths = r.evaluate(page, """() => Object.fromEntries(
        [...document.querySelectorAll('[data-fam]')].map(
            el => [el.dataset.fam, el.getBoundingClientRect().width]))""")
    return {f: WIDTH_DOTS / (w / len(MEASURE)) for f, w in widths.items()}


def suggested(cpl_at_18: float) -> int:
    """The body px render/fonts.py should hold for a face. Never below default."""
    return max(DEFAULT_SIZES[0], round(18 * cpl_at_18 / TARGET_CPL) + BUMP_PX)


def card(p: dict, cpl18: dict[str, float]) -> str:
    esc = html.escape
    fonts = {r: f for r, f in p.get("fonts", {}).items()
             if r in ("display", "accent") and f in manifest()}
    dw = p.get("fonts", {}).get("display_weight", 400) if "display" in fonts else 400
    body_face = p["font"]
    b, s, t = sizes(body_face)
    body = stack(body_face)
    disp = stack(fonts["display"]) if "display" in fonts else body
    acc = stack(fonts["accent"]) if "accent" in fonts else None
    vocab = p["vocabulary"]

    cpl = cpl18[body_face] * 18 / b
    ideal = suggested(cpl18[body_face])
    fit = (f"{cpl:.0f} cpl" if ideal <= b
           else f'{cpl:.0f} cpl <span class="warn">try {ideal}px</span>')

    style = (f"--f:{body};--d:{disp};--a:{acc or body};--b:{b}px;--s:{s}px;--t:{t}px;"
             f"--bold:{700 if has_bold(body_face) else 400};"
             f"--dbold:{dw if dw != 400 else 700 if has_bold(fonts.get('display', body_face)) else 400};"
             f"--dw:{dw};")
    out = [f'<div class="card" style="{esc(style)}">',
           f'<div class="top"><div class="name">{esc(p["display"])}</div>'
           f'<div class="meta"><b>{p["rarity"].upper()}</b><br>'
           f'{"audition" if p.get("audition") else "LIVE"}</div></div>']

    if "display" in fonts:
        out += [f'<div class="role"><span class="tag">DISPLAY</span>'
                f'<span class="face">{esc(fonts["display"])}</span>'
                f'<span>{weights(fonts["display"])}</span>'
                + (f'<span>- set at {dw}</span>' if dw != 400 else '')
                + ('<span>- figures at 700</span>'
                   if dw == 400 and has_bold(fonts["display"]) else '')
                + '</div>',
                f'<div class="disp">{esc(vocab["weather"])}</div>',
                '<div class="disp figs">0123456789 &amp; ?! ABCDEFG abcdefg</div>']
    else:
        out.append('<div class="role"><span class="tag">DISPLAY</span>'
                   '<span>none - headings use the body face</span></div>')

    out += [f'<div class="role"><span class="tag">BODY</span>'
            f'<span class="face">{esc(body_face)}</span>'
            f'<span>{weights(body_face)}</span>'
            f'<span>{b}px - {fit}</span></div>',
            f'<div class="body">{esc(voice_line(p))}</div>',
            f'<div class="body bold">{esc(FIGURES)}</div>',
            f'<div class="body tiers"><span class="sm">{esc(SMALL)}</span>'
            f'<span class="tn">{esc(TINY)}</span></div>',
            f'<div class="inv">Reversed: {esc(vocab["coupon"])} 12°</div>']

    if acc:
        out += [f'<div class="role"><span class="tag">ACCENT</span>'
                f'<span class="face">{esc(fonts["accent"])}</span>'
                f'<span>{weights(fonts["accent"])}</span></div>',
                f'<div class="acc">{esc(vocab["micro_dare"])}</div>',
                f'<div class="acc tear">{esc(p["tear_glyph"])}</div>']
    else:
        out.append('<div class="role"><span class="tag">ACCENT</span>'
                   '<span>none</span></div>')
    out.append("</div>")
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="persona names; default all")
    ap.add_argument("--print", dest="to_paper", action="store_true")
    args = ap.parse_args()

    pool = personas()
    if args.names:
        unknown = set(args.names) - {p["name"] for p in pool}
        if unknown:
            sys.exit(f"unknown persona(s): {', '.join(sorted(unknown))}")
        pool = [p for p in pool if p["name"] in args.names]

    families = list(dict.fromkeys(
        f for p in pool for f in [p["font"], *p.get("fonts", {}).values()]
        if isinstance(f, str) and f in manifest()))
    with Renderer() as r:
        cpl18 = measure(r, [p["font"] for p in pool])
        page = ("<!doctype html><html><head><meta charset='utf-8'><style>"
                + "".join(face_css(f) for f in families) + mono_face_css()
                + f":root{{--mono:{mono_stack()};}}" + CSS
                + "</style></head><body>"
                + '<div class="sheet-head">PERSONA TYPE SPECIMEN</div>'
                + f'<div class="sheet-sub">{len(pool)} personas, {len(families)} '
                  f'families. Printed at the real threshold. Body measure '
                  f'target: {TARGET_CPL} characters per line at 18px, plus '
                  f'{BUMP_PX}px.</div>'
                + "".join(card(p, cpl18) for p in pool)
                + "</body></html>")
        img = r.render(page, strict_budget=False)

    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT)
    print(f"{len(pool)} personas, {img.height / 8:.0f}mm -> {OUT}")
    for p in pool:
        b = sizes(p["font"])[0]
        print(f"  {p['name']:<20} {p['font']:<18} {b}px  "
              f"{cpl18[p['font']] * 18 / b:5.1f} cpl  "
              f"try {suggested(cpl18[p['font']])}px")
    if args.to_paper:
        get_printer("usb").print_image(img)
        print("printed")


if __name__ == "__main__":
    main()
