"""Slots 57 and 59 - things only paper can do.

Two renderer slots. Neither has content in the ordinary sense; each is a
property of the physical object, which is why they are rare and why they are
not narrated.

  * **57 keep this one** - a mark saying this receipt is worth photographing
    before the paper fades.
  * **59 ruler down the edge** - a real ruler, printed alongside whatever else
    is on the page, costing no paper of its own.

**The ruler is a real ruler, and that is checkable.** 576 dots across 72mm is
exactly 8 dots per millimetre, so a tick every 8 pixels is a millimetre with no
rounding anywhere. That exactness is the whole reason this slot can exist: a
ruler that is approximately right is worse than no ruler, because you would only
find out after trusting it. Verified against a tape measure on paper.

It costs no paper because it is positioned absolutely against the receipt rather
than taking a section of its own - `.receipt` carries `position: relative` in the
base stylesheet for this. It is the only slot that draws outside its own box.

**Slot 53, fold-to-reveal, was built and then cut.** See `docs/SLOTS.md`.
"""

from __future__ import annotations

from printer.base import DOTS_PER_MM

from .base import Context, Slot, SlotResult, SlotSpec
from .registry import register


# --- 57 -------------------------------------------------------------------
@register
class KeepThisOne(Slot):
    spec = SlotSpec(id=57, name="Keep this one", tier="rare", paper_mm=18,
                    needs_narrator=True)

    # Thermal paper fades - that is the physics of the thing, not a defect, and
    # this slot exists because of it. The mark is the point; the words under it
    # are just the reason.
    MARK = """
<style>
.keep { border: 4px solid #000; padding: 8px var(--pad); margin: 4px 0;
        display: flex; align-items: center; gap: 12px; }
.keep-glyph { font-size: calc(var(--size-body) + 10px);
              font-weight: var(--bold); line-height: 1; }
.keep-text { font-size: var(--size-small); }
</style>
<div class="keep"><div class="keep-glyph">[*]</div>
<div class="keep-text">%s</div></div>
"""

    def _result(self, ctx: Context) -> SlotResult:
        return SlotResult(
            head="",
            body=self.MARK % ("Photograph this one. Thermal paper gives you "
                              "a few years at most, and less in the sun."),
            brief={"verbatim": True,
                   "instruction": "Name this section in voice, in a few words, "
                                  "or give an empty header. The mark is printed "
                                  "and speaks for itself."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)


# --- 59 -------------------------------------------------------------------
RULER_MM = 120          # as long as the shortest plausible receipt
TICK_MM = 4
TICK_5MM = 9
TICK_CM = 16


def ruler_svg(length_mm: int = RULER_MM) -> str:
    """A real ruler. One tick per millimetre, exactly.

    Exact because 576 dots over 72mm is 8 dots per millimetre with nothing left
    over, so every tick lands on a whole pixel and nothing accumulates error
    down the length of it.
    """
    height = length_mm * DOTS_PER_MM
    parts = [f'<line x1="0" y1="0" x2="0" y2="{height}" stroke="#000" '
             f'stroke-width="2"/>']
    for mm in range(length_mm + 1):
        y = mm * DOTS_PER_MM
        if mm % 10 == 0:
            width = TICK_CM
            parts.append(f'<text x="{width + 3}" y="{y + 4}" font-size="9" '
                         f'style="font-family:var(--font-mono)" fill="#000">'
                         f'{mm // 10}</text>')
        elif mm % 5 == 0:
            width = TICK_5MM
        else:
            width = TICK_MM
        parts.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" '
                     f'stroke="#000" stroke-width="1.5"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="30" '
            f'height="{height}" viewBox="0 0 30 {height}">'
            + "".join(parts) + "</svg>")


@register
class RulerDownTheEdge(Slot):
    spec = SlotSpec(id=59, name="Ruler down the edge", tier="rare", paper_mm=0,
                    needs_narrator=False)

    def _result(self, ctx: Context) -> SlotResult:
        # Positioned against `.receipt`, which the base stylesheet makes a
        # positioning context. That is what lets this cost no paper: it runs
        # down the side of whatever else the day happened to draw.
        return SlotResult(
            head="",
            body='<style>'
                 '.ruler-edge{position:absolute;left:0;top:112px;z-index:5}'
                 '.slot-59{margin:0;padding:0;height:0;overflow:visible}'
                 # The page insets ONLY on days this slot draws, and it does so
                 # from here rather than from the base stylesheet - a permanent
                 # gutter for a rare slot would be a gutter on 29 days out of 30,
                 # and invariant 3 says the page has no gutters of its own. The
                 # ruler still runs alongside the content and still costs no
                 # paper; it just stops printing through the text.
                 '.receipt:has(.ruler-edge) .pad{padding-left:38px}'
                 '.receipt:has(.ruler-edge) .masthead{padding-left:38px}'
                 '</style>'
                 f'<div class="ruler-edge">{ruler_svg()}</div>',
            paper_mm=0,
            brief={"verbatim": True,
                   "instruction": "Give an empty header. This section is a ruler "
                                  "printed down the edge of the page and has no "
                                  "text of its own."},
        )

    def fetch(self, ctx: Context) -> SlotResult:
        return self._result(ctx)

    def fixture(self, ctx: Context) -> SlotResult:
        return self._result(ctx)
