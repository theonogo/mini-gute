"""Slot 72 - Friend timezones.

What time it is where friends are, who is awake, and how warm it is there. The
zones are `TIMEZONES` in .env (`config.friend_timezones()`); the city printed is
the zone's own name, America/New_York as New York.

**The clocks are Python's and cannot fail.** Each zone goes through the tz
database (`zoneinfo`, backed by the `tzdata` package - Windows ships no database
of its own), so summer time in London and New York, which change on different
weekends, is right on any date with no network at all. A zone the database does
not know is dropped alone; the rest still print.

**Awake is 07:00 to 23:00 where they are**, `[timezones]` in config.toml. It is
a guess about other people's sleep, so the section states the rule in its fine
print: "asleep" reads as "it is 01:00 there", not as a claim about anyone.

**A temperature that cannot be fetched is left out, never borrowed.** One
Open-Meteo call carries every city's current reading. If it fails every clock
still prints and only the degrees go: yesterday's reading from the cache would
be a confident wrong number beside a correct time, so the readings have no
stale fallback. Coordinates are the opposite - a city does not move - so each
zone is geocoded once, checked against its own zone (Sydney, Australia and not
Sydney, Nova Scotia), and kept for good.

**The rows are verbatim.** A time and a temperature are facts (invariant 8);
the narrator names the section and writes nothing into it.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from datetime import date as Date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

FORECAST = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
NAMESPACE = "friendtz"

# A real Open-Meteo reply for a handful of major zones, the ones in
# .env.example among them. The fixture's temperatures come from here (a zone
# not in it prints without degrees); the clocks never do.
SAMPLE = (Path(__file__).resolve().parent.parent
          / "assets" / "fixtures" / "openmeteo-friends.json")

# The hour the receipt prints. A simulated date and the fixture show the
# clocks as they will stand then, rather than at whatever hour the preview
# happens to be run.
PRINT_HOUR = 7

STEP_MIN = 15             # resolution of the night bands; India is +05:30


@dataclass
class Clock:
    zone: str
    city: str
    local: datetime                # aware, in the friend's zone
    ahead_min: int                 # minutes ahead of here; negative is behind
    awake: bool
    # Night where they are, as (from, to) minutes along today's 24 hours here.
    nights: list[tuple[int, int]] = field(default_factory=list)
    temp: float | None = None


def awake_hours() -> tuple[int, int]:
    return (int(config.get("timezones", "awake_from", default=7)),
            int(config.get("timezones", "awake_until", default=23)))


def is_awake(hour: int, hours: tuple[int, int]) -> bool:
    lo, hi = hours
    return lo <= hour < hi if lo <= hi else (hour >= lo or hour < hi)


def city_name(zone: str) -> str:
    return zone.rsplit("/", 1)[-1].replace("_", " ")


def instant(ctx: Context, live: bool) -> datetime:
    """The moment the clocks are read, aware, in this machine's zone.

    A naive local time's `astimezone()` takes the offset in force on that date,
    so a simulated December morning gets winter time here as well as there.
    """
    if live and ctx.date == Date.today():
        return datetime.now().astimezone()
    return datetime.combine(ctx.date, time(PRINT_HOUR)).astimezone()


def night_spans(tz: ZoneInfo, day: Date,
                hours: tuple[int, int]) -> list[tuple[int, int]]:
    """When it is night there, along today's 24 hours here."""
    start = datetime.combine(day, time()).astimezone().astimezone(timezone.utc)
    spans: list[tuple[int, int]] = []
    for m in range(0, 24 * 60, STEP_MIN):
        local = (start + timedelta(minutes=m)).astimezone(tz)
        if is_awake(local.hour, hours):
            continue
        if spans and spans[-1][1] == m:
            spans[-1] = (spans[-1][0], m + STEP_MIN)
        else:
            spans.append((m, m + STEP_MIN))
    return spans


