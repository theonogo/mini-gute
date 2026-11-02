"""Harvest Wikipedia:Unusual_articles into assets/unusual.json.

Slot 30 needs a pool of genuinely strange articles. `SLOTS.md` is explicit about
why it is not the random-article endpoint: that returns geographic stubs almost
every time, and "a village in Lower Saxony, population 340" is not a rabbit
hole. Unusual_articles is hand-curated by editors over twenty years, which is
exactly the filter we cannot write.

**Harvested once and committed, not fetched every morning.** The list changes a
few times a month, the receipt runs every day, and a slot that depends on
scraping wikitext at 07:00 is a slot that breaks the morning the table markup
changes. Re-run this occasionally; it is not part of the print path.

The list lives across ~20 subpages, each holding a wikitable whose rows are

    | '''[[Article title]]'''
    | A one-line description written by an editor.

Both halves are kept. The slot fetches the real article summary at print time,
but the editor's line is a good fallback and is often funnier.

    python tools/harvestunusual.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sources.http import get_json  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "assets" / "unusual.json"
API = "https://en.wikipedia.org/w/api.php"

# A row's title cell: optional {{icon|..}}, optional width attribute, then the
# bolded wikilink. The description is the following cell.
_ROW = re.compile(
    r"^\|(?:\s*width=\"[^\"]*\"\s*\|)?\s*(?:\{\{icon\|[^}]*\}\}\s*)?"
    r"'''\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\][^\n]*\n\|\s*([^\n]+)",
    re.M)

# A description cell can carry its own attributes before the content pipe -
# rowspan="2"| and friends. Without stripping these the attribute string prints
# on the receipt as though it were the description.
_CELL_ATTRS = re.compile(r'^\s*(?:rowspan|colspan|align|valign|style|width|class)'
                         r'\s*=\s*"[^"]*"\s*\|\s*', re.I)
_WIKILINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]")
_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")
_HTML = re.compile(r"<[^>]+>")

# Subpages to leave out.
#   Death     - strange in a way nobody wants at breakfast. The slot is framed
#               as a curiosity, not a memento mori.
#   Removed   - articles DELISTED from the curated list. Harvesting these gets
#               it exactly backwards: they are the ones editors decided were not
#               unusual enough, or were deleted outright.
#   Categories- a meta page of category links, not articles.
SKIP = {"Death", "Removed", "Categories"}


def subpages() -> list[str]:
    data = get_json(f"{API}?action=query&list=allpages&apprefix=Unusual%20articles/"
                    "&apnamespace=4&aplimit=500&format=json&formatversion=2")
    return [p["title"] for p in data["query"]["allpages"]]


def wikitext(title: str) -> str:
    data = get_json(f"{API}?action=parse&page={quote(title)}&prop=wikitext"
                    "&format=json&formatversion=2")
    return data["parse"]["wikitext"]


def clean(text: str) -> str:
    while (stripped := _CELL_ATTRS.sub("", text)) != text:
        text = stripped
    text = _TEMPLATE.sub("", text)
    text = _WIKILINK.sub(r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = _HTML.sub("", text)
    return " ".join(text.split())


def main() -> None:
    entries: dict[str, str] = {}
    counts: list[tuple[str, int]] = []

    for page in subpages():
        category = page.split("/", 1)[-1]
        if category in SKIP:
            print(f"  skip {category}")
            continue
        try:
            rows = _ROW.findall(wikitext(page))
        except Exception as exc:  # noqa: BLE001 - a dead subpage costs variety only
            print(f"  {category}: FAILED {exc}")
            continue
        kept = 0
        for title, blurb in rows:
            text = clean(blurb)
            # A row whose description cell was empty captures the next row's
            # "|-" separator instead. Those entries have no blurb to fall back
            # on, so they are dropped rather than shipped half-formed.
            if len(text) < 12:
                continue
            entries.setdefault(title.strip(), text)
            kept += 1
        counts.append((category, kept))
        print(f"  {category:<46} {kept:>4}")

    payload = {
        "_note": ("Harvested from Wikipedia:Unusual_articles by "
                  "tools/harvestunusual.py. Titles and the editors' own one-line "
                  "descriptions. Slot 30 fetches the real article summary at "
                  "print time and keeps the description as a fallback."),
        "harvested_from": "https://en.wikipedia.org/wiki/Wikipedia:Unusual_articles",
        "count": len(entries),
        "articles": [{"title": t, "blurb": b} for t, b in sorted(entries.items())],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n{len(entries)} articles from {len(counts)} categories -> {OUT}")


if __name__ == "__main__":
    main()
