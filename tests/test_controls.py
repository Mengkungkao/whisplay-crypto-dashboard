"""The controls are the whole UI contract -- and they are MFruit OS's.

Button and keyboard go through mfruit_sdk.input.InputController, the same
controller every MFruit app uses; these tests drive the real controller
(no threads, a fake clock) into the dashboard's real dispatch methods,
bound to a stub that records what happened. No hardware, no network, no
writes to the user's home directory.
"""

import json
from pathlib import Path

import pytest
from mfruit_sdk.input import (BACK, CHAR, EXTRA, KEY, NEXT, PREVIOUS, SELECT, Action,
                              InputController)
from mfruit_sdk.keys import DOWN, REPEAT, UP, KeyEvent

from app.main import DashboardApp
from app.ui.bitcoin_screen import BitcoinScreen
from app.ui.crypto_screen import CryptoScreen
from app.ui.market_screen import MarketScreen
from app.ui.statistics_screen import StatisticsScreen
from app.ui.system_screen import SystemScreen

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class _App:
    """The dashboard's dispatch, with the effects recorded instead of run."""

    handle_action = DashboardApp.handle_action
    handle_char = DashboardApp.handle_char
    page_action = DashboardApp.page_action

    def __init__(self, page=0):
        self.calls = []
        self.page_index = page
        self.screens = [BitcoinScreen(), MarketScreen(), CryptoScreen(),
                        StatisticsScreen(), SystemScreen()]

    def next_page(self):
        self.calls.append("next page")

    def previous_page(self):
        self.calls.append("previous page")

    def cycle_timeframe(self):
        self.calls.append("timeframe")

    def force_refresh(self):
        self.calls.append("refresh")

    def request_exit(self):
        self.calls.append("exit")

    def go_home(self):
        self.calls.append("home")

    def go_to(self, index):
        self.calls.append(f"page {index + 1}")


@pytest.mark.parametrize("action,expected", [
    (Action(NEXT), "next page"),
    (Action(PREVIOUS), "previous page"),
    (Action(SELECT), "timeframe"),          # on the Bitcoin chart
    (Action(EXTRA), "refresh"),
    (Action(BACK), "exit"),
    (Action(KEY, key="home"), "home"),
    (Action(CHAR, char="r"), "refresh"),
    (Action(CHAR, char="T"), "timeframe"),
    (Action(CHAR, char="h"), "home"),
    (Action(CHAR, char="3"), "page 3"),
])
def test_action_mapping(action, expected):
    app = _App()
    app.handle_action(action)
    assert app.calls == [expected]


def test_hold_refreshes_on_every_page_but_the_chart():
    for page in range(1, 5):
        app = _App(page)
        app.handle_action(Action(SELECT))
        assert app.calls == ["refresh"], page


def test_unmapped_input_does_nothing():
    app = _App()
    for action in (Action(CHAR, char="z"), Action(CHAR, char="9"), Action(KEY, key="end")):
        app.handle_action(action)
    assert app.calls == []


def controller(app, clock):
    return InputController(app.handle_action, keyboard=False, threaded=False, clock=clock,
                           click_window_ms=400, long_press_ms=700, debounce_ms=75)


def test_button_gestures_through_the_real_controller():
    app, clock = _App(), Clock()
    ctl = controller(app, clock)

    def step(seconds):
        clock.now += seconds
        ctl.gestures.poll()

    def clicks(count):
        for _ in range(count):
            ctl.press()
            step(0.06)
            ctl.release()
            step(0.12)
        step(0.5)

    clicks(1)
    clicks(2)
    clicks(3)
    ctl.press()
    step(1.0)
    assert app.calls == ["next page", "previous page", "refresh"]   # nothing while held
    ctl.release()
    step(0.5)
    clicks(4)
    assert app.calls == ["next page", "previous page", "refresh", "timeframe", "exit"]


def test_keyboard_through_the_real_controller():
    app, clock = _App(), Clock()
    ctl = controller(app, clock)
    for name, code in (("down", 108), ("up", 103), ("enter", 28), ("escape", 1)):
        ctl.key_event(KeyEvent("key", name, DOWN, code))
    ctl.key_event(KeyEvent("char", "r", DOWN, 19))
    assert app.calls == ["next page", "previous page", "timeframe", "exit", "refresh"]


def test_keys_are_ignored_while_another_app_has_the_screen():
    app, clock = _App(), Clock()
    owns = {"screen": False}
    ctl = InputController(app.handle_action, keyboard=False, threaded=False, clock=clock,
                          active=lambda: owns["screen"])
    ctl.key_event(KeyEvent("key", "escape", DOWN, 1))
    owns["screen"] = True
    # The Enter that opened the dashboard is released after it appears.
    ctl.key_event(KeyEvent("key", "enter", REPEAT, 28))
    ctl.key_event(KeyEvent("key", "enter", UP, 28))
    assert app.calls == []


def test_app_owns_every_gesture_and_the_esc_key():
    """exit_gesture 'none' and disable_esc_exit_key, or the daemon steals hold/quad/Esc."""
    from app.board import EXIT_GESTURE

    assert EXIT_GESTURE == "none"
    manifest = json.loads((ROOT / "packaging" / "whisplay-crypto-dashboard.json").read_text())
    assert manifest["exit_gesture"] == "none"
    assert manifest["disable_esc_exit_key"] is True


def test_vendored_sdk_is_importable_as_mfruit_sdk():
    import mfruit_sdk

    assert (ROOT / "mfruit_sdk" / "VENDORED").exists()
    assert mfruit_sdk.SDK_VERSION
