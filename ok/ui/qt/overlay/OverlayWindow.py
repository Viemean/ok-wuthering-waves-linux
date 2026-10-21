"""Compatibility import for overlay window on Linux."""

from ok.ui.overlay import Win32GdiOverlay, LinuxOverlay

OverlayWindow = LinuxOverlay
GdiCanvas = None

__all__ = ["GdiCanvas", "OverlayWindow", "Win32GdiOverlay", "LinuxOverlay"]
