import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.combat.AxisWatch import f_settings, start_enable_watch, start_f_watch


class TestAxisWatch(unittest.TestCase):
    def test_f_settings_defaults_when_task_missing(self):
        task = SimpleNamespace()
        enabled, delay = f_settings(task)
        self.assertTrue(enabled)
        self.assertEqual(delay, 0.0)

    def test_start_enable_watch_records_restart_time(self):
        task = SimpleNamespace(enabled=False)
        logger = Mock()

        start_enable_watch(task, logger)
        self.assertEqual(task._ww_task_restarted_at, -1)

        task.enabled = True
        time.sleep(0.35)
        self.assertGreater(task._ww_task_restarted_at, 0)
        logger.info.assert_called_with('auto combat re-enabled -> opener re-armed')

    def test_start_f_watch_initializes_and_runs_safely(self):
        task = SimpleNamespace()
        logger = Mock()

        start_f_watch(task, logger)
        self.assertTrue(task._f_watch_started)
        self.assertEqual(task._f_last_press, -1)


if __name__ == '__main__':
    unittest.main()
