"""Slot 138 - Wikipedia most-read yesterday.

What people actually read, which `SLOTS.md` promises is "reliably stranger than
the news".

**It is not, if you take the top of the chart.** A live sample of yesterday's
most-read returned five tennis players and a killing in the first eight. The
pageview list is dominated by whoever was on television and whoever died, which
is the same material the news section already carries.

So two filters, in `sources/wikipedia.py`:

  * grim articles are dropped outright, the same call the news slot makes, and
  * the remainder is ranked for how much of a rabbit hole it is, using
    Wikipedia's own one-line description - "American tennis player (born 2002)"
    against "Equations of motion for viscous fluids" separates cleanly.

**The real rank is printed.** Picking the sixth most-read and implying it was
the first would be exactly the embellishment SYSTEM.md 9 forbids, and the
honest version is more interesting anyway: sixth place with 150,000 readers
says something the first place does not.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

SHARED_KEY = "wikipedia:mostread"

FIXTURE = {
    "title": "Toynbee tiles",
    "rank": 7,
    "views": 118_402,
    "description": "Messages of unknown origin embedded in street asphalt",
    "extract": "The Toynbee tiles, also called Toynbee plaques, are messages of "
               "unknown origin found embedded in asphalt of streets in about two "
               "dozen major cities in the United States and three South American "
               "cities.",
    "url": "https://en.wikipedia.org/wiki/Toynbee_tiles",
    "stale": False,
}


@register
class MostRead(Slot):
    spec = SlotSpec(id=138, name="Wikipedia most-read yesterday",
                    tier="common", paper_mm=29, needs_network=True,
                    needs_narrator=True)

    def _build(self, ctx: Context, article: dict) -> SlotResult:
        from sources.wikipedia import first_sentence

        views = f"{article['views']:,}"
        return SlotResult(
            head="Most Read Yesterday",
            body=first_sentence(article["extract"]),
            fine=f"{article['title']} &middot; no.{article['rank']} yesterday, "
                 f"{views} readers"
                 + (" &middot; from cache" if article.get("stale") else ""),
            brief={"title": article["title"],
                   "description": article["description"],
                   "rank": article["rank"],
                   "views": article["views"],
                   "summary": article["extract"][:400],
                   "instruction": "Say what this is, in voice, in one or two "
                                  "sentences, using only the summary given. It "
                                  "is genuinely what people read yesterday, so "
                                  "the rank and reader count are true and may be "
                                  "remarked on. Invent no detail about the "
                                  "subject."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        from sources import wikipedia

        # Shared so slot 30 can reuse the same feed rather than fetching twice
        # on a day both are drawn.
        articles = ctx.shared.get(SHARED_KEY)
        if articles is None:
            articles = wikipedia.most_read(ctx.date, store=ctx.store,
                                           offline=ctx.offline)
            ctx.shared[SHARED_KEY] = articles
        return self._build(ctx, wikipedia.most_interesting(articles))

    def fixture(self, ctx: Context) -> SlotResult:
        return self._build(ctx, FIXTURE)
