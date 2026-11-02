"""Five ways of drawing the same day. One per persona.

The weather is the one section that prints every morning, so it is the section
a persona is recognised by before a word is read. The facts are identical in all
five - slots 2, 3, 4 and 5 compute them and nothing here decides anything - but
the ops officer gets a chart, the oracle gets a dial, and the diner gets four
cards you can read across a counter.

    chart      the hourly curve, rain rising from the floor, night in the axis
    parts      morning / afternoon / evening / night, four cards
    threedays  yesterday, today, tomorrow on one temperature axis
    dial       a 24-hour clock: ring is warmth, spokes are rain
    counted    the day as tallies - hours of rain, hours of clear sky

A persona picks one with `weather = "dial"` in `personas.toml`; absent, it gets
the chart. An unknown name gets the chart too, because a typo in a persona file
must not cost the morning its weather.

**Drawn from the forecast, never from the copy.** The layouts read the hourly
series out of `SlotResult.extra`, so they can show rain by hour or tomorrow's
range without the narrator ever seeing those numbers - and they cannot
contradict the verdict, because they do not write any words of their own.

**1-bit rules apply here as everywhere**: no greys, no opacity. Every shade is a
pattern - dots, hatch, solid - and every weight comes from `var(--bold)`.
"""

from __future__ import annotations

import math
from typing import Any

from sources import openmeteo as om

DEFAULT = "chart"

# Rain is marked where it is close to a certainty rather than wherever it is
# possible. A 20% chance shaded on the page reads as "it will rain".
SURE = 60

PATTERNS = (
    '<defs>'
    '<pattern id="wxdots" width="8" height="8" patternUnits="userSpaceOnUse">'
    '<circle cx="2" cy="2" r="1.7" fill="#000"/></pattern>'
    '<pattern id="wxhatch" width="8" height="8" patternUnits="userSpaceOnUse" '
    'patternTransform="rotate(45)"><rect width="3" height="8" fill="#000"/></pattern>'
    '<pattern id="wxrain" width="4" height="4" patternUnits="userSpaceOnUse">'
    '<path d="M-1,1 l2,-2 M0,4 l4,-4 M3,5 l2,-2" stroke="#000" stroke-width="1"/>'
    '</pattern></defs>'
)

