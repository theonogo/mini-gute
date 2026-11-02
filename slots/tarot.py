"""Slot 132 - Tarot card.

Reference implementation for an IMAGE slot, and for graceful degradation.

Card art is baked to final 1-bit PNGs in `assets/tarot/<slug>.png` by
`tools/baketarot.py`. The slot prefers those: the contour pass is expensive and
there is no reason to redo it at 07:00 every morning. Failing that it falls back
to the raw colour scan in `assets/tarot/source/`, and failing that to a drawn
frame.

Size was settled on paper: 132px turns any deck to mud, 256px is the legible
floor, and 320px is where individual hairs resolve. 320 is therefore the size -
exactly on the detail threshold, as small as the deck goes without losing the
line work that made it worth using. See CARD_W below.

Deck is Rider-Waite-Smith 1909, processed through `render.prepare_contour`.
RWS numbering: Strength VIII, Justice XI (Marseille swaps them).

Five decks were tested before settling here. RWS is *coloured*, and a plain
threshold ruins it - the flat colour fields flood black. But Pamela Colman Smith
drew heavy black outlines beneath that colour, and a contour pass recovers them
as clean line art. Woodcut decks (Conver, Dodal) failed the opposite way: their
flat fills have no outline to recover, so cloaks and robes became black masses no
threshold could rescue.

The drawn fallback frame is already pure black and white, so it takes the plain
threshold path instead. Nothing downstream knows which it got.

That pattern is worth copying: a slot that degrades to something printable beats
a slot that waits for its assets.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render import prepare_contour, prepare_line_art

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

DECK_DIR = Path(__file__).resolve().parent.parent / "assets" / "tarot"
# 320px = 40mm wide, 64mm tall, on a 72mm page.
#
# Measured on paper: 132px blobs the robes into one black mass, 256px is the
# legible floor, 320px resolves individual feathers. So this sits exactly on the
# point where fine detail still holds - any smaller and the deck starts losing
# the line work that made it worth using.
#
# Larger is worse in the other direction: at 352 and 400 the card dominates
# the page.
#
# Changing this requires re-running tools/baketarot.py: the baked PNGs are
# rendered at exactly this width, and a card baked at the wrong one is treated
# as stale.
CARD_W = 320

MAJOR = [
    ("The Fool", "0", "beginnings, the leap taken without looking"),
    ("The Magician", "I", "will, and the tools already to hand"),
    ("The High Priestess", "II", "what is known but not yet said"),
    ("The Empress", "III", "abundance, growth, patience with slow things"),
    ("The Emperor", "IV", "structure, and the cost of it"),
    ("The Hierophant", "V", "tradition, and whether it still serves"),
    ("The Lovers", "VI", "a choice that cannot be split"),
    ("The Chariot", "VII", "momentum held in tension"),
    ("Strength", "VIII", "the quiet kind, not the loud kind"),
    ("The Hermit", "IX", "withdrawal as method, not retreat"),
    ("Wheel of Fortune", "X", "the turn nobody scheduled"),
    ("Justice", "XI", "consequence, arriving on time"),
    ("The Hanged Man", "XII", "the view from the wrong way up"),
    ("Death", "XIII", "an ending that clears ground"),
    ("Temperance", "XIV", "the correct proportion of two things"),
    ("The Devil", "XV", "the chain you are holding yourself"),
    ("The Tower", "XVI", "sudden, structural, survivable"),
    ("The Star", "XVII", "hope after the worst of it"),
    ("The Moon", "XVIII", "what the dark makes of ordinary shapes"),
    ("The Sun", "XIX", "plain, uncomplicated good"),
    ("Judgement", "XX", "the reckoning, and the invitation"),
    ("The World", "XXI", "completion, and the next threshold"),
]


def _slug(name: str) -> str:
    return name.lower().replace("the ", "").replace(" ", "-")


def _font(size: int) -> ImageFont.ImageFont:
    for path in (r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def draw_card(name: str, numeral: str, reversed_: bool) -> Image.Image:
    """Fallback art: a plain card frame. Legible, never pretty."""
    w, h = CARD_W, round(CARD_W * 1.6)
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=0, width=3)
    d.rectangle([6, 6, w - 7, h - 7], outline=0, width=1)

    d.text((w / 2, 20), numeral, font=_font(22), fill=0, anchor="mm")
    d.line([(14, 34), (w - 14, 34)], fill=0, width=1)

    # Name, wrapped by hand - the frame is narrow and PIL will not wrap for us.
    words, line, y = name.upper().split(), "", h - 44
    lines: list[str] = []
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=_font(13)) > w - 20:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    for text in lines:
        d.text((w / 2, y), text, font=_font(13), fill=0, anchor="mm")
        y += 15

    if reversed_:
        img = img.rotate(180)
    return img


@register
class Tarot(Slot):
    spec = SlotSpec(id=132, name="Tarot card", tier="common", paper_mm=87,
                    needs_narrator=True)

    def _draw(self, ctx: Context) -> SlotResult:
        rng = ctx.rng(self.spec.id)
        name, numeral, meaning = rng.choice(MAJOR)
        reversed_ = rng.random() < 0.4

        slug = _slug(name)
        baked = DECK_DIR / f"{slug}.png"
        scan = DECK_DIR / "source" / f"{slug}.jpg"

        if baked.exists():
            # Already final 1-bit art from tools/baketarot.py. Do NOT run it
            # through prepare_contour again - it is not a colour illustration
            # any more, and re-processing would eat the line work.
            card = Image.open(baked).convert("1")
        elif scan.exists():
            # Slow path: raw colour scan. RWS is coloured with heavy black
            # outlines, so contour-extract the line work; a plain threshold
            # floods the flat colour fields. Bake it to skip this.
            card = prepare_contour(Image.open(scan), CARD_W)
        else:
            # The drawn fallback is already pure black and white - threshold it.
            card = prepare_line_art(draw_card(name, numeral, False), CARD_W)

        # Rotate last, on the 1-bit image: a 180 turn is an exact pixel flip,
        # so a reversed card is identical to its upright twin, just inverted.
        # Rotating the source first would re-run the threshold search and give
        # a subtly different card.
        if reversed_:
            card = card.rotate(180)

        label = f"{name}{', reversed' if reversed_ else ''}"
        return SlotResult(
            head="Tarot",
            image=card,
            fine=label,
            brief={
                "card": name, "numeral": numeral, "reversed": reversed_,
                "traditional_meaning": meaning,
                "instruction": "Give your own reading of this card, in voice, "
                               "in one or two sentences. It is a diversion, not "
                               "a prediction - do not claim it will come true.",
            },
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._draw(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._draw(ctx)
