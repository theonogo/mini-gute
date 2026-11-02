"""Slot 78 - Fake product line item.

An infomercial for something that ought to exist, priced, laid out as a receipt
row. Rare, so it stays a surprise.

**Python names the product and sets the price; the narrator writes the pitch.**
That split is not arbitrary. The row and the pitch have to agree, and the
narrator returns free text with no field for a product name, so letting it
invent one would mean the row said one thing and the sentence underneath said
another. The name is in the brief instead, and the persona sells that.

The price is drawn from the same seeded generator as everything else, so a given
date always prices a given product the same way. It is deliberately specific -
£38.40 rather than £40 - because a round number reads as a joke and an odd one
reads as a catalogue.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# (product, what it does). The second half is a fact for the narrator to sell,
# not copy to print: without it every pitch is just the name restated.
PRODUCTS: list[tuple[str, str]] = [
    ("THE CONVERSATION EXIT", "ends a conversation without either party losing face"),
    ("SPARE HOUR", "one additional hour, usable only on a Sunday afternoon"),
    ("UMBRELLA THAT CANNOT BE LEFT BEHIND", "returns to its owner within the hour"),
    ("SILENT SMOKE ALARM", "informs you of a fire by other means"),
    ("PRE-APOLOGISED EMAIL", "arrives already forgiven"),
    ("THE SECOND FIRST IMPRESSION", "single use, non-transferable"),
    ("CABLE IDENTIFIER", "states what a cable is for and whether you still need it"),
    ("SLIGHTLY SHORTER MEETING", "identical to the meeting, ending eleven minutes sooner"),
    ("KEYS THAT ANSWER WHEN CALLED", "responds to its own name, once per day"),
    ("PORTABLE SENSE OF DIRECTION", "worn on the wrist, works only outdoors"),
    ("THE UNSENT MESSAGE RETRIEVER", "recovers a message up to four seconds after sending"),
    ("BREAD THAT STAYS FRESH HONESTLY", "goes stale on schedule and says so in advance"),
    ("QUEUE POSITION TRANSFER", "swap places with someone who is not in a hurry"),
    ("A GOOD NIGHT'S SLEEP, BOXED", "eight hours, redeemable within one calendar month"),
    ("THE DECISION MAKER", "chooses between two options and never explains itself"),
    ("SOCK REUNIFICATION SERVICE", "matches one sock to its pair anywhere in the country"),
    ("PLANT THAT SURVIVES YOU", "requires neglect; dies if watered on a schedule"),
    ("THE POLITE INTERRUPTION", "stops someone mid-sentence with no ill feeling"),
]


@register
class FakeProduct(Slot):
    spec = SlotSpec(id=78, name="Fake product line item", tier="rare",
                    paper_mm=23, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        name, does = rng.choice(PRODUCTS)
        # Deliberately unround. Weighted low so the row sits plausibly among the
        # real itemization prices rather than towering over them.
        price = rng.randint(3, 89) + rng.choice([0.40, 0.99, 0.25, 0.75, 0.95])
        return SlotResult(
            head="Also Available",
            body=f"{name} &mdash; {does}.",
            # `fine` is never narrated, so the row and the pitch cannot drift.
            fine=f'<span class="item"><span class="item-name">{name}</span>'
                 f'<span class="leader"></span>'
                 f'<span class="item-price">{price:.2f}</span></span>',
            brief={"product": name,
                   "does": does,
                   "price": f"{price:.2f}",
                   "instruction": "Sell this product in one or two sentences, in "
                                  "voice, as though it genuinely exists and is "
                                  "in stock. Use the product's name exactly as "
                                  "given - it is printed as a line item below "
                                  "your text and the two must match. Do not "
                                  "restate the price."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
