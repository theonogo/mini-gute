"""Slots 109 and 131 - the persona off the leash.

  * **109 persona free slot** - the persona drops the format and talks about
    whatever it likes.
  * **131 direct address** - the persona speaks to the reader directly
    (SYSTEM.md 3.3): introduces itself, complains about another persona,
    comments on the machine, or taunts the reader with sections never received.

The catalogue lists these as one entry, "109 + 131". They are two slots here
because SYSTEM.md 3.3 gives 131 its own section with its own behaviour, and
because two modes that both draw at rare would otherwise be one slot drawn twice
as often as its tier says.

**The taunt uses the real archive.** "Sections never received" is
computed - the registry minus every slot id that has ever printed - rather than
invented. A persona boasting about a section that has in fact printed three
times is not a taunt, it is a mistake, and the reader would catch it. Early in
the machine's life nearly everything is unreceived, which is exactly when a
taunt about it is funniest.

**These are the only slots with no subject at all**, which is what makes them
dangerous: nothing constrains them. So the brief hands over the persona's
rivals, the machine's age and the unreceived list as material - something to
push against - rather than a blank page.
"""

from __future__ import annotations

from typing import Any

import config

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


def unreceived(store: Any) -> list[str]:
    """Names of built sections that have never once printed."""
    from .registry import all_slots

    printed: set[int] = set()
    if store is not None:
        try:
            for row in store.recent_receipts(10_000):
                printed.update(row.get("slots", []))
        except Exception:  # noqa: BLE001 - an unreadable archive is an empty one
            pass
    rotating = {"common", "uncommon", "rare"}
    return sorted(s.spec.name for s in all_slots()
                  if s.spec.tier in rotating and s.spec.id not in printed)


def rivals(ctx: Context) -> list[str]:
    """The other personas, for a persona to have opinions about."""
    try:
        import main
        me = ctx.shared.get("persona_name")
        return [p.get("display", name) for name, p in
                main.load_personas().items() if name != me]
    except Exception:  # noqa: BLE001
        return []


def receipts_so_far(store: Any) -> int:
    try:
        return store.receipt_count() if store is not None else 0
    except Exception:  # noqa: BLE001
        return 0


# --------------------------------------------------------------------------
@register
class PersonaFreeSlot(Slot):
    spec = SlotSpec(id=109, name="Persona free slot", tier="rare", paper_mm=44,
                    needs_narrator=True)

    FALLBACK = ("The section usually printed here has been set aside. Nothing "
                "in particular has replaced it.")

    def _result(self, ctx: Context) -> SlotResult:
        return SlotResult(
            head="Off The Record",
            body=self.FALLBACK,
            brief={
                "other_personas": rivals(ctx),
                "receipts_printed_so_far": receipts_so_far(ctx.store),
                "instruction": "Drop the format. This section has no subject - "
                               "talk about whatever THIS persona would want to "
                               "talk about, in its own voice, for three to five "
                               "sentences. It might be a grievance, an "
                               "observation, a small confession, a preoccupation "
                               "it has been nursing. It must sound like nobody "
                               "else. Invent no facts about the world; opinions "
                               "and inner life are yours to make up.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


@register
class DirectAddress(Slot):
    spec = SlotSpec(id=131, name="Direct address", tier="rare", paper_mm=44,
                    needs_narrator=True)

    FALLBACK = ("A word, directly. There are sections of this receipt that have "
                "never once reached you. They are aware of this.")

    def _result(self, ctx: Context) -> SlotResult:
        never = unreceived(ctx.store)
        rng = ctx.rng(self.spec.id)
        sample = rng.sample(never, min(4, len(never))) if never else []
        name = config.reader_name()
        return SlotResult(
            head="A Word, Directly",
            body=self.FALLBACK,
            brief={
                "sections_never_received": sample,
                "how_many_never_received": len(never),
                "other_personas": rivals(ctx),
                "receipts_printed_so_far": receipts_so_far(ctx.store),
                "instruction": f"Address {name} directly, by name, stepping out "
                               "of the receipt format. Choose ONE of: introduce "
                               "yourself; complain about one of the other "
                               "personas; comment on the machine that prints "
                               f"you; or taunt {name} with sections never "
                               "received. If you taunt, use only the real names "
                               "in `sections_never_received` - they are "
                               "genuinely unreceived, and naming one that is not "
                               "on that list would be a lie the reader could "
                               "catch. Three to five sentences, in voice.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
