import sys
from enum import IntEnum

class ImageShape(IntEnum):
    Y = 0
    X = 1
    Channels = 2



class ColorChannel(IntEnum):
    Blue = 0
    Green = 1
    Red = 2
    Alpha = 3



def decimal(value: float):
    return f"{int(value * 100) / 100}".ljust(4, "0")



def is_digit(value: str | int | None):
    if value is None:
        return False
    try:
        return 0 <= int(value) <= 9
    except (ValueError, TypeError):
        return False



def is_valid_hwnd(hwnd: int):
    return bool(hwnd and hwnd > 0)


def get_crop_point(frame_width, frame_height, target_width, target_height):
    x = round((frame_width - target_width) / 2)
    y = (frame_height - target_height) - x
    return x, y
