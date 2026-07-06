"""Weekly paper-trading bot — crisis-dividend strategy v5.
Runs on GitHub Actions (or any machine). Stocks only; indices used solely as regime gauge.
Signals on latest completed weekly close -> orders queued -> executed at NEXT week's open
(identical to the validated backtest; no look-ahead).

Usage:
  python paper_bot.py                 # normal weekly run
  python paper_bot.py --backfill 52   # reset ledger and replay the last 52 weeks
"""
import json, os, sys
import numpy as np
import pandas as pd
import yfinance as yf
from strategy import P5, signals, to_weekly

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, 'ledger.json')

STOCKS = [
    '000001.SZ','0001.HK','0002.HK','0003.HK','0005.HK','000568.SZ','0006.HK','000651.SZ','000858.SZ','0012.HK',
    '0016.HK','002352.SZ','002475.SZ','002594.SZ','0027.HK','002714.SZ','003816.SZ','0066.HK','0101.HK','0175.HK',
    '0241.HK','0267.HK','0285.HK','0288.HK','0291.HK','0300.HK','0316.HK','0322.HK','0386.HK','0388.HK',
    '0669.HK','0688.HK','0700.HK','0762.HK','0823.HK','0836.HK','0857.HK','0868.HK','0881.HK','0883.HK',
    '0939.HK','0941.HK','0960.HK','0968.HK','0981.HK','0992.HK','1024.HK','1038.HK','1044.HK','1088.HK',
    '1093.HK','1099.HK','1109.HK','1113.HK','1177.HK','1209.HK','1211.HK','1299.HK','1378.HK','1398.HK',
    '1773.HK','1810.HK','1833.HK','1876.HK','1928.HK','1929.HK','1997.HK','2015.HK','2020.HK','2057.HK',
    '2269.HK','2313.HK','2318.HK','2319.HK','2331.HK','2359.HK','2382.HK','2388.HK','2577.HK','2618.HK',
    '2628.HK','2688.HK','2899.HK','300059.SZ','300308.SZ','300750.SZ','300760.SZ','300999.SZ','3690.HK','3692.HK',
    '3968.HK','3988.HK','600000.SS','600028.SS','600030.SS','600036.SS','600066.SS','600276.SS','600309.SS','600406.SS',
    '600519.SS','600690.SS','600809.SS','600887.SS','600900.SS','601012.SS','601066.SS','601088.SS','601138.SS','601166.SS',
    '601225.SS','601288.SS','601318.SS','601319.SS','601328.SS','601398.SS','601601.SS','601633.SS','601658.SS','601668.SS',
    '601816.SS','601818.SS','601857.SS','601888.SS','601899.SS','601939.SS','601988.SS','601998.SS','603288.SS','6169.HK',
    '6618.HK','6690.HK','6862.HK','688041.SS','688256.SS','688795.SS','9618.HK','9633.HK','9868.HK','9888.HK',
    '9961.HK','9988.HK','9992.HK','9999.HK','AAPL','ABI.BR','ABNB','AD.AS','ADBE','ADI',
    'ADP','ADS.DE','ADSK','ADYEN.AS','AEP','AI.PA','AIR.PA','ALNY','ALV.DE','AMAT',
    'AMATA.BK','AMD','AMGN','AMZN','AOT.BK','APP','ARGX.BR','ARM','ASML','ASML.AS',
    'AURA.BK','AVGO','AXON','BABA','BAS.DE','BAYN.DE','BBVA.MC','BH.BK','BIDU','BKNG',
    'BKR','BMW.DE','BN.PA','BNP.PA','BRK-A','CCEP','CDNS','CEG','CHAYO.BK','CHTR',
    'CMCSA','COM7.BK','COST','CPALL.BK','CPRT','CRC.BK','CRWD','CS.PA','CSCO','CSGP',
    'CSX','CTAS','CTSH','DASH','DB1.DE','DBK.DE','DDOG','DELTA.BK','DG.PA','DHL.DE',
    'DIDIY','DOHOME.BK','DTE.DE','DUOL','DXCM','EA','EL.PA','ELF','ENEL.MI','ENI.MI',
    'ENR.DE','EXC','FANG','FAST','FER','FPT.VN','FTNT','GEHC','GILD','GOOG',
    'GOOGL','HMPRO.BK','HON','IBE.MC','IDXX','IFX.DE','INGA.AS','INSM','INTC','INTU',
    'ISP.MI','ISRG','ITX.MC','JMT.BK','KCE.BK','KDP','KHC','KISS.BK','KLAC','KLINIQ.BK',
    'KTC.BK','LH.BK','LIN','LMND','LRCX','MAR','MBG.DE','MC.PA','MCHP','MDLZ',
    'MELI','META','MNST','MPWR','MRVL','MSFT','MSTR','MTC.BK','MU','MUV2.DE',
    'MWG.VN','NDA-FI.HE','NFLX','NSL.BK','NVDA','NXPI','ODFL','ONON','OR.PA','ORI.BK',
    'ORLY','PANW','PAYX','PCAR','PDD','PEP','PLTR','PRX.AS','PYPL','QCOM',
    'QH.BK','RACE.MI','REGN','RHM.DE','RMS.PA','ROP','ROST','SAF.PA','SAN.MC','SAN.PA',
    'SAP.DE','SBUX','SCB.BK','SGO.PA','SHOP','SIE.DE','SISB.BK','SNDK','SNPS','STX',
    'SU.PA','TMUS','TRI','TRUE.BK','TSLA','TSM','TTE.PA','TTWO','TXN','UCG.MI',
    'UNH','VIC.VN','VOW.DE','VRSK','VRTX','WBD','WDAY','WDC','WHAUP.BK','WKL.AS',
    'WMT','WPH.BK','XEL','ZS',
]
EU_SUFFIXES = ('.PA','.DE','.AS','.MI','.MC','.BR','.HE','.LS','.IE')
FXS = ['THB=X','HKD=X','CNY=X','EURUSD=X','VND=X']
IDX = ['^IXIC','^HSI','^STOXX50E']   # regime gauge only, never traded
COST, WH = 0.0020, 0.90

