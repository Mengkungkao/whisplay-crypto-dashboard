"""One finished frame: a page's content inside MFruit OS's chrome.

    status bar   page name on the left; a data light (green live, amber
                 refreshing, grey offline), WiFi and battery on the right
    content      the page, between theme.CONTENT_TOP and CONTENT_BOTTOM
    footer       the gestures that work on this page
    toast        short feedback ("Timeframe 4H", "Refreshing…")

The chrome comes from the vendored MFruit App SDK (mfruit_sdk/), so it is
pixel-for-pixel the launcher's. Used by the app and by tools/preview.py.
"""

from __future__ import annotations

from mfruit_sdk.ui import Canvas, footer, status_bar, toast

from app.ui import theme, widgets
from app.utils.logger import get_logger

log = get_logger("frame")

TOAST_TONES = {"info": "accent", "success": "success", "error": "error"}


def data_light(snapshot) -> tuple:
    """Status-bar light: green live, amber refreshing, grey offline."""
    if snapshot.refreshing:
        return theme.WARN
    if snapshot.online:
        return theme.LIVE
    return theme.OFFLINE


def hints(screen, armed: bool = False) -> list:
    """Footer hints; after a hold passes the threshold, what releasing does."""
    if armed:
        return [("release", f"to {screen.select_label}")]
    return [("tap", "next"), ("hold", screen.select_label), ("4×", "exit")]


def compose(screen, ctx, status=None, armed: bool = False):
    canvas = Canvas(theme=theme.MFRUIT)
    try:
        screen.render(canvas.draw, ctx)
    except Exception:
        # One broken page must never take the whole device down.
        log.exception("screen %s failed to render", screen.name)
        widgets.draw_centered(canvas.draw, 130, "RENDER ERROR", theme.font(14, bold=True),
                              fill=theme.ERROR)
        widgets.draw_centered(canvas.draw, 152, screen.name.upper(), theme.font(11),
                              fill=theme.TEXT_MUTED)
    status_bar(canvas, screen.title_for(ctx), status, dot=data_light(ctx.snapshot))
    footer(canvas, hints(screen, armed))
    if ctx.toast:
        toast(canvas, ctx.toast, TOAST_TONES.get(ctx.toast_kind, ""))
    return canvas.image
