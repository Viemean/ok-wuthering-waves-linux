import base64
import json
import re
from pathlib import Path

from ok import Logger, og
from ok.core.notifications import alert_error

logger = Logger.get_logger(__name__)
GAME_PACKAGES = ('sd', 'hd', 'uhd')
GAME_ASSETS_QUALITY_ERROR = 'Failed to read game assets quality config. Starting with HD assets.'


def _read_launcher_config(path, encoded=False):
    try:
        data = path.read_bytes()
        if encoded:
            # Kuro's launcher stores its UI state as Base64 with an XOR mask.
            data = bytes(value ^ 0x63 for value in base64.b64decode(data, validate=True))
        config = json.loads(data.decode('utf-8-sig'))
        return config if isinstance(config, dict) else {}
    except (OSError, ValueError, UnicodeError) as error:
        logger.debug(f'Could not read launcher config {path}: {error}')
        return {}


def detect_game_package(game_exe_path):
    """Read the selected Wuthering Waves bundle from this installation's launcher."""
    game_folder = Path(game_exe_path).parent
    state = _read_launcher_config(
        game_folder.parent / 'kr_game_cache' / 'platform_ui_state.bin', encoded=True,
    )
    active = state.get('activeGameScope')
    recent_games = state.get('recentGames')
    recent = recent_games.get('Aki') if isinstance(recent_games, dict) else None
    for scope in (active, recent):
        if not isinstance(scope, dict):
            continue
        if scope is active and scope.get('gameIdentity') != 'Aki':
            continue
        package = scope.get('bundleName')
        if isinstance(package, str) and package.lower() in GAME_PACKAGES:
            return package.lower()

    # A download manifest can identify the package only when it is unambiguous.
    manifest = _read_launcher_config(game_folder / 'launcherDownloadConfig.json')
    bundles = manifest.get('bundles')
    if isinstance(bundles, dict):
        packages = {name.lower() for name in bundles if name.lower() in GAME_PACKAGES}
        if len(packages) == 1:
            return packages.pop()
    return None


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
    """Match running game package and update global config if option exists."""
    package = match_game_package_from_process()
    if package:
        global_config = getattr(og, 'global_config', None)
        if global_config:
            try:
                basic_options = global_config.get_config('Basic Options')
            except Exception:
                basic_options = None
            if basic_options is not None and 'Game Package' in basic_options and basic_options.get('Game Package') != package:
                logger.info(f"Sync Game Package: {basic_options.get('Game Package')} -> {package}")
                basic_options['Game Package'] = package
                try:
                    from ok.core.events import communicate
                    communicate.config_updated.emit('Basic Options', 'Game Package', package)
                except Exception as e:
                    logger.debug(f"Failed to emit config_updated: {e}")
    return package


def get_game_launch_arguments():
    """Detect the launcher selection on each launch, alerting and using HD on failure."""
    device_manager = getattr(og, 'device_manager', None)
    if device_manager is not None:
        device = device_manager.get_preferred_device()
        if device and device.get('device') in ('windows', 'linux'):
            game_exe_path = device_manager.get_exe_path(device)
            if game_exe_path and (package := detect_game_package(game_exe_path)):
                logger.info(f'Detected game package {package} from launcher config')
                return f'-krqlv={package}'
    logger.warning(GAME_ASSETS_QUALITY_ERROR)
    app = getattr(og, 'app', None)
    message = app.tr(GAME_ASSETS_QUALITY_ERROR) if app is not None else GAME_ASSETS_QUALITY_ERROR
    alert_error(message, tray=True)
    return '-krqlv=hd'
