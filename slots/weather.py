"""Slots 2, 3, 4, 5 - the weather spine.

Four slots, one HTTP call. They share it through `ctx.shared` rather than each
fetching, which is what that scratch space exists for. Offline they share one
bundled payload the same way, so a fixture render exercises the same slicing,
signal and composition code a real morning does - the only thing swapped is
where the JSON came from.

Slot 2 is the only one that needs judgement. The rest are presentation:
  3  the 24h chart          - SVG, hatch fills, never opacity
  4  delta vs yesterday     - from Open-Meteo's past_days, not our own cache
  5  sunrise/sunset/daylight

**The verdict here is a fallback, not the final copy.** The persona writes it
from `brief`. What the slot must do is compute the *signals* - what
today actually requires - so the narrator is reasoning over facts rather than
inventing a forecast. SLOTS.md is explicit that it must range widely and never
collapse to a binary jacket yes/no, so the composer below builds a sentence from
several independent clauses instead of picking from a ladder.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import config
from render.chart import temp_rain_svg
from sources import openmeteo

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

SHARED_KEY = "weather.forecast"


# --------------------------------------------------------------------------
# shared fetch


def _shared(ctx: Context,
            make: Callable[[], openmeteo.Forecast]) -> openmeteo.Forecast:
    """One forecast per run, live or bundled, whichever door it came in by."""
    if SHARED_KEY not in ctx.shared:
        fc = make()
        fc.place = config.location()[2]
        ctx.shared[SHARED_KEY] = fc
    return ctx.shared[SHARED_KEY]


def forecast(ctx: Context) -> openmeteo.Forecast:
    """Today's forecast, fetched once per run however many slots ask."""
    def fetch() -> openmeteo.Forecast:
        lat, lon, _ = config.location()
        return openmeteo.get(
            lat, lon,
            timezone=config.get("location", "timezone", default="auto"),
            store=ctx.store, offline=ctx.offline, day=ctx.date)

    return _shared(ctx, fetch)


def sample_forecast(ctx: Context) -> openmeteo.Forecast:
    """The bundled forecast, shared exactly as the live one is.

    `openmeteo.get(offline=True)` is not the fixture path: it reads the store,
    so it hands back yesterday's real weather on a machine that has run before
    and raises on one that has not. A fixture has to be the same on both.
    """
    return _shared(ctx, lambda: openmeteo.sample(ctx.date))


# --------------------------------------------------------------------------
# signals


@dataclass
class RainWindow:
    start: int
    end: int          # exclusive
    peak: float

    def __str__(self) -> str:
        return f"{self.start:02d}-{self.end:02d}"


@dataclass
class Signals:
    t_min: float
    t_max: float
    feels_min: float
    feels_max: float
    swing: float
    rain: list[RainWindow]
    precip_mm: float
    uv_max: float
    wind_max: float


def signals(day: openmeteo.Day) -> Signals:
    lo = int(config.get("weather", "day_start", default=7))
    hi = int(config.get("weather", "day_end", default=22))
    prob = float(config.get("weather", "rain_probability", default=45))
    min_hours = int(config.get("weather", "rain_min_hours", default=1))

    window = slice(lo, hi)
    temps = day.temp[window] or day.temp
    feels = day.apparent[window] or day.apparent

    rain: list[RainWindow] = []
    start: int | None = None
    for hour in range(lo, hi):
        wet = day.rain_prob[hour] >= prob
        if wet and start is None:
            start = hour
        elif not wet and start is not None:
            if hour - start >= min_hours:
                rain.append(RainWindow(start, hour,
                                       max(day.rain_prob[start:hour])))
            start = None
    if start is not None and hi - start >= min_hours:
        rain.append(RainWindow(start, hi, max(day.rain_prob[start:hi])))

    return Signals(
        t_min=min(temps), t_max=max(temps),
        feels_min=min(feels), feels_max=max(feels),
        swing=max(temps) - min(temps),
        rain=rain,
        precip_mm=day.precip_sum,
        uv_max=day.uv_max,
        wind_max=max(day.wind[window] or day.wind),
    )


