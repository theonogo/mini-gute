"""Slot 43 - Year-percent progress bar.

Local arithmetic, no network, cannot fail. The whole slot is one number, so the
work is entirely in making that number land: a bar you can read at a glance
beats a percentage you have to think about.

Two rendering notes that generalise to any bar on this printer:

  * The fill is a solid black rectangle, not a gradient and not a tint. Anything
    between black and white is a grey, and greys do not survive the page
    threshold - they resolve to pure white and the bar prints empty.
  * Month ticks sit *inside* the bar as white notches through the filled part
    and black notches through the empty part. Drawing them over the top in a
    lighter ink would be the obvious approach and would vanish for the same
    reason.
"""

from __future__ import annotations

from datetime import date as Date

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

BAR_W = 540          # 576 less a comfortable inset; the page has no gutters
BAR_H = 26
STROKE = 3


def year_fraction(d: Date) -> tuple[int, int, float]:
    """(days elapsed, days in year, fraction elapsed 0-1).

    Counts the day itself as elapsed, so 31 December reads 100% rather than
    99.7% - "the year is 99.7% over" is technically true and reads as a bug.
    """
    start = Date(d.year, 1, 1)
    total = (Date(d.year + 1, 1, 1) - start).days
    elapsed = (d - start).days + 1
    return elapsed, total, elapsed / total


def bar_svg(fraction: float) -> str:
    inner_w = BAR_W - 2 * STROKE
    fill_w = round(inner_w * fraction)

    ticks = []
    for month in range(2, 13):
        # Month boundaries as a fraction of the year, drawn in whichever ink
        # contrasts with the ground they land on.
        at = (Date(2001, month, 1) - Date(2001, 1, 1)).days / 365
        x = STROKE + at * inner_w
        colour = "#fff" if x <= STROKE + fill_w else "#000"
        ticks.append(f'<rect x="{x:.1f}" y="{BAR_H - 9}" width="1.5" height="6" '
                     f'fill="{colour}"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{BAR_W}" '
        f'height="{BAR_H}" viewBox="0 0 {BAR_W} {BAR_H}">'
        f'<rect x="{STROKE / 2}" y="{STROKE / 2}" width="{BAR_W - STROKE}" '
        f'height="{BAR_H - STROKE}" fill="#fff" stroke="#000" '
        f'stroke-width="{STROKE}"/>'
        f'<rect x="{STROKE}" y="{STROKE}" width="{fill_w}" '
        f'height="{BAR_H - 2 * STROKE}" fill="#000"/>'
        + "".join(ticks) +
        '</svg>')


@register
class YearProgress(Slot):
    spec = SlotSpec(id=43, name="Year-percent progress bar", tier="uncommon",
                    paper_mm=20, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        elapsed, total, fraction = year_fraction(ctx.date)
        remaining = total - elapsed
        return SlotResult(
            head="Year Progress",
            # Verbatim because the body is an SVG, not prose. The narrator has
            # nothing useful to do to a rectangle, and a body field it can write
            # into is a body field it will eventually overwrite with a sentence.
            body=bar_svg(fraction),
            fine=f"{fraction * 100:.1f}% of {ctx.date.year} elapsed "
                 f"&middot; {remaining} day{'s' if remaining != 1 else ''} left",
            brief={"verbatim": True,
                   "year": ctx.date.year,
                   "percent_elapsed": round(fraction * 100, 1),
                   "days_elapsed": elapsed,
                   "days_remaining": remaining,
                   "instruction": "Name this section in voice. The bar speaks "
                                  "for itself."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
