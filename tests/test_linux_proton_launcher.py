import os
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
        with tempfile.TemporaryDirectory() as temp_dir:
            launcher = LinuxProtonLauncher()
            launcher.config.config_file = os.path.join(temp_dir, "proton_launch.json")
            launcher.update_config(
                game_exe="/dummy/game/Client-Win64-Shipping.exe",
                wine_prefix="/dummy/pfx",
                launch_args="Client -dx12",
                wrapper="mangohud umu-run",
                custom_env="DXVK_FRAME_RATE=90"
            )

            cfg = launcher.get_config()
            self.assertEqual(cfg['game_exe'], "/dummy/game/Client-Win64-Shipping.exe")
            self.assertEqual(cfg['wine_prefix'], "/dummy/pfx")
            self.assertEqual(cfg['launch_args'], "Client -dx12")
            self.assertEqual(cfg['wrapper'], "mangohud umu-run")
            self.assertEqual(cfg['custom_env'], "DXVK_FRAME_RATE=90")

    def test_can_launch_check(self):
        launcher = LinuxProtonLauncher()
        launcher.config['game_exe'] = ""
        launcher.config['wrapper'] = ""
        self.assertFalse(launcher.can_launch())

        with tempfile.NamedTemporaryFile(suffix=".exe") as temp_exe:
            launcher.config['game_exe'] = temp_exe.name
            self.assertTrue(launcher.can_launch())

    @patch("subprocess.Popen")
    def test_launch_with_wrapper(self, mock_popen):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe_path = os.path.join(temp_dir, "Client-Win64-Shipping.exe")
            Path(exe_path).touch()

            launcher = LinuxProtonLauncher()
            launcher.config['game_exe'] = exe_path
            launcher.config['wine_prefix'] = os.path.join(temp_dir, "pfx")
            launcher.config['launch_args'] = "Client -dx12"
            launcher.config['wrapper'] = "dlssg mangohud umu-run"
            launcher.config['custom_env'] = "DXVK_FRAME_RATE=90\nANTI_DITHER_ENABLED=1"

            with patch.object(sys, "platform", "linux"):
                success, err = launcher.launch()

            self.assertTrue(success)
            self.assertEqual(err, "")
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


if __name__ == "__main__":
    unittest.main()
