"""The persistent cache.

SQLite, one file, created on first use. Two jobs:

  * `kv` - generic namespaced key/value, used for slot cursors (poem position,
    series progress) and for last-known-good source payloads.
  * `receipts` - one row per morning, which later feeds persona continuity, the
    monthly report and receipt archaeology (SYSTEM.md 8).

The last-known-good behaviour is what makes "network off still prints" true:
a source stores every successful fetch, and serves the most recent one back when
the network fails. A day-old forecast is wrong in the details and right about
whether it is winter; a blank page is wrong about everything.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    ns      TEXT NOT NULL,
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    stored  TEXT NOT NULL,
    PRIMARY KEY (ns, key)
);
CREATE TABLE IF NOT EXISTS receipts (
    day         TEXT PRIMARY KEY,
    number      INTEGER NOT NULL,
    persona     TEXT NOT NULL,
    slots       TEXT NOT NULL,   -- json list of slot ids
    rarity      TEXT NOT NULL,   -- json {tier: count}
    paper_mm    INTEGER,
    api_cost    REAL,
    created     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS receipts_number ON receipts(number);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    @classmethod
    def scratch(cls, path: str | Path) -> "Store":
        """An in-memory copy of the store at `path`, for a simulation.

        Reads see everything the real store holds - its caches, its pins, its
        receipts - and writes land in the copy and go when it closes. The
        contact sheet records each simulated morning here, so day two is damped
        by day one the way a real fortnight would be, and the real file is
        opened read-only and never written. A missing file is an empty store.
        """
        store = cls.__new__(cls)
        store.path = Path(path)
        store.db = sqlite3.connect(":memory:")
        if store.path.exists():
            src = sqlite3.connect(store.path.resolve().as_uri() + "?mode=ro",
                                  uri=True)
            try:
                src.backup(store.db)
            finally:
                src.close()
        store.db.row_factory = sqlite3.Row
        store.db.executescript(SCHEMA)
        store.db.commit()
        return store

    # --- generic kv ----------------------------------------------------
    def put(self, ns: str, key: str, value: Any, when: Date | None = None) -> None:
        self.db.execute(
            "INSERT INTO kv (ns, key, value, stored) VALUES (?,?,?,?) "
            "ON CONFLICT(ns, key) DO UPDATE SET value=excluded.value, "
            "stored=excluded.stored",
            (ns, key, json.dumps(value), (when or Date.today()).isoformat()))
        self.db.commit()

    def fetch(self, ns: str, key: str, default: Any = None) -> Any:
        row = self.db.execute(
            "SELECT value FROM kv WHERE ns=? AND key=?", (ns, key)).fetchone()
        return json.loads(row["value"]) if row else default

    def latest(self, ns: str) -> tuple[str, Any] | None:
        """The most recently stored entry in a namespace, or None.

        This is the last-known-good lookup. Ordering is by `stored` then `key`,
        so same-day writes fall back to key order rather than insertion order.
        """
        row = self.db.execute(
            "SELECT key, value FROM kv WHERE ns=? ORDER BY stored DESC, key DESC "
            "LIMIT 1", (ns,)).fetchone()
        return (row["key"], json.loads(row["value"])) if row else None

    # --- receipts ------------------------------------------------------
    def receipt_number_for(self, day: Date) -> int:
        """The serial for `day` - stable across re-runs.

        A day that already has a row keeps its number. Reprinting after a paper
        jam should produce the same receipt, not consume the next serial, which
        is the same reasoning behind seeding slot draws by date.
        """
        row = self.db.execute(
            "SELECT number FROM receipts WHERE day=?", (day.isoformat(),)
        ).fetchone()
        if row:
            return row["number"]
        nxt = self.db.execute("SELECT MAX(number) AS n FROM receipts").fetchone()
        return (nxt["n"] or 0) + 1

    def save_receipt(self, day: Date, number: int, persona: str,
                     slots: list[int], rarity: dict[str, int],
                     paper_mm: int, api_cost: float = 0.0) -> None:
        """Record a printed morning.

        This is what makes the machine have a past: persona continuity, the
        running bit, receipt archaeology, the changelog and the recency damping
        all read this table. Keyed by day, so a re-run replaces rather than
        duplicates.
        """
        from datetime import datetime

        self.db.execute(
            "INSERT INTO receipts (day, number, persona, slots, rarity, "
            "paper_mm, api_cost, created) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET persona=excluded.persona, "
            "slots=excluded.slots, rarity=excluded.rarity, "
            "paper_mm=excluded.paper_mm, api_cost=excluded.api_cost",
            (day.isoformat(), number, persona, json.dumps(slots),
             json.dumps(rarity), paper_mm, api_cost,
             datetime.now().isoformat(timespec="seconds")))
        self.db.commit()

    def last_seen(self, before: Date, within_days: int = 120) -> dict[int, Date]:
        """slot id -> the most recent day it printed. Drives recency damping.

        Derived from the receipts table rather than kept as its own counter, so
        it cannot drift out of step with what actually printed.
        """
        rows = self.db.execute(
            "SELECT day, slots FROM receipts WHERE day < ? ORDER BY day DESC "
            "LIMIT ?", (before.isoformat(), within_days)).fetchall()
        seen: dict[int, Date] = {}
        for row in rows:                       # newest first, so first wins
            when = Date.fromisoformat(row["day"])
            for sid in json.loads(row["slots"]):
                seen.setdefault(int(sid), when)
        return seen

    def personas_last_seen(self, before: Date,
                           within_days: int = 180) -> dict[str, Date]:
        """persona name -> the most recent day it wore the page.

        The persona half of the recency damping. Read from the receipts table
        for the same reason `last_seen` is: a persona that printed is a persona
        that printed, and a separate counter would eventually disagree with the
        paper. The window is longer than the slot one because the pool is
        smaller - sixteen personas means a gap of four months is a real gap, not
        a lost record.
        """
        rows = self.db.execute(
            "SELECT day, persona FROM receipts WHERE day < ? ORDER BY day DESC "
            "LIMIT ?", (before.isoformat(), within_days)).fetchall()
        seen: dict[str, Date] = {}
        for row in rows:                       # newest first, so first wins
            seen.setdefault(row["persona"], Date.fromisoformat(row["day"]))
        return seen

    def has_receipt(self, day: Date) -> bool:
        """Is this day already on file? Guards a preview from overwriting a
        morning that really printed (`ON CONFLICT(day) DO UPDATE`)."""
        return self.db.execute(
            "SELECT 1 FROM receipts WHERE day=?",
            (day.isoformat(),)).fetchone() is not None

    def receipt_count(self) -> int:
        return self.db.execute(
            "SELECT COUNT(*) AS n FROM receipts").fetchone()["n"]

    def paper_mm_total(self) -> int:
        """Every millimetre this machine has printed, as recorded."""
        row = self.db.execute(
            "SELECT COALESCE(SUM(paper_mm), 0) AS mm FROM receipts").fetchone()
        return int(row["mm"])

    def persona_history(self, persona: str) -> dict:
        """How often one persona has printed, how much paper it has spent, and
        when it first appeared.

        The Machine is told this about itself: its awakening is supposed to
        progress with the count, and its paper gauge is only honest if the
        figure behind it is real (`[persona] wants_history`).
        """
        row = self.db.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(paper_mm), 0) AS mm, "
            "MIN(day) AS first FROM receipts WHERE persona=?",
            (persona,)).fetchone()
        return {"appearances": int(row["n"]),
                "paper_mm": int(row["mm"]),
                "first": row["first"],
                "paper_mm_all": self.paper_mm_total()}

    def appearances_before(self, persona: str, day: Date) -> int:
        """How many mornings a persona printed before `day`.

        Strictly before, so a reprint of today counts what the first print
        counted: a persona's daily draw goes round once per appearance
        (`main.rotate`), and a reprint has to draw the same thing.
        """
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM receipts WHERE persona=? AND day<?",
            (persona, day.isoformat())).fetchone()
        return int(row["n"])

    def recent_receipts(self, limit: int = 14) -> list[dict]:
        rows = self.db.execute(
            "SELECT * FROM receipts ORDER BY day DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["slots"] = json.loads(d["slots"])
            d["rarity"] = json.loads(d["rarity"])
            out.append(d)
        return out

    def close(self) -> None:
        self.db.close()
