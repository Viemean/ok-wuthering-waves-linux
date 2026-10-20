"""Cross-platform task schedule metadata and cache management."""

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from ok.util.config import Config

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    ONCE = "Once"
    CUSTOM = "Custom"


class TaskStatus(Enum):
    READY = "Ready"
    RUNNING = "Running"
    DISABLED = "Disabled"
    UNKNOWN = "Unknown"


@dataclass
class ScheduleTaskInfo:
    name: str
    path: str = ""
    enabled: bool = False
    status: str = "Unknown"
    trigger_type: str = ""
    next_run_time: str = ""
    last_run_time: str = ""
    last_result: int = 0
    actions: str = ""
    author: str = ""
    created_time: str = ""
    description: str = ""
    xml_config: str = ""
    task_index: int = -1
    task_identifier: Optional[str] = ""
    interval_days: int = 0
    interval_hours: int = 0
    read_only: bool = False

    def to_dict(self):
        return asdict(self)


def normalize_trigger_type(raw_type: str) -> TriggerType:
    value = str(raw_type or "").strip()
    lowered = value.lower()
    if value in (TriggerType.DAILY.value, "2") or "daily" in lowered:
        return TriggerType.DAILY
    if value in (TriggerType.WEEKLY.value, "3") or "weekly" in lowered:
        return TriggerType.WEEKLY
    if value in (TriggerType.MONTHLY.value, "4", "5", "6") or "monthly" in lowered:
        return TriggerType.MONTHLY
    if value in (TriggerType.ONCE.value, "1") or "once" in lowered or "time" in lowered:
        return TriggerType.ONCE
    if value == TriggerType.CUSTOM.value or "custom" in lowered:
        return TriggerType.CUSTOM
    return TriggerType.DAILY


def infer_trigger_type(raw_type: str, xml_config: str = "", interval_days: int = 0,
                       interval_hours: int = 0) -> TriggerType:
    if interval_hours > 0 or interval_days > 1:
        return TriggerType.CUSTOM
    trigger = normalize_trigger_type(raw_type)
    raw_value = str(raw_type or "").strip()
    if raw_value and (raw_value.isdigit() or raw_value.lower() in {
            "daily", "weekly", "monthly", "once", "custom"}):
        return trigger
    xml = str(xml_config or "").lower()
    if "<repetition>" in xml and "<interval>pt" in xml and "h</interval>" in xml:
        return TriggerType.CUSTOM
    if "<schedulebyweek" in xml:
        return TriggerType.WEEKLY
    if "<schedulebymonth" in xml:
        return TriggerType.MONTHLY
    if "<timetrigger" in xml and "<repetition>" not in xml:
        return TriggerType.ONCE
    if "<schedulebyday" in xml:
        return TriggerType.DAILY
    return trigger


def trigger_type_for_task(task_info: ScheduleTaskInfo) -> TriggerType:
    return infer_trigger_type(
        task_info.trigger_type, task_info.xml_config,
        task_info.interval_days, task_info.interval_hours)


def format_next_run_time(next_run_time: str) -> str:
    value = str(next_run_time or "")
    if not value:
        return "-"
    if len(value) <= 16:
        return value
    parts = value.split()
    return " ".join(parts[:2])[:16] if len(parts) >= 2 else value[:16]


TASK_ARG_PATTERN = re.compile(r"(^|\s)-t\s+([^\s<]+)")


def extract_task_target(*texts) -> Optional[str]:
    for text in texts:
        if not text:
            continue
        match = TASK_ARG_PATTERN.search(str(text))
        if match:
            return match.group(2).strip()
    return None


def resolve_schedule_task_index(identifier: str, tasks) -> int:
    tasks = list(tasks or [])
    target = identifier.lower()
    matches = [index for index, task in enumerate(tasks, 1)
               if f"{type(task).__module__}.{type(task).__name__}".lower() == target]
    if not matches:
        matches = [index for index, task in enumerate(tasks, 1)
                   if type(task).__name__.lower() == target.rsplit(".", 1)[-1]]
    return matches[0] if len(matches) == 1 else -1


def parse_task_target_fields(xml_config: str = "", actions: str = "") -> tuple:
    target = extract_task_target(actions, xml_config)
    if not target:
        return -1, ""
    if target.isdigit():
        return int(target), ""
    if "." in target:
        return -1, target
    return -1, ""


class WindowsScheduleCache:
    def __init__(self, config: Config = None):
        self.config = config or Config()
        default_cache_dir = self.config.get("config_folder", "configs")
        self.cache_dir = Path(default_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "schedule_tasks_cache.json"
        self.lock = threading.RLock()
        self.cache: Dict[str, ScheduleTaskInfo] = {}
        self.load_cache()

    def load_cache(self):
        with self.lock:
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.cache = {
                        k: ScheduleTaskInfo(**v) for k, v in data.items()
                    }
                except Exception as e:
                    logger.warning(f"Failed to load schedule cache: {e}")
                    self.cache = {}

    def save_cache(self):
        with self.lock:
            try:
                data = {k: v.to_dict() for k, v in self.cache.items()}
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Failed to save schedule cache: {e}")

    def get_all(self) -> List[ScheduleTaskInfo]:
        with self.lock:
            return list(self.cache.values())

    def get(self, task_name: str) -> Optional[ScheduleTaskInfo]:
        with self.lock:
            return self.cache.get(task_name)

    def add_or_update(self, task_info: ScheduleTaskInfo):
        with self.lock:
            self.cache[task_info.name] = task_info
            self.save_cache()

    def delete(self, task_name: str) -> bool:
        with self.lock:
            if task_name in self.cache:
                del self.cache[task_name]
                self.save_cache()
                return True
            return False

    def clear(self):
        with self.lock:
            self.cache.clear()
            self.save_cache()


class WindowsScheduleManager:
    """Safe schedule manager on Linux using local json cache."""
    SCHEDULE_ROOT_PATH = "\\ok-script\\"

    def __init__(self, app_name: str = "ok-script", config: Config = None):
        self.app_name = app_name
        self.config = config or Config()
        self.cache = WindowsScheduleCache(self.config)
        self.update_callbacks = []

    def is_available(self) -> bool:
        return False

    def register_update_callback(self, callback):
        if callback not in self.update_callbacks:
            self.update_callbacks.append(callback)

    def start_background_sync(self, interval: int = 60):
        pass

    def stop_background_sync(self):
        pass

    def sync_tasks(self, force: bool = False):
        pass

    def query_all_tasks(self, force_refresh: bool = False, force_sync: bool = False) -> List[ScheduleTaskInfo]:
        return self.cache.get_all()

    def get_task(self, task_name: str) -> Optional[ScheduleTaskInfo]:
        return self.cache.get(task_name)

    def create_task(self, *args, **kwargs) -> bool:
        logger.warning("Windows Task Scheduler is not available in Linux runtime")
        return False

    def update_task(self, *args, **kwargs) -> bool:
        return False

    def delete_task(self, task_name: str) -> bool:
        return self.cache.delete(task_name)

    def enable_task(self, task_name: str, enabled: bool = True) -> bool:
        task = self.cache.get(task_name)
        if task:
            task.enabled = enabled
            self.cache.add_or_update(task)
            return True
        return False

    def disable_task(self, task_name: str) -> bool:
        return self.enable_task(task_name, False)

    def run_task(self, task_name: str) -> bool:
        return False
