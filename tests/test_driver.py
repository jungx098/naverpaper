"""Tests for renderer health detection in driver.py."""

from selenium.common.exceptions import TimeoutException

from driver import is_alive


class FakeDriver:
    """Minimal driver stand-in recording script-timeout changes."""

    def __init__(self, raise_exc: Exception | None = None):
        self.raise_exc = raise_exc
        self.script_timeouts: list[int] = []

    def set_script_timeout(self, timeout: int) -> None:
        self.script_timeouts.append(timeout)

    def execute_script(self, script: str):
        if self.raise_exc is not None:
            raise self.raise_exc
        return 1


def test_is_alive_true_when_script_returns():
    assert is_alive(FakeDriver()) is True


def test_is_alive_false_when_renderer_hangs():
    driver = FakeDriver(raise_exc=TimeoutException("renderer"))
    assert is_alive(driver) is False


def test_is_alive_restores_default_script_timeout():
    driver = FakeDriver()
    is_alive(driver, timeout=5)
    # Probe lowers the script timeout, then restores it to the run default.
    assert driver.script_timeouts == [5, 30]