def clocks(zones: list[str], now: datetime) -> list[Clock]:
    """Every readable zone, west to east."""
    hours = awake_hours()
    here = now.utcoffset() or timedelta()
    out = []
    for zone in zones:
        try:
            tz = ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError):
            continue                  # a typo costs one friend, not the section
        local = now.astimezone(tz)
        out.append(Clock(
            zone=zone, city=city_name(zone), local=local,
            ahead_min=round(((local.utcoffset() or timedelta()) - here)
                            .total_seconds() / 60),
            awake=is_awake(local.hour, hours),
            nights=night_spans(tz, now.date(), hours)))
    return sorted(out, key=lambda c: c.ahead_min)


# --------------------------------------------------------------------------
# temperatures


def coordinates(zone: str, store: Any) -> tuple[float, float] | None:
    """The zone's own city, geocoded once and kept.

    The first result that sits in the zone, not the first result: "Sydney"
    returns several Sydneys, and only one of them is in Australia/Sydney.
    """
    from sources.http import cached_json

    ns = f"{NAMESPACE}:geocode:{zone}"
    payload = store.fetch(ns, "search") if store is not None else None
    if payload is None:
        url = f"{GEOCODE}?" + urllib.parse.urlencode(
            {"name": city_name(zone), "count": 10, "format": "json"})
        payload, _ = cached_json(url, store=store, namespace=ns, key="search")
    for hit in payload.get("results") or []:
        if hit.get("timezone") == zone:
            return float(hit["latitude"]), float(hit["longitude"])
    return None


def readings(payload: Any) -> list[float | None]:
    """Current temperatures from a multi-location reply, in request order.

    Open-Meteo answers a single location with an object and several with a
    list, so one city is wrapped.
    """
    rows = payload if isinstance(payload, list) else [payload]
    out: list[float | None] = []
    for row in rows:
        t = (row.get("current") or {}).get("temperature_2m")
        out.append(None if t is None else float(t))
    return out


def attach_live(found: list[Clock], store: Any) -> None:
    """Fill in what can be fetched. Anything that cannot stays None."""
    from sources.http import get_json

    located: list[tuple[Clock, tuple[float, float]]] = []
    for c in found:
        try:
            where = coordinates(c.zone, store)
        except Exception:  # noqa: BLE001 - this city loses its degrees only
            where = None
        if where:
            located.append((c, where))
    if not located:
        return
    url = f"{FORECAST}?" + urllib.parse.urlencode({
        "latitude": ",".join(f"{lat:.4f}" for _, (lat, _) in located),
        "longitude": ",".join(f"{lon:.4f}" for _, (_, lon) in located),
        "current": "temperature_2m",
    })
    try:
        temps = readings(get_json(url))
    except Exception:  # noqa: BLE001 - every clock keeps its time
        return
    for (c, _), t in zip(located, temps):
        c.temp = t


def attach_sample(found: list[Clock]) -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    by_zone = dict(zip(sample["zones"], readings(sample["response"])))
    for c in found:
        c.temp = by_zone.get(c.zone)


# --------------------------------------------------------------------------
# the page


def ahead_text(minutes: int) -> str:
    if minutes == 0:
        return "same time"
    h, m = divmod(abs(minutes), 60)
    return f"{'+' if minutes > 0 else '-'}{h}h{f'{m:02d}' if m else ''}"


def day_text(local: datetime, here: Date) -> str:
    diff = (local.date() - here).days
    return {1: "tomorrow", -1: "yesterday"}.get(diff, "")


def pct(minutes: float) -> str:
    return f"{100 * minutes / (24 * 60):.3f}%"


def row_html(c: Clock, here: Date, now_min: float) -> str:
    note = " &middot; ".join(p for p in (ahead_text(c.ahead_min),
                                         day_text(c.local, here),
                                         "awake" if c.awake else "asleep") if p)
    temp = "" if c.temp is None else f"{round(c.temp)}&deg;C"
    bands = "".join(f'<i class="tz-night" style="left:{pct(a)};'
                    f'width:{pct(b - a)}"></i>' for a, b in c.nights)
    return (f'<div class="tz-row">'
            f'<div class="tz-line">'
            f'<span class="tz-time{"" if c.awake else " inv"}">'
            f'{c.local:%H:%M}</span>'
            f'<span class="tz-who"><span class="tz-city">{c.city}</span> '
            f'<span class="tz-note">{note}</span></span>'
            f'<span class="tz-temp">{temp}</span></div>'
            f'<div class="tz-strip">{bands}'
            f'<i class="tz-now" style="left:{pct(now_min)}"></i></div>'
            f'</div>')


