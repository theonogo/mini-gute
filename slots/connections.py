"""Slot 15 - Connections-style word grid.

Sixteen words, group them into four. Circled with a pen, solved over a coffee,
answers upside-down at the footer under the puzzle house rule.

**Python builds the puzzle, not the narrator.** The narrator returns one header
string and one body string, with nowhere to put four labelled groups of four -
and building it here is the better architecture anyway, for the reason the
whole project is organised around: the puzzle is a *fact*. It has to have exactly one valid grouping, and a
model asked to invent sixteen words on the spot will now and then produce a grid
where a word fits two categories, which is unsolvable on paper with no way to
check. A curated bank cannot do that.

**The difficulty comes from collisions between groups, and so does the risk.**
Four groups drawn at random from the bank will sometimes both want the same
word, which is the entire pleasure of the puzzle when it is deliberate and a
broken grid when it is accidental. Every group therefore carries its `decoys` -
the words elsewhere in the bank it could plausibly claim - and the draw rejects
any set where two chosen groups compete for a word. What survives is a puzzle
whose traps are real and whose answer is unique.

Group order in the grid is shuffled, and so is the order within each group, so
the layout leaks nothing.
"""

from __future__ import annotations

import random

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

COLS = 4

# (category, four words, words elsewhere in the bank this category could also
# fairly claim). The third field is what keeps the puzzle honest: it is not
# decoration, it is the rejection test.
GROUPS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("Types of knot", ("BOWLINE", "HITCH", "REEF", "SHEET"),
     ("BEND", "LOOP", "TIE", "BOW")),
    ("Parts of a ship", ("BOW", "STERN", "KEEL", "MAST"),
     ("SHEET", "DECK", "HOLD", "BRIDGE")),
    ("___ card", ("WILD", "REPORT", "CREDIT", "FLASH"),
     ("PLACE", "TRUMP", "GREEN", "POST")),
    ("Card games", ("BRIDGE", "HEARTS", "RUMMY", "PATIENCE"),
     ("SNAP", "WHIST", "POKER", "SPADES")),
    ("Chess pieces", ("ROOK", "BISHOP", "KNIGHT", "PAWN"),
     ("CASTLE", "KING", "QUEEN", "CHECK")),
    ("Birds", ("ROOK", "CRANE", "SWIFT", "KITE"),
     ("SWALLOW", "MARTIN", "RAIL", "COOT")),
    ("Lifting machines", ("CRANE", "JACK", "HOIST", "WINCH"),
     ("DERRICK", "PULLEY", "LIFT", "RIG")),
    ("Playing card ranks", ("JACK", "ACE", "QUEEN", "DEUCE"),
     ("KING", "KNAVE", "TEN", "JOKER")),
    ("Things that can be blown", ("FUSE", "WHISTLE", "BUBBLE", "GASKET"),
     ("HORN", "COVER", "KISS", "CANDLE")),
    ("Cricket terms", ("SILLY", "GULLY", "COVER", "DUCK"),
     ("SLIP", "OVER", "MAIDEN", "STUMP")),
    ("Ways to avoid", ("DUCK", "DODGE", "SKIRT", "SIDESTEP"),
     ("EVADE", "SHIRK", "MISS", "PARRY")),
    ("Car makes", ("DODGE", "FORD", "JAGUAR", "LOTUS"),
     ("SKODA", "SEAT", "RAM", "COOPER")),
    ("River crossings", ("FORD", "BRIDGE", "FERRY", "STEPPING"),
     ("CAUSEWAY", "TUNNEL", "WEIR", "LOCK")),
    ("Big cats", ("JAGUAR", "PUMA", "LYNX", "OCELOT"),
     ("PANTHER", "COUGAR", "TIGER", "LION")),
    ("Trainer brands", ("PUMA", "NIKE", "ASICS", "REEBOK"),
     ("ADIDAS", "CONVERSE", "VANS", "SAUCONY")),
    ("Greek gods", ("NIKE", "HERMES", "ATLAS", "IRIS"),
     ("APOLLO", "ARES", "HERA", "PAN")),
    ("Parts of the eye", ("IRIS", "LENS", "RETINA", "CORNEA"),
     ("PUPIL", "SCLERA", "HUMOUR", "ROD")),
    ("Flowers", ("IRIS", "LILY", "DAISY", "PANSY"),
     ("ASTER", "PEONY", "TULIP", "POPPY")),
    ("Fear words", ("PANSY", "COWARD", "CHICKEN", "WIMP"),
     ("YELLOW", "MOUSE", "CRAVEN", "FUNK")),
    ("Playwrights", ("COWARD", "SHAW", "WILDE", "PINTER"),
     ("MILLER", "IBSEN", "SYNGE", "STOPPARD")),
    ("Beers", ("MILLER", "STELLA", "PERONI", "GUINNESS"),
     ("CARLING", "AMSTEL", "BECKS", "TIGER")),
    ("Occupational surnames", ("MILLER", "SMITH", "COOPER", "FLETCHER"),
     ("BAKER", "TURNER", "MASON", "WRIGHT")),
    ("Mini models", ("COOPER", "CLUBMAN", "COUNTRYMAN", "PACEMAN"),
     ("ONE", "CONVERTIBLE", "HATCH", "ROADSTER")),
    ("Kitchen units", ("PINCH", "DASH", "CUP", "SPOON"),
     ("KNOB", "GLUG", "HANDFUL", "DROP")),
    ("Morse elements", ("DASH", "DOT", "PAUSE", "SIGNAL"),
     ("BEEP", "KEY", "TONE", "GAP")),
    ("Punctuation", ("DASH", "COLON", "COMMA", "PERIOD"),
     ("DOT", "STOP", "BRACKET", "SLASH")),
    ("Body cavities", ("COLON", "SINUS", "PLEURA", "ORBIT"),
     ("CHAMBER", "TRACT", "DUCT", "CANAL")),
    ("Things that orbit", ("MOON", "COMET", "SATELLITE", "PROBE"),
     ("ORBIT", "RING", "STATION", "DEBRIS")),
    ("Sailing manoeuvres", ("TACK", "GYBE", "LUFF", "REACH"),
     ("TRIM", "HEEL", "YAW", "RUN")),
    ("Small nails", ("TACK", "BRAD", "PIN", "SPRIG"),
     ("STUD", "RIVET", "STAPLE", "NAIL")),
    ("Bowling terms", ("STRIKE", "SPARE", "SPLIT", "TURKEY"),
     ("FRAME", "GUTTER", "PIN", "LANE")),
    ("Spare ___", ("ROOM", "TYRE", "CHANGE", "RIB"),
     ("PART", "TIME", "KEY", "WHEEL")),
    ("Kinds of pressure", ("PEER", "BLOOD", "AIR", "WATER"),
     ("TIME", "GROUP", "TYRE", "STEAM")),
    ("Look intently", ("PEER", "GAZE", "STARE", "SQUINT"),
     ("PEEK", "GLARE", "OGLE", "WATCH")),
    ("Members of the Lords", ("PEER", "BARON", "EARL", "DUKE"),
     ("LORD", "COUNT", "VISCOUNT", "MARQUESS")),
    ("Coffee orders", ("FLAT", "LONG", "SHORT", "BLACK"),
     ("WHITE", "DOUBLE", "ICED", "FILTER")),
    ("Musical intervals", ("THIRD", "FIFTH", "OCTAVE", "TRITONE"),
     ("SECOND", "FOURTH", "SIXTH", "UNISON")),
    ("Whisky measures", ("FIFTH", "DRAM", "NIP", "FINGER"),
     ("SHOT", "MEASURE", "TOT", "SNIFTER")),
    ("Sharp tastes", ("TART", "KEEN", "ACID", "BITING"),
     ("SOUR", "ZESTY", "PUNGENT", "SHARP")),
    ("Baked goods", ("TART", "SCONE", "ECLAIR", "STRUDEL"),
     ("FLAN", "PASTY", "BUN", "ROLL")),
    ("Enthusiastic", ("KEEN", "EAGER", "AVID", "RARING"),
     ("GAME", "READY", "HOT", "MAD")),
    ("Types of tide", ("SPRING", "NEAP", "EBB", "FLOOD"),
     ("HIGH", "LOW", "SLACK", "RIP")),
    ("Sources of water", ("SPRING", "WELL", "BORE", "STREAM"),
     ("BROOK", "FOUNT", "GEYSER", "TAP")),
    ("Tedious people", ("BORE", "DRIP", "WINDBAG", "PRIG"),
     ("PILL", "DRAG", "SNOOZE", "PLODDER")),
]

