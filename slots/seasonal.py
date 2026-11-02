"""Slot 34 - What's in season.

What is actually good to eat right now, by month.

**Northern hemisphere, and specifically northern Europe.** The data is a table
rather than an API because the good sources are either national and paywalled or
national and unstructured, and because this genuinely is a lookup table that
changes once a decade. The month is what matters, not the year.

The hemisphere is derived from the configured latitude rather than assumed: a
table that silently claims asparagus in April for a reader in Melbourne would be
wrong in the one way this receipt is not allowed to be wrong. Below the equator the
lookup is shifted six months, which is a rough but honest approximation - it
gets the season right even where it gets the local crop wrong, and the slot says
so.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# month -> (vegetables, fruit, one thing worth going out of your way for)
CALENDAR: dict[int, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    1: (("kale", "leeks", "celeriac", "swede", "chicory"),
        ("blood oranges", "forced rhubarb", "quince"),
        "forced rhubarb, which is grown in the dark and only lasts weeks"),
    2: (("purple sprouting broccoli", "cabbage", "parsnips", "cauliflower"),
        ("blood oranges", "forced rhubarb", "seville oranges"),
        "purple sprouting broccoli, at its best before the weather turns"),
    3: (("leeks", "spring greens", "sorrel", "wild garlic"),
        ("rhubarb", "bananas"),
        "wild garlic, which grows free in damp woodland and disappears by May"),
    4: (("asparagus", "spring onions", "radishes", "new potatoes"),
        ("rhubarb",),
        "the first asparagus, which has about eight weeks and no substitute"),
    5: (("asparagus", "peas", "broad beans", "new potatoes", "watercress"),
        ("strawberries", "rhubarb"),
        "broad beans small enough to eat raw"),
    6: (("courgettes", "peas", "broad beans", "lettuce", "beetroot"),
        ("strawberries", "cherries", "gooseberries", "elderflower"),
        "cherries, for the three weeks they are worth the money"),
    7: (("runner beans", "courgettes", "fennel", "tomatoes", "chard"),
        ("raspberries", "blackcurrants", "apricots", "cherries"),
        "tomatoes that have actually seen sun"),
    8: (("sweetcorn", "tomatoes", "aubergines", "peppers", "runner beans"),
        ("blackberries", "plums", "greengages", "peaches"),
        "greengages, which are around for a fortnight and then not"),
    9: (("sweetcorn", "marrow", "kale", "leeks", "wild mushrooms"),
        ("blackberries", "damsons", "figs", "apples"),
        "wild mushrooms, if you know someone who knows"),
    10: (("pumpkin", "squash", "celeriac", "beetroot", "wild mushrooms"),
         ("apples", "pears", "quince", "sloes"),
         "quince, which is inedible raw and extraordinary cooked"),
    11: (("brussels sprouts", "parsnips", "swede", "jerusalem artichokes"),
         ("apples", "pears", "cranberries", "chestnuts"),
         "chestnuts, roasted badly at home rather than well on a street"),
    12: (("brussels sprouts", "red cabbage", "celeriac", "kale"),
         ("clementines", "pomegranate", "cranberries"),
         "clementines with the leaves still on"),
}

SHIFT = 6      # months, to approximate the southern hemisphere


def month_for(ctx: Context) -> tuple[int, bool]:
    """(month to look up, whether it was shifted for the hemisphere)."""
    try:
        import config
        latitude, _, _ = config.location()
    except Exception:  # noqa: BLE001 - an unset location is not a failure here
        return ctx.date.month, False
    if latitude >= 0:
        return ctx.date.month, False
    return (ctx.date.month + SHIFT - 1) % 12 + 1, True


@register
class InSeason(Slot):
    spec = SlotSpec(id=34, name="What's in season", tier="uncommon",
                    paper_mm=20, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        month, shifted = month_for(ctx)
        veg, fruit, pick = CALENDAR[month]
        rng = ctx.rng(self.spec.id)

        # Three of the vegetables rather than all of them: a list of five is a
        # stock check, and three is a suggestion.
        chosen = rng.sample(list(veg), min(3, len(veg)))
        return SlotResult(
            head="In Season",
            body=f"{', '.join(chosen).capitalize()}. "
                 f"{pick[0].upper() + pick[1:]}.",
            fine=("Northern-hemisphere calendar, shifted six months for your "
                  "latitude - the season is right, the local crop may not be."
                  if shifted else None),
            brief={"month": f"{ctx.date:%B}",
                   "vegetables": chosen,
                   "fruit": list(fruit),
                   "worth_seeking": pick,
                   "instruction": "Say what is worth eating now, in voice, in "
                                  "one or two sentences, leading with the thing "
                                  "worth seeking out. Use only the produce "
                                  "listed - do not add items, and do not claim "
                                  "anything about prices or availability."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
