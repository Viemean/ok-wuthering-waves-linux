"""Linux safe game overlay implementations."""


class LinuxOverlay:
    """Safe no-op game overlay implementation for Linux / Proton."""

    def __init__(self, hwnd_window=None, exit_event=None):
        self.hwnd_window = hwnd_window
        self.exit_event = exit_event
        self._boxes_enabled = False

    def update_overlay(self, *args, **kwargs):
        pass

    def set_boxes_enabled(self, enabled):
        self._boxes_enabled = bool(enabled)

    def close(self, wait=True):
        pass

    def sync_source_window(self, window):
        self.hwnd_window = window


Win32GdiOverlay = LinuxOverlay

__all__ = ["LinuxOverlay", "Win32GdiOverlay"]
