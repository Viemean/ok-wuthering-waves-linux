import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from ok.device.capture_methods.base import BaseCaptureMethod
from ok.util.GlobalConfig import basic_options, create_basic_options


def test_basic_options_contains_fps_and_onnx_threads():
    options = create_basic_options()
    assert options.default_config.get('Capture Frame Rate Limit') == 90
    assert options.default_config.get('ONNX Inference Threads') == 4

    assert options.config_type.get('Capture Frame Rate Limit') == {'min': 0, 'max': 240}
    assert options.config_type.get('ONNX Inference Threads') == {'min': 1, 'max': 32}

    assert 'Capture Frame Rate Limit' in options.config_description
    assert 'ONNX Inference Threads' in options.config_description


def test_base_capture_method_target_fps_default():
    cap = BaseCaptureMethod()
    assert cap.get_target_fps() == 90


def test_base_capture_method_target_fps_from_global_config():
    cap = BaseCaptureMethod()
    mock_global_config = MagicMock()
    mock_global_config.get_config.return_value = {
        'Capture Frame Rate Limit': 120,
    }

    with patch('ok.og.global_config', mock_global_config):
        assert cap.get_target_fps() == 120


def test_base_capture_method_fps_pacing_sleeps_when_fast():
    cap = BaseCaptureMethod()
    cap.get_target_fps = MagicMock(return_value=100)  # 10ms per frame
    cap._last_capture_time = 100.0

    # Simulate now = 100.002s (only 2ms elapsed, should sleep ~8ms)
    with patch('time.perf_counter', side_effect=[100.002, 100.010]), \
         patch('time.sleep') as mock_sleep:
        cap._apply_fps_limit()
        mock_sleep.assert_called_once()
        sleep_arg = mock_sleep.call_args[0][0]
        assert pytest.approx(sleep_arg, abs=0.001) == 0.008


def test_base_capture_method_fps_pacing_skips_sleep_when_unlimited():
    cap = BaseCaptureMethod()
    cap.get_target_fps = MagicMock(return_value=0)  # unlimited
    cap._last_capture_time = 100.0

    with patch('time.perf_counter') as mock_perf, patch('time.sleep') as mock_sleep:
        cap._apply_fps_limit()
        mock_perf.assert_not_called()
        mock_sleep.assert_not_called()


def test_get_frame_invokes_apply_fps_limit():
    class DummyCapture(BaseCaptureMethod):
        def do_get_frame(self):
            return np.zeros((100, 100, 3), dtype=np.uint8)

    cap = DummyCapture()
    with patch.object(cap, '_apply_fps_limit') as mock_apply:
        frame = cap.get_frame()
        assert frame is not None
        mock_apply.assert_called_once()
