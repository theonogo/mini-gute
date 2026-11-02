"""Harvest public-domain short stories into assets/stories/stories.json.

Feeds slot 148 (a story over three mornings) and legendary format 9 (a whole
story at once). Books are Project Gutenberg plain-text collections listed in
`assets/stories/sources.toml`; each is downloaded once and split into stories at
its all-caps title headings.

**A half story printed as a whole one is the failure to design against.** Most
collections put section titles, letters and signatures in capitals too, and a
split at one of those produces a fragment that looks complete. So every book's
internal capitals are listed in `sources.toml`, roman-numeral section markers
never count as a boundary, and `--list` shows exactly where a book would split
before anything is kept.

Kept only between MIN_WORDS and MAX_WORDS, and never if the text contains a word
from `SKIP_WORDS` - several of these collections are of their period in ways a
breakfast receipt should not reprint.

    python tools/harveststories.py              # fetch and split every book
    python tools/harveststories.py --list 269   # show one book's splits
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "assets" / "stories"
CACHE = ROOT / "data" / "gutenberg"
UA = "quick-guthe/0.1 (personal receipt printer; a few books, once)"

MIN_WORDS = 700
MAX_WORDS = 6_000
SKIP_WORDS = re.compile(r"\bnigger|\bnegro|\bdarkey|\bdarky|\bcoon\b|\bsquaw\b|"
                        r"\bchink\b|\bjap\b|\bkaffir|\bgolliwog|\bpickaninn",
                        re.I)
_NUMERAL = re.compile(r"^[IVXLC]+\.?$")
# Sections that split cleanly but are not stories.
NOT_A_STORY = re.compile(r"^(contents|notes?|footnotes|introduction|preface|"
                         r"index|author's note|acknowledg)", re.I)
SMALL = {"a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the",
         "to", "with"}


def titlecase(text: str) -> str:
    text = re.sub(r"\s*\{\d+\}", "", text)
    words = text.lower().split()
    return " ".join(w if i and w in SMALL else
                    re.sub(r"(^|[-\"(])([a-z])",
                           lambda m: m.group(1) + m.group(2).upper(), w)
                    for i, w in enumerate(words))


def text_of(book_id: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"pg{book_id}.txt"
    if not path.exists():
        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            path.write_bytes(resp.read())
        time.sleep(3)
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = raw.find("\n", raw.find("*** START"))
    end = raw.find("*** END")
    return raw[start:end]


def _normal(line: str) -> str:
    return line.strip().replace("\u2019", "'").replace("\u201c", '"') \
        .replace("\u201d", '"')


def headings(lines: list[str], internal: set[str]) -> list[int]:
    out = []
    for i in range(1, len(lines) - 1):
        s = _normal(lines[i])
        if (s and len(s) < 80 and s.upper() == s and re.search("[A-Z]", s)
                and not lines[i - 1].strip() and not lines[i + 1].strip()
                and not _NUMERAL.match(s) and s not in internal
                and not s.endswith(":")):
            out.append(i)
    return out


def clean(block: list[str]) -> list[str]:
    """Hard-wrapped lines to paragraphs, Gutenberg markup removed."""
    paras, cur = [], []
    for line in block + [""]:
        s = line.strip()
        if not s:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s)
    out = []
    for p in paras:
        p = re.sub(r"\{\d+\}|\[Illustration[^\]]*\]|\[\d+\]", "", p)
        p = re.sub(r"_(.+?)_", r"\1", p).replace("_", "").strip()
        if not p or _NUMERAL.match(p) or re.fullmatch(r"[*\s.]+", p):
            continue
        out.append(p)
    return out


def split(book: dict) -> list[dict]:
    lines = text_of(book["id"]).split("\n")
    internal = {_normal(x) for x in book.get("internal", [])}
    marks = headings(lines, internal)
    found: dict[str, dict] = {}
    carried = None
    for n, i in enumerate(marks):
        stop = marks[n + 1] if n + 1 < len(marks) else len(lines)
        paras = clean(lines[i + 1:stop])
        words = sum(len(p.split()) for p in paras)
        title = carried or titlecase(_normal(lines[i]).rstrip("."))
        carried = None
        # A heading straight on top of another is a title over its subtitle
        # ("ONE OF TWINS" / "A LETTER FOUND AMONG THE PAPERS..."). The story
        # keeps the first as its title.
        if words == 0 and stop - i <= 4:
            carried = title
            continue
        if NOT_A_STORY.match(title):
            continue
        # A title appears in the contents and again at the story; keep the
        # longer, which is the story.
        if title not in found or words > found[title]["words"]:
            found[title] = {"title": title, "author": book["author"],
                            "source": f"Project Gutenberg #{book['id']}",
                            "words": words, "paragraphs": paras}
    return list(found.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", type=int, metavar="BOOK_ID")
    args = ap.parse_args()
    books = tomllib.loads((DIR / "sources.toml").read_text(encoding="utf-8"))["book"]

    if args.list:
        book = next(b for b in books if b["id"] == args.list)
        for s in split(book):
            last = s["paragraphs"][-1][-60:] if s["paragraphs"] else ""
            print(f"{s['words']:6}  {s['title'][:40]:40}  ...{last}")
        return 0

    stories, skipped = [], 0
    for book in books:
        for s in split(book):
            if not MIN_WORDS <= s["words"] <= MAX_WORDS:
                continue
            if SKIP_WORDS.search(" ".join(s["paragraphs"])):
                skipped += 1
                continue
            stories.append(s)
        print(f"  #{book['id']:<6} {book['author']}")
    stories.sort(key=lambda s: (s["author"], s["title"]))
    (DIR / "stories.json").write_text(
        json.dumps(stories, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(stories)} stories kept, {skipped} skipped for language")
    return 0


if __name__ == "__main__":
    sys.exit(main())
