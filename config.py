"""
Central configuration. All values can be overridden by environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RiskConfig:
    max_position_pct: float = float(os.getenv("MAX_POSITION_PCT", 0.10))
    max_portfolio_heat: float = float(os.getenv("MAX_PORTFOLIO_HEAT", 0.40))
    kelly_fraction: float = float(os.getenv("KELLY_FRACTION", 0.5))  # half-Kelly
    min_edge: float = float(os.getenv("MIN_EDGE", 0.05))
    daily_loss_limit_pct: float = float(os.getenv("DAILY_LOSS_LIMIT_PCT", 0.05))
    max_open_positions: int = 15
    min_liquidity_usd: float = 500.0


@dataclass
class CopyConfig:
    # Add real profitable wallets from public leaderboards here
    # Example addresses (replace with current top performers after your own due diligence)
    wallets: List[str] = field(default_factory=lambda: [
        # "0x...",  # example
    ])
    scale: float = float(os.getenv("COPY_SCALE", 0.5))
    poll_seconds: int = int(os.getenv("COPY_POLL_SECONDS", 60))
    min_leader_size_usd: float = 20.0
    max_copy_per_trade_usd: float = 200.0
    allowed_categories: List[str] = field(default_factory=lambda: ["all"])  # or ["Politics", "Crypto", ...]


@dataclass
class Config:
    mode: str = os.getenv("MODE", "paper")  # paper | live_poly | live_exness
    starting_capital: float = float(os.getenv("STARTING_CAPITAL", 1000.0))
    cycle_seconds: int = 120  # main loop interval

    # Polymarket
    poly_host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137

    # LLM
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022")

    # Live credentials
    poly_private_key: str = os.getenv("POLY_PRIVATE_KEY", "")
    poly_funder: str = os.getenv("POLY_FUNDER_ADDRESS", "")
    poly_signature_type: int = int(os.getenv("POLY_SIGNATURE_TYPE", 0))

    mt5_login: int = int(os.getenv("MT5_LOGIN", 0) or 0)
    mt5_password: str = os.getenv("MT5_PASSWORD", "")
    mt5_server: str = os.getenv("MT5_SERVER", "")
    mt5_path: str = os.getenv("MT5_PATH", "")

    risk: RiskConfig = field(default_factory=RiskConfig)
    copy: CopyConfig = field(default_factory=CopyConfig)

    def is_paper(self) -> bool:
        return self.mode == "paper"

    def is_live_poly(self) -> bool:
        return self.mode == "live_poly"

    def is_live_exness(self) -> bool:
        return self.mode == "live_exness"


# Global singleton
cfg = Config()
