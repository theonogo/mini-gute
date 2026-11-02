"""Harvest Goodreads quotations for the read list into data/quotes.json.

Slot 25 reads from that cache, so the morning run almost never has to touch
Goodreads. This fills it, slowly.

**Slowly is the whole design.** Goodreads sits behind AWS WAF, which served a bot
challenge after five requests in about thirty seconds when this was first
tried. So the harvest is a trickle: one book, then a long wait - two minutes by
default - then the next. A hundred books takes a few hours, which is fine,
because it only has to happen once a season.

**It stops the moment it is challenged, and does not come back for hours.** A
challenge records a cooldown in the cache, and both this tool and the morning
slot respect it. The tool does not retry, does not wait the challenge out in a
loop, and does nothing to get past it. Run it again later and it resumes from
the first book it has not got, skipping everything already cached.

    python tools/harvestquotes.py              # the whole list, 120s apart
    python tools/harvestquotes.py --limit 5    # just a few
    python tools/harvestquotes.py --gap 300    # gentler still
    python tools/harvestquotes.py --status     # what is cached, what is not
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slots.book_quote import reading_list  # noqa: E402
from sources import goodreads as gr  # noqa: E402


def status() -> int:
    cache = gr.load_cache()
    books = reading_list()
    have = [t for t, _ in books if (cache["books"].get(t) or {}).get("quotes")]
    none = [t for t, _ in books if t in cache["books"]
            and not cache["books"][t].get("quotes")]
    todo = [t for t, _ in books if t not in cache["books"]]
    total = sum(len(cache["books"][t]["quotes"]) for t in have)
    print(f"{len(have)} books with quotes ({total} quotations), "
          f"{len(none)} with none on Goodreads, {len(todo)} not yet fetched.")
    if gr.cooling_down(cache):
        print(f"Cooling down after a bot challenge until "
              f"{cache['challenged_until']}.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=120,
                    help="seconds between books (default 120)")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after this many books (0 = all)")
    ap.add_argument("--refresh", action="store_true",
                    help="refetch books whose cache is a season old")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if not reading_list():
        print("No reading list. Copy data/books.example.txt to data/books.txt "
              "and fill it in.")
        return 1
    if args.status:
        return status()

    cache = gr.load_cache()
    if gr.cooling_down(cache):
        print(f"Goodreads challenged this client; cooling down until "
              f"{cache['challenged_until']}. Not sending anything.")
        return 1

    todo = [(t, a) for t, a in reading_list()
            if t not in cache["books"]
            or (args.refresh and gr.is_stale(cache["books"][t]))]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo)} books to fetch, {args.gap:.0f}s apart.")

    fetched = 0
    for i, (title, author) in enumerate(todo):
        if i:
            time.sleep(args.gap)
        stamp = datetime.now().strftime("%H:%M:%S")
        try:
            quotes = gr.refresh(cache, title, author)
        except gr.Challenged:
            print(f"{stamp}  CHALLENGED on {title!r}. Stopping; cooling down "
                  f"until {cache['challenged_until']}.")
            break
        except gr.GoodreadsBroken as exc:
            print(f"{stamp}  broken on {title!r}: {exc}. Stopping.")
            break
        fetched += 1
        print(f"{stamp}  {len(quotes):>2} quotes  {title} - {author}")

    print()
    status()
    return 0 if fetched == len(todo) else 1


if __name__ == "__main__":
    raise SystemExit(main())
