"""Receipt rendering: HTML in, 1-bit bitmap out."""

from .dither import (atkinson, contrast_score, cut_for_ink, data_uri,
                     img_tag, ink_fraction, prepare, prepare_contour,
                     prepare_line_art)
from .page import BUDGET_PX, BudgetExceeded, Renderer, render_once

__all__ = [
    "Renderer", "render_once", "BUDGET_PX", "BudgetExceeded",
    "atkinson", "prepare", "prepare_line_art", "prepare_contour", "img_tag", "data_uri",
    "contrast_score", "cut_for_ink", "ink_fraction",
]
