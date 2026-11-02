"""Slot 84 - Wallet cheat sheet.

Cut out and keep. A small reference card for something you keep almost knowing.

**The topic range is the slot.** `SLOTS.md` names keyboard shortcuts, knots,
unit conversions, the phonetic alphabet, chord shapes and regex, and the word it
uses is "rotate widely" - which is the same instruction the coupon and the joke
needed, for the same reason. A cheat sheet that is always about one kind of
thing is a reference card you stop reading. Topics are drawn with recent ones
suppressed.

**Every card is data, not prose.** These are things to look at, not read, so
they render as a two-column table in the monospace face rather than as
sentences. That also makes them checkable: a wrong knot instruction is a wrong
knot, and a table of facts can be verified line by line in a way a paragraph
cannot.

**Cut marks, because it is meant to leave the receipt.** The card is bordered
with a dashed rule and sits on its own, so the scissors have somewhere to go.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "cheatsheet"
AVOID_LAST = 6

# (key, title, [(left, right), ...]). Left is what you look up, right is the
# answer - so the eye goes down the left column and stops.
CARDS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("phonetic", "NATO phonetic alphabet", [
        ("A B C D", "Alfa Bravo Charlie Delta"),
        ("E F G H", "Echo Foxtrot Golf Hotel"),
        ("I J K L", "India Juliett Kilo Lima"),
        ("M N O P", "Mike November Oscar Papa"),
        ("Q R S T", "Quebec Romeo Sierra Tango"),
        ("U V W X", "Uniform Victor Whiskey X-ray"),
        ("Y Z", "Yankee Zulu"),
    ]),
    ("knots", "Four knots worth knowing", [
        ("Bowline", "a loop that will not slip or jam, however loaded"),
        ("Clove hitch", "fast to a post, adjusts, needs constant tension"),
        ("Figure eight", "a stopper that will not pull through a hole"),
        ("Sheet bend", "joins two ropes of DIFFERENT thickness"),
    ]),
    ("units", "Conversions, close enough", [
        ("1 inch", "25.4 mm exactly"),
        ("1 foot", "30.5 cm"),
        ("1 mile", "1.61 km"),
        ("1 kg", "2.20 lb"),
        ("1 litre", "1.76 UK pints, 2.11 US pints"),
        ("1 hectare", "2.47 acres"),
        ("C to F", "double it, subtract a tenth, add 32"),
    ]),
    ("regex", "Regex, the useful half", [
        (r"\\d \\w \\s", "digit, word character, whitespace"),
        (r"+ * ?", "one or more, zero or more, optional"),
        (r"{2,5}", "between two and five"),
        (r"^ $", "start of line, end of line"),
        (r"\\b", "word boundary - the one people forget"),
        (r"(?:...)", "group WITHOUT capturing it"),
        (r"(?=...)", "lookahead: match only if followed by"),
    ]),
    ("chords", "Guitar, the first five shapes", [
        ("E minor", "022000"),
        ("A minor", "x02210"),
        ("C major", "x32010"),
        ("G major", "320003"),
        ("D major", "xx0232"),
        ("Capo", "each fret up moves every chord one semitone"),
    ]),
    ("keyboard", "Shortcuts most people miss", [
        ("Ctrl Shift T", "reopen the tab you just closed"),
        ("Ctrl L", "jump to the address bar"),
        ("Ctrl Backspace", "delete the whole previous word"),
        ("Win V", "clipboard history, if it is switched on"),
        ("Alt Tab, hold", "pick from the whole stack, not the last one"),
        ("Ctrl Shift Esc", "task manager, directly"),
    ]),
    ("tipping", "Tipping, roughly, by country", [
        ("France", "service compris; round up if it was good"),
        ("Japan", "no tip, and it can cause offence"),
        ("USA", "18-22% in restaurants, and it is wages"),
        ("UK", "10-12%, check it is not already on the bill"),
        ("Italy", "coperto is a cover charge, not a tip"),
    ]),
    ("morse", "Morse, the bits you would use", [
        ("SOS", "... --- ..."),
        ("A B C", ".-  -...  -.-."),
        ("E T", ". and - , the two commonest letters"),
        ("Numbers", "1 is .---- , 5 is ..... , 0 is -----"),
        ("Rule", "a dash is three dots long, gaps likewise"),
    ]),
    ("firstaid", "Things worth knowing before you need them", [
        ("Compressions", "100-120 a minute, centre of the chest, hard"),
        ("Choking", "five back blows, then five abdominal thrusts"),
        ("Burns", "cool running water, twenty minutes, no ice"),
        ("Bleeding", "press hard, keep pressing, raise it"),
        ("Note", "this is a reminder, not training. Get trained."),
    ]),
    ("stars", "Finding your way by the sky", [
        ("Polaris", "follow the Plough's two end stars up, five times"),
        ("Orion's belt", "three in a row; points down-left to Sirius"),
        ("South", "in the southern sky, use the Southern Cross's long axis"),
        ("Rule", "stars rise in the east and set in the west, as the sun does"),
    ]),
    ("paper", "Paper sizes, and why they work", [
        ("A0", "one square metre, sides in ratio 1 to root two"),
        ("Each step", "fold the long side in half; the ratio is preserved"),
        ("A4", "210 x 297 mm"),
        ("A5", "half of A4. A3 is double it"),
        ("This roll", "80 mm wide, 72 mm of it printable"),
    ]),
    ("time", "Time zones without the arithmetic", [
        ("UTC", "the one everything else is quoted against"),
        ("New York", "UTC-5, or -4 in summer"),
        ("Paris", "UTC+1, or +2 in summer"),
        ("Tokyo", "UTC+9, and no daylight saving at all"),
        ("Rule", "summer time shifts almost everywhere except the tropics"),
    ]),
]

_CSS = """
<style>
/* A card to cut out, so it is bordered and set apart from the page. Dashed,
   because a solid border reads as a box and a dashed one reads as an
   instruction. */
