import os
import ctypes
import subprocess
import tempfile
import cv2
import numpy as np

from ok.device.capture_methods.base import BaseCaptureMethod, BaseWindowsCaptureMethod
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


class _XShmCaptureBackend:
    def __init__(self):
        self.lib = None
        self.x11 = None
        self.display = None
        self.screen = 0
        self.ctx = None
        self.width = 0
        self.height = 0
        self.available = False
        self._buf_ptr = ctypes.POINTER(ctypes.c_uint8)()
        self._stride = ctypes.c_int()

        self._init_library()

    def _init_library(self):
        try:
            cur_dir = os.path.dirname(os.path.abspath(__file__))
            so_path = os.path.join(cur_dir, "bin", "ok-xshm-capture.so")
            c_path = os.path.join(cur_dir, "xshm", "xshm_capture.c")

            if not os.path.exists(so_path) and os.path.exists(c_path):
                os.makedirs(os.path.dirname(so_path), exist_ok=True)
                compile_cmd = [
                    "gcc", "-O3", "-fPIC", "-shared",
                    c_path, "-lX11", "-lXext", "-o", so_path
                ]
                subprocess.run(compile_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(so_path):
                self.lib = ctypes.cdll.LoadLibrary(so_path)
                self.x11 = ctypes.cdll.LoadLibrary("libX11.so.6")

                self.x11.XOpenDisplay.restype = ctypes.c_void_p
                self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
                self.x11.XDefaultScreen.restype = ctypes.c_int
                self.x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
                self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

                self.lib.xshm_init.restype = ctypes.c_void_p
                self.lib.xshm_init.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]

                self.lib.xshm_capture.restype = ctypes.c_int
                self.lib.xshm_capture.argtypes = [
                    ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                    ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)), ctypes.POINTER(ctypes.c_int)
                ]

                self.lib.xshm_destroy.argtypes = [ctypes.c_void_p]

                self.display = self.x11.XOpenDisplay(None)
                if self.display:
                    self.screen = self.x11.XDefaultScreen(self.display)
                    self.available = True
                    logger.info("X11 MIT-SHM capture backend initialized")
        except Exception as e:
            logger.debug(f"Failed to initialize X11 MIT-SHM capture backend: {e}")
            self.available = False

    def ensure_context(self, width, height):
        if not self.available or not self.display:
            return False

        if self.ctx and (self.width != width or self.height != height):
            self.lib.xshm_destroy(self.ctx)
            self.ctx = None

        if self.ctx is None:
            self.ctx = self.lib.xshm_init(self.display, self.screen, width, height)
            if self.ctx:
                self.width = width
                self.height = height
            else:
                return False

        return True

    def capture(self, hwnd, width, height):
        if not self.ensure_context(width, height):
            return None

        ret = self.lib.xshm_capture(
            self.ctx, hwnd, 0, 0,
            ctypes.byref(self._buf_ptr), ctypes.byref(self._stride)
        )
        if ret == 1 and bool(self._buf_ptr):
            stride = self._stride.value
            stride_pixels = stride // 4
            arr = np.ctypeslib.as_array(self._buf_ptr, shape=(height, stride_pixels, 4))
            if stride_pixels == width:
                return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            else:
                return cv2.cvtColor(arr[:, :width], cv2.COLOR_BGRA2BGR)
        return None

    def close(self):
        if self.lib and self.ctx:
            try:
                self.lib.xshm_destroy(self.ctx)
            except Exception:
                pass
            self.ctx = None
        if self.x11 and self.display:
            try:
                self.x11.XCloseDisplay(self.display)
            except Exception:
                pass
            self.display = None
        self.available = False


class LinuxCaptureMethod(BaseWindowsCaptureMethod):
    name = "X11_Direct"
    description = "XWayland 窗口直接内存采集"

    def __init__(self, hwnd_window, exit_event=None):
        super().__init__(hwnd_window)
        self.exit_event = exit_event
        self._temp_img_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        self._shm_backend = _XShmCaptureBackend()

    def connected(self):
        return self.hwnd_window is not None and self.hwnd_window.exists and self.hwnd_window.hwnd > 0

    def clickable(self):
        return self.hwnd_window is not None and self.hwnd_window.visible

    def get_abs_cords(self, x, y):
        if self.hwnd_window:
            return self.hwnd_window.get_abs_cords(x, y)
        return int(x), int(y)

    def do_get_frame(self):
        if not self.connected():
            return None

        w, h = self.hwnd_window.width, self.hwnd_window.height
        hwnd = self.hwnd_window.hwnd

        # 1. Primary path: X11 MIT-SHM shared memory capture
        if self._shm_backend.available and w > 0 and h > 0 and hwnd > 0:
            try:
                frame = self._shm_backend.capture(hwnd, w, h)
                if frame is not None:
                    return frame
            except Exception as e:
                logger.debug(f"XShm capture failed, falling back: {e}")

        # 2. Secondary path: Direct XWayland window buffer read via Xlib
        try:
            import Xlib.X
            win = self.hwnd_window.window_obj
            if win is not None:
                geom = win.get_geometry()
                raw = win.get_image(0, 0, geom.width, geom.height, Xlib.X.ZPixmap, 0xffffffff)
                if raw and raw.data:
                    arr = np.frombuffer(raw.data, dtype=np.uint8).reshape((geom.height, geom.width, 4))
                    return arr[:, :, :3]  # Return BGR
        except Exception as e:
            logger.debug(f"Xlib direct frame grab fallback: {e}")

        # 3. Tertiary path: Spectacle area capture (KDE Wayland standard)
        try:
            x, y = self.hwnd_window.x, self.hwnd_window.y
            if w > 0 and h > 0:
                ret = subprocess.run(
                    ["spectacle", "-b", "-n", "-o", self._temp_img_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
                if ret.returncode == 0:
                    img = cv2.imread(self._temp_img_file)
                    if img is not None and img.shape[0] >= y + h and img.shape[1] >= x + w:
                        return img[y:y+h, x:x+w]
                    return img
        except Exception as e:
            logger.debug(f"Spectacle screenshot fallback error: {e}")

        return None

    def close(self):
        if self._shm_backend:
            self._shm_backend.close()

        if os.path.exists(self._temp_img_file):
            try:
                os.remove(self._temp_img_file)
            except OSError:
                pass
