"""Slot registry status, and a smoke test of every fixture.

Two jobs:
  * report coverage against docs/SLOTS.md - the honest progress bar
  * fetch every registered slot through `safe_fetch` and confirm none of them
    raises, which is the invariant the whole morning depends on
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slots import Context, safe_fetch  # noqa: E402
from slots.base import SlotFailure  # noqa: E402
from slots.registry import all_slots, coverage, every_slot, load_all  # noqa: E402


def main() -> None:
    load_all()
    cov = coverage()

    print(f"COVERAGE  {len(cov.built)}/{cov.total} slots built ({cov.pct:.0f}%)\n")

    print("built:")
    for slot in every_slot():
        s = slot.spec
        flags = "".join(c for c, on in
                        (("N", s.needs_network), ("W", s.needs_narrator),
                         ("S", s.series)) if on)
        mark = ""
        base = getattr(slot, "base_spec", s)
        if base.tier != s.tier:
            mark = f"  (config: was {base.tier})"
        if s.id in cov.disabled:
            mark += "  [DISABLED]"
        print(f"  #{s.id:<4} {s.name:<24} {s.tier:<10} {s.paper_mm:>3}mm  "
              f"{flags}{mark}")

    if cov.mismatched:
        print("\nTIER MISMATCH vs docs/SLOTS.md:")
        for sid, doc, code in cov.mismatched:
            print(f"  #{sid}: docs say {doc!r}, code says {code!r}")

    if cov.undocumented:
        print(f"\nNOT IN SLOTS.md: {cov.undocumented}")

    print(f"\nremaining ({len(cov.missing)}):")
    for e in cov.missing[:12]:
        print(f"  #{e.id:<4} {e.name[:40]:<40} {e.tier}")
    if len(cov.missing) > 12:
        print(f"  ... and {len(cov.missing) - 12} more")

    # --- smoke test -----------------------------------------------------
    print("\nFIXTURE SMOKE TEST (offline, no slot may raise)")
    ctx = Context(date=date(2026, 9, 3), offline=True)
    failures: list[SlotFailure] = []
    for slot in all_slots():
        r = safe_fetch(slot, ctx, failures)
        got = "None" if r is None else (
            ", ".join(k for k, v in
                      (("body", r.body), ("image", r.image), ("fine", r.fine),
                       ("answer", r.answer))
                      if v) or "empty")
        print(f"  #{slot.spec.id:<4} {slot.spec.name:<24} -> {got}")
    if failures:
        print("\n  FAILURES:")
        for f in failures:
            print(f"    #{f.slot_id} {f.name}: {f.error}")
        sys.exit(1)
    print("\n  all fixtures returned without raising")


if __name__ == "__main__":
    main()
