"""
Kelly Criterion utilities for prediction markets and general betting.
"""

from typing import Optional
import math


def kelly_fraction(
    true_prob: float,
    market_price: float,
    fraction: float = 0.5,
    max_fraction: float = 0.25,
) -> float:
    """
    Calculate fractional Kelly for a binary market.

    For buying YES at price p when true probability is q:
        edge = q - p
        b = (1 - p) / p          # net odds
        full_kelly = (b * q - (1 - q)) / b = (q - p) / (1 - p)

    We return fraction * full_kelly, capped at max_fraction of bankroll.
    """
    if market_price <= 0 or market_price >= 1:
        return 0.0
    if true_prob <= market_price:
        return 0.0  # no edge

    full = (true_prob - market_price) / (1.0 - market_price)
    sized = full * fraction
    return max(0.0, min(sized, max_fraction))


def position_size_usd(
    bankroll: float,
    true_prob: float,
    market_price: float,
    kelly_frac: float = 0.5,
    max_pct: float = 0.10,
) -> float:
    """Return recommended USD size to risk / allocate."""
    f = kelly_fraction(true_prob, market_price, fraction=kelly_frac, max_fraction=max_pct)
    return bankroll * f


def shares_from_usd(usd: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return usd / price
