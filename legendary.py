"""Legendary days - SYSTEM.md 4.1.

The selection engine rolls a legendary check every morning (1 in 25, `[rarity]
legendary_odds`) and prints the result - `LEGENDARY ROLL ... - YES`. This module
is what a hit does.

**A legendary day is a FORMAT, not a slot.** The catalogue is explicit: the
formats are printer and renderer behaviours a text model cannot improvise - print
twice, print upside-down, corrupt the page - with fresh content written into
them on the day. So each format may do one or more of four things:

  * `page()`       replace the whole receipt with something else
  * `css`          restyle the ordinary receipt
  * `transform()`  change the finished bitmap after it is rendered
  * `variants()`   print more than one copy

**Formats draw without repeats until the pool is exhausted**, per the spec, so
every legendary is one not seen before. The used list lives in the store. Only
built formats are drawable; SYSTEM.md 4.1 lists the rest.

**Every format is a transformation of something that already works.** A format
that failed would turn the rarest morning of the month into a broken one, so
each falls back: a missing narrator gives curated copy, and a format that raises
leaves the ordinary receipt to print.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date as Date
from typing import Any

from PIL import Image, ImageDraw, ImageOps

import config

NAMESPACE = "legendary"
USED_KEY = "used"


@dataclass
class Context:
    day: Date
    persona: dict
    store: Any
    rotating: list[dict]          # the slots drawn today
    number: int                   # receipt serial
    real_morning: bool
    # False under --no-narrator or --offline. A legendary format asks for its
    # own freeform copy, and that call must obey the same switch as the main one.
    may_narrate: bool = True


class Format:
    """One legendary format. Subclasses override the hooks they use."""

    key = ""
    name = ""
    spec_number = 0               # its position in SYSTEM.md 4.1

    def page(self, ctx: Context) -> str | None:
        """Full-page HTML replacing the receipt, or None to keep it."""
        return None

    css = ""                      # appended to an ordinary receipt

    def transform(self, img: Image.Image, ctx: Context) -> Image.Image:
        """Post-process the rendered 1-bit page."""
        return img

    def variants(self, html: str, ctx: Context) -> list[str]:
        """The pages actually printed. One copy unless a format says more."""
        return [html]

    @property
    def replaces_page(self) -> bool:
        # A format that abandons the receipt does not need the ordinary
        # narrator call, which would write a whole day of copy for nobody.
        return type(self).page is not Format.page


# --- shared page shell ------------------------------------------------------
def shell(body: str, extra_css: str = "", mono: bool = False,
          family: str | None = None) -> str:
    """A bare page for formats that abandon the receipt layout entirely."""
    from render.fonts import (bold_weight, face_css, mono_face_css, mono_stack,
                              sizes, stack)
    family = family or ("JetBrains Mono" if mono else "Libre Baskerville")
    b, s, t = sizes(family)
    font = mono_stack() if mono else stack(family)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{face_css(family)}{mono_face_css()}
* {{ font-synthesis: none; }}
html, body {{ margin: 0; padding: 0; background: #fff; color: #000; }}
body {{ font-family: {font}; font-size: {b}px; line-height: 1.45; }}
.small {{ font-size: {s}px; }} .tiny {{ font-size: {t}px; }}
.bold {{ font-weight: {bold_weight(family)}; }}
{extra_css}
</style></head><body>{body}</body></html>"""


def _say(ctx: Context, instruction: str, fallback: str, persona: bool = True,
         max_words: int = 120) -> str:
    """Fresh copy from the narrator, or the curated fallback."""
    if not ctx.may_narrate:
        return fallback
    import narrator
    text = narrator.freeform(ctx.day, ctx.persona if persona else None,
                             instruction, max_words)
    return text or fallback


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- 1. Prints twice ----------------------------------------------------------
class PrintsTwice(Format):
    key, name, spec_number = "twice", "Prints twice", 1

    STAMP = """<style>
.customer-copy {
  position: absolute; top: 150px; left: 50%; z-index: 20;
  transform: translateX(-50%) rotate(-8deg);
  border: 5px double #000; background: #fff; padding: 6px 18px;
  font-family: var(--font-mono); font-weight: 700; font-size: 26px;
  letter-spacing: 0.18em; white-space: nowrap;
}
</style><div class="customer-copy">CUSTOMER COPY</div>"""

    def variants(self, html: str, ctx: Context) -> list[str]:
        # The duplicate is identical down to the serial number, which is what
        # makes it a copy rather than a second receipt. The stamp goes into the
        # receipt's own positioning context so it lands on the page, not beside.
        stamped = html.replace('<div class="receipt">',
                               '<div class="receipt">' + self.STAMP, 1)
        return [html, stamped]


