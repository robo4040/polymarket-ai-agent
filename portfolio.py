"""
Unified portfolio tracker for paper and live modes.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import json
import os
from pathlib import Path


@dataclass
class Position:
    market_id: str
    token_id: str
    side: str                 # "YES" or "NO"
    size: float               # number of shares
    avg_price: float          # average entry price (0-1 for Polymarket)
    cost_basis: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "research"  # "research" | "copy" | "manual"
    meta: Dict[str, Any] = field(default_factory=dict)

    def update_price(self, price: float):
        self.current_price = price
        self.unrealized_pnl = (price - self.avg_price) * self.size


@dataclass
class Trade:
    timestamp: str
    market_id: str
    token_id: str
    side: str
    action: str               # "BUY" | "SELL"
    size: float
    price: float
    fee: float
    pnl: float = 0.0
    source: str = "research"
    notes: str = ""


class Portfolio:
    def __init__(self, starting_cash: float, data_dir: str = None):
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.positions: Dict[str, Position] = {}  # key = token_id
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict[str, Any]] = []
        if data_dir is None:
            data_dir = "/tmp/ai-trading-agent-data"
        self.data_dir = Path(data_dir)
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            self.data_dir = Path("/tmp")
        self._load()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def buy(self, market_id: str, token_id: str, side: str, size: float,
            price: float, fee: float = 0.0, source: str = "research",
            notes: str = "", meta: Optional[Dict] = None) -> bool:
        cost = size * price + fee
        if cost > self.cash + 1e-9:
            return False

        self.cash -= cost
        key = token_id
        if key in self.positions:
            pos = self.positions[key]
            total_size = pos.size + size
            pos.avg_price = (pos.avg_price * pos.size + price * size) / total_size
            pos.size = total_size
            pos.cost_basis += cost
        else:
            self.positions[key] = Position(
                market_id=market_id,
                token_id=token_id,
                side=side,
                size=size,
                avg_price=price,
                cost_basis=cost,
                current_price=price,
                source=source,
                meta=meta or {},
            )

        self.trades.append(Trade(
            timestamp=datetime.now(timezone.utc).isoformat(),
            market_id=market_id,
            token_id=token_id,
            side=side,
            action="BUY",
            size=size,
            price=price,
            fee=fee,
            source=source,
            notes=notes,
        ))
        self._save()
        return True

    def sell(self, token_id: str, size: float, price: float,
             fee: float = 0.0, notes: str = "") -> bool:
        if token_id not in self.positions:
            return False
        pos = self.positions[token_id]
        if size > pos.size + 1e-9:
            size = pos.size

        proceeds = size * price - fee
        pnl = (price - pos.avg_price) * size - fee
        self.cash += proceeds
        pos.size -= size
        pos.realized_pnl += pnl

        self.trades.append(Trade(
            timestamp=datetime.now(timezone.utc).isoformat(),
            market_id=pos.market_id,
            token_id=token_id,
            side=pos.side,
            action="SELL",
            size=size,
            price=price,
            fee=fee,
            pnl=pnl,
            source=pos.source,
            notes=notes,
        ))

        if pos.size < 1e-9:
            del self.positions[token_id]
        self._save()
        return True

    def mark_to_market(self, price_map: Dict[str, float]):
        """price_map: token_id -> current mid price"""
        for tid, pos in self.positions.items():
            if tid in price_map:
                pos.update_price(price_map[tid])

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    @property
    def equity(self) -> float:
        return self.cash + sum(p.size * p.current_price for p in self.positions.values())

    @property
    def exposure(self) -> float:
        return sum(p.size * p.current_price for p in self.positions.values())

    @property
    def heat(self) -> float:
        eq = self.equity
        return self.exposure / eq if eq > 0 else 0.0

    def record_equity(self):
        self.equity_curve.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "equity": self.equity,
            "cash": self.cash,
            "exposure": self.exposure,
            "n_positions": len(self.positions),
        })
        self._save()

    def summary(self) -> Dict[str, Any]:
        return {
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "exposure": round(self.exposure, 2),
            "heat": round(self.heat, 3),
            "n_positions": len(self.positions),
            "realized_pnl": round(sum(t.pnl for t in self.trades), 2),
            "starting_capital": self.starting_cash,
            "return_pct": round((self.equity / self.starting_cash - 1) * 100, 2),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save(self):
        state = {
            "cash": self.cash,
            "starting_cash": self.starting_cash,
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trades": [asdict(t) for t in self.trades[-500:]],  # keep last 500
            "equity_curve": self.equity_curve[-1000:],
        }
        path = self.data_dir / "portfolio.json"
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

    def _load(self):
        path = self.data_dir / "portfolio.json"
        if not path.exists():
            return
        try:
            with open(path) as f:
                state = json.load(f)
            self.cash = state.get("cash", self.starting_cash)
            self.starting_cash = state.get("starting_cash", self.starting_cash)
            for k, v in state.get("positions", {}).items():
                self.positions[k] = Position(**v)
            self.trades = [Trade(**t) for t in state.get("trades", [])]
            self.equity_curve = state.get("equity_curve", [])
        except Exception as e:
            print(f"[Portfolio] load error: {e}")
