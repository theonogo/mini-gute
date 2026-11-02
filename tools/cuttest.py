"""Find which cut command this printer answers to.

ESC/POS has several, and support varies by model and by how the cutter is
configured in the printer's memory switches:

    GS V 0        full cut, immediate
    GS V 1        partial cut, immediate
    GS V 65 n     feed n, then full cut
    GS V 66 n     feed n, then partial cut
    ESC i         partial cut (legacy)
    ESC m         full cut (legacy)

"Immediate" cuts are the ones that usually disappoint: the cutter sits ~14mm
above the print head, so a cut with no feed lands in the middle of what was just
printed. The feed variants exist precisely to avoid that.

Each attempt is labelled on paper, so the slips themselves say which worked.
Text mode is used for the labels rather than raster - fewer moving parts when
the thing under test is the printer's command handling.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32con  # noqa: E402
import win32file  # noqa: E402

from printer.usbwin import find_device  # noqa: E402

ATTEMPTS: list[tuple[str, bytes]] = [
    ("1  GS V 0     full, no feed",    b"\x1dV\x00"),
    ("2  GS V 1     partial, no feed", b"\x1dV\x01"),
    ("3  GS V 65 100 feed + full",     b"\x1dV\x41\x64"),
    ("4  GS V 66 100 feed + partial",  b"\x1dV\x42\x64"),
    ("5  ESC i      partial, legacy",  b"\x1bi"),
    ("6  ESC m      full, legacy",     b"\x1bm"),
]


def main() -> None:
    path = find_device()
    if path is None:
        raise SystemExit("no printer found")

    data = bytearray(b"\x1b@")               # init
    data += b"\x1ba\x01CUT TEST\n\x1ba\x00"  # centred title
    data += b"note which slips separate\n\n"

    for label, cmd in ATTEMPTS:
        data += label.encode("ascii") + b"\n"
        data += b"\x1bd\x02"   # a little feed so the label clears the head
        data += cmd
        data += b"\x1bd\x01"

    data += b"\nEND OF CUT TEST\n"
    data += b"\x1bd\x04"

    handle = win32file.CreateFile(path, win32con.GENERIC_WRITE, 0, None,
                                  win32con.OPEN_EXISTING, 0, None)
    try:
        written = 0
        blob = bytes(data)
        while written < len(blob):
            _, n = win32file.WriteFile(handle, blob[written:])
            if not n:
                raise IOError(f"stalled at byte {written}")
            written += n
    finally:
        win32file.CloseHandle(handle)

    print(f"sent {len(data)} bytes, {len(ATTEMPTS)} cut attempts:")
    for label, cmd in ATTEMPTS:
        print(f"  {label:<32} {cmd.hex(' ')}")
    print("\nTell me which numbers actually separated the paper.")


if __name__ == "__main__":
    main()
