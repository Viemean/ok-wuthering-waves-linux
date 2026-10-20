import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import config
from src import game_launcher


class TestGameLauncher(unittest.TestCase):
    def test_windows_config_registers_launch_arguments_callback(self):
        self.assertIs(
            config.config['windows']['launch_arguments'],
            game_launcher.get_game_launch_arguments,
        )

    def test_windows_config_registers_on_game_restart_callback(self):
        self.assertIs(
            config.config['windows']['on_game_restart'],
            game_launcher.sync_game_package,
        )

    def test_config_game_package_is_read_only(self):
        game_package_type = config.basic_config_option.config_type.get('Game Package')
        self.assertIsInstance(game_package_type, dict)
        self.assertEqual('read_only', game_package_type.get('type'))

    def test_launch_arguments_read_current_game_package(self):
        basic_options = {'Game Package': 'hd'}
        global_config = Mock()
        global_config.get_config.return_value = basic_options
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)), \
                patch.object(game_launcher, 'match_game_package_from_process', return_value=None):
            for package in ('sd', 'hd', 'uhd'):
                basic_options['Game Package'] = package
                self.assertEqual(f'-krqlv={package}', game_launcher.get_game_launch_arguments())

        self.assertEqual(3, global_config.get_config.call_count)
        global_config.get_config.assert_called_with('Basic Options')

    def test_launch_arguments_default_to_hd(self):
        global_config = Mock()
        global_config.get_config.return_value = {}
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)), \
                patch.object(game_launcher, 'match_game_package_from_process', return_value=None):
            self.assertEqual('-krqlv=hd', game_launcher.get_game_launch_arguments())

    def test_match_game_package_from_process_cmdline(self):
        mock_proc = Mock()
        mock_proc.info = {
            'cmdline': ['Client-Win64-Shipping.exe', 'Client', '-dx12', '-krqlv=uhd']
        }
        with patch('psutil.process_iter', return_value=[mock_proc]):
            matched = game_launcher.match_game_package_from_process()
            self.assertEqual('uhd', matched)

    def test_match_game_package_from_process_no_param(self):
        mock_proc = Mock()
        mock_proc.info = {
            'cmdline': ['Client-Win64-Shipping.exe', 'Client', '-dx12']
        }
        with patch('psutil.process_iter', return_value=[mock_proc]):
            matched = game_launcher.match_game_package_from_process()
            self.assertIsNone(matched)

    def test_sync_game_package_updates_config_and_emits_event(self):
        basic_options = {'Game Package': 'hd'}
        global_config = Mock()
        global_config.get_config.return_value = basic_options
        with patch.object(game_launcher, 'og', SimpleNamespace(global_config=global_config)), \
                patch.object(game_launcher, 'match_game_package_from_process', return_value='sd'), \
                patch('ok.core.events.communicate.config_updated.emit') as mock_emit:
            synced = game_launcher.sync_game_package()
            self.assertEqual('sd', synced)
            self.assertEqual('sd', basic_options['Game Package'])
            mock_emit.assert_called_once_with('Basic Options', 'Game Package', 'sd')


if __name__ == '__main__':
    unittest.main()
