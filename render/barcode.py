"""CODE39 barcode, drawn at exact pixel widths.

`python-barcode` handles the encoding, which is the part worth getting right -
the spec says CODE39, so it should actually scan, not merely look like stripes.
But its own image writer antialiases, which would leave grey edges for the page
threshold to guess at. So we take the module string and draw the bars ourselves
at whole-pixel widths, giving pure 1-bit output that survives untouched.
"""

import barcode
from PIL import Image, ImageDraw

QUIET_MODULES = 10  # CODE39 wants a quiet zone; 10 modules is the usual minimum


def modules(text: str) -> str:
    """The '1'/'0' module string for `text`, including start/stop characters."""
    code = barcode.get_barcode_class("code39")(text, add_checksum=False)
    return code.build()[0]


def code39(text: str, *, width: int | None = None, module_px: int = 2,
           height: int = 34) -> Image.Image:
    """Render `text` as a 1-bit CODE39 image.

    If `width` is given, the module width is chosen to fit inside it (never
    below 1px, which is the point at which a scanner gives up).
    """
    bits = modules(text)
    total = len(bits) + QUIET_MODULES * 2

    if width is not None:
        module_px = max(1, width // total)

    bar_w = module_px
    img_w = total * bar_w if width is None else width
    img = Image.new("1", (img_w, height), 1)  # 1 = white
    d = ImageDraw.Draw(img)

    # Centre the symbol when it does not divide the target width exactly.
    x = (img_w - (len(bits) + QUIET_MODULES * 2) * bar_w) // 2 + QUIET_MODULES * bar_w
    for bit in bits:
        if bit == "1":
            d.rectangle([x, 0, x + bar_w - 1, height - 1], fill=0)
        x += bar_w
    return img
