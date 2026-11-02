"""QR codes, drawn at whole-pixel module sizes.

The same rule as `render.barcode`: a scanner reads edges, and a code whose
modules land on fractional pixels gets those edges smeared by resampling. So the
module size is an integer and the final image size follows from it, rather than
picking a target size and scaling a code to fit.

**Error correction is set high (H, ~30%).** Thermal paper fades, creases along
the roll, and gets read off a curled strip in bad kitchen light. The extra
modules cost a few millimetres and buy a code that still scans after the receipt
has been in a pocket.

**Never dithered, never thresholded twice.** A QR is already pure black and
white. It is emitted through `img_tag`, which carries the exact-size and
`image-rendering:pixelated` markup that stops the browser resampling it on the
way into the page.
"""

from __future__ import annotations

import qrcode
from PIL import Image

from printer.base import WIDTH_DOTS

# 4 modules is the spec-mandated quiet zone. Scanners are more forgiving than
# that in practice, but the page has no gutters of its own and a code butted
# against a rule fails to acquire.
QUIET = 4
DEFAULT_MODULE = 4          # px per module; 4 is comfortable on this head


def qr_image(payload: str, *, module_px: int = DEFAULT_MODULE,
             max_width: int = WIDTH_DOTS) -> Image.Image:
    """A 1-bit QR of `payload`, sized in whole modules.

    Shrinks the module size rather than scaling the finished image if the code
    would overflow the page - a version-heavy payload with a long URL can get
    large, and resampling it is exactly what must not happen.
    """
    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1, border=QUIET,
    )
    code.add_data(payload)
    code.make(fit=True)
    matrix = code.get_matrix()
    modules = len(matrix)

    while module_px > 1 and modules * module_px > max_width:
        module_px -= 1

    size = modules * module_px
    img = Image.new("1", (size, size), 1)          # 1 = white
    px = img.load()
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if not dark:
                continue
            for dy in range(module_px):
                for dx in range(module_px):
                    px[x * module_px + dx, y * module_px + dy] = 0
    return img


def mailto(address: str, subject: str, body: str = "") -> str:
    """A `mailto:` payload, for the input-channel slots (SYSTEM.md 6).

    Scanning opens the mail app already addressed and titled, so replying costs
    a tap and a sentence. The subject is what routes the reply, so it is not
    decorative - see the routing table in SYSTEM.md.
    """
    from urllib.parse import quote

    query = f"subject={quote(subject)}"
    if body:
        query += f"&body={quote(body)}"
    return f"mailto:{address}?{query}"
