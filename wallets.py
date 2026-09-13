"""
Copy-trading support: track target wallets and surface new positions.
For production you will want on-chain monitoring (Polygon) or a third-party
leaderboard API. This module provides a clean interface + simple polling
against public Polymarket profile data where available.
"""

from __future__ import annotations
import requests
import time
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from config import cfg


@dataclass
class WalletPosition:
    wallet: str
    market_id: str
    token_id: str
    side: str
    size: float
    avg_price: float
    value_usd: float
    timestamp: str
    question: str = ""


@dataclass
class CopySignal:
    wallet: str
    action: str          # "OPEN" | "INCREASE" | "CLOSE"
    market_id: str
    token_id: str
    side: str
    size_usd: float
    price: float
    question: str
    leader_size: float
    recommended_copy_usd: float


class WalletTracker:
    """
    Simple in-memory tracker.
    In production replace `_fetch_wallet_positions` with:
    - Direct Polygon event listening, or
    - A reliable third-party API / leaderboard service, or
    - Official Polymarket profile endpoints if available.
    """

    def __init__(self, wallets: Optional[List[str]] = None):
        self.wallets = wallets or cfg.copy.wallets
        self.last_positions: Dict[str, Dict[str, WalletPosition]] = {}  # wallet -> token_id -> pos
        self.seen_signals: Set[str] = set()
        self.session = requests.Session()

    def add_wallet(self, address: str):
        addr = address.lower()
        if addr not in self.wallets:
            self.wallets.append(addr)

    def _fetch_wallet_positions(self, wallet: str) -> List[WalletPosition]:
        """
        Placeholder. Real implementation options:

        1. Scrape https://polymarket.com/profile/{wallet} (fragile)
        2. Use a data provider that indexes Polymarket positions
        3. Query the CTF / Conditional Tokens contracts on Polygon via web3
        4. Use community leaderboards that expose APIs

        For now returns empty so the rest of the system can be tested.
        """
        # Example of what a real response shape would look like:
        # return [
        #     WalletPosition(
        #         wallet=wallet,
        #         market_id="...",
        #         token_id="...",
        #         side="YES",
        #         size=150.0,
        #         avg_price=0.62,
        #         value_usd=93.0,
        #         timestamp=datetime.now(timezone.utc).isoformat(),
        #         question="Will X happen?",
        #     )
        # ]
        return []

    def poll(self) -> List[CopySignal]:
        signals: List[CopySignal] = []
        for wallet in self.wallets:
            current = {p.token_id: p for p in self._fetch_wallet_positions(wallet)}
            previous = self.last_positions.get(wallet, {})

            # New or increased positions
            for tid, pos in current.items():
                prev = previous.get(tid)
                if prev is None or pos.size > prev.size * 1.05:
                    action = "OPEN" if prev is None else "INCREASE"
                    size_usd = pos.value_usd
                    if size_usd < cfg.copy.min_leader_size_usd:
                        continue
                    copy_usd = min(
                        size_usd * cfg.copy.scale,
                        cfg.copy.max_copy_per_trade_usd,
                    )
                    sig_id = f"{wallet}:{tid}:{action}:{pos.timestamp}"
                    if sig_id in self.seen_signals:
                        continue
                    self.seen_signals.add(sig_id)
                    signals.append(CopySignal(
                        wallet=wallet,
                        action=action,
                        market_id=pos.market_id,
                        token_id=pos.token_id,
                        side=pos.side,
                        size_usd=size_usd,
                        price=pos.avg_price,
                        question=pos.question,
                        leader_size=pos.size,
                        recommended_copy_usd=copy_usd,
                    ))

            # Closed positions
            for tid, prev in previous.items():
                if tid not in current:
                    sig_id = f"{wallet}:{tid}:CLOSE"
                    if sig_id not in self.seen_signals:
                        self.seen_signals.add(sig_id)
                        signals.append(CopySignal(
                            wallet=wallet,
                            action="CLOSE",
                            market_id=prev.market_id,
                            token_id=tid,
                            side=prev.side,
                            size_usd=prev.value_usd,
                            price=prev.avg_price,
                            question=prev.question,
                            leader_size=0,
                            recommended_copy_usd=0,
                        ))

            self.last_positions[wallet] = current
        return signals
