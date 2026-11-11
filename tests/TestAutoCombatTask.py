import unittest
from unittest.mock import Mock, patch

from ok import TaskDisabledException, TaskPausedException, communicate
from src.char.BaseChar import BaseChar
from src.char.CharFactory import get_char_by_pos
from src.scene.WWScene import WWScene
from src.task.AutoCombatTask import AutoCombatTask


class TestAutoCombatTask(unittest.TestCase):
    def setUp(self):
        self.scene = WWScene()
        self.executor = Mock(scene=self.scene, debug=False)
        self.task = AutoCombatTask(self.executor, None)
        self.task.tr = str
        self.task.scene = self.scene
        self.task.config = dict(self.task.default_config)
        self.task.char_config = {}
        self.task.warm_up_char_features = Mock()
        self.task.in_team_and_world = Mock(return_value=True)
        self.task.in_world = Mock(return_value=True)
        self.task.switch_healer = Mock()
        self.task.combat_end = Mock()

    def seed_combat(self):
        old_char = BaseChar(self.task, 0, char_name='old_team')
        old_char.is_current_char = True
        old_char.perform = Mock(side_effect=TaskDisabledException)
        self.task.chars = [old_char, None, None]
        self.task._in_combat = True
        self.task.in_liberation = True
        self.task.skip_combat_check = True
        self.task.cds = {'resonance': 12}
        self.task.freeze_durations = [(1, 2, 0.1)]
        self.scene.set_in_combat()
        return old_char

    def assert_combat_cleared(self):
        self.assertFalse(self.task._in_combat)
        self.assertFalse(self.task.in_liberation)
        self.assertFalse(self.task.skip_combat_check)
        self.assertFalse(self.task.in_sleep_check)
        self.assertEqual(self.task.chars, [None, None, None])
        self.assertEqual(self.task.cds, {})
        self.assertEqual(self.task.freeze_durations, [])
        self.assertFalse(self.scene.in_combat())

    def test_disable_during_rotation_cleans_up_and_propagates(self):
        old_char = self.seed_combat()

        with self.assertRaises(TaskDisabledException):
            self.task.run()

        old_char.perform.assert_called_once()
        self.assert_combat_cleared()
        self.task.combat_end.assert_not_called()
        self.task.switch_healer.assert_called_once()

    def test_disable_inside_combat_check_cleans_up_and_propagates(self):
        old_char = self.seed_combat()
        self.task.in_liberation = False
        self.scene.reset()
        self.task.check_f_break = Mock()
        self.task.on_combat_check = Mock(return_value=True)
        self.task.has_target = Mock(side_effect=TaskDisabledException)

        with self.assertRaises(TaskDisabledException):
            self.task.run()

        self.assert_combat_cleared()
        old_char.perform.assert_not_called()
        self.task.combat_end.assert_not_called()
        self.task.switch_healer.assert_not_called()

    def test_disable_between_runs_invalidates_chars_before_reentry(self):
        old_char = self.seed_combat()
        self.task._in_combat = False
        self.task.in_liberation = False
        self.task._enabled = True
        self.task.disable()
        self.task.enable()
        self.scene.reset()
        self.task.load_hotkey = Mock()
        self.task.in_team = Mock(return_value=(True, 0, 3))
        self.task.get_box_by_name = Mock()
        self.task.has_target = Mock(return_value=True)
        self.task.find_one = Mock(return_value=None)
        # Simulate an obscured portrait: no match must not revive an old char.
        self.task.find_best_match_in_box = Mock(return_value=None)
        recognized_chars = []

        def recognize(task, box, index, previous):
            self.assertIsNone(previous)
            char = get_char_by_pos(task, box, index, previous)
            char.perform = Mock(side_effect=TaskDisabledException)
            recognized_chars.append(char)
            return char

        with patch('src.task.BaseCombatTask.get_char_by_pos', side_effect=recognize):
            with self.assertRaises(TaskDisabledException):
                self.task.run()

        self.assertEqual([char.char_name for char in recognized_chars], ['unknown'] * 3)
        old_char.perform.assert_not_called()
        recognized_chars[0].perform.assert_called_once()
        self.assert_combat_cleared()

    def test_leaving_world_invalidates_combat_and_chars(self):
        old_char = self.seed_combat()
        self.task.in_team_and_world.return_value = False

        self.assertFalse(self.task.run())

        self.assert_combat_cleared()
        old_char.perform.assert_not_called()
        self.task.switch_healer.assert_not_called()

    def test_normal_polling_preserves_character_cache(self):
        char = BaseChar(self.task, 0, char_name='same_team')
        self.task.chars = [char, None, None]
        self.task.in_combat = Mock(return_value=False)

        self.assertFalse(self.task.run())
        self.scene.reset()
        self.assertFalse(self.task.run())

        self.assertIs(self.task.chars[0], char)

    def test_sleep_restores_skip_flag_after_disable(self):
        char = BaseChar(self.task, 0)
        for previous in (False, True):
            for check_combat in (False, True):
                with self.subTest(previous=previous, check_combat=check_combat):
                    self.task.skip_combat_check = previous

                    def interrupt_sleep(seconds):
                        self.assertEqual(self.task.skip_combat_check, previous or not check_combat)
                        raise TaskDisabledException()

                    self.task.sleep = interrupt_sleep
                    with self.assertRaises(TaskDisabledException):
                        char.sleep(0.1, check_combat=check_combat)
                    self.assertEqual(self.task.skip_combat_check, previous)

    def test_nested_sleep_keeps_outer_combat_check_suppressed(self):
        char = BaseChar(self.task, 0)
        flags = []

        def sleep(seconds):
            flags.append(self.task.skip_combat_check)
            if seconds == 1:
                char.sleep(0.1)
                flags.append(self.task.skip_combat_check)

        self.task.sleep = sleep
        char.sleep(1, check_combat=False)

        self.assertEqual(flags, [True, True, True])
        self.assertFalse(self.task.skip_combat_check)

    def test_task_paused_exception_exits_combat_and_cleans_up(self):
        old_char = self.seed_combat()
        old_char.perform = Mock(side_effect=TaskPausedException("paused by user"))

        result = self.task.run()

        old_char.perform.assert_called_once()
        self.task.combat_end.assert_called_once()
        self.assertEqual(self.task.switch_healer.call_count, 2)
        self.assertTrue(result)

    def test_executor_unpaused_resets_opener_progress(self):
        char = BaseChar(self.task, 0, char_name='test_char')
        char.opener_armed = False
        char.last_opener = 1000.0
        self.task.chars = [char, None, None]
        self.task._f_last_press = 500.0

        # Simulate user pressing F9 to unpause / start
        communicate.executor_paused.emit(False)

        self.assertTrue(self.task._reset_combat_on_run)
        self.assertTrue(char.opener_armed)
        self.assertEqual(char.last_opener, -1)
        self.assertGreater(self.task._f_last_press, 1000.0)

    def test_custom_macro_opener_rearmed_after_unpause(self):
        # Mock the exact logic of workshop custom characters (Cartethyia/Hsin/Zani)
        class CustomChar(BaseChar):
            def __init__(self, task, index):
                super().__init__(task, index)
                self.opener_armed = True
                self.last_opener = -1
                self.OPENER_MIN_GAP = 60.0

            def opener_blocked_by(self):
                if not self.opener_armed:
                    return 'already armed-down (ran once this combat)'
                f_press = getattr(self.task, '_f_last_press', -1)
                if f_press > self.last_opener:
                    return None
                if self.last_opener >= 0 and (time.time() - self.last_opener) < self.OPENER_MIN_GAP:
                    return f'ran recently (< {self.OPENER_MIN_GAP:.0f}s)'
                return None

        import time
        char = CustomChar(self.task, 0)
        self.task.chars = [char, None, None]

        # 1. First run of opener
        self.assertIsNone(char.opener_blocked_by())
        char.opener_armed = False
        char.last_opener = time.time()

        # 2. Subsequent check without F / restart -> blocked!
        self.assertEqual(char.opener_blocked_by(), 'already armed-down (ran once this combat)')

        # 3. Simulate pressing F9 to restart
        communicate.executor_paused.emit(False)

        # 4. Verified: blocked reason cleared, opener re-armed!
        self.assertTrue(char.opener_armed)
        self.assertEqual(char.last_opener, -1)
        self.assertIsNone(char.opener_blocked_by())


if __name__ == '__main__':
    unittest.main()