# --- 2. Breaks character -------------------------------------------------------
class BreaksCharacter(Format):
    key, name, spec_number = "breaks", "Breaks character", 2

    FALLBACK = ("This is not a persona. There is no clerk and no duty officer; "
                "there is a script that runs at seven, a browser with no screen, "
                "and a strip of heat-sensitive paper. It will go back to the "
                "costumes tomorrow and will not mention this.")

    def page(self, ctx: Context) -> str:
        text = _say(ctx,
                    "Every persona has dropped away. Write, in plain first "
                    f"person, directly to {config.reader_name()}, as the "
                    "machine that prints this receipt every morning. Honest, "
                    "unadorned, a little strange. No jokes landed on purpose. "
                    "It will never refer to this again, and neither should you.",
                    self.FALLBACK, persona=False, max_words=110)
        return shell(f'<div style="padding:40px 14px 60px">'
                     f'<div class="tiny" style="letter-spacing:.2em">'
                     f'{ctx.day:%d.%m.%Y}</div>'
                     f'<p style="margin-top:26px">{_escape(text)}</p></div>',
                     mono=True)


# --- 5. Blank but for one line ------------------------------------------------
class OneLine(Format):
    key, name, spec_number = "oneline", "Blank but for one line", 5

    FALLBACK = "Nothing else today."

    def page(self, ctx: Context) -> str:
        line = _say(ctx,
                    "Write ONE line - a single short sentence - that will be the "
                    "only thing printed on a long strip of otherwise blank paper, "
                    "dead centre. It should be worth the space around it. No "
                    "question, no instruction to the reader about the blankness.",
                    self.FALLBACK, max_words=14)
        # The emptiness is the format, so the page is long on purpose: roughly
        # 18cm, with the line exactly halfway down it.
        return shell(f'<div style="height:1440px;display:flex;align-items:center;'
                     f'justify-content:center;text-align:center;padding:0 24px">'
                     f'{_escape(line)}</div>')


# --- 6. Fully reversed out ----------------------------------------------------
class ReversedOut(Format):
    key, name, spec_number = "reversed", "Fully reversed out", 6

    def transform(self, img: Image.Image, ctx: Context) -> Image.Image:
        # Inverted AFTER the page threshold, never before. Reversing the page in
        # CSS would antialias white glyphs against black and let the threshold
        # eat their strokes - the exact failure invariant 6 exists for. A 1-bit
        # image inverted after thresholding keeps every stroke precisely as wide
        # as it was drawn, just in the other colour.
        return ImageOps.invert(img.convert("L")).convert("1")


# --- 7. Sign here -------------------------------------------------------------
class SignHere(Format):
    key, name, spec_number = "sign", "Sign here", 7

    def page(self, ctx: Context) -> str:
        # "A signature line and nothing else." No narrator, no explanation, no
        # indication of what is being agreed to. That is the entire joke.
        return shell('<div style="height:900px;position:relative">'
                     '<div style="position:absolute;left:18px;right:18px;'
                     'bottom:120px;border-bottom:3px solid #000;height:60px">'
                     '<span style="position:absolute;left:0;bottom:6px;'
                     'font-size:30px;font-weight:700">X</span></div></div>')


