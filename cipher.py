"""Real ciphers, for the one persona that sends real ones.

The Revolutionary transmits a message every morning and it is enciphered for
actual - not with a row of decorative squiggles, but with a cipher a reader
breaks over breakfast without a pencil. That is the whole trick: the key is
printed on the same page, in plain sight, dressed as a detail of the broadcast,
and the plaintext is upside-down in the answers footer for anyone who cannot be
bothered.

**These are deliberately easy** - pig latin level of decipherable. Word
boundaries are kept rather than hidden, the numbers have no shift at all, and
the fence is printed as a fence you read with your eyes. A
cipher nobody breaks is a picture of a cipher; the point is the five seconds
where you realise you can read it.

Three of them, rotated by the theme's variant so consecutive mornings are not the
same puzzle:

    caesar     letters shifted, words kept whole, the shift printed as the
               station's frequency
    numbers    A is one, read out as a numbers station would, no shift - the
               figures are the alphabet and the page says so
    railfence  three rails, printed AS the zigzag: the letters stand in their
               own columns and you read them down the page

Each returns its own key line, which is the key in character (a frequency, a
schedule, a bird), and a note: one short line of her taking the credit, in her
own voice, which gives away as much as an explanation would.

The shift is the date, so a re-run of a past morning enciphers identically, and
two consecutive mornings never share a key.

    python cipher.py "MEET AT THE USUAL PLACE"     # all three, today
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date as Date

KINDS = ("caesar", "numbers", "railfence")
RAILS = 3


@dataclass(frozen=True)
class Cipher:
    """One enciphered transmission, and everything the page needs to print it."""
    kind: str
    text: str          # the ciphertext, ready to set
    key_line: str      # the key, in character, printed on the page
    note: str          # her explanation of it, which gives the game away
    plain: str         # what it says, for the answers footer


def shift_for(day: Date) -> int:
    """1-25, from the date. Never 0: a shift of nothing is not a cipher.

    The ordinal rather than the day of the month, so the 1st of one month and
    the 1st of the next are not the same key - a correspondent who noticed that
    would only have to break it once.
    """
    return 1 + day.toordinal() % 25


def _words(text: str) -> list[str]:
    """The message as words of letters alone. Punctuation is dropped rather
    than enciphered: a comma survives every cipher here untouched and hands a
    reader the sentence's shape for free."""
    return ["".join(c for c in w if c.isalpha()).upper()
            for w in text.split() if any(c.isalpha() for c in w)]


def _caesar(word: str, shift: int) -> str:
    return "".join(chr((ord(c) - 65 + shift) % 26 + 65) for c in word)


def _fence(letters: str, rails: int = RAILS) -> str:
    """The zigzag, drawn. Each letter stands in its own column on the rail it
    falls on, and the reader takes the columns left to right.

    Printed rather than read off in rows, which is the difference between a
    puzzle and a chore: the shape on the paper IS the method, so nobody has to
    be told how a rail fence works to get the message out of one.
    """
    rows = [[" "] * len(letters) for _ in range(rails)]
    rail, step = 0, 1
    for i, ch in enumerate(letters):
        rows[rail][i] = ch
        if rail == 0:
            step = 1
        elif rail == rails - 1:
            step = -1
        rail += step
    return "\n".join("".join(r).rstrip() for r in rows)


# What she adds after the key. Her own voice, first person, and SHORT - the
# cipher explains itself, so the note is her taking the credit. Three per
# cipher, picked by date.
_NOTES = {
    "caesar": (
        "the frequency is the key. that was me.",
        "shift back by the decimal. elegant, and mine.",
        "hiding it in plain sight was the clever part.",
    ),
    "numbers": (
        "a is one. simple things do not break.",
        "figures sound like weather on the air. my idea.",
        "they are listening to this and hearing nothing.",
    ),
    "railfence": (
        "read down the columns. the shape is the method.",
        "three rails, like the bird. i named it.",
        "best thing this cell ever came up with. mine.",
    ),
}


def encipher(plain: str, day: Date, kind: str) -> Cipher | None:
    """Encipher one message. `None` if there is nothing enciphrable in it.

    The plaintext keeps its spaces and punctuation for the answers footer.
    """
    words = _words(plain)
    if sum(len(w) for w in words) < 8:
        return None
    shift = shift_for(day)
    plain = " ".join(plain.split())
    note = _NOTES[kind][random.Random(f"note:{day.isoformat()}").randrange(3)]

    if kind == "numbers":
        # No shift. The figures are the alphabet and the key line says so - a
        # shifted version is genuinely hard, which is not what this is for.
        return Cipher(
            kind,
            "  /  ".join(" ".join(f"{ord(c) - 64:02d}" for c in w) for w in words),
            "STATION NIGHTJAR · A IS ONE · DO NOT ACKNOWLEDGE",
            note, plain)

    if kind == "railfence":
        return Cipher(
            kind, _fence("".join(words)),
            f"THREE SWALLOWS OVER THE YARD · 6.{shift:02d} MC/S",
            note, plain)

    return Cipher(
        "caesar", " ".join(_caesar(w, shift) for w in words),
        f"FREQUENCY 6.{shift:02d} MC/S · AS AGREED · BURN AFTER",
        note, plain)


def kind_for(variant: int) -> str:
    return KINDS[variant % len(KINDS)]


if __name__ == "__main__":
    import sys
    message = " ".join(sys.argv[1:]) or "MEET AT THE USUAL PLACE BRING NOTHING"
    today = Date.today()
    print(f"shift {shift_for(today)}\n")
    for k in KINDS:
        c = encipher(message, today, k)
        print(f"--- {k}\n{c.text}\n{c.key_line}\n{c.note}\n{c.plain}\n")
