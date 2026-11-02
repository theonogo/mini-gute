"""Find the stories several outlets are telling at once - slot 115's collector.

Pure Python and free. Every headline becomes a bag of words (title plus the
start of its summary), weighted by rarity across the day's pool - "Kramatorsk"
says far more than "attack" - and two headlines are near when their weighted
overlap is high. A story is a seed headline plus the nearest headline from
each other outlet, kept only if its members agree with each other and not just
with the seed.

Tested on a real morning (457 headlines from 15 outlets): the
groups it found were the Kramatorsk bus strike (8 outlets), the death of the
evicted pensioner Maricarmen (8), Anne Carson's Nobel (6), South Korea's envoy
(6), and the East Jerusalem consulate (6). It also found what it cannot tell
apart: the Guardian's "Can Sanchez convince Spanish voters..." sits in the
Maricarmen group because it shares the words. "Same event, framed differently"
against "same topic, different article" is a judgement, and `narrator.framings`
makes it, along with whether the difference is worth printing.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Loose: enough to group one story's coverage. The narrator decides the rest.
NEAR = 0.25

_WORD = re.compile(r"[a-z0-9][a-z0-9'-]*")
_STOP = set("""the a an and or of to in on for with from by at as is are was
were be been has have had it its this that these those after before over under
into about says said say new more than not but who what when where why how will
would could can may might amid against up down out off his her their they them
he she we you our your all any one two three first last year years day days week
news live latest report reports""".split())


def _norm(word: str) -> str:
    word = word.strip("'-").replace("'s", "")
    if len(word) > 4 and re.search(r"(s|x|ch|sh)es$", word):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(text: str) -> set[str]:
    out = set()
    for w in _WORD.findall(text.lower()):
        w = _norm(w)
        if len(w) > 2 and w not in _STOP:
            out.add(w)
    return out


class Pool:
    """The day's headlines, with the weights `near` needs."""

    def __init__(self, items: list[Any]):
        self.items = items
        self.title = [_words(i.title) for i in items]
        self.text = [_words(f"{i.title} {i.summary[:220]}") for i in items]
        df: dict[str, int] = {}
        for words in self.text:
            for w in words:
                df[w] = df.get(w, 0) + 1
        n = max(len(items), 1)
        self.idf = {w: math.log(n / c) for w, c in df.items()}
        self._mass = [sum(self.idf[w] for w in t) or 1.0 for t in self.text]

    def near(self, a: int, b: int) -> float:
        shared = self.text[a] & self.text[b]
        if not shared:
            return 0.0
        return (sum(self.idf[w] for w in shared)
                / math.sqrt(self._mass[a] * self._mass[b]))



def stories(items: list[Any], *, minimum: int = 3,
            limit: int = 6, per_story: int = 8) -> list[list[Any]]:
    """The day's most widely covered stories, each a list of headlines from
    different outlets, biggest first. Overlapping groups are collapsed."""
    pool = Pool(items)
    n = len(items)
    found: list[tuple[int, list[int]]] = []
    for a in range(n):
        best: dict[str, tuple[float, int]] = {}
        for b in range(n):
            if items[b].source == items[a].source:
                continue
            s = pool.near(a, b)
            if s >= NEAR and s > best.get(items[b].source, (0.0, -1))[0]:
                best[items[b].source] = (s, b)
        group = [a] + [b for _, b in sorted(best.values(), reverse=True)]
        # Each member must agree with at least half the others, not only with
        # the seed - one shared name is how a neighbouring story gets in.
        group = [i for i in group
                 if sum(pool.near(i, j) >= NEAR * 0.6 for j in group if j != i)
                 >= max(1, (len(group) - 1) // 2)]
        outlets = {items[i].source for i in group}
        if len(outlets) >= minimum:
            found.append((len(outlets), group))

    found.sort(key=lambda f: -f[0])
    out: list[list[Any]] = []
    taken: list[set[int]] = []
    for _, group in found:
        if any(len(set(group) & t) >= 2 for t in taken):
            continue
        taken.append(set(group))
        seen: set[str] = set()
        members = []
        for i in group:
            if items[i].source not in seen:
                seen.add(items[i].source)
                members.append(items[i])
        out.append(members[:per_story])
        if len(out) >= limit:
            break
    return out