CSS = """<style>
.wx { margin: 0; }
.wx-verdict { padding: 0 var(--pad); margin-bottom: 6px; }
.wx-meta { display:flex; justify-content:space-between; padding: 4px var(--pad) 2px;
           font-size: var(--size-small); }
.wx-svg { display:block; margin: 0 auto; }
.wx-figs { display:flex; border:3px solid #000; margin: 0 var(--pad); }
.wx-fig { padding:6px 14px 8px; display:flex; flex-direction:column;
          justify-content:center; }
.wx-fig + .wx-fig { border-left:3px solid #000; }
.wx-k { font-size:12px; letter-spacing:.26em; font-weight:var(--bold); }
.wx-v { font-size:52px; line-height:.9; font-weight:var(--bold);
        font-family: var(--font-display); letter-spacing:-.02em; }
.wx-sky { flex:1; flex-direction:row; align-items:center; justify-content:center;
          gap:12px; padding:4px 10px; }
.wx-sky .wx-ic { display:flex; align-items:center; }
.wx-w { font-size:26px; }
/* parts of the day */
.wx-head { display:flex; justify-content:space-between; align-items:baseline;
           border-bottom:4px solid #000; padding:0 var(--pad) 4px; }
.wx-head .wx-hk { letter-spacing:.34em; font-size:15px; }
.wx-head .wx-hv { font-size:38px; line-height:1; font-weight:var(--bold);
              font-family: var(--font-display); }
.wx-head i { font-style:normal; padding:0 4px; font-size:26px; }
.wx-cards { display:grid; grid-template-columns:1fr 1fr; margin: 0 var(--pad);
            border-left:3px solid #000; border-right:3px solid #000;
            border-bottom:3px solid #000; }
.wx-card { padding:6px 9px 7px; }
.wx-card:nth-child(odd) { border-right:3px solid #000; }
.wx-card:nth-child(1), .wx-card:nth-child(2) { border-bottom:3px solid #000; }
.wx-lbl { display:flex; justify-content:space-between; align-items:baseline;
          border-bottom:2px solid #000; padding-bottom:3px; }
.wx-nm { letter-spacing:.16em; font-size:13px; font-weight:var(--bold); }
.wx-hrs { font-family:var(--font-mono); font-size:13px; }
.wx-mid { display:flex; align-items:center; justify-content:space-between;
          gap:4px; margin:3px 0 2px; }
.wx-t { font-size:31px; line-height:1; font-weight:var(--bold);
        font-family: var(--font-display); }
.wx-ft { display:flex; justify-content:space-between; align-items:center;
         font-size:14px; }
.wx-stamp { display:inline-flex; align-items:center; gap:3px; font-size:13px;
            font-family:var(--font-mono); }
/* The advice is the last row of the card table, not a line floating under
   it: the same 3px rule, sharing the grid's bottom edge. The label is reversed
   out, so it carries .inv and the weight comes with it (CLAUDE.md 6). */
.wx-take { display:flex; align-items:stretch; margin: 0 var(--pad);
           border:3px solid #000; border-top:0; }
.wx-tk { font-size:16px; letter-spacing:.22em; display:flex; align-items:center;
         padding:7px 8px 7px 12px; }
.wx-tv { flex:1; display:flex; align-items:center; gap:9px; font-size:20px;
         line-height:1.15; padding:5px 10px; }
.wx-tr { display:flex; align-items:center; white-space:nowrap;
         font-family:var(--font-mono); font-size:15px; padding:5px 11px 5px 0; }
.wx-um { flex:0 0 auto; }
/* three days */
.wx-day { display:flex; align-items:center; gap:8px; padding:5px var(--pad);
          border-bottom:2px solid #000; }
.wx-day.now { border-top:3px solid #000; border-bottom:3px solid #000; }
.wx-day .wx-ico { flex:0 0 40px; }
.wx-day .wx-txt { flex:0 0 146px; }
.wx-day .wx-nm { letter-spacing:.12em; font-size:14px; font-weight:var(--bold); }
.wx-day .wx-cond { font-size: var(--size-tiny); line-height:1.25; }
.wx-day .wx-bar { flex:1; }
.wx-line { margin:8px 0 2px; padding: 0 var(--pad); font-size:18px; }
/* dial */
.wx-row { display:flex; align-items:center; gap:4px; padding: 0 var(--pad); }
.wx-side { flex:1; }
.wx-side .wx-skyline { display:flex; align-items:center; gap:6px;
                border-bottom:2px solid #000; padding-bottom:4px; }
.wx-side .wx-skyline .wx-word { font-size:26px; }
.wx-times div { border-bottom:1px dotted #000; padding:3px 0; font-size:17px; }
.wx-times b { font-size:21px; font-weight:var(--bold); }
.wx-keys { margin-top:8px; }
.wx-key { display:flex; align-items:center; gap:11px; font-size:24px; padding:4px 0; }
.wx-sw { width:29px; height:29px; border:2px solid #000; display:inline-block; }
/* counted */
.wx-ttl { display:flex; justify-content:space-between; align-items:center;
          letter-spacing:.3em; font-size:16px; border-bottom:3px solid #000;
          padding: 0 var(--pad) 4px; margin: 0 0 4px; }
.wx-ttl .wx-skyline { display:flex; align-items:center; gap:7px; letter-spacing:0;
               font-size:21px; }
.wx-unit { margin-top:9px; padding: 0 var(--pad); }
.wx-unit .wx-lab { display:flex; align-items:baseline; gap:8px; margin-bottom:3px; }
.wx-unit .wx-lab b { font-size:26px; font-weight:var(--bold);
                  font-family: var(--font-display); }
.wx-unit .wx-lab span { font-size:15px; }
.wx-note { border-top:2px solid #000; margin:10px var(--pad) 0; padding-top:5px;
           font-size: var(--size-small); }
</style>"""

WORD = {"clear": "clear", "part": "bright", "cloud": "grey", "fog": "fog",
        "drizzle": "drizzle", "rain": "rain", "snow": "snow", "storm": "storms"}
SEVERITY = ("clear", "part", "cloud", "fog", "drizzle", "rain", "snow", "storm")
# Conditions whose own word already says water, so a card footer that labelled
# the figure "rain" after them would read "rain - rain 20%".
WET = ("drizzle", "rain", "snow", "storm")