_CSS = """
<style>
/* A grid, not a table: the cells must be equal width regardless of word length,
   and the words must be centred in them. Words are capped at ten characters in
   the bank, so nothing here has to shrink to fit. */
.conn { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px;
        margin: 4px 0; }
/* One step above `small`: at 16px the words read as fine print rather than as
   a puzzle you are meant to work on. Ten characters still fits a quarter of
   72mm at this size. */
.conn-cell { border: 2px solid #000; padding: 10px 2px; text-align: center;
             font-size: calc(var(--size-small) + 1px);
             font-weight: var(--bold);
             line-height: 1.1;
             display: flex; align-items: center; justify-content: center;
             min-height: 44px; }
.conn-answer { margin-top: 2px; }
</style>
"""


def compatible(chosen: list[int], candidate: int) -> bool:
    """True if `candidate` can join `chosen` without making the grid ambiguous.

    Two failure modes, and both produce a puzzle that cannot be solved on paper:
    a word literally appearing in two groups, and a word in one group that
    another group could fairly claim. The second is the one that is invisible
    when you write the bank by hand, which is why `decoys` is carried per group.
    """
    _, words, decoys = GROUPS[candidate]
    new_words, new_decoys = set(words), set(decoys)
    for index in chosen:
        _, other_words, other_decoys = GROUPS[index]
        other_words, other_decoys = set(other_words), set(other_decoys)
        if new_words & other_words:
            return False
        if new_words & other_decoys or other_words & new_decoys:
            return False
    return True


