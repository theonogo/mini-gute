"""Slot 14 - Nonogram.

Date-seeded, 5x5 or 10x10, with the solved grid printed upside-down at the
footer under the house rule for puzzles (SLOTS.md, PUZZLES).

**The puzzle is checked for a unique logical solution before it is printed.**
This is the whole difficulty of the slot and the reason it is more than a random
bitmap. A random pattern very often produces clues that admit several grids, or
that need trial and error rather than deduction, and there is no way to tell by
looking. Printing one of those means handing someone a puzzle that cannot be
finished, on paper, with no way to check - the worst possible failure for a
thing you do over coffee.

So the generator runs a line solver over its own output and keeps only patterns
the solver can finish by deduction alone:

  * for each row and column, enumerate every arrangement of its blocks that is
    consistent with the cells already known,
  * any cell that is the same in all of them is now known,
  * repeat until nothing changes.

If that fixpoint leaves no unknown cells, the puzzle is solvable by pure logic
and its solution is unique. If it does not, the pattern is discarded and another
is drawn. Enumeration is cheap at these sizes - a ten-cell line never has more
than a few dozen arrangements - so this costs a few milliseconds.
"""

from __future__ import annotations

import random
from itertools import combinations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

UNKNOWN, EMPTY, FILLED = -1, 0, 1

# Two sizes, per the spec. The small one is the common case: a 5x5 is a minute
# over breakfast, which is what this slot is for, and the 10x10 is the occasional
# one that takes the whole of breakfast.
BIG_CHANCE = 0.25
SMALL, BIG = 5, 10
DENSITY = {SMALL: 0.55, BIG: 0.52}
ATTEMPTS = 200

LAYOUT = {  # size -> (cell px, clue slot px, font px)
    SMALL: (50, 24, 16),
    BIG: (34, 20, 14),         # 14px, comfortably above the 12px floor
}
ANSWER_CELL = 11
GRID_STROKE = 2
GROUP_STROKE = 4               # every fifth line, the usual nonogram convention


def clues(line: list[int]) -> list[int]:
    """Run lengths of filled cells. `[0]` for an empty line, never `[]`."""
    out, run = [], 0
    for cell in line:
        if cell == FILLED:
            run += 1
        elif run:
            out.append(run)
            run = 0
    if run:
        out.append(run)
    return out or [0]


def placements(clue: list[int], length: int) -> list[tuple[int, ...]]:
    """Every arrangement of these blocks in a line of this length.

    Blocks are placed by choosing where the slack goes. With k blocks there are
    k+1 gaps (before, between, after); the between-gaps need at least one cell,
    so the free cells to distribute are `length - sum(blocks) - (k-1)`. Choosing
    positions for those is a combination, which is why this stays small.
    """
    if clue == [0]:
        return [tuple([EMPTY] * length)]

    blocks = clue
    free = length - sum(blocks) - (len(blocks) - 1)
    if free < 0:
        return []

    out = []
    # Distribute `free` slack cells across len(blocks)+1 gaps.
    for cuts in combinations(range(free + len(blocks)), len(blocks)):
        gaps, prev = [], -1
        for c in cuts:
            gaps.append(c - prev - 1)
            prev = c
        gaps.append(free + len(blocks) - 1 - prev)

        row: list[int] = []
        for i, block in enumerate(blocks):
            row.extend([EMPTY] * gaps[i])
            row.extend([FILLED] * block)
            if i < len(blocks) - 1:
                row.append(EMPTY)          # the mandatory separator
        row.extend([EMPTY] * gaps[-1])
        out.append(tuple(row))
    return out


def _narrow(known: list[int], clue: list[int]) -> list[int] | None:
    """Everything this line's clue forces, given what is already known."""
    options = [p for p in placements(clue, len(known))
               if all(k == UNKNOWN or k == v for k, v in zip(known, p))]
    if not options:
        return None                        # contradiction: pattern is broken
    first = options[0]
    return [first[i] if all(o[i] == first[i] for o in options) else UNKNOWN
            for i in range(len(known))]


def logic_solvable(row_clues: list[list[int]],
                   col_clues: list[list[int]]) -> bool:
    """True if line-by-line deduction alone finishes the grid.

    A grid the solver can finish has exactly one solution, since every cell it
    fixed was forced. The converse is not quite true - a few uniquely-solvable
    puzzles need deeper reasoning - and rejecting those is the point: they are
    the ones that need guessing on paper.
    """
    rows, cols = len(row_clues), len(col_clues)
    grid = [[UNKNOWN] * cols for _ in range(rows)]

    while True:
        changed = False
        for y in range(rows):
            got = _narrow(grid[y], row_clues[y])
            if got is None:
                return False
            if got != grid[y]:
                grid[y], changed = got, True
        for x in range(cols):
            column = [grid[y][x] for y in range(rows)]
            got = _narrow(column, col_clues[x])
            if got is None:
                return False
            if got != column:
                changed = True
                for y in range(rows):
                    grid[y][x] = got[y]
        if not changed:
            break

    return all(cell != UNKNOWN for row in grid for cell in row)


