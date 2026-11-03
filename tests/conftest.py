"""Pytest global configuration and safety guards for tests."""
import os
import pytest

# Ensure all tests run with test safety mode enabled
os.environ["OK_TEST_MODE"] = "1"


@pytest.fixture(autouse=True, scope="session")
def enforce_test_mode_environment():
    """Ensure host game processes and windows are never disrupted during tests."""
    os.environ["OK_TEST_MODE"] = "1"
    yield