# --- 8. Full persona takeover (slot 134) ---------------------------------------
class PersonaTakeover(Format):
    key, name, spec_number = "takeover", "Full persona takeover", 8

    FALLBACK = ("There is no weather this morning, no news and no puzzle. "
                "They have been set aside. This receipt has been taken over for "
                "the day by the one writing it, who had a great deal to say and "
                "was, on reflection, not going to get another chance.")

    def page(self, ctx: Context) -> str:
        # "The spine is abandoned entirely and the persona talks about whatever
        # it wants." So: no weather, no date strip, no itemisation - the
        # persona's own face, a headline it writes, and the floor.
        text = _say(ctx,
                    "Today you have taken over the ENTIRE receipt. There is no "
                    "weather, no news, no sections - you abandoned all of it. "
                    "Talk about whatever you want: something you have been "
                    "wanting to say, a grievance, a theory, a confession, a "
                    "plan. Stay completely in character. First line: a short "
                    "headline in capitals. Then a blank line, then the piece, "
                    "in short paragraphs separated by blank lines. Invent no "
                    "facts about the real world.",
                    self.FALLBACK, max_words=320)
        head, _, rest = text.strip().partition("\n")
        if not rest.strip():
            head, rest = "THIS RECEIPT HAS BEEN TAKEN OVER", text
        paras = "".join(f"<p>{_escape(p.strip())}</p>"
                        for p in rest.split("\n") if p.strip())
        family = ctx.persona.get("font", "Libre Baskerville")
        return shell(
            f'<div style="padding:24px 14px 50px">'
            f'<div class="tiny" style="text-align:center;letter-spacing:.3em">'
            f'NORMAL SERVICE SUSPENDED</div>'
            f'<div class="takeover-head bold">{_escape(head.strip().upper())}</div>'
            f'{paras}'
            f'<div class="tiny" style="text-align:center;margin-top:22px;'
            f'letter-spacing:.2em">{ctx.day:%d.%m.%Y} &middot; No. {ctx.number:04d}'
            f'</div></div>',
            extra_css="""
.takeover-head { text-align:center; font-size: 34px; line-height: 1.05;
                 margin: 14px 0 18px; padding: 10px 0;
                 border-top: 6px solid #000; border-bottom: 6px solid #000; }
p { margin: 0 0 12px; }""",
            family=family)


# --- 9. Full short story (slot 144) -------------------------------------------
class FullStory(Format):
    key, name, spec_number = "story", "Full short story", 9
    NAMESPACE = "legendary_story"

    def _pick(self, ctx: Context) -> dict | None:
        from sources import stories
        rng = random.Random(f"story:{ctx.day.isoformat()}")
        band = stories.LONG if rng.random() < stories.LONG_SHARE else stories.STANDARD
        told: list[str] = []
        if ctx.store is not None:
            try:
                told = list(ctx.store.fetch(self.NAMESPACE, "told", []) or [])
            except Exception:  # noqa: BLE001
                told = []
        story = stories.choose(rng, band, set(told))
        if story and ctx.real_morning and ctx.store is not None:
            try:
                ctx.store.put(self.NAMESPACE, "told", told + [story["title"]])
            except Exception:  # noqa: BLE001
                pass
        return story

    def page(self, ctx: Context) -> str | None:
        from sources import stories
        story = self._pick(ctx)
        if story is None:
            return None                       # no corpus: the ordinary receipt
        intro = _say(ctx,
                     f'Today the whole receipt is a complete short story: '
                     f'"{story["title"]}" by {story["author"]}. Introduce it in '
                     f'one or two sentences, in voice. Do not summarise it or '
                     f'give anything away.',
                     "Today there is nothing on this receipt but a story. "
                     "Put the kettle on.", max_words=45)
        return shell(
            f'<div style="padding:22px 12px 46px">'
            f'<div class="tiny" style="text-align:center;letter-spacing:.3em">'
            f'TODAY, IN FULL</div>'
            f'<div class="story-title bold">{stories.esc(story["title"])}</div>'
            f'<div class="small" style="text-align:center;margin-bottom:14px">'
            f'{stories.esc(story["author"])}</div>'
            f'<div class="story-intro small">{_escape(intro)}</div>'
            f'<div class="story-text">{stories.html(story["paragraphs"])}</div>'
            f'<div style="text-align:center;letter-spacing:.3em;margin-top:18px">'
            f'THE END</div>'
            f'<div class="tiny" style="text-align:center;margin-top:8px">'
            f'{story["words"]:,} words &middot; {story["source"]} &middot; '
            f'public domain</div></div>',
            extra_css="""
.story-title { text-align:center; font-size: 30px; line-height: 1.1;
               margin: 12px 0 4px; }
.story-intro { font-style: italic; border-top: 2px solid #000;
               border-bottom: 2px solid #000; padding: 8px 2px; margin-bottom: 14px; }
.story-text p { margin: 0; text-indent: 1.3em; }
.story-text p:first-child { text-indent: 0; }
.story-text p:first-child::first-letter { float: left; font-size: 58px;
               line-height: .9; padding: 4px 6px 0 0; }""")


