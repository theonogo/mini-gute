"""The live-search slots - 93, 94, 96, 98, 99, 110, 114, 130.

These are the flakiest sections on the receipt: slowest, likeliest to come back
with nothing, and the only ones whose content does not exist until the morning
it prints. `SLOTS.md` puts them all at uncommon or rarer and requires every one
to have a cached fallback.

**They cost no extra round trip.** Anthropic's web search runs server-side, so
declaring it on the narrator's single daily call is enough - the results come
back as content blocks in the same response, alongside the structured output.

**The fallback is the previous answer, and it says how old it is.** Unlike every
other slot here, a search slot has no content of its own - the section *is* the
generated text. So there is nothing to degrade to except the last time it
worked. `remember()` stores what the narrator wrote; `recall()` serves it back
with its date attached. A three-day-old good sentence is worth printing. A
three-day-old sentence passed off as today's is not, which is why the date goes
on the paper.

**What search may and may not be used for.** Everything here is a *finding* -
something that exists in the world and could be checked. The narrator's house
rule against inventing facts applies with full force, and these briefs say so
individually, because a search slot is the one place where the model is
explicitly reaching outside its brief and the ordinary guard rail does not
apply.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Any

import config

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "search"
# Past this, a cached answer is too stale to be worth the paper.
MAX_CACHE_DAYS = 21


def remember(store: Any, slot_id: int, head: str, body: str,
             day: Date) -> None:
    """Keep what the narrator wrote, for the day the search comes back empty."""
    if store is None or not body:
        return
    try:
        store.put(NAMESPACE, str(slot_id),
                  {"head": head, "body": body, "day": day.isoformat()},
                  when=day)
    except Exception:  # noqa: BLE001 - never break a print over a cache write
        pass


def recall(store: Any, slot_id: int, day: Date) -> dict | None:
    """The last thing this slot successfully said, if it is recent enough."""
    if store is None:
        return None
    try:
        got = store.fetch(NAMESPACE, str(slot_id))
    except Exception:  # noqa: BLE001
        return None
    if not got or not got.get("body"):
        return None
    try:
        age = (day - Date.fromisoformat(got["day"])).days
    except (KeyError, ValueError):
        return None
    if age < 0 or age > MAX_CACHE_DAYS:
        return None
    got["age_days"] = age
    return got


class SearchSlot(Slot):
    """Shared shape: a brief the narrator searches against, and a cache.

    Subclasses declare `spec`, a fallback `HEAD`, and `brief()`. They do not
    implement `fetch` - there is nothing to fetch here, because the narrator is
    the collector. What `fetch` returns is the *instruction* plus whatever the
    slot last managed to say.
    """

    HEAD = "Found Today"
    # Printed if there is no cache either. Deliberately in-character about the
    # failure rather than blank: SYSTEM.md 7 says a dead source is content.
    EMPTY = "Nothing worth reporting was found."

    def brief(self, ctx: Context) -> dict:
        raise NotImplementedError

    def fetch(self, ctx: Context) -> SlotResult:
        cached = recall(ctx.store, self.spec.id, ctx.date)
        brief = dict(self.brief(ctx))
        brief.setdefault("today", ctx.date.isoformat())
        if cached:
            # Handed to the narrator so it can avoid repeating itself, not so it
            # can reuse it.
            brief["previously"] = cached["body"][:300]

        body = cached["body"] if cached else self.EMPTY
        fine = None
        if cached:
            age = cached["age_days"]
            fine = ("from the archive, " +
                    ("earlier today" if age == 0 else
                     "yesterday" if age == 1 else f"{age} days old"))
        # The archive note belongs to the cached body, not to what the narrator
        # finds today: when it searches and writes afresh, the note goes too.
        return SlotResult(head=self.HEAD, body=body, fine=fine, brief=brief,
                          fallback=True)

    def after_narration(self, store: Any, day: Date, head: str,
                        body: str) -> None:
        remember(store, self.spec.id, head, body, day)

    def fixture(self, ctx: Context) -> SlotResult:
        """Offline: whatever it last said, or nothing.

        No invented sample. A fabricated "finding" in a fixture is one careless
        copy-paste away from being printed as real.
        """
        cached = recall(ctx.store, self.spec.id, ctx.date)
        return SlotResult(
            head=self.HEAD,
            body=cached["body"] if cached else self.EMPTY,
            fine="offline" if not cached else "from the archive",
            brief={"verbatim": True, "instruction": "Name this section in "
                                                    "voice."},
        )


def _brief(instruction: str, **extra: Any) -> dict:
    return {"instruction": instruction, **extra}


# --------------------------------------------------------------------------
@register
class FunFact(SearchSlot):
    spec = SlotSpec(id=130, name="Fun fact", tier="common", paper_mm=24,
                    needs_network=True, needs_narrator=True, needs_search=True)
    HEAD = "Fun Fact"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for one genuinely surprising true fact and give it in one "
            "or two sentences, in voice. It must be REAL and checkable - this "
            "is a factual section and the reader may well look it up. Prefer "
            "something specific and concrete over a category of thing. Avoid "
            "the well-worn ones everybody has already heard.")


@register
class ExplainAtLunch(SearchSlot):
    spec = SlotSpec(id=110, name="Explain this like I'll be asked at lunch",
                    tier="common", paper_mm=34, needs_network=True,
                    needs_narrator=True, needs_search=True)
    HEAD = "For Lunch"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for the thing most discussed in the last day or two, and "
            "explain it in three short lines - enough to hold a conversation "
            "about it at lunch without having read anything. What happened, "
            "why people care, what is still unsettled. In voice, but the facts "
            "are facts: no speculation presented as reporting.")


@register
class BangerCorner(SearchSlot):
    spec = SlotSpec(id=93, name="Banger corner", tier="uncommon", paper_mm=24,
                    needs_network=True, needs_narrator=True, needs_search=True)
    HEAD = "One Good Thing"

    def brief(self, ctx: Context) -> dict:
        # The catalogue says the persona renames this every time but the spirit
        # of the name stays - so the instruction carries the spirit rather than
        # the name.
        return _brief(
            "Search for one thing that genuinely got BETTER in the last day or "
            "two - a real improvement somewhere in the world, however small. "
            "Not a plan, not a promise, not a funding round: something that has "
            "actually happened. One or two sentences in voice. Rename the "
            "section in your own words, keeping the spirit of good news filed "
            "plainly.")


@register
class PersonWorthKnowing(SearchSlot):
    spec = SlotSpec(id=114, name="A person worth knowing about",
                    tier="uncommon", paper_mm=34, needs_network=True,
                    needs_narrator=True, needs_search=True)
    HEAD = "Worth Knowing About"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for someone remarkable and largely unknown, and say who "
            "they were and what they did, in two or three sentences, in voice. "
            "A real person with a real record - name, roughly when, and the "
            "specific thing. Not a household name. Living or dead. Do not "
            "embellish the achievement.")


@register
class CurioPriceCheck(SearchSlot):
    spec = SlotSpec(id=99, name="Curio price check", tier="uncommon",
                    paper_mm=22, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Price Check"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for an object, auction lot or oddity currently for sale or "
            "recently sold, and give it with its price, in one or two "
            "sentences, in voice. It should be noteworthy or strange - never "
            "mundane. THE NUMBER ONLY: state what it cost and nothing about "
            "whether it is worth it, and give no advice of any kind.")


@register
class GithubRepo(SearchSlot):
    spec = SlotSpec(id=94, name="GitHub repo that blew up", tier="rare",
                    paper_mm=26, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Repo Of Note"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for a software project that has gained a lot of attention "
            "in the last week or so. Say what it does in one sentence, then "
            "give an HONEST line on whether it is actually any good or merely "
            "hype - the second half is the point of the section, and 'too early "
            "to say' is a legitimate answer. In voice.")


@register
class SomeoneSolvedSomething(SearchSlot):
    spec = SlotSpec(id=96, name="Someone solved something", tier="rare",
                    paper_mm=26, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Solved"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for a real result from the past week - a proof, a "
            "discovery, a long-standing problem answered, a thing built that "
            "did not work before. Three lines: what the problem was, what the "
            "answer is, who got there. In voice. Do not overstate the finding, "
            "and do not report a preprint as a settled result.")


@register
class BestSentence(SearchSlot):
    spec = SlotSpec(id=98, name="Today's best sentence", tier="rare",
                    paper_mm=24, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Best Sentence Found Today"

    def brief(self, ctx: Context) -> dict:
        # Curatorial rather than informational, per the catalogue - so the
        # quotation is the content and the persona only frames it.
        return _brief(
            "Search recent writing - journalism, essays, reviews, obituaries - "
            "and find the single best-written SENTENCE you come across. Quote "
            "it EXACTLY, in quotation marks, and attribute it to its author and "
            "where it appeared. The quotation must be verbatim and real; if you "
            "cannot verify the wording, choose a different one. Add at most one "
            "short line of your own around it - this section is curation, not "
            "commentary.")


# --------------------------------------------------------------------------
# The three that need to know where the reader is. Location lives in `.env`
# and is read at fetch time rather than baked into the brief, so a move takes
# effect the next morning.
def _place() -> str | None:
    try:
        _, _, name = config.location()
        return name or None
    except Exception:  # noqa: BLE001 - an unset location drops the slot
        return None


def _city() -> str | None:
    """The city rather than the suburb: QG_CITY, else the location name."""
    try:
        return config.city() or None
    except Exception:  # noqa: BLE001 - an unset city drops the slot
        return None


class LocalSearchSlot(SearchSlot):
    """A search slot that is meaningless without a place to search near."""

    def place(self) -> str | None:
        return _place()

    def fetch(self, ctx: Context) -> SlotResult | None:
        if not self.place():
            return None          # not a failure - there is simply no locality
        return super().fetch(ctx)


@register
class WhatsOnTonight(LocalSearchSlot):
    spec = SlotSpec(id=95, name="What's on in the city tonight", tier="uncommon",
                    paper_mm=26, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Tonight"

    def place(self) -> str | None:
        # The city, not the suburb: nothing is ever on in a suburb.
        return _city()

    def brief(self, ctx: Context) -> dict:
        # The catalogue notes venue listings are unstructured HTML that no API
        # covers, which is exactly why this is a search slot rather than a feed.
        return _brief(
            f"Search for ONE thing happening in or near {self.place()} tonight "
            f"or in the next few days - a gig, a talk, an exhibition, a screening, "
            f"a market. Give what it is, where, and when, in one or two "
            f"sentences, in voice. It must be a real event that is actually on: "
            f"if you cannot confirm the date and the venue, say you found "
            f"nothing rather than offering something plausible.",
            near=self.place())


@register
class CheckOutThisPlace(LocalSearchSlot):
    spec = SlotSpec(id=133, name="Check out this place", tier="rare",
                    paper_mm=30, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Worth A Look"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            f"Search for a place near {_place()} that is either new or has "
            f"recently been reviewed well - a restaurant, bar, shop, cafe, "
            f"gallery. Write it as a small advertisement, in voice: what it is, "
            f"where, and the one thing that makes it worth the walk. It must "
            f"be real and currently open. Do not invent an address, and do not "
            f"quote a review you cannot verify.",
            near=_place())


@register
class Steelman(SearchSlot):
    spec = SlotSpec(id=111, name="Steelman", tier="rare", paper_mm=38,
                    needs_network=True, needs_narrator=True, needs_search=True)
    HEAD = "The Other Side"

    def brief(self, ctx: Context) -> dict:
        from .news import profile_terms

        _, disliked = profile_terms()
        subject = ""
        if disliked:
            subject = ctx.rng(self.spec.id).choice(sorted(disliked))
        return _brief(
            f"Take a position {config.reader_name()} would probably disagree "
            "with and argue it as "
            "WELL as it can honestly be argued, in four lines. Search for the "
            "actual strongest case rather than reconstructing it from memory, "
            "and use real reasoning that real proponents give. This is a "
            "steelman: no strawman, no sneering, and no closing line that "
            "undercuts what you just built. State the position plainly first, "
            "then the best case for it.",
            # A seed rather than an instruction: the profile's anti-list is the
            # nearest thing we have to knowing what the reader disagrees with, and a
            # single term is enough to point the search somewhere specific
            # instead of at "a controversial topic".
            starting_point=subject or "anything from the profile's anti-list")


@register
class YouWereWrongAbout(SearchSlot):
    spec = SlotSpec(id=116, name="You were wrong about", tier="rare",
                    paper_mm=30, needs_network=True, needs_narrator=True,
                    needs_search=True)
    HEAD = "Scored In Hindsight"

    def brief(self, ctx: Context) -> dict:
        return _brief(
            "Search for a confident prediction, forecast or verdict made a "
            "while ago about something that has since resolved, and score how "
            "it actually turned out. Who said what, when, and what happened "
            "instead. Two or three sentences, in voice. Both halves must be "
            "real and checkable - this only works if the prediction was "
            "genuinely made and the outcome genuinely known. Pick predictions "
            "about technology, science, business or culture, not about "
            "individual people's private lives.")