DIV = dict(max_pos=5, min_yield=0.035, stop=0.20, mcap=3)
GRO = dict(max_pos=3, stop=0.15, idx_block=0.25, mcap=2)

def mkt(s):
    for suf in ('.HK','.SS','.SZ'):
        if s.endswith(suf): return 'HKCN'
    if s.endswith(EU_SUFFIXES): return 'EU'
    for suf in ('.BK','.VN'):
        if s.endswith(suf): return suf
    return 'US'

def fetch():
    data = {}
    for s in STOCKS + FXS + IDX:
        try:
            df = yf.Ticker(s).history(period='10y', auto_adjust=False, actions=True)
            if df is None or len(df) < 60: continue
            df = df.rename(columns=str.lower)[['open','high','low','close','volume','dividends']]
            df = df.rename(columns={'dividends': 'dividend'})
            df.index = df.index.tz_localize(None)
            if s.endswith('=X'):  # scrub FX outliers
                med = df['close'].rolling(21, center=True, min_periods=5).median()
                df = df[(df['close']/med).sub(1).abs() <= 0.5]
            data[s] = to_weekly(df)
        except Exception as e:
            print('fetch fail', s, e)
    return data

def usd_mult(s, fx, d):
    if s.endswith(EU_SUFFIXES):
        ser = fx['EURUSD=X']['close']
        return float(ser[ser.index <= d].iloc[-1])
    m = {'.BK':'THB=X','.HK':'HKD=X','.SS':'CNY=X','.SZ':'CNY=X','.VN':'VND=X'}
    for suf, f in m.items():
        if s.endswith(suf):
            ser = fx[f]['close']
            return 1.0 / float(ser[ser.index <= d].iloc[-1])
    return 1.0

def pe_snapshot(symbols):
    out = {}
    for s in symbols:
        try:
            out[s] = yf.Ticker(s).info.get('trailingPE')
        except Exception:
            out[s] = None
    return out

def telegram(msg):
    tok, chat = os.environ.get('TG_TOKEN'), os.environ.get('TG_CHAT')
    if not tok or not chat:
        print('TG not configured; message:\n' + msg); return
    import requests
    requests.post(f'https://api.telegram.org/bot{tok}/sendMessage',
                  json={'chat_id': chat, 'text': msg, 'parse_mode': 'HTML'}, timeout=20)

def precompute(data):
    """Signals are purely backward-looking, so computing once on full history is
    identical to recomputing on truncated history each week."""
    SIG = {s: signals(data[s]) for s in STOCKS if s in data and len(data[s]) >= 120}
    IDXDD = {}
    for ix in IDX:
        if ix in data:
            c = data[ix]['close']
            IDXDD[ix] = c / c.rolling(104, min_periods=8).max() - 1
    return SIG, IDXDD

