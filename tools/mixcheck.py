"""Simulate N mornings and check the rarity mix against SYSTEM.md.

Covers the persona draw too (SYSTEM.md 3.6): which face a morning wears is the
same shape of question, and the persona tiers have their own dials.

The maths in SYSTEM.md 4 predicts an uncommon-or-better on ~76% of days and a
rare on ~25%. This runs the real selection engine over a simulated archive and
reports what actually comes out - the numbers were derived on paper and have
never been checked against the code that implements them.

It also answers the question the maths cannot: whether the mix *feels* right.
Watching the per-day tier strings scroll past is the cheap version of the
contact sheet, without rendering or paper.
"""

import sys
from collections import Counter
from datetime import date as Date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import main as pipeline  # noqa: E402  (this file has a main() of its own)
import selection  # noqa: E402

# Read rather than hardcoded, so the target moves when the odds do.
LEGENDARY_ODDS = int(config.get('rarity', 'legendary_odds', default=25))
W = {t: float(config.get('rarity', t)) for t in ('common', 'uncommon', 'rare')}
_DRAWS = range(int(config.get('rarity', 'draws_min', default=3)),
               int(config.get('rarity', 'draws_max', default=6)) + 1)
# Expected frequencies derived from the configured weights, averaged over the
# draw counts, so the targets move when the weights do.
T_UNCOMMON_DAY = 1 - sum(W['common'] ** n for n in _DRAWS) / len(_DRAWS)
T_RARE_DAY = 1 - sum((1 - W['rare']) ** n for n in _DRAWS) / len(_DRAWS)
from slots.registry import all_slots, load_all  # noqa: E402

SYMBOL = {"common": ".", "uncommon": "+", "rare": "*"}
PERSONA_TIERS = pipeline.PERSONA_TIERS


class FakeStore:
    """An in-memory archive, so a simulation never touches the real one."""

    def __init__(self):
        self.rows: list[tuple[Date, list[int]]] = []
        self.faces: list[tuple[Date, str]] = []

    def receipt_count(self) -> int:
        return len(self.rows)

    def last_seen(self, before: Date, within_days: int = 120) -> dict[int, Date]:
        seen: dict[int, Date] = {}
        for when, ids in sorted(self.rows, reverse=True):
            if when >= before:
                continue
            for sid in ids:
                seen.setdefault(sid, when)
        return seen

    def personas_last_seen(self, before: Date,
                           within_days: int = 180) -> dict[str, Date]:
        seen: dict[str, Date] = {}
        for when, who in sorted(self.faces, reverse=True):
            if when < before:
                seen.setdefault(who, when)
        return seen

    def record(self, when: Date, ids: list[int], persona: str = "") -> None:
        self.rows.append((when, ids))
        if persona:
            self.faces.append((when, persona))


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("days", nargs="?", type=int, default=90)
    ap.add_argument("--show", type=int, default=30, help="days to print")
    ap.add_argument("--auditions", action="store_true",
                    help="draw the personas still in audition too")
    args = ap.parse_args()

    load_all()
    slots = all_slots()
    personas = pipeline.load_personas(auditions=args.auditions)
    if args.auditions:                         # a rehearsal draw, not the real pool
        personas = {k: {**v, "audition": False} for k, v in personas.items()}
    store = FakeStore()
    start = Date.today()

    tier_counts: Counter[str] = Counter()
    per_slot: Counter[int] = Counter()
    with_uncommon = with_rare = legendary = 0
    gaps: list[int] = []
    per_persona: Counter[str] = Counter()
    persona_tiers: Counter[str] = Counter()
    repeats = 0
    worn: str | None = None

    for i in range(args.days):
        day = start + timedelta(days=i)
        # offline=True keeps the legendary roll on the local PRNG; hammering
        # random.org ninety times for a simulation would be rude.
        draw = selection.select(day, slots, store=store, offline=True)
        face = pipeline.pick_persona(personas, day, None, store)
        per_persona[face["name"]] += 1
        persona_tiers[face.get("rarity", "common")] += 1
        repeats += face["name"] == worn
        worn = face["name"]
        tiers = draw.tiers
        tier_counts.update(tiers)
        per_slot.update(s.spec.id for s in draw.slots)
        if set(tiers) & {"uncommon", "rare"}:
            with_uncommon += 1
        if "rare" in tiers:
            with_rare += 1
            gaps.append(i)
        if draw.legendary:
            legendary += 1
        store.record(day, [s.spec.id for s in draw.slots], face["name"])

        if i < args.show:
            strip = "".join(SYMBOL.get(t, "?") for t in tiers)
            names = ", ".join(s.spec.name for s in draw.slots)
            print(f"  {day}  {strip:<5} {face['name']:<19} "
                  f"{draw.paper_mm:>3}mm  {names[:40]}"
                  + ("   LEGENDARY" if draw.legendary else ""))

    n = args.days
    print(f"\n{n} simulated mornings, {sum(tier_counts.values())} draws\n")
    print(f"{'':<26}{'actual':>10}{'target':>10}")
    print(f"{'  days with uncommon+':<26}{with_uncommon / n:>9.0%}{T_UNCOMMON_DAY:>10.0%}")
    print(f"{'  days with a rare':<26}{with_rare / n:>9.0%}{T_RARE_DAY:>10.0%}")
    print(f"{'  legendary per year':<26}{legendary / n * 365:>9.1f}{365 / LEGENDARY_ODDS:>10.1f}")
    total = sum(tier_counts.values())
    for tier, target in W.items():
        print(f"{'  draws ' + tier:<26}{tier_counts[tier] / total:>9.0%}"
              f"{target:>10.0%}")

    if len(gaps) > 1:
        spacing = [b - a for a, b in zip(gaps, gaps[1:])]
        print(f"\n  gap between rares: min {min(spacing)}d, "
              f"max {max(spacing)}d, mean {sum(spacing) / len(spacing):.1f}d")

    print(f"\n  persona frequency over {n} days "
          f"(SYSTEM.md 3.6; the same face twice running {repeats} times):")
    pw = {t: float(config.get("personas", t)) for t in PERSONA_TIERS}
    for tier in PERSONA_TIERS:
        print(f"    {tier:<10} {persona_tiers[tier] / n:>9.0%}"
              f"{pw[tier]:>10.0%} target")
    for name, count in per_persona.most_common():
        tier = personas[name].get("rarity", "common")
        print(f"    {name:<22} {tier:<9} {count:>3}  every {n / count:.0f}d")

    print(f"\n  slot frequency over {n} days (recency damping should keep these "
          f"even):")
    for sid, count in per_slot.most_common():
        name = next(s.spec.name for s in slots if s.spec.id == sid)
        print(f"    #{sid:<4} {name:<24} {count:>3}  every {n / count:.0f}d")


if __name__ == "__main__":
    main()