# --------------------------------------------------------------------------
# drawing


def glyph(kind: str, size: int = 44, night: bool = False) -> str:
    """A condition mark, drawn. Line art at this size, never a font glyph."""
    s = size / 46

    def S(v: float) -> str:
        return f"{v * s:.1f}"

    sun = (f'<circle cx="{S(16)}" cy="{S(15)}" r="{S(8)}" fill="none" stroke="#000" '
           f'stroke-width="{S(3)}"/>'
           + "".join(f'<line x1="{S(16 + 12 * math.cos(a))}" y1="{S(15 + 12 * math.sin(a))}"'
                     f' x2="{S(16 + 16.5 * math.cos(a))}" y2="{S(15 + 16.5 * math.sin(a))}"'
                     f' stroke="#000" stroke-width="{S(3)}"/>'
                     for a in [i * math.pi / 4 for i in range(8)]))
    moon = (f'<path d="M{S(23)},{S(6)} a{S(11)},{S(11)} 0 1,0 {S(2)},{S(19)}'
            f' a{S(13)},{S(13)} 0 1,1 {S(-2)},{S(-19)} z" fill="#000"/>')
    cloud = (f'<path d="M{S(11)},{S(33)} a{S(8)},{S(8)} 0 0,1 {S(1)},{S(-15)}'
             f' a{S(10)},{S(10)} 0 0,1 {S(19)},{S(2)}'
             f' a{S(7)},{S(7)} 0 0,1 {S(1)},{S(13)} z"'
             f' fill="{"#000" if kind in ("rain", "storm", "drizzle", "snow") else "none"}"'
             f' stroke="#000" stroke-width="{S(3)}" stroke-linejoin="round"/>')
    drops = "".join(f'<line x1="{S(12 + i * 7)}" y1="{S(36)}" x2="{S(9 + i * 7)}" '
                    f'y2="{S(44)}" stroke="#000" stroke-width="{S(3)}"/>' for i in range(3))
    dots = "".join(f'<circle cx="{S(12 + i * 7)}" cy="{S(40)}" r="{S(1.8)}" fill="#000"/>'
                   for i in range(3))
    flakes = "".join(f'<path d="M{S(9 + i * 7)},{S(37)} v{S(7)} M{S(6 + i * 7)},{S(40.5)} '
                     f'h{S(6)} M{S(6.8 + i * 7)},{S(38.3)} l{S(4.4)},{S(4.4)} '
                     f'M{S(11.2 + i * 7)},{S(38.3)} l{S(-4.4)},{S(4.4)}" '
                     f'stroke="#000" stroke-width="{S(1.6)}"/>' for i in range(3))
    bolt = (f'<path d="M{S(22)},{S(35)} l{S(-6)},{S(9)} l{S(5)},0 l{S(-3)},{S(7)}'
            f' l{S(10)},{S(-11)} l{S(-5)},0 l{S(4)},{S(-5)} z" fill="#000"/>')
    fogbars = "".join(f'<line x1="{S(6)}" y1="{S(20 + i * 7)}" x2="{S(40)}" '
                      f'y2="{S(20 + i * 7)}" stroke="#000" stroke-width="{S(3)}"/>'
                      for i in range(3))
    body = {"clear": moon if night else sun,
            "part": (moon if night else sun) + cloud,
            "cloud": cloud, "fog": fogbars, "drizzle": cloud + dots,
            "rain": cloud + drops, "snow": cloud + flakes,
            "storm": cloud + bolt}.get(kind, cloud)
    return (f'<svg class="wx-glyph" width="{size}" height="{size * 1.12:.0f}" '
            f'viewBox="0 0 {size} {size * 1.12:.0f}">{body}</svg>')


def sky_over(day, hours) -> str:
    """The condition that best describes a stretch: the worst of it, not the
    average. A morning with one wet hour in it is a morning you take a coat."""
    codes = [day.code[h] for h in hours]
    worst = max(codes, key=lambda c: SEVERITY.index(om.condition(c)))
    return om.condition(worst)


