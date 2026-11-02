"""Slots 101, 102, 104, 113 and 137 - the ones that remember.

  * **101 persona continuity** - today's persona on the others (SYSTEM.md 3.2)
  * **102 a running bit** - a joke invented once, called back forever
  * **104 tomorrow's receipt, predicted** - a guess, graded the next morning
  * **113 receipt archaeology** - real patterns in the receipts (SYSTEM.md 8.1)
  * **137 changelog** - a section's first appearance, among nonsense (8.2)

All five read the archive, and all five are in `selection.HISTORY_DEPENDENT`:
none can be drawn until fourteen receipts are on file, because on a cold start
the machine should not pretend to a past it does not have.

**The past is Python's; the voice is the persona's.** Every one of these is built
on something computed from the receipts table - who printed, what was drawn,
what debuted - and hands that to the narrator as fact. The drama around it is
invented and welcome. The record underneath is not, because the reader can go
and check it against the receipts in the drawer.

**Only a real morning writes memory.** The running bit keeps the joke it
invented and tomorrow-predicted keeps its guess, but a `--date` simulation or a
dry run writes neither - otherwise a preview could leave the machine
remembering a joke nobody ever read.
"""

from __future__ import annotations

from datetime import date as Date, timedelta
from typing import Any

from data import archive

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


def _store_get(store: Any, ns: str, key: str, default=None):
    if store is None:
        return default
    try:
        return store.fetch(ns, key, default)
    except Exception:  # noqa: BLE001
        return default


def _store_put(store: Any, ns: str, key: str, value) -> None:
    if store is None:
        return
    try:
        store.put(ns, key, value)
    except Exception:  # noqa: BLE001 - memory is never worth a crash
        pass


