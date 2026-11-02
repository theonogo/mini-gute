"""Printer backends."""

from .base import DOTS_PER_MM, WIDTH_DOTS, Printer
from .preview import PreviewPrinter

__all__ = ["Printer", "PreviewPrinter", "WIDTH_DOTS", "DOTS_PER_MM", "get_printer"]


def get_printer(target: str = "preview", **kwargs) -> Printer:
    """Return a backend by name.

    'usb' is imported lazily so the project still runs, for previews, on a
    machine with no pywin32.
    """
    if target == "preview":
        return PreviewPrinter(**kwargs)
    if target == "usb":
        from .usbwin import UsbWinPrinter
        return UsbWinPrinter(**kwargs)
    raise ValueError(f"unknown printer target {target!r} (want 'preview' or 'usb')")