def step(data, fx, SIG, IDXDD, led, latest):
    """One weekly cycle evaluated at weekly bar `latest`. Returns (week, log)."""
    D = data
    idx_dd = {}
    for ix, ser in IDXDD.items():
        sub = ser[ser.index <= latest]
        if len(sub): idx_dd[ix] = float(sub.iloc[-1])
    home_ix = lambda s: '^HSI' if mkt(s) == 'HKCN' else ('^STOXX50E' if mkt(s) == 'EU' else '^IXIC')
    week = str(latest.date())
    if led.get('last_week') == week:
        return None, []
    log = []

    # 1) execute pending orders at this week's open
    for o in led.get('pending', []):
        s = o['symbol']
        if s not in D or latest not in D[s].index: continue
        px = float(D[s].at[latest, 'open']) * usd_mult(s, fx, latest)
        if px <= 0 or np.isnan(px): continue
        if o['side'] == 'sell' and s in led['positions']:
            pos = led['positions'].pop(s)
            proceeds = pos['shares'] * px * (1 - COST)
            led['sleeves'][pos['sleeve']]['cash'] += proceeds
            pnl = px / pos['entry_px'] - 1
            # reporting-only fields: pnl_usd = proceeds minus original cost basis,
            # held_wk = holding period in weeks, stop = whether a stop-loss queued this exit
            cost_basis = pos['shares'] * pos['entry_px']
            held_wk = int((latest - pd.Timestamp(pos['entry_date'])).days / 7)
            led['trades'].append(dict(symbol=s, side='sell', date=week, px_usd=round(px,4),
                                      pnl_pct=round(pnl,4), div_usd=round(pos['div_usd'],2), sleeve=pos['sleeve'],
                                      pnl_usd=round(proceeds - cost_basis, 2), held_wk=held_wk,
                                      stop=bool(o.get('stop'))))
            log.append(f"SELL {s} @ ${px:,.2f} ({pnl:+.1%}, divs ${pos['div_usd']:,.0f})")
        elif o['side'] == 'buy' and s not in led['positions']:
            sl = led['sleeves'][o['sleeve']]
            cfg = DIV if o['sleeve'] == 'div' else GRO
            n_in = sum(1 for p in led['positions'].values() if p['sleeve'] == o['sleeve'])
            n_mkt = sum(1 for q, p in led['positions'].items() if p['sleeve'] == o['sleeve'] and mkt(q) == mkt(s))
            if n_in >= cfg['max_pos'] or n_mkt >= cfg['mcap']: continue
            sleeve_eq = sl['cash'] + sum(p['mv'] for q, p in led['positions'].items() if p['sleeve'] == o['sleeve'])
            alloc = min(sl['cash'], sleeve_eq / cfg['max_pos'])
            if alloc < 500: continue
            sh = alloc * (1 - COST) / px
            sl['cash'] -= alloc
            led['positions'][s] = dict(shares=sh, entry_px=px, entry_date=week, div_usd=0.0,
                                       mv=sh*px, sleeve=o['sleeve'])
            # cost_usd is reporting-only (turnover / invested-capital analytics)
            led['trades'].append(dict(symbol=s, side='buy', date=week, px_usd=round(px,4), sleeve=o['sleeve'],
                                      cost_usd=round(alloc, 2)))
            log.append(f"BUY {s} @ ${px:,.2f} (${alloc:,.0f}, {o['sleeve']})")
    led['pending'] = []

    # 2) dividends + mark to market
    week_divs = {}  # reporting-only: dividends credited this week, per symbol
    for s, pos in led['positions'].items():
        if s not in D: continue
        w = D[s]
        m_usd = usd_mult(s, fx, latest)
        if latest in w.index:
            dv = float(w.at[latest, 'dividend'])
            if dv > 0:
                dv_usd = dv * m_usd * pos['shares'] * WH
                led['sleeves'][pos['sleeve']]['cash'] += dv_usd
                pos['div_usd'] += dv_usd
                week_divs[s] = round(dv_usd, 2)
                log.append(f"DIV {s}: +${dv_usd:,.2f}")
        # prev_px is reporting-only: last week's close, for "weekly leaders" in the report
        pos['prev_px'] = pos.get('last_px')
        sub = w[w.index <= latest]
        if len(sub): pos['last_px'] = float(sub['close'].iloc[-1]) * m_usd
        pos['mv'] = pos['shares'] * pos['last_px']
    led['last_run'] = dict(week=week, divs=week_divs)  # reporting-only metadata

    # 3) new signals -> queue orders for next week
    cands = {'div': [], 'gro': []}
    cooldown = led.setdefault('stopped', {})
    for s, sg in SIG.items():
        if latest not in sg.index: continue
        row = sg.loc[latest]
        if s in led['positions']:
            pos = led['positions'][s]
            cfg = DIV if pos['sleeve'] == 'div' else GRO
            stop = pos.get('last_px', pos['entry_px']) < pos['entry_px'] * (1 - cfg['stop'])
            if bool(row['exit']) or stop:
                # 'stop' flag on the order is reporting-only (labels the exit in the report)
                led['pending'].append(dict(symbol=s, side='sell', sleeve=pos['sleeve'], stop=bool(stop)))
                if stop: cooldown[s] = week
                log.append(f"signal EXIT {s}" + (' (stop)' if stop else ''))
        elif bool(row['entry']):
            if s in cooldown and (pd.Timestamp(week) - pd.Timestamp(cooldown[s])).days < 56:
                continue
            y = float(row['ttm_yield'])
            if DIV['min_yield'] <= y <= 0.20:
                cands['div'].append((s, y))
            elif y < DIV['min_yield'] and idx_dd.get(home_ix(s), 0) > -GRO['idx_block']:
                cands['gro'].append((s, float(D[s].at[latest, 'close'] / row['vwap']) if row['vwap'] and latest in D[s].index else 1))
    for s, y in sorted(cands['div'], key=lambda t: -t[1])[:DIV['max_pos']]:
        led['pending'].append(dict(symbol=s, side='buy', sleeve='div'))
        log.append(f"signal BUY {s} (yield {y:.1%})")
    for s, r in sorted(cands['gro'], key=lambda t: t[1])[:GRO['max_pos']]:
        led['pending'].append(dict(symbol=s, side='buy', sleeve='gro'))
        log.append(f"signal BUY {s} (growth)")

    # 4) equity + history
    mv = sum(p['mv'] for p in led['positions'].values())
    cash = sum(sl['cash'] for sl in led['sleeves'].values())
    led['history'].append(dict(week=week, equity=round(cash+mv,2), cash=round(cash,2), npos=len(led['positions'])))
    led['last_week'] = week
    return week, log

