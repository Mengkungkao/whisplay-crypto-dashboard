"""Colour palette, fonts and text helpers for the 240x280 panel.

The chrome (status bar, footer hints, toasts, background) follows MFruit OS
through the vendored MFruit App SDK (mfruit_sdk/), so the dashboard looks
like the rest of the device. Inside the content area Bitcoin orange stays
the accent, so the device still reads as a dedicated BTC instrument.

Design rules, in priority order: large readable numbers, high contrast,
minimal text, clear hierarchy.
"""

from __future__ import annotations

from mfruit_sdk.ui import fonts as _fonts
from mfruit_sdk.ui import theme as _mfruit

SCREEN_WIDTH = _mfruit.SCREEN_W
SCREEN_HEIGHT = _mfruit.SCREEN_H

# Content lives between MFruit OS's status bar and footer.
CONTENT_TOP = _mfruit.CONTENT_TOP
CONTENT_BOTTOM = _mfruit.CONTENT_BOTTOM

MFRUIT = _mfruit.DARK

# --- palette (RGB) ----------------------------------------------------
BG = MFRUIT.bg
PANEL = MFRUIT.surface
PANEL_ALT = MFRUIT.surface_hi
GRID = (34, 40, 52)
DIVIDER = MFRUIT.separator

TEXT = MFRUIT.text
TEXT_DIM = MFRUIT.text_muted
TEXT_MUTED = (118, 126, 140)

ACCENT = (247, 147, 26)        # Bitcoin orange
ACCENT_DIM = (139, 86, 24)

UP = MFRUIT.success
DOWN = MFRUIT.error
FLAT = (150, 158, 178)

LIVE = MFRUIT.success
OFFLINE = MFRUIT.text_muted
WARN = MFRUIT.warning
ERROR = MFRUIT.error

FEAR = MFRUIT.error
NEUTRAL = MFRUIT.warning
GREED = MFRUIT.success


def font(size: int, bold: bool = False):
    """MFruit OS's font (Inter, or DejaVu where MFruit OS is not installed)."""
    return _fonts.font(int(size), "bold" if bold else "regular")


def text_size(draw, text: str, fnt) -> tuple:
    """(width, height) of ``text``, across Pillow versions."""
    if not text:
        return (0, 0)
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=fnt)
        return (right - left, bottom - top)
    except AttributeError:  # Pillow < 8
        return fnt.getsize(text)


def text_width(draw, text: str, fnt) -> int:
    return text_size(draw, text, fnt)[0]


def fit_font(draw, text: str, max_width: int, sizes, bold: bool = True):
    """Largest font from ``sizes`` (descending) whose text fits the width."""
    chosen = font(sizes[-1], bold)
    for size in sizes:
        candidate = font(size, bold)
        if text_width(draw, text, candidate) <= max_width:
            return candidate
        chosen = candidate
    return chosen


def change_color(value) -> tuple:
    """Green up, red down, grey flat/unknown."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return FLAT
    if number > 0:
        return UP
    if number < 0:
        return DOWN
    return FLAT


def fear_greed_color(value) -> tuple:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return TEXT_DIM
    if number <= 25:
        return FEAR
    if number <= 45:
        return (240, 130, 70)
    if number <= 55:
        return NEUTRAL
    if number <= 75:
        return (150, 200, 90)
    return GREED
