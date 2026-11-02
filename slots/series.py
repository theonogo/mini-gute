"""The series engine - SYSTEM.md 5.

A series is a picture assembled one printed tile at a time: the growing city map
(62), and the jigsaw (60) when it is built.

  * **One series runs at a time.** A series slot drawn while another is running
    drops out of the day.
  * **Rare to start, then every morning until done.** The first tile arrives
    through an ordinary rare draw; each later tile pins itself to the next day,
    so a running series never has to win the draw again.
  * **A three-week cooldown** after one finishes, before any can begin.
  * **They alternate**, when there is more than one to alternate between.

State lives in the store under `series_engine`. Only a real morning starts,
advances, pins or finishes anything - a `--date` simulation reads the state and
prints what it finds without consuming a tile. A rerun of the same morning
reprints the same tile.

Subclasses give the number of tiles and draw one; this class decides which.
"""

from __future__ import annotations

from datetime import date as Date, timedelta
from typing import Any

from .base import Context, Slot, SlotResult

NAMESPACE = "series_engine"
COOLDOWN_DAYS = 21


class SeriesSlot(Slot):
    """A slot that prints one tile of a larger picture per morning."""

    def tiles(self) -> int:
        raise NotImplementedError

    def begin(self, ctx: Context) -> dict:
        """Fresh per-series data (e.g. where the map is centred). Stored."""
        return {}

    def tile(self, ctx: Context, n: int, data: dict) -> SlotResult | None:
        """Tile `n` (1-based) of `self.tiles()`."""
        raise NotImplementedError

    # --- the engine -----------------------------------------------------------
    def _state(self, ctx: Context) -> dict:
        if ctx.store is None:
            return {}
        try:
            return ctx.store.fetch(NAMESPACE, "state", {}) or {}
        except Exception:  # noqa: BLE001 - unreadable state is no series
            return {}

    def _save(self, ctx: Context, state: dict) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        try:
            ctx.store.put(NAMESPACE, "state", state)
        except Exception:  # noqa: BLE001
            pass

    def _pin(self, ctx: Context, day: Date) -> None:
        if ctx.store is None or not ctx.shared.get("real_morning"):
            return
        from selection import pin
        pin(ctx.store, self.spec.id, day)

    def _others(self) -> bool:
        from .registry import all_slots
        return any(isinstance(s, SeriesSlot) and s.spec.id != self.spec.id
                   for s in all_slots())

    def fetch(self, ctx: Context) -> SlotResult | None:
        state = self._state(ctx)
        today = ctx.date.isoformat()
        active: dict[str, Any] | None = state.get("active")

        if active and active.get("slot") != self.spec.id:
            return None                                   # another is running

        if active:
            rerun = active.get("day") == today
            n = int(active["done"]) + (0 if rerun else 1)
            # Draw first, commit after: a tile that cannot be drawn today (no
            # network, no cache) is printed tomorrow, not silently skipped.
            result = self.tile(ctx, n, active.get("data", {}))
            if result is None or rerun:
                return result
            active = {**active, "done": n, "day": today}
            if n >= self.tiles():
                self._save(ctx, {"active": None, "last": self.spec.id,
                                 "finished": active,
                                 "cooldown_until": (ctx.date + timedelta(
                                     days=COOLDOWN_DAYS)).isoformat()})
            else:
                self._save(ctx, {**state, "active": active})
                self._pin(ctx, ctx.date + timedelta(days=1))
            return result

        finished = state.get("finished") or {}
        if finished.get("slot") == self.spec.id and finished.get("day") == today:
            return self.tile(ctx, int(finished["done"]), finished.get("data", {}))
        if state.get("cooldown_until", "") > today:
            return None
        if state.get("last") == self.spec.id and self._others():
            return None                                   # the other one's turn
        data = self.begin(ctx)
        result = self.tile(ctx, 1, data)
        if result is not None:
            self._save(ctx, {**state, "active": {"slot": self.spec.id, "done": 1,
                                                 "day": today, "data": data}})
            self._pin(ctx, ctx.date + timedelta(days=1))
        return result
