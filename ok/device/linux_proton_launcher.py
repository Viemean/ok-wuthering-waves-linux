import os
import re
import shlex
import subprocess
import sys
import tempfile
import psutil
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

    def __init__(self, config=None):
        if config is not None:
            self.config = config
        else:
            self.config = Config('proton_launch', DEFAULT_PROTON_CONFIG)

    def get_config(self) -> Dict[str, Any]:
        return dict(self.config)

    def update_config(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if k in DEFAULT_PROTON_CONFIG:
                self.config[k] = v
        if hasattr(self.config, 'save_file'):
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

        # Collect process tree and candidate processes
        best_env: Dict[str, str] = {}
        best_exe = ""
        best_args = []
        best_wrapper = []
        best_runner = ""
        raw_prefix = ""

        # Trace process tree upwards to find launcher/wrapper process and clean environment
        top_env: Dict[str, str] = {}
        all_tree_pids = []

        for pid in game_pids:
            curr = pid
            chain = [curr]
            while curr > 1:
                try:
                    stat_file = proc_dir / str(curr) / "stat"
                    if not stat_file.is_file():
                        break
                    ppid = int(stat_file.read_text().split()[3])
                    if ppid <= 1:
                        break
                    env_file = proc_dir / str(ppid) / "environ"
                    if env_file.is_file():
                        chain.append(ppid)
                        curr = ppid
                    else:
                        break
                except Exception:
                    break
            all_tree_pids.extend(chain)

        # Inspect all related processes in the chain
        for pid in all_tree_pids:
            p = proc_dir / str(pid)
            try:
                cmd_bytes = (p / "cmdline").read_bytes()
                cmd_args = [a.decode("utf-8", errors="ignore") for a in cmd_bytes.split(b"\0") if a]

                raw_env = (p / "environ").read_bytes()
                proc_env: Dict[str, str] = {}
                for item in raw_env.split(b"\0"):
                    if b"=" in item:
                        k, v = item.split(b"=", 1)
                        best_env[k.decode("utf-8", errors="ignore")] = v.decode("utf-8", errors="ignore")

                if not raw_prefix and best_env.get("WINEPREFIX"):
                    raw_prefix = best_env["WINEPREFIX"]
                if not raw_prefix and best_env.get("STEAM_COMPAT_DATA_PATH"):
                    raw_prefix = best_env["STEAM_COMPAT_DATA_PATH"]

                if not best_runner:
                    proton_path = best_env.get("PROTONPATH", "")
                    if proton_path and os.path.isfile(os.path.join(proton_path, "proton")):
                        best_runner = os.path.join(proton_path, "proton")

                for idx, arg in enumerate(cmd_args):
                    if arg.endswith("/proton") and os.path.isfile(arg):
                        best_runner = arg
                    if arg.lower().endswith(".exe") and not best_exe:
                        if os.path.isabs(arg) and os.path.isfile(arg):
                            best_exe = arg
                            best_args = cmd_args[idx + 1:]
                    if any(w in arg for w in ["umu-run", "mangohud", "dlssg", "dlss-swapper"]):
                        w_name = os.path.basename(arg)
                        if w_name in ["umu-run", "mangohud", "dlssg", "dlss-swapper"] and w_name not in best_wrapper:
                            best_wrapper.append(w_name)
            except Exception:
                continue

        # Normalize prefix
        clean_prefix = raw_prefix.rstrip("/")
        if clean_prefix.endswith("/pfx"):
            clean_prefix = clean_prefix[:-4]

        # Build clean wrapper string
        known_wrappers = ["dlss-swapper", "dlssg", "mangohud", "umu-run"]
        detected_wrappers = [w for w in known_wrappers if w in best_wrapper]
        wrapper_str = " ".join(detected_wrappers) if detected_wrappers else ""

        # Match game, graphics, shader, driver, anti-dither and Proton/Wine runtime variables
        game_env_prefixes = (
            "DXVK_", "VKD3D_", "PROTON_", "WINE_", "ANTI_DITHER_", "MANGOHUD",
            "ENABLE_", "DISABLE_", "RADV_", "MESA_", "AMD_", "NVIDIA_", "__NV_",
            "DRI_", "GALLIUM_", "VKBASALT", "FSR_", "DLSS_", "GAMEMODE"
        )

        # Base exclusion: container, paths and runtime internal files
        exclude_keys = {
            "WINEPREFIX", "PROTONPATH", "WINEESYNC", "WINEFSYNC", "PROTON_VERB",
            "PROTON_CRASH_REPORT_DIR", "WINE_CRASH_REPORT_DIR", "WINE_GST_REGISTRY_DIR",
            "WINE_LARGE_ADDRESS_AWARE", "WINE_LD_PRELOAD", "WINELOADERNOEXEC", "WINEDEBUG",
            "WINEPRELOADRESERVE", "WINESERVERSOCKET", "WINEDLLPATH", "WINEDLLOVERRIDES",
            "NVIDIA_WINE_DLL_DIR", "STEAM_COMPAT_DATA_PATH", "STEAM_COMPAT_CLIENT_INSTALL_PATH",
            "GAMEID", "UMU_ID", "STORE", "WINE_GECKO_CACHE_DIR", "WINE_MONO_CACHE_DIR",
            "PROTON_BATTLEYE_RUNTIME", "PROTON_EAC_RUNTIME",
        }
        exclude_prefixes = set()

        # Conditionally omit wrapper-injected variables only if the wrapper is detected
        if "mangohud" in detected_wrappers:
            exclude_keys.update({"MANGOHUD", "MANGOHUD_DLSYM"})

        if any(w in detected_wrappers for w in ["dlssg", "dlss-swapper"]):
            exclude_keys.update({
                "DXVK_NVAPI_SET_NGX_DEBUG_OPTIONS",
                "DXVK_NVAPIHACK",
                "WINE_UPSCALER_REPLACE",
            })
            exclude_prefixes.add("DXVK_NVAPI_DRS_NGX_DLSS_")

        if "umu-run" in detected_wrappers or best_runner:
            exclude_keys.update({
                "DXVK_CONFIG", "DXVK_LOG_LEVEL", "DXVK_ENABLE_NVAPI",
                "VKD3D_DEBUG", "VKD3D_SHADER_DEBUG",
                "PROTON_ENABLE_NVAPI", "PROTON_ENABLE_NGX_UPDATER", "PROTON_NVIDIA_NVCUDA",
                "PROTON_DXVK_D3D8", "WINE_ENABLE_NVAPI", "WINE_FULLSCREEN_FSR",
            })

        target_env_dict = best_env
        custom_env_lines = []

        for k in sorted(target_env_dict.keys()):
            if k in exclude_keys or any(k.startswith(pfx) for pfx in exclude_prefixes):
                continue
            if any(k.startswith(pfx) for pfx in game_env_prefixes):
                v = target_env_dict[k]
                if v:
                    custom_env_lines.append(f"{k}={v}")

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

    @staticmethod
    def kill_existing_game_processes(game_exe: str, timeout: float = 3.0) -> int:
        """Detects and terminates residual game or proton processes before launching."""
        if os.environ.get("OK_TEST_MODE") == "1":
            from unittest.mock import Mock
            if not isinstance(psutil.process_iter, Mock):
                logger.warning("OK_TEST_MODE active: skip terminating real host processes")
                return 0

        current_pid = os.getpid()
        parent_pid = os.getppid()

        exe_basename = os.path.basename(game_exe).lower() if game_exe else ""
        exe_stem = os.path.splitext(exe_basename)[0]
        candidate_names = {exe_basename, exe_stem, exe_stem[:15]} if exe_stem else set()
        candidate_names.discard("")

        target_procs = []

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid == current_pid or pid == parent_pid:
                    continue

                proc_name = (proc.info['name'] or "").lower()
                cmdline = proc.info.get('cmdline') or []
                cmd_str = " ".join(cmdline).lower()

                is_match = False
                if any(cand in proc_name for cand in candidate_names):
                    is_match = True
                elif exe_basename and exe_basename in cmd_str:
                    is_match = True
                elif "umu.exe" in proc_name and exe_stem and exe_stem in cmd_str:
                    is_match = True

                if is_match:
                    target_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        if not target_procs:
            return 0

        logger.info(f"Detected {len(target_procs)} residual game process(es) before launch, terminating...")
        for p in target_procs:
            try:
                p.terminate()
            except Exception:
                pass

        gone, alive = psutil.wait_procs(target_procs, timeout=timeout)
        killed_count = len(gone)
        for p in alive:
            try:
                p.kill()
                killed_count += 1
            except Exception:
                pass

        logger.info(f"Cleaned up {killed_count} residual game process(es)")
        return killed_count

    def launch(self) -> Tuple[bool, str]:
        """Launches the game process using the configured Proton/Wine parameters."""
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

        args_list = shlex.split(launch_args) if launch_args else []

        # Determine runner command if wrapper does not provide umu-run
        wrapper_tokens = shlex.split(wrapper) if wrapper else []
        has_umu = any(w == "umu-run" or w.endswith("/umu-run") for w in wrapper_tokens)

        runner_cmd = []
        if not has_umu:
            if runner_path and os.path.isfile(runner_path):
                runner_cmd = ["python3", runner_path, "waitforexitandrun"]
            else:
                runner_cmd = ["wine"]

        # Build final command
        cmd_list = []
        if wrapper_tokens:
            cmd_list.extend(wrapper_tokens)
        cmd_list.extend(runner_cmd)
        cmd_list.append(game_exe)
        cmd_list.extend(args_list)

        working_dir = os.path.dirname(game_exe) if os.path.isfile(game_exe) else None

        # Terminate any residual game processes before starting a new session
        self.kill_existing_game_processes(game_exe)

        # Clean up stale dlssg backup directory if left behind by previous crashes
        if working_dir:
            stale_bak = os.path.join(working_dir, "dlssg_sm86.bak_dlssg")
            if os.path.isdir(stale_bak):
                try:
                    import shutil
                    shutil.rmtree(stale_bak)
                    logger.info(f"Cleaned up stale dlssg backup directory: {stale_bak}")
                except Exception as e:
                    logger.warning(f"Failed to clean up stale dlssg backup: {e}")

        logger.info(f"LinuxProtonLauncher executing: {' '.join(cmd_list)} (cwd={working_dir})")

        log_path = os.path.join(tempfile.gettempdir(), "ok_proton_launch.log")
        try:
            log_file = open(log_path, "w", encoding="utf-8")
        except Exception:
            log_file = subprocess.DEVNULL

        try:
            proc = subprocess.Popen(
                cmd_list,
                env=env,
                cwd=working_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

            # Detect immediate exit on launch failure
            try:
                proc.wait(timeout=1.0)
                err_content = ""
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        err_content = lf.read().strip()
                except Exception:
                    pass
                msg = f"Game launch process exited prematurely with code {proc.returncode}"
                if err_content:
                    msg += f": {err_content[-300:]}"
                logger.error(msg)
                return False, msg
            except subprocess.TimeoutExpired:
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
