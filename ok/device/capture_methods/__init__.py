import sys

from ok.device.capture_methods.adb import ADBCaptureMethod
from ok.device.capture_methods.base import BaseCaptureMethod, BaseWindowsCaptureMethod
from ok.device.capture_methods.browser import BrowserCaptureMethod, BrowserWindowAdapter
from ok.device.capture_methods.image import ImageCaptureMethod
from ok.device.capture_methods.nemu_ipc import NemuIpcCaptureMethod
from ok.device.capture_methods.types import ColorChannel, ImageShape, decimal, is_digit, is_valid_hwnd, get_crop_point
from ok.device.capture_methods.update import get_capture, update_capture_method
from ok.device.capture_methods.linux_window import LinuxWindow
from ok.device.capture_methods.linux_capture import LinuxCaptureMethod
from ok.device.audio_methods.linux_audio import get_mute_state, set_mute_state

HwndWindow = LinuxWindow

