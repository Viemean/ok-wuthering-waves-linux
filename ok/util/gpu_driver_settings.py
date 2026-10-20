"""Cross-platform GPU driver post-processing checks."""

from dataclasses import dataclass
from typing import List, Optional

from ok.util.logger import Logger

logger = Logger.get_logger(__name__)


@dataclass(frozen=True)
class GpuDriverPostProcessing:
    vendor: str
    feature: str
    enabled: bool
    detail: Optional[str] = None


def get_enabled_gpu_driver_post_processing(target_exe_path: Optional[str] = None,
                                           target_hwnd: Optional[int] = None) -> List[GpuDriverPostProcessing]:
    return []


def is_gpu_post_processing_enabled(target_exe_path: Optional[str] = None,
                                   target_hwnd: Optional[int] = None) -> bool:
    return False
