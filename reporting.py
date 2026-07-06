"""Portfolio analytics & Telegram report builder — READ-ONLY over ledger data.
No trading logic here: everything is computed from ledger.json contents.
"""
import math

START_CAPITAL = 100_000.0

def _weekly_returns(history):
    """Week-over-week % changes of total equity."""
    eq = [h['equity'] for h in history]
    return [eq[i] / eq[i-1] - 1 for i in range(1, len(eq)) if eq[i-1] > 0]

def analytics(led):
    """All portfolio statistics. Metrics needing more history than available are
    set to None so callers can omit them gracefully."""
    a = {}
    hist = led.get('history', [])
    trades = led.get('trades', [])
    sells = [t for t in trades if t['side'] == 'sell']
    buys = [t for t in trades if t['side'] == 'buy']
    pos = led.get('positions', {})

    eq = hist[-1]['equity'] if hist else START_CAPITAL
    cash = hist[-1]['cash'] if hist else START_CAPITAL
    a['equity'], a['cash'] = eq, cash
    a['invested'] = eq - cash
    a['total_return'] = eq / START_CAPITAL - 1
    a['n_weeks'] = len(hist)

    rets = _weekly_returns(hist)
    a['weekly_return'] = rets[-1] if rets else None

    # CAGR: annualize total return over elapsed weeks (needs >= 26 weeks to be meaningful)
    a['cagr'] = (eq / START_CAPITAL) ** (52 / len(rets)) - 1 if len(rets) >= 26 else None

    # volatility & Sharpe: stdev of weekly returns, annualized by sqrt(52) (needs >= 8 weeks)
    if len(rets) >= 8:
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        a['volatility'] = sd * math.sqrt(52)
        a['sharpe'] = (mu / sd) * math.sqrt(52) if sd > 0 else None
    else:
        a['volatility'] = a['sharpe'] = None

    # drawdowns: running peak of the equity curve
    peak, maxdd, ath = -1e18, 0.0, eq
    for h in hist:
        peak = max(peak, h['equity'])
        maxdd = min(maxdd, h['equity'] / peak - 1)
    ath = peak if hist else eq
    a['ath'] = ath
    a['max_drawdown'] = maxdd if hist else None
    a['current_drawdown'] = eq / ath - 1 if hist else None

    # closed-trade stats
    a['n_closed'] = len(sells)
    wins = [t for t in sells if t.get('pnl_pct', 0) > 0]
    losses = [t for t in sells if t.get('pnl_pct', 0) <= 0]
    a['n_wins'], a['n_losses'] = len(wins), len(losses)
    a['win_rate'] = len(wins) / len(sells) if sells else None
    a['avg_gain'] = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else None
    a['avg_loss'] = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else None
    a['largest_win'] = max((t['pnl_pct'] for t in sells), default=None)
    a['largest_loss'] = min((t['pnl_pct'] for t in sells), default=None)

    # avg holding period (weeks) — uses held_wk recorded on sell (may be absent on old records)
    held = [t['held_wk'] for t in sells if 'held_wk' in t]
    a['avg_holding_wk'] = sum(held) / len(held) if held else None

    # realized profit ($) — uses pnl_usd recorded on sell; omit if records lack it
    pusd = [t['pnl_usd'] for t in sells if 'pnl_usd' in t]
    a['realized_pnl'] = sum(pusd) if pusd else None

    # unrealized profit ($) on open positions
    a['unrealized_pnl'] = sum(
        (p.get('last_px', p['entry_px']) - p['entry_px']) * p['shares'] for p in pos.values()) or 0.0

    # dividends: lifetime = closed-trade divs + open-position divs
    a['total_dividends'] = (sum(t.get('div_usd', 0) for t in sells)
                            + sum(p.get('div_usd', 0) for p in pos.values()))
    # trailing dividend yield: dividends over last 52 weeks / current equity
    if hist:
        cutoff = hist[max(0, len(hist) - 52)]['week']
        recent_div = (sum(t.get('div_usd', 0) for t in sells if t['date'] >= cutoff)
                      + sum(p.get('div_usd', 0) for p in pos.values()))
        a['dividend_yield'] = recent_div / eq if eq > 0 else None
    else:
        a['dividend_yield'] = None

    # turnover: annualized bought-notional / average equity — needs cost_usd on buys
    costs = [t['cost_usd'] for t in buys if 'cost_usd' in t]
    if costs and len(rets) >= 8:
        avg_eq = sum(h['equity'] for h in hist) / len(hist)
        a['turnover'] = (sum(costs) / avg_eq) * (52 / len(rets))
    else:
        a['turnover'] = None
    return a

def _pct(x, signed=True):
    return ('+' if signed and x >= 0 else '') + f'{x*100:.1f}%'

def _usd(x):
    return f'${x:,.0f}'