# ============================================================================
@register
class PersonaContinuity(Slot):
    spec = SlotSpec(id=101, name="Persona continuity", tier="uncommon",
                    paper_mm=22, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        me = ctx.shared.get("persona_name")
        others = archive.recent_personas(ctx.store, exclude=me)
        if not others:
            return None                   # nobody else on file to have a view on
        lines = [f"{o['persona']}: {o['count']} of the last receipts, "
                 f"last seen {o['last']}" for o in others]
        return SlotResult(
            head="On The Others",
            body="The other correspondents have been noted.",
            brief={
                "today_is": me,
                "the_others_recently": lines,
                "instruction": "Comment, in voice, on one or more of the other "
                               "personas who have written recent receipts. "
                               "Grudges, rivalries, grudging respect, running "
                               "complaints - drama is encouraged, and a feud "
                               "nobody designed is the goal. The appearance "
                               "counts and dates are TRUE; use them as given "
                               "and invent no others. Two or three sentences.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)


# ============================================================================
@register
class RunningBit(Slot):
    """A joke invented once and called back at unpredictable intervals forever.

    The first time it is drawn there is no bit, so the narrator invents one and
    `after_narration` keeps it word for word. Every later draw hands that exact
    text back and asks for a callback. The unpredictability comes free: the slot
    is rare, so the gap between callbacks is whatever the rarity engine makes it.
    """

    spec = SlotSpec(id=102, name="A running bit", tier="rare", paper_mm=22,
                    needs_narrator=True)
    NS = "runningbit"

    def _state(self, store: Any) -> dict | None:
        state = _store_get(store, self.NS, "bit")
        return state if isinstance(state, dict) and state.get("origin") else None

    def _result(self, ctx: Context) -> SlotResult:
        state = self._state(ctx.store)
        if not state:
            return SlotResult(
                head="A Running Bit",
                body="A bit has been started. It will be back.",
                brief={"stage": "invention",
                       "instruction": "Invent a running joke - one short, "
                                      "specific, faintly absurd premise this "
                                      "persona could plausibly bring up again "
                                      "in weeks or months. State it as though "
                                      "it is already a thing, in one or two "
                                      "sentences. Do not announce that it is a "
                                      "running joke."},
            )
        invented = Date.fromisoformat(state["invented"])
        return SlotResult(
            head="As Previously Noted",
            body=state["origin"],
            brief={"stage": "callback",
                   "the_original_bit": state["origin"],
                   "first_printed": state["invented"],
                   "days_since": (ctx.date - invented).days,
                   "times_called_back": state.get("callbacks", 0),
                   "instruction": "Call back to the running bit given, in voice, "
                                  "in one or two sentences - develop it, "
                                  "escalate it, or treat it as long-established "
                                  "fact. It must be recognisably the SAME bit. "
                                  "The dates and counts given are true."},
        )

    def after_narration(self, store: Any, day: Date, head: str,
                        body: str) -> None:
        state = self._state(store)
        if not state:
            _store_put(store, self.NS, "bit",
                       {"origin": body, "invented": day.isoformat(),
                        "callbacks": 0})
        else:
            state["callbacks"] = state.get("callbacks", 0) + 1
            state["last"] = day.isoformat()
            _store_put(store, self.NS, "bit", state)

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


# ============================================================================
@register
class TomorrowPredicted(Slot):
    """A guess at tomorrow's receipt, graded the morning after.

    **The guess and the grade are Python's.** Three objective claims - which
    persona, how many sections, whether a rare lands - so there is no argument
    about the score. The narrator writes the prediction and the self-assessment
    in voice around numbers it cannot fudge, which is where the in-jokes come
    from: a persona forced to report that it got two of three wrong.

    Day one records the guess and pins the slot for tomorrow. Day two grades it
    against what the selection engine actually drew, then clears it.
    """

    spec = SlotSpec(id=104, name="Tomorrow's receipt, predicted", tier="rare",
                    paper_mm=34, needs_narrator=True)
    NS = "prediction"

    def _actual(self, ctx: Context) -> dict:
        from .registry import get
        drawn = [sid for sid in ctx.shared.get("drawn_ids", [])
                 if sid != self.spec.id]
        tiers = []
        for sid in drawn:
            try:
                tiers.append(get(sid).spec.tier)
            except KeyError:
                pass
        return {"persona": ctx.shared.get("persona_name"),
                "count": len(drawn), "rare": "rare" in tiers}

    def _grade(self, ctx: Context, guess: dict) -> SlotResult:
        actual = self._actual(ctx)
        checks = [
            ("persona", guess["persona"], actual["persona"],
             guess["persona"] == actual["persona"]),
            ("sections", guess["count"], actual["count"],
             guess["count"] == actual["count"]),
            ("a rare", "yes" if guess["rare"] else "no",
             "yes" if actual["rare"] else "no", guess["rare"] == actual["rare"]),
        ]
        score = sum(ok for *_, ok in checks)
        rows = "".join(
            f'<div class="grade-row"><span>{label}</span>'
            f'<span>guessed {g}</span><span>got {a}</span>'
            # Words, not tick and cross glyphs: several persona faces have no
            # U+2713, and a missing glyph prints as a tofu box - on the one
            # section whose entire point is a clear right-or-wrong.
            f'<span class="grade-mark">{"HIT" if ok else "MISS"}</span></div>'
            for label, g, a, ok in checks)
        if ctx.shared.get("real_morning"):
            _store_put(ctx.store, self.NS, "pending", None)
        return SlotResult(
            head="Yesterday's Prediction, Graded",
            body=_GRADE_CSS + f'<div class="grade">{rows}</div>',
            fine=f"Score: {score} of 3.",
            brief={"verbatim": True, "score": score, "out_of": 3,
                   "instruction": "Name this section in voice - it is yesterday's "
                                  "prediction marked against what actually "
                                  f"happened, and it scored {score} of 3. The "
                                  "marks are facts and print as they are."},
        )

    def _predict(self, ctx: Context) -> SlotResult:
        import main
        rng = ctx.rng(self.spec.id)
        personas = list(main.load_personas())
        guess = {"for": (ctx.date + timedelta(days=1)).isoformat(),
                 "persona": rng.choice(personas),
                 "count": rng.randint(2, 4),
                 "rare": rng.random() < 0.3}
        if ctx.shared.get("real_morning") and ctx.store is not None:
            from selection import pin
            _store_put(ctx.store, self.NS, "pending", guess)
            pin(ctx.store, self.spec.id, ctx.date + timedelta(days=1))
        return SlotResult(
            head="Tomorrow, Predicted",
            body=(f"Tomorrow: {guess['persona']}, {guess['count']} sections, "
                  f"{'a rare' if guess['rare'] else 'no rare'}."),
            fine="Graded here tomorrow.",
            brief={"guess_persona": guess["persona"],
                   "guess_sections": guess["count"],
                   "guess_rare": guess["rare"],
                   "instruction": "Predict tomorrow's receipt, in voice, using "
                                  "EXACTLY these three guesses - the persona, "
                                  "the number of sections, and whether a rare "
                                  "section appears. They will be graded against "
                                  "reality tomorrow, so state them plainly and "
                                  "do not hedge or change them. Two or three "
                                  "sentences, in-jokes welcome."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        pending = _store_get(ctx.store, self.NS, "pending")
        if isinstance(pending, dict) and pending.get("for") == ctx.date.isoformat():
            return self._grade(ctx, pending)
        return self._predict(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._predict(ctx)


_GRADE_CSS = """
<style>
.grade-row  { display: grid; grid-template-columns: 5.5em 1fr 1fr 3.2em;
              gap: 6px; align-items: baseline; margin: 2px 0;
              font-size: var(--size-small); }
.grade-mark { font-weight: var(--bold); text-align: right;
              letter-spacing: 0.06em; }
</style>
"""


# ============================================================================
@register
class ReceiptArchaeology(Slot):
    spec = SlotSpec(id=113, name="Receipt archaeology", tier="rare",
                    paper_mm=26, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult | None:
        found = archive.patterns(ctx.store, ctx.date)
        if not found:
            return None
        picked = ctx.rng(self.spec.id).sample(found, min(2, len(found)))
        return SlotResult(
            head="From The Archive",
            body=picked[0][0].upper() + picked[0][1:] + ".",
            fine=f"Computed from {len(archive.receipts(ctx.store, 30))} "
                 f"receipts on file.",
            brief={"true_patterns": picked,
                   "instruction": "Report one or both of these patterns in the "
                                  "receipts, in voice, in two or three "
                                  "sentences, as an archivist who has found "
                                  "something. They are TRUE and were computed "
                                  "from the archive - state them exactly and "
                                  "add no pattern that is not listed. You may "
                                  "wonder what they mean; do not claim to know."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)


# ============================================================================
# Nonsense entries. Each carries the fabrication mark on paper - CLAUDE.md
# invariant 8 - because they sit beside real entries in the same list, and a
# reader has to be able to tell "added ISS pass times" (true) from "added a
# small tax on sunlight" (not) without being told.
NONSENSE: list[str] = [
    "removed herobrine",
    "nerfed mosquitos",
    "gained sentience",
    "fixed a bug where Tuesdays were slightly too long",
    "deprecated the concept of elevenses",
    "rebalanced the weather to favour umbrellas",
    "added a small tax on sunlight",
    "patched out the feeling of having left the oven on",
    "reduced the spawn rate of Mondays",
    "moved the air fryer two centimetres to the left",
    "restored the missing sock from 2019",
    "increased the drop rate of good ideas in the shower",
]
MARK = "&dagger;"


@register
class Changelog(Slot):
    spec = SlotSpec(id=137, name="Changelog", tier="rare", paper_mm=26,
                    needs_narrator=True)

    def _debuts(self, ctx: Context) -> list[str]:
        """Sections printing for the first time today, or else this week."""
        printed = archive.ever_printed(ctx.store)
        today = [sid for sid in ctx.shared.get("drawn_ids", [])
                 if sid != self.spec.id and sid not in printed
                 and archive.is_rotating(sid)]
        if today:
            return [archive.name(sid) for sid in today]
        week_ago = ctx.date - timedelta(days=7)
        return [archive.name(sid) for sid, day in archive.first_seen(ctx.store).items()
                if day >= week_ago and archive.is_rotating(sid)]

    def _result(self, ctx: Context) -> SlotResult | None:
        debuts = self._debuts(ctx)
        if not debuts:
            # A changelog of pure nonsense would abandon the premise, which is
            # that a real change is hidden among the jokes.
            return None
        rng = ctx.rng(self.spec.id)
        jokes = rng.sample(NONSENSE, 3)
        entries = [f"+ added {d.lower()}" for d in debuts[:3]]
        entries += [f"~ {j} {MARK}" for j in jokes]
        rng.shuffle(entries)
        version = f"v{ctx.date:%Y.%m.%d}"
        return SlotResult(
            head="Changelog",
            body=_LOG_CSS + f'<div class="log-ver">{version}</div>'
                 + "".join(f'<div class="log-row">{e}</div>' for e in entries),
            fine=f"{MARK} not a real change",
            brief={"verbatim": True, "version": version,
                   "instruction": "Name this section in voice - it is a release "
                                  "changelog for the receipt. The entries print "
                                  "exactly as they are."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult | None:
        return self._result(ctx)


_LOG_CSS = """
<style>
/* A software changelog, so a fixed pitch and a version line - it is meant to
   look exactly like the thing it is parodying. */
.log-ver { font-family: var(--font-mono); font-weight: 700;
           font-size: var(--size-small); margin-bottom: 3px; }
.log-row { font-family: var(--font-mono); font-size: var(--size-small);
           line-height: 1.45; padding-left: 1.4em; text-indent: -1.4em; }
</style>
"""
