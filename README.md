# Crisis bot — run it free, with your PC off

The bot runs on GitHub's servers every Saturday 08:00 (Bangkok time), trades a **334-stock universe on paper: every individual constituent of the NASDAQ-100, Hang Seng Index, FTSE China A50, and EURO STOXX 50, plus your Thai/Vietnam watchlists** (never the indices themselves — those are only the regime gauge). It messages you on Telegram and updates a web dashboard with a stock search box: type any symbol to see the bot's complete history for that stock — open position, pending orders, every live trade, and its 2008–2026 research-backtest trades. Total cost: $0.

Note: with 334 symbols the weekly run takes ~10 minutes of GitHub's free 2,000 min/month — still nothing. Constituent lists are as of Jul 2026; refresh `STOCKS` in `paper_bot.py` once or twice a year as indices rebalance.

## Step 1 — GitHub account + repository (5 min)

1. Sign up at https://github.com (free) if you don't have an account.
2. Click **+** (top right) → **New repository**. Name: `crisis-bot`. Set **Public** (required for the free dashboard; the money is paper so nothing sensitive is exposed — your Telegram token is stored separately as a secret, never in the code).
3. On the new repo page: **uploading an existing file** link → drag ALL files from this `crisis-bot` folder in (including the `docs` folder). One catch: the web uploader can't create the hidden `.github/workflows` folder by drag-drop. Instead click **Add file → Create new file**, type `.github/workflows/bot.yml` as the filename (the slashes create the folders), then paste the contents of `bot.yml` and commit.

## Step 2 — Telegram bot (5 min)

1. In Telegram, message **@BotFather** → send `/newbot` → pick any name and a username ending in `bot`. BotFather replies with a **token** like `7123456789:AAH...` — copy it.
2. Message your new bot anything (e.g. "hi") so it can reply to you.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in your browser. Find `"chat":{"id":123456789` — that number is your **chat id**.

## Step 3 — Add the secrets (2 min)

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**:
- Name `TG_TOKEN`, value = the token from BotFather
- Name `TG_CHAT`, value = your chat id

## Step 4 — Turn on the schedule and dashboard (2 min)

1. Repo → **Actions** tab → if prompted, click **Enable workflows**.
2. Repo → **Settings → Pages** → under "Build and deployment", Source: **Deploy from a branch**, Branch: **main**, folder: **/docs** → Save. After ~2 minutes your dashboard is live at `https://<your-username>.github.io/crisis-bot/`.

## Step 5 — First run (1 min)

**Actions** tab → **weekly-paper-bot** → **Run workflow** → Run. Watch it go green (~3 min). You'll get a Telegram message with the first status. From now on it runs every Saturday morning automatically — laptop off, phone off, doesn't matter.

## One-year backfill (already included)

The `ledger.json` in this folder ships pre-seeded with a 52-week replay (Jul 2025 → Jul 2026) over the full 334-stock universe using the exact same signal logic: **+25.4%**, 33 trades (best: WBD +163.7%), 5 open positions (WHAUP.BK, BH.BK, KCE.BK, AOT.BK, 601066.SS). Your dashboard starts with a year of equity curve instead of a blank page, and the bot continues from these positions.

To re-run the backfill yourself from scratch (e.g. after changing the universe): run `python paper_bot.py --backfill 52` locally, or temporarily change the workflow run line to that command and trigger it manually once. Warning: it resets the ledger.

## Weekly Telegram report & dashboard analytics

Each run sends a full portfolio report to Telegram: value/total return/weekly return/cash/dividends, this week's buys/sells/dividend payments (stop-losses labelled), every open position (invested → current, P&L in $ and %, entry date), weekly best/worst holding, allocation %, pending orders, and a stats footer (CAGR, Sharpe, max drawdown, win rate). All report logic lives in `reporting.py` — completely separate from trading logic; it only reads the ledger. The dashboard adds allocation pie, cash history, weekly & monthly return charts, trade statistics (win rate, avg gain/loss, largest win/loss, realized & unrealized P&L) and risk metrics (volatility, turnover, dividend yield, drawdowns, all-time high). Metrics that need more history than exists are omitted automatically rather than shown wrong.

## What happens each week

1. Downloads the latest weekly bars for all 74 stocks + FX + 3 indices (regime only).
2. Executes last week's queued orders at this week's open — same no-look-ahead logic as the backtest.
3. Credits dividends (90% after withholding) to cash.
4. Evaluates all v5 signals → queues new buy/sell orders for next week.
5. Records a P/E snapshot (building the P/E history for the future P/E filter).
6. Commits `ledger.json` — the git history is your permanent, tamper-proof trade journal.
7. Sends you the Telegram digest; dashboard updates automatically.

## Strategy configuration (v5, validated 2008–2026)

Dividend sleeve 70% ($70k): crisis ≥30% drawdown, price ≤ 182-wk volume-weighted avg, trend break up, RSI thrust; yield ≥3.5%, ranked by yield, max 5 positions, ≤3 per market, stop −20%.
Growth sleeve 30% ($30k): same entry, max 3 positions, ≤2 per market, stop −15%, paused while home index ≤ −25% from 2-yr peak.
Exit: ≥2 of {price ≥2× VP avg, EMA −6% break, MACD<0, RSI bearish divergence}, or stop.

Backtest (walk-forward): full period 2008–26 = 21.6%/yr, Sharpe 1.34, maxDD −22.5%; conservative expectation 16–18%/yr. Paper trading — not investment advice.

## FAQ

- **Change the universe**: edit `STOCKS` in `paper_bot.py` directly on GitHub (pencil icon), commit.
- **Run more often**: edit the `cron` line in `.github/workflows/bot.yml` (e.g. `0 1 * * 1,6` = Mon+Sat).
- **See why it did something**: every run's full log is in the Actions tab; every ledger change is a git commit.
- **Kill switch**: Actions tab → weekly-paper-bot → "..." menu → Disable workflow.
