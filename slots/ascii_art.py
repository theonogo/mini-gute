"""Slot 26 - ASCII art.

A tagged pack, matched to the day's persona. Two sources, read the same way:

  * `assets/ascii/harvested.json` - the bulk of it, harvested from asciiart.eu by
    `tools/harvestascii.py` and tagged by the site's own categories through
    `assets/ascii/sources.toml`, with the artist kept for a credit.
  * `assets/ascii/*.txt` - hand-placed pieces, added by dropping in a file (see
    the README there).

The morning run only ever reads files; nothing here touches the network.

**Matched to the persona, not chosen by Claude.** SLOTS.md describes Claude
picking the piece that fits, with a random draw as fallback. The narrator cannot
do that: it returns a header and a body string, so it has no way to hand back a
choice, and giving it one would mean a second call or a schema that can express
selection. Personas already carry `art_tags` in `personas.toml`, so the match is
configured, which is both cheaper and more predictable. Most days the piece
shares a tag with the persona; some days it does not, so the pack never splits
into private collections that never mix.

**Rendered in the embedded monospace, never the persona face, and sized to fit.**
The whole point of ASCII art is that columns line up, and the day's face may
well be a serif. A wide piece is set smaller rather than allowed to wrap -
wrapped ASCII art is ruined art - but never below the 12px floor, which is what
bounds `MAX_COLS`.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

PACK = Path(__file__).resolve().parent.parent / "assets" / "ascii"
HARVEST = PACK / "harvested.json"
HEADER_LINE = re.compile(r"^#\s*(\w+):\s*(.*)$")
NAMESPACE = "ascii"

# JetBrains Mono's advance width is exactly 0.6em, so a piece's width is
# columns * 0.6 * font-size. The section body is narrower than the 576px head -
# the template pads it - so the fit is done in CSS against the body's measured
# width (container query units), not against WIDTH_DOTS. At the 12px floor a
# column is 7.2px, and 74 columns (533px) is the widest piece that fits the
# ~540px body with room to spare.
MONO_ADVANCE_EM = 0.6
MAX_COLS = 74
MAX_ROWS = 26
# Below these a piece is a speck on the page rather than a picture.
MIN_COLS = 12
MIN_ROWS = 5

# How often the piece shares a tag with the persona, when the pack has one that
# does. High enough to feel deliberate, low enough that anyone can still draw
# anything.
MATCH_SHARE = 0.8
# Pieces printed recently are not drawn again until this many others have been.
AVOID_RECENT = 60

_CSS = """
<style>
/* Two rules here are load-bearing.

   The art is centred by centring its BOX, never its lines. `text-align:center`
   on the art itself centres each line independently, which silently destroys
   any asymmetric piece - a ship's masts drift off its hull and the whole thing
   shatters. Symmetric art survives it, so the fault hides until the first piece
   that is not symmetric. The art is therefore an inline-block that stays
   left-aligned inside a centred wrapper.

   line-height is 1 because ASCII art is drawn on a roughly square grid; the
   body's 1.35 stretches every piece vertically and breaks anything built from
   diagonals. */
.ascii-wrap { text-align: center; overflow: hidden; margin: 4px 0;
              container-type: inline-size; }