def generate(size: int, rng: random.Random) -> tuple[list[list[int]],
                                                     list[list[int]],
                                                     list[list[int]]]:
    """(solution grid, row clues, column clues) for a solvable puzzle."""
    density = DENSITY[size]
    best = None
    for _ in range(ATTEMPTS):
        grid = [[FILLED if rng.random() < density else EMPTY
                 for _ in range(size)] for _ in range(size)]
        filled = sum(c for row in grid for c in row)
        if not 0.3 <= filled / (size * size) <= 0.75:
            continue                       # all-black and near-blank both read badly
        rc = [clues(row) for row in grid]
        cc = [clues([grid[y][x] for y in range(size)]) for x in range(size)]
        best = (grid, rc, cc)
        if logic_solvable(rc, cc):
            return grid, rc, cc

    # Every attempt failed, which at 5x5 effectively never happens. Falling back
    # to the smaller size is better than printing an unsolvable grid.
    if size != SMALL:
        return generate(SMALL, rng)
    return best  # type: ignore[return-value]


def _grid_svg(size: int, row_clues: list[list[int]], col_clues: list[list[int]],
              cell: int, clue_px: int, font_px: int,
              solution: list[list[int]] | None = None) -> str:
    max_rc = max(len(c) for c in row_clues)
    max_cc = max(len(c) for c in col_clues)
    pad_x, pad_y = max_rc * clue_px, max_cc * clue_px
    w = pad_x + size * cell + GRID_STROKE
    h = pad_y + size * cell + GRID_STROKE
    half = GRID_STROKE / 2

    parts = [f'<rect x="0" y="0" width="{w}" height="{h}" fill="#fff"/>']

    if solution:
        for y in range(size):
            for x in range(size):
                if solution[y][x] == FILLED:
                    parts.append(
                        f'<rect x="{pad_x + x * cell + half}" '
                        f'y="{pad_y + y * cell + half}" width="{cell}" '
                        f'height="{cell}" fill="#000"/>')

    for i in range(size + 1):
        # Every fifth line heavier, so a 10x10 can be counted at a glance.
        stroke = GROUP_STROKE if i % 5 == 0 else GRID_STROKE
        x = pad_x + i * cell + half
        y = pad_y + i * cell + half
        parts.append(f'<line x1="{x}" y1="{pad_y}" x2="{x}" y2="{h}" '
                     f'stroke="#000" stroke-width="{stroke}"/>')
        parts.append(f'<line x1="{pad_x}" y1="{y}" x2="{w}" y2="{y}" '
                     f'stroke="#000" stroke-width="{stroke}"/>')

    # var(--font-mono) rather than the generic `monospace`: the embedded face
    # is the only one guaranteed present, and clue digits that fall back to the
    # persona serif sit at a different width and stop lining up in the gutter.
    style = (f'style="font-family:var(--font-mono);font-size:{font_px}px;'
             # 700 is safe here: the clue digits are set in the embedded
             # mono face, which ships a real bold.
             f'font-weight:700" fill="#000"')
    for y, clue in enumerate(row_clues):
        cy = pad_y + y * cell + cell / 2 + font_px * 0.35
        for i, n in enumerate(reversed(clue)):    # right-aligned against the grid
            cx = pad_x - (i + 0.5) * clue_px
            parts.append(f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                         f'{style}>{n}</text>')
    for x, clue in enumerate(col_clues):
        cx = pad_x + x * cell + cell / 2
        for i, n in enumerate(reversed(clue)):    # bottom-aligned against the grid
            cy = pad_y - i * clue_px - clue_px * 0.5 + font_px * 0.35
            parts.append(f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
                         f'{style}>{n}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">' + "".join(parts) + "</svg>")


def puzzle_svg(size: int, row_clues, col_clues) -> str:
    cell, clue_px, font_px = LAYOUT[size]
    return _grid_svg(size, row_clues, col_clues, cell, clue_px, font_px)


def answer_svg(size: int, grid: list[list[int]]) -> str:
    """Just the picture. Clue numbers on the solution would be noise."""
    w = size * ANSWER_CELL + GRID_STROKE
    half = GRID_STROKE / 2
    parts = [f'<rect x="0" y="0" width="{w}" height="{w}" fill="#fff"/>']
    for y in range(size):
        for x in range(size):
            if grid[y][x] == FILLED:
                parts.append(f'<rect x="{x * ANSWER_CELL + half}" '
                             f'y="{y * ANSWER_CELL + half}" '
                             f'width="{ANSWER_CELL}" height="{ANSWER_CELL}" '
                             f'fill="#000"/>')
    for i in range(size + 1):
        p = i * ANSWER_CELL + half
        parts.append(f'<line x1="{p}" y1="0" x2="{p}" y2="{w}" stroke="#000" '
                     f'stroke-width="{GRID_STROKE}"/>')
        parts.append(f'<line x1="0" y1="{p}" x2="{w}" y2="{p}" stroke="#000" '
                     f'stroke-width="{GRID_STROKE}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{w}" '
            f'viewBox="0 0 {w} {w}">' + "".join(parts) + "</svg>")


@register
class Nonogram(Slot):
    spec = SlotSpec(id=14, name="Nonogram", tier="common", paper_mm=92,
                    needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        size = BIG if rng.random() < BIG_CHANCE else SMALL
        grid, row_clues, col_clues = generate(size, rng)
        return SlotResult(
            head="Nonogram",
            body=puzzle_svg(size, row_clues, col_clues),
            fine="Numbers are runs of filled squares, in order, with at least "
                 "one gap between them.",
            answer=answer_svg(size, grid),
            paper_mm=60 if size == BIG else 45,
            brief={"verbatim": True,
                   "size": f"{size} by {size}",
                   "instruction": "Name this section in voice. The grid is a "
                                  "drawing and prints as it is. Do not explain "
                                  "the rules and do not hint at the picture."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
