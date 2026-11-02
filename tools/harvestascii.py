"""Harvest ASCII art from asciiart.eu into assets/ascii/harvested.json.

Slot 26 reads that file, so the morning run never touches the network. This
fills it, once, and again whenever `assets/ascii/sources.toml` gains a tag.

**Tagged by where it was filed.** `sources.toml` maps each persona art tag to the
asciiart.eu sub-categories that suit it - `nautical` gets boats, anchors and
lighthouses - so a piece carries every tag whose sub-categories it was found in,
plus any `[title_tags]` its own title earns. Categories are a person's judgement
about what a piece is, which is a better tag than anything guessed from the
characters.

**Filtered for the paper, not the screen.** A piece is kept only if it is pure
ASCII, fits the page at or above the 12px type floor, is tall enough to be a
picture rather than a speck, and has enough dense characters to survive the page
threshold - art drawn entirely in dots and apostrophes prints faint. Dimensions
are measured from the cleaned art, never taken from the site's attributes.

**Kept to what belongs on a breakfast table.** The archive is decades of Usenet
and some of it is crude. Categories that lean that way are simply not in
`sources.toml`, and `SKIP_TITLE` catches the rest by title. Both filters are
re-applied to the whole pack on every run, so tightening one prunes pieces
already harvested without refetching anything.

**Polite.** robots.txt allows the gallery. One page every few seconds, a named
User-Agent, and it stops at the first refusal rather than retrying round it.
Resumable: pages already harvested are skipped unless `--refresh`.

    python tools/harvestascii.py              # everything in sources.toml
    python tools/harvestascii.py --gap 8      # gentler
    python tools/harvestascii.py --refresh    # refetch every page
    python tools/harvestascii.py --status     # counts per tag
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slots.ascii_art import (HARVEST, MAX_COLS, MAX_ROWS,  # noqa: E402
                             MIN_COLS, MIN_ROWS)

SOURCES = HARVEST.parent / "sources.toml"
BASE = "https://www.asciiart.eu"
UA = "quick-guthe/0.1 (personal receipt printer; small one-off harvest)"

# Characters that carry enough ink to survive the page threshold. A piece whose
# visible characters are mostly the light ones prints as a faint scatter.
LIGHT = set(".'`,-:~")
MIN_DENSE_SHARE = 0.25
# Art shaded with letters and digits ("sRfkgvc+rsnm") is a photo converted to
# text. At receipt size it reads as a jumble of characters, not a picture.
MAX_ALNUM_SHARE = 0.45

SKIP_TITLE = re.compile(r"\bsex|\bnud(e|ist|ity)\b|naked|breast|boob|\bbutts?\b|bikini|"
                        r"lingerie|playboy|body says|porn|erotic|\bdrugs?\b|"
                        r"prozac|cocaine|marijuana|\bweed\b|middle finger", re.I)

_CARD = re.compile(
    r'data-id="(?P<id>[0-9a-f]+)" data-title="(?P<title>[^"]*)" '
    r'data-artist="(?P<artist>[^"]*)".*?'
    r'art-card__stats mt-1">(?P<kind>[^&<]*)&middot;.*?'
    r'<div class="art-card__ascii">(?P<art>.*?)</div></div></div>',
    re.S)


class Refused(Exception):
    """The site said no. Stop, do not work round it."""


def fetch(path: str) -> str | None:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None                     # a renamed sub-category, skip it
        raise Refused(f"{path}: HTTP {e.code}") from e


def clean(raw: str) -> str | None:
    """Unescaped, tab-expanded, right-trimmed, dedented art. None if not ASCII."""
    text = html.unescape(raw).expandtabs(8)
    if re.search(r"<[a-z/]", text) or any(ord(c) > 126 for c in text):
        return None                         # coloured markup or non-ASCII
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return None
    indent = min(len(ln) - len(ln.lstrip()) for ln in lines if ln)
    return "\n".join(ln[indent:] for ln in lines)


def printable(art: str) -> bool:
    lines = art.split("\n")
    cols, rows = max(map(len, lines)), len(lines)
    if not (MIN_COLS <= cols <= MAX_COLS and MIN_ROWS <= rows <= MAX_ROWS):
        return False
    ink = [c for c in art if not c.isspace()]
    if not ink:
        return False
    dense = sum(c not in LIGHT for c in ink) / len(ink)
    alnum = sum(c.isalnum() for c in ink) / len(ink)
    return dense >= MIN_DENSE_SHARE and alnum <= MAX_ALNUM_SHARE


def keep(piece: dict) -> bool:
    return printable(piece["art"]) and not SKIP_TITLE.search(piece["title"])


def parse(page: str) -> list[dict]:
    out = []
    for m in _CARD.finditer(page):
        if m["kind"].strip() != "Pure ASCII":
            continue
        art = clean(m["art"])
        if art is None:
            continue
        artist = html.unescape(m["artist"]).strip()
        piece = {
            "id": m["id"],
            "title": html.unescape(m["title"]).strip(),
            "artist": None if artist.lower() in ("", "unknown") else artist,
            "art": art,
        }
        if keep(piece):
            out.append(piece)
    return out


def harvest_page(page: str, gap: float) -> tuple[list[dict], bool]:
    """(pieces, found). Some sub-categories are only an index of deeper pages -
    insects is ants, bees, butterflies - so their children are read too, one
    level down, and filed under the page `sources.toml` names."""
    body = fetch(page)
    if body is None:
        return [], False
    pieces = parse(body)
    children = sorted(set(re.findall(rf'href="/{re.escape(page)}/([a-z0-9-]+)"',
                                     body)))
    for child in children:
        time.sleep(gap)
        sub = fetch(f"{page}/{child}")
        if sub:
            pieces += parse(sub)
    return pieces, True


def load() -> dict:
    if HARVEST.exists():
        return json.loads(HARVEST.read_text(encoding="utf-8"))
    return {"source": BASE, "pages": {}, "pieces": {}}


def save(data: dict) -> None:
    data["harvested"] = date.today().isoformat()
    tmp = HARVEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(HARVEST)


def retag(data: dict, sources: dict) -> None:
    """Recompute every piece's tags from the pages it was found on, and drop
    pieces that fail today's filters or whose pages are no longer listed."""
    by_page: dict[str, set[str]] = {}
    for tag, pages in sources["tags"].items():
        for page in pages:
            by_page.setdefault(page, set()).add(tag)
    for pid, piece in list(data["pieces"].items()):
        piece["categories"] = [c for c in piece["categories"] if c in by_page]
        if (not piece["categories"] or not keep(piece)
                or pid in sources.get("skip", [])):
            del data["pieces"][pid]
    data["pages"] = {p: n for p, n in data["pages"].items() if p in by_page}
    title_tags = sources.get("title_tags", {})
    for piece in data["pieces"].values():
        tags = set()
        for page in piece["categories"]:
            tags |= by_page.get(page, set())
        title = piece["title"].lower()
        for tag, words in title_tags.items():
            if any(re.search(rf"\b{re.escape(w)}", title) for w in words):
                tags.add(tag)
        piece["tags"] = sorted(tags)


