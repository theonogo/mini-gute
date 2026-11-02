"""The First Mate's treasure maps, one 25mm piece at a time.

Each map is a whole chart of one island, 600 dots square - 75mm, three pieces by
three - drawn here from a seed, so the same map comes back the same every time
and a piece cut out in March still meets its neighbour cut out in June. The
First Mate's coupon prints one piece per appearance (`piece_for`, wired up as a
block `drawing` in main.py): the pieces furthest from the X first, the X last,
then the next map. Cut along the dashes and a piece is exactly 200 dots, 25mm,
because the printer lays down 8 dots to the millimetre.

What makes nine scraps one map is continuity: the coastline, its ripples, the
river and the dotted trail all run across the cuts, and the border round the
outside is graduated, so the corner and edge pieces find their places by it.
Every piece also carries its grid reference and the map's number.

Drawn as flat 1-bit SVG - black and white, nothing thinner than 1.6px, no
greys - and inline in the page, so its lettering uses the page's own faces
(IM Fell for the labels, Pirata One for the title), never a system font.

    python tools/treasuremaps.py      # every map, whole and cut, for review
"""

from __future__ import annotations

import html
import math
import random

W = 600              # the whole map, in dots
CELL = 200           # one piece: 25mm at 8 dots/mm
GRID = W // CELL     # three by three
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


# ---------------------------------------------------------------------------
# geometry

def _smooth(points: list[tuple[float, float]], closed: bool = True) -> str:
    """A Catmull-Rom curve through `points`, as an SVG path of cubic Beziers."""
    n = len(points)
    if n < 2:
        return ""
    pts = points
    out = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    last = n if closed else n - 1
    for i in range(last):
        p0 = pts[(i - 1) % n] if closed or i > 0 else pts[0]
        p1 = pts[i % n]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if closed or i + 2 < n else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} "
                   f"{p2[0]:.1f} {p2[1]:.1f}")
    if closed:
        out.append("Z")
    return "".join(out)


