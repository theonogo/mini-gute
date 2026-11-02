"""Slot 16 - Micro-maze.

A perfect maze, generated locally, with the solution printed upside-down at the
footer under the house rule for puzzles (SLOTS.md, PUZZLES).

"Perfect" means fully connected with no loops: exactly one path between any two
cells. That is a property of the generator rather than something checked
afterwards - randomised depth-first search only ever carves into unvisited
cells, so it cannot close a loop. It also means the solution is unique without
having to prove it, and that a plain breadth-first search recovers it.

Randomised DFS specifically, rather than Prim's or Kruskal's, because it
produces long winding corridors and few short branches. The others make mazes
that are technically harder and feel like a lattice; this one feels like a maze.

Walls are drawn at 3px. On thermal paper a 1px line is legible but breaks up
under a moving head, and a maze with a gap in a wall is not a maze.
"""

from __future__ import annotations

import random

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

COLS, ROWS = 15, 11
CELL = 30
WALL = 3
SOLUTION_CELL = 15     # the footer copy, small enough to sit under the fold

# 15x11 at 30px is 450x330, about 41mm tall - big enough to trace with a pen,
# small enough not to crowd the rest of the page. Cell size is the thing to
# move here, not the cell count: fewer cells makes it stop reading as a maze
# long before 30px stops being a comfortable corridor.

N, E, S, W = 1, 2, 4, 8
_OPPOSITE = {N: S, S: N, E: W, W: E}
_STEP = {N: (0, -1), S: (0, 1), E: (1, 0), W: (-1, 0)}


def carve(cols: int, rows: int, rng: random.Random) -> list[list[int]]:
    """A perfect maze as a grid of open-direction bitmasks."""
    open_dirs = [[0] * cols for _ in range(rows)]
    seen = [[False] * cols for _ in range(rows)]
    stack = [(0, 0)]
    seen[0][0] = True

    while stack:
        x, y = stack[-1]
        options = []
        for d, (dx, dy) in _STEP.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < cols and 0 <= ny < rows and not seen[ny][nx]:
                options.append((d, nx, ny))
        if not options:
            stack.pop()
            continue
        d, nx, ny = rng.choice(options)
        open_dirs[y][x] |= d
        open_dirs[ny][nx] |= _OPPOSITE[d]
        seen[ny][nx] = True
        stack.append((nx, ny))
    return open_dirs


def solve(grid: list[list[int]], cols: int, rows: int) -> list[tuple[int, int]]:
    """The one path from top-left to bottom-right, by breadth-first search."""
    start, goal = (0, 0), (cols - 1, rows - 1)
    prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue = [start]
    while queue:
        cell = queue.pop(0)
        if cell == goal:
            break
        x, y = cell
        for d, (dx, dy) in _STEP.items():
            if not grid[y][x] & d:
                continue
            nxt = (x + dx, y + dy)
            if nxt not in prev:
                prev[nxt] = cell
                queue.append(nxt)

    path: list[tuple[int, int]] = []
    node: tuple[int, int] | None = goal
    while node is not None:
        path.append(node)
        node = prev[node]
    return list(reversed(path))


def _walls(grid: list[list[int]], cols: int, rows: int, cell: int,
           wall: int) -> list[str]:
    """Wall segments, with the entrance and exit left open."""
    out = [f'<rect x="0" y="0" width="{cols * cell + wall}" '
           f'height="{rows * cell + wall}" fill="#fff"/>']

    def line(x1: float, y1: float, x2: float, y2: float) -> str:
        return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000" '
                f'stroke-width="{wall}" stroke-linecap="square"/>')

    half = wall / 2
    for y in range(rows):
        for x in range(cols):
            px, py = x * cell + half, y * cell + half
            mask = grid[y][x]
            # Entrance in the top of (0,0), exit through the bottom of the last
            # cell. Without these the maze is a sealed box.
            if not mask & N and not (x == 0 and y == 0):
                out.append(line(px, py, px + cell, py))
            if not mask & W:
                out.append(line(px, py, px, py + cell))
            if y == rows - 1 and not (x == cols - 1):
                out.append(line(px, py + cell, px + cell, py + cell))
            if x == cols - 1:
                out.append(line(px + cell, py, px + cell, py + cell))
    return out


def maze_svg(grid: list[list[int]], cols: int, rows: int, cell: int = CELL,
             path: list[tuple[int, int]] | None = None) -> str:
    # The solution copy inverts the usual weights: hairline walls, fat path.
    # Drawn at the same 3px as the puzzle, the route is indistinguishable from
    # the corridors and the answer reads as a second maze.
    wall = WALL if path is None else 1
    w, h = cols * cell + wall, rows * cell + wall
    parts = _walls(grid, cols, rows, cell, wall)

    if path:
        half = wall / 2
        pts = " ".join(f"{x * cell + cell / 2 + half:.1f},"
                       f"{y * cell + cell / 2 + half:.1f}" for x, y in path)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="#000" '
                     f'stroke-width="{cell * 0.5:.1f}" stroke-linejoin="round" '
                     f'stroke-linecap="round"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">' + "".join(parts) + "</svg>")


@register
class MicroMaze(Slot):
    spec = SlotSpec(id=16, name="Micro-maze", tier="uncommon", paper_mm=85,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        grid = carve(COLS, ROWS, rng)
        path = solve(grid, COLS, ROWS)
        return SlotResult(
            head="Micro-maze",
            body=maze_svg(grid, COLS, ROWS),
            fine="In at the top left, out at the bottom right.",
            answer=maze_svg(grid, COLS, ROWS, cell=SOLUTION_CELL, path=path),
            brief={"verbatim": True,
                   "size": f"{COLS} by {ROWS}",
                   "path_length": len(path),
                   "instruction": "Name this section in voice. The maze is a "
                                  "drawing and prints as it is; do not describe "
                                  "the route."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