def axis_html() -> str:
    labels = "".join(f'<span style="left:{pct(h * 60)}">{h:02d}</span>'
                     for h in range(0, 25, 6))
    return f'<div class="tz-axis">{labels}</div>'


def body_html(found: list[Clock], now: datetime) -> str:
    start = datetime.combine(now.date(), time()).astimezone()
    now_min = min(24 * 60, max(0, (now - start).total_seconds() / 60))
    rows = "".join(row_html(c, now.date(), now_min) for c in found)
    return _CSS + rows + axis_html()


@register
class FriendTimezones(Slot):
    # Measured with five zones: 54mm (the Revolutionary) to 67mm (the Bootleg
    # Tape), plus a narrated header that wraps. Each friend is a row of about
    # 12mm, so a sixth needs [slots.paper_mm] 72 raised with it.
    spec = SlotSpec(id=72, name="Friend timezones", tier="uncommon",
                    paper_mm=70, needs_network=True, needs_narrator=True)

    def _result(self, found: list[Clock], now: datetime) -> SlotResult | None:
        if not found:
            return None               # nobody configured, or every zone a typo
        lo, hi = awake_hours()
        return SlotResult(
            head="Friends' Clocks",
            body=body_html(found, now),
            fine=f"Each bar is today, midnight to midnight here. Black is "
                 f"{hi:02d}:00 to {lo:02d}:00 where they are; the line is now.",
            brief={"verbatim": True,
                   "time_here": f"{now:%H:%M}",
                   "awake": [c.city for c in found if c.awake],
                   "asleep": [c.city for c in found if not c.awake],
                   "instruction": "Name this section in voice. The times and "
                                  "temperatures are facts and print exactly "
                                  "as they are."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        now = instant(ctx, live=True)
        found = clocks(config.friend_timezones(), now)
        if found:
            attach_live(found, ctx.store)
        return self._result(found, now)

    def fixture(self, ctx: Context) -> SlotResult | None:
        """Real clocks for the date at 07:00, the sample's temperatures.

        Reads no store, so it is the same on a machine that has run before and
        one that has not.
        """
        now = instant(ctx, live=False)
        found = clocks(config.friend_timezones(), now)
        attach_sample(found)
        return self._result(found, now)


_CSS = """
<style>
/* A world clock. The time leads and is boxed, as in the ISS timetable; it is
   reversed out when it is night there, so the sleepers are found at a glance
   down the left edge before anything is read. */
.tz-row   { margin: 0 0 9px; }
.tz-line  { display: grid; grid-template-columns: auto 1fr auto; gap: 10px;
            align-items: baseline; }
.tz-time  { font-family: var(--font-mono); font-weight: 700;
            border: 2px solid #000; padding: 1px 5px; }
.tz-city  { font-weight: var(--bold); }
.tz-note  { font-size: var(--size-small); white-space: nowrap; }
.tz-temp  { font-family: var(--font-mono); font-weight: 700;
            white-space: nowrap; }
/* Today here, midnight to midnight, with their night in black. Every bar
   shares the axis, so the nights march left from west to east and a free hour
   to call is a white gap. */
.tz-strip { position: relative; height: 12px; border: 2px solid #000;
            margin-top: 4px; }
.tz-night { position: absolute; top: 0; bottom: 0; background: #000; }
/* Now: one white rule, differenced, so it is black on white and white on
   black - there is no ground it vanishes into. Overhangs the bar so it reads
   as a pointer rather than as part of the night. */
.tz-now   { position: absolute; top: -6px; bottom: -6px; width: 3px;
            margin-left: -1px; background: #fff; mix-blend-mode: difference; }
.tz-axis  { position: relative; height: 1.3em; margin-top: -4px;
            font-family: var(--font-mono); font-size: var(--size-tiny); }
.tz-axis span { position: absolute; transform: translateX(-50%); }
.tz-axis span:first-child { transform: none; }
.tz-axis span:last-child  { transform: translateX(-100%); }
</style>
"""
