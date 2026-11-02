"""Render the First Mate's treasure maps for review: each one whole, with the
cut grid over it, and its nine pieces in the order they are handed out.

    python tools/treasuremaps.py                 # the maps in personas.toml
    python tools/treasuremaps.py --seeds 1-12    # candidate islands, to choose from
    python tools/treasuremaps.py --out out/maps

Rendered through the page renderer at the page threshold, so what you see is
what prints: 1-bit, the page's own faces. The whole map is drawn 1:1 (600 dots
is 75mm), as are the pieces (200 dots, 25mm).
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import render.page as page  # noqa: E402
from render import Renderer  # noqa: E402
from render.fonts import face_css  # noqa: E402
from render.treasure_map import CELL, STYLE, TreasureMap, map_for, piece_svg  # noqa: E402

PLACEHOLDER_MARKS = [{"name": "Skull Rock", "kind": "skull"},
                     {"name": "the Bishop's Wreck", "kind": "wreck"},
                     {"name": "Hangman's Oak", "kind": "tree"}]


def maps_from_personas() -> list[dict]:
    data = tomllib.loads((ROOT / "personas" / "personas.toml").read_text(encoding="utf-8"))
    mate = next(p for p in data["persona"] if p["name"] == "first-mate")
    return mate["blocks"]["coupon"]["maps"]


def sheet(m: TreasureMap) -> str:
    grid = "".join(
        f"<path d='M{i * CELL} 0 V600 M0 {i * CELL} H600' stroke='#000' stroke-width='1' "
        f"stroke-dasharray='3 3'/>" for i in (1, 2))
    whole = f"<svg width='600' height='600' viewBox='0 0 600 600'>{STYLE}{m.body()}{grid}</svg>"
    pieces = "".join(
        f"<div class='p'><div class='n'>{n + 1}. {'ABC'[c]}{r + 1}</div>{piece_svg(m, c, r)}</div>"
        for n, (c, r) in enumerate(m.order()))
    return (f"<div class='map'><div class='t'>{m.number}: {m.name} (seed {m.seed})</div>"
            f"<div class='row'>{whole}<div class='grid'>{pieces}</div></div></div>")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=None, help="e.g. 1-12: candidate islands")
    ap.add_argument("--out", default="out/maps")
    args = ap.parse_args()

    if args.seeds:
        a, _, b = args.seeds.partition("-")
        specs = [{"seed": s, "name": f"Candidate {s}", "landmarks": PLACEHOLDER_MARKS}
                 for s in range(int(a), int(b or a) + 1)]
    else:
        specs = maps_from_personas()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    page.BUDGET_PX = 99_999
    faces = face_css("IM Fell English") + face_css("Pirata One")
    with Renderer(width=1300) as r:
        for i, spec in enumerate(specs, start=1):
            # The listed maps go through map_for, so what is reviewed is what
            # prints; candidates are drawn raw, faults and all.
            m = (TreasureMap(spec["seed"], spec["name"], spec["landmarks"], i) if args.seeds
                 else map_for(specs, i - 1))
            html = (f"<html><head><meta charset='utf-8'><style>{faces}"
                    ":root{--font:'IM Fell English';--font-display:'Pirata One';--bold:400}"
                    "body{margin:0;background:#fff;font-family:var(--font)}"
                    ".map{padding:10px}.t{font-size:18px;margin-bottom:6px}"
                    ".row{display:flex;gap:24px;align-items:flex-start}"
                    ".grid{display:grid;grid-template-columns:repeat(3,200px);gap:14px}"
                    ".n{font-size:13px}</style></head><body>"
                    f"{sheet(m)}</body></html>")
            img = r.render(html, strict_budget=False)
            path = out / f"map-{spec['seed']}.png"
            img.save(path)
            print(path)
            for fault in m.faults():
                print(f"   ! {fault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
