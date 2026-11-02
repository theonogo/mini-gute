"""Slot 10 - News x3.

Three headlines from a mixed diet of feeds, ranked against `data/profile.md`.

**Two rankers, prose first.** `narrator.rank` reads the prose of profile.md -
the sentences, with their qualifications and their tone - and picks the day's
three. Keyword overlap is the fallback for an offline morning, no API key, or a
call that fails, and it is blunter for a reason: prose defeats it. "Acquisitions,
unless the thing acquired is interesting on its own" puts *interesting* into the
anti-list, which is the opposite of what the sentence says.

**A fair look, on a fixed budget.** Feeds chosen for the profile rather than
for being news, and weighted in `config.toml` by how good each is for this
reader. The ranker reads `[news] candidates` of them and no more - that number
is the token bill. Every feed gets one seat, then the rest go by weight
(D'Hondt), so a blog that posts twice a day is in front of the ranker as surely
as a wire that posts a hundred times. Within a feed the
freshest go first, except Hacker News, which is read in points order: its
highest-ranked posts, not its newest.

**A link aggregator gets its article read.** A Hacker News item is a title and
two vote counts. `sources.article` reads the linked page's own description, and
the top comment when the page says nothing, so the ranker picks from what the
item is and the gloss says it. Only for HN items in the pool - a handful of
fetches, cached per URL.

**The diversity rules are Python's either way.** One headline per outlet and at
most `grim_max` grim headlines are applied to whichever order comes back, and a
short pick is topped up from the keyword ranking. A model that returns three
disasters from the same wire does not get to make that a bad morning.

**It remembers what it printed.** A 36-hour window means yesterday's headline is
still a candidate today. Printed headlines are kept for `memory_days`; the same
link or title never prints twice, and the ranker is shown the list so that the
same story under a new headline is skipped too - unless it has genuinely moved
on, in which case the note says it is a follow-up and of which day.

Two rules from SLOTS.md that outlive the ranking:

  * **Headlines need not be serious.** A genuinely strange story counts as news.
    Nor are serious ones avoided: an important story earns its place even
    when it is grim.
  * **Persona touch is capped lower here than anywhere else** - header styling
    and a light flavour, never a rewrite. Headlines are facts about the world;
    they go in `body` verbatim, not in `brief` where they could be reworded.
"""

from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date as Date, timedelta
from pathlib import Path

import config
from sources import article, rss

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# Slot 112 reads the headlines that actually printed from here.
SHARED_KEY = "news:headlines"
# What printed on each day, for tomorrow's ranker. Keyed by ISO date.
PRINTED = "news:printed"

PROFILE = Path(__file__).resolve().parent.parent / "data" / "profile.md"
_WORD = re.compile(r"[a-z][a-z'-]{3,}")

# Words that carry no signal about taste, so matching on them is noise.
_STOP = {
    "this", "that", "with", "from", "have", "than", "them", "they", "there",
    "about", "which", "their", "would", "could", "only", "over", "into",
    "more", "most", "some", "such", "when", "what", "were", "been", "being",
    "prefer", "rather", "beats", "unless", "thing", "things", "story",
    "stories", "news", "piece", "coverage", "anything", "something",
    "interested", "genuinely", "especially", "worth", "read", "file", "slot",
    "phase", "keywords", "wording", "matters", "write", "list", "edit",
}


def _terms(block: str) -> set[str]:
    return {w for w in _WORD.findall(block.lower()) if w not in _STOP}


# Headlines about death and disaster. Serious news is news, and the cap
# (`[news] grim_max`) is only there so the whole section is never bleak. Capped
# rather than ranked down, which would only promote the next disaster.
# Death and disaster only: "shot", "strike", "fire" and "arrested" used to be
# here and caught a game-winner, a transport strike and a coach being fired.
_GRIM = {
    "killed", "dead", "death", "deaths", "dies", "died", "fatal", "victims",
    "toll", "attack", "attacks", "war", "bombing", "airstrike", "airstrikes",
    "shooting", "murder", "murdered", "assault", "invasion", "troops",
    "crash", "crashed", "wreck", "blaze", "explosion", "quake",
    "earthquake", "flood", "floods", "famine", "outbreak", "collapse",
    "massacre", "hostage", "abuse", "trafficking",
}


