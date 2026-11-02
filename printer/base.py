"""Printer backend interface.

Every backend takes a PIL image and puts it somewhere: real paper, a PNG, a
byte log. `main.py` never knows which one it has.
"""

from abc import ABC, abstractmethod

from PIL import Image

# Epson TM-T20II, 203dpi (8 dots/mm), with an 80mm roll fitted.
#
# 576 dots = 72mm, the head's native full width, leaving ~4mm unprintable each
# side of an 80mm roll. That margin is the design margin (see SYSTEM.md): pages
# run full bleed to 576 and add no gutters of their own. A 58mm roll on the
# same printer is 416 (`tools/widthprobe.py` finds the real limit).
#
# MUST BE A MULTIPLE OF 8. Rows pack into whole bytes; a width that is not a
# multiple of 8 carries padding bits, and getting the stride wrong prints as
# diagonal smear rather than as an obvious error. check_width() enforces it.
WIDTH_DOTS = 576
DOTS_PER_MM = 8


class Printer(ABC):
    """A destination for a rendered receipt."""

    @abstractmethod
    def print_image(self, img: Image.Image) -> None:
        """Emit a receipt. `img` must be WIDTH_DOTS wide; any height."""

    def close(self) -> None:
        """Release resources. Safe to call more than once."""


def check_width(img: Image.Image) -> None:
    """Reject images that are not exactly the printable width.

    Silently rescaling would be worse than failing: a receipt that is 3% narrow
    looks fine on screen and wrong on paper, every morning, until someone
    notices.
    """
    if img.width != WIDTH_DOTS:
        raise ValueError(
            f"image is {img.width}px wide, printer needs exactly {WIDTH_DOTS}px"
        )
    if WIDTH_DOTS % 8:
        raise ValueError(
            f"WIDTH_DOTS is {WIDTH_DOTS}, which is not a multiple of 8. Rows "
            "pack into whole bytes; a non-multiple prints as diagonal smear."
        )
