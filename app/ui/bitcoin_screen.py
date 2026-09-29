r"""Page 1 -- Bitcoin home.

    +----------------------+
    | BTC/USD   LIVE  ≋ 82%|   status bar (MFruit OS)
    | $112,540.32          |
    | ^ +2.41%    H/L      |
    |                      |
    |      /\              |
    |    /    \/\          |
    |  /          \        |
    |                      |
    | 1H  4H  1D  1W  1Y   |
    | tap next  hold ...   |   footer hints (MFruit OS)
    +----------------------+

The price is the largest element on the screen; everything else is
subordinate to it.
"""

from __future__ import annotations

from app.chart.renderer import render_chart
from app.market.provider import TIMEFRAMES
from app.ui import theme, widgets
from app.ui.base import Screen
from app.utils.format import format_clock, format_compact, format_price

PRICE_SIZES = (34, 30, 27, 24, 21)


class BitcoinScreen(Screen):
    name = "bitcoin"
    title = "BTC/USD"
    select_label = "timeframe"

    def title_for(self, ctx) -> str:
        return ctx.settings.pair_label

    def render(self, draw, ctx):
        snap = ctx.snapshot
        settings = ctx.settings
        top = theme.CONTENT_TOP

        # --- price ------------------------------------------------------
        price_text = format_price(snap.best_price, settings.currency)
        price_font = theme.fit_font(draw, price_text, 212, PRICE_SIZES, bold=True)
        price_color = theme.TEXT if snap.has_any_data else theme.TEXT_MUTED
        draw.text((14, top), price_text, font=price_font, fill=price_color)

        # --- 24h change + high/low --------------------------------------
        widgets.draw_change(draw, 14, top + 40, snap.best_change_24h, font_size=16)

        market = snap.market
        if market.high_24h is not None and market.low_24h is not None:
            fnt = theme.font(10, bold=True)
            high = format_compact(market.high_24h, settings.currency)
            low = format_compact(market.low_24h, settings.currency)
            text = f"H {high}   L {low}"
            width = theme.text_width(draw, text, fnt)
            draw.text(
                (theme.SCREEN_WIDTH - 14 - width, top + 44),
                text, font=fnt, fill=theme.TEXT_MUTED,
            )

        # --- chart -------------------------------------------------------
        render_chart(
            draw, snap.chart, (0, top + 62, theme.SCREEN_WIDTH - 8, top + 154),
            currency=settings.currency,
        )

        # --- window performance, and how fresh the data is ---------------
        row = top + 160
        change = snap.chart.change_pct if snap.chart is not None else None
        if change is not None:
            fnt = theme.font(10, bold=True)
            label = f"{snap.timeframe} CHANGE"
            draw.text((14, row + 2), label, font=fnt, fill=theme.TEXT_MUTED)
            widgets.draw_change(draw, 14 + theme.text_width(draw, label, fnt) + 8,
                                row, change, font_size=12)

        fnt = theme.font(10, bold=True)
        if not snap.online and snap.last_success:
            text, color = f"LAST {format_clock(snap.last_success)[:5]}", theme.WARN
        elif not snap.has_any_data:
            text, color = "CONNECTING…", theme.TEXT_MUTED
        elif market.volume_24h is not None:
            text = f"VOL {format_compact(market.volume_24h, settings.currency)}"
            color = theme.TEXT_DIM
        else:
            text = ""
        if text:
            width = theme.text_width(draw, text, fnt)
            draw.text((theme.SCREEN_WIDTH - 14 - width, row + 2), text, font=fnt, fill=color)

        # --- timeframe selector ------------------------------------------
        widgets.draw_timeframe_strip(draw, top + 182, TIMEFRAMES, snap.timeframe, height=22)
