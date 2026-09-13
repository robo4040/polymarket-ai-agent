#!/usr/bin/env python3
"""
AI Trading Agent — entry point.

Usage examples:
  python main.py --mode paper --strategy both --capital 1000
  python main.py --mode paper --strategy research --cycles 5
  python main.py --mode paper --strategy copy
"""

import argparse
from config import cfg
from core.engine import Engine
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="AI Trading Agent (Polymarket + Exness)")
    parser.add_argument("--mode", choices=["paper", "live_poly", "live_exness"],
                        default=cfg.mode, help="Trading mode")
    parser.add_argument("--strategy", choices=["research", "copy", "both"],
                        default="both", help="Which strategies to run")
    parser.add_argument("--capital", type=float, default=cfg.starting_capital,
                        help="Starting capital for paper mode")
    parser.add_argument("--cycles", type=int, default=0,
                        help="Number of cycles (0 = infinite)")
    parser.add_argument("--add-wallet", type=str, action="append",
                        help="Add a Polymarket wallet address to copy list")
    args = parser.parse_args()

    # Override config from CLI
    cfg.mode = args.mode
    cfg.starting_capital = args.capital

    console.print(f"""
[bold green]AI Trading Agent[/]
Mode      : {cfg.mode}
Strategy  : {args.strategy}
Capital   : ${cfg.starting_capital:,.2f}
Kelly     : {cfg.risk.kelly_fraction}× | Max pos {cfg.risk.max_position_pct:.0%} | Heat {cfg.risk.max_portfolio_heat:.0%}
""")

    engine = Engine()

    if args.add_wallet:
        for w in args.add_wallet:
            engine.tracker.add_wallet(w)
            console.print(f"Added wallet to copy list: {w}")

    if not cfg.copy.wallets and args.strategy in ("copy", "both"):
        console.print(
            "[yellow]Warning: No copy wallets configured. "
            "Add addresses via config.COPY_WALLETS or --add-wallet[/]"
        )

    engine.run_loop(strategies=args.strategy, max_cycles=args.cycles)


if __name__ == "__main__":
    main()
