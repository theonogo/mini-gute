"""The selection engine - SYSTEM.md section 4.

Decides what lands each morning. Four mechanisms, in the order they apply:

**Tier weights, per draw.** 50% common, 37% uncommon, 13% rare, over the three
to five draws a day set by `rarity.draws_min`/`draws_max`. They are coupled to
that count - more draws is more chances at a rare, so raising it moves the felt
rarity without a weight changing. Recompute rather than eyeball (SYSTEM.md 4).

**Recency damping, not a shuffle bag.** A slot that just printed drops to 0.1x
weight and recovers on a smooth curve. It is never banned - a repeat inside a
week stays possible, just unlikely. A strict bag would make the rotation feel
mechanical, which is the failure mode on the other side.

**Legendary is a separate roll**, 1 in 25, outside the tier mix. Decided by
random.org where reachable so the receipt can honestly say the roll came from
atmospheric noise, and silently by the local PRNG when it is not.

**Budget fitting is last.** A draw that does not fit the remaining paper is
skipped rather than shrunk - a slot's paper cost is part of its design. What it
fits into is the budget MINUS a reserve for the spine: the spine prints every
day and is never drawn, so it is not something the engine can choose to leave
out, and without the reserve a full draw on top of it fails the render's
budget check.
"""

from __future__ import annotations

import math
import random
import urllib.request
from dataclasses import dataclass, field
from datetime import date as Date
from typing import Any

import config
from slots.base import Slot
from sources.http import UA

# Slots that refer to the archive. Ineligible until there is an archive to refer
# to (SYSTEM.md 10.4) - on a cold start the machine should not pretend to a past.
HISTORY_DEPENDENT = {101, 102, 104, 113, 137, 139}
RECEIPTS_BEFORE_HISTORY = 14

# Slots that hand you a pen: blank boxes, ruled lines, a scale to circle, empty
# comic panels. Any one of them is a good morning. Three of them is a worksheet,
# and a receipt that mostly asks you to fill it in stops being something you
# read. This is the one place the engine knows anything about content, and it
# earns that by preventing a failure the tier weights cannot see - the four are
# spread across the tiers, so nothing else in the draw correlates them.
ANALOG = {48, 49, 50, 87}
MAX_ANALOG = 2

# Pinned slots - the foundation of every series (SYSTEM.md 5). A slot that has
# started something it must finish tomorrow - day two of a recipe, the next part
# of a story, the next jigsaw tile - pins itself to that date, and the engine
# prints it that day regardless of tier or recency. Without this nothing can be
# continued, because every morning is drawn independently.
PIN_NAMESPACE = "series"
PIN_KEY = "pinned"


def pin(store: Any, slot_id: int, day: Date) -> None:
    """Promise that `slot_id` prints on `day`."""
    if store is None:
        return
    pins = [p for p in (store.fetch(PIN_NAMESPACE, PIN_KEY, []) or [])
            if p.get("day", "") >= Date.today().isoformat()]
    entry = {"slot": slot_id, "day": day.isoformat()}
    if entry not in pins:
        pins.append(entry)
    store.put(PIN_NAMESPACE, PIN_KEY, pins)


def pinned_for(store: Any, day: Date) -> set[int]:
    if store is None:
        return set()
    try:
        pins = store.fetch(PIN_NAMESPACE, PIN_KEY, []) or []
    except Exception:  # noqa: BLE001 - a corrupt pin list must not stop a print
        return set()
    return {int(p["slot"]) for p in pins if p.get("day") == day.isoformat()}


TIERS = ("common", "uncommon", "rare")


@dataclass
class Draw:
    slots: list[Slot] = field(default_factory=list)
    legendary: bool = False
    legendary_odds: int = 25
    roll_source: str = "prng"
    paper_mm: int = 0
    skipped_for_budget: list[int] = field(default_factory=list)

    @property
    def tiers(self) -> list[str]:
        return [s.spec.tier for s in self.slots]


def recency_multiplier(days: float | None, suppression: float, tau: float) -> float:
    """1.0 for never-seen, 0.1 the day after printing, recovering over ~tau."""
    if days is None:
        return 1.0
    return 1.0 - suppression * math.exp(-max(0.0, days) / tau)