def _inside(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    hit = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi:
            hit = not hit
        j = i
    return hit


def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _blob(rng: random.Random, cx: float, cy: float, r: float, n: int,
          rough: float, stretch: tuple[float, float] = (1.0, 1.0)) -> list[tuple[float, float]]:
    """A closed, irregular coastline: a circle bent by a few harmonics."""
    harm = [(k, rng.uniform(0.3, 1.0) * rough / k ** 0.75, rng.uniform(0, math.tau))
            for k in range(2, 7)]
    harm += [(k, rng.uniform(0.0, 0.25) * rough / k ** 0.5, rng.uniform(0, math.tau))
             for k in range(8, 14)]
    pts = []
    for i in range(n):
        t = math.tau * i / n
        f = 1 + sum(a * math.cos(k * t + ph) for k, a, ph in harm)
        pts.append((cx + r * f * math.cos(t) * stretch[0],
                    cy + r * f * math.sin(t) * stretch[1]))
    return pts


# ---------------------------------------------------------------------------
# glyphs - every one drawn round (0, 0) and placed with a translate

def _g(x: float, y: float, body: str, scale: float = 1.0) -> str:
    s = f" scale({scale:.2f})" if scale != 1 else ""
    return f"<g transform='translate({x:.1f} {y:.1f}){s}'>{body}</g>"


PALM = ("<path d='M0 0 C1 -6 3 -11 2 -17' fill='none' stroke='#000' stroke-width='2.2' stroke-linecap='round'/>"
        "<path d='M2 -17 C-3 -20 -8 -19 -10 -15 M2 -17 C7 -21 11 -19 12 -15 M2 -17 C-1 -23 -6 -24 -8 -23 "
        "M2 -17 C5 -24 10 -24 11 -22' fill='none' stroke='#000' stroke-width='2' stroke-linecap='round'/>"
        "<path d='M-4 0 H6' stroke='#000' stroke-width='1.8' stroke-linecap='round'/>")


def _peak(s: float) -> str:
    h = s * 1.25
    hatch = "".join(
        f"M{s * j / 4:.1f} {-h * (1 - j / 4) + 3:.1f} L{s * j / 4 - 2:.1f} -1"
        for j in (1, 2, 3))
    return (f"<path d='M{-s:.1f} 0 L0 {-h:.1f} L{s:.1f} 0 Z' fill='#fff' stroke='#000' "
            f"stroke-width='2.2' stroke-linejoin='round'/>"
            f"<path d='{hatch}' stroke='#000' stroke-width='1.6' stroke-linecap='round'/>")


WAVE = ("<path d='M-8 0 q4 -4 8 0 t8 0' fill='none' stroke='#000' stroke-width='1.7' "
        "stroke-linecap='round'/>")

LANDMARKS = {
    # A rock with a skull's face worn into it.
    "skull": ("<path d='M-14 8 C-16 -6 -10 -15 0 -15 C10 -15 16 -6 14 8 Z' fill='#fff' stroke='#000' stroke-width='2.2'/>"
              "<circle cx='-5' cy='-4' r='3.6'/><circle cx='5' cy='-4' r='3.6'/>"
              "<path d='M0 0 L-2 4 H2 Z'/><path d='M-6 8 V4 M-2 8 V5 M2 8 V5 M6 8 V4' stroke='#000' stroke-width='1.8'/>"),
    # A hull on its side with a snapped mast.
    "wreck": ("<path d='M-16 2 Q-14 10 0 11 Q12 10 16 0 Z' fill='#fff' stroke='#000' stroke-width='2.2'/>"
              "<path d='M-4 2 L2 -14 M2 -14 L9 -9' stroke='#000' stroke-width='2.2' stroke-linecap='round'/>"
              "<path d='M-10 5 H8 M-7 8 H5' stroke='#000' stroke-width='1.6'/>"),
    # A dead tree, bare, one noose-shaped branch.
    "tree": ("<path d='M0 10 C-1 2 1 -6 0 -14 M0 -6 C-5 -9 -8 -13 -9 -17 M0 -9 C5 -11 8 -15 10 -18 "
             "M-5 -10 L-9 -10 M7 -14 V-9' fill='none' stroke='#000' stroke-width='2.4' stroke-linecap='round'/>"
             "<circle cx='7' cy='-7' r='2' fill='none' stroke='#000' stroke-width='1.6'/>"),
    # A cave mouth in a bluff.
    "cave": ("<path d='M-16 8 C-14 -8 -6 -14 0 -14 C6 -14 14 -8 16 8 Z' fill='#fff' stroke='#000' stroke-width='2.2'/>"
             "<path d='M-6 8 C-6 0 -3 -4 0 -4 C3 -4 6 0 6 8 Z'/>"),
    # A ruined tower, crenellated, one side fallen.
    "tower": ("<path d='M-8 10 V-10 H-5 V-14 H-1 V-10 H2 V-14 H5 V-6 L8 -2 V10 Z' fill='#fff' stroke='#000' "
              "stroke-width='2.2' stroke-linejoin='round'/><path d='M-3 10 V3 Q0 0 3 3 V10 Z'/>"),
    # A smoking volcano.
    "volcano": ("<path d='M-17 10 L-5 -9 H5 L17 10 Z' fill='#fff' stroke='#000' stroke-width='2.2' stroke-linejoin='round'/>"
                "<path d='M-5 -9 Q0 -5 5 -9' fill='none' stroke='#000' stroke-width='1.8'/>"
                "<path d='M-1 -12 C-5 -16 2 -18 -1 -23 M3 -12 C7 -17 1 -19 5 -24' fill='none' stroke='#000' "
                "stroke-width='1.8' stroke-linecap='round'/>"),
    # Three broken teeth of rock standing in the surf.
    "teeth": ("<path d='M-15 8 L-11 -8 L-7 8 Z M-4 8 L0 -13 L4 8 Z M7 8 L11 -6 L15 8 Z' fill='#fff' stroke='#000' "
              "stroke-width='2.2' stroke-linejoin='round'/><path d='M-17 9 H17' stroke='#000' stroke-width='1.8'/>"),
    # The bones of a very large fish, picked clean. Never crossed bones: on a
    # treasure map anything crossed reads as the X. (A ribcage read as a barrel.)
    "bones": ("<g transform='scale(1.2)'><path d='M-8 0 H13' fill='none' stroke='#000' stroke-width='2.6' "
              "stroke-linecap='round'/><path d='M-4 0 L-1 -8 M-4 0 L-1 8 M2 0 L5 -7 M2 0 L5 7 M8 0 L10 -5 M8 0 L10 5' "
              "fill='none' stroke='#000' stroke-width='2.2' stroke-linecap='round'/>"
              "<path d='M13 0 L20 -7 L18 0 L20 7 Z' fill='#000' stroke='#000' stroke-width='1.4' stroke-linejoin='round'/>"
              "<path d='M-8 -7 Q-20 -6 -21 0 Q-20 6 -8 7 Z' fill='#fff' stroke='#000' stroke-width='2.2' "
              "stroke-linejoin='round'/><circle cx='-15' cy='-1.5' r='2' fill='#000'/></g>"),
    # A lighthouse on the point, dark.
    "lighthouse": ("<path d='M-6 10 L-4 -10 H4 L6 10 Z' fill='#fff' stroke='#000' stroke-width='2.2' stroke-linejoin='round'/>"
                   "<path d='M-5 -10 H5 V-15 H-5 Z M-3 -15 L0 -19 L3 -15' fill='#000' stroke='#000' stroke-width='1.6'/>"
                   "<path d='M-5 -1 H5 M-5.5 4 H5.5' stroke='#000' stroke-width='1.8'/>"),
}
OFFSHORE = {"wreck", "teeth"}


def _spiral() -> str:
    pts = [((2 + 1.5 * t) * math.cos(t), (2 + 1.5 * t) * math.sin(t) * 0.7)
           for t in [i * 0.35 for i in range(36)]]
    return (f"<path d='{_smooth(pts, closed=False)}' fill='none' stroke='#000' stroke-width='2' "
            f"stroke-linecap='round'/>")


# Something to find on every piece that would otherwise be only water.
SEA_THINGS = [
    ("a whirlpool", _spiral()),
    ("a whale, diving", "<path d='M-15 -10 Q-7 -4 0 3 Q7 -4 15 -10 Q9 -12 4 -6 Q2 -10 0 -8 Q-2 -10 -4 -6 "
     "Q-9 -12 -15 -10 Z' fill='#000'/><path d='M-1 3 V9' stroke='#000' stroke-width='3'/>"
     "<path d='M-18 10 q4 -4 8 0 t8 0 t8 0 t8 0' fill='none' stroke='#000' stroke-width='1.8'/>"),
    ("the arm of something very large", "<path d='M-12 12 C-12 -4 4 -16 11 -8 C15 -3 9 3 5 -1' fill='none' "
     "stroke='#000' stroke-width='4.5' stroke-linecap='round'/><circle cx='-8' cy='2' r='1.4' fill='#fff'/>"
     "<circle cx='-5' cy='-5' r='1.4' fill='#fff'/><circle cx='1' cy='-10' r='1.3' fill='#fff'/>"
     "<path d='M-20 13 q4 -4 8 0 t8 0 t8 0' fill='none' stroke='#000' stroke-width='1.8'/>"),
    ("a bottle, floating, with paper in it", "<g transform='rotate(-24)'><path d='M-12 -5 H6 Q9 -5 10 -2 H14 V2 H10 "
     "Q9 5 6 5 H-12 Q-15 5 -15 0 Q-15 -5 -12 -5 Z' fill='#fff' stroke='#000' stroke-width='2'/>"
     "<rect x='14' y='-2.5' width='4' height='5' fill='#000'/><path d='M-10 -1 H4 M-10 2 H1' stroke='#000' "
     "stroke-width='1.4'/></g><path d='M-18 9 q4 -4 8 0 t8 0 t8 0 t8 0' fill='none' stroke='#000' stroke-width='1.8'/>"),
    ("gulls, circling something", "<path d='M-16 2 Q-12 -6 -6 -2 L-4 0 L-2 -2 Q4 -6 8 2 Q2 -2 -4 3 Q-10 -2 -16 2 Z "
     "M2 -12 Q5 -17 9 -14 L10 -13 L11 -14 Q15 -17 18 -12 Q14 -14 10 -10 Q6 -14 2 -12 Z' fill='#000'/>"
     "<circle cx='0' cy='14' r='5' fill='none' stroke='#000' stroke-width='1.8' stroke-dasharray='3 3'/>"),
    ("rocks in the surf", "<path d='M-12 4 Q-10 -6 -4 -5 Q0 -4 0 4 Z M2 4 Q4 -2 8 -2 Q12 -1 12 4 Z' fill='#000'/>"
     "<path d='M-16 8 q4 -4 8 0 t8 0 t8 0 t8 0' fill='none' stroke='#000' stroke-width='1.8'/>"),
]

SHIP = ("<path d='M-15 3 H15 L11 9 H-11 Z' fill='#000'/>"
        "<path d='M-4 3 V-18 M6 3 V-13' stroke='#000' stroke-width='1.8'/>"
        "<path d='M-4 -17 Q4 -12 -4 -5 Z M6 -12 Q12 -8 6 -3 Z' fill='#fff' stroke='#000' stroke-width='1.6' stroke-linejoin='round'/>"
        "<path d='M-4 -18 L-10 -16 L-4 -14' fill='#000'/>")

SERPENT = ("<path d='M-34 4 Q-28 -10 -22 4 M-14 4 Q-8 -12 -2 4 M6 4 Q12 -10 18 4' fill='none' stroke='#000' "
           "stroke-width='3' stroke-linecap='round'/>"
           "<path d='M22 4 Q24 -14 34 -12 Q40 -10 37 -6 Q31 -7 29 -2 Q28 3 26 4' fill='#fff' stroke='#000' "
           "stroke-width='2.4' stroke-linejoin='round'/><circle cx='33' cy='-9' r='1.6'/>"
           "<path d='M-40 2 Q-37 6 -34 4' fill='none' stroke='#000' stroke-width='2.2' stroke-linecap='round'/>")

ANCHOR = ("<circle cx='0' cy='-8' r='2.6' fill='none' stroke='#000' stroke-width='1.8'/>"
          "<path d='M0 -5 V8 M-5 -2 H5 M-7 3 Q-6 9 0 9 Q6 9 7 3' fill='none' stroke='#000' stroke-width='2' stroke-linecap='round'/>")


def _compass(r: float) -> str:
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.55
        tip = (rr * math.cos(a), rr * math.sin(a))
        left = (r * 0.16 * math.cos(a - math.pi / 2), r * 0.16 * math.sin(a - math.pi / 2))
        right = (r * 0.16 * math.cos(a + math.pi / 2), r * 0.16 * math.sin(a + math.pi / 2))
        # Half of each point is black: the classic rose, readable at a glance.
        pts.append(f"<path d='M0 0 L{left[0]:.1f} {left[1]:.1f} L{tip[0]:.1f} {tip[1]:.1f} Z' fill='#000'/>"
                   f"<path d='M0 0 L{right[0]:.1f} {right[1]:.1f} L{tip[0]:.1f} {tip[1]:.1f} Z' fill='#fff' "
                   f"stroke='#000' stroke-width='1.4' stroke-linejoin='round'/>")
    return (f"<circle r='{r * 0.72:.1f}' fill='#fff' stroke='#000' stroke-width='1.6'/>"
            + "".join(reversed(pts))
            + "<circle r='2.6' fill='#fff' stroke='#000' stroke-width='1.4'/>"
            + f"<text y='{-r - 5:.1f}' text-anchor='middle' class='tm-n'>N</text>")


# ---------------------------------------------------------------------------
# the map

class TreasureMap:
    """One island, drawn from `seed`, with the landmarks it is given."""

    def __init__(self, seed: int, name: str, landmarks: list[dict], number: int = 1):
        self.seed, self.name, self.number = seed, name, number
        self.rng = random.Random(f"treasure:{seed}")
        self.marks_wanted = landmarks
        self.busy: set[tuple[int, int]] = set()   # 10px cells something is drawn in
        self.items: list[str] = []                # SVG, in drawing order
        self.where: list[tuple[str, float, float]] = []   # (what, x, y) for the narrator
        self.labels: list[tuple[str, float, float, float, float]] = []   # (name, box)
        self._build()
        # Drawn once: drawing places the palms, labels and serpent, and the
        # narrator's description of a piece has to include them.
        self._svg = self._draw()

    # -- occupancy -------------------------------------------------------
    def _free(self, x, y, rx, ry) -> bool:
        for i in range(int((x - rx) // 10), int((x + rx) // 10) + 1):
            for j in range(int((y - ry) // 10), int((y + ry) // 10) + 1):
                if (i, j) in self.busy:
                    return False
        return True

    def _overlap(self, x, y, rx, ry) -> int:
        return sum((i, j) in self.busy
                   for i in range(int((x - rx) // 10), int((x + rx) // 10) + 1)
                   for j in range(int((y - ry) // 10), int((y + ry) // 10) + 1))

    def _take(self, x, y, rx, ry) -> None:
        for i in range(int((x - rx) // 10), int((x + rx) // 10) + 1):
            for j in range(int((y - ry) // 10), int((y + ry) // 10) + 1):
                self.busy.add((i, j))

    @staticmethod
    def _cut_dist(x, y) -> float:
        """How far a point is from the nearest cut line."""
        return min(abs(v - c) for v in (x, y) for c in (CELL, 2 * CELL))

    @staticmethod
    def _cuts(x0, y0, x1, y1) -> int:
        """How many cut lines a box crosses: a label across one leaves a
        stray half-word on the next piece."""
        return sum(a < c < b for a, b in ((x0, x1), (y0, y1)) for c in (CELL, 2 * CELL))

    @staticmethod
    def _label_spots(lx, ly, name):
        """Where a landmark's label may go - below, above, beside, or off a
        corner - as (x, y, anchor, left edge, width), whole on the map."""
        w = 6.4 * len(name) + 6
        for tx, ty, anchor in ((lx, ly + 27, "middle"), (lx, ly - 22, "middle"),
                               (lx + 22, ly + 5, "start"), (lx - 22, ly + 5, "end"),
                               (lx + 16, ly + 26, "start"), (lx - 16, ly + 26, "end"),
                               (lx + 16, ly - 20, "start"), (lx - 16, ly - 20, "end")):
            bx = tx if anchor == "start" else tx - w if anchor == "end" else tx - w / 2
            if 16 < bx and bx + w < W - 16 and 22 < ty < W - 14:
                yield tx, ty, anchor, bx, w

    def _sits_whole(self, x, y, name) -> bool:
        """Whether a landmark here is clear of the cuts and has somewhere to
        put its name that is too, so both land on the same piece."""
        return self._cut_dist(x, y) > 22 and any(
            self._cuts(bx, ty - 12, bx + w, ty + 3) == 0
            for _, ty, _, bx, w in self._label_spots(x, y, name))

    # -- land and sea ----------------------------------------------------
    def land(self, x, y) -> bool:
        return any(_inside(x, y, p) for p in self.polys)

    def coast_dist(self, x, y) -> float:
        best = 1e9
        for p in self.polys:
            for i in range(0, len(p), 2):
                a, b = p[i], p[(i + 2) % len(p)]
                best = min(best, _seg_dist(x, y, a[0], a[1], b[0], b[1]))
        return best

    def _land_point(self, margin: float, avoid: list[tuple[float, float]] = (),
                    spread: float = 0, tries: int = 400):
        rng = self.rng
        for _ in range(tries):
            x, y = rng.uniform(60, W - 60), rng.uniform(60, W - 60)
            if (self.land(x, y) and self.coast_dist(x, y) >= margin
                    and all(math.hypot(x - ax, y - ay) >= spread for ax, ay in avoid)):
                return x, y
        return None

    # -- build -----------------------------------------------------------
    def _build(self) -> None:
        rng = self.rng
        cx, cy = 300 + rng.uniform(-28, 28), 300 + rng.uniform(-28, 28)
        stretch = (1.0, rng.uniform(0.84, 0.96)) if rng.random() < 0.5 else (rng.uniform(0.84, 0.96), 1.0)
        main = _blob(rng, cx, cy, rng.uniform(190, 212), 180, rng.uniform(0.34, 0.46), stretch)
        # Shrink to fit rather than clamp: a clamped coast runs ruler-straight
        # along the margin, and no island does that.
        lo, hi = 64, W - 64
        k = 1.0
        for x, y in main:
            for v, c0 in ((x, cx), (y, cy)):
                if v < lo:
                    k = min(k, (c0 - lo) / (c0 - v))
                if v > hi:
                    k = min(k, (hi - c0) / (v - c0))
        main = [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in main]
        self.polys = [main]
        self.main = main

        # Every piece's grid tag sits in its bottom-right corner (piece_svg),
        # so nothing else may.
        for r in range(GRID):
            for c in range(GRID):
                self._take((c + 1) * CELL - 46, (r + 1) * CELL - 13, 44, 11)

        # Corners for the furniture: the two with the most open water.
        corners = [(78, 78), (W - 78, 78), (78, W - 78), (W - 78, W - 78)]
        corners.sort(key=lambda c: -self.coast_dist(*c) * (0 if self.land(*c) else 1))
        self.compass_at = corners[0]
        self._take(*self.compass_at, 44, 50)
        # The title scroll along the top or bottom edge, whichever is clearer.
        # Centred if the water there is anywhere near as clear, so the name
        # sits on the middle piece rather than torn across two.
        edges = [(300, 40), (300, W - 40), (190, 40), (410, W - 40), (410, 40), (190, W - 40)]
        edges.sort(key=lambda c: -min(self.coast_dist(c[0] + dx, c[1]) for dx in (-90, 0, 90))
                   - (30 if c[0] == 300 else 0))
        self.title_at = next((e for e in edges if self._free(e[0], e[1], 105, 20)), edges[0])
        self._take(*self.title_at, 108, 22)

        # An islet or two, out in clear water.
        for _ in range(rng.choice([1, 2, 2, 3])):
            for _try in range(200):
                x, y = rng.uniform(70, W - 70), rng.uniform(70, W - 70)
                r = rng.uniform(12, 24)
                if (not self.land(x, y) and self.coast_dist(x, y) > r + 34
                        and self._free(x, y, r + 16, r + 16)):
                    self.polys.append(_blob(rng, x, y, r, 40, 0.3))
                    self._take(x, y, r + 14, r + 14)
                    break

        # The X: well inland, clear of the cuts so it sits whole on one piece.
        for _ in range(600):
            p = self._land_point(46)
            if p and self._cut_dist(*p) > 28 and self._free(*p, 16, 16):
                self.x = p
                break
        else:
            self.x = (cx, cy)
        self._take(*self.x, 18, 18)

        # Mountains, away from the X.
        m = self._land_point(46, [self.x], 120) or self._land_point(36) or (cx, cy)
        self.peaks = []
        for _ in range(rng.randint(3, 5)):
            px, py = m[0] + rng.uniform(-30, 30), m[1] + rng.uniform(-18, 18)
            if self.land(px, py) and self.coast_dist(px, py) > 20:
                self.peaks.append((px, py, rng.uniform(13, 20)))
        self.peaks.sort(key=lambda p: p[1])
        for px, py, s in self.peaks:
            self._take(px, py - s * 0.6, s, s * 0.8)
        self.where.append(("the mountains", m[0], m[1]))

        # Where they come ashore: the coast furthest from the X, with the
        # ship at anchor off it - inside the border, and whole on one piece
        # if it can be.
        best, land_at = None, main[0]
        self.ship_at = (W - 60, W - 60)
        for i in range(0, len(main), 6):
            x, y = main[i]
            out = (x - cx, y - cy)
            n = math.hypot(*out) or 1
            sea = (x + out[0] / n * 46, y + out[1] / n * 46)
            if not (32 < sea[0] < W - 46 and 36 < sea[1] < W - 26) or self.land(*sea):
                continue
            if not self._free(sea[0], sea[1], 20, 16):
                continue
            score = (self._cut_dist(*sea) > 26, math.hypot(x - self.x[0], y - self.x[1]))
            if best is None or score > best:
                best, land_at, self.ship_at = score, (x, y), sea
        self.landing = land_at
        self._take(*self.ship_at, 18, 16)
        self.where.append(("the landing place, with the ship at anchor off it", *self.landing))

        # Landmarks: inland ones on the way to the X, offshore ones in the surf.
        # Each clear of the cuts for most of its tries, so it is whole on one
        # piece, and only then anywhere it fits.
        self.marks = []
        placed = [self.x, self.landing]
        for spec in self.marks_wanted:
            kind = spec["kind"]
            pos = None
            if kind in OFFSHORE:
                for _try in range(500):
                    x, y = rng.uniform(50, W - 50), rng.uniform(50, W - 50)
                    if (not self.land(x, y) and 16 < self.coast_dist(x, y) < 40
                            and (_try > 350 or self._sits_whole(x, y, spec["name"]))
                            and self._free(x, y, 22, 16)
                            and all(math.hypot(x - a, y - b) > 110 for a, b in placed)):
                        pos = (x, y)
                        break
            elif kind == "lighthouse":
                coast = rng.sample(range(len(main)), len(main))
                for strict in (True, False):
                    for i in coast:
                        x, y = main[i]
                        x, y = x + (cx - x) * 0.06, y + (cy - y) * 0.06
                        if ((not strict or self._sits_whole(x, y, spec["name"])) and self._free(x, y, 12, 16)
                                and all(math.hypot(x - a, y - b) > 110 for a, b in placed)):
                            pos = (x, y)
                            break
                    if pos:
                        break
            else:
                for _try in range(400):
                    p = self._land_point(28, placed, 110)
                    if p and self._free(p[0], p[1], 18, 16) and (_try > 250 or self._sits_whole(*p, spec["name"])):
                        pos = p
                        break
            if pos is None:
                continue
            self._take(pos[0], pos[1], 18, 16)
            self.marks.append((spec, pos))
            placed.append(pos)
            self.where.append((spec["name"], *pos))

        self._trail()
        self._river(m)

        # Now and then a lake inland, where there is room for one.
        self.lake = None
        if rng.random() < 0.5:
            for _try in range(200):
                p = self._land_point(52)
                if p and self._free(p[0], p[1], 26, 20):
                    self.lake = _blob(rng, p[0], p[1], rng.uniform(15, 22), 36, 0.25, (1.3, 0.8))
                    self._take(p[0], p[1], 30, 22)
                    self.where.append(("a lake", *p))
                    break

    def _trail(self) -> None:
        """The dotted way from the landing to the X, by the inland landmarks."""
        rng = self.rng
        stops = [self.landing]
        inland = [p for s, p in self.marks if s["kind"] not in OFFSHORE and s["kind"] != "lighthouse"]
        here = self.landing
        while inland:
            nxt = min(inland, key=lambda p: math.hypot(p[0] - here[0], p[1] - here[1]))
            # Pass the landmark, not through it.
            side = 1 if rng.random() < 0.5 else -1
            stops.append((nxt[0] + 24 * side, nxt[1] + 14))
            inland.remove(nxt)
            here = nxt
            if len(stops) > 2:
                break
        stops.append(self.x)
        pts: list[tuple[float, float]] = []
        for (ax, ay), (bx, by) in zip(stops, stops[1:]):
            seg = max(2, int(math.hypot(bx - ax, by - ay) / 34))
            nx, ny = -(by - ay), bx - ax
            n = math.hypot(nx, ny) or 1
            for k in range(seg):
                t = k / seg
                wob = math.sin(t * math.pi) * rng.uniform(-22, 22)
                px, py = ax + (bx - ax) * t + nx / n * wob, ay + (by - ay) * t + ny / n * wob
                # Keep to the land: pull a stray point back towards the X.
                tries = 0
                while not self.land(px, py) and tries < 12 and k:
                    px, py = px + (self.x[0] - px) * 0.18, py + (self.x[1] - py) * 0.18
                    tries += 1
                pts.append((px, py))
        pts.append((self.x[0] - 8, self.x[1] + 8))
        self.trail = pts
        for x, y in pts:
            self._take(x, y, 6, 6)

    def _river(self, source) -> None:
        """From the mountains to the nearest coast, wandering."""
        rng = self.rng
        sx, sy = source[0] + rng.uniform(-10, 10), source[1] + 14
        # A mouth far enough off to wander towards, and not past the X.
        mouths = [p for p in self.main
                  if 90 < math.hypot(p[0] - sx, p[1] - sy) < 210
                  and _seg_dist(self.x[0], self.x[1], sx, sy, p[0], p[1]) > 40]
        best = (rng.choice(mouths) if mouths else
                min(self.main, key=lambda p: math.hypot(p[0] - sx, p[1] - sy)))
        n = 9
        nx, ny = -(best[1] - sy), best[0] - sx
        nn = math.hypot(nx, ny) or 1
        phase = rng.uniform(0, math.tau)
        pts = []
        for k in range(n + 1):
            t = k / n
            wob = math.sin(t * 9 + phase) * 13 * math.sin(t * math.pi)
            pts.append((sx + (best[0] - sx) * t + nx / nn * wob,
                        sy + (best[1] - sy) * t + ny / nn * wob))
        # Run it a little past the coast so the mouth meets the water.
        ex, ey = pts[-1]
        dx, dy = ex - pts[-2][0], ey - pts[-2][1]
        d = math.hypot(dx, dy) or 1
        pts.append((ex + dx / d * 8, ey + dy / d * 8))
        self.river = pts
        for x, y in pts:
            self._take(x, y, 5, 5)
        self.where.append(("the river", *pts[len(pts) // 2]))

    # -- drawing ---------------------------------------------------------
    def body(self) -> str:
        return self._svg

    def _draw(self) -> str:
        rng = random.Random(f"treasure-ink:{self.seed}")
        out = ["<rect width='600' height='600' fill='#fff'/>"]

        # The big things at sea first, so the pieces they are on count as busy.
        self.serpent = None
        for _ in range(300):
            x, y = rng.uniform(70, W - 70), rng.uniform(50, W - 50)
            if not self.land(x, y) and self.coast_dist(x, y) > 42 and self._free(x, y, 44, 14):
                self.serpent = (x, y)
                self._take(x, y, 44, 14)
                self.where.append(("a sea serpent", x, y))
                break
        self.where.append(("the compass rose", *self.compass_at))
        self.where.append((f"the title scroll, {self.name}", *self.title_at))

        # Every piece gets something to look at: one that would be only water
        # gets one thing from the sea, placed before the waves so they part
        # round it. Each thing once per map.
        things = SEA_THINGS[:]
        rng.shuffle(things)
        later = []
        for r in range(GRID):
            for c in range(GRID):
                x0, y0 = c * CELL, r * CELL
                if any(x0 <= x < x0 + CELL and y0 <= y < y0 + CELL for _, x, y in self.where):
                    continue
                for _try in range(300):
                    x, y = x0 + rng.uniform(34, CELL - 40), y0 + rng.uniform(34, CELL - 40)
                    if (not self.land(x, y) and self.coast_dist(x, y) > 32
                            and self._free(x, y, 28, 22) and things):
                        what, glyph = things.pop()
                        later.append(_g(x, y, glyph, 1.35))
                        self._take(x, y, 28, 22)
                        self.where.append((what, x, y))
                        break

        # Waves in the open water, then the coast's ripples over them.
        for gx in range(26, W, 36):
            for gy in range(30, W, 30):
                x, y = gx + rng.uniform(-12, 12) + (18 if (gy // 30) % 2 else 0), gy + rng.uniform(-6, 6)
                if (16 < x < W - 16 and 16 < y < W - 16 and not self.land(x, y)
                        and self.coast_dist(x, y) > 28 and self._free(x, y, 9, 5)
                        and rng.random() < 0.55):
                    out.append(_g(x, y, WAVE))
        for poly in self.polys:
            d = _smooth(poly)
            # Two lines of water round every coast: a solid one close in and a
            # broken one further out, the inner halves covered by the land.
            out.append(f"<path d='{d}' fill='none' stroke='#000' stroke-width='35' stroke-dasharray='6 5'/>"
                       f"<path d='{d}' fill='none' stroke='#fff' stroke-width='31'/>"
                       f"<path d='{d}' fill='none' stroke='#000' stroke-width='18'/>"
                       f"<path d='{d}' fill='none' stroke='#fff' stroke-width='14'/>")
        for poly in self.polys:
            out.append(f"<path d='{_smooth(poly)}' fill='#fff' stroke='#000' stroke-width='3' "
                       f"stroke-linejoin='round'/>")

        if self.lake:
            ld = _smooth(self.lake)
            lx = sum(x for x, _ in self.lake) / len(self.lake)
            ly = sum(y for _, y in self.lake) / len(self.lake)
            out.append(f"<path d='{ld}' fill='#fff' stroke='#000' stroke-width='2.4'/>"
                       + _g(lx, ly + 2, WAVE, 0.8))

        # The river, then the land's furniture.
        out.append(f"<path d='{_smooth(self.river, closed=False)}' fill='none' stroke='#000' "
                   f"stroke-width='2.6' stroke-linecap='round'/>")
        for px, py, s in self.peaks:
            out.append(_g(px, py, _peak(s)))
        for _ in range(140):
            x, y = rng.uniform(40, W - 40), rng.uniform(40, W - 40)
            if (self.land(x, y) and self.coast_dist(x, y) > 12
                    and self._free(x, y - 8, 11, 12) and rng.random() < 0.5):
                out.append(_g(x, y, PALM))
                self._take(x, y - 8, 11, 12)

        # The trail, dots with a gap at each end, and the X over it.
        out.append(f"<path d='{_smooth(self.trail, closed=False)}' fill='none' stroke='#000' "
                   f"stroke-width='3.4' stroke-dasharray='0.1 8' stroke-linecap='round'/>")
        x, y = self.x
        out.append(f"<path d='M{x - 11:.1f} {y - 11:.1f} L{x + 11:.1f} {y + 11:.1f} M{x + 11:.1f} {y - 11:.1f} "
                   f"L{x - 11:.1f} {y + 11:.1f}' stroke='#fff' stroke-width='10' stroke-linecap='round'/>"
                   f"<path d='M{x - 11:.1f} {y - 11:.1f} L{x + 11:.1f} {y + 11:.1f} M{x + 11:.1f} {y - 11:.1f} "
                   f"L{x - 11:.1f} {y + 11:.1f}' stroke='#000' stroke-width='5.5' stroke-linecap='round'/>")

        out += later

        # Landmarks, labelled where the label is whole, on the map, on the
        # same piece as its landmark, and over the least that is already
        # drawn; a white halo keeps it readable.
        for spec, (lx, ly) in self.marks:
            glyph = LANDMARKS[spec["kind"]]
            if spec["kind"] == "wreck":
                glyph = f"<g transform='rotate(-20)'>{glyph}</g>"
            out.append(_g(lx, ly, glyph))
            name = html.escape(spec["name"])
            best = None
            for tx, ty, anchor, bx, w in self._label_spots(lx, ly, spec["name"]):
                cost = self._overlap(bx + w / 2, ty - 4, w / 2, 7) + 25 * self._cuts(bx, ty - 12, bx + w, ty + 3)
                if best is None or cost < best[0]:
                    best = (cost, tx, ty, anchor, bx, w)
                if cost == 0:
                    break
            if best is None:
                continue
            _, tx, ty, anchor, bx, w = best
            self._take(bx + w / 2, ty - 4, w / 2, 7)
            self.labels.append((spec["name"], bx, ty - 12, bx + w, ty + 3))
            out.append(f"<text x='{tx:.1f}' y='{ty:.1f}' text-anchor='{anchor}' class='tm-label'>{name}</text>")

        # Out at sea: the ship at anchor, a serpent, the compass and the title.
        sx, sy = self.ship_at
        out.append(_g(sx, sy, SHIP))
        out.append(_g(sx + 20, sy + 4, ANCHOR, 0.8))
        if self.serpent:
            out.append(_g(*self.serpent, SERPENT))
        cx, cy = self.compass_at
        out.append(_g(cx, cy + 4, _compass(30)))
        tx, ty = self.title_at
        out.append(_g(tx, ty, _scroll(self.name)))

        # The graduated border, drawn last so nothing sits over it.
        blocks = "".join(
            f"<rect x='{i * 25}' y='3' width='25' height='6'/><rect x='{i * 25}' y='591' width='25' height='6'/>"
            f"<rect x='3' y='{i * 25}' width='6' height='25'/><rect x='591' y='{i * 25}' width='6' height='25'/>"
            for i in range(0, 24, 2))
        out.append(f"<g fill='#000'>{blocks}</g>"
                   "<rect x='1.5' y='1.5' width='597' height='597' fill='none' stroke='#000' stroke-width='3'/>"
                   "<rect x='9.5' y='9.5' width='581' height='581' fill='none' stroke='#000' stroke-width='1.6'/>")
        return "".join(out)

    # -- pieces ----------------------------------------------------------
    def order(self) -> list[tuple[int, int]]:
        """The nine pieces in the order they are handed out: furthest from the
        X first, so the map closes in on the treasure, the X's own piece last."""
        cells = [(c, r) for r in range(GRID) for c in range(GRID)]
        x, y = self.x
        return sorted(cells, key=lambda cr: -math.hypot(cr[0] * CELL + CELL / 2 - x,
                                                        cr[1] * CELL + CELL / 2 - y))

    def faults(self) -> list[str]:
        """What would spoil the pieces: a label or landmark torn by a cut, an
        X near the coast. Empty for a good map (tools/treasuremaps.py)."""
        out = [f"label across a cut: {n}" for n, *box in self.labels if self._cuts(*box)]
        out += [f"landmark on a cut: {s['name']}" for s, p in self.marks if self._cut_dist(*p) <= 18]
        out += [f"landmark missing: {s['name']}" for s in self.marks_wanted
                if s["name"] not in {m["name"] for m, _ in self.marks}]
        if self.coast_dist(*self.x) < 40:
            out.append(f"X {self.coast_dist(*self.x):.0f} from the coast")
        return out

    def contents(self, c: int, r: int) -> str:
        """What a narrator could see on one piece."""
        x0, y0 = c * CELL, r * CELL
        on = [w for w, x, y in self.where if x0 <= x < x0 + CELL and y0 <= y < y0 + CELL]
        land = sum(self.land(x0 + i, y0 + j) for i in range(10, CELL, 20) for j in range(10, CELL, 20))
        terrain = ("open sea" if land == 0 else "mostly sea, with a stretch of coast" if land < 30
                   else "the coast" if land < 70 else "the island's interior")
        if any(x0 <= px < x0 + CELL and y0 <= py < y0 + CELL for px, py in self.trail):
            on.append("part of the dotted trail")
        if x0 <= self.x[0] < x0 + CELL and y0 <= self.x[1] < y0 + CELL:
            on.append("THE X")
        return terrain + (": " + ", ".join(on) if on else "")


def _scroll(name: str) -> str:
    """A banner with folded tails, the map's name across it."""
    w = max(150, 9.6 * len(name) + 40)
    h = 30
    return (f"<path d='M{-w / 2 - 20:.1f} {-h / 2 + 6:.1f} L{-w / 2 + 6:.1f} {-h / 2 + 6:.1f} L{-w / 2 + 6:.1f} {h / 2 + 6:.1f} "
            f"L{-w / 2 - 20:.1f} {h / 2 + 6:.1f} L{-w / 2 - 12:.1f} 6 Z M{w / 2 + 20:.1f} {-h / 2 + 6:.1f} "
            f"L{w / 2 - 6:.1f} {-h / 2 + 6:.1f} L{w / 2 - 6:.1f} {h / 2 + 6:.1f} L{w / 2 + 20:.1f} {h / 2 + 6:.1f} "
            f"L{w / 2 + 12:.1f} 6 Z' fill='#fff' stroke='#000' stroke-width='2' stroke-linejoin='round'/>"
            f"<rect x='{-w / 2:.1f}' y='{-h / 2:.1f}' width='{w:.1f}' height='{h}' fill='#fff' stroke='#000' stroke-width='2.2'/>"
            f"<text y='7' text-anchor='middle' class='tm-title'>{html.escape(name)}</text>")


# Labels set in the page's own faces - never a system font (CLAUDE.md, fonts).
STYLE = ("<style>.tm-label{font-family:var(--font);font-size:14px;fill:#000;"
         "paint-order:stroke;stroke:#fff;stroke-width:5px;stroke-linejoin:round}"
         ".tm-title{font-family:var(--font-display);font-size:20px;fill:#000}"
         ".tm-n{font-family:var(--font-display);font-size:15px;fill:#000}"
         ".tm-tag{font-family:var(--font);font-weight:var(--bold);font-size:13px;fill:#000}</style>")


def piece_svg(m: TreasureMap, c: int, r: int, cut: bool = True) -> str:
    """One piece, exactly CELL dots square, with its cut line and its grid tag."""
    x0, y0 = c * CELL, r * CELL
    ref = f"{'ABC'[c]}{r + 1}"
    # Map 0 is a forgery, which knows its square but not its map.
    tag = f"{ROMAN[(m.number - 1) % len(ROMAN)] if m.number else '?'} · {ref}"
    tw = 8 * len(tag) + 10
    over = (f"<rect x='{x0 + CELL - tw - 4}' y='{y0 + CELL - 22}' width='{tw}' height='18' fill='#fff' "
            f"stroke='#000' stroke-width='1.6'/>"
            f"<text x='{x0 + CELL - 4 - tw / 2:.1f}' y='{y0 + CELL - 8.5}' text-anchor='middle' class='tm-tag'>{tag}</text>")
    if cut:
        over += (f"<rect x='{x0 + 1}' y='{y0 + 1}' width='{CELL - 2}' height='{CELL - 2}' fill='none' "
                 f"stroke='#000' stroke-width='2' stroke-dasharray='7 5'/>")
    return (f"<svg class='map-piece' xmlns='http://www.w3.org/2000/svg' width='{CELL}' height='{CELL}' "
            f"viewBox='{x0} {y0} {CELL} {CELL}'>{STYLE}{m.body()}{over}</svg>")


def map_for(maps: list[dict], index: int) -> TreasureMap:
    """Map `index` (0-based) of the list, going round again with new seeds once
    every one has been found, so the crew never runs out of islands."""
    spec = maps[index % len(maps)]
    seed = spec["seed"] + 1000 * (index // len(maps))
    # Nobody has looked at a later lap's islands, and about one seed in twenty
    # tears a landmark or loses one, so take the first from here that draws
    # clean. The listed seeds are reviewed and clean, so they come back as is.
    for k in range(20):
        m = TreasureMap(seed + k, spec["name"], spec["landmarks"], index + 1)
        if not m.faults():
            break
    return m


def _forgery(maps: list[dict], day) -> dict:
    """The Mimic in the First Mate's clothes hands out a scrap too, and it is
    its own work: a piece of an island that does not exist, the day's own, so
    it fits nothing in the collection and takes no real piece out of turn."""
    seed = 7000 + (day.toordinal() if day else 0) % 1000
    spec = maps[seed % len(maps)]
    m = TreasureMap(seed, spec["name"], spec["landmarks"], number=0)
    c, r = m.order()[seed % (GRID * GRID)]
    return {
        "label": "Map ?  ·  piece ? of 9",
        "brief": (f"The scrap printed today is a FORGERY, made by you from memory of the real "
                  f"thing: it looks like the map of {m.name}, grid square {'ABC'[c]}{r + 1}, "
                  f"showing {m.contents(c, r)}, and it fits nothing the crew have. Log how "
                  f"they came by it as if it were real."),
        "body": "DAY 1: Found a scrap.\nDAY 2: It is a map.\nDAY 3: It is definitely a map.",
        "fine": "This is a real map piece.",
        "svg": piece_svg(m, c, r),
        "piece": 0,
        "final": 0,
    }


def piece_for(spec: dict, turn: int, day=None, number=None, store=None, name="") -> dict:
    """Today's piece, as a block pick: the drawing, what is on it for the
    narrator, a heading, and an offline log (main.today_block)."""
    maps = spec.get("maps") or []
    if not maps:
        return {}
    if spec.get("worn"):
        return _forgery(maps, day)
    pieces = GRID * GRID
    index, k = divmod(turn, pieces)
    m = map_for(maps, index)
    c, r = m.order()[k]
    first, last = k == 0, k == pieces - 1
    # Days at sea: the Salt Widow has been out so long nobody remembers the port,
    # so the count starts high and runs from the First Mate's first morning.
    at_sea = 1200
    if store is not None and day is not None:
        try:
            began = store.persona_history(name).get("first")
            if began:
                from datetime import date as Date
                at_sea += (day - Date.fromisoformat(began)).days
        except Exception:  # noqa: BLE001 - a guess at the day is still a day
            pass
    marks = ", ".join(s["name"] for s, _ in m.marks)
    status = ("This is the FIRST piece of a new map: the log tells how they came by it - where the "
              "scrap turned up, who had it, what it cost them." if first else
              "This is the LAST piece, and the X is on it: they went ashore today and dug, and the log "
              "ends with what they found - gloriously disappointing, or strangely right." if last else
              "The log tells the travels since the last piece, and where this scrap turned up.")
    brief = (f"Piece {k + 1} of {pieces} of the map of {m.name} (map {m.number}), grid square "
             f"{'ABC'[c]}{r + 1}. What this piece shows: {m.contents(c, r)}. The island's landmarks: "
             f"{marks}. Today is DAY {at_sea} at sea. {status}")
    body = {
        True: f"DAY {at_sea - 9}: Traded a goat for a bottle with paper in it.\nDAY {at_sea - 4}: "
              f"The paper is a map. The goat was worth more.\nDAY {at_sea}: Course set for {m.name}.",
        False: f"DAY {at_sea - 6}: Fog. Heard bells where no bells should be.\nDAY {at_sea - 2}: "
               f"Gilly found a scrap sewn into a dead man's hat.\nDAY {at_sea}: It fits the others. Mostly.",
    }[first]
    if last:
        body = (f"DAY {at_sea - 3}: Sighted {m.name}.\nDAY {at_sea - 1}: Ashore. Followed the dots.\n"
                f"DAY {at_sea}: Dug at the X. Found a smaller box, and a note saying sorry.")
    return {
        "label": f"Map {ROMAN[(m.number - 1) % len(ROMAN)]}  ·  piece {k + 1} of {pieces}",
        "brief": brief,
        "body": body,
        "fine": "Whoever finds this: do not trust the crab." if not last else "Keep digging. That is what the note said.",
        "svg": piece_svg(m, c, r),
        "piece": k + 1,
        "final": int(last),
    }
