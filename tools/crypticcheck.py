"""Check every cryptic clue's wordplay actually works (slot 17).

A wrong anagram is invisible on the page. It reads as a perfectly ordinary clue,
costs someone ten minutes, and only reveals itself when they turn the receipt
over to a parse that does not add up. Nobody proofreads their own wordplay
successfully, so it is checked here instead: anagram letters must genuinely
rearrange into the answer, a hidden word must genuinely be hidden in its fodder,
a reversal must genuinely reverse.

The slot already drops anything that fails, so a bad clue never prints. This
tool exists to say WHICH one failed, and to fail loudly when the bank is edited.

    python tools/crypticcheck.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slots.cryptic import CLUES, verify  # noqa: E402


def main() -> int:
    devices = Counter(c.device for c in CLUES)
    bad = [c for c in CLUES if not verify(c)]

    for clue in CLUES:
        mark = "ok  " if verify(clue) else "FAIL"
        print(f"  {mark} [{clue.device:<8}] {clue.answer:<10} {clue.clue}")
        if not verify(clue):
            print(f"       fodder {clue.fodder!r} does not yield {clue.answer!r}")

    print(f"\n{len(CLUES) - len(bad)}/{len(CLUES)} verify   "
          + "  ".join(f"{k} {v}" for k, v in sorted(devices.items())))

    # A bank that is all double definitions passes trivially and is a worse
    # puzzle every day, so the mix is reported and floored.
    checkable = len(CLUES) - devices["double"]
    if checkable < len(CLUES) // 2:
        print("WARNING: fewer than half the clues assert any mechanism.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
