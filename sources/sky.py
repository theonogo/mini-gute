"""The sky over wherever the receipt is, computed rather than fetched.

Shared by slots 35 (ISS passes), 36 (visible planets) and 38 (star chart).

**Local arithmetic, not an API.** PyEphem computes planetary and stellar
positions from orbital elements it carries internally, so planets and stars need
no network at all and cannot go stale. The one exception is the ISS, whose orbit
decays and is re-measured constantly: its elements come from CelesTrak, free and
unauthenticated, and are cached because a two-day-old element set is still good
to within a few seconds of a pass.

**"Tonight" means an hour after sunset, not 21:00.** A clock time is wrong in
two directions at once - in June 21:00 is still broad daylight at this latitude,
and in December it has been dark for four hours. An hour after local sunset is
roughly when the brighter objects become visible everywhere and in every season,
and it needs no timezone at all, because ephem computes sunset for the observer.

Everything here returns plain data. How the sky looks on paper is the slots'
problem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date as Date, datetime, timedelta, timezone
from typing import Any

import ephem
import ephem.stars  # the named-star catalogue is a submodule, not an attribute

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=tle"
TLE_NAMESPACE = "sky:tle"

PLANETS = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn")
# Below this the object is in the murk of the horizon and behind a building.
MIN_ALTITUDE_DEG = 10

COMPASS = ("north", "north-east", "east", "south-east",
           "south", "south-west", "west", "north-west")


def compass(azimuth_deg: float) -> str:
    return COMPASS[int((azimuth_deg % 360 + 22.5) // 45) % 8]


def observer(when: datetime | None = None) -> ephem.Observer:
    """An observer at the configured location."""
    import config

    lat, lon, _ = config.location()
    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.elevation = 0
    # Refraction on, at a typical sea-level pressure. It lifts objects near the
    # horizon by about half a degree, which is the difference between "just
    # visible" and "not" for anything low.
    obs.pressure = 1010
    if when is not None:
        obs.date = ephem.Date(when)
    return obs


def tonight(day: Date) -> datetime:
    """One hour after local sunset on `day`, as a UTC datetime."""
    obs = observer(datetime(day.year, day.month, day.day, 12,
                            tzinfo=timezone.utc).replace(tzinfo=None))
    try:
        sunset = obs.next_setting(ephem.Sun()).datetime()
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        # Polar day or night. Not a case this printer will meet, but it must not
        # raise: pick a fixed evening hour instead.
        sunset = datetime(day.year, day.month, day.day, 20)
    return sunset + timedelta(hours=1)


@dataclass
class SkyObject:
    name: str
    altitude: float        # degrees above the horizon
    azimuth: float         # degrees clockwise from north
    magnitude: float       # lower is brighter

    @property
    def direction(self) -> str:
        return compass(self.azimuth)


def planets_tonight(day: Date) -> list[SkyObject]:
    """Planets above MIN_ALTITUDE_DEG an hour after sunset, brightest first."""
    obs = observer(tonight(day))
    out = []
    for name in PLANETS:
        body = getattr(ephem, name)()
        body.compute(obs)
        alt, az = math.degrees(body.alt), math.degrees(body.az)
        if alt >= MIN_ALTITUDE_DEG:
            out.append(SkyObject(name, alt, az, float(body.mag)))
    return sorted(out, key=lambda o: o.magnitude)


def moon_tonight(day: Date) -> SkyObject | None:
    obs = observer(tonight(day))
    moon = ephem.Moon()
    moon.compute(obs)
    alt = math.degrees(moon.alt)
    if alt < MIN_ALTITUDE_DEG:
        return None
    return SkyObject("Moon", alt, math.degrees(moon.az), float(moon.mag))


def stars_tonight(day: Date, max_magnitude: float = 2.6) -> list[SkyObject]:
    """Named bright stars above the horizon an hour after sunset.

    ephem ships a catalogue of roughly a hundred named stars. Magnitude 2.6
    keeps the ones visible from a city - a chart full of stars nobody can
    actually see from a street is a chart of disappointment.
    """
    obs = observer(tonight(day))
    out = []
    for name in sorted(ephem.stars.stars):
        star = ephem.star(name)
        star.compute(obs)
        alt = math.degrees(star.alt)
        if alt > 0 and float(star.mag) <= max_magnitude:
            out.append(SkyObject(name, alt, math.degrees(star.az),
                                 float(star.mag)))
    return sorted(out, key=lambda o: o.magnitude)


# --- ISS -----------------------------------------------------------------
def iss_elements(store: Any = None, offline: bool = False) -> list[str]:
    """The ISS two-line element set, live or cached."""
    from sources.http import SourceUnavailable, get_bytes

    if not offline:
        try:
            lines = [ln.strip() for ln in get_bytes(TLE_URL).decode()
                     .strip().splitlines() if ln.strip()]
            if len(lines) == 3:
                if store is not None:
                    store.put(TLE_NAMESPACE, "iss", lines)
                return lines
        except Exception:  # noqa: BLE001 - fall back to the cache
            pass
    if store is not None:
        cached = store.fetch(TLE_NAMESPACE, "iss")
        if cached and len(cached) == 3:
            return cached
    raise SourceUnavailable("no ISS elements, live or cached")


@dataclass
class Pass:
    start: datetime        # local
    peak: datetime
    end: datetime
    max_altitude: float
    rise_direction: str
    set_direction: str

    @property
    def minutes(self) -> int:
        return max(1, round((self.end - self.start).total_seconds() / 60))


def visible_passes(day: Date, store: Any = None, offline: bool = False,
                   hours: int = 30, limit: int = 2) -> list[Pass]:
    """ISS passes someone could actually see, starting from the evening of `day`.

    A pass is only visible when three things hold at once: the station is above
    the horizon, the station is in sunlight, and the observer is in darkness.
    The first alone is what a naive pass predictor reports, and most of those
    passes happen in daylight or with the station in Earth's shadow - it is
    overhead and invisible. Checked at the pass peak, which is when it matters.
    """
    lines = iss_elements(store, offline)
    iss = ephem.readtle(*lines)
    start = tonight(day) - timedelta(hours=2)
    obs = observer(start)
    obs.horizon = str(MIN_ALTITUDE_DEG)

    out: list[Pass] = []
    cursor = ephem.Date(start)
    stop = ephem.Date(start + timedelta(hours=hours))
    for _ in range(20):
        obs.date = cursor
        try:
            rise_t, rise_az, peak_t, peak_alt, set_t, set_az = obs.next_pass(iss)
        except ValueError:
            break
        if rise_t is None or set_t is None or rise_t > stop:
            break

        obs.date = peak_t
        iss.compute(obs)
        sun = ephem.Sun()
        sun.compute(obs)
        dark_enough = math.degrees(sun.alt) < -6
        if dark_enough and not iss.eclipsed:
            out.append(Pass(
                start=ephem.localtime(rise_t), peak=ephem.localtime(peak_t),
                end=ephem.localtime(set_t),
                max_altitude=math.degrees(peak_alt),
                rise_direction=compass(math.degrees(rise_az)),
                set_direction=compass(math.degrees(set_az))))
            if len(out) >= limit:
                break
        cursor = ephem.Date(set_t + ephem.minute * 5)
    return out
