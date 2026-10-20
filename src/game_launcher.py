import re
from pathlib import Path

from ok import Logger, og

logger = Logger.get_logger(__name__)


def match_game_package_from_process() -> str | None:
    """Detect -krqlv=<package> from the running game process command line."""
    psutil_success = False
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline')
                if not cmdline:
                    continue
                cmd_str = " ".join(cmdline)
                if 'Client-Win64-Shipping' in cmd_str:
                    match = re.search(r'-krqlv=([a-zA-Z0-9_-]+)', cmd_str, re.IGNORECASE)
                    if match:
                        return match.group(1).lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        psutil_success = True
    except Exception as e:
        logger.debug(f"psutil match_game_package error: {e}")

    if not psutil_success:
        try:
            proc_dir = Path('/proc')
            if proc_dir.is_dir():
                for p in proc_dir.glob('[0-9]*'):
                    try:
                        cmd_file = p / 'cmdline'
                        if not cmd_file.exists():
                            continue
                        raw = cmd_file.read_bytes().decode('utf-8', errors='ignore')
                        if 'Client-Win64-Shipping' in raw:
                            match = re.search(r'-krqlv=([a-zA-Z0-9_-]+)', raw, re.IGNORECASE)
                            if match:
                                return match.group(1).lower()
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"/proc match_game_package error: {e}")

    return None


def sync_game_package() -> str | None:
    """Match running game package and update global config."""
    package = match_game_package_from_process()
    if package:
        global_config = getattr(og, 'global_config', None)
        if global_config:
            try:
                basic_options = global_config.get_config('Basic Options')
            except Exception:
                basic_options = None
            if basic_options is not None and basic_options.get('Game Package') != package:
                logger.info(f"Sync Game Package: {basic_options.get('Game Package')} -> {package}")
                basic_options['Game Package'] = package
                try:
                    from ok.core.events import communicate
                    communicate.config_updated.emit('Basic Options', 'Game Package', package)
                except Exception as e:
                    logger.debug(f"Failed to emit config_updated: {e}")
    return package


def get_game_launch_arguments():
    """Read the selected game package each time the game is launched."""
    sync_game_package()
    global_config = getattr(og, 'global_config', None)
    basic_options = None
    if global_config:
        try:
            basic_options = global_config.get_config('Basic Options')
        except Exception:
            basic_options = None
    package = basic_options.get('Game Package', 'hd') if basic_options else 'hd'
    return f'-krqlv={package}'
