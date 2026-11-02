"""Slot 143 - Wise saying.

Reference implementation for a NARRATOR TEXT slot. The slot supplies facts; the
persona supplies the voice.

Note the split, because it recurs across most slots:

  * `body` holds the quotation itself. It must reach paper VERBATIM, so it is
    not something the narrator may rewrite (SYSTEM.md 9 - quotes are never
    embellished).
  * `brief` holds what the narrator MAY work with: who said it, roughly when,
    and the theme. The persona uses that to frame the quote in its own voice
    without touching the words.

Sources are public domain: Marcus Aurelius, Sun Tzu, Epictetus, Seneca.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# (text, attribution, era, theme)
SAYINGS: list[tuple[str, str, str, str]] = [
    ("You have power over your mind - not outside events. Realise this, and you "
     "will find strength.", "Marcus Aurelius", "c. 170 AD", "control"),
    ("The impediment to action advances action. What stands in the way becomes "
     "the way.", "Marcus Aurelius", "c. 170 AD", "obstacles"),
    ("Never let the future disturb you. You will meet it with the same weapons "
     "of reason which today arm you against the present.",
     "Marcus Aurelius", "c. 170 AD", "anxiety"),
    ("In the midst of chaos, there is also opportunity.",
     "Sun Tzu", "c. 500 BC", "opportunity"),
    ("Victorious warriors win first and then go to war, while defeated warriors "
     "go to war first and then seek to win.", "Sun Tzu", "c. 500 BC", "preparation"),
    ("If you know the enemy and know yourself, you need not fear the result of a "
     "hundred battles.", "Sun Tzu", "c. 500 BC", "self-knowledge"),
    ("It is not what happens to you, but how you react to it that matters.",
     "Epictetus", "c. 100 AD", "response"),
    ("Wealth consists not in having great possessions, but in having few wants.",
     "Epictetus", "c. 100 AD", "enough"),
    ("We suffer more often in imagination than in reality.",
     "Seneca", "c. 60 AD", "worry"),
    ("Luck is what happens when preparation meets opportunity.",
     "Seneca", "c. 60 AD", "luck"),
    ("He who is brave is free.", "Seneca", "c. 60 AD", "courage"),
    ("Waste no more time arguing about what a good man should be. Be one.",
     "Marcus Aurelius", "c. 170 AD", "action"),
]


@register
class WiseSaying(Slot):
    spec = SlotSpec(id=143, name="Wise saying", tier="common", paper_mm=32,
                    needs_narrator=True)

    def _pick(self, ctx: Context) -> SlotResult:
        text, who, era, theme = ctx.rng(self.spec.id).choice(SAYINGS)
        return SlotResult(
            head="Wise Saying",
            body=text,                       # verbatim - never rewritten
            fine=f"{who}, {era}",
            brief={"verbatim": True,
                   "attribution": who, "era": era, "theme": theme,
                   "instruction": "Frame this quotation in voice. Do not alter "
                                  "its wording."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._pick(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._pick(ctx)
