"""Slot 23 - Painting of the day.

Halftoned, with one line of context, from three rotating open-access museum
APIs. Sources and the reasoning behind the rotation are in `sources/museum.py`.

**Dithered, not thresholded** - the opposite of the tarot and XKCD slots, and
the distinction that matters most on this printer. A painting is a photograph of
a continuous-tone object: thresholding it throws away every midtone and leaves a
Rorschach blot. Atkinson dithering keeps the tonal range as texture. Line art
goes the other way for the same underlying reason. `CLAUDE.md` states the rule;
this slot and slot 132 are the two ends of it.

**Contrast is checked before printing.** A washed-out watercolour or a dark
brown panel dithers to near-uniform mud that costs 60mm of paper and shows
nothing. The image is scored first and rejected below a floor, which is worth
doing here because the source is a random draw from a million objects and
nobody has looked at it.

The metadata is never narrated. Titles, artists and dates are facts about a real
object, and a persona rephrasing "Oil on canvas, 1888" is one step from getting
it wrong (SYSTEM.md 9).
"""

from __future__ import annotations

import io

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

IMAGE_W = 480          # 60mm wide, leaving the page room around it
MAX_H = 520
# Below this, a dithered image is mud. Measured against `contrast_score`, which
# is a spread statistic rather than a mean, so a dark painting with real detail
# still passes and a flat one does not.
MIN_CONTRAST = 0.16
ATTEMPTS = 4


@register
class Painting(Slot):
    spec = SlotSpec(id=23, name="Painting of the day", tier="uncommon",
                    paper_mm=80, needs_network=True, needs_narrator=True)

    def _build(self, meta: dict, image) -> SlotResult:
        line = " &middot; ".join(
            p for p in (meta.get("artist"), meta.get("date")) if p)
        return SlotResult(
            head=meta.get("title") or "Painting",
            image=image,
            fine=f"{meta.get('title')} &middot; {line}<br>{meta.get('source')}",
            brief={"verbatim": True,
                   "title": meta.get("title"),
                   "artist": meta.get("artist"),
                   "date": meta.get("date"),
                   "collection": meta.get("source"),
                   "instruction": "Name this section in voice. The picture and "
                                  "its label print as they are - the title, "
                                  "artist, date and collection are facts about a "
                                  "real object and are not yours to rephrase."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        from PIL import Image

        from render.dither import contrast_score, fit, prepare
        from sources import museum

        rng = ctx.rng(self.spec.id)
        last = None
        for _ in range(ATTEMPTS):
            meta, blob = museum.pick(rng, store=ctx.store, offline=ctx.offline)
            source = Image.open(io.BytesIO(blob)).convert("L")
            width = IMAGE_W
            if source.height / source.width * width > MAX_H:
                width = int(MAX_H * source.width / source.height)
            fitted = fit(source, width)
            last = (meta, fitted)
            if contrast_score(fitted) >= MIN_CONTRAST:
                return self._build(meta, prepare(source, width))

        # Every candidate was flat. Print the last one rather than dropping: a
        # muddy painting is a worse morning than a good one, and no worse than
        # a missing section.
        meta, fitted = last                                # type: ignore[misc]
        return self._build(meta, prepare(fitted, fitted.width))

    def fixture(self, ctx: Context) -> SlotResult:
        """A drawn frame, so an offline render is not one section short."""
        from PIL import Image, ImageDraw

        img = Image.new("1", (IMAGE_W, 320), 1)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, IMAGE_W - 1, 319), outline=0, width=6)
        draw.rectangle((18, 18, IMAGE_W - 19, 301), outline=0, width=2)
        # A 50% checker is the one pattern that survives a threshold as grey.
        for y in range(30, 290, 4):
            for x in range(30, IMAGE_W - 30, 4):
                draw.point((x + (y // 4 % 2) * 2, y), fill=0)
        return self._build(
            {"title": "Painting unavailable", "artist": "no network",
             "date": "", "source": "fixture"}, img)
