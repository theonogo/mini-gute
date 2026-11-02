"""Slot 17 - Cryptic crossword clue.

The cheapest puzzle on the receipt at 10mm, and the one that fits when the
budget is tight. The answer prints upside-down at the footer **with its parse**,
because a cryptic whose answer you cannot reconstruct is just a fact you were
told.

**The wordplay is machine-checked, not trusted.** Every clue carries its device
and its fodder as data, and `verify()` confirms the mechanism genuinely produces
the answer: that an anagram's letters really do rearrange into it, that a hidden
word really is hidden in the string given, that a reversal really reverses.
Anything that fails is dropped from the pool rather than printed.

That matters more here than anywhere else on the receipt. A wrong anagram looks
completely fine on the page and is unsolvable, and nobody finds out until
someone has spent ten minutes on it and turned the paper over to a parse that
does not work. Same reasoning as the nonogram's solver: a puzzle is a promise,
and the promise should be checked by something other than the person who made
it. `tools/crypticcheck.py` runs the whole bank.

Double definitions carry no fodder and claim no mechanism, so there is nothing
to check and nothing asserted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


@dataclass(frozen=True)
class Clue:
    clue: str
    answer: str
    device: str        # anagram | hidden | reversal | double
    fodder: str        # letters the device operates on; empty for double
    parse: str         # how it works, printed with the answer


CLUES: list[Clue] = [
    # --- anagrams ---
    Clue("Hear silent broadcast (6)", "LISTEN", "anagram", "SILENT",
         "SILENT rearranged. 'Broadcast' is the anagram signal, "
         "'hear' is the definition"),
    Clue("Dirty room converted for students (9)", "DORMITORY", "anagram",
         "DIRTY ROOM",
         "DIRTY ROOM rearranged. 'Converted' signals it; 'for students' defines"),
    Clue("Orchestra reorganised as a working animal (9)", "CARTHORSE",
         "anagram", "ORCHESTRA",
         "ORCHESTRA rearranged. 'Reorganised' signals it"),
    Clue("Trains crashed, causing injury (6)", "STRAIN", "anagram", "TRAINS",
         "TRAINS rearranged. 'Crashed' signals it; 'injury' defines"),
    Clue("Lemon squeezed into another fruit (5)", "MELON", "anagram", "LEMON",
         "LEMON rearranged. 'Squeezed' signals it"),
    Clue("Teacher, oddly, turns out to be a fraud (7)", "CHEATER", "anagram",
         "TEACHER", "TEACHER rearranged. 'Oddly' signals it; 'fraud' defines"),
    Clue("Danger surfaces where the roses are (6)", "GARDEN", "anagram",
         "DANGER", "DANGER rearranged. 'Surfaces' signals it"),
    Clue("Angered, somehow, and absolutely furious (7)", "ENRAGED", "anagram",
         "ANGERED", "ANGERED rearranged. 'Somehow' signals it"),
    Clue("Priest, disturbed, becomes a fairy (6)", "SPRITE", "anagram",
         "PRIEST", "PRIEST rearranged. 'Disturbed' signals it"),
    Clue("Cinema rebuilt for a cold character (6)", "ICEMAN", "anagram",
         "CINEMA", "CINEMA rearranged. 'Rebuilt' signals it"),
    Clue("Silver worked into a thin fragment (6)", "SLIVER", "anagram",
         "SILVER", "SILVER rearranged. 'Worked' signals it"),
    Clue("Parental upheaval - fatherly, in fact (8)", "PATERNAL", "anagram",
         "PARENTAL", "PARENTAL rearranged. 'Upheaval' signals it"),
    Clue("Nameless, surprisingly, and they are the ones selling (8)",
         "SALESMEN", "anagram", "NAMELESS",
         "NAMELESS rearranged. 'Surprisingly' signals it"),
    Clue("A night out becomes an object (5)", "THING", "anagram", "NIGHT",
         "NIGHT rearranged. 'Out' signals it; 'object' defines"),
    Clue("Earth moved - it is the centre of things (5)", "HEART", "anagram",
         "EARTH", "EARTH rearranged. 'Moved' signals it"),
    Clue("Sadder, somehow, and fears the worst (6)", "DREADS", "anagram",
         "SADDER", "SADDER rearranged. 'Somehow' signals it"),

    # --- hidden words ---
    Clue("Something steady found in pasta blends (6)", "STABLE", "hidden",
         "pasta blends", "hidden in paSTA BLEnds"),
    Clue("Fruit concealed by a major angel (6)", "ORANGE", "hidden",
         "major angel", "hidden in majOR ANGEl"),
    Clue("Bird spotted as the spar rotates (6)", "PARROT", "hidden",
         "spar rotates", "hidden in sPAR ROTates"),
    Clue("Raider hiding behind the top irate customer (6)", "PIRATE", "hidden",
         "top irate customer", "hidden in toP IRATE customer"),
    Clue("Myth buried in a possible gender debate (6)", "LEGEND", "hidden",
         "possible gender", "hidden in possibLE GENDer"),
    Clue("Territory in this land, essentially (6)", "ISLAND", "hidden",
         "this land", "hidden in thIS LAND"),
    Clue("Visitor from space arriving at a welcome time (5)", "COMET", "hidden",
         "welcome time", "hidden in welCOME Time"),
    Clue("What is kept quiet in these cretinous remarks (6)", "SECRET",
         "hidden", "these cretinous", "hidden in theSE CRETinous"),

    # --- reversals ---
    Clue("Wicked to play a live set backwards (4)", "EVIL", "reversal", "LIVE",
         "LIVE written backwards. 'Wicked' defines"),
    Clue("Desserts sent back cause anxiety (8)", "STRESSED", "reversal",
         "DESSERTS", "DESSERTS written backwards"),
    Clue("Straw turned over reveals blemishes (5)", "WARTS", "reversal",
         "STRAW", "STRAW written backwards"),
    Clue("Drawer pulled back as a prize (6)", "REWARD", "reversal", "DRAWER",
         "DRAWER written backwards"),
    Clue("Diaper returned, and the debt is settled (6)", "REPAID", "reversal",
         "DIAPER", "DIAPER written backwards"),
    Clue("Stop turning - these are for cooking (4)", "POTS", "reversal", "STOP",
         "STOP written backwards"),
    Clue("Smart, turning back to public transport (5)", "TRAMS", "reversal",
         "SMART", "SMART written backwards"),
    Clue("Gateman turned round for identification (7)", "NAMETAG", "reversal",
         "GATEMAN", "GATEMAN written backwards"),
    Clue("Deliver backwards, and be much hated (7)", "REVILED", "reversal",
         "DELIVER", "DELIVER written backwards"),

    # --- double definitions (nothing mechanical to assert) ---
    Clue("A ship's left, or something fortified (4)", "PORT", "double", "",
         "two definitions: the left side of a vessel, and the wine"),
    Clue("Departed, or what remains (4)", "LEFT", "double", "",
         "two definitions: went away, and remaining"),
    Clue("It flies at night, or strikes in the day (3)", "BAT", "double", "",
         "two definitions: the animal, and the cricket implement"),
    Clue("A season to jump (6)", "SPRING", "double", "",
         "two definitions: the season, and to leap"),
    Clue("Teach the thing that runs on rails (5)", "TRAIN", "double", "",
         "two definitions: to instruct, and the locomotive"),
    Clue("Just, or a place with rides (4)", "FAIR", "double", "",
         "two definitions: equitable, and the funfair"),
    Clue("Not heavy, and not dark (5)", "LIGHT", "double", "",
         "two definitions: weightless, and illumination"),
    Clue("Where money sits, or the edge of a river (4)", "BANK", "double", "",
         "two definitions: the institution, and the riverside"),
    Clue("It strikes, or it pairs (5)", "MATCH", "double", "",
         "two definitions: the thing you light, and a pairing"),
    Clue("Advice, or what is left behind (3)", "TIP", "double", "",
         "two definitions: a hint, and the gratuity"),
]


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z]", "", text.upper())


def verify(clue: Clue) -> bool:
    """Does this clue's stated mechanism actually produce its answer?"""
    answer = _letters(clue.answer)
    fodder = _letters(clue.fodder)

    if clue.device == "anagram":
        # Must be a genuine rearrangement: same letters, different order.
        return sorted(fodder) == sorted(answer) and fodder != answer
    if clue.device == "hidden":
        return answer in fodder and answer != fodder
    if clue.device == "reversal":
        return fodder[::-1] == answer
    if clue.device == "double":
        return not clue.fodder          # claims no mechanism, asserts nothing
    return False


def verified() -> list[Clue]:
    """The clues whose wordplay checks out. The only pool the slot draws from."""
    return [c for c in CLUES if verify(c)]


@register
class CrypticClue(Slot):
    spec = SlotSpec(id=17, name="Cryptic crossword clue", tier="uncommon",
                    paper_mm=28, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        clue = ctx.rng(self.spec.id).choice(verified())
        return SlotResult(
            head="Cryptic",
            body=clue.clue,
            answer=f"<b>{clue.answer}</b> &mdash; {clue.parse}.",
            brief={"verbatim": True,
                   "instruction": "Name this section in voice. The clue prints "
                                  "exactly as written - changing one word of a "
                                  "cryptic breaks it - and the answer is "
                                  "upside-down at the foot of the receipt, so "
                                  "do not give it away."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