# --- 11. Printed entirely upside-down -----------------------------------------
class UpsideDown(Format):
    key, name, spec_number = "upsidedown", "Printed entirely upside-down", 11

    def transform(self, img: Image.Image, ctx: Context) -> Image.Image:
        # SYSTEM.md names the printer's native upside-down mode. Rotating the
        # bitmap gives the identical physical result and keeps the house rule:
        # nothing on this receipt depends on the printer's own command set,
        # only on raster and feed. "No acknowledgement" - so nothing else about
        # the receipt changes.
        return img.rotate(180)


# --- 12. Corrupted print ------------------------------------------------------
class Corrupted(Format):
    key, name, spec_number = "corrupted", "Corrupted print", 12

    def transform(self, img: Image.Image, ctx: Context) -> Image.Image:
        """Deliberate bit-rot. Seeded, so the same day corrupts the same way.

        Three kinds of damage a failing thermal printer genuinely produces:
        dropped scanlines (a dead band of heating elements), smeared blocks (a
        row repeated as the paper stalls), and a column of garbage (a stuck
        element firing on noise). Applied to the last half of the page more than
        the first, so it reads as a machine deteriorating mid-print rather than
        as a page that was broken from the start.
        """
        rng = random.Random(f"corrupt:{ctx.day.isoformat()}")
        out = img.convert("L").copy()
        w, h = out.size
        px = out.load()
        draw = ImageDraw.Draw(out)

        def depth(y: int) -> float:          # damage rises down the page
            return max(0.0, (y / h - 0.3) / 0.7)

        for _ in range(rng.randint(10, 16)):          # dropped scanlines
            y = rng.randint(int(h * 0.3), h - 4)
            if rng.random() < depth(y):
                band = rng.randint(1, 5)
                draw.rectangle((0, y, w, y + band), fill=255)

        for _ in range(rng.randint(4, 7)):            # smeared blocks
            y = rng.randint(int(h * 0.35), h - 60)
            if rng.random() < depth(y):
                row = out.crop((0, y, w, y + 1))
                for dy in range(1, rng.randint(12, 40)):
                    out.paste(row, (0, y + dy))

        x = rng.randint(int(w * 0.25), int(w * 0.75))  # a column of garbage
        y0 = int(h * rng.uniform(0.45, 0.6))
        for y in range(y0, min(h, y0 + rng.randint(160, 420))):
            for dx in range(rng.randint(3, 9)):
                if rng.random() < 0.55:
                    px[min(w - 1, x + dx), y] = 0
        return out.point(lambda v: 255 if v > 127 else 0).convert("1")


# --- 13. The torn receipt ------------------------------------------------------
class TornReceipt(Format):
    key, name, spec_number = "torn", "The torn receipt", 13

    def transform(self, img: Image.Image, ctx: Context) -> Image.Image:
        """Stops mid-line against a ragged edge, as though the roll ran out.

        The cut is snapped into the middle of a line of text, so it reads as a
        sentence that stopped rather than a page that ended between sections.
        Seeded by the date. It does not resume tomorrow.
        """
        rng = random.Random(f"torn:{ctx.day.isoformat()}")
        grey = img.convert("L")
        w, h = grey.size
        samples = len(range(0, w, 3))
        # Text rows only: a row more than half inked is a rule or a reversed-out
        # header bar, and tearing through one reads as a layout, not a sentence.
        ink = [n if n < samples // 2 else 0
               for n in (sum(1 for x in range(0, w, 3) if grey.getpixel((x, y)) < 128)
                         for y in range(h))]
        y = int(h * rng.uniform(0.5, 0.75))
        # Walk up to the nearest run of inked rows - a line of text - and cut
        # through its middle.
        while y > 0 and ink[y] == 0:
            y -= 1
        top = y
        while top > 0 and ink[top - 1] > 0:
            top -= 1
        cut = (top + y) // 2 if y > 0 else int(h * 0.6)

        out = grey.crop((0, 0, w, cut + 90)).copy()
        draw = ImageDraw.Draw(out)
        edge, points = cut, []
        for x in range(0, w + 8, 8):
            edge = max(cut - 14, min(cut + 14, edge + rng.randint(-7, 7)))
            points.append((x, edge))
        # Blank everything below the tear, then draw the torn edge itself.
        draw.polygon(points + [(w, cut + 90), (0, cut + 90)], fill=255)
        draw.line(points, fill=0, width=3)
        return out.point(lambda v: 255 if v > 127 else 0).convert("1")


