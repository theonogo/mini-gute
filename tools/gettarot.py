"""Fetch the Rider-Waite-Smith major arcana (1909) from Wikimedia Commons.

Run once; scans cache in `assets/tarot/source/`. Throttled - Commons 429s a
burst and sets Retry-After.

WHY THIS DECK. Five decks were scored by how bimodal their histogram is, which
decides whether a scan survives 1-bit rendering:

    deck            midtone%   verdict
    Falconnier 1896     6.8%   excellent line art, but Egyptian imagery
    Wirth 1889         18.8%   good, but large flat cloaks flood to black
    Conver 1760        23.1%   mixed - flat colour fills blot badly
    Dodal 1701         48.9%   photograph of a coloured deck
    Sola Busca         53.2%   photograph of a coloured deck

RWS is a coloured deck and scores no better raw - BUT Pamela Colman Smith drew
heavy black outlines under the colour, so a CONTOUR pass recovers clean line art
that a plain threshold cannot. See `render.dither.prepare_contour`. That is why
this deck is fetched in colour and processed, rather than sought as line art.

Copyright: the 1909 artwork is public domain in most jurisdictions. Personal use
here regardless.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "assets" / "tarot" / "source"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) quick-guthe/0.1"
THUMB_W = 700
DELAY = 4.0

# RWS numbering: Strength is VIII and Justice XI (Marseille swaps them).
NAMES = [
    "Fool", "Magician", "High Priestess", "Empress", "Emperor", "Hierophant",
    "Lovers", "Chariot", "Strength", "Hermit", "Wheel of Fortune", "Justice",
    "Hanged Man", "Death", "Temperance", "Devil", "Tower", "Star", "Moon",
    "Sun", "Judgement", "World",
]


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def _get(url: str, timeout: int = 90, tries: int = 5) -> bytes:
    delay = 5.0
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == tries - 1:
                raise
            wait = float(exc.headers.get("Retry-After") or delay)
            print(f"      429, waiting {wait:.0f}s")
            time.sleep(wait)
            delay *= 2
    raise RuntimeError("unreachable")


def api(params: dict) -> dict:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return json.loads(_get(url, timeout=40))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(NAMES):
        out = DEST / f"{slug(name)}.jpg"
        if out.exists():
            print(f"  {slug(name):<18} cached")
            continue
        title = f"File:RWS1909 - {i:02d} {name}.jpeg"
        info = api({"action": "query", "titles": title, "prop": "imageinfo",
                    "iiprop": "url|size", "iiurlwidth": str(THUMB_W),
                    "format": "json"})
        page = next(iter(info["query"]["pages"].values()))
        if "missing" in page:
            print(f"  {slug(name):<18} MISSING")
            continue
        ii = page["imageinfo"][0]
        out.write_bytes(_get(ii.get("thumburl") or ii["url"]))
        print(f"  {slug(name):<18} {ii.get('thumbwidth')}x{ii.get('thumbheight')}"
              f"  {out.stat().st_size / 1024:.0f}KB")
        time.sleep(DELAY)

    have = sorted(p.stem for p in DEST.glob("*.jpg"))
    print(f"\n{len(have)}/22 cards -> {DEST}")


if __name__ == "__main__":
    main()
