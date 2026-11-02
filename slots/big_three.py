"""Slot 49 - Big three checkboxes.

Three empty boxes and three ruled lines. Deliberately analog: the receipt does
not know what the three things are and never finds out.

The body is markup rather than prose, so it is marked verbatim - the narrator
gets the header and nothing else. That combination (real HTML in `body`, plus
`verbatim`) is the pattern for every slot whose content is a shape rather than a
sentence, and it is enforcement rather than etiquette: without it, the narrator
has a `body` field in its schema and will eventually write a sentence into it,
replacing the boxes.

The boxes are drawn with borders rather than characters. A ballot-box glyph
depends on the persona face having one, and Special Elite does not.
"""

from __future__ import annotations

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register

COUNT = 3

# Sized for a pen, in millimetres rather than by eye: the page is 576px across
# 72mm, so 8px is 1mm. A 64px line is 8mm, which is school-ruled and what an
# ordinary hand actually needs. The rule is 2px because a hairline under a
# written word reads as a smudge on thermal paper.
_CSS = """
<style>
.big3 { margin: 4px 0 2px; }
.big3-row { display: flex; align-items: flex-end; gap: 12px; margin-top: 14px; }
.big3-box { flex: 0 0 auto; width: 32px; height: 32px; border: 3px solid #000; }
.big3-line { flex: 1 1 auto; border-bottom: 2px solid #000; height: 64px; }
</style>
"""


def boxes_html(count: int = COUNT) -> str:
    rows = "".join(
        '<div class="big3-row"><div class="big3-box"></div>'
        '<div class="big3-line"></div></div>'
        for _ in range(count))
    return f'{_CSS}<div class="big3">{rows}</div>'


@register
class BigThree(Slot):
    spec = SlotSpec(id=49, name="Big three checkboxes", tier="common",
                    paper_mm=42, needs_narrator=True)

    def _result(self, ctx: Context) -> SlotResult:
        return SlotResult(
            head="The Big Three",
            body=boxes_html(),
            brief={"verbatim": True,
                   "count": COUNT,
                   "purpose": "three blank boxes and ruled lines, filled in by "
                              "hand - the three things that matter today",
                   "instruction": "Name this section in voice. The lines are "
                                  "blank on purpose; do not fill them in and do "
                                  "not suggest what should go on them."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