def build(rng: random.Random) -> list[tuple[str, list[str]]]:
    """Four mutually unambiguous groups, in a random order."""
    for _ in range(400):
        order = list(range(len(GROUPS)))
        rng.shuffle(order)
        chosen: list[int] = []
        for candidate in order:
            if compatible(chosen, candidate):
                chosen.append(candidate)
            if len(chosen) == 4:
                break
        if len(chosen) == 4:
            out = []
            for index in chosen:
                name, words, _ = GROUPS[index]
                shuffled = list(words)
                rng.shuffle(shuffled)
                out.append((name, shuffled))
            return out
    raise ValueError("could not assemble four unambiguous groups")


def grid_html(groups: list[tuple[str, list[str]]], rng: random.Random) -> str:
    words = [w for _, group in groups for w in group]
    rng.shuffle(words)
    cells = "".join(f'<div class="conn-cell">{w}</div>' for w in words)
    return f'{_CSS}<div class="conn">{cells}</div>'


def answer_html(groups: list[tuple[str, list[str]]]) -> str:
    rows = "".join(
        f'<div class="conn-answer"><b>{name}:</b> {", ".join(sorted(group))}</div>'
        for name, group in groups)
    return rows


@register
class Connections(Slot):
    spec = SlotSpec(id=15, name="Connections-style word grid", tier="common",
                    paper_mm=66, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        groups = build(rng)
        return SlotResult(
            head="Four Groups of Four",
            body=grid_html(groups, rng),
            fine="Sixteen words, four groups of four. Circle them.",
            answer=answer_html(groups),
            brief={"verbatim": True,
                   "instruction": "Name this section in voice. The grid is a "
                                  "puzzle and prints as it is - do not hint at "
                                  "the categories or name any of the words."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
