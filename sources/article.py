"""What a linked page says about itself, for a headline that came with nothing.

Hacker News gives a title, a URL and two vote counts. "Push ifs up and fors
down" says nothing on paper; the page it links to says what it is in one line,
in its own `og:description` - written by the publisher precisely so a link can
be previewed. That line is a fact about the article, quoted, never generated.

The order of preference, each step only when the one before has nothing:

  1. A GitHub repo's own description, from the API. GitHub's page meta is the
     boilerplate "Contribute to x development by creating an account".
  2. The page's description meta (`og:description`, `twitter:description`,
     `description`), minus boilerplate.
  3. The page's first real paragraph.
  4. On Hacker News itself: the poster's text (Ask HN, Show HN), then the top
     comment, which HN's API lists first. Often snarky; that is fine, it is
     labelled as a comment and never passed off as the article.

Every result is cached per URL, so a re-run is free and an offline morning
still has yesterday's text. Nothing here raises: a dead page is an empty string.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .http import UA

NAMESPACE = "article"
TIMEOUT = 6
# A description past this is a paragraph, and the ranker reads it in tokens.
MAX_CHARS = 240
# Enough of the page to reach the <head> and the first paragraphs.
READ_BYTES = 400_000

_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r'([a-zA-Z:-]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_HN_ID = re.compile(r"news\.ycombinator\.com/item\?id=(\d+)")

# Text a page says about itself that says nothing about the article.
_BOILERPLATE = re.compile(
    r"contribute to .* by creating an account|sign in|log in|cookies|"
    r"enable javascript|subscribe to|your browser|access denied|"
    r"just a moment|page not found|we use cookies", re.I)


def _get(url: str, limit: int = READ_BYTES) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            kind = r.headers.get_content_type() or ""
            if "html" not in kind and "json" not in kind:
                return None          # a PDF or an image has no meta to read
            charset = r.headers.get_content_charset() or "utf-8"
            return r.read(limit).decode(charset, errors="replace")
    except Exception:  # noqa: BLE001 - any failure is "nothing to say"
        return None


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAGS.sub(" ", fragment)).split())


def _usable(text: str) -> bool:
    return len(text) >= 40 and not _BOILERPLATE.search(text)


def trim(text: str, limit: int = MAX_CHARS) -> str:
    """Cut at a sentence if one ends in range, else at a word."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end > limit * 0.5:
        return cut[:end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "..."


def from_page(page: str) -> str:
    """The description a page gives itself, else its first real paragraph."""
    metas: dict[str, str] = {}
    for tag in _META.findall(page[:READ_BYTES]):
        attrs = {m.group(1).lower(): m.group(3) if m.group(3) is not None
                 else m.group(4) for m in _ATTR.finditer(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key and attrs.get("content"):
            metas.setdefault(key, _text(attrs["content"]))
    for key in ("og:description", "twitter:description", "description"):
        if _usable(metas.get(key, "")):
            return trim(metas[key])
    for para in _PARA.findall(page):
        text = _text(para)
        if len(text) >= 80 and _usable(text):
            return trim(text)
    return ""


def _github(url: str) -> str:
    parts = [p for p in urllib.parse.urlsplit(url).path.split("/") if p]
    if len(parts) < 2:
        return ""
    raw = _get(f"https://api.github.com/repos/{parts[0]}/{parts[1]}")
    try:
        return trim(json.loads(raw or "{}").get("description") or "")
    except ValueError:
        return ""


def hn_id(text: str) -> str | None:
    """The HN item id inside a feed summary or a link, if there is one."""
    m = _HN_ID.search(text or "")
    return m.group(1) if m else None


def _hn_item(item_id: str | int) -> dict:
    raw = _get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
               limit=200_000)
    try:
        return json.loads(raw or "{}") or {}
    except ValueError:
        return {}


def _hn_words(item_id: str) -> tuple[str, str]:
    """(poster's own text, top comment) for an HN item. Either may be ""."""
    story = _hn_item(item_id)
    own = _text(story.get("text") or "")
    # `kids` is in HN's ranked order, so the first live one is the top comment.
    for kid in (story.get("kids") or [])[:3]:
        comment = _hn_item(kid)
        if comment.get("deleted") or comment.get("dead"):
            continue
        words = _text(comment.get("text") or "")
        if words:
            return own, trim(words, 200)
    return own, ""


def _key(link: str, hn: str | None) -> str:
    return link or f"hn:{hn}"


def recall(store: Any, link: str, hn: str | None = None) -> dict | None:
    """What was read for this link before, or None. Call from the thread that
    owns `store` - a SQLite connection refuses to be used from any other."""
    if store is None:
        return None
    try:
        return store.fetch(NAMESPACE, _key(link, hn))
    except Exception:  # noqa: BLE001
        return None


def keep(store: Any, link: str, hn: str | None, got: dict) -> None:
    """Cache a reading. Same threading rule as `recall`."""
    if store is None or not (got.get("article") or got.get("comment")):
        return
    try:
        store.put(NAMESPACE, _key(link, hn), got)
    except Exception:  # noqa: BLE001 - a cache write is never worth a crash
        pass


def read(link: str, hn: str | None = None) -> dict:
    """{"article": ..., "comment": ...} for a link, from the network - each ""
    when unknown. Touches no store, so it is safe to run in a worker thread.

    `hn` is the Hacker News item id when the link came from there; only then
    is the thread consulted, and only when the article said nothing.
    """
    article = ""
    host = urllib.parse.urlsplit(link).netloc.lower()
    if link and "news.ycombinator.com" not in host:
        if host.endswith("github.com"):
            article = _github(link)
        if not article:
            article = from_page(_get(link) or "")
    comment = ""
    if hn and not article:
        own, comment = _hn_words(hn)
        article = trim(own) if own else ""
    return {"article": article, "comment": comment}
