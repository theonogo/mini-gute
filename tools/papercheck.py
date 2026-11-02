"""Measure what each slot actually costs in paper, against what it claims.

`SlotSpec.paper_mm` is not documentation. The selection engine fits the day's
draw to the budget using those numbers *before* anything is fetched, so a slot
that under-reports gets drawn on days it does not fit, and the render blows the
budget assertion at seven in the morning.

A claim drifts whenever a layout changes, and the variable slots are worse
than they look: a poem costs far more on the day it draws a long one, a painting
on the day it draws a tall one.

This renders each slot on its own, several times over different dates so the
variable ones show their spread, and reports the WORST case against the claim.
The spec should be an upper bound, not an average: being generous costs a slot
being skipped occasionally, and being optimistic costs a failed morning.

    python tools/papercheck.py
    python tools/papercheck.py --days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import date as Date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as M  # noqa: E402
import render.page as page  # noqa: E402
from render import Renderer, img_tag  # noqa: E402
from slots import Context, safe_fetch  # noqa: E402
from slots.registry import all_slots, load_all  # noqa: E402

# The frame every slot renders inside: masthead, rules, footer. Subtracted so
# the figure reported is the slot's own contribution.
DOTS_PER_MM = 8

# Slots that claim no paper because they draw outside their own box, beside the
# rest of the page. Rendered alone they are taller than the near-empty page they
# sit on, so they always measure as under-reporting - a standing false failure,
# which is the kind that hides a real one. Named, not inferred from a claim of
# zero: a slot that says 0 by mistake must still be caught.
OVERLAYS = {
    59: "the ruler runs down the edge beside the content (SLOT-STATUS 59)",
}


def chrome_mm(renderer: Renderer, persona: dict, day: Date) -> float:
    html = M.build_html(day, persona, {}, [], 1, None)
    return renderer.render(html).height / DOTS_PER_MM


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--persona", default="victorian-clerk",
                    help="the persona whose page the slots are measured on")
    args = ap.parse_args()

    page.BUDGET_PX = 99_999          # measuring, not enforcing
    load_all()
    persona = M.load_personas()[args.persona]
    slots = [s for s in all_slots() if s.spec.id not in M.SPINE_IDS]

    rows = []
    with Renderer() as renderer:
        base = chrome_mm(renderer, persona, Date.today())
        for slot in slots:
            heights = []
            for i in range(args.days):
                day = Date.today() + timedelta(days=i)
                ctx = Context(date=day, offline=True)
                ctx.shared["persona_art_tags"] = persona.get("art_tags", [])
                result = safe_fetch(slot, ctx)
                if result is None:
                    continue
                item = {
                    "id": slot.spec.id, "tier": slot.spec.tier,
                    "name": slot.spec.name, "head": result.head,
                    "body": result.body,
                    "image": (img_tag(result.image)
                              if result.image is not None else None),
                    "fine": result.fine, "answer": result.answer,
                    "brief": result.brief, "needs_narrator": False,
                }
                html = M.build_html(day, persona, {}, [item], 1, None)
                heights.append(renderer.render(html).height / DOTS_PER_MM - base)
            if heights:
                rows.append((slot.spec.id, slot.spec.name, slot.spec.paper_mm,
                             min(heights), max(heights)))

    print(f"Rendered alone in {args.persona} over {args.days} days, chrome "
          f"({base:.0f}mm) subtracted.\n")
    print(f"{'id':>5}  {'slot':<30}{'spec':>6}{'min':>7}{'max':>7}  verdict")
    bad = 0
    for sid, name, spec, low, high in sorted(rows, key=lambda r: r[4] - r[2]):
        over = high - spec
        if sid in OVERLAYS:
            verdict = "overlay: costs no paper by design"
        elif over > 4:
            verdict, bad = f"UNDER-REPORTS by {over:.0f}mm", bad + 1
        elif over < -12:
            verdict = f"over-reserves by {-over:.0f}mm"
        else:
            verdict = "ok"
        print(f"{sid:>5}  {name[:30]:<30}{spec:>6}{low:>7.0f}{high:>7.0f}"
              f"  {verdict}")

    print(f"\n{bad} slot(s) claim less paper than they use. Those are the ones "
          f"that break a morning:\nthe engine fits them, then the page "
          f"overflows.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
