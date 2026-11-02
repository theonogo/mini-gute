"""Download persona candidate fonts from Google Fonts.

Fetched once into `assets/fonts/` and committed, so the morning run never
depends on the network for typography. Each face is embedded into the page as a
base64 @font-face at render time - `page.set_content()` has no base URL, so
relative font paths would not resolve.

Only the day's persona font gets embedded, not the whole library.

Families already on disk are kept, not re-downloaded. The type scale and the
page threshold were measured against these exact files, and Google does revise
fonts - a silent re-fetch could move a measured face. `--refresh` re-fetches
everything anyway.

    python tools/getfonts.py
    python tools/getfonts.py --refresh
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "assets" / "fonts"

# Chosen for 203dpi survival and for having distinct personalities. The point of
# a font here is to *be* a voice, so the pool is deliberately varied rather than
# five flavours of the same clean mono.
FAMILIES = {
    "JetBrains Mono":   "wght@400;700",   # mono workhorse, very legible small
    "IBM Plex Mono":    "wght@400;700",   # mono with more character
    "Inter":            "wght@400;700",   # sans workhorse
    "Courier Prime":    "wght@400;700",   # typewriter - ship's log, clerk
    # The clerk. The italic is not decoration: his dateline, his asides, his
    # fine print and his warrant's terms are all set in it, and a face with no
    # italic file prints every one of them upright (font-synthesis: none).
    "Libre Baskerville": "ital,wght@0,400;0,700;1,400",
    "VT323":            None,             # terminal - ops officer
    "Special Elite":    None,             # distressed typewriter - detective

    # The persona faces (personas.toml). Body faces take a 700 wherever one
    # exists, since reversed-out text needs the heaviest honest weight; display
    # and accent faces are mostly single-weight by nature.
    "Playfair Display SC":   "wght@400;700",   # clerk display
    "Pinyon Script":         None,             # clerk signatures
    "Chakra Petch":          "wght@400;700",   # ops display
    "Almendra":              "wght@400;700",   # oracle
    "Grenze Gotisch":        "wght@400;700",
    "Uncial Antiqua":        None,
    "IBM Plex Sans":         "wght@400;700",   # accounts receivable
    "IBM Plex Sans Condensed": "wght@400;700",
    "IM Fell English":       None,             # first mate - 400 only
    "Pirata One":            None,
    "Rye":                   None,
    "Rubik Distressed":      None,             # detective stamps
    "Caveat":                "wght@400;700",   # detective pencil
    "Zilla Slab":            "wght@400;700",   # all-nite diner
    "Shrikhand":             None,
    "Kalam":                 "wght@400;700",
    "Libre Caslon Text":     "ital,wght@0,400;0,700;1,400",   # stage manager -
                                               # with the italic stage directions need
    "Abril Fatface":         None,
    "Oswald":                "wght@400;700",
    "Barlow":                "wght@400;700",   # commentary box
    "Barlow Condensed":      "wght@400;700",
    "Alfa Slab One":         None,
    "Space Mono":            "wght@400;700",   # monkey astronaut
    "Jost":                  "wght@400;700",
    "Gochi Hand":            None,
    "Archivo Narrow":        "wght@400;700",   # daily roll
    "Anton":                 None,
    "Archivo Black":         None,
    "Doto":                  "wght@400;700;900",  # the machine - reads only at 900
    "Silkscreen":            "wght@400;700",
    "Space Grotesk":         "wght@400;700",   # time traveller
    "Orbitron":              "wght@400;700",
    "Major Mono Display":    None,
    "Rubik Glitch":          None,             # mimic
    "Kablammo":              None,             # replaced Rubik Microbe, unreadable
    "Saira Stencil One":     None,             # revolutionary - replaced Stardos,
                                               # whose stencil cuts vanished at size
    "Rock Salt":             None,

    # The bootleg tape, in audition: an inlay-card grotesque, a spine
    # face for the fat condensed caps, and a mono for the tracklist.
    "Archivo":               "wght@400;700",
    "Bebas Neue":            None,
    "Roboto Mono":           "wght@400;700",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def css_url(family: str, axis: str | None) -> str:
    name = family.replace(" ", "+")
    spec = f"{name}:{axis}" if axis else name
    return f"https://fonts.googleapis.com/css2?family={spec}&display=swap"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    refresh = "--refresh" in sys.argv
    existing_path = DEST / "manifest.json"
    existing = (json.loads(existing_path.read_text())
                if existing_path.exists() else {})
    manifest: dict[str, list[str]] = {}

    for family, axis in FAMILIES.items():
        have = existing.get(family, [])
        if have and not refresh and all((DEST / f).exists() for f in have):
            manifest[family] = have
            continue
        try:
            css = fetch(css_url(family, axis)).decode("utf-8")
        except Exception as exc:
            print(f"  SKIP {family}: {exc}")
            continue

        # Latin subset only; the receipt is English.
        blocks = css.split("@font-face")
        files: list[str] = []
        seen: set[str] = set()
        for block in blocks:
            if "unicode-range" in block and "U+0000-00FF" not in block:
                continue
            m = re.search(r"url\((https://[^)]+\.woff2)\)", block)
            w = re.search(r"font-weight:\s*(\d+)", block)
            italic = re.search(r"font-style:\s*italic", block) is not None
            if not m:
                continue
            weight = w.group(1) if w else "400"
            slug = family.lower().replace(" ", "-")
            name = f"{slug}-{weight}{'italic' if italic else ''}.woff2"
            if name in seen:
                continue
            seen.add(name)
            (DEST / name).write_bytes(fetch(m.group(1)))
            files.append(name)

        if files:
            manifest[family] = sorted(files)
            print(f"  {family}: {', '.join(files)}")
        else:
            print(f"  SKIP {family}: no latin face found")

    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2))
    total = sum(len(v) for v in manifest.values())
    size = sum(f.stat().st_size for f in DEST.glob("*.woff2"))
    print(f"\n{total} faces, {len(manifest)} families, {size / 1024:.0f} KB")
    print(f"-> {DEST}")
    if not manifest:
        sys.exit(1)


if __name__ == "__main__":
    main()
