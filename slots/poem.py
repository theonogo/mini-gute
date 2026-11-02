"""Slot 147 - Poem of the day.

A complete short poem every morning. No serial, no commitment, nothing to keep
up with - which is the whole reason this slot exists and slot 19 was cut.

The corpus is `assets/poems.json`, not a list in this file, so poems can be
added without touching code. Two consequences worth knowing:

**Verbatim, absolutely.** The narrator gets a header and nothing else. A poem is
the one kind of text on this receipt where the exact words, the exact line
breaks and the exact punctuation are the content. Blank lines in the source are
stanza breaks and are preserved as such.

**Line breaks are the poem's, not the page's.** Lines print as written and are
allowed to wrap if they must; re-breaking them to fit 72mm would be rewriting
the poem. A wrapped line is marked with a hanging indent so a wrap is visually
distinct from a real line break.

**Paper cost is per poem, and the spec is the worst case.** SLOTS.md costs this
at 12mm, about five lines - true of the two-line Pound and wrong for the
twelve-line Housman. The declared spec is 58mm, which is the longest poem in the
corpus as measured by `tools/papercheck.py`, and each result reports its own
real height afterwards.

An average would have been the intuitive choice and is the wrong one. The
selection engine fits the draw *before* anything is fetched, so it only ever
sees the spec; an average means the long poems are drawn onto days they do not
fit and the page overflows. Being generous costs an occasional skip. Being
optimistic costs a failed morning.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from render.fonts import DEFAULT_SIZES

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

CORPUS = Path(__file__).resolve().parent.parent / "assets" / "poems.json"

# Body size at 1.35 line-height, from the house scale rather than a copy of it,
# so the estimate follows the scale when it moves.
LINE_PX = math.ceil(DEFAULT_SIZES[0] * 1.35)
STANZA_PX = 12
CHROME_PX = 44      # header and attribution
DOTS_PER_MM = 8


@lru_cache(maxsize=1)
def corpus() -> list[dict]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    poems = data.get("poems", [])
    if not poems:
        raise ValueError(f"{CORPUS} has no poems")
    return poems


_CSS = """
<style>
/* Hanging indent so a line too long for 72mm is visibly a wrap and not a line
   the poet wrote. Leading spaces in the source are significant - Hopkins
   indents - so they are preserved rather than collapsed. */
.poem      { margin: 2px 0; }
.poem-line { padding-left: 1.4em; text-indent: -1.4em; white-space: pre-wrap; }
.poem-gap  { height: 12px; }
</style>
"""


def poem_html(poem: dict) -> str:
    rows = []
    for line in poem["lines"]:
        if line.strip():
            rows.append(f'<div class="poem-line">{_escape(line)}</div>')
        else:
            rows.append('<div class="poem-gap"></div>')
    return f'{_CSS}<div class="poem">{"".join(rows)}</div>'


def _escape(text: str) -> str:
    """The template renders unescaped, so a poem containing < or & must not
    become markup. Spaces are non-breaking only at the start of a line, where
    they are the poet's indentation."""
    out = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    stripped = out.lstrip(" ")
    indent = len(out) - len(stripped)
    return "&nbsp;" * indent + stripped


def height_mm(poem: dict) -> int:
    lines = sum(1 for line in poem["lines"] if line.strip())
    gaps = sum(1 for line in poem["lines"] if not line.strip())
    return round((lines * LINE_PX + gaps * STANZA_PX + CHROME_PX) / DOTS_PER_MM)


@register
class PoemOfTheDay(Slot):
    spec = SlotSpec(id=147, name="Poem of the day", tier="common",
                    paper_mm=58, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        poem = ctx.rng(self.spec.id).choice(corpus())
        return SlotResult(
            head="Poem of the Day",
            body=poem_html(poem),
            fine=f"{poem['title']} &middot; {poem['author']}, {poem['year']}",
            paper_mm=height_mm(poem),
            brief={"verbatim": True,
                   "title": poem["title"],
                   "author": poem["author"],
                   "year": poem["year"],
                   "instruction": "Name this section in voice. The poem prints "
                                  "exactly as written - every word, line break "
                                  "and mark of punctuation. Do not summarise or "
                                  "interpret it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
