"""Wikipedia, for slots 30 (rabbit hole) and 138 (most-read), and the Daily
Roll's photograph (`picture_of_the_day`).

Two endpoints, both on `en.wikipedia.org/api/rest_v1`, both open with no key.
The newer `api.wikimedia.org` host wants an account for some feeds; this one
does not, and is what the mobile apps use.

**The most-read feed needs filtering, not just ranking.** What people actually
read yesterday is reliably strange - and reliably also full of whoever died.
A live sample returned a killing at number two. `SLOTS.md` sells this slot as
"stranger than the news", so a death or disaster article defeats the point of
it: the receipt already carries three headlines, and this is the section that is
supposed to be a relief from them. Grim entries are dropped here rather than
ranked down, the same call the news slot made and for the same reason - ranking
only promotes the next one.

Wikipedia's own main-page fixtures are also excluded. "Main Page" and
"Special:Search" are always near the top of the pageview list and are not
articles.
"""

from __future__ import annotations

import re
from datetime import date as Date, timedelta
from typing import Any
from urllib.parse import quote

from .http import SourceUnavailable, cached_json, get_bytes, get_json

NAMESPACE = "wikipedia"
REST = "https://en.wikipedia.org/api/rest_v1"

_WORD = re.compile(r"[a-z']+")

# Shares its intent with `slots.news._GRIM` but not its list: a pageview chart
# is dominated by deaths, killings and disasters in a way a curated feed is not,
# so this leans harder and includes the words that mark an article *about* a
# person's death rather than a news event.
_GRIM = {
    "killing", "killed", "kill", "murder", "murders", "murdered", "death",
    "deaths", "died", "dies", "dead", "massacre", "shooting", "shootings",
    "shot", "assassination", "bombing", "terrorist", "terrorism", "attack",
    "war", "genocide", "holocaust", "rape", "abuse", "assault", "suicide",
    "crash", "disaster", "earthquake", "hurricane", "wildfire", "famine",
    "execution", "executed", "hostage", "kidnapping", "trafficking", "victim",
    "victims", "disappearance", "manslaughter", "homicide", "funeral",
}

_NOT_ARTICLES = {"main page", "special:search", "wikipedia:featured pictures"}


def _is_grim(title: str, extract: str) -> bool:
    # The title carries most of the signal; the first sentence catches the
    # biographies whose title is only a name.
    words = set(_WORD.findall(f"{title} {extract[:180]}".lower()))
    return bool(words & _GRIM)


# Wikipedia's one-line `description` field is an unusually clean signal for what
# kind of thing an article is. "American tennis player (born 2002)" and
# "Equations of motion for viscous fluids" are trivially separable, and on any
# given day the pageview chart is mostly the former.
_PERSON_HINT = re.compile(
    r"\(born \d{4}\)|\b(?:player|footballer|actor|actress|singer|rapper|"
    r"musician|politician|athlete|boxer|wrestler|model|presenter|youtuber|"
    r"comedian|businessman|businesswoman|entrepreneur)\b", re.I)
_MEDIA_HINT = re.compile(
    r"\b(?:film|album|song|series|season|episode|video game|novel|"
    r"television|sitcom|tournament|championship|league|match)\b", re.I)


def _interest(article: dict) -> float:
    """How much of a rabbit hole this is, rather than how many read it.

    `SLOTS.md` sells slot 138 as "the article people actually read, which is
    reliably stranger than the news". On a live sample the top six were five
    tennis players and the Navier-Stokes equations - so taking the most-read
    article delivers a sportsperson, not a curiosity. The whole list is genuinely
    what people read; picking the interesting one out of it keeps the premise and
    the honesty, provided the real rank goes on the paper too.
    """
    blob = f"{article['description']} {article['extract'][:160]}"
    score = 0.0
    if _PERSON_HINT.search(blob):
        score -= 3.0
    if _MEDIA_HINT.search(blob):
        score -= 1.0
    if not article["description"]:
        score -= 0.5           # usually a stub or a disambiguation
    # A gentle pull back towards the top of the chart, so an obscure entry at
    # number forty does not beat a genuinely odd thing at number three.
    return score - 0.06 * article["rank"]


