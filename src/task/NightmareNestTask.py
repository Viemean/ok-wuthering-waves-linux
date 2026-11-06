import re
import cv2
from dataclasses import dataclass

from ok import Logger
from src.task.BaseCombatTask import BaseCombatTask, CharRevivedException
from src.task.BaseWWTask import TEAM_SCREEN_FEATURES
from src.task.WWOneTimeTask import WWOneTimeTask

logger = Logger.get_logger(__name__)
TRAVEL_FEATURES = ['fast_travel_custom', 'gray_teleport', 'remove_custom']
CONFIRM_FEATURES = ['confirm_btn_hcenter_vcenter', 'confirm_btn_highlight_hcenter_vcenter']
ONLY_NESTS = 'Only Farm These Nests'
MAX_NEST_INDEX = 10


def parse_nest_indices(raw):
    """Parse '1, 2, 3' or '1-5' or '1, 3-5' into a set of 1-based integers in [1, 10].
    Returns None if raw is empty or contains no valid indices.
    """
    if not raw:
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    cleaned = raw_str.replace('，', ',').replace('~', '-')
    tokens = [t.strip() for t in cleaned.split(',') if t.strip()]
    indices = set()
    for token in tokens:
        if '-' in token:
            parts = token.split('-', 1)
            if parts[0].strip().isdigit() and parts[1].strip().isdigit():
                start, end = int(parts[0].strip()), int(parts[1].strip())
                start = max(1, min(start, MAX_NEST_INDEX))
                end = max(1, min(end, MAX_NEST_INDEX))
                step = 1 if start <= end else -1
                indices.update(range(start, end + step, step))
        elif token.isdigit():
            val = int(token)
            if 1 <= val <= MAX_NEST_INDEX:
                indices.add(val)
    return indices if indices else None


@dataclass
class NestTarget:
    box: object
    cache_key: str


