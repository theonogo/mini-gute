"""What the machine actually printed, read back from the store.

The receipts table knows which slots printed and who wore the page; this is the
words. Feedback on a morning ("the joke didn't land", "why that headline") is
checked against it rather than against a re-run, which would draw the same
slots and write different prose.

    python tools/printed.py              the last three mornings
    python tools/printed.py 7            the last seven
    python tools/printed.py 2026-10-28   one morning
    python tools/printed.py --slot 149   one section across every morning kept

Only real mornings are kept (`main.remember`), from 2026-10-29 on. The page as
printed is beside it in `[paths] archive`.
"""

import argparse
import sys
from datetime import date as Date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from data.store import Store  # noqa: E402
from main import PRINTED_TEXT  # noqa: E402


def mornings(store: Store) -> dict[str, dict]:
    """Every kept morning, oldest first."""
    rows = store.db.execute("SELECT key, value FROM kv WHERE ns=? ORDER BY key",
                            (PRINTED_TEXT,)).fetchall()
    return {r["key"]: store.fetch(PRINTED_TEXT, r["key"]) for r in rows}


def show(day: str, page: dict, only: int | None = None) -> None:
    who = page["persona"] + (f" as {page['wears']}" if page.get("wears") else "")
    print(f"=== {day}  {who}"
          + (f"  LEGENDARY: {page['legendary']}" if page.get("legendary") else "")
          + ("" if page.get("narrated") else "  (templated copy)"))
    if only is None:
        for key, line in (page.get("masthead") or {}).items():
            print(f"  [masthead {key}] {line}")
    for s in page["sections"]:
        if only is not None and s["id"] != only:
            continue
        print(f"\n  #{s['id']} {s['name']}  -  {s['head']}")
        for line in (s["body"] or "(no text)").splitlines():
            print(f"    {line}")
        if s.get("fine"):
            print(f"    ({s['fine']})")
    archive = config.path("paths", "archive") / f"{day}.png"
    if archive.exists():
        print(f"\n  page: {archive}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("which", nargs="?", default="3",
                    help="how many recent mornings, or one ISO date")
    ap.add_argument("--slot", type=int, help="one section, every morning kept")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    store = Store(config.path("paths", "cache"))
    kept = mornings(store)
    store.close()
    if not kept:
        print("nothing kept yet - only real mornings from 2026-10-29 on are")
        return 1

    if args.slot is not None:
        for day, page in kept.items():
            if any(s["id"] == args.slot for s in page["sections"]):
                show(day, page, args.slot)
        return 0
    try:
        day = Date.fromisoformat(args.which).isoformat()
    except ValueError:
        for day, page in list(kept.items())[-int(args.which):]:
            show(day, page)
        return 0
    if day not in kept:
        print(f"{day} is not kept")
        return 1
    show(day, kept[day])
    return 0


if __name__ == "__main__":
    sys.exit(main())
