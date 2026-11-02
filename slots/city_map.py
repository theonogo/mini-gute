"""Slot 62 - Growing city map.

The neighbourhood around home, printed one tile a morning for 25 mornings and
assembled on a wall. The first series on the series engine (`slots/series.py`).

**It grows outwards from home.** Tiles are laid on a 5x5 grid and printed in a
spiral from the centre, so the first tile is the street you live on and every
morning after adds a ring of city around it. Reading order would spend its first
week on a corner nobody walks to.

**Each tile is four OpenStreetMap tiles at zoom 17**, composed to 512px - about
400m of city a side, which puts street names at a size the head can print. The
whole map is roughly two kilometres square. Every tile is labelled with its
grid reference and has corner marks, so assembly needs no guessing.

**OpenStreetMap's tile policy is followed, not worked around**: an identifying
User-Agent, four tiles a morning, every tile cached on disk forever and never
fetched twice, and the attribution printed on every piece. The home location
comes from `.env` and never touches the repo; the offline fixture is a drawn
street grid, not a real place.

**Dithered, not thresholded.** OSM's standard style is soft colour fills -
buildings, parks, water - and a threshold would flatten them all to white.
Dithered before embedding, per invariant 2.
"""

from __future__ import annotations

import math
from pathlib import Path

from .base import Context, SlotResult, SlotSpec
from .registry import register
from .series import SeriesSlot

ZOOM = 17
GRID = 5                       # printed tiles per side
SUB = 2                        # OSM tiles per printed tile, per side
TILE_PX = 256 * SUB
TILES = Path(__file__).resolve().parent.parent / "data" / "tiles"
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
CONTRAST = 1.6


def spiral(grid: int = GRID) -> list[tuple[int, int]]:
    """(col, row) from the centre outwards, one ring at a time."""
    c = grid // 2
    cells = [(col, row) for row in range(grid) for col in range(grid)]
    return sorted(cells, key=lambda p: (max(abs(p[0] - c), abs(p[1] - c)),
                                        math.atan2(p[1] - c, p[0] - c)))


def ref(col: int, row: int) -> str:
    return f"{'ABCDEFGH'[col]}{row + 1}"


def home_tile(lat: float, lon: float, zoom: int = ZOOM) -> tuple[int, int]:
    n = 2 ** zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(x), int(y)


def osm_tile(z: int, x: int, y: int, offline: bool):
    """One OSM tile, from the disk cache or - once, ever - the network."""
    from PIL import Image
    path = TILES / str(z) / str(x) / f"{y}.png"
    if not path.exists():
        if offline:
            raise FileNotFoundError(path)
        from sources.http import get_bytes
        blob = get_bytes(TILE_URL.format(z=z, x=x, y=y), accept="image/png")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    return Image.open(path).convert("L")


_CSS = """
<style>
.map-tile { position: relative; width: 512px; margin: 6px auto 0; }
.map-tile img { margin: 0 auto; }
.map-mark { position: absolute; width: 16px; height: 16px; border: 0 solid #000; }
.map-mark.tl { left: -10px; top: -10px; border-width: 3px 0 0 3px; }
.map-mark.tr { right: -10px; top: -10px; border-width: 3px 3px 0 0; }
.map-mark.bl { left: -10px; bottom: -10px; border-width: 0 0 3px 3px; }
.map-mark.br { right: -10px; bottom: -10px; border-width: 0 3px 3px 0; }
.map-info { display: flex; align-items: center; gap: 14px; margin-top: 16px; }
.map-ref { font-family: var(--font-mono); font-size: 44px; line-height: 1;
           border: 4px solid #000; padding: 4px 10px; }
.map-grid { display: grid; grid-template-columns: repeat(5, 13px); gap: 2px; }
.map-grid span { width: 13px; height: 13px; border: 2px solid #000;
                 box-sizing: border-box; }
.map-grid span.done { background: #000; }
.map-grid span.today { background: repeating-linear-gradient(45deg, #000 0 2px,
                        #fff 2px 5px); }
.map-count { font-size: var(--size-small); line-height: 1.3; }
</style>
"""


@register
class GrowingCityMap(SeriesSlot):
    spec = SlotSpec(id=62, name="Growing city map", tier="rare", paper_mm=100,
                    needs_network=True, needs_narrator=True, series=True)

    def tiles(self) -> int:
        return GRID * GRID

    def begin(self, ctx: Context) -> dict:
        import config
        lat, lon, _ = config.location()
        cx, cy = home_tile(lat, lon)
        # The centre printed tile covers the home OSM tile and its neighbours
        # right and below, so home is always on the first piece.
        return {"x0": cx - SUB * (GRID // 2), "y0": cy - SUB * (GRID // 2)}

    def _image(self, data: dict, col: int, row: int, offline: bool):
        from PIL import Image, ImageEnhance
        from render.dither import atkinson
        img = Image.new("L", (TILE_PX, TILE_PX), 255)
        for dx in range(SUB):
            for dy in range(SUB):
                x = data["x0"] + col * SUB + dx
                y = data["y0"] + row * SUB + dy
                img.paste(osm_tile(ZOOM, x, y, offline), (dx * 256, dy * 256))
        return atkinson(ImageEnhance.Contrast(img).enhance(CONTRAST))

    def _result(self, n: int, col: int, row: int, image) -> SlotResult:
        from render.dither import img_tag
        order = spiral()
        cells = []
        for r in range(GRID):
            for c in range(GRID):
                i = order.index((c, r)) + 1
                cls = "today" if i == n else "done" if i < n else ""
                cells.append(f'<span class="{cls}"></span>')
        marks = "".join(f'<span class="map-mark {k}"></span>'
                        for k in ("tl", "tr", "bl", "br"))
        left = self.tiles() - n
        return SlotResult(
            head="The Map",
            body=(f'{_CSS}<div class="map-tile">{marks}{img_tag(image)}</div>'
                  f'<div class="map-info"><div class="map-ref">{ref(col, row)}</div>'
                  f'<div class="map-grid">{"".join(cells)}</div>'
                  f'<div class="map-count">Piece {n} of {self.tiles()}.<br>'
                  f'{"The map is complete." if not left else f"{left} to come."}'
                  f'</div></div>'),
            fine="Map data &copy; OpenStreetMap contributors",
            brief={"verbatim": True, "piece": n, "of": self.tiles(),
                   "grid_ref": ref(col, row),
                   "instruction": "Name this section in voice. It is one piece of "
                                  "a map of the neighbourhood being assembled a "
                                  "piece a morning, growing outward from home. "
                                  "Do not name streets or places."},
        )

    def tile(self, ctx: Context, n: int, data: dict) -> SlotResult | None:
        col, row = spiral()[n - 1]
        try:
            image = self._image(data, col, row, ctx.offline)
        except Exception:  # noqa: BLE001 - no tiles: skip today, keep the series
            return None
        return self._result(n, col, row, image)

    def fixture(self, ctx: Context) -> SlotResult:
        """A drawn street grid - never a real place."""
        from PIL import Image, ImageDraw
        from render.dither import atkinson
        img = Image.new("L", (TILE_PX, TILE_PX), 236)
        draw = ImageDraw.Draw(img)
        for i, step in enumerate(range(-40, TILE_PX + 40, 70)):
            w = 18 if i % 3 == 0 else 9
            draw.line((step, 0, step + 60, TILE_PX), fill=255, width=w)
            draw.line((0, step, TILE_PX, step - 30), fill=255, width=w)
        draw.ellipse((300, 60, 460, 200), fill=190)
        return self._result(1, GRID // 2, GRID // 2, atkinson(img))
