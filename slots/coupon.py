"""Slots 11 (coupon) and 146 (absurd legalese). Both are persona-written.

**The coupon is the persona's own object.** Every persona declares its coupon
in `[persona.blocks]` - the Clerk's warrant, the Oracle's charm, the Diner's
punch card - so the slot draws no form or subject of its own, which would only
contradict it. The persona's block says what the coupon is, and the narrator
writes the whole of it, fine print included (`fine_print`).

What is left here is the offline copy, for a morning with no narrator.

The legalese is Terry Pratchett register: bureaucratic language applied
straight-faced to impossible subject matter, with a footnote that undermines the
clause above it. The footnote is the joke; a clause without one is just a clause.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Only ever printed when there is no narrator. The persona's own coupon heading
# still sits over it (`[persona.vocabulary] coupon`), so these stay plain enough
# to sit under any of them.
OFFLINE = [
    ("Redeemable for one (1) good coffee, bought without looking at the price.",
     "Not transferable. Expires at midnight."),
    ("Good for one second attempt at something already attempted badly.",
     "The first attempt is not refunded."),
    ("Entitles the bearer to a fifteen-minute detour on the way to somewhere else.",
     "Valid this date only. No retracing."),
    ("Good for one favour, claimable from any person willing to grant it.",
     "The management does not recognise appeals."),
    ("Admits one bearer to today. Row H, Seat 14.",
     "No re-entry. Retain this portion."),
    ("Full amnesty for one thing left undone last week.",
     "Excludes anything the bearer did knowingly."),
]


@register
class Coupon(Slot):
    spec = SlotSpec(id=11, name="Coupon", tier="spine", paper_mm=20,
                    needs_narrator=True)

    def _build(self, ctx: Context) -> SlotResult:
        body, terms = ctx.rng(self.spec.id).choice(OFFLINE)
        return SlotResult(
            head="Coupon",
            body=body,
            fine=terms,
            brief={
                "instruction": "Today's coupon: the object at the very foot of "
                               "the receipt, below the tear line, that the "
                               "reader tears off and keeps. Its form is this "
                               "persona's own, given below - write it as that "
                               "object, never as a generic coupon. Make it good "
                               "for one specific, concrete thing. Absurd but "
                               "straight-faced. Do NOT make it permission to be "
                               "idle or to procrastinate. Put the fine print in "
                               "its own field, not here, and do not end with a "
                               "signature line.",
                # The narrator writes the terms too (narrator.build_schema).
                "fine_print": "The fine print set small beneath the coupon. If "
                              "this persona's form says what its footnote is, "
                              "write exactly that; otherwise one short line of "
                              "terms in voice. At most 120 characters. An empty "
                              "string if the form has no place for one.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._build(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._build(ctx)


LEGALESE = [
    ("THE MANAGEMENT ACCEPTS NO LIABILITY FOR PROPHECIES FULFILLED IN SPIRIT "
     "BUT NOT IN LETTER.* NO REFUNDS ON WEDNESDAYS.",
     "* OR IN ANY OTHER TENSE SUBSEQUENTLY DISCOVERED."),
    ("ALL WEATHER IS SUPPLIED IN GOOD FAITH AND WITHOUT WARRANTY. THE BEARER "
     "ACCEPTS THAT THE SKY IS NOT A PARTY TO THIS AGREEMENT.*",
     "* THE SKY HAS DECLINED TO COMMENT."),
    ("BY READING THIS RECEIPT THE BEARER IS DEEMED TO HAVE READ IT.* THIS "
     "CLAUSE IS SELF-EXECUTING AND CANNOT BE UNREAD.",
     "* CLAUSE APPLIES RETROACTIVELY TO THE MOMENT BEFORE READING."),
    ("ANY RESEMBLANCE BETWEEN THIS FORECAST AND THE ACTUAL DAY IS COINCIDENTAL "
     "AND SHOULD NOT BE RELIED UPON IN COURT.*",
     "* IT MAY HOWEVER BE MENTIONED IN PASSING."),
    ("THE HOURS 03:00 TO 05:00 ARE PROVIDED AS-IS AND ARE NOT SUPPORTED.* "
     "USE OF THEM IS AT THE BEARER'S OWN RISK.",
     "* SUPPORT RESUMES WHEN THE RICE COOKER CLICKS."),
    ("ITEMS MARKED COMMON ARE NOT THEREBY WORTHLESS.* THE MANAGEMENT REJECTS "
     "THE IMPLICATION AND RESENTS THE QUESTION.",
     "* THIS FOOTNOTE HAS BEEN ADDED AT THE REQUEST OF THE COMMON ITEMS."),
]


@register
class AbsurdLegalese(Slot):
    spec = SlotSpec(id=146, name="Absurd legalese", tier="occasional",
                    paper_mm=15, needs_narrator=True)

    def _build(self, ctx: Context) -> SlotResult | None:
        rng = ctx.rng(self.spec.id)
        # "Occasional" is a tier of its own: it is not drawn by the rarity
        # engine, it simply turns up on roughly a third of receipts.
        if rng.random() > 0.34:
            return None
        clause, footnote = rng.choice(LEGALESE)
        return SlotResult(
            head="Terms",
            body=clause,
            fine=footnote,
            brief={
                "instruction": "Write one short mock-legal clause in voice. "
                               "Terry Pratchett register: bureaucratic language "
                               "applied straight-faced to impossible subject "
                               "matter. The footnote that undermines it goes in "
                               "its own field - do not write it here.",
                # The narrator writes the footnote too (narrator.build_schema),
                # so it always belongs to the clause above it.
                "fine_print": "The footnote set small under the clause, which "
                              "undermines it - this is the joke. If this "
                              "persona's form says what its footnote is, write "
                              "exactly that. One short sentence, at most 120 "
                              "characters.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._build(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._build(ctx)