def umbrella(size: int = 33) -> str:
    """A drawn umbrella for the TAKE bar.

    Strokes only, no `<pattern>` fill - see `striped()` for why a pattern id is
    not safe on a page carrying several of these fragments. The scalloped hem
    is what makes it read as an umbrella rather than an arch at this size.
    """
    hem = " ".join(["q-2.6,-2.9 -5.2,0"] * 4)
    return (f'<svg class="wx-um" width="{size}" height="{size}" '
            f'viewBox="0 0 24 24">'
            f'<path d="M1.6,12.2 A10.4,10.4 0 0 1 22.4,12.2 {hem} Z" fill="none" '
            f'stroke="#000" stroke-width="2.1" stroke-linejoin="round"/>'
            f'<path d="M12,12.2 V19.4 A3,3 0 0 0 18,19.4" fill="none" '
            f'stroke="#000" stroke-width="2.1"/>'
            f'<line x1="12" y1="0.9" x2="12" y2="2.6" stroke="#000" '
            f'stroke-width="2.1"/></svg>')


def wet_hours(day, threshold: int = SURE) -> list[int]:
    return [h for h in range(24) if day.rain_prob[h] >= threshold]


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def striped(x: float, y: float, w: float, h: float, gap: int = 8,
            uid: str = "") -> str:
    """A hatched box drawn as real lines rather than a `<pattern>` fill.

    Patterns are referenced by id, and three bars on one page means three
    fragments defining the same ids. In the receipt that resolved to a solid
    black fill - every bar filled in, the figures lost behind them - while the
    same markup on a page of its own was fine. Lines cannot be mis-resolved,
    and a diagonal every 8px survives the threshold identically.
    """
    lines = []
    span = int(w + h)
    for n in range(-int(h), span, gap):
        x0 = x + n
        y0 = y + h
        x1 = x + n + h
        y1 = y
        # Clip by hand to the box, which is cheaper and surer than a clipPath.
        if x0 < x:
            y0 -= (x - x0)
            x0 = x
        if x1 > x + w:
            y1 += (x1 - (x + w))
            x1 = x + w
        if x0 >= x1 or y0 <= y1:
            continue
        lines.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" '
                     f'y2="{y1:.1f}" stroke="#000" stroke-width="3"/>')
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'fill="none" stroke="#000" stroke-width="2"/>{"".join(lines)}')


# --------------------------------------------------------------------------
# layouts


def _chart(f: dict) -> str:
    day = f["today"]
    T, RP = day.temp, day.rain_prob
    w, h = 552, 148
    pad, plot = 34, 106
    inner = w - pad - 8
    lo, hi = min(T), max(T)
    span = max(1.0, hi - lo)

    def X(i: float) -> float:
        return pad + inner * i / 23

    def Y(t: float) -> float:
        return 8 + (plot - 26) * (1 - (t - lo) / span)

    out = [PATTERNS]
    bw = inner / 24
    for i, prob in enumerate(RP):
        if prob < 5:
            continue
        height = max(1.0, (plot - 10) * prob / 100)
        out.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{plot - height:.1f}" '
                   f'width="{bw:.1f}" height="{height:.1f}" fill="url(#wxrain)"/>')

    for n, t in enumerate([lo, lo + span / 3, lo + 2 * span / 3, hi]):
        y = Y(t)
        dash = "" if n in (0, 3) else ' stroke-dasharray="2 7"'
        out.append(f'<line x1="{pad}" y1="{y:.1f}" x2="{pad + inner}" y2="{y:.1f}" '
                   f'stroke="#000" stroke-width="{2 if n in (0, 3) else 1.5}"{dash}/>')
        out.append(f'<text x="{pad - 6}" y="{y + 5:.1f}" font-size="14" text-anchor="end" '
                   f'font-family="var(--font-mono)">{t:.0f}&#176;</text>')

    pts = " ".join(f"{X(i):.1f},{Y(t):.1f}" for i, t in enumerate(T))
    out.append(f'<polyline points="{pts}" fill="none" stroke="#fff" stroke-width="9"/>')
    out.append(f'<polyline points="{pts}" fill="none" stroke="#000" stroke-width="3.5"/>')

    # Night is carried by the axis: heavy where it is dark, hairline where it
    # is light. Shading the background instead buries the curve in texture.
    sr = X(day.sunrise.hour + day.sunrise.minute / 60)
    ss = X(day.sunset.hour + day.sunset.minute / 60)
    for x0, x1, weight in ((pad, sr, 9), (sr, ss, 2), (ss, pad + inner, 9)):
        out.append(f'<line x1="{x0:.0f}" y1="{plot}" x2="{x1:.0f}" y2="{plot}" '
                   f'stroke="#000" stroke-width="{weight}"/>')
    for hour in range(0, 24, 3):
        major = hour % 6 == 0
        out.append(f'<line x1="{X(hour):.1f}" y1="{plot + 5}" x2="{X(hour):.1f}" '
                   f'y2="{plot + (13 if major else 9)}" stroke="#000" stroke-width="2"/>')
        out.append(f'<text x="{X(hour):.0f}" y="{h - 3}" font-size="{15 if major else 13}" '
                   f'text-anchor="middle" font-family="var(--font-mono)" '
                   f'font-weight="{700 if major else 400}">{hour:02d}</text>')

    sky = sky_over(day, range(6, 20))
    return f"""{CSS}<div class="wx">
  <div class="wx-verdict">{f["verdict"]}</div>
  <div class="wx-figs">
    <div class="wx-fig"><div class="wx-k">LOW</div>
      <div class="wx-v">{f["low"]}</div></div>
    <div class="wx-fig"><div class="wx-k">HIGH</div>
      <div class="wx-v">{f["high"]}</div></div>
    <div class="wx-fig wx-sky"><span class="wx-ic">{glyph(sky, 44)}</span>
      <span class="wx-w">{WORD[sky]}</span></div>
  </div>
  <div class="wx-meta"><span>{f["delta"]}</span><span>{f["feels"]}</span></div>
  <svg class="wx-svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{"".join(out)}</svg>
  <div class="wx-meta"><span>{f["sun"]}</span><span>{f["daylight"]}</span></div>
</div>"""


