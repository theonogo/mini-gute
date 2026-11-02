"""Open-Meteo forecast source.

Free, no key, no auth. Three design notes worth keeping:

  * **`past_days=1`.** Yesterday's actuals arrive in the same request as today's
    forecast, so "three degrees cooler than yesterday" (slot 4) and the daylight
    delta (slot 5) work on the very first run. Deriving them from our own cache
    would have meant a cold-start day with two blank slots and a fortnight of
    subtly wrong deltas after any gap.
  * **Every success is cached.** On a network failure we serve the most recent
    stored payload and flag it stale. A day-old forecast is wrong about the
    afternoon and right about the season; a blank page is wrong about everything.
  * **A bundled sample forecast.** `sample()` reads a committed payload of the
    same shape, so the four weather slots have real fixtures and the receipt
    renders with no network and no cache. It is a separate door from `get()` on
    purpose: the cache fallback exists to rescue a bad morning, and quietly
    serving invented weather when a fetch fails would be the one thing the
    forecast must never do.

`sources/` fetches, `slots/` presents. Keeping them apart means four slots can
share one HTTP call without any of them knowing about the others.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date as Date
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .http import UA

ENDPOINT = "https://api.open-meteo.com/v1/forecast"
NAMESPACE = "openmeteo"
TIMEOUT = 15

SAMPLE = (Path(__file__).resolve().parent.parent
          / "assets" / "fixtures" / "openmeteo-london.json")

HOURLY = ("temperature_2m", "apparent_temperature", "precipitation_probability",
          "precipitation", "wind_speed_10m", "uv_index", "cloud_cover",
          "weather_code")
DAILY = ("sunrise", "sunset", "temperature_2m_max", "temperature_2m_min",
         "precipitation_sum", "uv_index_max", "weather_code")
# Yesterday for the delta, today, and tomorrow - which the three-day comparison
# needs and which costs nothing extra on the same call.
FORECAST_DAYS = 2


@dataclass
class Day:
    """One calendar day of weather. Hourly lists are always 24 long."""

    date: Date
    temp: list[float]
    apparent: list[float]
    rain_prob: list[float]
    precip: list[float]
    wind: list[float]
    uv: list[float]
    cloud: list[float]
    t_max: float
    t_min: float
    # WMO weather codes, hourly and for the day as a whole. Open-Meteo's own
    # judgement of what the sky is doing - fog, drizzle, sleet, thunder - which
    # cloud cover and rain probability can only approximate.
    code: list[int]
    day_code: int
    sunrise: datetime
    sunset: datetime
    precip_sum: float
    uv_max: float

    @property
    def daylight(self) -> float:
        """Seconds between sunrise and sunset."""
        return (self.sunset - self.sunrise).total_seconds()


@dataclass
class Forecast:
    today: Day
    yesterday: Day | None = None
    tomorrow: Day | None = None
    stale: bool = False
    stale_from: str | None = None
    place: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class WeatherUnavailable(RuntimeError):
    """No live fetch and nothing cached. The slot should drop."""


def _url(lat: float, lon: float, timezone: str) -> str:
    query = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": ",".join(HOURLY),
        "daily": ",".join(DAILY),
        "timezone": timezone,
        "past_days": 1,
        "forecast_days": FORECAST_DAYS,
    })
    return f"{ENDPOINT}?{query}"


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _slice_day(payload: dict, index: int) -> Day:
    """Extract one day. `index` is 0 for yesterday, 1 for today (past_days=1)."""
    hourly, daily = payload["hourly"], payload["daily"]
    lo, hi = index * 24, index * 24 + 24

    def h(key: str) -> list[float]:
        # Open-Meteo can return nulls at the edges of a series.
        return [0.0 if v is None else float(v) for v in hourly.get(key, [])[lo:hi]]

    return Day(
        date=Date.fromisoformat(daily["time"][index]),
        temp=h("temperature_2m"),
        apparent=h("apparent_temperature"),
        rain_prob=h("precipitation_probability"),
        precip=h("precipitation"),
        wind=h("wind_speed_10m"),
        uv=h("uv_index"),
        cloud=h("cloud_cover"),
        code=[int(v or 0) for v in hourly["weather_code"][lo:hi]],
        day_code=int(daily["weather_code"][index] or 0),
        t_max=float(daily["temperature_2m_max"][index]),
        t_min=float(daily["temperature_2m_min"][index]),
        sunrise=datetime.fromisoformat(daily["sunrise"][index]),
        sunset=datetime.fromisoformat(daily["sunset"][index]),
        precip_sum=float(daily["precipitation_sum"][index] or 0.0),
        uv_max=float(daily["uv_index_max"][index] or 0.0),
    )


# WMO 4677, grouped into the marks the receipt can actually draw.
CONDITIONS = {
    "clear": (0,), "part": (1, 2), "cloud": (3,), "fog": (45, 48),
    "drizzle": (51, 53, 55, 56, 57), "rain": (61, 63, 65, 66, 67, 80, 81, 82),
    "snow": (71, 73, 75, 77, 85, 86), "storm": (95, 96, 99),
}


def condition(code: int) -> str:
    """The drawable group a WMO code belongs to."""
    for name, codes in CONDITIONS.items():
        if code in codes:
            return name
    return "cloud"


def parse(payload: dict[str, Any]) -> Forecast:
    days = payload.get("daily", {}).get("time", [])
    if not days:
        raise WeatherUnavailable("payload has no daily series")
    # past_days=1 puts yesterday at 0 and today at 1. If the API returned only
    # one day, treat it as today and go without a delta rather than mislabel it.
    today_i = 1 if len(days) > 1 else 0
    return Forecast(
        today=_slice_day(payload, today_i),
        yesterday=_slice_day(payload, 0) if today_i == 1 else None,
        tomorrow=(_slice_day(payload, today_i + 1)
                  if len(days) > today_i + 1 else None),
        raw=payload,
    )


def get(lat: float, lon: float, *, timezone: str = "auto", store: Any = None,
        offline: bool = False, day: Date | None = None) -> Forecast:
    """Today's forecast, from the network or from the last good cache."""
    key = (day or Date.today()).isoformat()

    if not offline:
        try:
            payload = _fetch_json(_url(lat, lon, timezone))
            if store is not None:
                store.put(NAMESPACE, key, payload, when=day)
            return parse(payload)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, json.JSONDecodeError):
            pass  # fall through to cache; safe_fetch handles a total failure

    if store is not None:
        cached = store.fetch(NAMESPACE, key)
        if cached is not None:
            return parse(cached)
        latest = store.latest(NAMESPACE)
        if latest is not None:
            stored_key, payload = latest
            fc = parse(payload)
            fc.stale, fc.stale_from = True, stored_key
            return fc

    raise WeatherUnavailable("no live forecast and nothing cached")


