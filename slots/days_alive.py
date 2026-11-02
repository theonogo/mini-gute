"""Slot 44 - Days alive.

How many days the reader has been alive, and when the next round number falls.

A count of days is a strange, clarifying number - five figures reads as a lot
more than an age in years and a lot less than forever - and the next milestone is
what makes it worth printing more than once. The ten-thousandth day in particular
is a genuine occasion most people never notice passing.

**Computed, never stored.** The date of birth lives in `.env` as QG_BIRTHDAY and
the count is arithmetic at print time, so it cannot drift. Verbatim: a persona
restating a day count is one slip away from a wrong one. No date of birth
configured, no section.
"""

from __future__ import annotations

from datetime import timedelta

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


def next_milestone(days: int) -> int:
    """The next multiple of 1,000. The ten-thousandth day arrives on its own."""
    return (days // 1_000 + 1) * 1_000


@register
class DaysAlive(Slot):
    spec = SlotSpec(id=44, name="Days alive", tier="uncommon", paper_mm=22,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        import config
        born = config.birth_date()
        if born is None or born > ctx.date:
            return None
        days = (ctx.date - born).days
        milestone = next_milestone(days)
        on = born + timedelta(days=milestone)
        away = (on - ctx.date).days
        return SlotResult(
            head="Days Alive",
            body=f'<div class="days-n">{days:,}</div>',
            fine=f"Day {milestone:,} falls on {on:%A %d %B %Y}, "
                 f"{away:,} day{'s' if away != 1 else ''} from now.",
            brief={"verbatim": True, "days": days, "next_milestone": milestone,
                   "instruction": "Name this section in voice. The count is "
                                  "exact and prints as it is."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)