def profile_terms() -> tuple[set[str], set[str]]:
    """(liked, disliked) vocabulary from profile.md.

    Prefers the explicit `## Keywords` block. The prose sections are written for
    the narrator, and reading them as a bag of words misfires on qualifiers:
    "acquisitions, unless the thing acquired is interesting on its own" put
    *interesting* into the anti-list, which is the opposite of what it says.
    """
    if not PROFILE.exists():
        return set(), set()
    text = PROFILE.read_text(encoding="utf-8")

    def section(name: str) -> str:
        m = re.search(rf"##\s*{name}(.*?)(?=\n##|\Z)", text,
                      re.S | re.I)
        return m.group(1) if m else ""

    keywords = section("Keywords")
    if keywords.strip():
        def listed(label: str) -> set[str]:
            m = re.search(rf"^{label}:(.*?)(?=^\w+:|\Z)", keywords,
                          re.S | re.I | re.M)
            if not m:
                return set()
            return {w.strip().lower() for w in re.split(r"[,\n]", m.group(1))
                    if w.strip()}
        return listed("liked"), listed("disliked")

    return _terms(section("Interested in")), _terms(section("Not interested in"))


def is_grim(title: str) -> bool:
    return bool(_terms(title) & _GRIM)


def score(title: str, liked: set[str], disliked: set[str]) -> float:
    words = _terms(title)
    # Anti-matches weigh more than matches: keeping the wrong thing off the
    # paper matters more than ranking the right things perfectly.
    return len(words & liked) - 3.0 * len(words & disliked)


_HN = re.compile(r"Points:\s*(\d+).*?#\s*Comments:\s*(\d+)", re.S)


def hn_counts(item: rss.Item) -> tuple[int, int] | None:
    """(points, comments) for a Hacker News item, None for anything else."""
    m = _HN.search(item.summary)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _first_sentence(text: str, limit: int) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    first = m.group(1) if m else text
    return first if len(first) <= limit else ""


def summary_for(item: rss.Item, about: dict | None = None,
                limit: int = 160) -> str:
    """What the ranker is told about an item, cut to `limit` characters.

    Every candidate costs its summary in tokens every morning, so it is cut
    here, once. A Hacker News item carries no description of its own: it gets
    the linked page's (`about`, from `sources.article`), or the top comment's
    words, labelled as a comment so the gloss can never pass them off as the
    article - and the vote counts, which say how much of a stir it is.
    """
    counts = hn_counts(item)
    if counts:
        stir = f"(Hacker News: {counts[0]} points, {counts[1]} comments)"
        about = about or {}
        # A little more room than a feed summary: there are only a handful of
        # these, and a description cut mid-clause invites the gloss to finish
        # the sentence from memory.
        limit += 80
        if about.get("article"):
            return f"{article.trim(about['article'], limit)} {stir}"
        if about.get("comment"):
            return (f'Top comment on Hacker News: '
                    f'"{article.trim(about["comment"], limit)}" {stir}')
        return f"A link posted to Hacker News, no description. {stir}"
    without_urls = re.sub(r"https?://\S+", "", item.summary).strip()
    return article.trim(without_urls, limit) if len(without_urls) > 25 else ""


def offline_gloss(item: rss.Item, about: dict | None = None) -> str:
    """The line under a headline when there is no ranker to write one.

    Quoted from the feed or the page, never composed: the first sentence of
    the description if it is short enough to sit under a headline.
    """
    counts = hn_counts(item)
    about = about or {}
    if counts:
        if about.get("article"):
            return _first_sentence(about["article"], GLOSS_CHARS)
        if about.get("comment"):
            return f'Top comment: "{article.trim(about["comment"], 80)}"'
        return f"{counts[0]} points, {counts[1]} comments on Hacker News"
    text = re.sub(r"https?://\S+", "", item.summary).strip()
    return _first_sentence(text, GLOSS_CHARS)


def prose() -> str:
    """The profile's prose sections. The `## Keywords` block is for the fallback
    ranker alone and would only crowd the real sentences."""
    if not PROFILE.exists():
        return ""
    text = PROFILE.read_text(encoding="utf-8")
    return re.split(r"^##\s*Keywords", text, maxsplit=1, flags=re.M | re.I)[0].strip()


def _key(title: str) -> str:
    return " ".join(title.lower().split())[:60]


def pool(items: list[rss.Item], budget: int) -> list[rss.Item]:
    """The candidates the ranker reads: a fair share of every feed.

    One seat each, then the rest by D'Hondt on the feed weights, so the share
    follows the weight and a quiet feed's leftover seats go to the others.
    Within a feed, freshest first - `items` arrives that way - except Hacker
    News, read in points order: its best-ranked posts, not its newest.
    """
    by_feed: dict[str, list[rss.Item]] = {}
    for item in items:
        by_feed.setdefault(item.source, []).append(item)
    for name, got in by_feed.items():
        if all(hn_counts(i) for i in got):
            got.sort(key=lambda i: hn_counts(i)[0], reverse=True)

    seats = {name: 0 for name in by_feed}
    chosen: list[rss.Item] = []
    while len(chosen) < budget:
        open_ = [n for n in by_feed if seats[n] < len(by_feed[n])]
        if not open_:
            break
        # Everyone's first seat before anyone's second, then by weight.
        name = max(open_, key=lambda n: (seats[n] == 0,
                                         by_feed[n][0].weight / (seats[n] + 1)))
        chosen.append(by_feed[name][seats[name]])
        seats[name] += 1
    return chosen