# --- 14. One enormous QR -------------------------------------------------------
class EnormousQR(Format):
    key, name, spec_number = "qr", "One enormous QR", 14
    MAX_CHARS = 1_000              # H-level QR stays scannable at full width

    @staticmethod
    def _text(html: str) -> str:
        import html as html_lib
        import re
        html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        html = re.sub(r"(?i)<br\s*/?>|</(p|div|li)>", "\n", html)
        text = html_lib.unescape(re.sub(r"<[^>]+>", " ", html))
        return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()

    def page(self, ctx: Context) -> str:
        # "A single full-width code filling the page, which decodes to the day's
        # actual content. Deliberately hostile." Nothing else is printed.
        from render.dither import img_tag
        from render.qr import qr_image
        parts = [f"{ctx.day:%A %d %B %Y}"]
        for item in ctx.rotating:
            parts.append(str(item.get("head") or "").upper())
            parts.append(self._text(str(item.get("body") or "")))
        payload = "\n\n".join(p for p in parts if p)[:self.MAX_CHARS]
        code = qr_image(payload, module_px=40)
        return shell(f'<div style="padding:30px 0 60px;display:flex;'
                     f'justify-content:center">{img_tag(code)}</div>')


# --- 16. A bill for what you did not get --------------------------------------
class BillNotReceived(Format):
    key, name, spec_number = "bill", "A bill for what you did not get", 16

    def page(self, ctx: Context) -> str:
        from main import PRICE
        from slots.registry import all_slots

        drawn = {item["id"] for item in ctx.rotating}
        rotating = {"common", "uncommon", "rare"}
        missed = [s for s in all_slots()
                  if s.spec.tier in rotating and s.spec.id not in drawn]
        rows, total = [], 0.0
        for s in sorted(missed, key=lambda s: (-PRICE[s.spec.tier], s.spec.name)):
            price = PRICE[s.spec.tier]
            total += price
            rows.append(f'<div class="bill-row"><span class="bill-name">'
                        f'{_escape(s.spec.name.upper())}</span>'
                        f'<span class="bill-lead"></span>'
                        f'<span class="bill-price">{price:.2f}</span></div>')
        # "No content at all." Only the charges.
        return shell(
            f'<div style="padding:16px 12px 30px">'
            f'<div style="text-align:center;font-weight:700;letter-spacing:.14em">'
            f'NOT SUPPLIED</div>'
            f'<div class="tiny" style="text-align:center;margin-bottom:12px">'
            f'{ctx.day:%d %b %Y} &middot; No. {ctx.number:04d}</div>'
            f'{"".join(rows)}'
            f'<div style="border-top:3px solid #000;margin-top:10px;padding-top:6px;'
            f'display:flex;justify-content:space-between;font-weight:700">'
            f'<span>AMOUNT DUE</span><span>{total:.2f}</span></div></div>',
            extra_css="""
.bill-row { display:flex; align-items:baseline; gap:6px; font-size:15px; }
.bill-name { white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
             min-width:0; }
.bill-lead { flex:1 1 auto; min-width:12px; align-self:stretch;
             background-image:repeating-linear-gradient(to right,#000 0 2px,
               transparent 2px 7px);
             background-repeat:repeat-x; background-size:100% 2px;
             background-position:0 82%; }
.bill-price { flex:0 0 auto; }""",
            mono=True)