.card       { border: 2px dashed #000; padding: 8px 10px; margin: 6px 0; }
.card-title { font-weight: var(--bold); font-size: var(--size-small);
              margin-bottom: 4px; }
/* Fixed pitch: these are things to look at rather than read, and the left
   column has to line up for the eye to run down it. */
.card-row   { display: grid; grid-template-columns: 8.5em 1fr; gap: 8px;
              font-family: var(--font-mono); font-size: var(--size-tiny);
              line-height: 1.45; }
.card-key   { font-weight: 700; }
</style>
"""


@register
class WalletCheatSheet(Slot):
    spec = SlotSpec(id=84, name="Wallet cheat sheet", tier="uncommon",
                    paper_mm=58, needs_narrator=True)

    def _recent(self, ctx: Context) -> list[str]:
        if ctx.store is None:
            return []
        try:
            return list(ctx.store.fetch(NAMESPACE, "recent", []) or [])
        except Exception:  # noqa: BLE001
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

    def _result(self, ctx: Context) -> SlotResult:
        recent = set(self._recent(ctx))
        pool = [c for c in CARDS if c[0] not in recent] or CARDS
        key, title, rows = ctx.rng(self.spec.id).choice(pool)
        self._remember(ctx, key)

        body = "".join(
            f'<div class="card-row"><span class="card-key">{k}</span>'
            f'<span>{v}</span></div>' for k, v in rows)
        return SlotResult(
            head="Cut Out And Keep",
            body=f'{_CSS}<div class="card"><div class="card-title">{title}</div>'
                 f'{body}</div>',
            brief={"verbatim": True,
                   "topic": title,
                   "instruction": "Name this section in voice. The card itself "
                                  "is a reference table and prints exactly as "
                                  "it is - every line on it is a fact and none "
                                  "of them are yours to reword."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