def compose_verdict(s: Signals) -> str:
    """A fallback verdict, built from independent clauses.

    Deliberately not a lookup table keyed on temperature: SLOTS.md requires this
    to range widely. Each clause fires on its own condition, so a cold windy dry
    day and a mild wet one produce genuinely different sentences.
    """
    parts: list[str] = []

    if s.feels_min < 2:
        parts.append("Proper coat, and mean it")
    elif s.feels_min < 8:
        parts.append("Coat")
    elif s.feels_min < 13:
        parts.append("A jacket, or regret it after dark")
    elif s.feels_min < 18:
        parts.append("Something light over the top")
    elif s.feels_max > 26:
        parts.append("Too warm for anything with sleeves you care about")
    else:
        parts.append("Shirtsleeves hold")

    if s.rain:
        first = s.rain[0]
        heavy = first.peak >= 75
        if len(s.rain) > 1:
            parts.append(f"rain on and off from {s.rain[0].start:02d}00, "
                         f"worst around {first.start:02d}00")
        elif heavy:
            parts.append(f"rain {first} and it means it")
        else:
            parts.append(f"a wet patch {first}")
    elif s.precip_mm > 0.2:
        parts.append("a bit of drizzle, nothing organised")

    if s.uv_max >= float(config.get("weather", "uv_notable", default=5)):
        parts.append("and enough sun to squint at")

    if s.wind_max >= float(config.get("weather", "wind_notable", default=30)):
        parts.append(f"wind to {s.wind_max:.0f}km/h, so nothing loose")

    if s.swing >= 10 and len(parts) < 3:
        parts.append(f"{s.swing:.0f} degrees between the coldest and warmest "
                     f"parts of the day, so layers")

    # A mild, dry, still day trips none of the clauses above and would leave the
    # verdict at five words. Say something true rather than nothing.
    if len(parts) == 1:
        if s.t_max >= 24:
            parts.append(f"topping out at {s.t_max:.0f} and no complications")
        elif s.t_max <= 8:
            parts.append(f"cold all day, {s.t_min:.0f} to {s.t_max:.0f}, "
                         f"and dry with it")
        else:
            parts.append(f"{s.t_min:.0f} to {s.t_max:.0f}, dry, and nothing "
                         f"the day intends to do about it")

    sentence = ". ".join(p[0].upper() + p[1:] for p in parts[:1])
    rest = ", ".join(parts[1:])
    return f"{sentence}. {rest[0].upper() + rest[1:]}." if rest else f"{sentence}."


def _stale_note(fc: openmeteo.Forecast) -> str | None:
    if not fc.stale:
        return None
    return f"Forecast is stale &mdash; last good reading {fc.stale_from}"


# --------------------------------------------------------------------------
# slots


@register
class WeatherVerdict(Slot):
    spec = SlotSpec(id=2, name="Weather verdict", tier="spine", paper_mm=15,
                    needs_network=True, needs_narrator=True)

    def fetch(self, ctx: Context) -> SlotResult:
        return self._present(forecast(ctx))

    def fixture(self, ctx: Context) -> SlotResult:
        return self._present(sample_forecast(ctx))

    @staticmethod
    def _present(fc: openmeteo.Forecast) -> SlotResult:
        s = signals(fc.today)
        return SlotResult(
            head="Weather",
            body=compose_verdict(s),
            fine=_stale_note(fc),
            brief={
                "place": fc.place,
                "high_c": round(s.t_max, 1), "low_c": round(s.t_min, 1),
                "feels_low_c": round(s.feels_min, 1),
                "feels_high_c": round(s.feels_max, 1),
                "rain_windows": [str(w) for w in s.rain],
                "rain_peak_pct": round(max((w.peak for w in s.rain), default=0)),
                "precip_mm": round(s.precip_mm, 1),
                "uv_max": round(s.uv_max, 1),
                "wind_max_kmh": round(s.wind_max),
                "stale": fc.stale,
                "instruction": "Say what today actually requires, in voice, in "
                               "one or two sentences. Range widely - never "
                               "reduce it to whether a jacket is needed. Do not "
                               "invent weather that is not in these figures. "
                               "The high and the low are printed as large "
                               "figures directly beneath your text, so do NOT "
                               "state either temperature - say what they mean "
                               "for the day instead.",
            },
        )


