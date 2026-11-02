"""Slot 115 - Three outlets, one story.

One line per outlet, in the narrator's words: how each is telling the same
event. **Grounded in what the outlets actually published** - the narrator is
handed their real headlines and summaries for one event and paraphrases those,
rather than searching and characterising coverage it found on its own.

**Only printed when it is worth it.** The slot is drawn like any uncommon, then
asks a cheap model whether any story today is being told three genuinely
different ways. Three wordings of the same facts are not a section, so most of
the time the answer is no and the slot drops - the day prints one slot fewer
rather than a dull comparison.

**How the story is found, cheaply.**
  1. A pool of outlets chosen for spread rather than taste (`[framing]` in
     config.toml - US left and right, UK, France, Germany, Qatar, India, Hong
     Kong...). Read only on the days 115 is drawn; feeds slot 10 already
     downloaded are not downloaded again.
  2. `sources.framing` groups the headlines that share rare words - free, and
     reliable at "these outlets all covered one thing".
  3. `narrator.framings`, on the cheap model at low effort, picks the group and
     the three headlines where one event is framed most differently, and judges
     whether the difference is interesting. That is the gate. It also says in a
     line what differs, which the narrator gets as a fact to write from.
  4. The narrator paraphrases, in the day's single call. If that call fails,
     the three headlines print as they were published, under their outlets.

No narrator (offline, no key) means no gate, and the slot drops. A story printed
here in the last fortnight is skipped, so an ongoing war does not become the
slot's permanent subject.
"""

from __future__ import annotations

from datetime import timedelta

import config
from sources import article, framing, rss

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

PRINTED = "framing:printed"
MEMORY_DAYS = 14


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _recent_words(ctx: Context) -> list[set[str]]:
    """The words of each story this slot printed in the last fortnight."""
    if ctx.store is None:
        return []
    out = []
    for back in range(1, MEMORY_DAYS + 1):
        day = (ctx.date - timedelta(days=back)).isoformat()
        try:
            got = ctx.store.fetch(PRINTED, day)
        except Exception:  # noqa: BLE001
            got = None
        if got:
            out.append(framing._words(" ".join(got)))
    return out


def _is_repeat(group: list[rss.Item], recent: list[set[str]]) -> bool:
    words = framing._words(" ".join(i.title for i in group))
    return any(len(words & old) / max(1, len(words | old)) >= 0.25
               for old in recent)


@register
class ThreeOutlets(Slot):
    # 52mm: three outlets of up to 120-character headlines, the fallback body,
    # measured on the Clerk (tools/papercheck.py's persona). The paraphrase is
    # shorter.
    spec = SlotSpec(id=115, name="Three outlets, one story", tier="uncommon",
                    paper_mm=52, needs_network=True, needs_narrator=True)
    HEAD = "One Story, Three Ways"

    def fetch(self, ctx: Context) -> SlotResult | None:
        if ctx.offline or not ctx.shared.get("may_narrate", True):
            return None          # no gate, no slot
        items = rss.gather(
            config.get("framing", "feeds", default=[]),
            store=ctx.store, offline=ctx.offline,
            max_age_hours=float(config.get("framing", "max_age_hours",
                                           default=36)),
            memo=ctx.shared)
        recent = _recent_words(ctx)
        groups = [g for g in framing.stories(items) if not _is_repeat(g, recent)]
        if not groups:
            return None

        import narrator
        verdict = narrator.framings(
            [[{"title": i.title, "source": i.source} for i in g]
             for g in groups])
        if verdict is None:
            return None          # nothing told three interesting ways today
        three = [groups[verdict.group][p] for p in verdict.picks]

        if ctx.store is not None and ctx.shared.get("real_morning") \
                and not ctx.shared.get("printed_already"):
            try:
                ctx.store.put(PRINTED, ctx.date.isoformat(),
                              [i.title for i in three], when=ctx.date)
            except Exception:  # noqa: BLE001 - memory is never worth a crash
                pass

        return SlotResult(
            head=self.HEAD,
            # What prints if the narrator does not: the headlines themselves,
            # under their outlets. Facts, and a fair comparison on their own.
            body="".join(
                f'<div class="framing"><span class="framing-src">'
                f'{_esc(i.source)}</span>{_esc(i.title)}</div>' for i in three),
            brief={
                "coverage": [{"outlet": i.source, "headline": i.title,
                              "summary": article.trim(i.summary, 200)}
                             for i in three],
                "what_differs": verdict.angle,
                "instruction":
                    "Three outlets are telling one event. Write exactly three "
                    "short lines, one per outlet, separated by a BLANK line, "
                    "each starting with the outlet's name and a colon, then "
                    "how IT frames the event - what it leads with, which "
                    "number, who it makes the subject, whose words it "
                    "carries. Work only from that outlet's headline and "
                    "summary given here; add no facts. Keep every "
                    "attribution: when the summary says officials, a "
                    "government or one side claims something, the outlet is "
                    "REPORTING that claim, not making it - say whose claim it "
                    "carries, never present it as the outlet's own view. "
                    "Report the framing, do not judge it, and add no fourth "
                    "line saying which is right. In voice, but plainly.",
            },
        )

    def fixture(self, ctx: Context) -> SlotResult | None:
        # The gate is a model call, so there is no offline 115. Dropping is
        # this slot's honest offline answer, like 112 without its headlines.
        return None