.ascii {
  display: inline-block;
  text-align: left;
  font-family: var(--font-mono);
  line-height: 1;
  white-space: pre;
}
.ascii-credit {
  text-align: right;
  font-size: var(--size-tiny);
  margin-top: 2px;
}
</style>
"""


def _hand_pieces() -> list[dict]:
    out = []
    for path in sorted(PACK.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").rstrip("\n").splitlines()
        meta: dict[str, str] = {}
        while lines and (m := HEADER_LINE.match(lines[0])):
            meta[m.group(1).lower()] = m.group(2).strip()
            lines = lines[1:]
        if not lines:
            continue
        tags = [t.strip().lower() for t in meta.get("tags", "").split(",")
                if t.strip()]
        out.append({"id": path.stem, "title": path.stem, "tags": tags,
                    "artist": meta.get("artist"), "art": "\n".join(lines)})
    return out


def _harvested() -> list[dict]:
    try:
        data = json.loads(HARVEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(data.get("pieces", {}).values())


def fits(art: str) -> bool:
    """Checked again at load, so tightening a limit needs no re-harvest."""
    lines = art.split("\n")
    return 0 < max(map(len, lines)) <= MAX_COLS and len(lines) <= MAX_ROWS


@lru_cache(maxsize=1)
def pack() -> list[dict]:
    """Every piece: id, title, tags, artist (or None), art."""
    out = [p for p in _hand_pieces() + _harvested() if fits(p.get("art", ""))]
    if not out:
        raise FileNotFoundError(f"no ASCII art in {PACK}")
    return out


def font_size_css(art: str) -> str:
    """The largest mono size, up to the house small size, that fits the body.

    `99cqi` is the section body's own width, whatever padding the template or a
    persona theme gives it; the 1% spare absorbs glyph-advance rounding.
    """
    from render.fonts import FLOOR_PX, MONO_FAMILY, small_px
    cols = max(len(line) for line in art.split("\n"))
    return (f"clamp({FLOOR_PX}px, calc(99cqi / {cols * MONO_ADVANCE_EM:.2f}), "
            f"{small_px(MONO_FAMILY)}px)")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def signed(art: str, artist: str) -> bool:
    """Is the artist's signature already drawn into the piece?

    Most old ASCII artists sign in the corner - "jgs", "LGB", "DrS" - and a
    printed credit under a signed piece says the same thing twice. Loose on
    purpose: a word of the name, or the name's initials in order inside a short
    token ("CeeJay" for C.J.). A miss only costs a redundant credit line.
    """
    names = re.findall(r"[a-z]+", artist.lower())
    groups = [names] + [re.findall(r"[a-z]+", g.lower())
                        for g in re.findall(r"\(([^)]*)\)", artist)]
    groups.append(re.findall(r"[a-z]+", artist.split("(")[0].lower()))
    initials = {"".join(w[0] for w in g) for g in groups if len(g) > 1}
    words = {w for w in names if len(w) >= 3} | {w[:3] for w in names if len(w) > 3}
    for token in re.findall(r"[a-z]+", art.lower()):
        if token in words or token in initials:
            return True
        if len(token) <= 6 and any(len(i) >= 2 and _subsequence(i, token)
                                   for i in initials):
            return True
    return False


def _subsequence(needle: str, hay: str) -> bool:
    it = iter(hay)
    return needle[0] == hay[0] and all(c in it for c in needle)


def art_html(art: str, artist: str | None = None) -> str:
    credit = (f'<div class="ascii-credit">art: {_escape(artist)}</div>'
              if artist and not signed(art, artist) else "")
    return (f'{_CSS}<div class="ascii-wrap">'
            f'<div class="ascii" style="font-size:{font_size_css(art)}">'
            f'{_escape(art)}</div></div>{credit}')


def choose(pieces: list[dict], art_tags: list[str], rng,
           avoid: set[str] = frozenset()) -> dict:
    fresh = [p for p in pieces if p["id"] not in avoid] or pieces
    wanted = {t.lower() for t in art_tags}
    matching = [p for p in fresh if wanted & set(p["tags"])]
    if matching and rng.random() < MATCH_SHARE:
        return rng.choice(matching)
    return rng.choice(fresh)


@register
class AsciiArt(Slot):
    spec = SlotSpec(id=26, name="ASCII art", tier="common", paper_mm=76,
                    needs_narrator=True)

    def _recent(self, ctx: Context) -> list[str]:
        if ctx.store is None:
            return []
        try:
            return list(ctx.store.fetch(NAMESPACE, "recent", []) or [])
        except Exception:  # noqa: BLE001 - no memory just means repeats
            return []

    def _remember(self, ctx: Context, piece_id: str, recent: list[str]) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            ctx.store.put(NAMESPACE, "recent",
                          ([piece_id] + recent)[:AVOID_RECENT])
        except Exception:  # noqa: BLE001
            pass

    def _result(self, ctx: Context) -> SlotResult:
        # The persona is drawn before slots, so its tags are available here via
        # the shared scratch space. Absent in a bare fixture, which just means
        # an unweighted draw.
        tags = ctx.shared.get("persona_art_tags", [])
        recent = self._recent(ctx)
        piece = choose(pack(), tags, ctx.rng(self.spec.id), set(recent))
        self._remember(ctx, piece["id"], recent)
        return SlotResult(
            head="Today's Engraving",
            body=art_html(piece["art"], piece.get("artist")),
            brief={"verbatim": True,
                   "subject": piece["title"] or "untitled",
                   "tags": piece["tags"],
                   "instruction": "Name this section in voice. The art is fixed "
                                  "and prints as it is; do not describe it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
