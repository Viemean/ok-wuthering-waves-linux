import socket
import struct
import array
import os
import mmap
import threading
import time
import cv2
import numpy as np

from ok.device.capture_methods.base import BaseWindowsCaptureMethod
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

# [LINUX-PORT-CRITICAL] Abstract domain socket for obs-vkcapture
SOCK_PATH = "\0/com/obsproject/vkcapture"

CLIENT_DATA_SIZE = 128
CONTROL_DATA_SIZE = 32
TEXTURE_DATA_SIZE = 128


class LinuxVulkanCaptureMethod(BaseWindowsCaptureMethod):
    name = "Vulkan"
    description = "Vulkan Layer 零拷贝直读"

    def __init__(self, hwnd_window, exit_event=None):
        super().__init__(hwnd_window)
        self.exit_event = exit_event

        self._server_sock = None
        self._conn = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._current_fd = -1
        self._mmap_buf = None
        self._width = 0
        self._height = 0
        self._stride = 0
        self._format = 0

        self._last_capture_time = 0.0
        self._min_frame_interval = 1.0 / 60.0  # 60 FPS

        self._init_server()

    def _init_server(self):
        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(SOCK_PATH)
            self._server_sock.listen(5)
            self._server_sock.settimeout(0.5)

            self._thread = threading.Thread(target=self._server_loop, name="vkcapture_receiver", daemon=True)
            self._thread.start()
            logger.info("Vulkan capture server listening on abstract socket")
        except Exception as e:
            logger.error(f"Failed to start Vulkan capture server: {e}")
            self.close()

    def _server_loop(self):
        while not self._stop_event.is_set():
            if self.exit_event and self.exit_event.is_set():
                break

            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.debug(f"Vulkan capture accept error: {e}")
                break

            try:
                conn.settimeout(2.0)
                cdata = conn.recv(CLIENT_DATA_SIZE)
                if len(cdata) < CLIENT_DATA_SIZE:
                    conn.close()
                    continue

                msg_type = cdata[0]
                exe_raw = cdata[1:49]
                exe_name = exe_raw.split(b'\0', 1)[0].decode('utf-8', errors='ignore')
                logger.info(f"Vulkan capture client connected: type={msg_type}, exe='{exe_name}'")

                # Send control handshake (linear=1, map_host=1, capturing=1)
                ctrl_data = bytearray(CONTROL_DATA_SIZE)
                ctrl_data[0] = 1  # capturing
                ctrl_data[1] = 1  # no_modifiers
                ctrl_data[2] = 1  # linear
                ctrl_data[3] = 1  # map_host
                conn.sendall(ctrl_data)

                # Keep connection alive and listen for swapchain resize / texture updates
                conn.settimeout(0.5)
                cmsg_space = socket.CMSG_SPACE(4 * 4)
                while not self._stop_event.is_set():
                    if self.exit_event and self.exit_event.is_set():
                        break
                    try:
                        data, ancdata, _, _ = conn.recvmsg(TEXTURE_DATA_SIZE, cmsg_space)
                    except socket.timeout:
                        continue
                    except Exception:
                        break

                    if not data:
                        break

                    new_fds = array.array("i")
                    for cmsg_level, cmsg_type, cmsg_data in ancdata:
                        if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
                            new_fds.frombytes(cmsg_data[:len(cmsg_data) - (len(cmsg_data) % new_fds.itemsize)])

                    if len(data) >= TEXTURE_DATA_SIZE and new_fds:
                        msg_type = data[0]
                        if msg_type == 11:  # CAPTURE_TEXTURE_DATA_TYPE
                            _, _, n_w, n_h, n_fmt, s0, _, _, _, _, _, _, _, _, _, _, _, _ = struct.unpack_from(
                                "=B B i i i 4i 4i Q I B I 65s", data, 0)
                            n_stride = s0
                            with self._lock:
                                self._cleanup_mmap(close_conn=False)
                                self._current_fd = new_fds[0]
                                for extra_fd in new_fds[1:]:
                                    try:
                                        os.close(extra_fd)
                                    except Exception:
                                        pass
                                total_size = n_stride * n_h
                                self._mmap_buf = mmap.mmap(self._current_fd, total_size, mmap.MAP_SHARED, mmap.PROT_READ)
                                self._width = n_w
                                self._height = n_h
                                self._stride = n_stride
                                self._format = n_fmt
                                self._conn = conn
                            logger.info(f"Vulkan texture updated: {n_w}x{n_h}, stride={n_stride}, format={n_fmt}")
                        else:
                            for fd in new_fds:
                                try:
                                    os.close(fd)
                                except Exception:
                                    pass

            except Exception as e:
                logger.debug(f"Vulkan capture connection error: {e}")
            finally:
                with self._lock:
                    self._cleanup_mmap(close_conn=True)

    def _cleanup_mmap(self, close_conn=True):
        if self._mmap_buf is not None:
            try:
                self._mmap_buf.close()
            except Exception:
                pass
            self._mmap_buf = None

        if self._current_fd >= 0:
            try:
                os.close(self._current_fd)
            except Exception:
                pass
            self._current_fd = -1

        if close_conn and self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def connected(self):
        if not self.hwnd_window or not self.hwnd_window.exists or self.hwnd_window.hwnd <= 0:
            return False
        with self._lock:
            return self._mmap_buf is not None and self._width > 0 and self._height > 0

    def clickable(self):
        return self.hwnd_window is not None and self.hwnd_window.visible

    def get_abs_cords(self, x, y):
        if self.hwnd_window:
            return self.hwnd_window.get_abs_cords(x, y)
        return int(x), int(y)

    def do_get_frame(self):
        if not self.hwnd_window or not self.hwnd_window.exists:
            return None

        with self._lock:
            if self._mmap_buf is None or self._width <= 0 or self._height <= 0:
                return None

            try:
                # Direct zero-copy ndarray from shared memory
                arr = np.frombuffer(self._mmap_buf, dtype=np.uint8).reshape((self._height, self._stride))
                # Crop valid width and convert BGRA to BGR
                valid_width_bytes = self._width * 4
                img_bgra = arr[:, :valid_width_bytes].reshape((self._height, self._width, 4))
                return cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
            except Exception as e:
                logger.debug(f"Vulkan do_get_frame error: {e}")
                return None

    def close(self):
        self._stop_event.set()
        with self._lock:
            self._cleanup_mmap()

        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if self._thread is not None and self._thread.is_alive():
            if self._thread != threading.current_thread():
                self._thread.join(timeout=1.0)
            self._thread = None

    def reset(self):
        pass
