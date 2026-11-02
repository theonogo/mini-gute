"""Slot 125 - XKCD of the day.

The JSON API is open, unversioned and has worked unchanged for fifteen years:
`https://xkcd.com/info.0.json` for the current strip, `/NNN/info.0.json` for a
specific one.

**Thresholded, not dithered.** XKCD is line art - black stick figures on white -
so it takes the same treatment as the tarot deck and for the same reason:
Atkinson turns solid ink into grey texture and throws away the crispness that
made it printable. `prepare_line_art` is the right pipeline, and its per-image
threshold matters here because a dense strip and a three-panel gag have wildly
different ink coverage.

**The title text is included.** It is not in the catalogue entry, but it is half
the comic - the joke under the joke, which you only get by hovering on the web.
On paper there is nowhere to hover, so it prints as fine print, which is exactly
the right register for it.

**A random back-catalogue strip, not today's.** Today's is a coin flip on
whether it is any good, and there are three thousand behind it. Comic 404 is
skipped because it does not exist - that is the joke, and the API returns a 404
for it, which would otherwise look like an outage.
"""

from __future__ import annotations

import io

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "xkcd"
COMIC_W = 520          # inside the page width, with room to breathe
MAX_H = 560            # ~70mm; a few strips are enormous and get scaled down
NOT_FOUND = 404        # the comic that is deliberately absent


@register
class Xkcd(Slot):
    spec = SlotSpec(id=125, name="XKCD of the day", tier="uncommon",
                    paper_mm=84, needs_network=True, needs_narrator=True)

    def _build(self, meta: dict, image, stale: bool = False) -> SlotResult:
        alt = " ".join((meta.get("alt") or "").split())
        return SlotResult(
            head=meta.get("safe_title") or meta.get("title") or "XKCD",
            image=image,
            fine=alt + (" &middot; from cache" if stale else ""),
            brief={"verbatim": True,
                   "number": meta.get("num"),
                   "title": meta.get("safe_title") or meta.get("title"),
                   "instruction": "Name this section in voice. The comic is a "
                                  "drawing and prints as it is; do not describe "
                                  "or explain it."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        from render.dither import prepare_line_art
        from sources.http import cached_json, get_bytes
        from PIL import Image

        latest, _ = cached_json("https://xkcd.com/info.0.json", store=ctx.store,
                                namespace=NAMESPACE, key="latest",
                                offline=ctx.offline, when=ctx.date)
        newest = int(latest.get("num", 1))

        rng = ctx.rng(self.spec.id)
        number = rng.randint(1, newest)
        while number == NOT_FOUND:
            number = rng.randint(1, newest)

        meta, stale = cached_json(f"https://xkcd.com/{number}/info.0.json",
                                  store=ctx.store, namespace=NAMESPACE,
                                  key=str(number), offline=ctx.offline,
                                  when=ctx.date)
        source = Image.open(io.BytesIO(get_bytes(meta["img"])))
        # A comic is line art on white, and already close to 1-bit. autolevel is
        # off: a strip that is mostly white has almost no dynamic range to
        # stretch, and levelling it amplifies JPEG ringing into grey speckle.
        image = prepare_line_art(source, min(COMIC_W, source.width),
                                 cut=128, autolevel=False)
        if image.height > MAX_H:
            width = int(COMIC_W * MAX_H / image.height)
            image = prepare_line_art(source, width, cut=128, autolevel=False)
        return self._build(meta, image, stale)

    def fixture(self, ctx: Context) -> SlotResult:
        """No network: a drawn placeholder card rather than a dropped slot.

        The same call the tarot slot makes. A fixture that returns None would
        make every offline render and every contact sheet silently one section
        shorter than the real thing.
        """
        from PIL import Image, ImageDraw

        img = Image.new("1", (COMIC_W, 200), 1)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, COMIC_W - 1, 199), outline=0, width=3)
        for x in (COMIC_W // 3, 2 * COMIC_W // 3):
            draw.line((x, 0, x, 199), fill=0, width=3)
        draw.text((16, 90), "[ three panels, offline ]", fill=0)
        return self._build(
            {"num": 0, "safe_title": "XKCD", "alt": "Fixture: no network."},
            img)