def pick(items: list[rss.Item], count: int, max_chars: int,
         order: list | None = None,
         offered: list[rss.Item] | None = None,
         grim_max: int = 2) -> list[rss.Item]:
    """The day's headlines: the ranker's order, then the diversity rules.

    `order` holds the ranker's picks as indices into `offered`. Without one,
    the keyword ranking over every item decides, nudged by feed weight.
    """
    fitting = [i for i in items if len(i.title) <= max_chars]
    liked, disliked = profile_terms()
    ranked = sorted(fitting,
                    key=lambda i: (score(i.title, liked, disliked)
                                   + 0.5 * math.log2(max(i.weight, 0.1)),
                                   -i.age_hours),
                    reverse=True)
    if order and offered:
        # The narrator's order first, then the keyword ranking to top up a
        # short or duplicated pick.
        picked = [offered[p.index] for p in order if p.index < len(offered)]
        seen = {id(i) for i in picked}
        ranked = picked + [i for i in ranked if id(i) not in seen]

    chosen: list[rss.Item] = []
    seen_sources: set[str] = set()
    seen_titles: set[str] = set()

    # Never more than count - 1, so at least one headline is not bleak.
    grim_cap = max(1, min(grim_max, count - 1))

    def take(item: rss.Item) -> bool:
        key = _key(item.title)
        if key in seen_titles:
            return False
        if is_grim(item.title) and sum(is_grim(c.title) for c in chosen) >= grim_cap:
            return False
        chosen.append(item)
        seen_sources.add(item.source)
        seen_titles.add(key)
        return len(chosen) == count

    # Best from each outlet first, so one prolific feed cannot take the whole
    # section, then fill any shortfall from what is left.
    for item in ranked:
        if item.source not in seen_sources and take(item):
            return chosen
    for item in ranked:
        if take(item):
            return chosen
    return chosen


# --- memory ---------------------------------------------------------------

def printed_before(store, day: Date, days: int) -> list[dict]:
    """Headlines printed in the `days` before `day`, oldest first."""
    if store is None:
        return []
    out: list[dict] = []
    for back in range(days, 0, -1):
        when = day - timedelta(days=back)
        try:
            got = store.fetch(PRINTED, when.isoformat()) or []
        except Exception:  # noqa: BLE001 - memory is never worth a crash
            got = []
        out.extend(dict(h, day=when.isoformat()) for h in got)
    return out


def _when(day: Date, then: str) -> str:
    """How the ranker and the note refer to a past day: "yesterday", "Tuesday"."""
    then_day = Date.fromisoformat(then)
    gap = (day - then_day).days
    return "yesterday" if gap == 1 else then_day.strftime("%A")


# A gloss sits on one or two lines under its headline. Past this it is a
# paragraph, whatever the ranker meant.
GLOSS_CHARS = 110
# Between the parts of a note's label. A middle dot is Latin-1, so every face
# on the page has it - unlike the em dash.
SEP = " · "