def status(data: dict) -> int:
    pieces = data["pieces"].values()
    print(f"{len(data['pieces'])} pieces from {len(data['pages'])} pages")
    counts = Counter(t for p in pieces for t in p["tags"])
    for tag, n in sorted(counts.items(), key=lambda kv: kv[1]):
        print(f"  {tag:10} {n}")
    credited = sum(1 for p in pieces if p["artist"])
    print(f"credited: {credited}, unknown artist: {len(data['pieces']) - credited}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=4,
                    help="seconds between pages (default 4)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    sources = tomllib.loads(SOURCES.read_text(encoding="utf-8"))
    data = load()
    if args.status:
        return status(data)

    pages = sorted({p for ps in sources["tags"].values() for p in ps})
    todo = [p for p in pages if args.refresh or p not in data["pages"]]
    print(f"{len(pages)} pages in sources.toml, {len(todo)} to fetch")
    code = 0
    for i, page in enumerate(todo):
        try:
            found, exists = harvest_page(page, args.gap)
        except (Refused, urllib.error.URLError, TimeoutError) as e:
            print(f"stopping: {e}")
            code = 1
            break
        for piece in found:
            entry = data["pieces"].setdefault(piece["id"],
                                              {**piece, "categories": []})
            if page not in entry["categories"]:
                entry["categories"].append(page)
        data["pages"][page] = len(found)
        print(f"  {page:45} {len(found):3} kept"
              + ("" if exists else "  (404)"))
        if i % 10 == 9:
            retag(data, sources)
            save(data)
        if i < len(todo) - 1:
            time.sleep(args.gap)

    retag(data, sources)
    save(data)
    status(data)
    return code


if __name__ == "__main__":
    sys.exit(main())
