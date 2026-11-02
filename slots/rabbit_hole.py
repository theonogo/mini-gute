"""Slot 30 - Wikipedia rabbit hole.

One sentence about something genuinely strange, plus a QR to the rest, framed
as an assignment rather than a fact.

**The pool is a harvest, not the random-article endpoint.** `SLOTS.md` is
explicit and it is right: `Special:Random` returns a geographic stub almost
every time, and "a village in Lower Saxony, population 340" is not a rabbit
hole. `assets/unusual.json` holds 3,700 articles harvested from
`Wikipedia:Unusual_articles`, which editors have curated for twenty years -
exactly the filter we cannot write ourselves. Re-harvest with
`tools/harvestunusual.py`; it is not part of the morning run, because a slot
that scrapes wikitext at 07:00 is a slot that breaks the day the table markup
changes.

**The QR is the point of the slot.** The sentence is bait; the assignment is to
follow it. It encodes the article URL directly rather than a `mailto:`, unlike
the input-channel slots.

If Wikipedia is unreachable the harvested one-line description stands in. Those
are written by editors and are frequently better than the article's own opening
sentence, so the degraded version is not obviously degraded.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

POOL = Path(__file__).resolve().parent.parent / "assets" / "unusual.json"
QR_MODULE_PX = 3        # ~25mm square for a typical article URL


@lru_cache(maxsize=1)
def pool() -> list[dict]:
    data = json.loads(POOL.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    if not articles:
        raise FileNotFoundError(
            f"{POOL} is empty - run `python tools/harvestunusual.py`")
    return articles


def article_url(title: str) -> str:
    return f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


@register
class RabbitHole(Slot):
    spec = SlotSpec(id=30, name="Wikipedia rabbit hole", tier="common",
                    paper_mm=53, needs_network=True, needs_narrator=True)

    def _build(self, title: str, sentence: str, url: str,
               stale: bool = False) -> SlotResult:
        from render.qr import qr_image

        return SlotResult(
            head="Rabbit Hole",
            body=sentence,
            image=qr_image(url, module_px=QR_MODULE_PX),
            fine=title + (" &middot; from cache" if stale else ""),
            brief={"title": title,
                   "summary": sentence,
                   "instruction": "Set this as an assignment, in voice, in one "
                                  "or two sentences - something to go and look "
                                  "at, not a fact being reported. Do not add any "
                                  "detail beyond the summary given; the article "
                                  "is real and the reader can check."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        from sources import wikipedia

        entry = ctx.rng(self.spec.id).choice(pool())
        title = entry["title"]
        try:
            got = wikipedia.summary(title, store=ctx.store,
                                    offline=ctx.offline, when=ctx.date)
            sentence = wikipedia.first_sentence(got["extract"])
            if sentence:
                return self._build(got["title"], sentence, got["url"],
                                   got.get("stale", False))
        except Exception:  # noqa: BLE001 - the harvested blurb is a real fallback
            pass
        return self._build(title, entry["blurb"], article_url(title))

    def fixture(self, ctx: Context) -> SlotResult:
        entry = ctx.rng(self.spec.id).choice(pool())
        return self._build(entry["title"], entry["blurb"],
                           article_url(entry["title"]))
