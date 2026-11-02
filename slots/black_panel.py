"""Slot 55 - Reversed-out black panel.

A solid black block with one line knocked out in white. Rare, because it is
heavy on heat: a 30mm panel of solid ink is the most demanding thing this
printer is ever asked to do, and doing it every day would both slow the print
and make it ordinary.

**The panel is styled in the template, not here.** The body is the sentence
only, so the narrator can write it - a slot that puts its own markup in `body`
has to be verbatim, and this one wants the persona's words. The base stylesheet
carries a `.slot-55` rule instead. That is the pattern for any slot whose
appearance is its content but whose text is narrated.

Two hardware facts drive the styling, both from SYSTEM.md 1.1:

  * **Reversed-out text is always bold.** At the page threshold, surrounding ink
    bleeds into white glyphs and eats thin strokes. This is the invariant's
    worst case - a whole panel of it - so the weight is not optional.
  * **The type goes up, not down.** White-on-black loses more stroke than
    black-on-white gains, so the panel runs larger than body text rather than
    the same size.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Fallbacks when the narrator is unavailable. Short, declarative, and able to
# carry the weight of being the only sentence in a black rectangle - a hedged
# sentence reversed out at 24px looks absurd.
LINES: list[str] = [
    "Nothing is required of you before nine o'clock.",
    "The difficult thing and the important thing are the same thing today.",
    "You already know which one it is.",
    "Do the part you have been circling.",
    "Everything on this page is smaller than it feels.",
    "Begin badly. Begin anyway.",
    "The day does not need a plan. It needs a first move.",
    "Whatever you are putting off is thirty minutes long.",
    "No one is checking. That is the problem and the permission.",
    "Finish one thing before noon and the rest is negotiable.",
]


@register
class BlackPanel(Slot):
    spec = SlotSpec(id=55, name="Reversed-out black panel", tier="rare",
                    paper_mm=34, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        return SlotResult(
            head="",   # the panel is the whole section; a header above it
                       # halves the impact and the template hides an empty one
            body=ctx.rng(self.spec.id).choice(LINES),
            brief={"format": "one line, reversed out white on a solid black "
                             "panel roughly 30mm tall",
                   "instruction": "Write ONE short declarative sentence, at most "
                                  "fifteen words, in voice. It is printed large "
                                  "and white on solid black and is the only text "
                                  "in the section. No question, no hedge, no "
                                  "second sentence. Give the header as an empty "
                                  "string."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
