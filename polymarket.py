"""
Polymarket data + trading client (paper + live hooks).
Uses public Gamma API for market discovery (no auth required).
Live trading requires py-clob-client-v2 or official polymarket-client.
"""

from __future__ import annotations
import requests
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from config import cfg


@dataclass
class Market:
    id: str
    question: str
    slug: str
    outcome_prices: List[float]      # [yes, no]
    token_ids: List[str]             # [yes_token, no_token]
    volume: float
    liquidity: float
    end_date: Optional[str]
    category: str = ""
    active: bool = True
    raw: Dict[str, Any] = None


class PolymarketClient:
    def __init__(self):
        self.gamma = cfg.gamma_host
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ai-trading-agent/1.0"})
        self._clob = None  # lazy live client

    # ------------------------------------------------------------------
    # Public market data (Gamma)
    # ------------------------------------------------------------------
    def get_markets(
        self,
        limit: int = 50,
        active: bool = True,
        closed: bool = False,
        order: str = "volume24hr",
    ) -> List[Market]:
        """Fetch active markets sorted by recent volume."""
        url = f"{self.gamma}/markets"
        params = {
            "limit": limit,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": "false",
        }
        try:
            r = self.session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[Polymarket] get_markets error: {e}")
            return []

        markets = []
        for m in data:
            try:
                prices = m.get("outcomePrices") or m.get("outcome_prices") or ["0.5", "0.5"]
                if isinstance(prices, str):
                    import json
                    prices = json.loads(prices)
                prices = [float(p) for p in prices]

                tokens = m.get("clobTokenIds") or m.get("clob_token_ids") or []
                if isinstance(tokens, str):
                    import json
                    tokens = json.loads(tokens)

                markets.append(Market(
                    id=str(m.get("id") or m.get("conditionId") or ""),
                    question=m.get("question", ""),
                    slug=m.get("slug", ""),
                    outcome_prices=prices,
                    token_ids=tokens,
                    volume=float(m.get("volume") or m.get("volumeNum") or 0),
                    liquidity=float(m.get("liquidity") or m.get("liquidityNum") or 0),
                    end_date=m.get("endDate") or m.get("end_date_iso"),
                    category=m.get("category") or (m.get("tags") or [""])[0] if m.get("tags") else "",
                    active=bool(m.get("active", True)),
                    raw=m,
                ))
            except Exception:
                continue
        return markets

    def get_market(self, market_id: str) -> Optional[Market]:
        url = f"{self.gamma}/markets/{market_id}"
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            m = r.json()
            # Reuse parsing logic... simplified
            prices = [float(p) for p in (m.get("outcomePrices") or ["0.5", "0.5"])]
            tokens = m.get("clobTokenIds") or []
            return Market(
                id=str(m.get("id")),
                question=m.get("question", ""),
                slug=m.get("slug", ""),
                outcome_prices=prices,
                token_ids=tokens,
                volume=float(m.get("volume") or 0),
                liquidity=float(m.get("liquidity") or 0),
                end_date=m.get("endDate"),
                raw=m,
            )
        except Exception as e:
            print(f"[Polymarket] get_market error: {e}")
            return None

    def get_mid_price(self, token_id: str) -> Optional[float]:
        """Best effort mid from public orderbook or last trade."""
        # Gamma doesn't always give live book; for paper we can use outcomePrices
        # For better accuracy in live, use CLOB /book endpoint
        return None  # caller should use market.outcome_prices

    # ------------------------------------------------------------------
    # Live trading hooks (require py-clob-client-v2)
    # ------------------------------------------------------------------
    def _init_live_client(self):
        if self._clob is not None:
            return self._clob
        if not cfg.poly_private_key:
            raise RuntimeError("POLY_PRIVATE_KEY not set for live trading")
        try:
            from py_clob_client_v2 import ClobClient, ApiCreds
            # Adjust import according to installed package version
            client = ClobClient(
                host=cfg.poly_host,
                key=cfg.poly_private_key,
                chain_id=cfg.chain_id,
                signature_type=cfg.poly_signature_type,
                funder=cfg.poly_funder or None,
            )
            creds = client.create_or_derive_api_key()
            client.set_api_creds(creds)
            self._clob = client
            return client
        except ImportError:
            raise RuntimeError(
                "Install py-clob-client-v2 or polymarket-client for live trading.\n"
                "See https://docs.polymarket.com"
            )

    def place_order_live(self, token_id: str, side: str, price: float, size: float) -> Dict:
        """Place a limit order. side = 'BUY' or 'SELL'."""
        client = self._init_live_client()
        # Implementation depends on exact client version – see official examples
        # This is a placeholder that shows the shape
        raise NotImplementedError(
            "Live order placement: implement using current py-clob-client-v2 docs. "
            "Paper mode is fully functional."
        )

    def get_positions_live(self) -> List[Dict]:
        client = self._init_live_client()
        # return client.get_positions() or equivalent
        return []
