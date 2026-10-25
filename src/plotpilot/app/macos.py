"""macOS-specific process and branding when running under the Python interpreter."""

from __future__ import annotations

import sys
from ctypes import CDLL, c_char_p

_PLOTPILOT_BUNDLE_ID = "com.plotpilot.app"


def uses_system_dock_icon(platform: str, bundle_identifier: str | None) -> bool:
    """Packaged PlotPilot.app lets macOS mask the bundle icon. Dev runs do not."""
    return platform == "darwin" and bundle_identifier == _PLOTPILOT_BUNDLE_ID


def running_inside_plotpilot_app() -> bool:
    """Return True when this process is the packaged PlotPilot.app bundle."""
    return uses_system_dock_icon(sys.platform, _main_bundle_identifier())


def _main_bundle_identifier() -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        from Foundation import NSBundle
    except ImportError:
        return None
    bundle = NSBundle.mainBundle()
    if bundle is None:
        return None
    identifier = bundle.bundleIdentifier()
    return str(identifier) if identifier else None


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
