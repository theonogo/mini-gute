"""Reading the receipts archive - the machine's memory of itself.

Shared by every slot that refers to past mornings: receipt archaeology (113), the
changelog (137), persona continuity (101), tomorrow-predicted (104), and the
conspiracy slot (106), whose "dots" SLOTS.md says come from archaeology.

**Everything here returns statements that are true.** Each pattern is computed
from the receipts table at the moment it is asked for, never remembered or
estimated, so a slot built on it cannot assert a streak that did not happen.
That is the whole value of these slots: the persona may make whatever it likes
of a pattern, but the pattern itself is a fact about the archive, and a reader
who goes and counts will find it holds.

Only rotating sections count towards "most drawn" and similar. The spine prints
every day by design, so "the weather has appeared on every receipt" is true,
trivially true, and not a pattern.
"""

from __future__ import annotations

from collections import Counter
from datetime import date as Date
from typing import Any

ROTATING = {"common", "uncommon", "rare", "legendary"}


def receipts(store: Any, limit: int = 10_000) -> list[dict]:
    """Every recorded receipt, newest first. Empty on any problem."""
    if store is None:
        return []
    try:
        return store.recent_receipts(limit)
    except Exception:  # noqa: BLE001 - an unreadable archive is an empty one
        return []


def _spec(sid: int):
    try:
        from slots.registry import get
        return get(sid).spec
    except (KeyError, ImportError):
        return None


def is_rotating(sid: int) -> bool:
    spec = _spec(sid)
    return spec is not None and spec.tier in ROTATING


def name(sid: int) -> str:
    spec = _spec(sid)
    return spec.name if spec else f"section {sid}"


def ever_printed(store: Any) -> set[int]:
    return {int(s) for r in receipts(store) for s in r.get("slots", [])}


def first_seen(store: Any) -> dict[int, Date]:
    """slot id -> the first morning it ever printed."""
    out: dict[int, Date] = {}
    for row in reversed(receipts(store)):                 # oldest first
        day = Date.fromisoformat(row["day"])
        for sid in row.get("slots", []):
            out.setdefault(int(sid), day)
    return out


def _rare_days(rows: list[dict]) -> list[Date]:
    return [Date.fromisoformat(r["day"]) for r in rows
            if (r.get("rarity") or {}).get("rare", 0)
            or (r.get("rarity") or {}).get("legendary", 0)]


def patterns(store: Any, today: Date, window: int = 30) -> list[str]:
    """True statements about the recent archive, most striking first.

    Returns an empty list when there is too little history for a pattern to mean
    anything - a streak of two out of three receipts is arithmetic, not a trend.
    """
    rows = receipts(store, window)
    if len(rows) < 6:
        return []
    out: list[str] = []
    n = len(rows)

    personas = Counter(r["persona"] for r in rows)
    top, count = personas.most_common(1)[0]
    if count >= 3:
        out.append(f"{top} has written {count} of the last {n} receipts")

    streak = 0
    for row in rows:
        if row["persona"] != rows[0]["persona"]:
            break
        streak += 1
    if streak >= 3:
        out.append(f"the last {streak} receipts in a row came from "
                   f"{rows[0]['persona']}")

    rares = _rare_days(rows)
    if not rares:
        out.append(f"not one rare section has been drawn in {n} mornings")
    else:
        drought = (today - max(rares)).days
        if drought >= 7:
            out.append(f"the last rare section was {drought} days ago")

    counts = Counter(int(s) for r in rows for s in r.get("slots", [])
                     if is_rotating(int(s)))
    if counts:
        sid, seen = counts.most_common(1)[0]
        if seen >= 3:
            out.append(f"{name(sid)} has appeared {seen} times in {n} mornings")

    paper = sum(r.get("paper_mm") or 0 for r in rows)
    if paper:
        out.append(f"{paper / 1000:.1f} metres of paper have been printed in "
                   f"the last {n} mornings")

    cost = sum(r.get("api_cost") or 0 for r in rows)
    if cost:
        out.append(f"the last {n} receipts cost ${cost:.2f} to write")
    return out


def recent_personas(store: Any, exclude: str | None, window: int = 14) -> list[dict]:
    """Other personas from the recent archive: name, count, last appearance."""
    seen: dict[str, dict] = {}
    for row in receipts(store, window):
        persona = row["persona"]
        if persona == exclude:
            continue
        entry = seen.setdefault(persona, {"persona": persona, "count": 0,
                                          "last": row["day"]})
        entry["count"] += 1
    return sorted(seen.values(), key=lambda e: e["last"], reverse=True)
