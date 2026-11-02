"""Assert a QR code survives the render path bit for bit.

A QR that does not scan is worse than no QR: it costs 20mm of paper and looks
like it works. The failure mode is not encoding - the library gets that right -
it is the trip through the page. A browser that resamples the image, or a
threshold applied to something already 1-bit, shifts module edges by a fraction
of a pixel and the code stops acquiring. None of that is visible by eye.

So this does what `tools/rendertest.py` does for photographs: renders a QR into
a real page through Playwright, thresholds it exactly as the morning run would,
finds it in the output, samples it back down to one pixel per module, and
compares against the matrix the encoder produced. Anything other than a perfect
match is a bug in the pipeline, not a tolerance to be tuned.

    python tools/qrtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import qrcode  # noqa: E402

from render import Renderer  # noqa: E402
from render.dither import img_tag  # noqa: E402
from render.qr import QUIET, mailto, qr_image  # noqa: E402

PAYLOADS = [
    "https://en.wikipedia.org/wiki/Toynbee_tiles",
    "https://en.wikipedia.org/wiki/Coober_Pedy",
    mailto("receipts@example.com", "RE: no.0042", "It was the maze again."),
    "https://en.wikipedia.org/wiki/List_of_lists_of_lists",
]

# The rule below the code is not decoration. `Renderer` trims trailing white
# from the page, and a QR's bottom quiet zone IS trailing white - with nothing
# under it, four rows of modules' worth of margin is cropped away and the code
# stops acquiring. On a real receipt something always follows a QR (its own
# caption, the itemization, the footer), so the rule makes this page faithful
# rather than papering over the problem. A slot that ever put a QR last on the
# page would hit this for real.
PAGE = """<!doctype html><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#fff}}
.after{{height:6px;background:#000;margin-top:10px}}</style>
<body>{tag}<div class="after"></div></body>"""


def expected(payload: str) -> np.ndarray:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,
                         box_size=1, border=QUIET)
    code.add_data(payload)
    code.make(fit=True)
    return np.array(code.get_matrix(), dtype=bool)     # True = dark


def locate(page: np.ndarray, size: int) -> np.ndarray:
    """Crop the QR out of the rendered page by its ink bounding box."""
    dark = page == 0
    # Ignore the trailing rule: only the QR's own rows are of interest.
    full_rows = np.where(dark.all(axis=1))[0]
    if full_rows.size:
        dark = dark[:full_rows.min()]
    rows = np.where(dark.any(axis=1))[0]
    cols = np.where(dark.any(axis=0))[0]
    if rows.size == 0:
        raise AssertionError("nothing rendered")
    # The quiet zone is white, so the ink box is inset by exactly QUIET modules
    # on every side. Grow it back to recover the full symbol.
    top, left = rows[0], cols[0]
    module = (rows[-1] - top + 1) / (size - 2 * QUIET)
    pad = round(QUIET * module)
    return page[top - pad:top - pad + round(size * module),
                left - pad:left - pad + round(size * module)]


def sample(crop: np.ndarray, size: int) -> np.ndarray:
    """One pixel per module, taken from each cell's centre."""
    module = crop.shape[0] / size
    out = np.zeros((size, size), dtype=bool)
    for y in range(size):
        for x in range(size):
            cy = int((y + 0.5) * module)
            cx = int((x + 0.5) * module)
            out[y, x] = crop[cy, cx] == 0
    return out


def main() -> int:
    failures = 0
    with Renderer() as renderer:
        for payload in PAYLOADS:
            want = expected(payload)
            size = want.shape[0]
            img = qr_image(payload)
            page = renderer.render(PAGE.format(tag=img_tag(img)))
            got = sample(locate(np.asarray(page.convert("L")), size), size)

            wrong = int((got != want).sum())
            label = payload[:52] + ("..." if len(payload) > 52 else "")
            if wrong:
                print(f"  FAIL  {size}x{size} modules, {wrong} wrong  {label}")
                failures += 1
            else:
                print(f"  ok    {size}x{size} modules, {img.width}px "
                      f"({img.width / 8:.0f}mm)  {label}")

    print()
    if failures:
        print(f"{failures} of {len(PAYLOADS)} QR codes did not survive the page.")
        return 1
    print(f"All {len(PAYLOADS)} QR codes render module-exact through the page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