def _plain(text: str) -> str:
    """Escaped, with the dashes the pixel faces have no glyph for removed.

    VT323 and the other pixel faces print a tofu box for an em or en dash.
    Headlines are quoted verbatim and keep whatever they came with; everything
    we write around them - the gloss, the source - is ours to normalise.
    """
    text = text.replace("—", " - ").replace("–", "-")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def headline_html(item: rss.Item, gloss: str, follow_up: str = "") -> str:
    """One line for `news_block` to split on: a headline and the note under it.

    Two children, always, because two is what the themes lay out - the marker
    the template prints, and ONE block holding the headline and everything
    beneath it. A note added as a third child lands in the marker's column.

    The note's label line says where the story is from - the outlet, and for
    an aggregator the site the link goes to, which says what kind of thing it
    is before a word is read - and, for a story already printed this week, that
    this is a follow-up. The gloss sits under it. The section renders with
    `autoescape=False`, like every other slot body, so the headline is escaped
    here too.
    """
    label = [item.source]
    if hn_counts(item) and item.link and "ycombinator" not in item.link:
        label.append(rss.host(item.link))
    if follow_up:
        label.append(f"follow-up from {follow_up}")
    note = f'<span class="news-src">{_plain(SEP.join(label))}</span>'
    if gloss:
        note += _plain(article.trim(gloss, GLOSS_CHARS))
    title = (item.title.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;"))
    return (f'<div class="news-body">{title}'
            f'<div class="news-note">{note}</div></div>')


def _read_links(items: list[rss.Item], ctx: Context) -> dict[str, dict]:
    """The linked page's words for every Hacker News item in `items`.

    The pages are read in parallel; the cache is read and written here, on the
    main thread, because a SQLite connection refuses any other.
    """
    out: dict[str, dict] = {}
    todo: list[rss.Item] = []
    for item in items:
        if not hn_counts(item):
            continue
        hn = article.hn_id(item.summary)
        cached = article.recall(ctx.store, item.link, hn)
        if cached is not None:
            out[item.link] = cached
        elif not ctx.offline:
            todo.append(item)
    if todo:
        with ThreadPoolExecutor(max_workers=6) as ex:
            got = ex.map(lambda i: article.read(i.link,
                                                article.hn_id(i.summary)), todo)
            for item, words in zip(todo, got):
                article.keep(ctx.store, item.link,
                             article.hn_id(item.summary), words)
                out[item.link] = words
    return out


@register
class News(Slot):
    spec = SlotSpec(id=10, name="News x3", tier="spine", paper_mm=35,
                    needs_network=True, needs_narrator=True)

    def fetch(self, ctx: Context) -> SlotResult | None:
        count = int(config.get("news", "count", default=3))
        items = rss.gather(
            config.get("news", "feeds", default=[]),
            store=ctx.store, offline=ctx.offline,
            max_age_hours=float(config.get("news", "max_age_hours", default=36)),
            memo=ctx.shared,
        )
        # Never the same headline twice: a 36-hour window and a weekly feed
        # would otherwise reprint yesterday's.
        days = int(config.get("news", "memory_days", default=5))
        before = printed_before(ctx.store, ctx.date, days)
        old = ({h.get("link") for h in before if h.get("link")}
               | {_key(h["title"]) for h in before})
        items = [i for i in items if i.link not in old and _key(i.title) not in old]
        if not items:
            return None  # nothing to say; the section drops rather than lying

        max_chars = int(config.get("news", "max_chars", default=120))
        grim_max = int(config.get("news", "grim_max", default=2))
        limit = int(config.get("news", "summary_chars", default=120))
        # The ranker is shown this list and answers with indices into it, so
        # every later lookup - the picks and their glosses - has to use the
        # same list, or one story's gloss lands under another's headline.
        offered = pool([i for i in items if len(i.title) <= max_chars],
                       int(config.get("news", "candidates", default=48)))
        about = _read_links(offered, ctx)
        order = None
        if not ctx.offline and ctx.shared.get("may_narrate", True):
            import narrator
            order = narrator.rank(
                ctx.date, prose(),
                [{"title": i.title, "source": i.source,
                  "summary": summary_for(i, about.get(i.link), limit)}
                 for i in offered], count,
                previously=[{"title": h["title"],
                             "when": _when(ctx.date, h["day"])}
                            for h in before],
                grim_max=grim_max)
        chosen = pick(items, count, max_chars, order, offered, grim_max)
        if not chosen:
            return None

        # A gloss belongs to its headline, not to its position: the diversity
        # rules can drop or reorder a pick after the ranker has chosen.
        glosses: dict[str, str] = {}
        follows: dict[str, str] = {}
        for p in order or []:
            if p.index >= len(offered):
                continue
            title = offered[p.index].title
            if p.gloss:
                glosses[title] = p.gloss
            if p.follows is not None:
                follows[title] = _when(ctx.date, before[p.follows]["day"])
        if order is None:
            glosses = {i.title: offline_gloss(i, about.get(i.link))
                       for i in chosen}

        # Slot 112 draws a link between two of today's stories and must work
        # from the ones that actually printed, not its own fetch - a connection
        # between headlines the reader cannot see is not a connection.
        ctx.shared[SHARED_KEY] = [{"title": i.title, "source": i.source}
                                  for i in chosen]
        # Tomorrow's memory. Real mornings only: a --date simulation must not
        # stop a real future morning printing a story, and an evening preview
        # must not replace what this morning actually printed.
        if (ctx.store is not None and ctx.shared.get("real_morning")
                and not ctx.shared.get("printed_already")):
            try:
                ctx.store.put(PRINTED, ctx.date.isoformat(),
                              [{"title": i.title, "source": i.source,
                                "link": i.link} for i in chosen],
                              when=ctx.date)
            except Exception:  # noqa: BLE001 - memory is never worth a crash
                pass

        return SlotResult(
            head="News",
            # Headlines are facts. They reach paper verbatim and are not
            # rewritten - only the section header takes the persona. One line
            # per headline, because `news_block` in main splits the body on
            # newlines; everything under a headline rides inside its line.
            body="\n".join(headline_html(i, glosses.get(i.title, ""),
                                         follows.get(i.title, ""))
                           for i in chosen),
            brief={
                "headlines": [{"title": i.title, "source": i.source}
                              for i in chosen],
                "verbatim": True,
                "instruction": "Style the section header only. Do NOT rewrite "
                               "the headlines - at most one short framing "
                               "clause before them.",
            },
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self.fetch(ctx)
