"""HTML to 1-bit bitmap.

Compose the receipt as an HTML page at the printer's full width - taken from
`printer.base.WIDTH_DOTS`, never hardcoded - render it in headless Chromium, then
threshold the screenshot to pure black and white. Persona themes are CSS files,
which is the whole reason for choosing a browser over drawing primitives.

The threshold is deliberately a threshold and not a dither: photographs were
already dithered in `dither.py` before being embedded, so every pixel they
contribute is already 0 or 255 and passes through untouched. Text stays crisp.
Dithering here instead would destroy both.
"""

import io

from PIL import Image
from playwright.sync_api import sync_playwright

import config
from printer.base import DOTS_PER_MM, WIDTH_DOTS

# Injected into every page so a template cannot forget it. The margin reset
# matters: the paper's own unprintable edge is the margin (SYSTEM.md 1.2), so
# the document itself must run full bleed.
RESET_CSS = """
  html, body { margin:0; padding:0; background:#fff; color:#000; }
  * { -webkit-font-smoothing: none; text-rendering: geometricPrecision;
      box-sizing: border-box; }
  img { display:block; }
"""

# The daily paper budget in dots, read from `[paper] budget_mm` rather than
# copied: a ceiling below the budget the engine fits to would fail a morning
# the engine called legal. A guard against a runaway render - a slot in a loop,
# an image that failed to scale - not a content limit (CLAUDE.md invariant 3).
# The legendary formats deliberately blow through it - the full short story
# runs 60cm to 3.4m (SYSTEM.md 4.2) - and render with `strict_budget=False`.
BUDGET_PX = int(config.get("paper", "budget_mm", default=1030)) * DOTS_PER_MM

# Measured on paper (tools/thresholdtest.py), then chosen on printed receipts.
#
# An antialiased hairline serif lands as mid-grey. Set the cut too low and the
# stroke falls below it, turns pure white and vanishes, breaking the glyph. Set
# it too high and reversed-out text is eaten by the surrounding ink. The two
# pull against each other and the answer is where they meet: 170 on the
# TM-T20II. Ink behaviour is a property of the specific printhead and does not
# transfer between machines - re-measure on any other printer.
#
# Safe for photographs at any value: they are dithered to pure 0/255 before
# reaching the page, so the byte-identical fidelity check holds regardless.
DEFAULT_THRESHOLD = 170


class BudgetExceeded(ValueError):
    """A receipt rendered taller than the daily budget."""


def _trim_trailing_white(img: Image.Image, keep: int = 0) -> Image.Image:
    """Drop blank rows from the bottom.

    Belt and braces alongside the viewport fit: a template with a trailing
    margin would otherwise feed blank paper. Leading whitespace is kept, since a
    receipt may open with deliberate space (the blank legendary format does).
    """
    import numpy as np

    arr = np.asarray(img.convert("L"))
    ink = np.where((arr < 250).any(axis=1))[0]
    if ink.size == 0:
        return img
    bottom = min(img.height, int(ink[-1]) + 1 + keep)
    return img.crop((0, 0, img.width, bottom))


class Renderer:
    """Reusable headless browser. Launching Chromium is slow; reuse it.

    Use as a context manager:

        with Renderer() as r:
            img = r.render(html)
    """

    def __init__(self, width: int = WIDTH_DOTS,
                 threshold: int = DEFAULT_THRESHOLD):
        self.width = width
        self.threshold = threshold
        self._pw = None
        self._browser = None

    def __enter__(self) -> "Renderer":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def evaluate(self, html: str, script: str):
        """Load `html` at the print width and return `script`'s result.

        For measuring type in the browser that prints it - never in PIL, which
        reads a pixel more generously than Chromium (SYSTEM.md 1.1). Runs once
        the fonts are ready, since a measurement taken against the fallback
        face is a measurement of the wrong font.
        """
        if self._browser is None:
            raise RuntimeError("Renderer used outside its context manager")
        page = self._browser.new_page(
            viewport={"width": self.width, "height": 800}, device_scale_factor=1)
        try:
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            return page.evaluate(script)
        finally:
            page.close()

    def render(self, html: str, *, strict_budget: bool = True,
               threshold: int | None = None, trim: bool = True) -> Image.Image:
        """Render an HTML document to a 1-bit image `self.width` wide.

        `threshold` overrides the instance default for one render - used by
        `tools/thresholdtest.py` to sweep values without relaunching Chromium.

        `trim=False` keeps trailing blank space. Ordinarily that space is a
        template margin feeding blank paper, and is cut. For a legendary format
        the blank space is the design - "blank but for one line, dead centre"
        has no centre once everything below the line is trimmed away.
        """
        if self._browser is None:
            raise RuntimeError("Renderer used outside its context manager")

        page = self._browser.new_page(
            viewport={"width": self.width, "height": 800},
            device_scale_factor=1,  # 1 CSS px == 1 printer dot. Never change.
        )
        try:
            page.set_content(html, wait_until="load")
            page.add_style_tag(content=RESET_CSS)
            page.evaluate("document.fonts.ready")
            # A full_page screenshot is never shorter than the viewport, so a
            # short receipt would come back padded with blank paper. Shrink the
            # viewport to the content first.
            content_h = page.evaluate(
                "Math.ceil(document.documentElement.getBoundingClientRect().height)")
            page.set_viewport_size(
                {"width": self.width, "height": max(1, int(content_h))})
            shot = page.screenshot(full_page=True, type="png")
        finally:
            page.close()

        img = Image.open(io.BytesIO(shot)).convert("L")
        if trim:
            img = _trim_trailing_white(img)

        if img.width != self.width:  # belt and braces; should never fire
            img = img.crop((0, 0, self.width, img.height))

        if img.height > BUDGET_PX:
            msg = (f"receipt is {img.height}px ({img.height / 8:.0f}mm), over the "
                   f"{BUDGET_PX}px budget")
            if strict_budget:
                raise BudgetExceeded(msg)
            print("WARNING:", msg)

        cut = self.threshold if threshold is None else threshold
        return img.point(lambda v: 255 if v >= cut else 0).convert("1")


def render_once(html: str, **kwargs) -> Image.Image:
    """Convenience for one-off renders. Launches and tears down a browser."""
    with Renderer(**{k: v for k, v in kwargs.items()
                     if k in ("width", "threshold")}) as r:
        return r.render(html, strict_budget=kwargs.get("strict_budget", True))