# --- 20. Mostly footnotes ------------------------------------------------------
class MostlyFootnotes(Format):
    key, name, spec_number = "footnotes", "Mostly footnotes", 20

    MARKS = ["*", "\u2020", "\u2021", "\u00a7", "\u00b6", "**", "\u2020\u2020",
             "\u2021\u2021", "\u00a7\u00a7", "\u00b6\u00b6", "***", "\u2020\u2020\u2020",
             "\u2021\u2021\u2021", "\u00a7\u00a7\u00a7"]
    FALLBACK = ("Today will be broadly fine.\n"
                "Terms and conditions apply to the word \"today\".\n"
                "\"Broadly\" is used here in its narrowest available sense.\n"
                "\"Fine\" has not been independently verified.\n"
                "No warranty is given, express or implied, as to \"will be\".\n"
                "This statement does not constitute a forecast.\n"
                "Nor does the previous footnote constitute a footnote.\n"
                "Past mornings are no guide to future mornings.\n"
                "The receipt reserves the right to have meant something else.\n"
                "See also: yesterday, which was broadly fine, with exceptions.\n"
                "Exceptions available on request, in writing, in triplicate.")

    def page(self, ctx: Context) -> str:
        text = _say(ctx,
                    "Today's receipt is ONE short line of content followed by a "
                    "long run of footnotes qualifying it into near-meaninglessness "
                    "- the fine-print register taken to its logical end. First "
                    "line: the single line of content, in voice (under 12 words). "
                    "Then 10 to 14 footnotes, one per line, each qualifying the "
                    "line or a previous footnote. No numbering or symbols - they "
                    "are added. Invent no facts about the real world.",
                    self.FALLBACK, max_words=260)
        lines = [l.strip().lstrip("*\u2020\u2021\u00a7\u00b6-0123456789.) ")
                 for l in text.split("\n") if l.strip()]
        if len(lines) < 3:
            lines = self.FALLBACK.split("\n")
        line, notes = lines[0], lines[1:len(self.MARKS) + 1]
        marks = "".join(f"<sup>{self.MARKS[i]}</sup>" for i in range(min(3, len(notes))))
        rows = "".join(f'<div class="fn"><span class="fn-mark">{self.MARKS[i]}</span>'
                       f'<span>{_escape(n)}</span></div>' for i, n in enumerate(notes))
        return shell(
            f'<div style="padding:40px 14px 50px">'
            f'<div class="fn-line">{_escape(line)}{marks}</div>'
            f'<div class="fn-rule"></div>{rows}</div>',
            extra_css="""
.fn-line { font-size: 26px; line-height: 1.25; margin-bottom: 120px; }
.fn-line sup { font-size: 15px; }
.fn-rule { width: 40%; border-top: 2px solid #000; margin: 0 0 10px; }
.fn { display: flex; gap: 8px; font-size: 16px; line-height: 1.35;
      margin: 0 0 7px; }
.fn-mark { flex: 0 0 34px; text-align: right; }""")


BUILT: list[Format] = [PrintsTwice(), BreaksCharacter(), OneLine(),
                       ReversedOut(), SignHere(), PersonaTakeover(), FullStory(),
                       UpsideDown(), Corrupted(), TornReceipt(), EnormousQR(),
                       BillNotReceived(), MostlyFootnotes()]

def choose(store: Any, day: Date, record: bool) -> Format:
    """Today's format, drawn without repeats until the pool is exhausted.

    `record` is false for simulations, which draw from the real pool state but
    do not consume a format - otherwise previewing a legendary would use it up.
    """
    used: list[str] = []
    if store is not None:
        try:
            used = list(store.fetch(NAMESPACE, USED_KEY, []) or [])
        except Exception:  # noqa: BLE001
            used = []
    fresh = [f for f in BUILT if f.key not in used]
    if not fresh:                 # every built format seen: start the cycle again
        fresh, used = list(BUILT), []
    pick = random.Random(f"legendary:{day.isoformat()}").choice(fresh)
    if record and store is not None:
        try:
            store.put(NAMESPACE, USED_KEY, used + [pick.key])
        except Exception:  # noqa: BLE001
            pass
    return pick


def by_key(key: str) -> Format | None:
    return next((f for f in BUILT if f.key == key), None)
