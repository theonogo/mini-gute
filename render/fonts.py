"""Font embedding for persona themes.

`page.set_content()` gives the document no base URL, so a relative `url()` in
@font-face resolves to nothing and the page silently falls back to a system
font - which looks like a styling bug and is actually a plumbing one. Faces are
therefore inlined as base64 data URIs.

Only the day's persona font is embedded, not the whole library.
"""

import base64
import json
from functools import lru_cache
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


@lru_cache(maxsize=1)
def manifest() -> dict[str, list[str]]:
    path = FONT_DIR / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing - run `python tools/getfonts.py` once to populate it")
    return json.loads(path.read_text())


def families() -> list[str]:
    return sorted(manifest())


@lru_cache(maxsize=32)
def face_css(family: str) -> str:
    """@font-face rules for one family, with the woff2 inlined."""
    files = manifest().get(family)
    if not files:
        raise KeyError(f"unknown font family {family!r}; have {families()}")

    rules = []
    for name in files:
        # "libre-caslon-text-400.woff2", or "-400italic" for a real italic -
        # the only kind a page may use, since font-synthesis is off.
        stem = name.rsplit("-", 1)[-1].split(".")[0]
        style = "italic" if stem.endswith("italic") else "normal"
        weight = stem.removesuffix("italic")
        blob = base64.b64encode((FONT_DIR / name).read_bytes()).decode()
        rules.append(
            f"@font-face{{font-family:'{family}';font-style:{style};"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{blob}) format('woff2')}}")
    return "".join(rules)


# Three-tier scale per family: (body, small, tiny) in px.
#
# The measured hardware floor is 12px (SYSTEM.md 1.1). The house scale sits
# well above it: body 19, small 17, tiny 15. Nothing anywhere prints below 12px.
#
# Sized for the 72mm page by characters per line, measured in Chromium at 576px
# (`tools/personafonts.py`). The house measure is ~65 characters at the 18px
# scale - Libre Baskerville at 18, VT323 at 22 - and every face narrower than
# that gets the size that brings it back to 65. Every tier of every face then
# goes up 1px, which read better on paper. So each size below is "back to the
# house measure, plus one".
#
# Per-family sizes exist because nominal px is a poor guide to visual size:
#   Special Elite      distressed face, broken strokes, runs small
#   VT323              pixel font, very narrow - 90 chars/line at 16px
#   Archivo Narrow     a condensed face: 90 chars/line at 18px
#   Almendra, IM Fell  calligraphic and old-style book faces, small on the body
#   Archivo            an inlay-card grotesque, and narrow with it
#   the rest           ordinary sans and slabs that simply run narrow
_SIZES: dict[str, tuple[int, int, int]] = {
    "Special Elite":     (20, 18, 16),
    "VT323":             (23, 21, 19),
    "Archivo Narrow":    (26, 24, 22),
    "Almendra":          (24, 22, 20),
    "IM Fell English":   (23, 21, 19),
    "Barlow":            (22, 20, 18),
    "Archivo":           (21, 19, 17),
    "Zilla Slab":        (22, 20, 18),
    "IBM Plex Sans":     (21, 19, 17),
    "Libre Caslon Text": (20, 18, 16),
    "Space Grotesk":     (20, 18, 16),
    "Inter":             (20, 18, 16),
}
DEFAULT_SIZES = (19, 17, 15)
FLOOR_PX = 12


def sizes(family: str) -> tuple[int, int, int]:
    """(body, small, tiny) in px. Never returns anything below FLOOR_PX."""
    scale = _SIZES.get(family, DEFAULT_SIZES)
    return tuple(max(FLOOR_PX, s) for s in scale)  # type: ignore[return-value]


def small_px(family: str) -> int:
    return sizes(family)[1]


# Embedded on every page regardless of persona, because some content is only
# correct in a fixed pitch: ASCII art, grids, anything aligned by column. The
# persona face may well be a serif, and letting these fall back to whatever
# monospace the machine happens to have makes the render non-deterministic -
# art authored to 40 columns would wrap on one box and not another.
#
# One extra face costs ~30KB of base64 per render, which is nothing against
# being sure the columns line up.
MONO_FAMILY = "JetBrains Mono"


def has_bold(family: str) -> bool:
    """Does this family ship a real 700 face?

    Many do not: Google Fonts publishes VT323, Special Elite and most display
    faces in a single weight only. Asked for 700 anyway, the browser does not decline -
    it SYNTHESISES a bold by smearing each glyph sideways. Measured at the page
    threshold (`tools/boldtest.py`), that smear adds about half again as much
    ink as the regular weight and widens the drawn stroke by 60%, without any
    of it being a heavier face. Soft smeared edges are precisely what a
    threshold turns into surplus ink, and 170 is already biased that way
    because it was picked to rescue thin strokes.
    """
    return any(name.endswith("-700.woff2") for name in manifest().get(family, []))


def bold_weight(family: str) -> int:
    """The heaviest weight this family can honestly render."""
    return 700 if has_bold(family) else 400


def mono_face_css() -> str:
    return face_css(MONO_FAMILY)


def mono_stack() -> str:
    return stack(MONO_FAMILY)


def stack(family: str) -> str:
    """A CSS font stack with a sane fallback if the face fails to load."""
    generic = ("serif" if family in ("Libre Baskerville",)
               else "sans-serif" if family in ("Inter", "Special Elite")
               else "monospace")
    return f"'{family}', {generic}"