def _parts(f: dict) -> str:
    day = f["today"]
    T, RP = day.temp, day.rain_prob
    spans = [("MORNING", 6, 12, f"{day.sunrise:%H:%M}", True),
             ("AFTERNOON", 12, 18, "", False),
             ("EVENING", 18, 22, f"{day.sunset:%H:%M}", False),
             ("NIGHT", 22, 24, "", False)]
    cards = []
    for label, a, b, stamp, rising in spans:
        kind = sky_over(day, range(a, b))
        corner = ""
        if stamp:
            head = ('<path d="M8.5,0 l4,5 h-8 z" fill="#000"/>' if rising
                    else '<path d="M8.5,5 l4,-5 h-8 z" fill="#000"/>')
            corner = (f'<span class="wx-stamp"><svg width="17" height="15" '
                      f'viewBox="0 0 17 15">'
                      f'<circle cx="8.5" cy="11" r="4.5" fill="none" stroke="#000" '
                      f'stroke-width="2"/><line x1="0" y1="14" x2="17" y2="14" '
                      f'stroke="#000" stroke-width="2.5"/>{head}</svg>{stamp}</span>')
        elif label == "EVENING":
            corner = ""
        cards.append(
            f'<div class="wx-card"><div class="wx-lbl">'
            f'<span class="wx-nm">{label}</span>'
            f'<span class="wx-hrs">{a:02d}&ndash;{b % 24:02d}</span></div>'
            f'<div class="wx-mid">{glyph(kind, 42, label == "NIGHT")}'
            f'<div class="wx-t">{min(T[a:b]):.0f}&ndash;{max(T[a:b]):.0f}&deg;</div></div>'
            f'<div class="wx-ft"><span>{WORD[kind]} &middot; '
            f'{"" if kind in WET else "rain "}{max(RP[a:b]):.0f}%'
            f'{" chance" if kind in WET else ""}</span>{corner}</div></div>')
    # What to carry, from the hours that are actually wet rather than the day's
    # total: a 30% afternoon is not an umbrella, a 70% hour is.
    wet = wet_hours(day)
    if wet:
        take = (f'<span class="wx-tv">{umbrella()}<span>an umbrella</span></span>'
                f'<span class="wx-tr">rain {wet[0]:02d}&ndash;'
                f'{wet[-1] + 1:02d}</span>')
    else:
        take = '<span class="wx-tv">nothing you do not already have</span>'
    return f"""{CSS}<div class="wx">
  <div class="wx-verdict">{f["verdict"]}</div>
  <div class="wx-head"><span class="wx-hk">TODAY</span>
    <span class="wx-hv">{f["low"]}<i>/</i>{f["high"]}</span></div>
  <div class="wx-cards">{"".join(cards)}</div>
  <div class="wx-take"><span class="wx-tk inv">TAKE</span>{take}</div>
  <div class="wx-meta"><span>{f["sun"]}</span><span>{f["daylight"]}</span></div>
</div>"""


