import unittest
import re

from src.task.BaseCombatTask import CharRevivedException
from src.task.NightmareNestTask import ONLY_NESTS, NestTarget, NightmareNestTask


class FakeBox:

    def __init__(self, name, x=0, y=0, width=20, height=10):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class TestNightmareNestTask(unittest.TestCase):

    def test_parse_nest_indices(self):
        from src.task.NightmareNestTask import parse_nest_indices
        self.assertIsNone(parse_nest_indices(''))
        self.assertIsNone(parse_nest_indices(None))
        self.assertIsNone(parse_nest_indices('abc, ?!, 0'))
        self.assertEqual({1, 2, 3}, parse_nest_indices('1, 2, 3'))
        self.assertEqual({1, 2, 3}, parse_nest_indices('1，2，3'))
        self.assertEqual({1, 2, 3, 4, 5}, parse_nest_indices('1-5'))
        self.assertEqual({1, 2, 3, 5}, parse_nest_indices('1-3, 5'))
        # Clamped to max 10 and 1-based
        self.assertEqual(set(range(1, 11)), parse_nest_indices('0-999'))
        self.assertEqual({10}, parse_nest_indices('10, 15, 99'))

    def test_only_farm_these_nests_empty_farms_first_incomplete(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.config = {ONLY_NESTS: ''}
        task.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        task._unreachable_nests = set()
        task.queues = [task.go_nest]
        task._discovered_nests = {'canxiang': [], 'mengyan': []}
        task.log_info = lambda *args, **kwargs: None
        task.tr = lambda s: s
        task.width_of_screen = lambda ratio: 1000
        task._make_nest_cache_key = lambda box, denominator: f'{box.name}@{denominator}'
        counts = [FakeBox('已击败残象：0/41', y=373, height=30), FakeBox('已击败残象：0/48', y=596, height=30)]
        task.ocr = lambda *args, **kwargs: counts
        nest = task.find_nest()
        self.assertIsInstance(nest, NestTarget)
        self.assertEqual('已击败残象：0/41@41', nest.cache_key)

    def test_find_nest_by_index_skips_unselected_and_completed(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        # Select index 1 and 2, but index 1 is already complete (48/48) -> should pick index 2 (0/48)
        task.config = {ONLY_NESTS: '1, 2'}
        task.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        task._unreachable_nests = set()
        task.queues = [task.go_nest]
        task._discovered_nests = {'canxiang': [], 'mengyan': []}
        task.log_info = lambda *args, **kwargs: None
        task.tr = lambda s: s
        task.width_of_screen = lambda ratio: 1000
        task._make_nest_cache_key = lambda box, denominator: f'{box.name}@{denominator}'
        names = [FakeBox('落渊南丘残象聚落', y=300, height=35), FakeBox('盲望之塌残象聚落', y=523, height=35)]
        counts = [FakeBox('已击败残象：48/48', y=373, height=30), FakeBox('已击败残象：0/48', y=596, height=30)]
        task.ocr = lambda *args, **kwargs: counts if 'match' in kwargs else names + counts
        nest = task.find_nest()
        self.assertIsInstance(nest, NestTarget)
        self.assertEqual('已击败残象：0/48@48', nest.cache_key)

    def test_find_nest_skips_indices_not_in_range(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        # Select only index 3, but current screen only has indices 1 and 2
        task.config = {ONLY_NESTS: '3'}
        task.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        task._unreachable_nests = set()
        task.queues = [task.go_nest]
        task._discovered_nests = {'canxiang': [], 'mengyan': []}
        task.log_info = lambda *args, **kwargs: None
        task.tr = lambda s: s
        task.width_of_screen = lambda ratio: 1000
        task._make_nest_cache_key = lambda box, denominator: f'{box.name}@{denominator}'
        names = [FakeBox('落渊南丘残象聚落', y=300, height=35), FakeBox('盲望之塌残象聚落', y=523, height=35)]
        counts = [FakeBox('已击败残象：0/41', y=373, height=30), FakeBox('已击败残象：0/48', y=596, height=30)]
        task.ocr = lambda *args, **kwargs: counts if 'match' in kwargs else names + counts
        self.assertIsNone(task.find_nest())

    def test_nest_is_checked_before_nightmare_changes_book_scroll(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task.config = {'Which to Farm': ['Nightmare Purification', 'Tacet Discord Nest']}
        task._init_queue()
        self.assertEqual(['go_nest', 'go_nest_scroll', 'go_nightmare', 'go_nightmare_scroll'],
                         [action.__name__ for action in task.queues])

    def test_capture_success_clears_combat_before_post_combat_waits(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._capture_mode = True
        task._in_combat = True
        picked = []

        task.pick_f = lambda handle_claim=True: picked.append(handle_claim)
        task.has_echo_notification = lambda: True

        def reset_to_false(reason=''):
            task._in_combat = False
            task.out_of_combat_reason = reason
            return False

        task.reset_to_false = reset_to_false

        self.assertFalse(task.on_combat_check())
        self.assertEqual([False], picked)
        self.assertFalse(task._in_combat)
        self.assertEqual('echo captured', task.out_of_combat_reason)

    def test_combat_nest_rechecks_after_pickup_in_team_and_open_world(self):
        for feature_name in ('team_close', 'team_start_challenge', 'fast_travel_custom'):
            with self.subTest(feature_name=feature_name):
                task = NightmareNestTask.__new__(NightmareNestTask)
                task.tr = str
                task._capture_mode = False
                task._capture_success = False
                combat_calls = []
                pickup_calls = []
                combat_results = iter([True, False])

                task.click = lambda *args, **kwargs: None
                task.wait_feature = lambda *args, **kwargs: FakeBox(feature_name)
                task.click_team_challenge = lambda: None
                task.wait_in_team_and_world = lambda *args, **kwargs: True
                task._travel_to_nest_or_skip = lambda nest: True
                task.sleep = lambda *args, **kwargs: None
                task.find_f_with_text = lambda: False
                task.run_until = lambda *args, **kwargs: None
                task.combat_once = lambda **kwargs: combat_calls.append(kwargs) or True
                task.pick_echo_by_method = lambda **kwargs: pickup_calls.append(kwargs) or True
                task.wait_combat = lambda **kwargs: next(combat_results)
                task.log_info = lambda *args, **kwargs: None
                task.send_key = lambda *args, **kwargs: None
                task.esc_world_confirm = lambda *args, **kwargs: None

                task.combat_nest(FakeBox('nest'))

                self.assertEqual([10, 1], [call['wait_combat_time'] for call in combat_calls])
                self.assertEqual(2, len(pickup_calls))

    def test_team_screen_is_detected_when_close_button_is_hovered(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._capture_mode = False
        task._capture_success = False
        challenge_clicks = []
        probes = []

        def wait_feature(features, **kwargs):
            probes.append(list(features))
            return FakeBox('team_start_challenge')

        task.click = lambda *args, **kwargs: None
        task.wait_feature = wait_feature
        task.click_team_challenge = lambda: challenge_clicks.append(True)
        task.wait_in_team_and_world = lambda *args, **kwargs: True
        task.combat_once = lambda **kwargs: False
        task.sleep = lambda *args, **kwargs: None
        task.pick_echo_by_method = lambda **kwargs: True
        task.wait_combat = lambda **kwargs: False
        task._should_continue_combat_after_pickup = lambda: False
        task.log_info = lambda *args, **kwargs: None
        task.esc_world_confirm = lambda *args, **kwargs: None

        task.combat_nest(FakeBox('nest'))

        self.assertIn('team_close', probes[0])
        self.assertIn('team_start_challenge', probes[0])
        self.assertEqual([True], challenge_clicks)

    def test_capture_mode_does_not_check_combat_after_pickup(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._capture_mode = True
        task.wait_combat = lambda **kwargs: self.fail('capture mode should leave after obtaining an echo')

        self.assertFalse(task._should_continue_combat_after_pickup())

    def test_unreachable_nest_is_cached_when_travel_does_not_enter_world(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._unreachable_nests = set()
        backs = []
        clicks = []
        wait_timeouts = []
        world_waits = []
        travel = FakeBox('fast_travel_custom')

        task.wait_until = lambda *args, **kwargs: wait_timeouts.append(kwargs['time_out']) or travel
        task.find_one = lambda name, **kwargs: travel if name == travel.name else None
        task.click = lambda box, **kwargs: clicks.append((box, kwargs))
        task.wait_in_team_and_world = lambda *args, **kwargs: world_waits.append(kwargs) or False
        task.back = lambda *args, **kwargs: backs.append(kwargs)
        task.log_info = lambda *args, **kwargs: None

        target = NestTarget(object(), 'go_nightmare:36:0.205')

        self.assertFalse(task._travel_to_nest_or_skip(target))
        self.assertIn(target.cache_key, task._unreachable_nests)
        self.assertEqual([1], wait_timeouts)
        self.assertEqual([(travel, {'after_sleep': 1})], clicks)
        self.assertEqual([], world_waits)
        self.assertEqual([{'after_sleep': 1}], backs)

    def test_nest_is_skipped_after_max_deaths(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._capture_mode = False
        task._capture_success = False
        task._unreachable_nests = set()
        task._nest_deaths = {}
        logs = []

        def combat_once(**kwargs):
            raise CharRevivedException('char dead')

        task.click = lambda *args, **kwargs: None
        task.wait_feature = lambda *args, **kwargs: FakeBox('team_close')
        task.click_team_challenge = lambda: None
        task.wait_in_team_and_world = lambda *args, **kwargs: True
        task.combat_once = combat_once
        task.log_info = lambda message, **kwargs: logs.append(message)
        nest = NestTarget(object(), 'go_nest:36:10')

        for _ in range(NightmareNestTask.max_nest_deaths - 1):
            task.combat_nest(nest)
            self.assertNotIn(nest.cache_key, task._unreachable_nests)
        task.combat_nest(nest)

        self.assertIn(nest.cache_key, task._unreachable_nests)
        self.assertIn('nightmare nest: died 3 times, skip this run: go_nest:36:10', logs)

    def test_travel_waits_up_to_120_seconds_for_loading(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task._unreachable_nests = set()
        travel = FakeBox('fast_travel_custom')
        world_waits = []

        task.wait_until = lambda *args, **kwargs: travel
        task.find_one = lambda *args, **kwargs: None
        task.click = lambda *args, **kwargs: None
        task.wait_in_team_and_world = lambda *args, **kwargs: world_waits.append(kwargs) or True

        self.assertTrue(task._travel_to_nest_or_skip(NestTarget(object(), 'go_nest:36:10')))
        self.assertEqual([{'time_out': 120, 'raise_if_not_found': False}], world_waits)

    def test_find_nest_skips_cached_unreachable_row(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        task.queues = [lambda: None]
        task._unreachable_nests = {'<lambda>:36:10'}
        task.log_info = lambda *args, **kwargs: None
        task.height_of_screen = lambda value: 1000 * value
        task.width_of_screen = lambda value: 2000 * value
        ocr_calls = []

        count_boxes = [
            FakeBox('0/36', y=200),
            FakeBox('0/36', y=300),
        ]

        def ocr(*args, **kwargs):
            ocr_calls.append((args, kwargs))
            return count_boxes

        task.ocr = ocr

        target = task.find_nest()

        self.assertIsInstance(target, NestTarget)
        self.assertIs(target.box, count_boxes[1])
        self.assertEqual('<lambda>:36:15', target.cache_key)
        self.assertEqual(1800, target.box.x)
        self.assertEqual(1, len(ocr_calls))

    def test_cache_key_ignores_small_ocr_position_jitter(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.tr = str
        task.queues = [lambda: None]
        task.height_of_screen = lambda value: 1000 * value

        first = task._make_nest_cache_key(FakeBox('0/36', y=200), '36')
        shifted = task._make_nest_cache_key(FakeBox('0/36', y=202), '36')

        self.assertEqual(first, shifted)

    def test_init_configures_echo_pickup_method(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task.default_config = {'_enabled': True}
        task.config_type = {}
        task.config_description = {}
        task.find_echo_method = task.get_find_echo_methods()
        task.default_config.update({
            'Which to Farm': ['Nightmare Purification', 'Tacet Discord Nest'],
            'Echo Pickup Method': 'Walk',
            ONLY_NESTS: '',
        })
        task.config_type['Which to Farm'] = {'type': "multi_selection",
                                             'options': ['Nightmare Purification', 'Tacet Discord Nest']}
        task.config_type['Echo Pickup Method'] = {'type': "drop_down", 'options': task.find_echo_method}

        expected_methods = ['Yolo', 'Run in Circle', 'Walk']
        if hasattr(task, 'back_and_forth_find_echo'):
            expected_methods.append('Back and Forth')

        self.assertEqual('Walk', task.default_config.get('Echo Pickup Method'))
        self.assertEqual(expected_methods, task.find_echo_method)
        self.assertEqual({'type': 'drop_down', 'options': expected_methods},
                         task.config_type.get('Echo Pickup Method'))

    def test_combat_nest_calls_pick_echo_by_method(self):
        task = NightmareNestTask.__new__(NightmareNestTask)
        task._capture_mode = False
        task._capture_success = False
        calls = []

        task.click = lambda *args, **kwargs: None
        task.wait_feature = lambda *args, **kwargs: FakeBox('team_close')
        task.click_team_challenge = lambda: None
        task.wait_in_team_and_world = lambda *args, **kwargs: True
        task.sleep = lambda *args, **kwargs: None
        task.combat_once = lambda **kwargs: True
        task.pick_echo_by_method = lambda **kwargs: calls.append(kwargs) or True
        task.wait_combat = lambda **kwargs: False
        task.esc_world_confirm = lambda *args, **kwargs: None

        task.combat_nest(FakeBox('nest'))

        self.assertEqual([{'turn': True}], calls)
        self.assertTrue(task._capture_success)


if __name__ == '__main__':
    unittest.main()
