import os
import unittest
from unittest.mock import MagicMock, patch

from ok.notification.system import LinuxSystemNotifier, TraySystemNotifier
from ok.notification.manager import NotificationManager


class TestLinuxNotification(unittest.TestCase):

    def test_linux_notifier_notify_send_success(self):
        notifier = LinuxSystemNotifier(app_name="test-app", app_icon="")
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/notify-send" if cmd == "notify-send" else None
            mock_run.return_value = MagicMock(returncode=0)

            result = notifier.show("Title", "Message", error=False)
            self.assertTrue(result)
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            cmd = args[0]
            self.assertEqual(cmd[0], "notify-send")
            self.assertIn("-a", cmd)
            self.assertIn("test-app", cmd)
            self.assertIn("-u", cmd)
            self.assertIn("normal", cmd)
            self.assertIn("Title", cmd)
            self.assertIn("Message", cmd)

    def test_linux_notifier_urgency_on_error(self):
        notifier = LinuxSystemNotifier(app_name="test-app")
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            mock_which.side_effect = lambda cmd: "/usr/bin/notify-send" if cmd == "notify-send" else None
            mock_run.return_value = MagicMock(returncode=0)

            notifier.show("Error Title", "Error Message", error=True)
            cmd = mock_run.call_args[0][0]
            self.assertIn("-u", cmd)
            u_index = cmd.index("-u")
            self.assertEqual(cmd[u_index + 1], "critical")

    def test_linux_notifier_fallback_to_gdbus(self):
        notifier = LinuxSystemNotifier(app_name="test-app")
        with patch("shutil.which") as mock_which, patch("subprocess.run") as mock_run:
            def which_side_effect(cmd):
                if cmd == "notify-send":
                    return None
                if cmd == "gdbus":
                    return "/usr/bin/gdbus"
                return None

            mock_which.side_effect = which_side_effect
            mock_run.return_value = MagicMock(returncode=0)

            result = notifier.show("Title", "Message", error=False)
            self.assertTrue(result)
            cmd = mock_run.call_args[0][0]
            self.assertEqual(cmd[0], "gdbus")
            self.assertIn("org.freedesktop.Notifications", cmd)

    def test_tray_system_notifier_delegates_to_desktop_notifier(self):
        fake_tray = MagicMock()
        notifier = TraySystemNotifier(fake_tray, 1, 2, app_name="test-app")
        with patch.object(notifier.desktop_notifier, "show", return_value=True) as mock_desktop_show:
            result = notifier.show("Title", "Message")
            self.assertTrue(result)
            mock_desktop_show.assert_called_once_with("Title", "Message", False)
            fake_tray.showMessage.assert_not_called()

    def test_tray_system_notifier_fallbacks_to_tray_when_desktop_notifier_fails(self):
        fake_tray = MagicMock()
        notifier = TraySystemNotifier(fake_tray, 1, 2, app_name="test-app")
        with patch.object(notifier.desktop_notifier, "show", return_value=False):
            result = notifier.show("Title", "Message")
            self.assertTrue(result)
            fake_tray.showMessage.assert_called_once_with("Title", "Message", 1, 5000)

    def test_notification_manager_default_linux_notifier(self):
        fake_config = MagicMock()
        fake_config.get_config.return_value = {}
        fake_executor = MagicMock()
        mgr = NotificationManager(fake_config, fake_executor, app_name="test-app")
        self.assertIsInstance(mgr.system_notifier, LinuxSystemNotifier)


if __name__ == "__main__":
    unittest.main()
