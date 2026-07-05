"""Crisis-dividend strategy v5 — signal engine (same code validated in backtest)."""
import numpy as np
import pandas as pd

# Final v5 parameters (walk-forward validated 2008-2026)
P5 = dict(
    dd_entry=0.30, peak_win=104,
    vp_mult=1.00, vp_exit_mult=2.0, vp_win=182,
    rsi_hi=70.0, rsi_lo=40.0, rsi_look=52,
    tl_span=30, tl_break_pct=0.06,
    macd_fast=12, macd_slow=26, macd_sig=9,
    exit_confluence=2, skip_entry='macd_pos',
)

def wilder_rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

def macd_line(close, fast=12, slow=26):
    return close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()

def to_weekly(daily):
    w = daily.resample('W-FRI').agg(
        open=('open', 'first'), high=('high', 'max'), low=('low', 'min'),
        close=('close', 'last'), volume=('volume', 'sum'), dividend=('dividend', 'sum'))
    return w.dropna(subset=['close'])

def vw_avg_price(w, win):
    pv = (w['close'] * w['volume']).rolling(win, min_periods=8).sum()
    v = w['volume'].rolling(win, min_periods=8).sum()
    vwap = pv / v.replace(0, np.nan)
    return vwap.fillna(w['close'].rolling(win, min_periods=8).mean())

def signals(w, p=None):
    p = {**P5, **(p or {})}
    c = w['close']
    out = pd.DataFrame(index=w.index)

    peak = c.rolling(p['peak_win'], min_periods=8).max()
    dd = c / peak - 1
    out['dd'] = dd
    out['crisis'] = (dd <= -p['dd_entry']).rolling(52, min_periods=1).max().astype(bool)

    vwap = vw_avg_price(w, p['vp_win'])
    out['vwap'] = vwap
    out['value_zone'] = c <= vwap * p['vp_mult']
    out['overvalued'] = c >= vwap * p['vp_exit_mult']

    ema = c.ewm(span=p['tl_span'], adjust=False).mean()
    out['ema'] = ema
    ema_up = ema > ema.shift(1)
    out['trend_break_up'] = (c > ema) & ema_up.rolling(2, min_periods=1).max().astype(bool)
    out['trend_break_dn'] = c < ema * (1 - p['tl_break_pct'])

    m = macd_line(c, p['macd_fast'], p['macd_slow'])
    out['macd'] = m
    out['macd_pos'] = m > 0
    out['macd_neg'] = m < 0

    rsi = wilder_rsi(c, 14)
    out['rsi'] = rsi
    hi_touch = rsi >= p['rsi_hi']
    out['rsi_thrust'] = hi_touch.rolling(p['rsi_look'], min_periods=1).max().astype(bool)
    out['rsi_pullback_ok'] = rsi >= p['rsi_lo']
    price_at_hi = c.where(hi_touch).ffill()
    out['rsi_bear_div'] = hi_touch & (c < price_at_hi.shift(1) * 0.995) & (price_at_hi.shift(1).notna())

    entry_parts = dict(crisis=out['crisis'], value_zone=out['value_zone'],
                       trend_break_up=out['trend_break_up'], macd_pos=out['macd_pos'],
                       rsi_thrust=out['rsi_thrust'], rsi_pullback_ok=out['rsi_pullback_ok'])
    ent = pd.Series(True, index=w.index)
    for k, v in entry_parts.items():
        if k != p.get('skip_entry'):
            ent &= v
    out['entry'] = ent
    ex_score = (out['overvalued'].astype(int) + out['trend_break_dn'].astype(int)
                + out['macd_neg'].astype(int) + out['rsi_bear_div'].astype(int))
    out['exit'] = ex_score >= int(p['exit_confluence'])
    out['ttm_yield'] = w['dividend'].rolling(52, min_periods=1).sum() / c
    return out
