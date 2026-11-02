"""The public-domain short story corpus - `assets/stories/stories.json`.

Shared by slot 148 (one story over three mornings) and legendary format 9 (a
whole story at once). Filled by `tools/harveststories.py`; nothing here touches
the network.

**Drawn by author first.** Saki wrote very short stories and a great many of
them, so a uniform draw would make this a Saki slot. Each author is weighted by
the square root of their story count, the same rule the book quotes use: a
prolific author still comes up more often, just not in proportion.

**The text is verbatim.** A story is a quotation at length; no persona touches a
word of it.
"""

from __future__ import annotations

import json
import math
import random
import re
from functools import lru_cache
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "assets" / "stories" / "stories.json"

# SYSTEM.md 4.2: the legendary story is 1,500-2,500 words nine times in ten, and
# the long one - up to about 6,000 - the tenth.
STANDARD = (1_500, 2_500)
LONG = (2_501, 6_000)
LONG_SHARE = 0.10
# Slot 148: short enough that three mornings of it are an easy read.
THREE_PART = (700, 1_499)


@lru_cache(maxsize=1)
def corpus() -> list[dict]:
    try:
        return json.loads(CORPUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def choose(rng: random.Random, band: tuple[int, int],
           avoid: set[str] = frozenset()) -> dict | None:
    """A story within `band` words, weighted by author, avoiding recent titles."""
    pool = [s for s in corpus() if band[0] <= s["words"] <= band[1]]
    fresh = [s for s in pool if s["title"] not in avoid] or pool
    if not fresh:
        return None
    by_author: dict[str, list[dict]] = {}
    for story in fresh:
        by_author.setdefault(story["author"], []).append(story)
    authors = sorted(by_author)
    author = rng.choices(authors,
                         weights=[math.sqrt(len(by_author[a])) for a in authors])[0]
    return rng.choice(by_author[author])


def by_title(title: str) -> dict | None:
    return next((s for s in corpus() if s["title"] == title), None)


_SENTENCE = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"”’'])\s+")


def split(story: dict, parts: int = 3) -> list[list[str]]:
    """The story in `parts` runs of near-equal length.

    Each boundary goes at the sentence end nearest its share of the words -
    usually a paragraph break, but a long paragraph is split rather than
    allowed to make one morning's part twice the size of the next. A part that
    begins mid-paragraph simply begins with that sentence.
    """
    # Flatten to sentences, remembering which paragraph each belongs to.
    units: list[tuple[int, str]] = []
    for index, para in enumerate(story["paragraphs"]):
        units += [(index, sentence) for sentence in _SENTENCE.split(para) if sentence]
    counts = [len(text.split()) for _, text in units]
    total = sum(counts)
    if len(units) < parts or not total:
        return [story["paragraphs"]]

    cumulative, running = [], 0
    for n in counts:
        running += n
        cumulative.append(running)

    def paragraph_break(i: int) -> bool:
        return i >= len(units) or units[i][0] != units[i - 1][0]

    cuts, last = [], 0
    for k in range(1, parts):
        target = total * k / parts
        # A paragraph break wins unless it is more than 5% of the story away.
        slack = total * 0.05
        candidates = range(last + 1, len(units) - (parts - k) + 1)
        best = min(candidates, key=lambda i: abs(cumulative[i - 1] - target)
                   + (0 if paragraph_break(i) else slack))
        cuts.append(best)
        last = best

    out = []
    for a, b in zip([0] + cuts, cuts + [len(units)]):
        paras: list[str] = []
        current = None
        for index, sentence in units[a:b]:
            if index != current:
                paras.append(sentence)
                current = index
            else:
                paras[-1] += " " + sentence
        out.append(paras)
    return out


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def html(paragraphs: list[str]) -> str:
    return "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
