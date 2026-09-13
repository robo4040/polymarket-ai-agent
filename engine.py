"""
Main trading engine — orchestrates research, copy trading, risk, and portfolio.
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from rich.console import Console
from rich.table import Table

from config import cfg
from core.portfolio import Portfolio
from core.risk import RiskManager
from data.polymarket import PolymarketClient
from data.wallets import WalletTracker
from data.exness import ExnessClient
from strategies.research_agent import ResearchAgent
from strategies.copy_trader import CopyTrader
from strategies.kelly import shares_from_usd


console = Console()


class Engine:
    def __init__(self):
        self.portfolio = Portfolio(cfg.starting_capital)
        self.risk = RiskManager(self.portfolio)
        self.poly = PolymarketClient()
        self.tracker = WalletTracker()
        self.research = ResearchAgent(self.poly, self.portfolio, self.risk)
        self.copy = CopyTrader(self.tracker, self.portfolio, self.risk)
        self.exness = ExnessClient() if cfg.is_live_exness() else None

        if cfg.is_live_exness() and self.exness:
            self.exness.connect()

    def run_once(self, strategies: str = "both"):
        """One full cycle."""
        console.rule(f"[bold]Cycle @ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # 1. Mark positions to market (best effort)
        markets = self.poly.get_markets(limit=100)
        price_map = {}
        for m in markets:
            if m.token_ids and m.outcome_prices:
                price_map[m.token_ids[0]] = m.outcome_prices[0]
                if len(m.token_ids) > 1:
                    price_map[m.token_ids[1]] = m.outcome_prices[1]
        self.portfolio.mark_to_market(price_map)
        self.portfolio.record_equity()

        # 2. Research agent
        if strategies in ("research", "both"):
            opps = self.research.scan(limit=40)
            console.print(f"[cyan]Research found {len(opps)} opportunities[/]")
            for opp in opps[:5]:  # take top 5 by edge
                self._execute_research(opp)

        # 3. Copy trading
        if strategies in ("copy", "both"):
            actions = self.copy.generate_actions()
            console.print(f"[cyan]Copy signals: {len(actions)}[/]")
            for act in actions:
                self._execute_copy(act)

        # 4. Status
        self._print_status()

    def _execute_research(self, opp):
        if cfg.is_paper() or cfg.is_live_poly():
            fee = opp.size_usd * 0.002  # rough fee model
            ok = self.portfolio.buy(
                market_id=opp.market.id,
                token_id=opp.token_id,
                side=opp.side,
                size=opp.shares,
                price=opp.market_price,
                fee=fee,
                source="research",
                notes=opp.reason,
                meta={"edge": opp.edge, "est_prob": opp.estimated_prob},
            )
            if ok:
                console.print(
                    f"[green]RESEARCH BUY[/] {opp.side} {opp.shares:.1f} @ {opp.market_price:.3f} "
                    f"(${opp.size_usd:.0f}) | {opp.market.question[:60]}…"
                )
            else:
                console.print(f"[yellow]Skipped (insufficient cash or risk)[/] {opp.market.question[:50]}")

    def _execute_copy(self, act: dict):
        if act["action"] == "BUY":
            shares = shares_from_usd(act["size_usd"], act["price"])
            fee = act["size_usd"] * 0.002
            ok = self.portfolio.buy(
                market_id=act["market_id"],
                token_id=act["token_id"],
                side=act["side"],
                size=shares,
                price=act["price"],
                fee=fee,
                source="copy",
                notes=act.get("notes", ""),
            )
            if ok:
                console.print(f"[magenta]COPY BUY[/] {act['side']} ${act['size_usd']:.0f} | {act.get('notes')}")
        elif act["action"] == "SELL":
            shares = act.get("shares") or shares_from_usd(act["size_usd"], act["price"])
            ok = self.portfolio.sell(
                token_id=act["token_id"],
                size=shares,
                price=act["price"],
                notes=act.get("notes", ""),
            )
            if ok:
                console.print(f"[magenta]COPY SELL[/] {act.get('notes')}")

    def _print_status(self):
        s = self.portfolio.summary()
        table = Table(title="Portfolio")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        for k, v in s.items():
            table.add_row(k, str(v))
        console.print(table)

        if self.portfolio.positions:
            console.print("\n[bold]Open Positions[/]")
            for tid, pos in list(self.portfolio.positions.items())[:10]:
                console.print(
                    f"  {pos.side:3} | size={pos.size:.1f} @ {pos.avg_price:.3f} "
                    f"→ {pos.current_price:.3f} | uPnL={pos.unrealized_pnl:+.2f} | {pos.source}"
                )

    def run_loop(self, strategies: str = "both", max_cycles: int = 0):
        cycle = 0
        try:
            while True:
                self.run_once(strategies=strategies)
                cycle += 1
                if max_cycles and cycle >= max_cycles:
                    break
                console.print(f"Sleeping {cfg.cycle_seconds}s…\n")
                time.sleep(cfg.cycle_seconds)
        except KeyboardInterrupt:
            console.print("\n[bold red]Stopped by user[/]")
        finally:
            if self.exness:
                self.exness.disconnect()
