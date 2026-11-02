"""Slot 51 - Micro-dare.

One small thing to do today that you would not otherwise do. Take the long way
home. Talk to a stranger.

**The name "micro-dare" must never reach paper.** SLOTS.md is emphatic about
this and it is the whole texture of the slot: an instruction reads differently
depending on what it calls itself. Every persona carries a `micro_dare` entry
in its vocabulary - `TODAY'S MISSION` for the duty officer, `The Task Set
Before You` for the clerk - so the rename is configured rather than improvised,
and the fallback header below is one of those rather than the internal name.

Unlike most slots here the body is *not* verbatim. The dare is a prompt, not a
fact, and a duty officer issuing an order should not sound like a Victorian
clerk suggesting an amusement. Python picks which dare; the persona phrases it.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Kept deliberately small and physical. Every one has to be doable today, in the
# ordinary course of a day, without money, planning or anyone else's agreement -
# a dare you have to schedule is a chore.
DARES: list[str] = [
    "Take a route home you have never taken, even if it is longer.",
    "Talk to a stranger for long enough that it stops being small talk.",
    "Buy the thing you always look at and put back.",
    "Eat lunch somewhere with no screen in front of you.",
    "Ask someone what they are working on, and keep asking until you understand it.",
    "Photograph the least photogenic thing you see today.",
    "Say the true answer to 'how are you' exactly once.",
    "Finish something you have been almost finishing for a month.",
    "Give away one object you own before the day is out.",
    "Go one stop past your stop and walk back.",
    "Write to someone you have been meaning to write to for over a year.",
    "Learn the name of one person you see regularly and have never asked.",
    "Do the small annoying task you have been stepping around all week.",
    "Sit somewhere public for ten minutes with nothing to do.",
    "Cook something with no recipe and eat it regardless.",
    "Pay a compliment that costs you something to say.",
    "Take the stairs every single time today, including the ones going down.",
    "Ask for the thing you assumed the answer would be no to.",
    "Leave the house without checking what the weather is doing.",
    "Put one thing back where it belongs and leave the rest.",
]


@register
class MicroDare(Slot):
    spec = SlotSpec(id=51, name="Micro-dare", tier="uncommon", paper_mm=20,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        dare = ctx.rng(self.spec.id).choice(DARES)
        return SlotResult(
            # Never "Micro-dare". If the narrator fails and this fallback goes
            # to paper unrenamed, it should still read as something a persona
            # might have written.
            head="Today's Mission",
            body=dare,
            brief={"dare": dare,
                   "instruction": "Issue this as an instruction for today, in "
                                  "voice, in one sentence. Keep what is being "
                                  "asked for exactly the same. Rename the "
                                  "section header - it must never print as "
                                  "'micro-dare' or anything like it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
