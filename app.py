"""
Mobile-friendly Polymarket AI Trading Agent Dashboard
Run with: streamlit run dashboard/app.py --server.port 8501
"""

import sys
import os
from pathlib import Path

# Make sure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from datetime import datetime, timezone
import time

from config import cfg
from core.portfolio import Portfolio
from core.risk import RiskManager
from data.polymarket import PolymarketClient
from data.wallets import WalletTracker
from strategies.research_agent import ResearchAgent
from strategies.copy_trader import CopyTrader
from strategies.kelly import shares_from_usd

st.set_page_config(
    page_title="Polymarket AI Agent",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS for better mobile experience
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-size: 1.1em;
    }
    .metric-card {
        background: #1e1e1e;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
    }
    h1, h2, h3 { text-align: center; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_engine_components():
    portfolio = Portfolio(cfg.starting_capital)
    risk = RiskManager(portfolio)
    poly = PolymarketClient()
    tracker = WalletTracker()
    research = ResearchAgent(poly, portfolio, risk)
    copy = CopyTrader(tracker, portfolio, risk)
    return portfolio, risk, poly, tracker, research, copy


portfolio, risk, poly, tracker, research, copy = get_engine_components()


def main():
    st.title("📈 Polymarket AI Agent")
    st.caption("Paper trading • Research + Copy Trading")

    # ---- Status ----
    summary = portfolio.summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("Equity", f"${summary['equity']:,.2f}", f"{summary['return_pct']:+.1f}%")
    col2.metric("Cash", f"${summary['cash']:,.2f}")
    col3.metric("Positions", summary['n_positions'])

    st.divider()

    # ---- Tabs ----
    tab1, tab2, tab3, tab4 = st.tabs(["▶ Run", "📋 Positions", "👥 Copy Wallets", "⚙️ Settings"])

    with tab1:
        st.subheader("Run Agent Cycle")
        strategy = st.radio(
            "Strategy",
            ["Research only", "Copy only", "Both"],
            horizontal=True,
            index=2,
        )
        strategy_map = {
            "Research only": "research",
            "Copy only": "copy",
            "Both": "both",
        }

        if st.button("🚀 Run One Cycle", type="primary"):
            with st.spinner("Scanning markets & generating signals..."):
                run_cycle(strategy_map[strategy])
            st.success("Cycle completed!")
            st.rerun()

        st.info("Tip: Run a cycle every few minutes while testing. Later we can make it automatic.")

    with tab2:
        st.subheader("Open Positions")
        if not portfolio.positions:
            st.write("No open positions yet.")
        else:
            for tid, pos in portfolio.positions.items():
                with st.container():
                    st.markdown(f"**{pos.side}** · {pos.source}")
                    st.write(f"Size: {pos.size:.1f} @ {pos.avg_price:.3f} → {pos.current_price:.3f}")
                    st.write(f"Unrealized PnL: **{pos.unrealized_pnl:+.2f}**")
                    st.caption(f"Opened: {pos.opened_at[:19]}")
                    st.divider()

        st.subheader("Recent Trades")
        if not portfolio.trades:
            st.write("No trades yet.")
        else:
            for t in reversed(portfolio.trades[-10:]):
                st.write(f"{t.action} {t.side} {t.size:.1f} @ {t.price:.3f} | {t.source} | {t.notes[:40]}")

    with tab3:
        st.subheader("Copy Trading Wallets")
        st.write("Add Polymarket wallet addresses you want to copy.")

        new_wallet = st.text_input("Wallet address (0x...)", placeholder="0x...")
        if st.button("➕ Add Wallet") and new_wallet:
            tracker.add_wallet(new_wallet.strip())
            st.success(f"Added {new_wallet[:10]}...")
            st.rerun()

        st.write("**Currently tracking:**")
        if not tracker.wallets:
            st.warning("No wallets added yet. Find top wallets on Polymarket leaderboards.")
        else:
            for w in tracker.wallets:
                st.code(w)

        st.caption("You can find strong wallets on public Polymarket leaderboards / copy-trading sites.")

    with tab4:
        st.subheader("Risk Settings (current)")
        st.write(f"• Starting capital: **${cfg.starting_capital:,.0f}**")
        st.write(f"• Kelly fraction: **{cfg.risk.kelly_fraction}×** (half-Kelly recommended)")
        st.write(f"• Max position: **{cfg.risk.max_position_pct:.0%}** of equity")
        st.write(f"• Max portfolio heat: **{cfg.risk.max_portfolio_heat:.0%}**")
        st.write(f"• Min edge required: **{cfg.risk.min_edge:.0%}**")
        st.write(f"• Daily loss limit: **{cfg.risk.daily_loss_limit_pct:.0%}**")

        st.divider()
        st.subheader("How to improve results")
        st.markdown("""
        1. Add a real LLM key (Anthropic / OpenAI) in `.env` for better probability estimates  
        2. Add high-quality wallets to copy  
        3. Start with small capital and paper trade for several days  
        4. Never risk money you cannot afford to lose
        """)


def run_cycle(strategy: str):
    """Execute one research / copy cycle and update portfolio."""
    # Mark to market
    markets = poly.get_markets(limit=80)
    price_map = {}
    for m in markets:
        if m.token_ids and m.outcome_prices:
            price_map[m.token_ids[0]] = m.outcome_prices[0]
            if len(m.token_ids) > 1:
                price_map[m.token_ids[1]] = m.outcome_prices[1]
    portfolio.mark_to_market(price_map)
    portfolio.record_equity()

    # Research
    if strategy in ("research", "both"):
        opps = research.scan(limit=40)
        for opp in opps[:5]:
            fee = opp.size_usd * 0.002
            portfolio.buy(
                market_id=opp.market.id,
                token_id=opp.token_id,
                side=opp.side,
                size=opp.shares,
                price=opp.market_price,
                fee=fee,
                source="research",
                notes=opp.reason,
                meta={"edge": opp.edge},
            )

    # Copy
    if strategy in ("copy", "both"):
        actions = copy.generate_actions()
        for act in actions:
            if act["action"] == "BUY":
                shares = shares_from_usd(act["size_usd"], act["price"])
                portfolio.buy(
                    market_id=act["market_id"],
                    token_id=act["token_id"],
                    side=act["side"],
                    size=shares,
                    price=act["price"],
                    fee=act["size_usd"] * 0.002,
                    source="copy",
                    notes=act.get("notes", ""),
                )
            elif act["action"] == "SELL":
                shares = act.get("shares") or shares_from_usd(act["size_usd"], act["price"])
                portfolio.sell(
                    token_id=act["token_id"],
                    size=shares,
                    price=act["price"],
                    notes=act.get("notes", ""),
                )


if __name__ == "__main__":
    main()