def most_read(day: Date, *, store: Any = None, offline: bool = False,
              limit: int = 25) -> list[dict]:
    """Yesterday's most-read articles, grim ones removed, most-read first.

    `rank` is the article's true position in the pageview chart *before*
    filtering, so anything printed about where it placed stays accurate.
    """
    when = day - timedelta(days=1)
    key = when.isoformat()
    url = f"{REST}/feed/featured/{when:%Y/%m/%d}"
    payload, stale = cached_json(url, store=store, namespace=f"{NAMESPACE}:mostread",
                                 key=key, offline=offline, when=day)

    out = []
    for rank, article in enumerate((payload.get("mostread") or {})
                                   .get("articles", []), start=1):
        title = (article.get("titles") or {}).get("normalized") or ""
        extract = article.get("extract") or ""
        if not title or title.lower() in _NOT_ARTICLES:
            continue
        if _is_grim(title, extract):
            continue
        out.append({
            "title": title,
            "rank": rank,
            "views": article.get("views", 0),
            "extract": extract,
            "description": article.get("description") or "",
            "url": ((article.get("content_urls") or {}).get("desktop") or {})
                   .get("page", ""),
            "stale": stale,
        })
        if len(out) >= limit:
            break

    if not out:
        raise SourceUnavailable("most-read returned nothing usable")
    return out


def most_interesting(articles: list[dict]) -> dict:
    """The best rabbit hole among yesterday's most-read."""
    return max(articles, key=_interest)


def summary(title: str, *, store: Any = None, offline: bool = False,
            when: Date | None = None) -> dict:
    """One article's REST summary: title, description, first paragraph, URL."""
    url = f"{REST}/page/summary/{quote(title.replace(' ', '_'), safe='')}"
    payload, stale = cached_json(url, store=store, namespace=f"{NAMESPACE}:summary",
                                 key=title, offline=offline, when=when)
    return {
        "title": payload.get("title") or title,
        "description": payload.get("description") or "",
        "extract": payload.get("extract") or "",
        "url": ((payload.get("content_urls") or {}).get("desktop") or {})
               .get("page", f"https://en.wikipedia.org/wiki/"
                            f"{quote(title.replace(' ', '_'))}"),
        "stale": stale,
    }


def first_sentence(extract: str, limit: int = 240) -> str:
    """The opening sentence, which is the one Wikipedia writes hardest.

    Abbreviations make naive splitting wrong, so full stops followed by a
    lowercase letter or sitting inside a short token are not treated as ends.
    """
    text = " ".join(extract.split())
    for match in re.finditer(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text):
        head = text[:match.start()]
        if len(head) < 40:
            continue                       # "Dr. Smith" and friends
        if re.search(r"\b(?:[A-Z]|no|vol|st|mt|approx)\.$", head, re.I):
            continue
        return head
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


def _plain(field: Any) -> str:
    """The text of one of the feed's {"text", "html"} fields, on one line."""
    text = (field or {}).get("text", "") if isinstance(field, dict) else ""
    return " ".join(str(text).split())


def picture_of_the_day(day: Date, *, store: Any = None,
                       offline: bool = False) -> dict:
    """Wikimedia Commons' picture of the day: what it shows and the image.

    It rides in the same featured feed as most-read, under `image`. Returns
    title, description, artist, licence and the JPEG bytes. The bytes are cached
    with the metadata (base64), not just the URL: a picture whose URL survived
    but whose image did not is no use to an offline morning, which prints the
    last one it saw rather than nothing. Raises SourceUnavailable when there is
    neither.
    """
    import base64
    namespace, key = f"{NAMESPACE}:potd", day.isoformat()
    entry = None
    if not offline:
        try:
            image = get_json(f"{REST}/feed/featured/{day:%Y/%m/%d}").get("image") or {}
            source = (image.get("thumbnail") or {}).get("source")
            if source:
                title = re.sub(r"\.[a-z0-9]+$", "", image.get("title", ""),
                               flags=re.I).removeprefix("File:").replace("_", " ")
                entry = {"title": title.strip(),
                         "description": _plain(image.get("description")),
                         "artist": _plain(image.get("artist")),
                         "licence": ((image.get("license") or {}).get("type") or ""),
                         "jpeg": base64.b64encode(get_bytes(source)).decode()}
                if store is not None:
                    store.put(namespace, key, entry, when=day)
        except Exception:  # noqa: BLE001 - fall back to the cache
            entry = None
    if entry is None and store is not None:
        entry = store.fetch(namespace, key)
        if entry is None:
            latest = store.latest(namespace)
            entry = latest[1] if latest else None
    if not entry:
        raise SourceUnavailable("no picture of the day, live or cached")
    return dict(entry, jpeg=base64.b64decode(entry["jpeg"]))