def _threedays(f: dict) -> str:
    days = [("YESTERDAY", f["yesterday"]), ("TODAY", f["today"]),
            ("TOMORROW", f["tomorrow"])]
    days = [(n, d) for n, d in days if d is not None]
    axis_lo = min(min(d.temp) for _, d in days) - 3
    axis_hi = max(max(d.temp) for _, d in days) + 3
    span = axis_hi - axis_lo
    w = 262
    step = 10 if span > 24 else 5
    grid = [v for v in range(int(axis_lo) + 1, int(axis_hi) + 1) if v % step == 0]

    rows = []
    for name, d in days:
        lo, hi = min(d.temp), max(d.temp)
        x0 = (lo - axis_lo) / span * w
        x1 = (hi - axis_lo) / span * w
        kind = om.condition(d.day_code)
        peak = max(d.rain_prob)
        wet = wet_hours(d)
        rain = (f"{peak:.0f}% rain, {wet[0]:02d}&ndash;{wet[-1] + 1:02d}" if wet
                else f"{peak:.0f}% rain")
        solid = name == "TODAY"
        ticks = "".join(
            f'<line x1="{(v - axis_lo) / span * w:.0f}" y1="0" '
            f'x2="{(v - axis_lo) / span * w:.0f}" y2="34" stroke="#000" '
            f'stroke-width="1" stroke-dasharray="2 6"/>' for v in grid)
        width = max(6, x1 - x0)
        shape = (f'<rect x="{x0:.0f}" y="3" width="{width:.0f}" height="28" '
                 f'fill="#000" stroke="#000" stroke-width="2"/>' if solid
                 else striped(x0, 3, width, 28))
        bar = (f'<svg width="{w + 104}" height="34" viewBox="-48 0 {w + 104} 34">'
               f'{ticks}{shape}'
               f'<text x="{x0 - 9:.0f}" y="25" font-size="19" text-anchor="end" '
               f'font-family="var(--font-mono)">{lo:.0f}&#176;</text>'
               f'<text x="{x1 + 9:.0f}" y="25" font-size="19" '
               f'font-family="var(--font-mono)">{hi:.0f}&#176;</text></svg>')
        rows.append(f'<div class="wx-day{" now" if solid else ""}">'
                    f'<div class="wx-ico">{glyph(kind, 40)}</div>'
                    f'<div class="wx-txt"><div class="wx-nm">{name}</div>'
                    f'<div class="wx-cond">{WORD[kind]}<br>{rain}</div></div>'
                    f'<div class="wx-bar">{bar}</div></div>')

    today, yesterday = f["today"], f["yesterday"]
    line = ""
    if yesterday is not None:
        delta = max(today.temp) - max(yesterday.temp)
        word = "cooler" if delta < 0 else "warmer"
        line = (f'<div class="wx-line"><b>{abs(delta):.0f}&deg; {word}</b> than '
                f'yesterday at its best, and {sum(today.precip):.1f}mm of rain '
                f'against {sum(yesterday.precip):.1f}mm.</div>')
    return f"""{CSS}<div class="wx">
  <div class="wx-verdict">{f["verdict"]}</div>
  {"".join(rows)}{line}
  <div class="wx-meta"><span>{f["sun"]}</span><span>{f["daylight"]}</span></div>
</div>"""


