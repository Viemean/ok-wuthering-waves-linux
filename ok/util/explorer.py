"""Open file manager folders or reveal items on Linux."""

import os
import shutil
import subprocess
from pathlib import Path

from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


def open_explorer_folder(folder):
    """Open folder using system file manager."""
    folder_path = Path(folder).resolve()
    folder_path.mkdir(parents=True, exist_ok=True)
    target = str(folder_path)
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Opened folder using xdg-open: {target}")
            return True
        except Exception as e:
            logger.warning(f"xdg-open failed: {e}")
    return False


def reveal_in_explorer(path):
    """Open parent directory of path using system file manager."""
    item_path = Path(path).resolve()
    return open_explorer_folder(item_path.parent)