# --------------------------------------------------------------------------
# the bundled sample


def _shift(stamp: str, days: int) -> str:
    """Move an ISO date, or an ISO timestamp, by whole days."""
    day, sep, clock = stamp.partition("T")
    moved = (Date.fromisoformat(day) + timedelta(days=days)).isoformat()
    return f"{moved}{sep}{clock}"


def _redate(payload: dict[str, Any], day: Date) -> dict[str, Any]:
    """Slide the sample so its last daily entry lands on `day`.

    The clock times are left alone. Shifting sunrise by the season as well would
    make the fixture a weak almanac, and it is not one - it is a fixed sample
    that has to sit under whatever date the contact sheet asks for.
    """
    daily, hourly = payload["daily"], payload["hourly"]
    # Align the day `parse` will call today - index 1 with past_days=1 - rather
    # than the last entry, which is tomorrow.
    today_i = 1 if len(daily["time"]) > 1 else 0
    offset = (day - Date.fromisoformat(daily["time"][today_i])).days
    if offset:
        for key in ("time", "sunrise", "sunset"):
            daily[key] = [_shift(v, offset) for v in daily[key]]
        hourly["time"] = [_shift(v, offset) for v in hourly["time"]]
    return payload


def sample(day: Date | None = None) -> Forecast:
    """The committed sample forecast, dated to `day`.

    Never touches the network or the store, so `--offline` and the contact sheet
    get the same weather every time they are asked for the same date. Two days
    of hourlies, as `past_days=1` returns, so the delta and daylight slots are
    exercised rather than skipped.
    """
    payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return parse(_redate(payload, day or Date.today()))
