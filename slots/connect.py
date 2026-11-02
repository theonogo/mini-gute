"""Slot 112 - Connect two headlines.

A non-obvious link between two of today's stories.

**It works from the headlines that actually printed**, taken from `ctx.shared`
where slot 10 leaves them, rather than fetching its own. A connection drawn
between two stories the reader cannot see on the same piece of paper is not a
connection - it is an assertion. This is the only slot that depends on another
slot's *output* rather than on a shared fetch, and it drops cleanly when the
news section is missing, which is exactly what should happen: with no headlines
above it there is nothing to connect.

**It does not search.** Everything it needs is already on the page. This is the
slot in the SEARCH AND JUDGEMENT family that turns out to need only the
judgement half, and giving it search would invite it to reach for a third story
the reader never saw.

The connection is allowed to be a stretch and is not allowed to be a claim.
A shared cause is a strong thing to assert about two news stories on no evidence,
so the brief asks for a noticing rather than a thesis.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


@register
class ConnectTwoHeadlines(Slot):
    spec = SlotSpec(id=112, name="Connect two headlines", tier="uncommon",
                    paper_mm=28, needs_narrator=True)

    def _from_shared(self, ctx: Context) -> SlotResult | None:
        from .news import SHARED_KEY

        headlines = ctx.shared.get(SHARED_KEY) or []
        if len(headlines) < 2:
            return None          # nothing printed to connect

        pair = ctx.rng(self.spec.id).sample(headlines, 2)
        return SlotResult(
            head="Two Of These",
            body=f"{pair[0]['title']} / {pair[1]['title']}",
            brief={
                "headline_one": pair[0]["title"],
                "headline_two": pair[1]["title"],
                "instruction": "Both of these printed higher up this receipt. "
                               "Draw one non-obvious link between them, in two "
                               "or three sentences, in voice. Name both stories "
                               "so the reader knows which two you mean. It may "
                               "be a stretch and it may be playful, but it must "
                               "be a NOTICING rather than a claim - do not "
                               "assert a shared cause, a conspiracy or a "
                               "consequence, and add no fact about either story "
                               "beyond its headline.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._from_shared(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        """Offline the news slot still runs from cached feeds, so this may work.

        When it does not, returning None is right: the fixture's job is to be
        honest about what the slot does with no input, and with no headlines it
        does nothing.
        """
        return self._from_shared(ctx)
