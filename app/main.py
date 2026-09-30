#!/usr/bin/env python3
"""Whisplay Bitcoin Market Dashboard -- application entry point.

Controls
--------
Five pages in a ring. The controls are MFruit OS's, the same in every app
(mfruit_sdk.input.InputController reads the button and any USB or
Bluetooth keyboard):

    HOME (Bitcoin) -> MARKET -> TOP CRYPTO -> STATISTICS -> SYSTEM -+
      ^                                                             |
      +-------------------------------------------------------------+

    button            keyboard           action
    tap               Down / Right / Tab next page
    2x                Up / Left          previous page
    hold, release     Enter              the page's action: next chart
                                         timeframe on Bitcoin, refresh
                                         elsewhere
    3x                R                  refresh now
    4x                Esc                leave the app
                      T                  next timeframe
                      H / Home, 1-5      Bitcoin page / page 1-5

The app registers with exit_gesture "none" and claims the Esc key, so it
owns every gesture and key and performs its own exit.

Threading
---------
Three threads, each with one job:

    main             render only; never touches the network
    market-service   all HTTP; publishes immutable snapshots
    mfruit-gestures  button timing          (mfruit_sdk)
    mfruit-keys      USB / Bluetooth keys   (mfruit_sdk)
    mfruit-status    WiFi and battery       (mfruit_sdk)

The render loop is event-driven: it sleeps on a condition until data
changes, a button is pressed, or the status tick expires. Idle cost is
therefore close to zero, which is what keeps a Pi Zero 2 W cool.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time
from pathlib import Path

# Allow `python3 app/main.py` as well as `python3 -m app.main`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mfruit_sdk.input import (BACK, CHAR, EXTRA, KEY, NEXT, PREVIOUS, SELECT,
                              InputController)
from mfruit_sdk.status import StatusMonitor

from app.board import APP_ID, acquire_board
from app.config.settings import load_settings
from app.market.cache import AppState, MarketCache
from app.market.service import MarketService
from app.ui.base import RenderContext
from app.ui.bitcoin_screen import BitcoinScreen
from app.ui.crypto_screen import CryptoScreen
from app.ui.display import Display
from app.ui.frame import compose
from app.ui.market_screen import MarketScreen
from app.ui.statistics_screen import StatisticsScreen
from app.ui.system_screen import SystemScreen
from app.utils.logger import get_logger, setup_logging
from app.utils.network import ConnectivityMonitor
from app.utils.system import SystemMonitor

log = get_logger("main")

HOME_INDEX = 0
TOAST_SECONDS = 2.5

# LED colours communicate market state at a glance across the room.
LED_OFF = (0, 0, 0)
LED_UP = (0, 70, 26)
LED_DOWN = (80, 8, 14)
LED_FLAT = (28, 30, 40)
LED_OFFLINE = (70, 40, 0)
LED_SYNC = (0, 40, 80)


class DashboardApp:
    def __init__(self):
        self.settings = load_settings()
        setup_logging(self.settings)
        log.info("=" * 52)
        log.info("Whisplay Bitcoin Market Dashboard starting (pid %s)", os.getpid())
        if self.settings.config_path:
            log.info("config: %s", self.settings.config_path)

        # --- render loop state (declared first: acquire_board may call
        # back from a background thread as soon as it is invoked) -------
        self._dirty = threading.Event()
        self._dirty.set()

        # --- hardware --------------------------------------------------
        self.board, self.board_mode = acquire_board(
            on_foreground_acquired=self._on_foreground_acquired
        )
        if self.board_mode == "waiting":
            log.warning(
                "another app owns the display; waiting for it to exit "
                "(the dashboard will appear automatically)"
            )
        self.display = Display(self.board, self.settings)

        # --- persisted state -------------------------------------------
        self.state = AppState(
            self.settings.state_path,
            {"timeframe": self.settings.default_timeframe},
        )
        saved_timeframe = self.state.get("timeframe", self.settings.default_timeframe)

        self.cache = MarketCache(self.settings.cache_path, self.settings.cache_enabled)

        # --- data ------------------------------------------------------
        self.service = MarketService(
            self.settings, self.cache,
            on_change=self.mark_dirty,
            timeframe=saved_timeframe,
        )
        log.info("restored timeframe %s", self.service.timeframe)

        self.system_monitor = SystemMonitor(self.settings.refresh["system_seconds"])
        self.connectivity = ConnectivityMonitor()

        # --- input: the button and any USB / Bluetooth keyboard ----------
        self.armed = False
        self.input = InputController(
            self.handle_action,
            active=self._owns_screen,
            on_armed=self._on_armed,
            debounce_ms=self.settings.button["debounce_ms"],
            click_window_ms=self.settings.button["click_window_ms"],
            long_press_ms=self.settings.button["long_press_ms"],
            app_id=APP_ID,                 # MFruit OS hands its keys to this app by id
        )
        self.status = StatusMonitor(on_change=lambda _status: self.mark_dirty())

        # --- screens ---------------------------------------------------
        self.screens = [
            BitcoinScreen(),
            MarketScreen(),
            CryptoScreen(),
            StatisticsScreen(),
            SystemScreen(),
        ]
        self.page_index = HOME_INDEX

        # --- render loop state -----------------------------------------
        self._running = True
        self._toast = None
        self._toast_kind = "info"
        self._toast_until = 0.0
        self._was_refreshing = False
        self._last_online = None

    # --- redraw scheduling --------------------------------------------
    def _on_foreground_acquired(self):
        """Called from the retry thread once the daemon grants the screen."""
        self.board_mode = "daemon"
        log.info("display acquired; resuming rendering")
        self.mark_dirty()

    def mark_dirty(self):
        """Ask the render loop for a frame. Safe from any thread."""
        self._dirty.set()

    def show_toast(self, text: str, kind: str = "info", seconds: float = TOAST_SECONDS):
        self._toast = text
        self._toast_kind = kind
        self._toast_until = time.monotonic() + seconds
        self.mark_dirty()

    # --- input -----------------------------------------------------------
    def _owns_screen(self) -> bool:
        # The keyboard is shared with every other app: act on keys only
        # while the dashboard is the one on screen.
        return bool(getattr(self.board, "foreground_ready", True))

    def _on_armed(self, armed: bool):
        """A hold passed the threshold: the footer says what releasing does."""
        self.armed = armed
        self.mark_dirty()

    def handle_action(self, action):
        name = action.name
        if name == NEXT:
            self.next_page()
        elif name == PREVIOUS:
            self.previous_page()
        elif name == SELECT:
            self.page_action()
        elif name == EXTRA:
            self.force_refresh()
        elif name == BACK:
            self.request_exit()
        elif name == KEY and action.key == "home":
            self.go_home()
        elif name == CHAR:
            self.handle_char(action.char.lower())

    def handle_char(self, char: str):
        if char == "r":
            self.force_refresh()
        elif char == "t":
            self.cycle_timeframe()
        elif char == "h":
            self.go_home()
        elif char.isdigit() and 1 <= int(char) <= len(self.screens):
            self.go_to(int(char) - 1)

    def page_action(self):
        """Hold (or Enter): the chart page changes timeframe, others refresh."""
        if self.screens[self.page_index].select_label == "timeframe":
            self.cycle_timeframe()
        else:
            self.force_refresh()

    def go_to(self, index: int):
        self.page_index = index % len(self.screens)
        log.info("screen -> %s", self.screens[self.page_index].name)
        self.mark_dirty()

    def next_page(self):
        self.go_to(self.page_index + 1)

    def previous_page(self):
        self.go_to(self.page_index - 1)

    def go_home(self):
        self.go_to(HOME_INDEX)

    def cycle_timeframe(self):
        """Hold on the chart page, or T. Deliberately does NOT change page."""
        timeframe = self.service.next_timeframe()
        self.state.set("timeframe", timeframe)
        self.show_toast(f"Timeframe {timeframe}", "info", 1.5)

    def request_exit(self):
        """Four clicks or Esc. Leave the app and hand the screen back."""
        log.info("exit requested (4 clicks / Esc)")
        self.show_toast("Exiting", "info", 1.0)
        try:
            self.render_frame()      # let the toast actually appear
        except Exception:
            log.debug("final frame failed", exc_info=True)
        self._running = False
        self.mark_dirty()

    def force_refresh(self):
        self.service.request_refresh()
        self.show_toast("Refreshing…", "info", 6.0)

    # --- daemon lifecycle -----------------------------------------------
    def handle_exit_request(self, *_args):
        log.info("daemon requested app exit")
        self._running = False
        self.mark_dirty()

    def handle_focus_revoked(self, *_args):
        # The framebuffer is invalid from this moment on: stop drawing.
        log.warning("focus revoked by daemon; stopping render")
        self.input.reset()
        self._running = False
        self.mark_dirty()

    def wire_daemon_callbacks(self):
        if hasattr(self.board, "on_exit_request"):
            self.board.on_exit_request(self.handle_exit_request)
        if hasattr(self.board, "on_focus_revoked"):
            self.board.on_focus_revoked(self.handle_focus_revoked)

    # --- LED -------------------------------------------------------------
    def update_led(self, snapshot):
        if snapshot.refreshing:
            color = LED_SYNC
        elif not snapshot.online:
            color = LED_OFFLINE
        else:
            change = snapshot.best_change_24h
            if change is None:
                color = LED_FLAT
            elif change > 0:
                color = LED_UP
            elif change < 0:
                color = LED_DOWN
            else:
                color = LED_FLAT
        self.display.set_led(*color, fade_ms=300)

    # --- rendering --------------------------------------------------------
    def render_frame(self):
        snapshot = self.service.snapshot()
        now = time.monotonic()

        # A finished manual refresh reports its outcome.
        if self._was_refreshing and not snapshot.refreshing:
            if snapshot.online:
                self.show_toast("Updated", "success", 2.0)
            else:
                self.show_toast("Network error", "error", 3.0)
        self._was_refreshing = snapshot.refreshing

        if snapshot.online != self._last_online:
            log.info("connection state: %s", "LIVE" if snapshot.online else "OFFLINE")
            self._last_online = snapshot.online

        toast = self._toast if (self._toast and now < self._toast_until) else None
        if self._toast and now >= self._toast_until:
            self._toast = None

        ctx = RenderContext(
            snapshot=snapshot,
            settings=self.settings,
            system=self.system_monitor.sample(),
            connectivity=self.connectivity.sample(),
            now=time.time(),
            page_index=self.page_index,
            page_count=len(self.screens),
            toast=toast,
            toast_kind=self._toast_kind,
            board_mode=self.board_mode,
        )

        image = compose(self.screens[self.page_index], ctx, self.status.sample(),
                        armed=self.armed)
        self.display.present(image)
        self.update_led(snapshot)

    def _next_wakeup(self, last_render: float) -> float:
        """Seconds to sleep: the soonest of status tick or toast expiry."""
        now = time.monotonic()
        timeout = self.settings.status_tick_seconds - (now - last_render)
        if self._toast:
            timeout = min(timeout, max(0.05, self._toast_until - now))
        return max(0.05, timeout)

    def run(self):
        self.wire_daemon_callbacks()
        self.input.attach(self.board)
        self.input.start()
        self.status.start()
        self.service.start()

        log.info(
            "dashboard ready (mode=%s, timeframe=%s, pages=%d)",
            self.board_mode, self.service.timeframe, len(self.screens),
        )
        log.info(
            "controls: tap/Down=next page, 2x/Up=previous, hold/Enter=page action, "
            "3x/R=refresh, 4x/Esc=exit, T=timeframe"
        )

        frame_interval = 1.0 / self.settings.fps
        last_render = 0.0

        try:
            while self._running:
                now = time.monotonic()
                # Rate-limit to the configured FPS even under a burst.
                since = now - last_render
                if since < frame_interval:
                    time.sleep(frame_interval - since)

                self._dirty.clear()
                self.render_frame()
                last_render = time.monotonic()

                # Sleep until something needs drawing. Wakes early when
                # data arrives or a button is pressed.
                self._dirty.wait(timeout=self._next_wakeup(last_render))
        except KeyboardInterrupt:
            log.info("interrupted by user")
        finally:
            self.shutdown()

    def shutdown(self):
        log.info("shutting down")
        self._running = False
        try:
            self.input.stop()
            self.status.stop()
        except Exception:
            log.debug("input stop failed", exc_info=True)
        try:
            self.service.stop()
        except Exception:
            log.debug("service stop failed", exc_info=True)
        try:
            self.display.set_led(*LED_OFF)
        except Exception:
            pass
        try:
            self.board.cleanup()
        except Exception:
            log.debug("board cleanup failed", exc_info=True)
        log.info("stopped")


def main():
    app = DashboardApp()

    def on_signal(signum, _frame):
        log.info("signal %s received", signum)
        app._running = False
        app.mark_dirty()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
