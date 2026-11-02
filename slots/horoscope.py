"""Slot 150 - Horoscope.

A reading for a star sign that does not exist. The persona invents the sign and
the reading together, so the sign is as much in voice as the prediction is - the
clerk's invented constellation and the duty officer's should not be
interchangeable.

**About one day in eight it uses a real zodiac sign.** That ratio is the whole
design. A slot that invents a sign every single time stops being a joke by the
second week, because the invention becomes the format; an occasional real sign
resets the expectation and makes the next invented one land. It is the same
reasoning as printing the failed legendary roll.

**The invention is disclosed in words, not marked with a symbol.** `CLAUDE.md`
invariant 8 requires fabricated content to carry a consistent mark, and the
letter of that would be the dagger slot 103 uses. Here the disclosure IS the
joke - "sign invented on the premises" is funnier than a footnote glyph and
discloses strictly more, since it says *what* was invented rather than merely
that something was. On a real-sign day the line says so instead, which is what
makes the ratio visible to the reader at all.

Nothing in this slot is a prediction about anything. The instruction is explicit
that it must not touch health, money or relationships in any way a reader could
act on - a horoscope is a toy, and a toy that gives advice is not one.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# One morning in eight. Frequent enough to be noticed across a month, rare
# enough that an invented sign is still the norm.
REAL_SIGN_CHANCE = 0.125

ZODIAC = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
          "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")

# Territories for an invented sign. Python picks the territory, the persona
# names the constellation within it - which keeps the inventions spread out
# instead of clustering wherever the model's instincts happen to sit, and gives
# the fallback something to work with.
DOMAINS: list[tuple[str, str]] = [
    ("household", "an ordinary household object"),
    ("stationery", "something from a desk drawer"),
    ("weather", "a specific and unglamorous kind of weather"),
    ("transport", "a form of transport or a part of one"),
    ("bureaucracy", "a piece of paperwork or officialdom"),
    ("kitchen", "something found in a kitchen"),
    ("timing", "a particular awkward hour or interval of the day"),
    ("posture", "a way of standing, sitting or waiting"),
    ("tools", "a hand tool, or the one you cannot find"),
    ("textiles", "an item of clothing, or the state of one"),
    ("smallanimal", "a small and unimpressive animal"),
    ("plumbing", "something that carries water and occasionally does not"),
    ("furniture", "a piece of furniture with a grievance"),
    ("sound", "a domestic noise nobody can locate"),
    ("stationary", "a thing that has not been moved in years"),
    ("leftovers", "a food in its final hours"),
]

DISCLOSURE_INVENTED = "Sign invented on the premises."
DISCLOSURE_REAL = "A real one, for once."

FALLBACK_INVENTED = (
    "Those born under this sign are advised that the week will resolve itself "
    "without their supervision, and may resent this.")
FALLBACK_REAL = (
    "The stars have filed nothing of note. Proceed as though unobserved.")


@register
class Horoscope(Slot):
    spec = SlotSpec(id=150, name="Horoscope", tier="common", paper_mm=32,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        real = rng.random() < REAL_SIGN_CHANCE

        if real:
            sign = rng.choice(ZODIAC)
            brief = {
                "sign": sign,
                "sign_is_real": True,
                "instruction": f"Write a horoscope for {sign}, in voice. This "
                               f"one is a REAL sign - use its name exactly and "
                               f"do not invent a different one. Two or three "
                               f"sentences. Give the header as the sign's name "
                               f"in your own styling. It must be entertainment "
                               f"only: nothing about health, money or "
                               f"relationships that a reader could act on, and "
                               f"no advice that costs anything to follow.",
            }
            return SlotResult(head=sign.upper(), body=FALLBACK_REAL,
                              fine=DISCLOSURE_REAL, brief=brief)

        _, domain = rng.choice(DOMAINS)
        return SlotResult(
            head="Your Sign Today",
            body=FALLBACK_INVENTED,
            # Never narrated, so the disclosure cannot be written away.
            fine=DISCLOSURE_INVENTED,
            brief={
                "sign_is_real": False,
                "fabricated": True,
                "invent_a_sign_from": domain,
                "instruction": "INVENT a star sign - one that does not exist - "
                               "drawn from the territory given, name it in "
                               "voice, and write its reading. Two or three "
                               "sentences. The section header is the sign's "
                               "name; give it as the header. The invention is "
                               "the joke and the page already states that the "
                               "sign was invented, so commit to it completely - "
                               "no winking, no disclaimer of your own. "
                               "Entertainment only: nothing about health, money "
                               "or relationships a reader could act on.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