def save(led):
    json.dump(led, open(LEDGER, 'w'), indent=1)
    os.makedirs(os.path.join(HERE, 'docs'), exist_ok=True)
    json.dump(led, open(os.path.join(HERE, 'docs', 'data.json'), 'w'), indent=1)

def fresh_ledger():
    return dict(last_week=None, sleeves=dict(div=dict(cash=70000.0), gro=dict(cash=30000.0)),
                positions={}, pending=[], trades=[], history=[], pe_log=[])

def main():
    data = fetch()
    fx = {k: data[k] for k in FXS if k in data}

    SIG, IDXDD = precompute(data)
    if '--backfill' in sys.argv:
        n = int(sys.argv[sys.argv.index('--backfill') + 1]) if len(sys.argv) > sys.argv.index('--backfill') + 1 else 52
        led = fresh_ledger()
        allw = sorted(set().union(*[set(w.index) for s, w in data.items() if s in STOCKS]))
        weeks = allw[-n:]
        print(f'backfilling {len(weeks)} weeks: {weeks[0].date()} -> {weeks[-1].date()}')
        for wts in weeks:
            wk, log = step(data, fx, SIG, IDXDD, led, wts)
            if wk and log:
                print(wk, '|', '; '.join(log))
        save(led)
        eq = led['history'][-1]['equity']
        telegram(f"<b>Crisis bot — backfill complete</b>\n{len(weeks)} weeks replayed. "
                 f"Equity: ${eq:,.0f} ({eq/100000-1:+.1%}) | {len(led['positions'])} open positions")
        return

    led = json.load(open(LEDGER))
    latest = max(w.index[-1] for s, w in data.items() if s in STOCKS)
    week, log = step(data, fx, SIG, IDXDD, led, latest)
    if week is None:
        print('no new weekly bar; exit'); return
    pe = pe_snapshot(list(led['positions']) + [o['symbol'] for o in led['pending']])
    led.setdefault('pe_log', []).append(dict(week=week, pe={k: v for k, v in pe.items() if v}))
    save(led)

    # weekly portfolio report (all analytics live in reporting.py, read-only over the ledger)
    import reporting
    msg = reporting.build_report(led, week, log)
    telegram(msg)
    print(msg)

if __name__ == '__main__':
    main()