def _dial(f: dict) -> str:
    day = f["today"]
    T, RP = day.temp, day.rain_prob
    cx = cy = 158
    R_IN, R_OUT = 112, 136
    SPOKE_IN, SPOKE_MAX = 60, 104
    R_DAY = 146

    def pt(hour: float, radius: float) -> tuple[float, float]:
        a = math.radians(hour / 24 * 360 - 90)
        return cx + radius * math.cos(a), cy + radius * math.sin(a)

    def wedge(h0, h1, r_in, r_out, fill):
        x0, y0 = pt(h0, r_out)
        x1, y1 = pt(h1, r_out)
        x2, y2 = pt(h1, r_in)
        x3, y3 = pt(h0, r_in)
        large = 1 if (h1 - h0) > 12 else 0
        return (f'<path d="M{x0:.1f},{y0:.1f} A{r_out},{r_out} 0 {large},1 '
                f'{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f} A{r_in},{r_in} 0 {large},0 '
                f'{x3:.1f},{y3:.1f} Z" fill="{fill}" stroke="#000" stroke-width="1.5"/>')

    # Four bands across the day's own range, empty at the cold end and solid at
    # the warm one, so the ring fills up as the day warms.
    lo, hi = math.floor(min(T)), math.ceil(max(T))
    edges = [lo + (hi - lo) * i / 4 for i in range(5)]
    fills = ["none", "url(#wxdots)", "url(#wxhatch)", "#000"]

    def band(t: float) -> int:
        for i in range(4):
            if t <= edges[i + 1]:
                return i
        return 3

    sunrise_h = day.sunrise.hour + day.sunrise.minute / 60
    sunset_h = day.sunset.hour + day.sunset.minute / 60
    out = [PATTERNS]
    x0, y0 = pt(sunrise_h, R_DAY)
    x1, y1 = pt(sunset_h, R_DAY)
    large = 1 if (sunset_h - sunrise_h) > 12 else 0
    out.append(f'<path d="M{x0:.1f},{y0:.1f} A{R_DAY},{R_DAY} 0 {large},1 '
               f'{x1:.1f},{y1:.1f}" fill="none" stroke="#000" stroke-width="5"/>')
    for h in range(24):
        out.append(wedge(h, h + 1, R_IN, R_OUT, fills[band(T[h])]))
    for h in range(24):
        length = (SPOKE_MAX - SPOKE_IN) * (RP[h] / 100)
        if length < 2:
            continue
        a0, b0 = pt(h + 0.5, SPOKE_IN)
        a1, b1 = pt(h + 0.5, SPOKE_IN + length)
        out.append(f'<line x1="{a0:.1f}" y1="{b0:.1f}" x2="{a1:.1f}" y2="{b1:.1f}" '
                   f'stroke="#000" stroke-width="5"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{SPOKE_IN - 4}" fill="none" '
               f'stroke="#000" stroke-width="1.5"/>')
    for h in range(0, 24, 3):
        major = h % 6 == 0
        x0, y0 = pt(h, R_OUT + 2)
        x1, y1 = pt(h, R_DAY - (2 if major else 5))
        out.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" '
                   f'stroke="#000" stroke-width="{3 if major else 2}"/>')
        x, y = pt(h, R_DAY + (19 if major else 15))
        out.append(f'<text x="{x:.0f}" y="{y + (7 if major else 5):.0f}" '
                   f'font-size="{22 if major else 15}" text-anchor="middle" '
                   f'font-family="var(--font-mono)" '
                   f'font-weight="{700 if major else 400}">{h:02d}</text>')
    for h in (sunrise_h, sunset_h):
        x, y = pt(h, R_DAY)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#fff" '
                   f'stroke="#000" stroke-width="4"/>')

    swatches = ["#fff", "radial-gradient(#000 1.7px,#fff 1.8px) 0 0/8px 8px",
                "repeating-linear-gradient(45deg,#000 0 3px,#fff 3px 8px)", "#000"]
    key = "".join(f'<div class="wx-key"><i class="wx-sw" style="background:{bg}"></i>'
                  f'{(edges[i] + edges[i + 1]) / 2:.0f}&deg;</div>'
                  for i, bg in enumerate(swatches))
    sky = sky_over(day, range(6, 20))
    return f"""{CSS}<div class="wx">
  <div class="wx-verdict">{f["verdict"]}</div>
  <div class="wx-row">
    <svg class="wx-svg" width="344" height="330" viewBox="-28 -3 376 330">
      {"".join(out)}
      <text x="{cx}" y="{cy - 10}" font-size="36" text-anchor="middle">{f["low"]}</text>
      <line x1="{cx - 26}" y1="{cy + 3}" x2="{cx + 26}" y2="{cy + 3}" stroke="#000"
            stroke-width="2"/>
      <text x="{cx}" y="{cy + 35}" font-size="36" text-anchor="middle">{f["high"]}</text>
    </svg>
    <div class="wx-side">
      <div class="wx-skyline">{glyph(sky, 44)}<div class="wx-word">{WORD[sky]}</div></div>
      <div class="wx-times"><div><b>{day.sunrise:%H:%M}</b> light</div>
        <div><b>{day.sunset:%H:%M}</b> dark</div></div>
      <div class="wx-keys">{key}</div>
    </div>
  </div>
  <div class="wx-meta"><span>{f["delta"]}</span><span>{f["daylight"]}</span></div>
</div>"""