class NightmareNestTask(WWOneTimeTask, BaseCombatTask):
    max_nest_deaths = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 0.1
        self.target_enemy_time_out = 10
        self.name = "🌙 Nightmare Nest Task"
        self.description = "Auto Farm all Nightmare Nest"
        self.support_schedule_task = True
        self.count_re = re.compile(r"(\d{1,2})/(\d{1,2})")
        self.queues = []
        self._capture_success = False
        self._capture_mode = False
        self._unreachable_nests = set()
        self._nest_deaths = {}
        self._discovered_nests = {'canxiang': [], 'mengyan': []}
        self.default_config.update({
            'Which to Farm': ['Nightmare Purification', 'Tacet Discord Nest'],
            'Echo Pickup Method': 'Walk',
            ONLY_NESTS: '',
        })
        self.find_echo_method = self.get_find_echo_methods()
        self.config_description[ONLY_NESTS] = (
            'Only farm nests with these 1-based indices (e.g. 1,2,3 or 1-5). Leave empty to farm all.')
        self.config_type['Which to Farm'] = {'type': "multi_selection",
                                             'options': ['Nightmare Purification', 'Tacet Discord Nest']}
        self.config_type['Echo Pickup Method'] = {'type': "drop_down", 'options': self.find_echo_method}

    def run(self):
        self._capture_mode = False
        self._capture_success = False
        self._unreachable_nests.clear()
        self._nest_deaths.clear()
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self._init_queue()
        self.log_info(self.tr('opened gray_book_boss'))
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
        self.ensure_main(time_out=30)

    def run_capture_mode(self):
        self._capture_mode = True
        self._capture_success = False
        self._unreachable_nests.clear()
        self._nest_deaths.clear()
        WWOneTimeTask.run(self)
        self.ensure_main(time_out=30)
        self._init_queue()
        self.log_info(self.tr('opened gray_book_boss'))
        while nest := self.get_nest_to_go():
            self.combat_nest(nest)
            if self._capture_success:
                break
        self.ensure_main(time_out=30)

    def on_combat_check(self):
        if self._capture_mode:
            self.pick_f(handle_claim=False)
            if self.has_echo_notification():
                return self.reset_to_false(reason='echo captured')
        return True

    def has_echo_notification(self):
        if self.find_best_match_in_box(self.box_of_screen(0.078, 0.488, 0.094, 0.514),
                                       ['char_1_text', 'char_3_text'], 0.6,
                                       frame_processor=convert_image_to_negative):
            self._capture_success = True
        return self._capture_success

    def combat_nest(self, nest):
        target_box = nest.box if isinstance(nest, NestTarget) else nest
        self.click(target_box, after_sleep=2)
        feature = self.wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom', *TEAM_SCREEN_FEATURES],
                                    time_out=10, settle_time=0.5, raise_if_not_found=True)
        is_team = feature.name in TEAM_SCREEN_FEATURES
        if is_team:
            self.click_team_challenge()
            self.wait_in_team_and_world(time_out=120)
        else:
            if not self._travel_to_nest_or_skip(nest):
                return
            self.sleep(1)
            while self.find_f_with_text():
                self.send_key('f', after_sleep=1)
                self.wait_in_team_and_world(time_out=40, raise_if_not_found=False)
            self.sleep(2)
            self.run_until(self.in_combat, 'w', time_out=10, running=False, target=True)
        wait_combat_time = 10
        while True:
            try:
                need_find = self.combat_once(wait_combat_time=wait_combat_time, target=True,
                                             raise_if_not_found=False)
            except CharRevivedException:
                if isinstance(nest, NestTarget):
                    deaths = self._nest_deaths.get(nest.cache_key, 0) + 1
                    self._nest_deaths[nest.cache_key] = deaths
                    if deaths >= self.max_nest_deaths:
                        self._unreachable_nests.add(nest.cache_key)
                        self.log_info(self.tr('nightmare nest: died {deaths} times, skip this run: {cache_key}').format(deaths=deaths, cache_key=nest.cache_key),
                                      notify=True)
                        return
                self.log_info(self.tr('nightmare nest: death recovered, re-enter from F2 book'))
                return
            captured_early = False
            if self._capture_mode:
                if self._capture_success or self.wait_until(self.has_echo_notification, time_out=3):
                    self.log_info(self.tr('Captured echo during combat, skipping search.'))
                    captured_early = True
            if not captured_early:
                self.sleep(3)
                if need_find:
                    dropped = self.pick_echo_by_method(turn=True)
                else:
                    dropped = True
                self._capture_success = dropped
            if not self._should_continue_combat_after_pickup():
                break
            self.log_info(self.tr('nightmare nest: combat detected after pickup'))
            wait_combat_time = 1
        # 与刷全部一致：退本后再结束 combat_nest，避免还在巢穴内回 Daily/开书
        if is_team:
            self.esc_world_confirm()
        self.sleep(1)

    def _should_continue_combat_after_pickup(self):
        return not self._capture_mode and self.wait_combat(
            target=True, time_out=3, raise_if_not_found=False)

    def _travel_to_nest_or_skip(self, nest):
        travel = self.wait_until(self._find_travel_button, raise_if_not_found=False, time_out=1)
        if travel:
            self.click(travel, after_sleep=1)
            if confirm := self._find_first_feature(CONFIRM_FEATURES, threshold=0.6):
                self.click(confirm, after_sleep=1)

        button_still_visible = travel and self.find_one(travel.name, threshold=0.7)
        if travel and not button_still_visible and self.wait_in_team_and_world(
                time_out=120, raise_if_not_found=False):
            return True

        if isinstance(nest, NestTarget):
            self._unreachable_nests.add(nest.cache_key)
            self.log_info(self.tr('nightmare nest unreachable, skip this run: {cache_key}').format(cache_key=nest.cache_key))
        else:
            self.log_info(self.tr('nightmare nest unreachable, skip this run'))
        self.back(after_sleep=1)
        return False

    def _find_travel_button(self):
        return self._find_first_feature(TRAVEL_FEATURES, threshold=0.7)

    def _find_first_feature(self, feature_names, threshold):
        for feature_name in feature_names:
            if feature := self.find_one(feature_name, threshold=threshold):
                return feature

    def get_nest_to_go(self):
        self.openF2Book("gray_book_boss")

        while self.queues:
            self.queues[0]()
            if nest := self.find_nest():
                return nest
            self.queues.pop(0)

    def _init_queue(self):
        self._discovered_nests = {'canxiang': [], 'mengyan': []}
        quests = self.config.get('Which to Farm') or ['Nightmare Purification', 'Tacet Discord Nest']
        actions = []
        if 'Tacet Discord Nest' in quests:
            actions.append(self.go_nest)
            actions.append(self.go_nest_scroll)
        if 'Nightmare Purification' in quests:
            actions.append(self.go_nightmare)
            actions.append(self.go_nightmare_scroll)
        self.queues = actions

    def go_nightmare(self):
        self.open_boss_book('mengyan')
        self.log_info(self.tr('go nightmare'))

    def go_nightmare_scroll(self):
        self.open_boss_book('mengyan')
        self.click(3737 / 3840, 0.54, after_sleep=1)
        self.log_info(self.tr('go nightmare scroll'))

    def go_nest(self):
        self.open_boss_book('canxiang')

    def go_nest_scroll(self):
        self.open_boss_book('canxiang')
        self.click(0.9730, 0.8806, after_sleep=1)

    @staticmethod
    def _get_nest_name_for_count(count_box, all_boxes):
        candidates = [b for b in all_boxes if count_box.y - count_box.height * 4.0 <= b.y <= count_box.y]
        if not candidates:
            return None
        for b in candidates:
            if b.name and any(kw in b.name for kw in ['聚落', 'Nest']):
                return b.name.strip()
        candidates.sort(key=lambda b: count_box.y - b.y)
        return candidates[0].name.strip() if candidates[0].name else None

    def find_nest(self):
        wanted_indices = parse_nest_indices((getattr(self, 'config', None) or {}).get(ONLY_NESTS))
        counts = self.ocr(0.35, 0.13, 1, 0.96, match=self.count_re)
        if not counts:
            return None

        counts = sorted(counts, key=lambda c: c.y)
        action_name = self.queues[0].__name__ if getattr(self, 'queues', None) else 'unknown'
        category = 'mengyan' if 'nightmare' in action_name else 'canxiang'
        if not hasattr(self, '_discovered_nests') or self._discovered_nests is None:
            self._discovered_nests = {'canxiang': [], 'mengyan': []}
        discovered = self._discovered_nests.setdefault(category, [])

        all_boxes = self.ocr(0.35, 0.13, 1, 0.96) if wanted_indices is not None else []

        for count_box in counts:
            if wanted_indices is not None:
                nest_name = self._get_nest_name_for_count(count_box, all_boxes)
                nest_id = nest_name or f"{action_name}:{round(count_box.y, 2)}"
                if nest_id not in discovered:
                    discovered.append(nest_id)
                nest_index = discovered.index(nest_id) + 1
                if nest_index not in wanted_indices:
                    continue

            for match in re.finditer(self.count_re, count_box.name):
                numerator = match.group(1)
                denominator = match.group(2)
                if numerator != denominator and denominator in ['24', '36', '48', '41'] and numerator == '0':
                    cache_key = self._make_nest_cache_key(count_box, denominator)
                    if cache_key in self._unreachable_nests:
                        self.log_info(self.tr('skip cached unreachable nightmare nest: {cache_key}').format(cache_key=cache_key))
                        continue
                    self.log_info(self.tr('{count_box} is not complete').format(count_box=count_box))
                    count_box.x = self.width_of_screen(0.9)
                    count_box.y -= count_box.height * 0.9
                    count_box.height = 1
                    count_box.width = 1
                    return NestTarget(count_box, cache_key)

    def _make_nest_cache_key(self, count_box, denominator):
        action_name = self.queues[0].__name__ if self.queues else 'unknown'
        screen_height = max(self.height_of_screen(1), 1)
        row_y = (count_box.y + count_box.height / 2) / screen_height
        row_slot = round(row_y / 0.02)
        # 使用粗粒度行槽位，避免 OCR 坐标轻微抖动导致同一目标被重复点击。
        return f'{action_name}:{denominator}:{row_slot}'


def convert_image_to_negative(img):
    to_gray = False
    _mat = img
    if len(_mat.shape) == 3:
        to_gray = True
        _mat = cv2.cvtColor(_mat, cv2.COLOR_BGR2GRAY)
    _, _mat = cv2.threshold(_mat, 80, 255, cv2.THRESH_BINARY)
    _mat = cv2.bitwise_not(_mat)
    if to_gray:
        _mat = cv2.cvtColor(_mat, cv2.COLOR_GRAY2BGR)
    return _mat


from ok import run_task
from config import config

if __name__ == "__main__":
    run_task(config, task=NightmareNestTask, debug=True)
