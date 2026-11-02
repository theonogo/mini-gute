"""Image preparation for thermal output.

Photographs are dithered to pure 1-bit **here**, before they ever reach the HTML
page. The page-wide threshold that happens at render time then leaves them
untouched, because every pixel is already 0 or 255. This is the whole of the
"threshold text, dither photos, never in the same pass" rule.

Two things will silently destroy a dither, so both are handled for you by
`img_tag`:

  * the browser resampling the image to a different size
  * the browser smoothing it while scaling

Atkinson rather than Floyd-Steinberg: it diffuses only 6/8 of the error, which
throws away some tonal accuracy in exchange for contrast. On a 203dpi thermal
head that trade is worth taking - Floyd-Steinberg mid-greys turn to mud.
"""

import base64
import io

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# (dx, dy) neighbours that receive 1/8 of the error each.
_ATKINSON = ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2))


def atkinson(img: Image.Image, threshold: int = 128) -> Image.Image:
    """Dither a greyscale image to pure black and white."""
    buf = np.asarray(img.convert("L"), dtype=np.float32).copy()
    height, width = buf.shape

    for y in range(height):
        for x in range(width):
            old = buf[y, x]
            new = 255.0 if old >= threshold else 0.0
            buf[y, x] = new
            err = (old - new) / 8.0
            if err == 0.0:
                continue
            for dx, dy in _ATKINSON:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    buf[ny, nx] += err

    return Image.fromarray(np.clip(buf, 0, 255).astype(np.uint8), "L").convert("1")


def fit(img: Image.Image, width: int, max_height: int | None = None) -> Image.Image:
    """Resize to `width`, preserving aspect. Resampling happens before dithering."""
    if img.width != width:
        height = max(1, round(img.height * width / img.width))
        img = img.resize((width, height), Image.LANCZOS)
    if max_height and img.height > max_height:
        img = img.crop((0, 0, img.width, max_height))
    return img


def contrast_score(img: Image.Image) -> float:
    """Rough 0-1 measure of how much tonal range an image has.

    Low-contrast photographs dither to mud. Slots that pick images from a folder
    should skip anything scoring poorly rather than print a grey rectangle - see
    the jigsaw source rules in SLOTS.md.
    """
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    return float(arr.std() / 64.0)


def data_uri(img: Image.Image) -> str:
    """PNG data URI. The image should already be 1-bit."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def img_tag(img: Image.Image, alt: str = "") -> str:
    """An <img> that the browser cannot resample or smooth.

    Explicit pixel dimensions plus `image-rendering: pixelated` are both
    required. Without them the dither is destroyed and the photo prints as grey
    fuzz - which looks like a printer problem and is not.
    """
    return (
        f'<img src="{data_uri(img)}" alt="{alt}" '
        f'width="{img.width}" height="{img.height}" '
        f'style="image-rendering:pixelated;display:block;'
        f'width:{img.width}px;height:{img.height}px">'
    )


def prepare(source: Image.Image, width: int) -> Image.Image:
    """Full PHOTOGRAPH pipeline: fit to width, then dither.

    For line art - woodcuts, engravings, diagrams, scanned prints - use
    `prepare_line_art` instead. Dithering line art is a mistake: it converts
    solid ink into grey texture and throws away the crispness that made it worth
    printing.
    """
    return atkinson(fit(source, width))


def ink_fraction(img: Image.Image, cut: int) -> float:
    """Proportion of pixels that would print black at this threshold."""
    return float((np.asarray(img.convert("L")) < cut).mean())


def cut_for_ink(img: Image.Image, target: float) -> int:
    """Binary-search the threshold that lands nearest `target` ink coverage.

    A fixed threshold cannot serve a whole deck. Marseille cards carry flat
    colour fills, and how much dark ink a card has varies enormously - the
    Emperor is mostly line, La Force has a large solid dress. At a fixed cut the
    dress floods to a black mass while the Emperor is perfect. Targeting a
    coverage instead normalises them, because what we actually want is constant
    *apparent density*, not a constant grey value.
    """
    grey = img.convert("L")
    lo, hi = 16, 244
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ink_fraction(grey, mid) > target:
            hi = mid
        else:
            lo = mid
    return lo


def prepare_line_art(source: Image.Image, width: int, *,
                     cut: int | None = None, target_ink: float = 0.22,
                     autolevel: bool = True) -> Image.Image:
    """Full LINE ART pipeline: level, fit, threshold. No dithering.

    By default the threshold is chosen per image to hit `target_ink` coverage
    (see `cut_for_ink`). Pass an explicit `cut` to override.

    Whatever value is used, it is NOT the page threshold. That exists to rescue
    antialiased type; line art wants far less ink. Two knobs, two problems - do
    not unify them.

    `autolevel` matters for old scans: 260-year-old paper is mid-grey, and
    without it the whole sheet falls below the cut and prints as a black
    rectangle.
    """
    img = source.convert("L")
    if autolevel:
        # Small cutoff so a few dark specks do not set the black point.
        img = ImageOps.autocontrast(img, cutoff=(1, 2))
    img = fit(img, width)
    if cut is None:
        cut = cut_for_ink(img, target_ink)
    return img.point(lambda v: 255 if v >= cut else 0).convert("1")


def prepare_contour(source: Image.Image, width: int, *, weight: int | None = None,
                    target_ink: float = 0.33, blur: float = 0.6,
                    supersample: int = 2) -> Image.Image:
    """Extract line art from a COLOURED illustration, then threshold it.

    For decks like Rider-Waite-Smith: heavy black outlines under flat colour.
    A plain threshold cannot help - the colour fields are mid-grey, so they
    either flood black or vanish. Contour extraction recovers the outlines the
    illustrator actually drew.

    The two knobs are coupled, which is the non-obvious part:

      `blur`   suppresses scan grain in flat areas BEFORE contouring. Without
               it the filter reads film grain as line work and large flat
               regions (a cloak, a storm sky) come out as noise.
      `weight` is the final threshold. Higher means more ink and heavier line.

    Blur is what buys headroom for weight. Raw at weight 200 is a black mess;
    with grain suppressed, that extra weight lands on real line work instead.
    Measured on paper across the whole deck; the conclusions are about grain and
    line weight, not size, so they hold at any card width.

    A light Gaussian beats a median kernel here. Median replaces each pixel with
    a neighbourhood value and flattens fine hatching; a small blur only softens
    grain enough for the contour filter to ignore it.

    `weight` defaults to None, meaning it is chosen per image to hit
    `target_ink`. A FIXED weight cannot serve a deck: at a flat 200 the RWS
    majors ranged from 28% ink (Hermit) to 55% (Temperance), and the heavy end
    was muddy. Same failure as a fixed threshold on line art - constant
    *apparent density* is what we actually want, not a constant parameter.
    """
    grey = ImageOps.autocontrast(source.convert("L"), cutoff=(1, 2))
    grey = fit(grey, width * supersample)
    if blur:
        grey = grey.filter(ImageFilter.GaussianBlur(radius=blur))
    grey = grey.filter(ImageFilter.CONTOUR).filter(ImageFilter.SMOOTH)
    grey = ImageOps.autocontrast(grey)
    grey = fit(grey, width)
    if weight is None:
        weight = cut_for_ink(grey, target_ink)
    return grey.point(lambda v: 255 if v >= weight else 0).convert("1")
