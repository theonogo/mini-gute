"""Slot 37 - Moon phase.

Reference implementation for a LOCAL DATA slot: pure arithmetic, no network,
no API key, no failure mode. Deterministic for a given date, so `--date` gives
the same moon every time.

SLOTS.md says "keep it tiny", so the disc is 48px - about 6mm.
Drawn as SVG rather than a bitmap because it is a hard-edged shape: it
thresholds cleanly and needs no dithering.
"""

from __future__ import annotations

import math
from datetime import date as Date

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Reference new moon: 2000-01-06 18:14 UTC, and the mean synodic month.
_EPOCH_JD = 2451550.26
_SYNODIC = 29.530588853

_NAMES = [
    (0.02, "New Moon"), (0.24, "Waxing Crescent"), (0.28, "First Quarter"),
    (0.48, "Waxing Gibbous"), (0.52, "Full Moon"), (0.72, "Waning Gibbous"),
    (0.78, "Last Quarter"), (0.98, "Waning Crescent"), (1.01, "New Moon"),
]


def julian_day(d: Date) -> float:
    y, m = d.year, d.month
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d.day + b - 1524.5)


def phase(d: Date) -> tuple[float, float, str]:
    """(cycle position 0-1, illuminated fraction 0-1, name)."""
    p = ((julian_day(d) - _EPOCH_JD) % _SYNODIC) / _SYNODIC
    illum = (1 - math.cos(2 * math.pi * p)) / 2
    name = next(n for threshold, n in _NAMES if p < threshold)
    return p, illum, name


def moon_svg(p: float, size: int = 64) -> str:
    """A 1-bit moon: black disc, white lit region, black limb.

    The terminator is an elliptical arc whose horizontal radius shrinks to zero
    at the quarters. Which side it bulges towards flips at each quarter, which
    is what the sweep flag encodes - get it wrong and a crescent renders as a
    gibbous.
    """
    r = size / 2 - 1.5
    c = size / 2
    rx = abs(math.cos(2 * math.pi * p)) * r
    waxing = p < 0.5
    # Bulge away from the lit limb before the quarter, towards it after.
    bulge_out = (p < 0.25) or (p > 0.75)
    sweep = (0 if bulge_out else 1) if waxing else (1 if bulge_out else 0)
    limb_sweep = 1 if waxing else 0

    lit = (f'M {c},{c - r} '
           f'A {r},{r} 0 0 {limb_sweep} {c},{c + r} '
           f'A {rx:.2f},{r} 0 0 {sweep} {c},{c - r} Z')

    # The dark side is hatched, not filled. At 4% illumination a solid disc
    # prints as a black blob with its outline invisible against it - correct,
    # and unreadable. Hatching keeps the disc legible as a disc at every phase
    # while still reading much darker than the lit side.
    return (f'<svg class="moon" xmlns="http://www.w3.org/2000/svg" '
            f'width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<defs><pattern id="moonshade" width="3" height="3" '
            f'patternUnits="userSpaceOnUse">'
            f'<path d="M-1,1 l2,-2 M0,3 l3,-3 M2,4 l2,-2" stroke="#000" '
            f'stroke-width="1"/></pattern></defs>'
            f'<circle cx="{c}" cy="{c}" r="{r}" fill="url(#moonshade)"/>'
            f'<path d="{lit}" fill="#fff"/>'
            f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="#000" '
            f'stroke-width="2"/></svg>')


@register
class MoonPhase(Slot):
    spec = SlotSpec(
        id=37, name="Moon phase", tier="common", paper_mm=24)

    def _result(self, d: Date) -> SlotResult:
        p, illum, name = phase(d)
        return SlotResult(
            head="Moon",
            body=moon_svg(p),
            fine=f"{name} &middot; {illum * 100:.0f}% illuminated",
            brief={"phase": name, "illuminated_pct": round(illum * 100)},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx.date)

    def fixture(self, ctx: Context) -> SlotResult:
        # No network to avoid, so the fixture is simply the real thing.
        return self._result(ctx.date)
