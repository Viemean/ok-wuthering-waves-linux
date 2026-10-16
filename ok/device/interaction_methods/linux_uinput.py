import time
import evdev
from evdev import ecodes
from pynput.mouse import Controller as MouseController

from ok.device.interaction_methods.base import BaseInteraction
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


class LinuxUinputInteraction(BaseInteraction):
    """Hardware-level virtual input device via Linux /dev/uinput (evdev)."""
    name = "UInput"
    description = "Linux UInput 虚拟键鼠硬件级输入"

    KEY_MAP = {
        'a': ecodes.KEY_A, 'b': ecodes.KEY_B, 'c': ecodes.KEY_C, 'd': ecodes.KEY_D,
        'e': ecodes.KEY_E, 'f': ecodes.KEY_F, 'g': ecodes.KEY_G, 'h': ecodes.KEY_H,
        'i': ecodes.KEY_I, 'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L,
        'm': ecodes.KEY_M, 'n': ecodes.KEY_N, 'o': ecodes.KEY_O, 'p': ecodes.KEY_P,
        'q': ecodes.KEY_Q, 'r': ecodes.KEY_R, 's': ecodes.KEY_S, 't': ecodes.KEY_T,
        'u': ecodes.KEY_U, 'v': ecodes.KEY_V, 'w': ecodes.KEY_W, 'x': ecodes.KEY_X,
        'y': ecodes.KEY_Y, 'z': ecodes.KEY_Z,
        '0': ecodes.KEY_0, '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3,
        '4': ecodes.KEY_4, '5': ecodes.KEY_5, '6': ecodes.KEY_6, '7': ecodes.KEY_7,
        '8': ecodes.KEY_8, '9': ecodes.KEY_9,
        'space': ecodes.KEY_SPACE, 'esc': ecodes.KEY_ESC, 'enter': ecodes.KEY_ENTER,
        'return': ecodes.KEY_ENTER, 'tab': ecodes.KEY_TAB,
        'lshift': ecodes.KEY_LEFTSHIFT, 'rshift': ecodes.KEY_RIGHTSHIFT,
        'shift': ecodes.KEY_LEFTSHIFT, 'lctrl': ecodes.KEY_LEFTCTRL,
        'rctrl': ecodes.KEY_RIGHTCTRL, 'ctrl': ecodes.KEY_LEFTCTRL,
        'lalt': ecodes.KEY_LEFTALT, 'ralt': ecodes.KEY_RIGHTALT, 'alt': ecodes.KEY_LEFTALT,
        'f1': ecodes.KEY_F1, 'f2': ecodes.KEY_F2, 'f3': ecodes.KEY_F3,
        'f4': ecodes.KEY_F4, 'f5': ecodes.KEY_F5, 'f6': ecodes.KEY_F6,
        'f7': ecodes.KEY_F7, 'f8': ecodes.KEY_F8, 'f9': ecodes.KEY_F9,
        'f10': ecodes.KEY_F10, 'f11': ecodes.KEY_F11, 'f12': ecodes.KEY_F12,
    }

    BTN_MAP = {
        'left': ecodes.BTN_LEFT,
        'right': ecodes.BTN_RIGHT,
        'middle': ecodes.BTN_MIDDLE,
    }

    def __init__(self, capture, hwnd_window=None):
        super().__init__(capture)
        self.hwnd_window = hwnd_window
        self.mouse = MouseController()
        self._uinput = None
        self._init_uinput()

    def _init_uinput(self):
        try:
            capabilities = {
                ecodes.EV_KEY: list(self.KEY_MAP.values()) + list(self.BTN_MAP.values()),
                ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL],
            }
            self._uinput = evdev.UInput(capabilities, name="ok-ww-uinput")
            logger.info("LinuxUinputInteraction device initialized successfully")
        except Exception as e:
            logger.error(f"Failed to open /dev/uinput: {e}")

    def _to_code(self, key):
        if isinstance(key, int):
            return key
        key_str = str(key).lower()
        return self.KEY_MAP.get(key_str)

    def _ensure_focus(self):
        if self.hwnd_window and not self.hwnd_window.is_foreground():
            self.hwnd_window.focus()
            time.sleep(0.05)

    def send_key(self, key, down_time=0.02):
        super().send_key(key, down_time)
        code = self._to_code(key)
        if code and self._uinput:
            self._ensure_focus()
            self._uinput.write(ecodes.EV_KEY, code, 1)
            self._uinput.syn()
            time.sleep(down_time)
            self._uinput.write(ecodes.EV_KEY, code, 0)
            self._uinput.syn()

    def send_key_down(self, key):
        code = self._to_code(key)
        if code and self._uinput:
            self._ensure_focus()
            self._uinput.write(ecodes.EV_KEY, code, 1)
            self._uinput.syn()

    def send_key_up(self, key):
        code = self._to_code(key)
        if code and self._uinput:
            self._uinput.write(ecodes.EV_KEY, code, 0)
            self._uinput.syn()

    def move(self, x, y):
        if self.hwnd_window:
            abs_x, abs_y = self.hwnd_window.get_abs_cords(x, y)
        else:
            abs_x, abs_y = int(x), int(y)
        self.mouse.position = (abs_x, abs_y)
        time.sleep(0.01)

    def move_rel(self, dx, dy):
        """Relative mouse movement for 3D camera rotation."""
        if self._uinput:
            self._ensure_focus()
            self._uinput.write(ecodes.EV_REL, ecodes.REL_X, int(dx))
            self._uinput.write(ecodes.EV_REL, ecodes.REL_Y, int(dy))
            self._uinput.syn()

    def click(self, x=-1, y=-1, move_back=False, name=None, move=True, down_time=0.05, key="left"):
        old_pos = self.mouse.position if move_back else None
        if x >= 0 and y >= 0 and move:
            self.move(x, y)
        self._ensure_focus()
        btn = self.BTN_MAP.get(str(key).lower(), ecodes.BTN_LEFT)
        if self._uinput:
            self._uinput.write(ecodes.EV_KEY, btn, 1)
            self._uinput.syn()
            time.sleep(down_time)
            self._uinput.write(ecodes.EV_KEY, btn, 0)
            self._uinput.syn()
        if old_pos:
            self.mouse.position = old_pos

    def scroll(self, x, y, scroll_amount):
        if x >= 0 and y >= 0:
            self.move(x, y)
        if self._uinput:
            self._uinput.write(ecodes.EV_REL, ecodes.REL_WHEEL, int(scroll_amount))
            self._uinput.syn()

    def input_text(self, text):
        for ch in text:
            self.send_key(ch, down_time=0.01)
            time.sleep(0.01)

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        """Press and hold mouse button."""
        if x >= 0 and y >= 0:
            self.move(x, y)
        self._ensure_focus()
        btn = self.BTN_MAP.get(str(key).lower(), ecodes.BTN_LEFT)
        if self._uinput:
            self._uinput.write(ecodes.EV_KEY, btn, 1)
            self._uinput.syn()

    def mouse_up(self, key="left"):
        """Release mouse button."""
        self._ensure_focus()
        btn = self.BTN_MAP.get(str(key).lower(), ecodes.BTN_LEFT)
        if self._uinput:
            self._uinput.write(ecodes.EV_KEY, btn, 0)
            self._uinput.syn()

    def swipe(self, x1, y1, x2, y2, duration=200, settle_time=0):
        """Simulate mouse drag/swipe."""
        self.move(x1, y1)
        time.sleep(0.05)
        self.mouse_down(key="left")
        dx = x2 - x1
        dy = y2 - y1
        steps = max(int(duration / 20), 1)
        step_dx = dx / steps
        step_dy = dy / steps
        for i in range(1, steps + 1):
            self.move(x1 + int(i * step_dx), y1 + int(i * step_dy))
            time.sleep(0.01)
        self.move(x2, y2)
        if settle_time:
            time.sleep(settle_time)
        self.mouse_up(key="left")

    def clickable(self):
        return self.hwnd_window is not None and self.hwnd_window.exists

    def should_capture(self):
        return True

    def on_run(self):
        self._ensure_focus()

    def on_destroy(self):
        if self._uinput:
            try:
                self._uinput.close()
            except Exception:
                pass
            self._uinput = None

    def close(self):
        self.on_destroy()

