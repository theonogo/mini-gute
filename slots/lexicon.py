"""Slots 31, 32 and 103 - the word slots.

Three slots in one module because two of them must be told apart at a glance and
the third is why:

  * **31 untranslatable word** - a real word from another language with no
    English equivalent. True.
  * **32 etymology of the day** - where a familiar word actually came from.
    True. Sometimes runs as a word-of-the-day instead.
  * **103 a newly invented word** - a word the reader needs that does not
    exist, with an invented etymology. **False, and marked as such.**

`SLOTS.md` says 32 "carries no apocryphal mark, so it must be distinguishable at
a glance from slot 103", and `CLAUDE.md` invariant 8 requires fabricated content
to carry a consistent mark. Keeping them in one file is the cheapest way to make
sure the mark stays consistent: the two cannot drift apart in separate modules
that nobody reads together.

**The mark lives in the stylesheet, not in the text.** Two weaker versions were
tried and rejected. Asking the narrator to mark its own inventions works most of
the time, and most of the time is not a marking scheme. Putting the dagger in
`body` is worse than it looks: slot 103's body is deliberately narrated, so the
narrator *replaces* the string the mark was in and the mark silently disappears
on exactly the days the writing is best. `.slot-103` in the base template adds
the dagger to the header and the body, which no amount of rewriting can remove.
The `fine` line explains it and is never narrated either.

The word lists are seeds, not the content. Python picks *which* word, so a given
date always gets the same one and the etymology is a fact rather than an
improvisation; the narrator writes the framing around it.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

# The mark for fabricated words. A dagger is what a dictionary uses for an
# obsolete or doubtful form, which is the right register - it reads as a
# footnote convention rather than as a disclaimer.
MARK = "&dagger;"
MARK_NOTE = "&dagger; not a real word"


# --- 31: real words with no English equivalent -------------------------------
# (word, language, gloss). The gloss is the fact; the narrator writes around it.
UNTRANSLATABLE: list[tuple[str, str, str]] = [
    ("mamihlapinatapai", "Yaghan",
     "a look shared by two people who each want the other to start something "
     "neither wants to begin"),
    ("komorebi", "Japanese", "sunlight as it filters through the leaves of trees"),
    ("saudade", "Portuguese",
     "longing for something absent that may never have existed"),
    ("gezelligheid", "Dutch",
     "the warmth of being with people you like, in a room you like being in"),
    ("iktsuarpok", "Inuktitut",
     "the restlessness of going to look outside for a visitor who has not arrived"),
    ("sobremesa", "Spanish",
     "the conversation that keeps everyone at the table long after the food is gone"),
    ("meraki", "Greek",
     "doing something with your whole self left in it"),
    ("tsundoku", "Japanese",
     "acquiring books and letting them pile up unread"),
    ("fernweh", "German",
     "an ache for a distant place you have never been"),
    ("utepils", "Norwegian", "a beer drunk outdoors on the first warm day"),
    ("jayus", "Indonesian",
     "a joke told so badly that you laugh anyway"),
    ("pochemuchka", "Russian", "a person who asks too many questions"),
    ("hygge", "Danish",
     "deliberate, unhurried cosiness treated as a thing worth arranging"),
    ("boketto", "Japanese",
     "staring into the middle distance while thinking about nothing"),
    ("cafune", "Brazilian Portuguese",
     "running your fingers through someone's hair, slowly"),
    ("wabi-sabi", "Japanese",
     "finding the beauty in something worn, imperfect and impermanent"),
    ("ya'aburnee", "Arabic",
     "the hope of dying first, because living without the other is unbearable"),
    ("kilig", "Tagalog",
     "the flutter in the stomach at something romantic"),
]

# --- 32: true etymologies ----------------------------------------------------
# (word, origin). Every one is a real, well-attested derivation.
ETYMOLOGY: list[tuple[str, str]] = [
    ("salary", "Latin salarium, a soldier's allowance connected with salt"),
    ("clue", "Middle English clew, a ball of thread - Theseus unwound one to "
             "find his way back out of the labyrinth"),
    ("quarantine", "Venetian quaranta giorni, the forty days a ship waited at "
                   "anchor before anyone was allowed ashore"),
    ("disaster", "Italian disastro, from dis- and astro: an ill star"),
    ("muscle", "Latin musculus, little mouse - from how one looks moving under "
               "the skin"),
    ("sarcasm", "Greek sarkazein, to tear flesh"),
    ("nightmare", "Old English mare, a demon believed to sit on the chest of a "
                  "sleeper. Nothing to do with horses"),
    ("companion", "Latin com- and panis: one you break bread with"),
    ("robot", "Czech robota, forced labour - coined for a 1920 play by Karel "
              "Capek"),
    ("tragedy", "Greek tragoidia, goat-song, for reasons nobody has settled"),
    ("malaria", "Italian mala aria, bad air - which is what it was blamed on"),
    ("candidate", "Latin candidatus, dressed in white, as Roman office-seekers were"),
    ("hazard", "Arabic az-zahr, the die - by way of a game of chance"),
    ("sabotage", "French sabot, a wooden shoe, and saboter, to work clumsily"),
    ("panic", "Pan, the Greek god whose shout emptied hillsides"),
    ("alcohol", "Arabic al-kuhl, the fine powder used as eye cosmetic - the word "
                "moved from the powder to the method to the distillate"),
    ("silly", "Old English saelig, meaning blessed, then innocent, then feeble, "
              "then foolish"),
    ("muscovy", "not included; this list holds only attested derivations"),
]
ETYMOLOGY = [e for e in ETYMOLOGY if not e[1].startswith("not included")]

# --- 103: words that ought to exist ------------------------------------------
# (invented word, what it names). The narrator supplies the fake etymology.
INVENTED: list[tuple[str, str]] = [
    ("shelfshame", "the specific guilt of a bookcase you have not read"),
    ("doorwaying", "arriving in a room having forgotten why"),
    ("tabgrief", "the loss felt on closing a browser window you meant to keep"),
    ("premourning", "being sad in advance about a thing that is still fine"),
    ("cablecert", "certainty that a cable is important, with no idea what for"),
    ("replydread", "the weight of a message that would take one minute to answer"),
    ("almostdone", "the state a project enters at ninety percent and stays in"),
    ("queuefaith", "the belief that the other line is moving faster"),
    ("soundcheck", "saying hello twice at the start of a call"),
    ("plansorrow", "relief at a cancellation, followed immediately by regret"),
    ("hoverback", "returning to a paragraph you have already read three times"),
    ("nightlogic", "the reasoning that is completely convincing at 2am"),
    ("gonebright", "how a room looks after someone has just left it"),
    ("lastbite", "deciding whether the final piece is worth the fullness"),
]


@register
class UntranslatableWord(Slot):
    spec = SlotSpec(id=31, name="Untranslatable word", tier="uncommon",
                    paper_mm=26, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        word, language, gloss = ctx.rng(self.spec.id).choice(UNTRANSLATABLE)
        return SlotResult(
            head="Untranslatable",
            body=f"<b>{word}</b> &mdash; {gloss}.",
            fine=language,
            brief={"word": word, "language": language, "meaning": gloss,
                   "instruction": "Give the word, then what it means, in voice, "
                                  "in one or two sentences. The word and the "
                                  "language are real; do not alter either, and "
                                  "do not invent a second meaning for it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


@register
class Etymology(Slot):
    spec = SlotSpec(id=32, name="Etymology of the day", tier="uncommon",
                    paper_mm=23, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        word, origin = ctx.rng(self.spec.id).choice(ETYMOLOGY)
        return SlotResult(
            head="Etymology",
            body=f"<b>{word}</b> &mdash; from {origin}.",
            brief={"word": word, "origin": origin,
                   "instruction": "Tell where this word came from, in voice, in "
                                  "one or two sentences. This derivation is TRUE "
                                  "and attested - keep it exactly as given, add "
                                  "no further history, and do not hedge it. It "
                                  "must not read as a story you are making up."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


@register
class InventedWord(Slot):
    spec = SlotSpec(id=103, name="A newly invented word", tier="rare",
                    paper_mm=22, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        word, meaning = ctx.rng(self.spec.id).choice(INVENTED)
        return SlotResult(
            # No mark in these strings on purpose - both are rewritten by the
            # narrator. `.slot-103` applies it, so it survives any rewrite.
            head="New Word",
            body=f"<b>{word}</b> &mdash; {meaning}.",
            fine=MARK_NOTE,
            brief={"word": word, "meaning": meaning,
                   "fabricated": True,
                   "instruction": "Coin this word properly: give it a plausible "
                                  "but invented etymology, in voice, in two or "
                                  "three sentences. It is openly made up and the "
                                  "layout marks it as such, so commit to it - no "
                                  "winking, no disclaimer. Do not attribute it to "
                                  "any real language or dictionary."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
