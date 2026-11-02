"""Windows USB printer-class backend.

Autocut is ON by default: the TM-T20II has a cutter (`tools/cuttest.py` finds
which command a printer answers to). A partial cut leaves a small tab so the
receipt stays attached rather than dropping on the floor. Printers without a
cutter ignore GS V, so this is safe to leave on.

USB receipt printers bind to Windows' inbox `usbprint.sys` driver, which exposes
a device interface we can open with CreateFile and write raw bytes to. That
means no print queue, no driver install, no elevation, and no Zadig.

The device path embeds the printer's serial number, so it is enumerated at run
time rather than stored in config. It also disappears the moment the printer is
unplugged, which is why `find_device` returning None is a normal outcome and not
an error.
"""

import ctypes as C
from ctypes import wintypes as W

import win32con
import win32file
from PIL import Image

from . import escpos
from .base import Printer

_setupapi = C.WinDLL("setupapi", use_last_error=True)


class _GUID(C.Structure):
    _fields_ = [
        ("Data1", W.DWORD),
        ("Data2", W.WORD),
        ("Data3", W.WORD),
        ("Data4", C.c_ubyte * 8),
    ]


class _InterfaceData(C.Structure):
    _fields_ = [
        ("cbSize", W.DWORD),
        ("InterfaceClassGuid", _GUID),
        ("Flags", W.DWORD),
        ("Reserved", C.POINTER(W.ULONG)),
    ]


# GUID_DEVINTERFACE_USBPRINT {28d78fad-5a12-11d1-ae5b-0000f803a8c2}
_USBPRINT = _GUID(0x28D78FAD, 0x5A12, 0x11D1,
                  (C.c_ubyte * 8)(0xAE, 0x5B, 0x00, 0x00, 0xF8, 0x03, 0xA8, 0xC2))

_DIGCF_PRESENT = 0x02
_DIGCF_DEVICEINTERFACE = 0x10
_INVALID_HANDLE = C.c_void_p(-1).value

_setupapi.SetupDiGetClassDevsW.restype = C.c_void_p
_setupapi.SetupDiGetClassDevsW.argtypes = [C.POINTER(_GUID), W.LPCWSTR, W.HWND, W.DWORD]
_setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    C.c_void_p, C.c_void_p, C.POINTER(_GUID), W.DWORD, C.POINTER(_InterfaceData)]
_setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    C.c_void_p, C.POINTER(_InterfaceData), C.c_void_p, W.DWORD,
    C.POINTER(W.DWORD), C.c_void_p]
_setupapi.SetupDiDestroyDeviceInfoList.argtypes = [C.c_void_p]

# SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize is 8 on 64-bit, 6 on 32-bit. This is
# a documented Windows quirk: the field is the struct's *declared* size, not the
# allocated buffer size.
_DETAIL_CBSIZE = 8 if C.sizeof(C.c_void_p) == 8 else 6


def list_devices() -> list[str]:
    """Every present USB printer-class device path."""
    handle = _setupapi.SetupDiGetClassDevsW(
        C.byref(_USBPRINT), None, None, _DIGCF_PRESENT | _DIGCF_DEVICEINTERFACE)
    if handle == _INVALID_HANDLE:
        raise OSError(f"SetupDiGetClassDevs failed: {C.get_last_error()}")

    paths: list[str] = []
    try:
        index = 0
        while True:
            iface = _InterfaceData()
            iface.cbSize = C.sizeof(_InterfaceData)
            if not _setupapi.SetupDiEnumDeviceInterfaces(
                    handle, None, C.byref(_USBPRINT), index, C.byref(iface)):
                break
            needed = W.DWORD(0)
            _setupapi.SetupDiGetDeviceInterfaceDetailW(
                handle, C.byref(iface), None, 0, C.byref(needed), None)
            buf = C.create_string_buffer(needed.value)
            C.cast(buf, C.POINTER(W.DWORD))[0] = _DETAIL_CBSIZE
            if _setupapi.SetupDiGetDeviceInterfaceDetailW(
                    handle, C.byref(iface), buf, needed, None, None):
                paths.append(C.wstring_at(C.addressof(buf) + C.sizeof(W.DWORD)))
            index += 1
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(handle)
    return paths


def find_device(match: str | None = None) -> str | None:
    """The device path to print to, or None if no printer is present.

    `match` is a case-insensitive substring of the path, for machines with more
    than one USB printer attached.
    """
    for path in list_devices():
        if match is None or match.lower() in path.lower():
            return path
    return None


class UsbWinPrinter(Printer):
    """Writes ESC/POS to a Windows USB printer-class device."""

    def __init__(self, match: str | None = None, feed_lines: int = 4,
                 autocut: bool = True, partial_cut: bool = True):
        self.match = match
        self.feed_lines = feed_lines
        self.autocut = autocut
        self.partial_cut = partial_cut

    def _open(self):
        path = find_device(self.match)
        if path is None:
            raise RuntimeError(
                "No USB printer found. Check it is plugged in and powered on. "
                "(Windows binds these to usbprint.sys; if the device shows in "
                "Device Manager but not here, it is not printer-class.)")
        return win32file.CreateFile(
            path, win32con.GENERIC_WRITE, 0, None,
            win32con.OPEN_EXISTING, 0, None)

    def print_image(self, img: Image.Image) -> None:
        data = escpos.receipt(img, self.feed_lines, autocut=self.autocut,
                              partial=self.partial_cut)
        handle = self._open()
        try:
            written = 0
            while written < len(data):
                _, n = win32file.WriteFile(handle, data[written:])
                if not n:
                    raise IOError(
                        f"printer stopped accepting data at byte {written} "
                        f"of {len(data)}")
                written += n
        finally:
            win32file.CloseHandle(handle)
