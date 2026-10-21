import re
import threading
import time

from ok.core.events import communicate
from ok.util.GlobalConfig import basic_options
from ok.util.logger import Logger
from ok.device.audio_methods.linux_audio import get_mute_state, set_mute_state

logger = Logger.get_logger(__name__)


class LinuxWindow:
    """Dynamic window detection and tracking for Linux (X11 / XWayland / Lutris / Proton)."""

    def __init__(self, exit_event=None, title=None, exe_names=None, hwnd_class=None,
                 global_config=None, device_manager=None, **kwargs):
        self.app_exit_event = exit_event if hasattr(exit_event, "is_set") else None
        self.device_manager = device_manager
        self.global_config = global_config
        self.windows_capture_config = kwargs.get('windows_capture_config')
        self.mute_option = None
        if self.global_config:
            if hasattr(self.global_config, "get_config"):
                try:
                    self.mute_option = self.global_config.get_config(basic_options)
                    self.mute_option.validator = self.validate_mute_config
                except Exception as e:
                    logger.debug(f"Failed to bind mute_option validator: {e}")
            elif isinstance(self.global_config, dict):
                self.mute_option = self.global_config
        self.to_handle_mute = True
        self._last_active = None
        self.stop_event = threading.Event()

        self.title_pattern = title or re.compile(r"wuthering waves|鸣潮|Client-Win64-Shipping", re.IGNORECASE)
        self.exe_names = [e.lower() for e in exe_names] if isinstance(exe_names, list) else (
            [exe_names.lower()] if exe_names else ["client-win64-shipping.exe", "wutheringwaves.exe"]
        )
        self.hwnd_class = hwnd_class or "UnrealWindow"

        self.hwnd = 0
        self.window_obj = None
        self.display = None
        self.root = None

        self.exists = False
        self.visible = False
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.client_width = 0
        self.client_height = 0
        self.window_width = 0
        self.window_height = 0
        self.real_x_offset = 0
        self.real_y_offset = 0
        self.scaling = 1.0

        self.title = ""
        self.exe_full_path = None
        self.top_hwnd = 0
        self.frame_width = 0
        self.frame_height = 0
        self.frame_aspect_ratio = 0
        self.real_width = 0
        self.real_height = 0
        self.hwnds = []

        self._scan_window()

        self.thread = threading.Thread(target=self._update_loop, name="linux_window_update", daemon=True)
        self.thread.start()

    def update_frame_size(self, width, height):
        self.frame_width = width
        self.frame_height = height
        self.frame_aspect_ratio = width / height if height != 0 else 0

    def update_window(self, title=None, exe=None, frame_width=0, frame_height=0, player_id=-1, hwnd_class=None, top_hwnd_class=None):
        if title:
            self.title_pattern = title
        if exe:
            self.exe_names = [e.lower() for e in exe] if isinstance(exe, list) else [exe.lower()]
        if hwnd_class:
            self.hwnd_class = hwnd_class
        if frame_width and frame_height:
            self.update_frame_size(frame_width, frame_height)



    def _init_display(self):
        try:
            import Xlib.display
            if self.display is None:
                self.display = Xlib.display.Display()
                self.root = self.display.screen().root
            return True
        except Exception as e:
            logger.debug(f"Failed to initialize X11/XWayland display: {e}")
            return False

    def _update_loop(self):
        while not self.stop_event.is_set() and not (self.app_exit_event and self.app_exit_event.is_set()):
            try:
                self._scan_window()
                self.handle_mute()
            except Exception as e:
                logger.debug(f"LinuxWindow scan error: {e}")
            time.sleep(0.5)

    def _get_window_name(self, win):
        try:
            name = win.get_wm_name()
            if name:
                return name if isinstance(name, str) else name.decode("utf-8", errors="ignore")
            prop = win.get_full_property(self.display.intern_atom("_NET_WM_NAME"), 0)
            if prop and prop.value:
                val = prop.value
                return val if isinstance(val, str) else val.decode("utf-8", errors="ignore")
        except Exception:
            pass
        return ""

    def _get_window_class(self, win):
        try:
            cls = win.get_wm_class()
            if cls:
                return [c.lower() for c in cls if isinstance(c, str)]
        except Exception:
            pass
        return []

    def _match_window(self, win):
        name = self._get_window_name(win)
        classes = self._get_window_class(win)

        # Match by class
        for c in classes:
            for exe in self.exe_names:
                if exe in c:
                    return True, name
            if self.hwnd_class and self.hwnd_class.lower() in c:
                return True, name

        # Match by title
        if name:
            if isinstance(self.title_pattern, re.Pattern):
                if self.title_pattern.search(name):
                    return True, name
            elif str(self.title_pattern).lower() in name.lower():
                return True, name

        return False, name

    def _find_target_window(self, root_win):
        import Xlib.X

        candidates = []
        stack = [root_win]
        while stack:
            curr = stack.pop()
            try:
                attrs = curr.get_attributes()
                matched, name = self._match_window(curr)
                if matched:
                    geom = curr.get_geometry()
                    if geom.width > 100 and geom.height > 100:
                        candidates.append((curr, name, geom, attrs.map_state == Xlib.X.IsViewable))
                children = curr.query_tree().children
                stack.extend(children)
            except Exception:
                continue

        if not candidates:
            return None, "", None, False

        # Prefer viewable windows with largest area
        candidates.sort(key=lambda item: (item[3], item[2].width * item[2].height), reverse=True)
        return candidates[0]

    def _scan_window(self):
        if self.stop_event.is_set():
            return
        if not self._init_display():
            return

        try:
            target_win, name, geom, is_viewable = self._find_target_window(self.root)
            if target_win is not None:
                coords = target_win.translate_coords(self.root, 0, 0)
                is_new_game = (not self.exists) or (self.hwnd != target_win.id)
                changed = is_new_game or (self.width != geom.width) or (self.height != geom.height)

                self.window_obj = target_win
                self.hwnd = target_win.id
                self.exists = True
                self.visible = is_viewable
                self.title = name
                self.x = coords.x
                self.y = coords.y
                self.width = geom.width
                self.height = geom.height
                self.client_width = geom.width
                self.client_height = geom.height
                self.window_width = geom.width
                self.window_height = geom.height

                if changed:
                    logger.info(f"LinuxWindow detected game: {name} (0x{self.hwnd:x}) at ({self.x}, {self.y}) size: {self.width}x{self.height}")
                    if is_new_game:
                        self._trigger_game_restart()
                        try:
                            from ok.device.linux_proton_launcher import get_proton_launcher
                            launcher = get_proton_launcher()
                            if not launcher.can_launch():
                                detected = launcher.detect_running_game_env()
                                if detected:
                                    launcher.update_config(**{k: v for k, v in detected.items() if v})
                        except Exception as e:
                            logger.debug(f"Auto-sync proton env failed: {e}")
                    if self.device_manager:
                        device = self.device_manager.get_preferred_device()
                        if device:
                            device['connected'] = True
                            device['width'] = self.width
                            device['height'] = self.height
                            device['resolution'] = f"{self.width}x{self.height}"
                            communicate.adb_devices.emit(True)
                    communicate.window.emit(self.visible, self.x, self.y, self.width, self.height, self.width, self.height, self.scaling)
            else:
                if self.exists:
                    logger.info("LinuxWindow: target game window closed or lost")
                    self.exists = False
                    self.visible = False
                    self.hwnd = 0
                    self.window_obj = None
                    if self.device_manager:
                        device = self.device_manager.get_preferred_device()
                        if device:
                            device['connected'] = False
                            communicate.adb_devices.emit(True)
        except Exception as e:
            logger.debug(f"LinuxWindow _scan_window exception: {e}")

    def _trigger_game_restart(self):
        try:
            callback = None
            if self.windows_capture_config:
                callback = self.windows_capture_config.get('on_game_restart')
            elif self.device_manager and getattr(self.device_manager, 'windows_capture_config', None):
                callback = self.device_manager.windows_capture_config.get('on_game_restart')
            if callable(callback):
                callback()
        except Exception as e:
            logger.debug(f"on_game_restart callback error: {e}")

    def get_abs_cords(self, x, y):
        return int(self.x + x), int(self.y + y)

    def get_capture_origin(self):
        return int(self.x), int(self.y)

    def is_foreground(self):
        if not self.exists or not self.display or not self.root:
            return False
        try:
            prop = self.root.get_full_property(self.display.intern_atom("_NET_ACTIVE_WINDOW"), 0)
            if prop and prop.value:
                active_id = prop.value[0]
                if active_id == self.hwnd:
                    return True
                if self.window_obj:
                    try:
                        child_ids = [c.id for c in self.window_obj.query_tree().children]
                        if active_id in child_ids:
                            return True
                    except Exception:
                        pass
        except Exception:
            pass

        return False

    def focus(self):
        if not self.exists or not self.window_obj or not self.display or not self.root:
            return False
        try:
            import Xlib.X
            import Xlib.protocol.event
            net_active = self.display.intern_atom("_NET_ACTIVE_WINDOW")
            data = [1, Xlib.X.CurrentTime, 0, 0, 0]
            ev = Xlib.protocol.event.ClientMessage(
                window=self.hwnd,
                client_type=net_active,
                data=(32, data)
            )
            self.root.send_event(ev, event_mask=Xlib.X.SubstructureRedirectMask | Xlib.X.SubstructureNotifyMask)
            self.display.sync()
            return True
        except Exception as e:
            logger.debug(f"LinuxWindow focus error: {e}")
            return False

    def frame_ratio(self, size):
        return size

    def _get_mute_config_val(self) -> bool:
        if self.mute_option is not None:
            if hasattr(self.mute_option, "get"):
                return bool(self.mute_option.get('Mute Game while in Background', False))
        if self.global_config:
            if hasattr(self.global_config, "get_config"):
                try:
                    cfg = self.global_config.get_config(basic_options)
                    if cfg and hasattr(cfg, "get"):
                        return bool(cfg.get('Mute Game while in Background', False))
                except Exception:
                    pass
            if isinstance(self.global_config, dict):
                return bool(self.global_config.get('Mute Game while in Background', False))
        return False

    def validate_mute_config(self, key, value):
        if key == 'Mute Game while in Background':
            logger.info(f'validate_mute_config changed: {value}')
            if value:
                self.handle_mute(mute=True)
            else:
                logger.info('config changed unmute set_mute_state 0')
                self._last_active = None
                set_mute_state(self.hwnd, 0)
        return True, None

    def handle_mute(self, mute=None):
        if mute is None:
            mute = self._get_mute_config_val()
        if self.hwnd and self.to_handle_mute:
            if mute:
                is_active = self.is_foreground()
                if self._last_active != is_active:
                    self._last_active = is_active
                    logger.info(f"LinuxWindow foreground state changed: is_active={is_active}, setting mute={0 if is_active else 1}")
                    set_mute_state(self.hwnd, 0 if is_active else 1)
            else:
                if self._last_active is not None:
                    self._last_active = None
                    set_mute_state(self.hwnd, 0)

    def get_mute_state(self):
        return get_mute_state(self.hwnd)

    def set_mute_state(self, mute: int):
        return set_mute_state(self.hwnd, mute)

    @property
    def real_hwnd(self) -> int:
        return self.hwnd

    @property
    def pos_valid(self) -> bool:
        return self.exists and self.visible and self.width > 0 and self.height > 0

    def bring_to_front(self) -> bool:
        return self.focus()

    def do_update_window_size(self):
        self._scan_window()

    def try_resize_to(self, resize_to) -> bool:
        return False

    def get_top_window_cords(self, x, y):
        return self.get_abs_cords(x, y)

    def capture_target_signature(self):
        return (self.hwnd, self.x, self.y, self.width, self.height)

    def stop(self):
        self.stop_event.set()
        if self.hwnd and self._get_mute_config_val():
            logger.info("LinuxWindow exit: resetting mute state to 0")
            set_mute_state(self.hwnd, 0)
        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            self.thread.join(timeout=1.0)
        try:
            if self.display:
                self.display.close()
        except Exception:
            pass

    def close(self):
        self.stop()


