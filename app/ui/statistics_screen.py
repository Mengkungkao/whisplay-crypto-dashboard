"""Page 4 -- Bitcoin statistics.

Builds a list of available metrics and lays them into a two-column grid,
skipping anything the provider did not return.
"""

from __future__ import annotations

from app.ui import theme, widgets
from app.ui.base import Screen
from app.utils.format import (
    format_compact,
    format_percent,
    format_price,
    format_supply,
)

BLOCK_HEIGHT = 32
COLUMN_X = (14, 126)

# The page name spells the asset out when it comfortably fits the width.
FULL_NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP"}


class StatisticsScreen(Screen):
    name = "statistics"
    title = "Statistics"

    def title_for(self, ctx) -> str:
        return FULL_NAMES.get(ctx.settings.symbol, ctx.settings.symbol)

    def render(self, draw, ctx):
        snap = ctx.snapshot
        settings = ctx.settings
        market = snap.market

        top = theme.CONTENT_TOP

        # --- headline price ------------------------------------------------
        price_text = format_price(snap.best_price, settings.currency)
        price_font = theme.fit_font(draw, price_text, 150, (26, 23, 20, 18), bold=True)
        draw.text((14, top), price_text, font=price_font, fill=theme.TEXT)
        widgets.draw_change(draw, 14, top + 30, snap.best_change_24h, font_size=13)

        if market.market_cap_rank is not None:
            fnt = theme.font(11, bold=True)
            text = f"Rank #{market.market_cap_rank}"
            width = theme.text_width(draw, text, fnt)
            draw.text(
                (theme.SCREEN_WIDTH - 14 - width, top + 6),
                text, font=fnt, fill=theme.ACCENT,
            )

        # --- metric grid ----------------------------------------------------
        blocks = self._collect(market, settings)
        if not blocks:
            widgets.draw_centered(
                draw, 150, "No statistics", theme.font(13, bold=True),
                fill=theme.TEXT_MUTED,
            )
            return

        top += 54
        draw.line(
            [(14, top - 6), (theme.SCREEN_WIDTH - 14, top - 6)],
            fill=theme.DIVIDER, width=1,
        )

        rows_available = (theme.CONTENT_BOTTOM - top + 4) // BLOCK_HEIGHT
        for index, (label, value, color) in enumerate(blocks[: rows_available * 2]):
            col = index % 2
            row = index // 2
            widgets.draw_label_value(
                draw, COLUMN_X[col], top + row * BLOCK_HEIGHT, label, value,
                value_color=color, label_size=9, value_size=14,
            )

    def _collect(self, market, settings) -> list:
        """Ordered by usefulness; None values are dropped entirely."""
        currency = settings.currency
        candidates = [
            ("Market cap", market.market_cap,
             lambda v: format_compact(v, currency), theme.TEXT),
            ("24H volume", market.volume_24h,
             lambda v: format_compact(v, currency), theme.TEXT),
            ("24H high", market.high_24h,
             lambda v: format_price(v, currency, 0), theme.UP),
            ("24H low", market.low_24h,
             lambda v: format_price(v, currency, 0), theme.DOWN),
            ("Supply", market.circulating_supply,
             lambda v: format_supply(v, settings.symbol), theme.TEXT),
            ("Max supply", market.max_supply,
             lambda v: format_supply(v, settings.symbol), theme.TEXT_DIM),
            ("All-time high", market.ath,
             lambda v: format_price(v, currency, 0), theme.TEXT),
            ("From ATH", market.ath_change_pct,
             lambda v: format_percent(v, 1), None),
            ("7D change", market.change_7d_pct,
             lambda v: format_percent(v, 1), None),
            ("30D change", market.change_30d_pct,
             lambda v: format_percent(v, 1), None),
        ]

        blocks = []
        for label, value, formatter, color in candidates:
            if value is None:
                continue
            # A None colour means "colour by direction".
            resolved = color if color is not None else theme.change_color(value)
            blocks.append((label, formatter(value), resolved))
        return blocks
