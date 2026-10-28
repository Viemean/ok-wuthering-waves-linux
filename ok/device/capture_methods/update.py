from ok.util.logger import Logger
from ok.device.capture_methods.linux_capture import LinuxCaptureMethod
from ok.device.capture_methods.linux_vulkan_capture import LinuxVulkanCaptureMethod

logger = Logger.get_logger(__name__)


def update_capture_method(config, capture_method, hwnd, exit_event=None, selected_method=None):
    try:
        # [LINUX-PORT-CRITICAL] Default to Vulkan Layer, preserve X11_Direct as fallback
        target_cls = LinuxCaptureMethod if selected_method == 'X11_Direct' else LinuxVulkanCaptureMethod
        return get_capture(capture_method, target_cls, hwnd, exit_event)
    except Exception as e:
        logger.error(f'update_capture_method exception, return None: {e}')
        return None


def get_capture(capture_method, target_method, hwnd, exit_event):
    if not isinstance(capture_method, target_method):
        if capture_method is not None:
            capture_method.close()
        capture_method = target_method(hwnd)
    capture_method.hwnd_window = hwnd
    capture_method.exit_event = exit_event
    return capture_method
