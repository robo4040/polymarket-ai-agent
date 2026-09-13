"""
Research agent: scans markets, estimates true probability via LLM, applies Kelly.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from data.polymarket import PolymarketClient, Market
from strategies.kelly import position_size_usd, shares_from_usd
from utils.llm import chat
from config import cfg
from core.portfolio import Portfolio
from core.risk import RiskManager


@dataclass
class Opportunity:
    market: Market
    side: str                 # "YES" or "NO"
    token_id: str
    market_price: float
    estimated_prob: float
    edge: float
    size_usd: float
    shares: float
    reason: str


class ResearchAgent:
    def __init__(self, poly: PolymarketClient, portfolio: Portfolio, risk: RiskManager):
        self.poly = poly
        self.portfolio = portfolio
        self.risk = risk

    def scan(self, limit: int = 30) -> List[Opportunity]:
        markets = self.poly.get_markets(limit=limit, active=True)
        opps: List[Opportunity] = []

        for m in markets:
            if m.liquidity < cfg.risk.min_liquidity_usd:
                continue
            if not m.token_ids or len(m.outcome_prices) < 2:
                continue

            # Simple: evaluate YES side primarily
            yes_price = m.outcome_prices[0]
            no_price = m.outcome_prices[1] if len(m.outcome_prices) > 1 else 1 - yes_price

            # Skip extreme prices (especially important with heuristic LLM)
            if yes_price < 0.05 or yes_price > 0.95:
                continue

            est = self._estimate_probability(m)
            if est is None:
                continue

            # Check YES
            edge_yes = est - yes_price
            if edge_yes >= cfg.risk.min_edge:
                size = position_size_usd(
                    self.portfolio.equity,
                    est,
                    yes_price,
                    kelly_frac=cfg.risk.kelly_fraction,
                    max_pct=cfg.risk.max_position_pct,
                )
                decision = self.risk.check_trade(size, is_new_position=True)
                if decision.allowed or decision.max_size_usd > 10:
                    final_size = min(size, decision.max_size_usd) if not decision.allowed else size
                    if final_size > 5:
                        opps.append(Opportunity(
                            market=m,
                            side="YES",
                            token_id=m.token_ids[0],
                            market_price=yes_price,
                            estimated_prob=est,
                            edge=edge_yes,
                            size_usd=final_size,
                            shares=shares_from_usd(final_size, yes_price),
                            reason=f"LLM est={est:.2f} vs market={yes_price:.2f}",
                        ))

            # Check NO (symmetric)
            edge_no = (1 - est) - no_price
            if edge_no >= cfg.risk.min_edge and len(m.token_ids) > 1:
                size = position_size_usd(
                    self.portfolio.equity,
                    1 - est,
                    no_price,
                    kelly_frac=cfg.risk.kelly_fraction,
                    max_pct=cfg.risk.max_position_pct,
                )
                decision = self.risk.check_trade(size, is_new_position=True)
                if decision.allowed or decision.max_size_usd > 10:
                    final_size = min(size, decision.max_size_usd) if not decision.allowed else size
                    if final_size > 5:
                        opps.append(Opportunity(
                            market=m,
                            side="NO",
                            token_id=m.token_ids[1],
                            market_price=no_price,
                            estimated_prob=1 - est,
                            edge=edge_no,
                            size_usd=final_size,
                            shares=shares_from_usd(final_size, no_price),
                            reason=f"LLM est={1-est:.2f} vs market={no_price:.2f}",
                        ))

        # Sort by edge
        opps.sort(key=lambda o: o.edge, reverse=True)
        return opps

    def _estimate_probability(self, market: Market) -> Optional[float]:
        prompt = f"""You are a careful prediction market analyst.
Question: {market.question}
Current YES price: {market.outcome_prices[0]:.3f}
Volume: ${market.volume:,.0f} | Liquidity: ${market.liquidity:,.0f}

Estimate the true probability that the answer is YES.
Reply with ONLY a number between 0.01 and 0.99 (e.g. 0.62).
No explanation."""

        messages = [
            {"role": "system", "content": "You are a calibrated probability estimator. Be conservative."},
            {"role": "user", "content": prompt},
        ]
        raw = chat(messages).strip()
        try:
            # Extract first float-looking number
            import re
            match = re.search(r"0\.\d+|\d+\.\d+", raw)
            if match:
                p = float(match.group())
                return max(0.01, min(0.99, p))
        except Exception:
            pass
        return None
