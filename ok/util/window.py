"""Cross-platform window helper utilities."""

import os
import re
from typing import List, Tuple

from ok.util.logger import Logger

logger = Logger.get_logger("window")


def windows_graphics_available() -> bool:
    return False


def is_blank(image) -> bool:
    return not image.any()


def is_window_minimized(hwnd: int) -> bool:
    return False


def get_exe_by_hwnd(hwnd: int) -> Tuple[str, str, str]:
    return "", "", ""


def find_display(hmonitor, displays):
    for display in displays:
        if getattr(display, "hmonitor", None) == hmonitor:
            return display
    raise ValueError("Display not found")


def get_window_bounds(hwnd: int) -> Tuple[int, int, int, int, int, int, float]:
    return 0, 0, 0, 0, 0, 0, 1.0


def is_foreground_window(hwnd: int) -> bool:
    return False


def sort_hwnds_top_to_bottom(hwnds: list) -> list:
    return hwnds


def expand_clickable_hwnds(hwnds: list, main_hwnd: int = 0, top_hwnd_class=None) -> list:
    return hwnds


def show_title_bar(hwnd: int) -> bool:
    return True


def resize_window(hwnd: int, width: int, height: int) -> bool:
    return True


def ratio_text_to_number(supported_ratio: str) -> float:
    supported_ratio_list = [int(i) for i in supported_ratio.split(":")]
    return supported_ratio_list[0] / supported_ratio_list[1]


def compare_path_safe(str1: str, str2: str) -> bool:
    if str1 is None and str2 is None:
        return True
    if str1 is None or str2 is None:
        return False
    return str1.replace("\\", "/").lower() == str2.replace("\\", "/").lower()


def get_player_id_from_cmdline(cmdline: list) -> int:
    for i in range(len(cmdline)):
        if i != 0 and cmdline[i].isdigit():
            return int(cmdline[i])
    for i in range(len(cmdline)):
        if i != 0:
            value = re.search(r"index=(\d+)", cmdline[i])
            if value is not None:
                return int(value.group(1))
    return 0


def find_hwnd(title=None, exe_names=None, frame_width=0, frame_height=0, player_id=-1,
              class_name=None, selected_hwnd=0, top_hwnd_class=None, last_hwnd=0):
    return None, 0, None, 0, 0, 0, 0, []


def find_all_visible_windows() -> List[Tuple[int, str, str, str]]:
    return []
