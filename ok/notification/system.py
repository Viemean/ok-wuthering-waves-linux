"""Desktop notifications following freedesktop.org specifications on Linux."""

from __future__ import annotations

import os
import shutil
import subprocess

from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


class LinuxSystemNotifier:
    """Desktop notification provider following freedesktop.org specifications on Linux."""

    def __init__(self, app_name="ok-script", app_icon=None):
        self.app_name = str(app_name or "ok-script")
        self.app_icon = self._resolve_icon(app_icon)

    def show(self, title, message, error=False):
        display_title = str(title or self.app_name)
        display_message = str(message or "")
        urgency = "critical" if error else "normal"

        if shutil.which("notify-send"):
            cmd = [
                "notify-send",
                "-a", self.app_name,
                "-u", urgency,
                "-t", "5000",
            ]
            if self.app_icon and os.path.exists(self.app_icon):
                cmd.extend(["-i", self.app_icon])
            cmd.extend([display_title, display_message])
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
                if result.returncode == 0:
                    return True
                logger.debug(f"notify-send returned code {result.returncode}")
            except Exception as exception:
                logger.debug(f"notify-send execution failed: {exception}")

        if shutil.which("gdbus"):
            icon_arg = self.app_icon if (self.app_icon and os.path.exists(self.app_icon)) else ""
            urgency_byte = "2" if error else "1"
            cmd = [
                "gdbus", "call", "--session",
                "--dest", "org.freedesktop.Notifications",
                "--object-path", "/org/freedesktop/Notifications",
                "--method", "org.freedesktop.Notifications.Notify",
                self.app_name, "0", icon_arg, display_title, display_message,
                "[]", f"{{'urgency': <byte {urgency_byte}>}}", "5000",
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
                if result.returncode == 0:
                    return True
                logger.debug(f"gdbus notification returned code {result.returncode}")
            except Exception as exception:
                logger.debug(f"gdbus execution failed: {exception}")

        return False

    def close(self):
        pass

    @staticmethod
    def _resolve_icon(app_icon):
        if not app_icon or str(app_icon).startswith(":/"):
            return ""
        from ok.util.file import get_path_relative_to_exe
        path = str(get_path_relative_to_exe(str(app_icon)) or "")
        return path if os.path.isfile(path) else ""


SystemNotifier = LinuxSystemNotifier


class TraySystemNotifier:
    """Adapt an existing UI tray icon to desktop notification manager."""

    def __init__(self, tray, information_icon, error_icon, app_name="ok-script", app_icon=None):
        self.tray = tray
        self.information_icon = information_icon
        self.error_icon = error_icon
        self.desktop_notifier = LinuxSystemNotifier(app_name, app_icon)

    def show(self, title, message, error=False):
        if self.desktop_notifier.show(title, message, error):
            return True
        if self.tray is not None:
            self.tray.showMessage(
                title, message, self.error_icon if error else self.information_icon, 5000)
            return True
        return False

    def close(self):
        self.desktop_notifier.close()
