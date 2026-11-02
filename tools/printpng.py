"""Print a PNG that already exists, usually a saved `--preview`.

Re-running `main.py` would produce a *different* receipt: the slot draws are
seeded by date and would match, but the narrator is not deterministic, so the
prose would change and it would cost another API call. When you want the receipt
you are looking at, print the file rather than regenerating it.

Preview PNGs are decorated - `PreviewPrinter` adds a grey surround and scales up
so the pixels are visible on screen. Both are undone here by detecting the
surround rather than by being told the parameters, so this keeps working if the
preview defaults change.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from printer import get_printer  # noqa: E402
from printer.base import WIDTH_DOTS  # noqa: E402

SURROUND = 0xC0  # PreviewPrinter's grey; never occurs in a 1-bit receipt


def strip_surround(img: Image.Image) -> Image.Image:
    """Crop the preview's grey border, if there is one."""
    arr = np.asarray(img.convert("L"))
    mask = arr != SURROUND
    rows, cols = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return img
    return img.crop((int(cols[0]), int(rows[0]),
                     int(cols[-1]) + 1, int(rows[-1]) + 1))


def to_printable(img: Image.Image, width: int = WIDTH_DOTS) -> Image.Image:
    img = strip_surround(img)
    if img.width != width:
        ratio = img.width / width
        # An integer downscale of a NEAREST upscale is exact - every source
        # block is uniform - so no resampling artefacts to threshold around.
        resample = (Image.NEAREST if ratio == int(ratio) and ratio >= 1
                    else Image.LANCZOS)
        img = img.resize((width, round(img.height / (img.width / width))),
                         resample)
    return img.convert("1")


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default="out/receipt.png")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Image.open(args.path)
    img = to_printable(src)
    print(f"{args.path}: {src.size[0]}x{src.size[1]} -> "
          f"{img.width}x{img.height} ({img.height / 8:.0f}mm)")

    if args.dry_run:
        return
    get_printer("usb").print_image(img)
    print("sent to printer")


if __name__ == "__main__":
    main()
