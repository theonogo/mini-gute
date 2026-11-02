"""Slots 35, 36 and 38 - the sky tonight.

  * **35 ISS pass times** - when the station crosses tonight, and where to look.
  * **36 visible planets tonight** - what is up there and roughly where.
  * **38 star chart** - a real rendered chart of tonight's sky.

All three read `sources/sky.py`, which computes positions locally with PyEphem,
so planets and stars need no network and cannot go stale. Only the ISS reaches
out, for its orbital elements, and caches them.

**Nothing up is not a failure.** On plenty of evenings no planet clears the
horizon murk and no ISS pass happens in darkness. Those slots return `None`
rather than an empty section: "no planets visible tonight" is true and is also a
waste of 20mm, and the catalogue is explicit that a slot with nothing to say
should simply not appear.

**These are facts, so they are verbatim.** A pass time, an altitude, a compass
direction - a persona rephrasing "78 degrees, west to east" is one paraphrase
from sending someone to look at the wrong part of the sky. The narrator names
the section and writes nothing into it.
"""

from __future__ import annotations

import math

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


# --- 35 ------------------------------------------------------------------
@register
class IssPasses(Slot):
    spec = SlotSpec(id=35, name="ISS pass times", tier="rare", paper_mm=26,
                    needs_network=True, needs_narrator=True)

    def _result(self, ctx: Context, passes) -> SlotResult | None:
        if not passes:
            return None
        rows = []
        for p in passes:
            # Height in words as well as degrees. 78 degrees means nothing to
            # most people; "nearly overhead" tells them to look straight up.
            height = ("nearly overhead" if p.max_altitude >= 70 else
                      "high" if p.max_altitude >= 45 else
                      "low" if p.max_altitude < 25 else "halfway up")
            rows.append(
                f'<div class="iss-row"><span class="iss-time">'
                f'{p.start:%a %H:%M}</span><span>{p.minutes} min, '
                f'{height} ({p.max_altitude:.0f}&deg;), from the '
                f'{p.rise_direction} towards the {p.set_direction}</span></div>')
        return SlotResult(
            head="The Station",
            body=_ISS_CSS + "".join(rows),
            fine="Look for a steady light that does not blink, moving faster "
                 "than a plane. It fades out when it enters Earth's shadow.",
            brief={"verbatim": True,
                   "next_pass": f"{passes[0].start:%A %H:%M}",
                   "instruction": "Name this section in voice. The pass times "
                                  "are facts and print exactly as they are."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        from sources.sky import visible_passes
        return self._result(ctx, visible_passes(ctx.date, ctx.store,
                                                ctx.offline))

    def fixture(self, ctx: Context) -> SlotResult | None:
        """Offline: cached elements if there are any, otherwise nothing.

        Deliberately no bundled element set. The ISS orbit decays and is
        re-measured constantly, so a TLE shipped in the repo would be months
        stale within a season - and `--offline` really prints, so a stale set
        would put a confident, wrong pass time on paper. No pass shown is true;
        a wrong pass time is not.
        """
        from sources.http import SourceUnavailable
        from sources.sky import visible_passes
        try:
            return self._result(ctx, visible_passes(ctx.date, ctx.store,
                                                    offline=True))
        except SourceUnavailable:
            return None


_ISS_CSS = """
<style>
/* A timetable, so the time leads and is set apart - it is the one thing you
   need to remember at 21:10 when you go outside. */
.iss-row  { display: grid; grid-template-columns: 5.2em 1fr; gap: 10px;
            margin: 3px 0; align-items: baseline; }
.iss-time { font-family: var(--font-mono); font-weight: 700;
            border: 2px solid #000; padding: 1px 4px; text-align: center; }
</style>
"""


# --- 36 ------------------------------------------------------------------
@register
class VisiblePlanets(Slot):
    spec = SlotSpec(id=36, name="Visible planets tonight", tier="rare",
                    paper_mm=24, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        from sources.sky import moon_tonight, planets_tonight

        planets = planets_tonight(ctx.date)
        if not planets:
            return None
        moon = moon_tonight(ctx.date)

        rows = "".join(
            f'<div class="planet-row"><span class="planet-name">{p.name}</span>'
            f'<span class="leader"></span>'
            f'<span>{p.direction}, {p.altitude:.0f}&deg; up</span></div>'
            for p in planets)
        fine = "An hour after sunset. Brightest first."
        if moon:
            fine += f" The Moon is up too, in the {moon.direction}."
        return SlotResult(
            head="Planets Tonight",
            body=_PLANET_CSS + rows,
            fine=fine,
            brief={"verbatim": True,
                   "planets": [p.name for p in planets],
                   "instruction": "Name this section in voice. The positions are "
                                  "facts and print exactly as they are."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)       # pure arithmetic; no network to avoid


_PLANET_CSS = """
<style>
.planet-row  { display: flex; align-items: baseline; gap: 7px; margin: 2px 0; }
.planet-name { font-weight: var(--bold); letter-spacing: 0.04em; }
</style>
"""


# --- 38 ------------------------------------------------------------------
CHART_R = 225             # the horizon circle, in px: 450px across, ~56mm
CHART_PAD = 30            # room for the compass letters outside the circle
LABELLED = 7              # brightest stars named on the chart


def project(altitude: float, azimuth: float, r: float = CHART_R) -> tuple[float, float]:
    """Sky position to chart position.

    Azimuthal equidistant: the zenith at the centre, the horizon at the rim,
    distance from centre proportional to distance from overhead. North is at
    the top and **east is on the LEFT** - a sky chart is held above your head
    and read looking up, so it is the mirror of a map. Get this backwards and
    the chart is exactly right and useless, because every constellation is
    reversed against the real sky.
    """
    c = CHART_R + CHART_PAD
    dist = r * (90 - altitude) / 90
    a = math.radians(azimuth)
    return c - dist * math.sin(a), c - dist * math.cos(a)


def dot_radius(magnitude: float) -> float:
    # Brighter is bigger, on a scale that keeps the faintest still a printable
    # dot. Below about 1.5px a dot vanishes at the page threshold.
    return max(1.8, min(7.0, 5.0 - 1.15 * magnitude))


def chart_svg(stars, planets, moon) -> str:
    size = 2 * (CHART_R + CHART_PAD)
    c = CHART_R + CHART_PAD
    p = [f'<rect width="{size}" height="{size}" fill="#fff"/>',
         f'<circle cx="{c}" cy="{c}" r="{CHART_R}" fill="none" stroke="#000" '
         f'stroke-width="3"/>',
         # Altitude rings at 30 and 60 degrees, as dashes so they read as
         # scaffolding rather than as part of the sky.
         *[f'<circle cx="{c}" cy="{c}" r="{CHART_R * (90 - a) / 90:.1f}" '
           f'fill="none" stroke="#000" stroke-width="1" '
           f'stroke-dasharray="2 6"/>' for a in (30, 60)]]

    for label, az in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        x, y = project(0, az, CHART_R + 17)
        p.append(f'<text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" '
                 f'style="font-family:var(--font-mono);font-size:15px;'
                 f'font-weight:700" fill="#000">{label}</text>')

    for i, s in enumerate(stars):
        x, y = project(s.altitude, s.azimuth)
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" '
                 f'r="{dot_radius(s.magnitude):.1f}" fill="#000"/>')
        if i < LABELLED:
            p.append(f'<text x="{x + 8:.1f}" y="{y + 4:.1f}" '
                     f'style="font-family:var(--font-mono);font-size:12px" '
                     f'fill="#000">{s.name}</text>')

    # Planets and the Moon are drawn as ringed marks, so they cannot be mistaken
    # for bright stars - which is the single most common confusion looking up.
    for body in planets + ([moon] if moon else []):
        x, y = project(body.altitude, body.azimuth)
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#fff" '
                 f'stroke="#000" stroke-width="2.5"/>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="#000"/>')
        p.append(f'<text x="{x + 11:.1f}" y="{y + 4:.1f}" '
                 f'style="font-family:var(--font-mono);font-size:13px;'
                 f'font-weight:700" fill="#000">{body.name}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
            f'height="{size}" viewBox="0 0 {size} {size}">'
            + "".join(p) + "</svg>")


@register
class StarChart(Slot):
    spec = SlotSpec(id=38, name="Star chart", tier="rare", paper_mm=82,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        from sources.sky import moon_tonight, planets_tonight, stars_tonight

        stars = stars_tonight(ctx.date)
        if len(stars) < 5:
            return None              # overcast polar noon; nothing to chart
        planets = planets_tonight(ctx.date)
        moon = moon_tonight(ctx.date)
        return SlotResult(
            head="Tonight's Sky",
            body=chart_svg(stars, planets, moon),
            fine="Hold it above your head, top to the north. East is on the left "
                 "because you are looking up. Ringed marks are planets.",
            brief={"verbatim": True,
                   "brightest": [s.name for s in stars[:5]],
                   "instruction": "Name this section in voice. The chart is a "
                                  "drawing of the real sky tonight and prints as "
                                  "it is; do not describe it."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)
