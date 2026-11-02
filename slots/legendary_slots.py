"""Slots 134 and 144 - the two legendary slots that are whole-page formats.

SLOTS.md lists a full persona takeover (134) and a full short story (144) as
legendary slots; SYSTEM.md 4.1 lists the same two as legendary formats 8 and 9.
They are one thing, and it is a format: both abandon the receipt entirely, which
a slot - a section on an ordinary receipt - cannot do. The work lives in
`legendary.py` (`PersonaTakeover`, `FullStory`).

These registrations exist so the catalogue knows they are built. They never
print a section: legendary-tier slots are not drawn by the selection engine, and
`fetch` returns None if anything ever asks.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


class _FormatSlot(Slot):
    def fetch(self, ctx: Context) -> SlotResult | None:
        return None

    def fixture(self, ctx: Context) -> SlotResult | None:
        return None


@register
class PersonaTakeover(_FormatSlot):
    spec = SlotSpec(id=134, name="Full persona takeover", tier="legendary",
                    paper_mm=0, needs_narrator=True)


@register
class FullShortStory(_FormatSlot):
    spec = SlotSpec(id=144, name="Full short story", tier="legendary",
                    paper_mm=0)
