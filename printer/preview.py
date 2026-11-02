"""PNG backend - the development workhorse.

Every layout, persona and slot-mix iteration goes through here. Real paper is
only for end-of-phase verification, because screen previews lie about contrast
but paper is slow.

The image is thresholded exactly as the real backend does, so what you see is
the actual bit pattern the printer would burn - not an approximation of it.
"""

from pathlib import Path

from PIL import Image

from .base import Printer, check_width


class PreviewPrinter(Printer):
    """Writes receipts to PNG instead of paper."""

    def __init__(self, path: str | Path = "preview.png", scale: int = 1,
                 margin: int = 12):
        self.path = Path(path)
        self.scale = scale
        self.margin = margin

    def print_image(self, img: Image.Image) -> None:
        check_width(img)
        bw = img.convert("1")

        # Grey surround so the paper edges are visible; the receipt itself stays
        # pure black and white.
        canvas = Image.new(
            "L",
            (bw.width + self.margin * 2, bw.height + self.margin * 2),
            0xC0,
        )
        canvas.paste(bw.convert("L"), (self.margin, self.margin))

        if self.scale > 1:
            canvas = canvas.resize(
                (canvas.width * self.scale, canvas.height * self.scale),
                Image.NEAREST,  # never smooth - it would hide dropped pixels
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(self.path)
        print(f"preview -> {self.path}  ({bw.width}x{bw.height}px, "
              f"{bw.height / 8:.0f}mm of paper)")
