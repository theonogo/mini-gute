"""Slot 148 - Three-part short story.

A public-domain story split across three consecutive mornings. Long enough to be
a real read, short enough to actually finish.

**A mini-series, built on pinning like the two-day recipe.** Part one is drawn
as a rare; it records the story and pins the slot to tomorrow, and parts two
and three arrive whatever the tier and recency would have said. Like the recipe
it is exempt from the one-series-at-a-time rule in SYSTEM.md 5 - it is three
days, not three weeks, and holding a city map up for it would be silly.

**If a morning is missed, the story waits.** The next part prints the next time
the slot runs, with no pretence that no time has passed. Only a real morning
advances or pins anything, so a `--date` simulation cannot consume part two.

**Verbatim.** The persona names the section; the story is not its to retell.
The split falls between paragraphs, roughly by word count.
"""

from __future__ import annotations

from datetime import timedelta

from sources import stories

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

NAMESPACE = "story3"
PARTS = 3
AVOID = 30          # recently told titles, skipped until this many others have been

_CSS = """
<style>
.story3 p { margin: 0 0 6px; text-indent: 1.2em; font-size: var(--size-small);
            line-height: 1.4; }
.story3 p:first-child { text-indent: 0; }
.story3-title { font-size: calc(var(--size-body) + 3px); font-weight: var(--bold);
                line-height: 1.2; }
.story3-byline { font-size: var(--size-tiny); letter-spacing: .08em;
                 text-transform: uppercase; margin-bottom: 6px; }
.story3-more { text-align: center; font-size: var(--size-tiny);
               letter-spacing: .2em; margin-top: 8px; }
</style>
"""


@register
class ThreePartStory(Slot):
    # Worst case measured: a 539-word part in the Daily Roll's large face.
    # Typical parts are ~400 words and well under this.
    spec = SlotSpec(id=148, name="Three-part short story", tier="rare",
                    paper_mm=295, needs_narrator=True)

    def _get(self, ctx: Context, key: str, default):
        if ctx.store is None:
            return default
        try:
            return ctx.store.fetch(NAMESPACE, key, default)
        except Exception:  # noqa: BLE001
            return default

    def _put(self, ctx: Context, key: str, value) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            ctx.store.put(NAMESPACE, key, value)
        except Exception:  # noqa: BLE001
            pass

    def _part(self, story: dict, n: int) -> SlotResult:
        runs = stories.split(story, PARTS)
        n = min(n, len(runs))
        last = n == len(runs)
        more = "THE END" if last else "CONTINUED TOMORROW"
        return SlotResult(
            head=story["title"],
            body=(f'{_CSS}<div class="story3">'
                  f'<div class="story3-title">{stories.esc(story["title"])}</div>'
                  f'<div class="story3-byline">{story["author"]} &middot; part '
                  f'{n} of {len(runs)}</div>{stories.html(runs[n - 1])}'
                  f'<div class="story3-more">{more}</div></div>'),
            fine=f'{story["source"]}. Public domain.',
            brief={"verbatim": True, "story": story["title"],
                   "author": story["author"], "part": n, "of": len(runs),
                   "instruction": "Name this section in voice - it is part "
                                  f"{n} of {len(runs)} of a short story by "
                                  f"{story['author']}. The story prints exactly "
                                  "as written. Do not summarise or spoil it."},
        )

    def fetch(self, ctx: Context) -> SlotResult | None:
        running = self._get(ctx, "running", None) or {}
        story = stories.by_title(running.get("title", ""))
        part = int(running.get("part", 0))
        if story is not None:
            if running.get("day") == ctx.date.isoformat():   # a rerun of today
                return self._part(story, part)
            if part < PARTS:
                part += 1
                self._put(ctx, "running", {"title": story["title"], "part": part,
                                           "day": ctx.date.isoformat()})
                if part < PARTS:
                    self._pin_tomorrow(ctx)
                return self._part(story, part)

        told = list(self._get(ctx, "told", []) or [])
        story = stories.choose(ctx.rng(self.spec.id), stories.THREE_PART, set(told))
        if story is None:
            return None
        self._put(ctx, "running", {"title": story["title"], "part": 1,
                                   "day": ctx.date.isoformat()})
        self._put(ctx, "told", ([story["title"]] + told)[:AVOID])
        self._pin_tomorrow(ctx)
        return self._part(story, 1)

    def _pin_tomorrow(self, ctx: Context) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        from selection import pin
        pin(ctx.store, self.spec.id, ctx.date + timedelta(days=1))

    def fixture(self, ctx: Context) -> SlotResult | None:
        story = stories.choose(ctx.rng(self.spec.id), stories.THREE_PART)
        return self._part(story, 1) if story else None
