import unittest
from unittest.mock import MagicMock, patch

from ok.core.events import communicate
from ok.device.capture_methods.linux_window import LinuxWindow


class TestLinuxWindowExitApp(unittest.TestCase):

    def setUp(self):
        self.patcher_thread = patch("threading.Thread")
        self.mock_thread = self.patcher_thread.start()
        self.patcher_init_disp = patch.object(LinuxWindow, "_init_display", return_value=True)
        self.mock_init_disp = self.patcher_init_disp.start()
        self.patcher_find = patch.object(LinuxWindow, "_find_target_window", return_value=(None, "", None, False))
        self.mock_find = self.patcher_find.start()

    def tearDown(self):
        self.patcher_find.stop()
        self.patcher_init_disp.stop()
        self.patcher_thread.stop()

    def test_exit_config_enabled_reads_true(self):
        mock_global_config = MagicMock()
        mock_global_config.get_config.return_value = {'Exit App when Game Exits': True}

        win = LinuxWindow(global_config=mock_global_config)
        self.assertTrue(win._is_exit_when_game_exits_enabled())

    def test_exit_config_disabled_reads_false(self):
        mock_global_config = MagicMock()
        mock_global_config.get_config.return_value = {'Exit App when Game Exits': False}

        win = LinuxWindow(global_config=mock_global_config)
        self.assertFalse(win._is_exit_when_game_exits_enabled())

    @patch.object(communicate.quit, "emit")
    @patch.object(communicate.notification, "emit")
    @patch.object(communicate.window, "emit")
    def test_game_closed_triggers_auto_exit_when_enabled(
        self, mock_window_emit, mock_notification_emit, mock_quit_emit
    ):
        mock_executor = MagicMock()
        mock_device_mgr = MagicMock()
        mock_device_mgr.executor = mock_executor
        mock_device = {'connected': True}
        mock_device_mgr.get_preferred_device.return_value = mock_device

        win = LinuxWindow(device_manager=mock_device_mgr)
        win.exists = True
        win.hwnd = 12345
        win._init_display = MagicMock(return_value=True)
        win._find_target_window = MagicMock(return_value=(None, "", None, False))
        win._is_exit_when_game_exits_enabled = MagicMock(return_value=True)

        win._scan_window()

        self.assertFalse(win.exists)
        self.assertEqual(win.hwnd, 0)
        self.assertFalse(mock_device['connected'])
        mock_executor.pause.assert_called_once()
        mock_quit_emit.assert_called_once()
        mock_notification_emit.assert_called_once_with(
            'Auto exit because game exited', None, False, True, None, None, None
        )

    @patch.object(communicate.quit, "emit")
    @patch.object(communicate.notification, "emit")
    @patch.object(communicate.window, "emit")
    def test_game_closed_does_not_quit_when_disabled(
        self, mock_window_emit, mock_notification_emit, mock_quit_emit
    ):
        mock_executor = MagicMock()
        mock_device_mgr = MagicMock()
        mock_device_mgr.executor = mock_executor
        mock_device = {'connected': True}
        mock_device_mgr.get_preferred_device.return_value = mock_device

        win = LinuxWindow(device_manager=mock_device_mgr)
        win.exists = True
        win.hwnd = 12345
        win._init_display = MagicMock(return_value=True)
        win._find_target_window = MagicMock(return_value=(None, "", None, False))
        win._is_exit_when_game_exits_enabled = MagicMock(return_value=False)

        win._scan_window()

        self.assertFalse(win.exists)
        self.assertEqual(win.hwnd, 0)
        self.assertFalse(mock_device['connected'])
        mock_executor.pause.assert_not_called()
        mock_quit_emit.assert_not_called()
        mock_notification_emit.assert_called_once_with(
            'Game Exited', None, True, True, None, None, None
        )
