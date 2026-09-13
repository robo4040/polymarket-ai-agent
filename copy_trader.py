"""
Copy trading strategy — turns WalletTracker signals into portfolio actions.
"""

from __future__ import annotations
from typing import List
from data.wallets import WalletTracker, CopySignal
from core.portfolio import Portfolio
from core.risk import RiskManager
from config import cfg


class CopyTrader:
    def __init__(self, tracker: WalletTracker, portfolio: Portfolio, risk: RiskManager):
        self.tracker = tracker
        self.portfolio = portfolio
        self.risk = risk

    def generate_actions(self) -> List[dict]:
        """
        Returns a list of proposed actions:
        {
            "action": "BUY" | "SELL",
            "token_id": ...,
            "market_id": ...,
            "side": "YES"/"NO",
            "size_usd": ...,
            "price": ...,
            "source": "copy",
            "notes": ...,
        }
        """
        signals = self.tracker.poll()
        actions = []

        for sig in signals:
            if sig.action in ("OPEN", "INCREASE"):
                decision = self.risk.check_trade(sig.recommended_copy_usd, is_new_position=True)
                size = sig.recommended_copy_usd
                if not decision.allowed:
                    if decision.max_size_usd < 5:
                        continue
                    size = decision.max_size_usd

                actions.append({
                    "action": "BUY",
                    "token_id": sig.token_id,
                    "market_id": sig.market_id,
                    "side": sig.side,
                    "size_usd": size,
                    "price": sig.price,
                    "source": "copy",
                    "notes": f"Copy {sig.wallet[:8]}… {sig.action} | leader ${sig.size_usd:.0f}",
                    "question": sig.question,
                })

            elif sig.action == "CLOSE":
                # Close our position if we have one
                if sig.token_id in self.portfolio.positions:
                    pos = self.portfolio.positions[sig.token_id]
                    actions.append({
                        "action": "SELL",
                        "token_id": sig.token_id,
                        "market_id": sig.market_id,
                        "side": pos.side,
                        "size_usd": pos.size * pos.current_price,
                        "price": pos.current_price or sig.price,
                        "source": "copy",
                        "notes": f"Copy close from {sig.wallet[:8]}…",
                        "shares": pos.size,
                    })

        return actions
