import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ok.device.linux_proton_launcher import LinuxProtonLauncher, get_proton_launcher
from ok.util.process import is_admin


class TestLinuxProtonLauncher(unittest.TestCase):

    def test_is_admin_returns_true_on_linux(self):
        with patch.object(sys, "platform", "linux"):
            self.assertTrue(is_admin())

    def test_launcher_config_persistence(self):
        isolated_cfg = {}
        launcher = LinuxProtonLauncher(config=isolated_cfg)
        launcher.update_config(
            game_exe="/dummy/game/mock_game.exe",
            wine_prefix="/dummy/pfx",
            launch_args="Client -dx12",
            wrapper="mangohud umu-run",
            custom_env="DXVK_FRAME_RATE=90"
        )

        cfg = launcher.get_config()
        self.assertEqual(cfg['game_exe'], "/dummy/game/mock_game.exe")
        self.assertEqual(cfg['wine_prefix'], "/dummy/pfx")
        self.assertEqual(cfg['launch_args'], "Client -dx12")
        self.assertEqual(cfg['wrapper'], "mangohud umu-run")
        self.assertEqual(cfg['custom_env'], "DXVK_FRAME_RATE=90")

    def test_can_launch_check(self):
        isolated_cfg = {'game_exe': '', 'wrapper': ''}
        launcher = LinuxProtonLauncher(config=isolated_cfg)
        self.assertFalse(launcher.can_launch())

        with tempfile.NamedTemporaryFile(suffix=".exe") as temp_exe:
            isolated_cfg['game_exe'] = temp_exe.name
            self.assertTrue(launcher.can_launch())

    @patch("subprocess.Popen")
    @patch.object(LinuxProtonLauncher, "kill_existing_game_processes", return_value=0)
    def test_launch_with_wrapper(self, mock_kill, mock_popen):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe_path = os.path.join(temp_dir, "mock_game.exe")
            Path(exe_path).touch()

            isolated_cfg = {
                'game_exe': exe_path,
                'wine_prefix': os.path.join(temp_dir, "pfx"),
                'launch_args': "Client -dx12",
                'wrapper': "dlssg mangohud umu-run",
                'custom_env': "DXVK_FRAME_RATE=90\nANTI_DITHER_ENABLED=1",
                'runner_path': ""
            }
            launcher = LinuxProtonLauncher(config=isolated_cfg)
            mock_popen.return_value.wait.side_effect = subprocess.TimeoutExpired(cmd="", timeout=1.0)

            with patch.object(sys, "platform", "linux"):
                success, err = launcher.launch()

            self.assertTrue(success)
            self.assertEqual(err, "")
            mock_kill.assert_called_once_with(exe_path)
            mock_popen.assert_called_once()
            call_args, call_kwargs = mock_popen.call_args

            cmd = call_args[0]
            self.assertEqual(cmd[0], "dlssg")
            self.assertEqual(cmd[1], "mangohud")
            self.assertEqual(cmd[2], "umu-run")
            self.assertEqual(cmd[3], exe_path)
            self.assertIn("-dx12", cmd)

            env = call_kwargs['env']
            self.assertEqual(env.get('DXVK_FRAME_RATE'), "90")
            self.assertEqual(env.get('ANTI_DITHER_ENABLED'), "1")
            self.assertEqual(env.get('WINEPREFIX'), os.path.join(temp_dir, "pfx"))

    @patch("subprocess.Popen")
    @patch.object(LinuxProtonLauncher, "kill_existing_game_processes", return_value=0)
    def test_launch_premature_exit_reports_failure(self, mock_kill, mock_popen):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe_path = os.path.join(temp_dir, "mock_game.exe")
            Path(exe_path).touch()

            isolated_cfg = {
                'game_exe': exe_path,
                'wine_prefix': os.path.join(temp_dir, "pfx"),
                'launch_args': "",
                'wrapper': "umu-run",
                'custom_env': "",
                'runner_path': ""
            }
            launcher = LinuxProtonLauncher(config=isolated_cfg)
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.wait.return_value = None  # Process finishes within wait timeout
            mock_popen.return_value = mock_proc

            with patch.object(sys, "platform", "linux"):
                success, err = launcher.launch()

            self.assertFalse(success)
            self.assertIn("exited prematurely with code 1", err)
            mock_kill.assert_called_once_with(exe_path)

    def test_detect_env_conditional_wrapper_filtering(self):
        with tempfile.TemporaryDirectory() as temp_proc:
            p_dir = Path(temp_proc) / "1234"
            p_dir.mkdir(parents=True)
            (p_dir / "comm").write_text("Client-Win64-Shipping.exe")
            (p_dir / "cmdline").write_bytes(b"/dummy/game/Client-Win64-Shipping.exe\0-dx12\0")
            (p_dir / "stat").write_text("1234 (Client) S 1 0 0 0 0")

            # Case A: with mangohud wrapper in cmdline
            (p_dir / "cmdline").write_bytes(b"mangohud\0/dummy/game/Client-Win64-Shipping.exe\0")
            (p_dir / "environ").write_bytes(
                b"WINEPREFIX=/dummy/pfx\0"
                b"MANGOHUD=1\0"
                b"ANTI_DITHER_ENABLED=1\0"
                b"DXVK_FRAME_RATE=90\0"
            )
            with patch("ok.device.linux_proton_launcher.Path", return_value=Path(temp_proc)):
                result = LinuxProtonLauncher.detect_running_game_env()
                self.assertIn("mangohud", result['wrapper'])
                self.assertNotIn("MANGOHUD=1", result['custom_env'])
                self.assertIn("ANTI_DITHER_ENABLED=1", result['custom_env'])
                self.assertIn("DXVK_FRAME_RATE=90", result['custom_env'])

            # Case B: without mangohud wrapper, MANGOHUD set via env
            (p_dir / "cmdline").write_bytes(b"/dummy/game/Client-Win64-Shipping.exe\0")
            with patch("ok.device.linux_proton_launcher.Path", return_value=Path(temp_proc)):
                result = LinuxProtonLauncher.detect_running_game_env()
                self.assertEqual(result['wrapper'], "")
                self.assertIn("MANGOHUD=1", result['custom_env'])
                self.assertIn("ANTI_DITHER_ENABLED=1", result['custom_env'])
                self.assertIn("DXVK_FRAME_RATE=90", result['custom_env'])

    @patch("psutil.wait_procs")
    @patch("psutil.process_iter")
    def test_kill_existing_game_processes(self, mock_iter, mock_wait):
        mock_proc1 = MagicMock()
        mock_proc1.info = {'pid': 99991, 'name': 'mock_game.exe', 'cmdline': ['S:\\dummy\\mock_game.exe']}
        mock_proc2 = MagicMock()
        mock_proc2.info = {'pid': 99992, 'name': 'umu.exe', 'cmdline': ['umu.exe', 'mock_game.exe']}
        mock_proc_other = MagicMock()
        mock_proc_other.info = {'pid': 99993, 'name': 'bash', 'cmdline': ['/bin/bash']}

        mock_iter.return_value = [mock_proc1, mock_proc2, mock_proc_other]
        mock_wait.return_value = ([mock_proc1], [mock_proc2])

        count = LinuxProtonLauncher.kill_existing_game_processes("/dummy/mock_game.exe")
        self.assertEqual(count, 2)
        mock_proc1.terminate.assert_called_once()
        mock_proc2.terminate.assert_called_once()
        mock_proc2.kill.assert_called_once()
        mock_proc_other.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
