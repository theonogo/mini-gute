"""Slot 118 - One-day-only slots.

Birthday, the solstices and equinoxes, and 29 February. These **bypass the draw
entirely** (SYSTEM.md 4): on the day, the section prints; on every other day it
cannot, whatever the rarity roll says.

**The astronomical dates are computed, not tabled.** The solstices and equinoxes
drift across two calendar days from year to year, and a table of "21 June, 21
December" is wrong often enough to matter on the one day the section exists to
mark. PyEphem gives the actual instant. The section fires on the local calendar
date that instant falls in, which is not always the UTC one: an equinox at
00:05 UTC is the previous evening west of Greenwich.

**The occasions can coincide, and the section says so when they do.** A birthday
on an equinox is one section about both, not two sections that ignore each
other.

**The age is a fact, so it is computed and handed over, never guessed.** With the
full date of birth in `.env` the section knows exactly how old the reader turns,
and the narrator receives that number rather than being left to infer it - a
persona rounding a birthday up by a year is a small wrong fact on the one
morning it would be noticed.
"""

from __future__ import annotations

from datetime import date as Date, timezone

import config

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


def _local_day(ephem_date) -> Date:
    """The calendar day an instant falls on in this machine's own zone."""
    import ephem
    utc = ephem.Date(ephem_date).datetime().replace(tzinfo=timezone.utc)
    return utc.astimezone().date()


def season_marker(day: Date) -> str | None:
    """'the September equinox' etc. if a season turns on `day`, else None."""
    try:
        import ephem
    except ImportError:
        return None
    start = f"{day.year}/1/1"
    markers = []
    cursor = start
    for _ in range(4):
        eq = ephem.next_equinox(cursor)
        so = ephem.next_solstice(cursor)
        markers.append((eq, "equinox"))
        markers.append((so, "solstice"))
        cursor = min(eq, so) + 1
    for instant, kind in markers:
        if _local_day(instant) == day:
            month = f"{_local_day(instant):%B}"
            return f"the {month} {kind}"
    return None


def birthday_name() -> str:
    return f"{config.reader_name()}'s birthday"


def occasions(day: Date) -> list[str]:
    """Every one-day-only occasion that falls on `day`."""
    out = []
    bday = config.birthday()
    if bday and (day.month, day.day) == bday:
        out.append(birthday_name())
    season = season_marker(day)
    if season:
        out.append(season)
    if day.month == 2 and day.day == 29:
        out.append("29 February, which only exists one year in four")
    return out


@register
class OneDayOnly(Slot):
    spec = SlotSpec(id=118, name="One-day-only slots", tier="legendary",
                    paper_mm=40, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        found = occasions(ctx.date)
        if not found:
            return None
        both = len(found) > 1
        name = config.reader_name()
        born = config.birth_date()
        turning = (ctx.date.year - born.year
                   if born and birthday_name() in found else None)
        return SlotResult(
            head="Today Only",
            body=("Today is " + " and ".join(found) + "."),
            fine="This section prints on this date and no other.",
            brief={
                "occasions": found,
                "coinciding": both,
                **({"age_turning": turning} if turning else {}),
                "instruction": "Mark today's occasion, in voice, in three or "
                               "four sentences. " +
                               ("It is TWO occasions at once - "
                                + " and ".join(found) + " - so make something "
                                "of their falling on the same day rather than "
                                "treating them separately. " if both else "") +
                               f"Warm but not saccharine. If it is {name}'s "
                               f"birthday, address {name} directly. The age turned "
                               "is given in `age_turning` and is exact; use that "
                               "number if you mention it, and never any other.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)
