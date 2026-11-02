"""Slot 25 - Book quote.

A quotation from a book the reader has actually read, scraped from Goodreads
as the catalogue specifies. The scraping itself, and its politeness rules, live
in `sources/goodreads.py`; this is the slot.

**The pool is the reader's own list, in `data/books.txt`**, not a list in this
file. Paste a Goodreads shelf into it and the slot follows.

**Cache first, network rarely.** The quotes are harvested ahead of time by
`tools/harvestquotes.py` into `data/quotes.json` (gitignored). A morning makes at
most one live request pair, only for a book whose cache is missing or a season
old, and none at all while Goodreads' bot challenge cooldown is in force.

**The draw is weighted by author, not by book.** A read list is dominated by
long series, and a uniform draw by title would hand a fifth of all mornings to
three authors. Each author carries the square root of their book count: a
series read eight deep still comes up more than a one-off, but not eight times
as often. Recently
quoted books and recently used quotations are both suppressed.

**Quiet on a bad morning, loud when it is really broken** - both halves of the
catalogue's instruction. A single failed fetch serves a cached quotation and says
nothing. Three consecutive mornings of failure means the scraper has broken, and
the section becomes the escalating in-persona bulletin from SYSTEM.md 7 - "AGENT
COMPROMISED - GOODREADS CRACKING DOWN" - growing more cataclysmic each day it
persists, until a fetch succeeds and it quietly stops.

The quotation is verbatim and the attribution is Python's: both come from the
scraped page, so the narrator names the section and touches nothing else.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

BOOKS = Path(__file__).resolve().parent.parent / "data" / "books.txt"
NAMESPACE = "bookquote"
AVOID_BOOKS = 30
AVOID_QUOTES = 120
LOUD_AFTER = 3              # consecutive failed mornings before it goes loud

_SEPARATOR = re.compile(r"\s+(?:—|--|-)\s+")


@lru_cache(maxsize=1)
def reading_list() -> list[tuple[str, str]]:
    """(title, author) for every book in data/books.txt.

    The list is personal and gitignored; `data/books.example.txt` is the
    template. No list is not an error - the section simply never prints.
    """
    books = []
    if not BOOKS.exists():
        return books
    for raw in BOOKS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = _SEPARATOR.split(line)
        if len(parts) < 2:
            continue
        title, author = " - ".join(parts[:-1]).strip(), parts[-1].strip()
        if title and author:
            books.append((title, author))
    if not books:
        raise ValueError(f"{BOOKS} has no books in 'Title — Author' form")
    return books


def author_weights(books: list[tuple[str, str]]) -> list[float]:
    """Per-book weight so each AUTHOR carries sqrt(their book count)."""
    counts: dict[str, int] = {}
    for _, author in books:
        counts[author] = counts.get(author, 0) + 1
    return [math.sqrt(counts[a]) / counts[a] for _, a in books]


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


@register
class BookQuote(Slot):
    spec = SlotSpec(id=25, name="Book quote", tier="common", paper_mm=36,
                    needs_network=True, needs_narrator=True)

    # --- store helpers ------------------------------------------------------
    def _get(self, ctx: Context, key: str, default):
        if ctx.store is None:
            return default
        try:
            return ctx.store.fetch(NAMESPACE, key, default)
        except Exception:  # noqa: BLE001
            return default

    def _put(self, ctx: Context, key: str, value) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            ctx.store.put(NAMESPACE, key, value)
        except Exception:  # noqa: BLE001
            pass

    # --- the draw -----------------------------------------------------------
    def _order(self, ctx: Context) -> list[tuple[str, str]]:
        """Every book, in today's weighted order, recent ones pushed to the back."""
        books = reading_list()
        recent = set(self._get(ctx, "recent_books", []) or [])
        weights = author_weights(books)
        rng = ctx.rng(self.spec.id)
        # Weighted shuffle: key each book by random ** (1 / weight).
        keyed = sorted(range(len(books)),
                       key=lambda i: rng.random() ** (1 / weights[i]),
                       reverse=True)
        fresh = [books[i] for i in keyed if books[i][0] not in recent]
        stale = [books[i] for i in keyed if books[i][0] in recent]
        return fresh + stale

    def _choose_quote(self, ctx: Context, quotes: list[dict]) -> dict | None:
        used = set(self._get(ctx, "recent_quotes", []) or [])
        pool = [q for q in quotes if _key(q["text"]) not in used] or quotes
        if not pool:
            return None
        # Weighted by the square root of likes: the well-loved lines come up
        # more, but the top one does not win every time.
        return ctx.rng(self.spec.id + 1).choices(
            pool, weights=[math.sqrt(max(1, q.get("likes", 0))) for q in pool])[0]

    # --- the section ---------------------------------------------------------
    def _quote_result(self, quote: dict, title: str, author: str,
                      stale_note: str | None) -> SlotResult:
        text = quote["text"].replace("\n", "<br>")
        return SlotResult(
            head="From The Shelf",
            body=text,
            fine=f"{author}, <i>{title}</i>"
                 + (f" &middot; {stale_note}" if stale_note else ""),
            brief={"verbatim": True,
                   "book": title, "author": author,
                   "instruction": "Name this section in voice. The quotation "
                                  "and its attribution print exactly as they "
                                  "are - they are someone else's words."},
        )

    def _bulletin(self, ctx: Context, streak: int) -> SlotResult:
        # Escalates with the streak, per SYSTEM.md 7. The facts are true - the
        # scraper really has been failing for `streak` mornings - and the
        # catastrophe around them is the persona's.
        level = ("compromised" if streak < 5 else
                 "cracking down" if streak < 9 else "total operational collapse")
        return SlotResult(
            head="AGENT COMPROMISED",
            body=f"The Goodreads line has been dark for {streak} "
                 f"morning{'s' if streak != 1 else ''}. "
                 f"No quotation could be retrieved.",
            fine="Normal service resumes when the source does.",
            brief={
                "days_failing": streak,
                "severity": level,
                "instruction": "Write an escalating, cataclysmic in-character "
                               "bulletin that the book-quote source, Goodreads, "
                               "has been cracking down and today's quotation "
                               "could not be retrieved. It has been failing for "
                               f"{streak} mornings running - the longer, the "
                               "more apocalyptic the tone (severity: "
                               f"{level}). Two or three sentences. Do NOT quote "
                               "any book and do not invent a quotation. Header "
                               "in the spirit of AGENT COMPROMISED.",
            },
        )

    def _result(self, ctx: Context, live: bool) -> SlotResult | None:
        from sources import goodreads as gr

        if not reading_list():
            return None
        cache = gr.load_cache()
        streak = int(self._get(ctx, "fail_streak", 0) or 0)
        order = self._order(ctx)
        attempted = False

        for title, author in order:
            entry = cache["books"].get(title)
            stale_note = None
            if live and not attempted and gr.is_stale(entry) \
                    and not gr.cooling_down(cache):
                attempted = True
                try:
                    gr.refresh(cache, title, author)
                    entry = cache["books"][title]
                    streak = 0
                except gr.GoodreadsBroken:
                    streak += 1
            quotes = (entry or {}).get("quotes") or []
            if not quotes:
                continue                     # no quotes for this book; next one
            if entry and gr.is_stale(entry):
                stale_note = "from the archive"
            if streak >= LOUD_AFTER:
                break
            quote = self._choose_quote(ctx, quotes)
            if quote is None:
                continue
            self._put(ctx, "fail_streak", streak)
            self._put(ctx, "recent_books",
                      (self._get(ctx, "recent_books", []) + [title])[-AVOID_BOOKS:])
            self._put(ctx, "recent_quotes",
                      (self._get(ctx, "recent_quotes", []) + [_key(quote["text"])])
                      [-AVOID_QUOTES:])
            return self._quote_result(quote, title, author, stale_note)

        self._put(ctx, "fail_streak", streak)
        if streak >= 1:
            return self._bulletin(ctx, streak)
        # Nothing harvested yet and nothing has failed. Dropping the section is
        # the honest outcome: a bulletin here would announce an outage that
        # never happened, which is a false fact printed as a joke.
        return None

    def fetch(self, ctx: Context) -> SlotResult | None:
        # Live only on a real morning. A --date simulation or a test context
        # has no business sending requests to someone else's site.
        return self._result(ctx, live=not ctx.offline
                            and bool(ctx.shared.get("real_morning")))

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx, live=False)
