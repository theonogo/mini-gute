"""Slot 85 - A line of sheet music.

Real notation, rendered in the page - not tab, not a picture of a stave. The
opening phrase of a public-domain melody everybody knows, printed without its
title: hum it, and the answer is upside-down at the foot of the receipt.

**Name-the-tune rather than "the persona chooses the song".** SLOTS.md has the
persona choosing. The narrator cannot hand back a choice (see slot 26), and a
melody it wrote out itself would be a wrong note away from a wrong fact - which
is also why the pack is only tunes whose opening is unambiguous. Leaving the
title off turns a curiosity into something to do with it: most people cannot
read a stave cold, and nearly everyone can hum one out once they try.

**abcjs, embedded.** `assets/js/abcjs-basic-min.js` (MIT) renders ABC notation to
SVG in the page as it loads, so the headless render needs no network. It is
inlined only on the days this slot is drawn. Stave lines are line art, so they
go through the ordinary page threshold like text.
"""

from __future__ import annotations

import json
import tomllib
from functools import lru_cache
from pathlib import Path

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

ROOT = Path(__file__).resolve().parent.parent
TUNES = ROOT / "assets" / "music" / "tunes.toml"
ABCJS = ROOT / "assets" / "js" / "abcjs-basic-min.js"
NAMESPACE = "sheetmusic"
AVOID = 12


@lru_cache(maxsize=1)
def tunes() -> list[dict]:
    return tomllib.loads(TUNES.read_text(encoding="utf-8"))["tune"]


def abc(tune: dict) -> str:
    return (f"X:1\nM:{tune['meter']}\nL:{tune['length']}\nK:{tune['key']}\n"
            f"{tune['abc']}\n")


def notation_html(tune: dict, element_id: str = "abc-85") -> str:
    # staffwidth is in abcjs units; `responsive: resize` then scales the SVG to
    # the section's own width, so it fits whatever padding a theme gives it.
    options = {"staffwidth": 420, "responsive": "resize",
               "paddingleft": 0, "paddingright": 0, "paddingtop": 0,
               "paddingbottom": 0,
               "wrap": {"minSpacing": 1.5, "maxSpacing": 2.6,
                        "preferredMeasuresPerLine": 4}}
    js = ABCJS.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return (f'<div id="{element_id}" class="sheet-music" style="margin-bottom:12px"></div>'
            f'<script>{js}</script>'
            f'<script>ABCJS.renderAbc({json.dumps(element_id)}, '
            f'{json.dumps(abc(tune))}, {json.dumps(options)});</script>')


@register
class SheetMusic(Slot):
    spec = SlotSpec(id=85, name="A line of sheet music", tier="rare",
                    paper_mm=70, needs_narrator=True)

    def _result(self, tune: dict) -> SlotResult:
        return SlotResult(
            head="Name That Tune",
            body=notation_html(tune),
            fine="Hum it. The answer is at the foot of the receipt.",
            answer=tune["title"],
            brief={"verbatim": True,
                   "instruction": "Name this section in voice. It is the opening "
                                  "of a famous melody printed as sheet music "
                                  "with the title hidden, for the reader to hum "
                                  "and name. Do NOT name, hint at or describe "
                                  "the tune."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        recent: list[str] = []
        if ctx.store is not None:
            try:
                recent = list(ctx.store.fetch(NAMESPACE, "recent", []) or [])
            except Exception:  # noqa: BLE001
                recent = []
        pool = [t for t in tunes() if t["title"] not in recent] or tunes()
        tune = ctx.rng(self.spec.id).choice(pool)
        if ctx.store is not None and ctx.shared.get("real_morning"):
            try:
                ctx.store.put(NAMESPACE, "recent", ([tune["title"]] + recent)[:AVOID])
            except Exception:  # noqa: BLE001
                pass
        return self._result(tune)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx.rng(self.spec.id).choice(tunes()))
