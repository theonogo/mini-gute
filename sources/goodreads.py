"""Goodreads quotations, scraped - for slot 25.

Goodreads shut its public API in December 2020, so there is no sanctioned way to
ask for a book's quotes; this reads the public quote pages instead, as the
catalogue specifies. It is written to be a good citizen and to break loudly.

**Within the published crawl rules.** Goodreads' robots.txt (as of September
2026) says `Allow: /work/quotes` for every agent and disallows only the quotes
RSS feed. The per-book quotes page this reads is therefore explicitly permitted.

**Polite by construction, not by intention.** An identifying user agent, and a
floor of five seconds between any two requests - the crawl delay Goodreads
publishes for Bing, taken as the house rate for everyone. The morning run makes
at most one or two requests; the bulk of the work is done ahead of time by
`tools/harvestquotes.py`, and everything is cached so the same page is not asked
for twice in a season.

**Two requests to find one book's quotes.** A quote search for a title returns
quotes from the author's *other* books as well - searching The Name of the Wind
leads with a line from The Wise Man's Fear. So the search is used only to find the
book's `/work/quotes/<id>` page, and that page, which lists quotes from that one
book, is where the quotations actually come from.

**Goodreads sits behind AWS WAF, and this scraper stops at its challenge.**
After five requests in about thirty seconds, every further request comes back
as a 2.4KB AWS WAF bot-challenge page - a JavaScript puzzle, not a quotes page. This module detects that page by name and raises
`Challenged`, and the caller backs off for hours. It does not attempt to solve,
evade or outlast the challenge: no headless browser executing its script, no
borrowed browser headers, no retry loop. The challenge is the site saying stop,
and a scraper that argues with it is no longer a polite one. The practical
consequence is that quotes are harvested slowly, a book at a time with long gaps
(`tools/harvestquotes.py`), and served from cache.

**It raises `GoodreadsBroken` rather than returning nothing when the page is not
what it expected.** A 200 response with no quote blocks in it means the markup
changed, which is a different thing from a book that simply has no quotes - and
the slot needs to know the difference, because one is a quiet morning and the
other is the scraper dying.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .http import UA

BASE = "https://www.goodreads.com"
TIMEOUT = 20
MIN_INTERVAL_S = 5.0  # Goodreads' published crawl delay, applied to all
MAX_WORDS = 60  # a quotation, not a passage

_last_request = 0.0

_BLOCK = re.compile(
    r'<div class="quoteText">(.*?)</div>\s*<div class="quoteFooter">'
    r"(.*?)</div>\s*</div>",
    re.S,
)
_TEXT = re.compile(r"&ldquo;(.*?)&rdquo;", re.S)
_AUTHOR = re.compile(r'<span class="authorOrTitle">\s*(.*?)\s*</span>', re.S)
_TITLE = re.compile(
    r'<a class="authorOrTitle" href="/work/quotes/(\d+)[^"]*">'
    r"(.*?)</a>",
    re.S,
)
_LIKES = re.compile(r"([\d,]+)\s+likes?")
_TAGS = re.compile(r"<[^>]+>")


class GoodreadsBroken(RuntimeError):
    """The site answered, but not in a shape this parser understands - or
    refused outright. Distinct from a book that has no quotes."""


class Challenged(GoodreadsBroken):
    """AWS WAF served its bot challenge instead of the page. Back off."""


def _is_challenge(page: str) -> bool:
    return "awsWafCookieDomainList" in page or "gokuProps" in page


@dataclass
class Quote:
    text: str
    author: str
    title: str
    likes: int
    work_id: str

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str) -> str:
    """One polite request. Enforces the interval across the whole process."""
    global _last_request
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # 403 and 429 are the site telling us to stop, not a missing book.
        raise GoodreadsBroken(f"HTTP {exc.code} from {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GoodreadsBroken(f"unreachable: {exc}") from exc
    finally:
        _last_request = time.monotonic()
    if _is_challenge(body):
        raise Challenged(f"AWS WAF bot challenge on {url}")
    return body


def _clean(fragment: str) -> str:
    text = fragment.replace("<br />", "\n").replace("<br>", "\n")
    text = htmllib.unescape(_TAGS.sub("", text))
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def parse(page: str) -> list[Quote]:
    """Every quote block on a Goodreads quotes page."""
    out = []
    for text_html, footer in _BLOCK.findall(page):
        text_match = _TEXT.search(text_html)
        if not text_match:
            continue
        # A long quote is truncated on the listing with a hidden continuation;
        # those are not whole quotations and are skipped.
        if 'id="quoteText' in text_html or "(more)" in text_html:
            continue
        author_match = _AUTHOR.search(text_html)
        title_match = _TITLE.search(text_html)
        likes_match = _LIKES.search(footer)
        out.append(
            Quote(
                text=_clean(text_match.group(1)),
                author=_clean(author_match.group(1)).rstrip(",").strip()
                if author_match
                else "",
                title=_clean(title_match.group(2)) if title_match else "",
                likes=int(likes_match.group(1).replace(",", "")) if likes_match else 0,
                work_id=title_match.group(1) if title_match else "",
            )
        )
    return out


def normalise(title: str) -> str:
    """Enough to match "Guards! Guards!" to "Guards! Guards! (Discworld, #8)"."""
    title = re.sub(r"\(.*?\)", "", title.lower())
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return " ".join(title.split())


def _matches(found: str, wanted: str) -> bool:
    a, b = normalise(found), normalise(wanted)
    return bool(a) and (a == b or a.startswith(b) or b.startswith(a))


def book_quotes(title: str, author: str, limit: int = 30) -> list[Quote]:
    """Quotations from exactly this book, most-liked first.

    Returns an empty list for a book Goodreads has no quotes for. Raises
    `GoodreadsBroken` if the site refuses or its markup has changed.
    """
    query = urllib.parse.quote_plus(f"{title} {author}")
    search = _get(f"{BASE}/quotes/search?q={query}")
    found = parse(search)
    if not found and "quoteText" in search:
        raise GoodreadsBroken("quote blocks present but unparseable - markup changed")
    if not found and "quoteDetails" not in search and "No results" not in search:
        # A page with neither quotes nor a no-results message is not a quotes
        # page at all: a login wall, a captcha, a redesign.
        raise GoodreadsBroken("search returned an unrecognised page")

    work_ids = [q.work_id for q in found if q.work_id and _matches(q.title, title)]
    quotes = [q for q in found if _matches(q.title, title)]

    if work_ids:
        # The book's own quotes page - explicitly allowed by robots.txt, and the
        # only listing that is guaranteed to be this book rather than the author.
        work_page = _get(f"{BASE}/work/quotes/{work_ids[0]}")
        from_work = [
            q for q in parse(work_page) if _matches(q.title, title) or not q.title
        ]
        for q in from_work:
            if not q.title:
                q.title = title
            if not q.author:
                q.author = author
        if from_work:
            quotes = from_work

    usable = [q for q in quotes if 0 < len(q.text.split()) <= MAX_WORDS]
    usable.sort(key=lambda q: q.likes, reverse=True)
    return usable[:limit]


# --- the local cache ---------------------------------------------------------
# `data/quotes.json` - gitignored, because these are other people's copyrighted
# words, scraped for a personal receipt, and have no business in a public
# repository.
CACHE = Path(__file__).resolve().parent.parent / "data" / "quotes.json"
# After a challenge, no request of any kind for this long, so the next attempt
# is not the same burst resumed.
COOLDOWN = timedelta(hours=1)
# A book's quotes change slowly; refetch after a season, not a week.
STALE_AFTER = timedelta(days=300)


def load_cache() -> dict:
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("books", {})
            return data
    except (FileNotFoundError, ValueError):
        pass
    return {"books": {}}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE)  # atomic, so a crash never truncates it


def cooling_down(cache: dict, now: datetime | None = None) -> bool:
    until = cache.get("challenged_until")
    if not until:
        return False
    try:
        return (now or datetime.now()) < datetime.fromisoformat(until)
    except ValueError:
        return False


def is_stale(entry: dict | None, now: datetime | None = None) -> bool:
    if not entry or "fetched" not in entry:
        return True
    try:
        fetched = datetime.fromisoformat(entry["fetched"])
    except ValueError:
        return True
    return (now or datetime.now()) - fetched > STALE_AFTER


def refresh(cache: dict, title: str, author: str) -> list[dict]:
    """Fetch one book live and write it into `cache`. Saves the cache.

    Raises `Challenged` or `GoodreadsBroken`; on a challenge the cooldown is
    recorded before re-raising, so no caller can forget to back off.
    """
    try:
        quotes = [q.as_dict() for q in book_quotes(title, author)]
    except Challenged:
        cache["challenged_until"] = (datetime.now() + COOLDOWN).isoformat(
            timespec="seconds"
        )
        save_cache(cache)
        raise
    cache["books"][title] = {
        "author": author,
        "quotes": quotes,
        "fetched": datetime.now().isoformat(timespec="seconds"),
    }
    cache.pop("challenged_until", None)
    save_cache(cache)
    return quotes
