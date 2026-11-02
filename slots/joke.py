"""Slot 149 - Joke.

A joke the day's persona would actually tell, rather than a joke with a persona
voice applied afterwards. The clerk and the duty officer should not arrive at
the same joke.

**Funny first, in character second.** The first version asked for the joke
"this persona would tell, its own idea of what is funny", and on paper that
read as voice with no punchline: the persona's register landed and the joke
did not. Now the joke has to make an ordinary reader laugh, and the persona is
the delivery - word choice and attitude - never the reason it is funny.

**Two rotating axes.** Rotating only the form leaves every joke aimed at the
same few things, and a joke that is structurally identical to yesterday's is
not a joke at all. So the day draws a **form** and a **subject** to aim it at,
from separate pools, and the persona writes into both.

**Only forms that are meant to land.** Anti-jokes, shaggy-dog stories and
"the second half of a joke you never heard" were in the pool and are cut: each
is built to fall flat on purpose, which reads as a joke that failed when it is
the only one on the page, glanced at over breakfast.

**Recently used pairs are suppressed**, the same mechanism the cheat sheet
uses, because date-seeding alone still lets two puns land in a week.

**It remembers what it told.** The jokes themselves are kept, as written, for
`TOLD_KEEP` mornings and handed back to the narrator as ones not to tell again -
the same punchline in a new form is still the same joke.

The narrator writes the whole thing: nothing here is a fact, so there is nothing
to protect from rephrasing. The fallback pool exists only for the mornings the
call fails, and is deliberately plain - a fallback joke that tried to be in
character would be in the wrong character five days out of ten.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Any

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "joke"
AVOID_LAST = 10
# The jokes as printed, keyed by ISO date, so a re-run of a morning replaces its
# own entry. Roughly the last forty times the slot drew.
TOLD = "told"
TOLD_KEEP = 40

# (key, what the persona is being asked to build)
FORMS: list[tuple[str, str]] = [
    ("oneliner", "a one-liner: a single sentence whose last few words flip "
                 "the meaning of the rest"),
    ("pun", "a pun built on a real double meaning, with a setup that makes the "
            "second meaning land at the very end"),
    ("qa", "a classic question-and-answer joke: a short question, then a "
           "punchline that is surprising and obviously right once heard"),
    ("definition", "a mock dictionary definition of an ordinary word, the "
                   "humour in how precisely true it is"),
    ("misdirection", "two sentences: the first sets an expectation, the second "
                     "snaps it somewhere unexpected but logical"),
    ("observational", "an observation about something everybody has noticed and "
                      "nobody has said, pushed one step further than is "
                      "reasonable"),
    ("three", "a rule of three: two ordinary items and a third that breaks the "
              "pattern, the twist in the last item"),
    ("exchange", "a two-line exchange between two people, no names, no "
                 "framing, the second line the punchline"),
    ("rule", "a solemnly stated rule or law of nature that is obviously false "
             "and completely convincing"),
    ("escalation", "a short list of three or four things, each slightly more "
                   "absurd than the last, ending on the most absurd"),
]

# Where to point it. Ordinary on purpose: a joke about something everyone knows
# needs no explaining at breakfast, and it keeps the persona doing the work
# rather than the topic.
SUBJECTS: list[tuple[str, str]] = [
    ("appliances", "fridges, air fryers, rice cookers, and the small rituals around them"),
    ("commute", "getting from one place to another and the delays involved"),
    ("meetings", "meetings, and the ones that should have been a note"),
    ("weather", "the weather, and checking the forecast anyway"),
    ("post", "letters, parcels, and things that arrive at the wrong time"),
    ("cats", "cats and their complete indifference"),
    ("dogs", "dogs and their complete lack of indifference"),
    ("queues", "queueing, and the etiquette nobody wrote down"),
    ("keys", "keys, wallets, and things that move when unobserved"),
    ("cooking", "cooking, meal prep, and recipes that assume too much"),
    ("sleep", "sleep, alarms, and the negotiation between them"),
    ("neighbours", "neighbours and the walls between them"),
    ("machines", "machines that beep, and what they want"),
    ("instructions", "instructions, and the step everybody skips"),
    ("plants", "houseplants and their survival prospects"),
    ("time", "being early, being late, and the space between"),
    ("names", "names, forgetting them, and recovering gracefully"),
    ("money", "small sums of money and where they go"),
    ("libraries", "books, libraries, and things borrowed indefinitely"),
    ("bureaucracy", "forms, queues for forms, and forms about forms"),
    ("games", "video games: tutorials, save points, side quests, one more turn"),
    ("gym", "the gym, the people in it, and the equipment nobody understands"),
    ("running", "running, and the things runners tell you about running"),
    ("phones", "phones, notifications, and the battery at 3%"),
    ("group-chats", "group chats and the messages nobody answers"),
    ("passwords", "passwords, and the rules for making them"),
    ("streaming", "streaming, choosing what to watch, and never watching it"),
]

# Plain, unvoiced, and only ever seen when the call fails.
FALLBACK: list[str] = [
    "I told my houseplant I was going away for a week. It had already assumed.",
    "My umbrella works perfectly. It has never once been with me in rain.",
    "I am not late. I am operating on a schedule nobody was told about.",
    "I found the pen. It was in the drawer marked pens, which is why it took "
    "so long.",
    "My alarm and I have different views on what constitutes an emergency.",
    "I would tell you a joke about the lift, but it would only work on some "
    "levels.",
    "I joined a gym in January. By February we had agreed to see other "
    "people.",
    "My phone says I have 3% battery. It said that an hour ago. We both know "
    "it is lying.",
]


@register
class Joke(Slot):
    spec = SlotSpec(id=149, name="Joke", tier="common", paper_mm=24,
                    needs_narrator=True)

    def _recent(self, ctx: Context) -> list[str]:
        if ctx.store is None:
            return []
        try:
            return list(ctx.store.fetch(NAMESPACE, "recent", []) or [])
        except Exception:  # noqa: BLE001 - a cold store is not a failure
            return []

    def _remember(self, ctx: Context, key: str) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            ctx.store.put(NAMESPACE, "recent",
                          (self._recent(ctx) + [key])[-AVOID_LAST:],
                          when=ctx.date)
        except Exception:  # noqa: BLE001
            pass

    def _told(self, store: Any) -> dict[str, str]:
        if store is None:
            return {}
        try:
            return dict(store.fetch(NAMESPACE, TOLD, {}) or {})
        except Exception:  # noqa: BLE001 - a cold store is not a failure
            return {}

    def after_narration(self, store: Any, day: Date, head: str,
                        body: str) -> None:
        told = self._told(store)
        told[day.isoformat()] = " ".join(body.split())
        keep = dict(sorted(told.items())[-TOLD_KEEP:])
        try:
            store.put(NAMESPACE, TOLD, keep, when=day)
        except Exception:  # noqa: BLE001 - memory is never worth a crash
            pass

    def _result(self, ctx: Context) -> SlotResult:
        recent = set(self._recent(ctx))
        forms = [f for f in FORMS if f[0] not in recent] or FORMS
        form_key, form = ctx.rng(self.spec.id).choice(forms)

        # A separate stream, so form and subject do not march in lockstep.
        subjects = [s for s in SUBJECTS if s[0] not in recent] or SUBJECTS
        subject_key, subject = ctx.rng(self.spec.id + 20_000).choice(subjects)
        self._remember(ctx, form_key)
        self._remember(ctx, subject_key)

        # Earlier mornings only: a reprint of today must be free to tell
        # today's joke again.
        told = [joke for day, joke in sorted(self._told(ctx.store).items())
                if day < ctx.date.isoformat()]

        return SlotResult(
            head="A Joke",
            body=ctx.rng(self.spec.id + 30_000).choice(FALLBACK),
            brief={
                "form": form,
                "subject": subject,
                "already_told": told,
                "instruction": "Tell a joke that would make an ordinary person "
                               "laugh out loud, in the FORM given, about the "
                               "SUBJECT given. Being funny comes first: the "
                               "persona is the delivery - its word choice and "
                               "attitude - not the punchline, and a joke that "
                               "only works if you know the persona has failed. "
                               "Before writing, think of at least five "
                               "candidates and print only the funniest. A good "
                               "one has a single clear surprise, put in the "
                               "last few words; no word that is neither setup "
                               "nor payoff; nothing that needs explaining; no "
                               "wordplay that only works when spelled out. "
                               "Avoid jokes everyone has already heard, and "
                               "never retell one from already_told, even in a "
                               "new form or on a new subject. Do not "
                               "announce or explain it, and add nothing after "
                               "the punchline. Under thirty words unless the "
                               "form needs more.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
