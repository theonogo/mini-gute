"""One strip of paper with every persona on it: a few lines each, in its faces.

For hearing the voices side by side without printing sixteen full receipts. Each
persona introduces itself to the reader in a sentence or three - no weather, no news,
no figures, so there is nothing for a voice to get wrong - and the card is set
in its own body, display and accent faces, with its renamed weather header and
its tear line. Auditions and live personas alike.

The introductions are one small narrator call each and are cached in
`out/auditions.json`, so a reprint costs nothing. `--fresh` writes new ones.

    python tools/auditionsheet.py                # render to out/auditions.png
    python tools/auditionsheet.py --print        # and print it
    python tools/auditionsheet.py --fresh --print
"""

import argparse
import html
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date as Date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import main as pipeline  # noqa: E402
import narrator  # noqa: E402
from printer import get_printer  # noqa: E402
from render import Renderer  # noqa: E402
from render.fonts import (face_css, manifest, mono_face_css,  # noqa: E402
                          mono_stack, sizes, stack)

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "auditions.json"
OUT = ROOT / "out" / "auditions.png"

INSTRUCTION = (
    f"This is your audition. Introduce yourself to {config.reader_name()} as if "
    f"on your very first receipt: who you are, and what to expect from you on "
    f"the mornings you print. Entirely in character. Mention no weather, no "
    f"news, no dates and no figures of any kind.")

CSS = """
* { font-synthesis: none; }
html, body { margin: 0; padding: 0; background: #fff; color: #000; }
body { font-family: var(--font-mono); line-height: 1.35; }
.card { padding: 14px 12px 16px; border-bottom: 3px dashed #000; }
.name { font-family: var(--d); font-size: calc(var(--b) * 1.9); line-height: 1.1; }
.meta { font-family: var(--font-mono); font-size: 14px; margin: 4px 0 8px;
        border-top: 2px solid #000; padding-top: 3px; }
.head { font-family: var(--d); font-size: calc(var(--b) * 1.25); line-height: 1.15;
        margin-bottom: 4px; }
.text { font-family: var(--f); font-size: var(--b); }
.tear { font-family: var(--a); font-size: var(--b); text-align: center;
        margin-top: 8px; }
"""


def personas() -> list[dict]:
    return list(pipeline.load_personas(auditions=True).values())


def introductions(pool: list[dict], fresh: bool) -> dict[str, str]:
    cached = {} if fresh or not CACHE.exists() else json.loads(CACHE.read_text("utf-8"))
    todo = [p for p in pool if p["name"] not in cached]
    if todo:
        print(f"narrating {len(todo)} introductions...")
        with ThreadPoolExecutor(max_workers=8) as ex:
            texts = ex.map(lambda p: narrator.freeform(Date.today(), p, INSTRUCTION,
                                                       max_words=70), todo)
            for p, text in zip(todo, texts):
                if text:
                    cached[p["name"]] = text
                else:
                    print(f"  {p['name']}: narrator failed, left blank")
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cached, indent=2, ensure_ascii=False), "utf-8")
    return cached


def card(p: dict, text: str) -> str:
    fonts = {r: f for r, f in p.get("fonts", {}).items()
             if r in ("display", "accent") and f in manifest()}
    body = stack(p["font"])
    b = sizes(p["font"])[0]
    faces = " / ".join([p["font"], *fonts.values()])
    status = "AUDITION" if p.get("audition") else "LIVE"
    style = (f"--f:{body};--d:{stack(fonts['display']) if 'display' in fonts else body};"
             f"--a:{stack(fonts['accent']) if 'accent' in fonts else body};--b:{b}px;")
    return (f'<div class="card" style="{html.escape(style)}">'
            f'<div class="name">{html.escape(p["display"])}</div>'
            f'<div class="meta">{p["rarity"].upper()} - {status}<br>{html.escape(faces)}</div>'
            f'<div class="head">{html.escape(p["vocabulary"]["weather"])}</div>'
            f'<div class="text" style="font-weight:400">{html.escape(text or "[no narration]")}</div>'
            f'<div class="tear">{html.escape(p["tear_glyph"])}</div></div>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="to_paper", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="re-narrate everything")
    args = ap.parse_args()

    pool = personas()
    texts = introductions(pool, args.fresh)
    families = dict.fromkeys(f for p in pool
                             for f in [p["font"], *p.get("fonts", {}).values()]
                             if isinstance(f, str) and f in manifest())
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>"
            + "".join(face_css(f) for f in families) + mono_face_css()
            + f":root{{--font-mono:{mono_stack()};}}" + CSS
            + "</style></head><body>"
            + "".join(card(p, texts.get(p["name"], "")) for p in pool)
            + "</body></html>")

    with Renderer() as r:
        img = r.render(page, strict_budget=False)
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT)
    print(f"{len(pool)} personas, {img.width}x{img.height}px "
          f"({img.height / 8:.0f}mm) -> {OUT}")
    if args.to_paper:
        get_printer("usb").print_image(img)
        print("printed")


if __name__ == "__main__":
    main()
