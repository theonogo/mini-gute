"""Rotating content slots.

One slot is one module. Import this package and every slot registers itself:

    from slots import registry
    registry.load_all()
    registry.all_slots()

`registry.coverage()` diffs what is built against docs/SLOTS.md.
"""

from .base import Context, Slot, SlotFailure, SlotResult, SlotSpec, safe_fetch

__all__ = ["Slot", "SlotSpec", "SlotResult", "SlotFailure", "Context", "safe_fetch"]
