"""macOS-specific process and branding when running under the Python interpreter."""

from __future__ import annotations

import sys
from ctypes import CDLL, c_char_p


def configure_branding(app_name: str) -> None:
    """Set menu bar / Dock label to *app_name* instead of the Python runtime."""
    if sys.platform != "darwin":
        return
    set_process_name(app_name)
    _set_main_bundle_display_name(app_name)


def set_process_name(name: str) -> None:
    try:
        CDLL("libc.dylib").setprogname(c_char_p(name.encode("utf-8")))
    except (AttributeError, OSError):
        pass


def _set_main_bundle_display_name(name: str) -> None:
    try:
        from Foundation import NSBundle
    except ImportError:
        return

    info = NSBundle.mainBundle().infoDictionary()
    if info is None:
        return
    info["CFBundleName"] = name
    info["CFBundleDisplayName"] = name
