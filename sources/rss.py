"""RSS and Atom fetching.

Hand-parsed with `xml.etree` rather than adding feedparser: we need four fields
from two formats, and a dependency that pulls in its own encoding heuristics is
more surface than the job deserves.

A feed that is down, malformed, or slow is skipped rather than fatal. Losing one
of thirty feeds costs variety; raising costs the whole news section.

**A feed is configured, not just listed.** `Feed` carries the name to print (a
feed's own title is often "Latest Updates" or "Blog"), a weight for how much of
the ranker's attention it deserves, its own freshness window (a feed that
posts weekly would never be seen in a 36-hour one), and a group, which slot 115
uses to pick outlets that differ. A bare URL string works too.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

from .http import UA

NAMESPACE = "rss"
TIMEOUT = 12

_TAG = re.compile(r"\{.*?\}")          # strip XML namespaces
_HTML = re.compile(r"<[^>]+>")


@dataclass
class Item:
    title: str
    link: str
    source: str
    published: datetime | None = None
    # The feed's own description, cleaned. Slot 10 glosses a cryptic headline
    # from this rather than from anything invented.
    summary: str = ""
    # From the feed's config: how much ranking attention the outlet deserves.
    weight: float = 1.0
    group: str = ""

    @property
    def age_hours(self) -> float:
        if self.published is None:
            return 0.0
        now = datetime.now(timezone.utc)
        return (now - self.published).total_seconds() / 3600


def _clean(text: str | None) -> str:
    if not text:
        return ""
    # Feeds put entities and stray markup in titles surprisingly often.
    text = _HTML.sub("", text)
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"),
                 ("&apos;", "'"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&nbsp;", " "), ("&#8217;", "'"), ("&hellip;", "...")):
        text = text.replace(a, b)
    return " ".join(text.split())


def _when(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)          # RFC 822, the RSS form
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # Atom
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# How a publication writes its own name, once the section it syndicated is
# taken off. The three shapes the feeds in config.toml actually use:
#   "World news | The Guardian"   -> the masthead is AFTER the pipe
#   "Ars Technica - All content"  -> and BEFORE the dash
#   "Hacker News: Front Page"     -> and before the colon
# Anything that survives none of them is left alone, which is the common case
# ("BBC News"). A result that is empty or absurdly long is not a masthead.
_SECTION = (("|", -1), (" - ", 0), (" \u2013 ", 0), (": ", 0))
MAX_NAME = 28


def publication(title: str, fallback: str) -> str:
    """A feed's own name for itself, for printing under a headline."""
    name = (title or "").strip()
    for sep, keep in _SECTION:
        if sep in name:
            name = name.split(sep)[keep].strip()
    return name if 0 < len(name) <= MAX_NAME else fallback


def _channel_title(root) -> str:
    """The feed's title - the one before the first item, not an item's own."""
    for node in root.iter():
        tag = _TAG.sub("", node.tag)
        if tag in ("item", "entry"):
            break
        if tag == "title" and node.text:
            return node.text
    return ""


def parse(xml: str, source: str) -> list[Item]:
    """Items from either an RSS 2.0 or an Atom document.

    `source` is the fallback name - the host the feed came from. A feed that
    says what it is called gets to say it, because "FEEDS.BBCI.CO.UK" under a
    headline is a URL, not an attribution.
    """
    root = ElementTree.fromstring(xml)
    source = publication(_channel_title(root), source)
    items: list[Item] = []

    for node in root.iter():
        tag = _TAG.sub("", node.tag)
        if tag not in ("item", "entry"):
            continue
        fields: dict[str, Any] = {}
        for child in node:
            name = _TAG.sub("", child.tag)
            if name == "link" and not child.text:
                fields["link"] = child.attrib.get("href", "")   # Atom form
            elif name not in fields:
                fields[name] = child.text
        title = _clean(fields.get("title"))
        if not title:
            continue
        items.append(Item(
            title=title,
            link=(fields.get("link") or "").strip(),
            source=source,
            summary=_clean(fields.get("description") or fields.get("summary")
                           or fields.get("content"))[:400],
            published=_when(fields.get("pubDate") or fields.get("updated")
                            or fields.get("published")),
        ))
    return items


def host(url: str) -> str:
    """The site a link points at, for printing: "404media.co", not a URL."""
    return urllib.parse.urlsplit(url).netloc.replace("www.", "")


@dataclass(frozen=True)
class Feed:
    url: str
    name: str = ""             # printed under a headline; "" = the feed's own
    weight: float = 1.0
    max_age_hours: float | None = None   # None = the caller's default
    group: str = ""


def feeds(raw: list) -> list[Feed]:
    """Config entries - URL strings or tables - as `Feed`s. Bad entries drop."""
    out: list[Feed] = []
    for entry in raw or []:
        if isinstance(entry, str):
            out.append(Feed(url=entry))
        elif isinstance(entry, dict) and entry.get("url"):
            age = entry.get("max_age_hours")
            out.append(Feed(url=str(entry["url"]), name=str(entry.get("name", "")),
                            weight=float(entry.get("weight", 1.0)),
                            max_age_hours=float(age) if age else None,
                            group=str(entry.get("group", ""))))
    return out


def fetch(url: str) -> list[Item]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return parse(r.read().decode("utf-8", errors="replace"), host(url))


def _download(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def gather(urls: list, *, store: Any = None, offline: bool = False,
           max_age_hours: float = 36, memo: dict | None = None) -> list[Item]:
    """Every item from every feed, freshest first. Never raises for one feed.

    `urls` is config entries or `Feed`s. Feeds download in parallel - thirty
    one after the other is minutes on a slow morning. Successful pulls are
    cached per feed, so an outage degrades to yesterday's headlines rather than
    an empty section. `memo` (pass `ctx.shared`) keeps one download per feed per
    run when two slots read the same feed.
    """
    wanted = feeds(urls)
    memo = memo if memo is not None else {}
    cache = memo.setdefault("rss:raw", {})

    todo = [f.url for f in wanted if f.url not in cache]
    if todo and not offline:
        with ThreadPoolExecutor(max_workers=12) as pool:
            for url, raw in zip(todo, pool.map(_download, todo)):
                cache[url] = raw
                if raw and store is not None:
                    store.put(NAMESPACE, url, raw)

    out: list[Item] = []
    for feed in wanted:
        raw = cache.get(feed.url)
        if raw is None and store is not None:
            raw = store.fetch(NAMESPACE, feed.url)
        if not raw:
            continue
        try:
            got = parse(raw, host(feed.url))
        except ElementTree.ParseError:
            continue
        limit = feed.max_age_hours or max_age_hours
        for item in got:
            if item.age_hours > limit:
                continue
            if feed.name:
                item.source = feed.name
            item.weight, item.group = feed.weight, feed.group
            out.append(item)

    out.sort(key=lambda i: i.published or datetime.min.replace(
        tzinfo=timezone.utc), reverse=True)
    return out
