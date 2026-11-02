"""Bake the tarot deck to final 1-bit cards, once.

`prepare_contour` is not cheap - it supersamples, blurs, extracts contours and
binary-searches a per-card threshold. Doing that at 07:00 to a 700px colour JPEG,
every time the tarot slot draws, is work we can do once and commit.

Baking also makes the deck *reviewable*: what prints is a file you can open,
not the output of a pipeline that might drift when a default changes.

    python tools/baketarot.py            # bake any card that is missing
    python tools/baketarot.py --force    # re-bake everything
    python tools/baketarot.py --check    # report only, change nothing

Source scans stay in `assets/tarot/source/` as the archive. They are already in
git history, so removing them would save nothing on clone size, and keeping them
means the deck can be re-baked when CARD_W or the contour defaults change.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from render import ink_fraction, prepare_contour  # noqa: E402
from slots.tarot import CARD_W, MAJOR, _slug  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "tarot" / "source"
DEST = ROOT / "assets" / "tarot"


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-bake existing cards")
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()

    if not SRC.exists():
        raise SystemExit(f"no source scans at {SRC} - run tools/gettarot.py first")

    baked = missing = skipped = 0
    total_bytes = 0

    for name, _numeral, _meaning in MAJOR:
        slug = _slug(name)
        src = SRC / f"{slug}.jpg"
        dst = DEST / f"{slug}.png"

        if not src.exists():
            print(f"  MISSING SOURCE  {slug}")
            missing += 1
            continue

        # A baked card at the wrong width is stale, not done. Without this the
        # deck silently keeps its old size when CARD_W changes, and the only
        # symptom is a card that looks slightly wrong on paper weeks later.
        stale = dst.exists() and Image.open(dst).width != CARD_W

        if dst.exists() and not stale and not (args.force or args.check):
            total_bytes += dst.stat().st_size
            skipped += 1
            continue

        card = prepare_contour(Image.open(src), CARD_W)
        ink = ink_fraction(card, 128)

        if args.check:
            state = "baked" if dst.exists() else "NOT BAKED"
            print(f"  {slug:<18} {card.width}x{card.height}  ink {ink:.3f}  {state}")
            continue

        card.save(dst, optimize=True)
        size = dst.stat().st_size
        total_bytes += size
        baked += 1
        print(f"  {slug:<18} {card.width}x{card.height}  ink {ink:.3f}  "
              f"{size / 1024:.0f}KB")

    if args.check:
        return

    src_bytes = sum(p.stat().st_size for p in SRC.glob("*.jpg"))
    print(f"\nbaked {baked}, skipped {skipped}, missing {missing}")
    print(f"deck: {total_bytes / 1024:.0f}KB baked "
          f"(source archive {src_bytes / 1024 / 1024:.1f}MB)")


if __name__ == "__main__":
    main()
