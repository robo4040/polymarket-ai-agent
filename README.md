# Polymarket AI Trading Agent (Mobile Friendly)

Paper-trading AI agent focused **only on Polymarket**.

Features:
- Research agent (scans markets + estimates probability + Kelly sizing)
- Copy-trading of any Polymarket wallets you add
- Full risk management (half-Kelly, position limits, daily loss stop)
- **Mobile-friendly web dashboard** (works great on phone)

---

## Quick Start

### 1. Install (one time)

```bash
cd ai-trading-agent
python -m venv venv
source venv/bin/activate          # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Run the Web Dashboard

```bash
streamlit run dashboard/app.py --server.port 8501
```

Then open the link that appears (usually http://localhost:8501) in your phone browser.

If you are running this on a cloud server / VPS, you can access it from your phone using the public IP or a free tunnel (ngrok, cloudflared, etc.).

### 3. Using the Dashboard

- **Run tab** → Choose strategy (Research / Copy / Both) → Press “Run One Cycle”
- **Positions** → See open positions and recent trades
- **Copy Wallets** → Paste any Polymarket wallet address you want to mirror
- **Settings** → Current risk rules

---

## How the Agent Works

1. **Research mode**  
   Scans active Polymarket markets → asks an LLM for true probability → calculates edge → sizes with fractional Kelly → opens paper positions.

2. **Copy mode**  
   You add wallet addresses → agent watches them → when they open/increase a position, it mirrors (scaled to your bankroll) while respecting risk limits.

3. **Risk controls** (always on)
   - Half-Kelly (or whatever you set)
   - Max 10% per position
   - Max 40% total portfolio heat
   - Daily loss limit
   - Minimum edge filter

---

## Recommended First Steps

1. Run several paper cycles with **Research only**.
2. Go to public Polymarket leaderboards / copy-trading sites and find 2–5 strong wallets.
3. Add those wallets in the **Copy Wallets** tab.
4. Switch to **Both** and keep running cycles.
5. After you are happy with paper results, we can discuss going live (requires a Polygon wallet + private key).

---

## Going Live later (optional)

When you are ready for real money on Polymarket:

1. Create a Polygon wallet
2. Get some USDC on Polygon
3. Set in `.env`:
   ```
   MODE=live_poly
   POLY_PRIVATE_KEY=0x...
   POLY_FUNDER_ADDRESS=0x...
   ```
4. Install the official client (`py-clob-client-v2` or `polymarket-client`)

---

## Important Warnings

- This is currently **paper trading** by default.
- Past performance of any wallet or AI agent does **not** guarantee future results.
- Start small. Never risk money you cannot afford to lose.
- Always do your own research on wallets you decide to copy.

---

Built for mobile-first use. Enjoy and trade responsibly.