@register
class WeatherChart(Slot):
    spec = SlotSpec(id=3, name="24h temp and rain chart", tier="spine",
                    paper_mm=30, needs_network=True)

    def fetch(self, ctx: Context) -> SlotResult:
        return self._present(forecast(ctx))

    def fixture(self, ctx: Context) -> SlotResult:
        return self._present(sample_forecast(ctx))

    @staticmethod
    def _present(fc: openmeteo.Forecast) -> SlotResult:
        day = fc.today
        return SlotResult(
            head="Today, hour by hour",
            # chart.py wants probability as 0-1; Open-Meteo gives 0-100.
            body=temp_rain_svg(day.temp, [p / 100 for p in day.rain_prob]),
            # The forecast itself, for the persona's weather layout to draw
            # (`render/weather_layouts.py`). `extra` and not `brief`: the
            # narrator has no business with twenty-four hourly figures, and the
            # body above is the fallback for a persona with no layout of its own.
            extra={"forecast": fc},
        )


@register
class WeatherDelta(Slot):
    spec = SlotSpec(id=4, name="Delta vs yesterday", tier="spine", paper_mm=5,
                    needs_network=True)

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._present(forecast(ctx))

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._present(sample_forecast(ctx))

    @staticmethod
    def _present(fc: openmeteo.Forecast) -> SlotResult | None:
        if fc.yesterday is None:
            return None  # no comparison to make; not a failure
        delta = fc.today.t_max - fc.yesterday.t_max
        rounded = round(delta)
        if abs(rounded) < 1:
            text = "About the same as yesterday"
        else:
            word = "warmer" if rounded > 0 else "cooler"
            plural = "" if abs(rounded) == 1 else "s"
            text = f"{abs(rounded)} degree{plural} {word} than yesterday"
        return SlotResult(
            head="Against yesterday",
            body=text,
            brief={"delta_c": round(delta, 1),
                   "yesterday_high_c": round(fc.yesterday.t_max, 1)},
        )


@register
class SunTimes(Slot):
    spec = SlotSpec(id=5, name="Sunrise, sunset and daylight delta",
                    tier="spine", paper_mm=10, needs_network=True)

    @staticmethod
    def _hms(seconds: float) -> str:
        seconds = int(abs(seconds))
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"

    def fetch(self, ctx: Context) -> SlotResult:
        return self._present(forecast(ctx))

    def fixture(self, ctx: Context) -> SlotResult:
        return self._present(sample_forecast(ctx))

    @classmethod
    def _present(cls, fc: openmeteo.Forecast) -> SlotResult:
        today = fc.today
        parts = [f"Sunrise {today.sunrise:%H:%M}",
                 f"sunset {today.sunset:%H:%M}"]
        daylight = cls._hms(today.daylight)

        delta_txt = ""
        brief = {"sunrise": f"{today.sunrise:%H:%M}",
                 "sunset": f"{today.sunset:%H:%M}",
                 "daylight": daylight}
        if fc.yesterday is not None:
            change = today.daylight - fc.yesterday.daylight
            sign = "+" if change >= 0 else "-"
            delta_txt = f" ({sign}{cls._hms(change)})"
            brief["daylight_change_s"] = round(change)

        return SlotResult(
            head="Light",
            body=", ".join(parts),
            fine=f"{daylight} of daylight{delta_txt}",
            brief=brief,
        )