def _counted(f: dict) -> str:
    day = f["today"]
    T, RP, CL = day.temp, day.rain_prob, day.cloud
    awake = range(6, 24)
    rain_h = sum(1 for h in awake if RP[h] >= SURE)
    clear_h = sum(1 for h in awake if CL[h] < 50)
    grey_h = len(awake) - rain_h - clear_h

    def blocks(n: int, total: int = 18) -> str:
        cells = "".join(f'<rect x="{i * 30}" y="0" width="24" height="24" '
                        f'fill="{"#000" if i < n else "none"}" stroke="#000" '
                        f'stroke-width="2"/>' for i in range(total))
        return f'<svg class="wx-svg" width="540" height="26" viewBox="0 0 540 26">{cells}</svg>'

    steps, lo_axis, hi_axis = 14, 0, 30
    lo, hi = min(T), max(T)
    cells = "".join(
        f'<rect x="{i * 38}" y="0" width="32" height="26" '
        f'fill="{"#000" if lo <= lo_axis + (hi_axis - lo_axis) * i / (steps - 1) <= hi else "none"}" '
        f'stroke="#000" stroke-width="2"/>' for i in range(steps))
    labels = "".join(f'<text x="{i * 38 + 16}" y="44" font-size="13" text-anchor="middle" '
                     f'font-family="var(--font-mono)">'
                     f'{lo_axis + (hi_axis - lo_axis) * i / (steps - 1):.0f}</text>'
                     for i in range(0, steps, 3))
    mercury = (f'<svg class="wx-svg" width="540" height="48" viewBox="0 0 540 48">'
               f'{cells}{labels}</svg>')
    sky = sky_over(day, range(6, 20))
    return f"""{CSS}<div class="wx">
  <div class="wx-verdict">{f["verdict"]}</div>
  <div class="wx-ttl"><span>TODAY, COUNTED</span>
    <span class="wx-skyline">{glyph(sky, 30)}{WORD[sky]}</span></div>
  <div class="wx-unit"><div class="wx-lab"><b>{f["low"]}&ndash;{f["high"]}</b>
    <span>temperature range</span></div>{mercury}</div>
  <div class="wx-unit"><div class="wx-lab"><b>{rain_h}</b>
    <span>hours of rain (of 18 awake)</span></div>{blocks(rain_h)}</div>
  <div class="wx-unit"><div class="wx-lab"><b>{clear_h}</b>
    <span>hours of clear sky</span></div>{blocks(clear_h)}</div>
  <div class="wx-unit"><div class="wx-lab"><b>{grey_h}</b>
    <span>hours merely grey</span></div>{blocks(grey_h)}</div>
  <div class="wx-note">{f["sun"]} &middot; {f["daylight"]}</div>
</div>"""


BUILDERS = {"chart": _chart, "parts": _parts, "threedays": _threedays,
            "dial": _dial, "counted": _counted}


def block(layout: str, facts: dict[str, Any]) -> str | None:
    """The weather section for `layout`, or None if it cannot be drawn.

    None is not a failure: the template falls back to the plain arrangement,
    which needs no hourly series and prints on a morning when the forecast came
    from a stale cache with a shape this code has never seen.
    """
    builder = BUILDERS.get(layout or DEFAULT, _chart)
    if facts.get("today") is None:
        return None
    try:
        return builder(facts)
    except Exception:  # noqa: BLE001 - a layout must never cost the morning
        return None
