"""The 24h weather chart, as inline SVG.

SVG rather than a bitmap because it is line art: crisp edges threshold cleanly
and there is nothing to dither. Keeping it out of the image pipeline also means
it inherits the theme's colours and can be restyled per persona.

Half-pixel offsets on strokes are deliberate - a 1px line on a whole coordinate
straddles two pixels and thresholds to either two grey rows or none.

**Never use opacity or grey fills.** The page threshold is binary: anything
lighter than its cut becomes pure white and disappears - bars at opacity 0.25
print as nothing at all. The rain bars are a hatch pattern for exactly this
reason.
"""

from printer.base import WIDTH_DOTS
from render.fonts import DEFAULT_SIZES


def temp_rain_svg(temps: list[float], rain: list[float], *,
                  width: int = WIDTH_DOTS, height: int = 104,
                  pad: int = 6, hours: tuple[int, ...] = (6, 9, 12, 15, 18, 21),
                  label_px: int = DEFAULT_SIZES[2]) -> str:
    """Temperature curve over precipitation-probability bars.

    `temps` and `rain` are 24 hourly values; rain is 0-1.

    `label_px` defaults to the house tiny tier, not the 12px hardware floor -
    chart labels are read alongside body copy and look like an oversight
    any smaller. Pass the persona's own tiny size if it differs.
    """
    inner_w = width - pad * 2
    plot_h = height - (label_px + 6)  # strip for hour labels

    lo, hi = min(temps), max(temps)
    span = max(1.0, hi - lo)

    def x(i: int) -> float:
        return pad + inner_w * i / (len(temps) - 1)

    def y(t: float) -> float:
        return 2 + (plot_h - 4) * (1 - (t - lo) / span)

    bars = []
    bar_w = inner_w / len(rain)
    for i, p in enumerate(rain):
        if p <= 0.02:
            continue
        h = max(1.0, plot_h * min(1.0, p))
        bars.append(
            f'<rect x="{pad + i * bar_w:.1f}" y="{plot_h - h:.1f}" '
            f'width="{bar_w - 0.6:.1f}" height="{h:.1f}" '
            f'fill="url(#rainhatch)"/>')

    pts = " ".join(f"{x(i):.1f},{y(t):.1f}" for i, t in enumerate(temps))

    ticks = []
    for h in hours:
        tx = x(h)
        ticks.append(f'<line x1="{tx:.1f}" y1="{plot_h}" x2="{tx:.1f}" '
                     f'y2="{plot_h + 3}" stroke="#000" stroke-width="1"/>')
        ticks.append(f'<text x="{tx:.1f}" y="{height - 2}" '
                     f'font-size="{label_px}" font-family="inherit" '
                     f'text-anchor="middle" fill="#000">{h:02d}</text>')

    return (
        f'<svg class="chart" xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<defs><pattern id="rainhatch" width="4" height="4" '
        f'patternUnits="userSpaceOnUse">'
        f'<path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" stroke="#000" '
        f'stroke-width="1"/></pattern></defs>'
        f'{"".join(bars)}'
        f'<polyline points="{pts}" fill="none" stroke="#000" stroke-width="2" '
        f'stroke-linejoin="round"/>'
        f'<line x1="{pad}" y1="{plot_h + 0.5}" x2="{width - pad}" '
        f'y2="{plot_h + 0.5}" stroke="#000" stroke-width="1"/>'
        f'{"".join(ticks)}'
        f'</svg>'
    )
