"""Slot 106 - Conspiracy theory.

Crazy dots connected into a conclusion. Two variants, per `SLOTS.md`:

  * a **world** theory - something invented, or a real one retold, and
  * a **machine** theory about this receipt system itself, fed by real patterns
    from the archive.

The second is the better one and is preferred whenever there is an archive to
draw on, because the dots are then genuinely true. That the ops-officer persona
has appeared four times running is a fact; that it is *arranging* this is not.

**The pattern may be true. The conclusion is not, and the layout says so.**
This is `CLAUDE.md` invariant 8 and it is enforced the same way slot 103 does
it - through `.slot-106` in the base stylesheet, not through text the narrator
can rewrite away. A conspiracy slot that failed to mark itself would be the
single worst thing this machine could print, because every other number on the
page is real and the reader has no way to tell where the reliable part stops.

The archive dots come from `data.archive`, shared with receipt archaeology, and
each is computed rather than recalled, so the slot cannot assert a pattern that
is not there.
"""

from __future__ import annotations

from typing import Any

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Invented or genuinely-held theories, retold. Kept broadly harmless: nothing
# about real named people, real groups, or anything a reader could mistake for
# a claim about the world worth acting on.
WORLD: list[tuple[str, str]] = [
    ("Escalators", "are all slightly slower on Mondays, and nobody who "
                   "maintains them will say who decides the schedule"),
    ("The sound a crisp packet makes", "was designed to be exactly loud enough "
                                       "to stop you eating them in a library"),
    ("Every town", "has one roundabout that exists solely to test whether you "
                   "are paying attention, and it is never the biggest one"),
    ("Odd socks", "are not lost. They are recalled, and the recall notice is "
                  "the sock you have left"),
    ("Lifts", "arrive faster if you have already decided to take the stairs, "
              "and this is measured"),
    ("The last three minutes of any meeting", "are where the actual decision "
                                              "is made, which is why they are "
                                              "never in the minutes"),
    ("Pigeons in city squares", "are arranged in the same formation each "
                                "morning by an authority that has never been "
                                "named"),
    ("Every pen that writes well", "is on loan, and the terms are unfavourable"),
    ("Traffic lights", "hold a grudge, and the grudge is per vehicle, not per "
                       "driver"),
    ("Supermarket background music", "slows by four beats a minute after six "
                                     "o'clock so that you buy the wine"),
]


def archive_dots(store: Any, day: Any) -> list[str]:
    """True patterns in the receipts, from the shared archive reader.

    SLOTS.md says these dots are the same patterns receipt archaeology (113)
    reports, so both read `data.archive.patterns` rather than each keeping its
    own copy of the arithmetic - two copies would eventually disagree about
    what is true.
    """
    from data.archive import patterns
    return patterns(store, day)


@register
class Conspiracy(Slot):
    spec = SlotSpec(id=106, name="Conspiracy theory", tier="uncommon",
                    paper_mm=28, needs_narrator=True)

    def _machine(self, dots: list[str], ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        picked = rng.sample(dots, min(3, len(dots)))
        return SlotResult(
            head="Connect The Dots",
            body="; ".join(picked).capitalize() + ". Draw your own conclusions.",
            fine="Every fact above is true. The conclusion is not.",
            brief={"variant": "machine",
                   "true_facts": picked,
                   "fabricated": True,
                   "instruction": "Connect these facts about this receipt "
                                  "printer into one paranoid conclusion, in "
                                  "voice, in two or three sentences. THE FACTS "
                                  "ARE TRUE and come from the archive - use them "
                                  "exactly as given and invent no further ones. "
                                  "The conclusion you draw from them is meant to "
                                  "be nonsense and is marked as such on the "
                                  "page, so commit to it."},
        )

    def _world(self, ctx: Context) -> SlotResult:
        subject, claim = ctx.rng(self.spec.id).choice(WORLD)
        return SlotResult(
            head="Connect The Dots",
            body=f"{subject} {claim}.",
            fine="Nonsense, presented without evidence.",
            brief={"variant": "world",
                   "subject": subject, "claim": claim,
                   "fabricated": True,
                   "instruction": "Argue this theory in voice, in two or three "
                                  "sentences, with total conviction and no "
                                  "evidence. It is openly nonsense and the page "
                                  "marks it as such, so do not hedge it or wink "
                                  "at the reader. Do not involve real people, "
                                  "companies or events."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        # The machine variant wins whenever the archive can supply real dots -
        # a conspiracy about the receipt is funnier when its evidence checks out.
        dots = archive_dots(ctx.store, ctx.date) if ctx.store else []
        if len(dots) >= 2:
            return self._machine(dots, ctx)
        return self._world(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._world(ctx)