def build_report(led, week, log_lines=None):
    """Assemble the weekly Telegram report (HTML parse mode, phone-friendly width)."""
    a = analytics(led)
    pos = led.get('positions', {})
    run = led.get('last_run', {})
    L = []

    # --- Portfolio summary ---
    L.append(f'📅 <b>Crisis Bot | Week {week}</b>')
    L.append('')
    L.append('💼 <b>Portfolio</b>')
    L.append(f'Value: {_usd(a["equity"])} ({_pct(a["total_return"])})')
    if a['weekly_return'] is not None:
        L.append(f'Week: {_pct(a["weekly_return"])}')
    L.append(f'Cash: {_usd(a["cash"])}')
    L.append(f'Positions: {len(pos)}')
    divs_wk = sum(run.get('divs', {}).values())
    L.append(f'Dividends this week: ${divs_wk:,.2f}')

    # --- Weekly activity ---
    wk_trades = [t for t in led.get('trades', []) if t['date'] == week]
    b = [t for t in wk_trades if t['side'] == 'buy']
    s = [t for t in wk_trades if t['side'] == 'sell']
    L.append('')
    L.append('📈 <b>This week</b>')
    L.append(f'✅ {len(b)} Buy{"s" if len(b)!=1 else ""}')
    L.append(f'❌ {len(s)} Sell{"s" if len(s)!=1 else ""}')
    L.append(f'💰 {len(run.get("divs", {}))} Dividend payment{"s" if len(run.get("divs", {}))!=1 else ""}')
    for t in b:
        L.append(f'BUY {t["symbol"]} @ {t["px_usd"]:,.2f}')
    for t in s:
        tag = ' (stop)' if t.get('stop') else ''
        L.append(f'SELL {t["symbol"]} @ {t["px_usd"]:,.2f} ({_pct(t["pnl_pct"])}){tag}')
    for sym, dv in run.get('divs', {}).items():
        L.append(f'DIV {sym} +${dv:,.2f}')
    exits_queued = [o for o in led.get('pending', []) if o['side'] == 'sell']
    if exits_queued:
        L.append('⚠️ Exit signals: ' + ', '.join(o['symbol'] for o in exits_queued))

    # --- Position performance ---
    if pos:
        L.append('')
        L.append('📊 <b>Positions</b>')
        for sym, p in sorted(pos.items(), key=lambda kv: -kv[1].get('mv', 0)):
            invested = p['shares'] * p['entry_px']
            cur = p.get('mv', invested)
            pnl_usd = cur - invested
            pnl_pct = cur / invested - 1 if invested else 0
            L.append(f'<b>{sym}</b>')
            L.append(f'Invested: {_usd(invested)} → {_usd(cur)}')
            L.append(f'Profit: {"+" if pnl_usd>=0 else "-"}{_usd(abs(pnl_usd))} ({_pct(pnl_pct)})')
            if p.get('div_usd', 0) > 0:
                L.append(f'Dividends: {_usd(p["div_usd"])}')
            L.append(f'Entry: {p["entry_date"]}')

        # --- Weekly leaders: needs prev_px (previous week close) on positions ---
        moves = [(sym, p['last_px'] / p['prev_px'] - 1) for sym, p in pos.items()
                 if p.get('prev_px') and p.get('last_px')]
        if moves:
            moves.sort(key=lambda kv: -kv[1])
            L.append('')
            L.append(f'🏆 Best: {moves[0][0]} {_pct(moves[0][1])}')
            L.append(f'📉 Worst: {moves[-1][0]} {_pct(moves[-1][1])}')

        # --- Allocation ---
        L.append('')
        L.append('<b>Allocation</b>')
        rows = sorted([(sym, p.get('mv', 0)) for sym, p in pos.items()], key=lambda kv: -kv[1])
        rows.append(('Cash', a['cash']))
        for sym, mv in rows:
            L.append(f'{sym:<12} {mv / a["equity"] * 100:.0f}%')

    # --- Pending orders ---
    L.append('')
    pend = led.get('pending', [])
    if pend:
        L.append('⏳ <b>Pending (next weekly open)</b>')
        for o in pend:
            L.append(f'{o["side"].upper()} {o["symbol"]} ({o.get("sleeve","")})')
    else:
        L.append('No pending orders.')

    # --- Key stats footer (omit metrics with insufficient history) ---
    stats = []
    if a['cagr'] is not None: stats.append(f'CAGR {_pct(a["cagr"], False)}')
    if a['sharpe'] is not None: stats.append(f'Sharpe {a["sharpe"]:.2f}')
    if a['max_drawdown'] is not None: stats.append(f'MaxDD {_pct(a["max_drawdown"])}')
    if a['win_rate'] is not None: stats.append(f'Win {a["win_rate"]*100:.0f}%')
    if stats:
        L.append('')
        L.append('📐 ' + ' | '.join(stats))
    return '\n'.join(L)
