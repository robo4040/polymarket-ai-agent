"""
Risk manager — enforces all hard limits before any trade is allowed.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
from core.portfolio import Portfolio
from config import cfg


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    max_size_usd: float = 0.0


class RiskManager:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.daily_start_equity: Optional[float] = None
        self._reset_daily_if_needed()

    def _reset_daily_if_needed(self):
        # Simple: reset every time equity is recorded at start of day (caller responsibility)
        if self.daily_start_equity is None:
            self.daily_start_equity = self.portfolio.equity

    def check_trade(
        self,
        proposed_usd: float,
        token_id: Optional[str] = None,
        is_new_position: bool = True,
    ) -> RiskDecision:
        eq = self.portfolio.equity
        if eq <= 0:
            return RiskDecision(False, "Equity is zero or negative")

        # Daily loss limit
        if self.daily_start_equity and self.daily_start_equity > 0:
            day_pnl_pct = (eq - self.daily_start_equity) / self.daily_start_equity
            if day_pnl_pct <= -cfg.risk.daily_loss_limit_pct:
                return RiskDecision(False, f"Daily loss limit hit ({day_pnl_pct:.1%})")

        # Max open positions
        if is_new_position and len(self.portfolio.positions) >= cfg.risk.max_open_positions:
            return RiskDecision(False, "Max open positions reached")

        # Portfolio heat
        current_heat = self.portfolio.heat
        additional_heat = proposed_usd / eq
        if current_heat + additional_heat > cfg.risk.max_portfolio_heat:
            max_allowed = max(0.0, (cfg.risk.max_portfolio_heat - current_heat) * eq)
            return RiskDecision(
                False,
                f"Portfolio heat would exceed {cfg.risk.max_portfolio_heat:.0%}",
                max_size_usd=max_allowed,
            )

        # Single position limit
        max_by_position = eq * cfg.risk.max_position_pct
        if proposed_usd > max_by_position:
            return RiskDecision(
                False,
                f"Exceeds max position size ({cfg.risk.max_position_pct:.0%})",
                max_size_usd=max_by_position,
            )

        return RiskDecision(True, "OK", max_size_usd=proposed_usd)

    def reset_daily(self):
        self.daily_start_equity = self.portfolio.equity
