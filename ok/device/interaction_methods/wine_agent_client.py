import atexit
import os
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict

from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

AGENT_MAGIC = 0x4F4B5757  # "OKWW"
DEFAULT_PORT = 49152

CMD_POST_MSG = 1
CMD_PING = 2
CMD_SET_HWND = 3
CMD_EXIT = 4


class WineAgentClient:
    """Manages the lifecycle and IPC socket connection to ok-wine-agent.exe inside Proton/Wine."""
    _instance: Optional["WineAgentClient"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, port: int = DEFAULT_PORT):
        if getattr(self, "_initialized", False):
            return
        self.port = port
        self.proc: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self.target_hwnd: int = 0
        self._send_lock = threading.RLock()
        atexit.register(self.close)
        self._initialized = True

    def _kill_existing_agent(self):
        try:
            subprocess.run(["pkill", "-f", "ok-wine-agent"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.1)
        except Exception:
            pass

    def _get_game_env_and_runner(self) -> tuple[Optional[str], Optional[Dict[str, str]]]:
        """Dynamically detect Proton/Wine environment from the running game process."""
        proc_dir = Path("/proc")
        if not proc_dir.is_dir():
            return None, None

        for p in proc_dir.glob("[0-9]*"):
            try:
                env_file = p / "environ"
                if not env_file.exists():
                    continue
                raw_bytes = env_file.read_bytes()
                if b"Client-Win64-Shipping" in raw_bytes and b"WINEPREFIX" in raw_bytes:
                    wine_env = dict(os.environ)
                    for item in raw_bytes.split(b"\0"):
                        if b"=" in item:
                            k, v = item.split(b"=", 1)
                            wine_env[k.decode("utf-8", errors="ignore")] = v.decode("utf-8", errors="ignore")

                    proton_path = wine_env.get("PROTONPATH")
                    if proton_path:
                        proton_script = Path(proton_path) / "proton"
                        if proton_script.exists():
                            return str(proton_script), wine_env

                    wine_bin = wine_env.get("WINE")
                    if wine_bin and Path(wine_bin).exists():
                        return str(wine_bin), wine_env
            except Exception:
                continue

        return None, None

    def start(self) -> bool:
        """Start ok-wine-agent.exe inside the game's Proton environment and connect."""
        if self.sock is not None:
            return True

        # Probe if an agent is already running and responsive
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", self.port))
            self.sock = s
            if self.ping():
                logger.info(f"Connected to existing ok-wine-agent successfully, target_hwnd=0x{self.target_hwnd:x}")
                return True
            self.close()
        except Exception:
            self.sock = None

        # Clean up any unresponsive zombie agent occupying the port
        self._kill_existing_agent()

        runner, wine_env = self._get_game_env_and_runner()
        if not runner or not wine_env:
            logger.warning("Could not detect Proton/Wine environment from running game process")
            return False

        agent_exe = Path(__file__).parent / "bin" / "ok-wine-agent.exe"
        if not agent_exe.exists():
            logger.error(f"ok-wine-agent.exe not found at {agent_exe}")
            return False

        try:
            if runner.endswith("proton"):
                cmd = ["python3", runner, "run", str(agent_exe.resolve()), str(self.port)]
            else:
                cmd = [runner, str(agent_exe.resolve()), str(self.port)]

            self.proc = subprocess.Popen(
                cmd,
                env=wine_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            logger.info(f"Launched ok-wine-agent inside Proton: pid={self.proc.pid}")

            # Connect with retries
            for attempt in range(15):
                time.sleep(0.3)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2.0)
                    s.connect(("127.0.0.1", self.port))
                    self.sock = s
                    break
                except (ConnectionRefusedError, OSError):
                    pass

            if not self.sock:
                logger.error("Failed to connect to ok-wine-agent socket on 127.0.0.1")
                self.close()
                return False

            # Ping and obtain target hwnd
            self.ping()
            logger.info(f"Connected to ok-wine-agent successfully, target_hwnd=0x{self.target_hwnd:x}")
            return True

        except Exception as e:
            logger.error(f"Error starting ok-wine-agent: {e}")
            self.close()
            return False

    def ping(self) -> bool:
        """Send PING command to verify connection and refresh target hwnd."""
        with self._send_lock:
            if not self.sock:
                return False
            try:
                req = struct.pack("<IIQIQq", AGENT_MAGIC, CMD_PING, 0, 0, 0, 0)
                self.sock.sendall(req)
                resp = self.sock.recv(16)
                if len(resp) == 16:
                    magic, status, hwnd = struct.unpack("<IiQ", resp)
                    if magic == AGENT_MAGIC and status == 0:
                        self.target_hwnd = hwnd
                        return True
            except Exception as e:
                logger.debug(f"WineAgent ping failed: {e}")
                self.close()
            return False

    def post_message(self, msg: int, wparam: int = 0, lparam: int = 0, hwnd: int = 0) -> bool:
        """Send Win32 PostMessage command to target HWND via agent."""
        with self._send_lock:
            if not self.sock:
                if not self.start():
                    return False

            target = hwnd or self.target_hwnd
            req = struct.pack("<IIQIQq", AGENT_MAGIC, CMD_POST_MSG, target, int(msg), int(wparam), int(lparam))
            try:
                self.sock.sendall(req)
                resp = self.sock.recv(16)
                if len(resp) == 16:
                    magic, status, cur_hwnd = struct.unpack("<IiQ", resp)
                    if cur_hwnd and cur_hwnd != self.target_hwnd:
                        self.target_hwnd = cur_hwnd
                    return status == 0
            except Exception as e:
                logger.debug(f"WineAgent post_message failed: {e}")
                self.close()
                if self.start():
                    try:
                        self.sock.sendall(req)
                        resp = self.sock.recv(16)
                        if len(resp) == 16:
                            magic, status, cur_hwnd = struct.unpack("<IiQ", resp)
                            return status == 0
                    except Exception:
                        pass
            return False

    def close(self):
        """Close socket connection and terminate agent subprocess."""
        if self.sock:
            try:
                req_exit = struct.pack("<IIQIQq", AGENT_MAGIC, CMD_EXIT, 0, 0, 0, 0)
                self.sock.sendall(req_exit)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), 15)
                self.proc.wait(timeout=1.0)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), 9)
                except Exception:
                    pass
            self.proc = None
        self._kill_existing_agent()
