import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from ok.util.config import Config
from ok.util.logger import Logger

logger = Logger.get_logger(__name__)

DEFAULT_PROTON_CONFIG = {
    'game_exe': '',
    'wine_prefix': '',
    'launch_args': '',
    'wrapper': '',
    'custom_env': '',
    'runner_path': '',
}


class LinuxProtonLauncher:
    """Detects running Proton environment, persists configuration, and launches Windows games on Linux."""

    def __init__(self):
        self.config = Config('proton_launch', DEFAULT_PROTON_CONFIG)

    def get_config(self) -> Dict[str, Any]:
        return dict(self.config)

    def update_config(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if k in DEFAULT_PROTON_CONFIG:
                self.config[k] = v
        self.config.save_file()

    @staticmethod
    def detect_running_game_env() -> Optional[Dict[str, str]]:
        """Scans /proc for active game process and extracts Proton container, arguments and environments."""
        proc_dir = Path("/proc")
        if not proc_dir.is_dir():
            return None

        # Find target game process and potential wrappers
        game_pids = []
        for p in proc_dir.glob("[0-9]*"):
            try:
                cmdline_file = p / "cmdline"
                if not cmdline_file.exists():
                    continue
                raw_bytes = cmdline_file.read_bytes()
                if not raw_bytes:
                    continue
                cmd_str = raw_bytes.decode("utf-8", errors="ignore").lower()
                if "client-win64-shipping" in cmd_str or "wutheringwaves" in cmd_str:
                    pid = int(p.name)
                    game_pids.append(pid)
            except Exception:
                continue

        if not game_pids:
            return None

        # Collect process tree info
        best_env: Dict[str, str] = {}
        best_exe = ""
        best_args = []
        best_wrapper = []
        best_runner = ""

        # Check Lutris game config first if present
        lutris_dir = Path.home() / ".local" / "share" / "lutris" / "games"
        lutris_cfg: Dict[str, Any] = {}
        if lutris_dir.is_dir():
            for yml_file in lutris_dir.glob("*wuthering*.yml"):
                try:
                    import yaml
                    lutris_cfg = yaml.safe_load(yml_file.read_text(encoding="utf-8")) or {}
                    break
                except Exception:
                    pass

        for pid in game_pids:
            p = proc_dir / str(pid)
            try:
                cmd_args = [a.decode("utf-8", errors="ignore") for a in (p / "cmdline").read_bytes().split(b"\0") if a]
                raw_env = (p / "environ").read_bytes()
                for item in raw_env.split(b"\0"):
                    if b"=" in item:
                        k, v = item.split(b"=", 1)
                        k_s = k.decode("utf-8", errors="ignore")
                        v_s = v.decode("utf-8", errors="ignore")
                        best_env[k_s] = v_s

                # Check command line arguments for executable and params
                for idx, arg in enumerate(cmd_args):
                    if arg.endswith("/proton") and os.path.isfile(arg):
                        best_runner = arg
                    if arg.lower().endswith(".exe") and not best_exe:
                        if os.path.isabs(arg) and os.path.isfile(arg):
                            best_exe = arg
                            best_args = cmd_args[idx + 1:]
                    if any(w in arg for w in ["umu-run", "mangohud", "dlssg", "dlss-swapper"]):
                        if arg not in best_wrapper:
                            best_wrapper.append(arg)
            except Exception:
                continue

        # Fallback to Lutris config if path/args missing
        if not best_exe and lutris_cfg.get("game", {}).get("exe"):
            best_exe = lutris_cfg["game"]["exe"]
        if not best_args and lutris_cfg.get("game", {}).get("args"):
            raw_args = lutris_cfg["game"]["args"]
            best_args = shlex.split(raw_args) if isinstance(raw_args, str) else list(raw_args)

        # Normalize prefix
        raw_prefix = best_env.get("WINEPREFIX", "")
        if not raw_prefix and lutris_cfg.get("game", {}).get("prefix"):
            raw_prefix = lutris_cfg["game"]["prefix"]

        clean_prefix = raw_prefix.rstrip("/")
        if clean_prefix.endswith("/pfx"):
            clean_prefix = clean_prefix[:-4]

        # Extract runner path
        if not best_runner:
            proton_path = best_env.get("PROTONPATH", "")
            if proton_path and os.path.isfile(os.path.join(proton_path, "proton")):
                best_runner = os.path.join(proton_path, "proton")

        # Extract key render / performance environment variables
        target_keys = [
            "ANTI_DITHER_ENABLED", "ANTI_DITHER_DUMP", "DXVK_FRAME_RATE",
            "DXVK_STATE_CACHE", "VKD3D_CONFIG", "VKD3D_SHADER_CACHE_PATH",
            "PROTON_DLSS_INDICATOR", "PROTON_NO_XALIA", "PROTON_USE_XALIA",
            "WINEESYNC", "WINEFSYNC", "GAMEID", "UMU_ID"
        ]
        custom_env_lines = []
        for k in target_keys:
            if k in best_env and best_env[k]:
                custom_env_lines.append(f"{k}={best_env[k]}")

        # Merge Lutris env if available
        if lutris_cfg.get("system", {}).get("env"):
            for k, v in lutris_cfg["system"]["env"].items():
                line = f"{k}={v}"
                if line not in custom_env_lines:
                    custom_env_lines.append(line)

        # Build clean wrapper string
        wrapper_str = ""
        known_wrappers = ["dlss-swapper", "dlssg", "mangohud", "umu-run"]
        detected_wrappers = []
        for w in known_wrappers:
            if any(w in arg for arg in best_wrapper):
                detected_wrappers.append(w)
        if detected_wrappers:
            wrapper_str = " ".join(detected_wrappers)
        elif lutris_cfg.get("system", {}).get("mangohud"):
            wrapper_str = "mangohud umu-run"

        return {
            'game_exe': best_exe,
            'wine_prefix': clean_prefix,
            'launch_args': " ".join(best_args) if isinstance(best_args, list) else str(best_args),
            'wrapper': wrapper_str,
            'custom_env': "\n".join(custom_env_lines),
            'runner_path': best_runner,
        }

    def can_launch(self) -> bool:
        """Returns True if minimum required launch parameters are configured."""
        exe = self.config.get('game_exe')
        return bool(exe and (os.path.isfile(exe) or self.config.get('wrapper')))

    def launch(self) -> Tuple[bool, str]:
        """Launches the game process using the configured Proton/Wine parameters."""
        if sys.platform == "win32":
            return False, "LinuxProtonLauncher is only supported on POSIX/Linux platforms."

        game_exe = self.config.get('game_exe', '').strip()
        if not game_exe:
            return False, "Game executable path is not configured."

        wine_prefix = self.config.get('wine_prefix', '').strip()
        launch_args = self.config.get('launch_args', '').strip()
        wrapper = self.config.get('wrapper', '').strip()
        custom_env_str = self.config.get('custom_env', '').strip()
        runner_path = self.config.get('runner_path', '').strip()

        # Build environment
        env = dict(os.environ)
        if wine_prefix:
            env['WINEPREFIX'] = wine_prefix
            env['STEAM_COMPAT_DATA_PATH'] = wine_prefix

        if runner_path and os.path.isfile(runner_path):
            env['PROTONPATH'] = os.path.dirname(runner_path)

        # Parse custom environment lines
        for line in custom_env_str.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

        # Build command list
        args_list = shlex.split(launch_args) if launch_args else []
        cmd_list = []

        if wrapper:
            cmd_list = shlex.split(wrapper) + [game_exe] + args_list
        elif runner_path and os.path.isfile(runner_path):
            cmd_list = ["python3", runner_path, "waitforexitandrun", game_exe] + args_list
        else:
            cmd_list = ["wine", game_exe] + args_list

        working_dir = os.path.dirname(game_exe) if os.path.isfile(game_exe) else None

        logger.info(f"LinuxProtonLauncher executing: {' '.join(cmd_list)} (cwd={working_dir})")
        try:
            subprocess.Popen(
                cmd_list,
                env=env,
                cwd=working_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            return True, ""
        except Exception as e:
            logger.error(f"Failed to launch game: {e}")
            return False, str(e)


_launcher_instance: Optional[LinuxProtonLauncher] = None


def get_proton_launcher() -> LinuxProtonLauncher:
    global _launcher_instance
    if _launcher_instance is None:
        _launcher_instance = LinuxProtonLauncher()
    return _launcher_instance
