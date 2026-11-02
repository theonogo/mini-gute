"""Slots 47, 48, 50 and 87 - the ones you need a pen for.

Four slots in one module because they share a constraint the receipt has to
enforce collectively rather than individually: **each one asks for a pen, and
too many on one morning turns the receipt into a worksheet.**

  * **47 dice roll** - a number to decide with. No pen, but it belongs here.
  * **50 mood scale** - one to five, circled.
  * **48 journaling prompt** - a question and four ruled lines.
  * **87 blank comic panels** - four empty panels and a drawing prompt.

`selection.ANALOG` caps the pen slots (48, 50, 87 and 49) at two a day. They
are spread across the tiers, so nothing in the tier weights or the recency curve
correlates them, and three landing together turns the receipt into a worksheet.

Both the line height and the panel count were set on printed evidence: 30px
lines and three-across panels were both too small to use.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

_CSS = """
<style>
/* 30px lines were too tight to write on - verified on paper. 44px is about
   5.5mm, which clears a normal hand without turning the slot into a page. */
.ruled     { margin-top: 10px; }
.ruled-line{ border-bottom: 2px solid #000; height: 44px; }
.scale     { display: flex; justify-content: space-between; align-items: center;
             gap: 6px; margin: 6px 0 2px; }
.scale-pip { flex: 1 1 0; border: 3px solid #000; border-radius: 50%;
             aspect-ratio: 1 / 1; max-width: 46px; display: flex;
             align-items: center; justify-content: center;
             font-weight: var(--bold);
             font-size: var(--size-small); }
.scale-ends{ display: flex; justify-content: space-between;
             font-size: var(--size-tiny); }
/* Four panels in a 2x2, not three in a row. Three across 72mm gave panels
   about 24mm wide, which is too small to draw in - and a 2x2 is the shape a
   comic strip actually wants anyway. */
.panels    { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;
             margin: 8px 0; }
.panel     { border: 3px solid #000; aspect-ratio: 4 / 3; }
.die       { display: flex; align-items: center; gap: 14px; margin: 4px 0; }
.die-face  { border: 3px solid #000; width: 54px; height: 54px;
             display: flex; align-items: center; justify-content: center;
             font-size: calc(var(--size-body) + 12px);
             font-weight: var(--bold); }
</style>
"""


# --------------------------------------------------------------------------
@register
class DiceRoll(Slot):
    """A number to hand a decision to when the decision does not deserve one."""

    spec = SlotSpec(id=47, name="Today's dice roll", tier="uncommon",
                    paper_mm=20, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        # d6 alongside a d20, because one is for "which of these" and the other
        # is for "how committed am I". Both seeded, so the receipt cannot be
        # re-rolled by reprinting it - which is the entire point of a die.
        rng = ctx.rng(self.spec.id)
        d6, d20 = rng.randint(1, 6), rng.randint(1, 20)
        return SlotResult(
            head="Today's Roll",
            body=f'{_CSS}<div class="die"><div class="die-face">{d6}</div>'
                 f'<div class="die-face">{d20}</div>'
                 f'<div class="small">d6 and d20, rolled once, at dawn. '
                 f'Not re-rollable.</div></div>',
            brief={"verbatim": True,
                   "d6": d6, "d20": d20,
                   "instruction": "Name this section in voice. The numbers are "
                                  "printed as dice faces beside your header; do "
                                  "not state them or say what they mean."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


# --------------------------------------------------------------------------
@register
class MoodScale(Slot):
    """One to five, circled. The pattern only emerges across kept slips."""

    spec = SlotSpec(id=50, name="Mood scale", tier="uncommon", paper_mm=22,
                    needs_narrator=True)

    # Deliberately unlabelled in the middle. Naming all five turns it into a
    # survey; naming only the ends leaves the scale to mean what it means today.
    ENDS = ("not great", "genuinely good")

    def _result(self, ctx: Context) -> SlotResult:
        pips = "".join(f'<div class="scale-pip">{n}</div>' for n in range(1, 6))
        low, high = self.ENDS
        return SlotResult(
            head="Circle One",
            body=f'{_CSS}<div class="scale">{pips}</div>'
                 f'<div class="scale-ends"><span>{low}</span>'
                 f'<span>{high}</span></div>',
            brief={"verbatim": True,
                   "instruction": "Name this section in voice, in a few words. "
                                  "The scale is printed beneath and is answered "
                                  "with a pen - do not ask a question, do not "
                                  "guess the answer, and do not comment on it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


# --------------------------------------------------------------------------
# Prompts that can be answered in four lines by someone standing up. A prompt
# needing a paragraph gets skipped, and a skipped prompt trains you to skip the
# next one.
PROMPTS: list[str] = [
    "What did you get wrong this week, and has it cost anything yet?",
    "Name the thing you keep almost starting.",
    "What would you do today if nobody asked you about it afterwards?",
    "Who are you avoiding, and is it about them?",
    "What is the smallest version of the thing you are putting off?",
    "Describe yesterday in one sentence that is not about work.",
    "What are you pretending not to have noticed?",
    "Which of your opinions has changed in the last year?",
    "What would make today count, specifically?",
    "What are you doing because you always have?",
    "Who did something for you recently that you have not acknowledged?",
    "What is currently costing you more attention than it is worth?",
    "Write down the thing you would tell a friend in your position.",
    "What went better than expected, and why did you expect worse?",
    "What are you good at that you have stopped practising?",
    "If today repeated, what would you change about it?",
    "Name one thing you own that you would not buy again.",
    "What have you been calling a plan that is actually a wish?",
]


@register
class JournalingPrompt(Slot):
    spec = SlotSpec(id=48, name="Journaling prompt", tier="uncommon",
                    paper_mm=43, needs_narrator=True)

    LINES = 4

    def _result(self, ctx: Context) -> SlotResult:
        prompt = ctx.rng(self.spec.id).choice(PROMPTS)
        rules = "".join('<div class="ruled-line"></div>'
                        for _ in range(self.LINES))
        return SlotResult(
            head="Four Lines",
            body=prompt,
            # The ruled lines go in `fine`, which the narrator never touches, so
            # the prompt itself stays narratable while the lines cannot be
            # overwritten by a sentence.
            fine=f'{_CSS}<div class="ruled">{rules}</div>',
            brief={"prompt": prompt,
                   "instruction": "Put this question in voice, in one sentence. "
                                  "Keep what it is asking exactly the same. "
                                  "Four ruled lines are printed beneath it - "
                                  "do not answer it, and do not suggest an "
                                  "answer."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


# --------------------------------------------------------------------------
# The prompt is what makes this a slot rather than three empty boxes. SLOTS.md
# is explicit about it, and it is the difference between "draw something" and
# something you might actually draw.
COMIC_PROMPTS: list[str] = [
    "Four panels: something arrives, something goes wrong, nobody comments.",
    "A conversation between two objects on your desk.",
    "The same room, four times, an hour apart.",
    "Something very small has a very large opinion.",
    "Draw the weather as a person having a bad day.",
    "A machine explains itself badly.",
    "Four panels, no words, one of them a lie.",
    "The last thing you looked at, from its own point of view.",
    "Someone is waiting. Then still waiting. Then something else.",
    "Draw what is directly behind you without turning round.",
    "A very ordinary object, promoted beyond its competence.",
    "Four panels where only the background changes.",
    "Something you saw yesterday and have not mentioned to anyone.",
    "A door, and what is being decided on either side of it.",
]


@register
class ComicPanels(Slot):
    spec = SlotSpec(id=87, name="Blank comic panels", tier="rare",
                    paper_mm=72, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        prompt = ctx.rng(self.spec.id).choice(COMIC_PROMPTS)
        panels = "".join('<div class="panel"></div>' for _ in range(4))
        return SlotResult(
            head="Four Panels",
            body=prompt,
            fine=f'{_CSS}<div class="panels">{panels}</div>',
            brief={"prompt": prompt,
                   "instruction": "Give this drawing prompt in voice, in one "
                                  "sentence. Keep what is being asked for the "
                                  "same. Four empty panels are printed beneath "
                                  "it; do not describe what should go in them "
                                  "beyond the prompt."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
