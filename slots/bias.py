"""Slot 33 - Logical fallacy or cognitive bias.

One bias, plus **how it will specifically catch the reader today**. That second
half is the whole slot. A bias named and defined is a flashcard; a bias plus the shape
of the trap is something you can actually notice happening.

So each entry carries a `trap` - a concrete, ordinary situation the bias shows
up in - and the narrator is told to point it at today rather than to define the
term. The definition is a fact and stays put; the warning is the voice.

Fallacies and biases are kept in one pool despite being different animals. On
paper the distinction does not help: both arrive as "here is a way your
reasoning goes wrong", and splitting them would only mean two thinner lists.
"""

from __future__ import annotations

import config

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# (name, what it is, where it will get you)
ENTRIES: list[tuple[str, str, str]] = [
    ("Survivorship bias",
     "judging from the things that made it through, because the failures are "
     "not there to be counted",
     "every piece of advice from someone successful, and every old building you "
     "admire for how well they built things back then"),
    ("The planning fallacy",
     "expecting a task to take the time it would take if nothing went wrong",
     "the thing you have told yourself is an afternoon of work"),
    ("Sunk cost",
     "continuing because of what you have already spent rather than what is "
     "left to gain",
     "the project, the book, or the conversation you are only still in because "
     "you are already in it"),
    ("Confirmation bias",
     "searching for and remembering what fits what you already think",
     "the first three search results you will read today and count as research"),
    ("The Dunning-Kruger effect",
     "being least able to see the gaps in a skill when you have least of it",
     "whatever you learned the basics of most recently"),
    ("Goodhart's law",
     "a measure stops being a good measure once it becomes a target",
     "any number you are currently trying to move"),
    ("The availability heuristic",
     "judging how likely something is by how easily an example comes to mind",
     "your estimate of any risk you have recently read a story about"),
    ("Anchoring",
     "the first number you hear setting the range for every number after it",
     "the first price you see, and the first estimate anyone says out loud in a "
     "meeting"),
    ("The fundamental attribution error",
     "explaining other people by their character and yourself by your "
     "circumstances",
     "the next person who does something inexplicable in traffic or in a thread"),
    ("Loss aversion",
     "feeling a loss about twice as strongly as an equivalent gain",
     "any decision framed as giving something up rather than getting something"),
    ("The curse of knowledge",
     "being unable to imagine not knowing what you know",
     "everything you write today for someone who has less context than you"),
    ("Parkinson's law of triviality",
     "spending time in proportion to how easy a decision is to have an opinion "
     "about",
     "the naming discussion that will outlast the architecture discussion"),
    ("Base rate neglect",
     "reasoning from the vivid specifics and ignoring how common the thing is "
     "to begin with",
     "any conclusion you draw today from a single striking example"),
    ("The IKEA effect",
     "valuing a thing more because you built it",
     "your own code, and your reluctance to delete it"),
    ("Motte and bailey",
     "defending an easy version of a claim, then going back to the strong one",
     "any argument that becomes reasonable the moment you push on it and "
     "unreasonable again afterwards"),
    ("Selection bias",
     "drawing conclusions from a sample that was never representative",
     "everything you learn today about what people think, from people who chose "
     "to post"),
    ("The false dilemma",
     "presenting two options as though they were the only ones",
     "the next either/or someone offers you, including the ones you offer "
     "yourself"),
    ("Hyperbolic discounting",
     "valuing a small reward now far above a large one later, steeply and "
     "irrationally",
     "the fifteen minutes you will spend at eleven o'clock instead of the thing "
     "due Thursday"),
    ("The recency illusion",
     "assuming something is new because you only just noticed it",
     "any usage, trend or word you are about to complain has appeared from "
     "nowhere"),
    ("Optimism bias about others' certainty",
     "reading confident delivery as evidence of being right",
     "whoever speaks first and most clearly in any room you are in today"),
]


@register
class Bias(Slot):
    spec = SlotSpec(id=33, name="Logical fallacy or cognitive bias",
                    tier="uncommon", paper_mm=29, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        name, what, trap = ctx.rng(self.spec.id).choice(ENTRIES)
        return SlotResult(
            head="Today's Blind Spot",
            body=f"<b>{name}</b> &mdash; {what}. Watch for it in {trap}.",
            brief={"name": name, "definition": what, "where_it_gets_you": trap,
                   "instruction": "Name the bias, say what it is in a few words, "
                                  "then spend the rest on where it will catch "
                                  f"{config.reader_name()} today - that second "
                                  "half is the point, "
                                  "not the definition. Two or three sentences, "
                                  "in voice. The definition is accurate as "
                                  "given; do not broaden it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