def _true_random_int(ceiling: int) -> tuple[int, str]:
    """A roll from random.org, falling back to the local PRNG.

    The fallback is silent by design: a receipt that cannot reach the internet
    should still print, and the only thing lost is the claim about atmospheric
    noise - which is why the source is returned rather than assumed.
    """
    url = ("https://www.random.org/integers/?num=1&min=1&max="
           f"{ceiling}&col=1&base=10&format=plain&rnd=new")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=6) as r:
            return int(r.read().decode().strip()), "atmospheric noise"
    except Exception:  # noqa: BLE001 - any failure means fall back and move on
        return random.randint(1, ceiling), "prng"


def eligible(slots: list[Slot], receipt_count: int) -> list[Slot]:
    """Rotating slots that may be drawn today."""
    out = []
    for slot in slots:
        if slot.spec.tier not in TIERS:
            continue  # spine, occasional and legendary are not drawn here
        if slot.spec.id in HISTORY_DEPENDENT and receipt_count < RECEIPTS_BEFORE_HISTORY:
            continue
        out.append(slot)
    return out


def select(day: Date, slots: list[Slot], *, store: Any = None,
           budget_mm: int | None = None, offline: bool = False) -> Draw:
    """Draw today's rotating slots."""
    weights = {t: float(config.get("rarity", t, default=w))
               for t, w in (("common", .50), ("uncommon", .37), ("rare", .13))}
    lo = int(config.get("rarity", "draws_min", default=3))
    hi = int(config.get("rarity", "draws_max", default=6))
    odds = int(config.get("rarity", "legendary_odds", default=25))
    suppression = float(config.get("recency", "suppression", default=0.9))
    tau = float(config.get("recency", "tau_days", default=10))
    if budget_mm is not None:
        budget = budget_mm
    else:
        budget = int(config.get("paper", "budget_mm", default=1030))
        budget -= int(config.get("paper", "spine_reserve_mm", default=480))

    rng = random.Random(f"select:{day.isoformat()}")
    pool = eligible(slots, store.receipt_count() if store else 0)
    seen = store.last_seen(day) if store else {}

    draw = Draw(legendary_odds=odds)

    # Legendary first: it can change what else fits.
    if not offline:
        roll, source = _true_random_int(odds)
        draw.roll_source = source
    else:
        roll, draw.roll_source = rng.randint(1, odds), "prng"
    draw.legendary = roll == 1

    target = rng.randint(lo, hi)
    remaining = budget
    chosen: list[Slot] = []

    # Promises first. A pinned slot is a continuation, not a draw: it is added on
    # top of the day's normal draw rather than taking one of them, so
    # being mid-recipe does not cost the morning a section it would otherwise
    # have had. It still spends paper, and is taken out of the pool so the draw
    # cannot pick it a second time.
    promised = pinned_for(store, day)
    for slot in slots:
        if slot.spec.id in promised:
            chosen.append(slot)
            remaining -= slot.spec.paper_mm
    pool = [s for s in pool if s.spec.id not in promised]
    target += len(chosen)

    for _ in range(target * 4):  # bounded: some picks are skipped, not retried
        if len(chosen) >= target:
            break
        available = [s for s in pool if s not in chosen]
        if not available:
            break

        tier = rng.choices(TIERS, weights=[weights[t] for t in TIERS])[0]
        candidates = [s for s in available if s.spec.tier == tier]
        if sum(s.spec.id in ANALOG for s in chosen) >= MAX_ANALOG:
            candidates = [s for s in candidates if s.spec.id not in ANALOG]
        if not candidates:
            continue

        scored = []
        for slot in candidates:
            last = seen.get(slot.spec.id)
            days = (day - last).days if last else None
            scored.append(recency_multiplier(days, suppression, tau))
        if not any(scored):
            continue
        pick = rng.choices(candidates, weights=scored)[0]

        if pick.spec.paper_mm > remaining:
            draw.skipped_for_budget.append(pick.spec.id)
            pool = [s for s in pool if s is not pick]  # will not fit today
            continue

        chosen.append(pick)
        remaining -= pick.spec.paper_mm

    draw.slots = sorted(chosen, key=lambda s: s.spec.id)
    draw.paper_mm = budget - remaining
    return draw


def miss_line(draw: Draw) -> str:
    """The printed near-miss. Showing the failure is what makes a hit land."""
    verdict = "YES" if draw.legendary else "NO"
    return f"LEGENDARY ROLL 1/{draw.legendary_odds} - {verdict}"
