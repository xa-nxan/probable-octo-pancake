import pandas as pd
import numpy as np

def detect_trades_on_bars(bars_m5, symbol='FX_Vol_40'):
    """
    Complete Multi-Timeframe Strategy Engine:
    1. Breakout Expansion (1-Candle Post-Breakout) - Enters immediately upon confirmed structural breakout close,
       riding the institutional expansion impulse with tight SL below/above breakout candle wick (1:2.5+ RR).
    2. Pullback Retracement - Enters at peak/trough exhaustion after the impulse,
       with Stop Loss strictly placed above/below the breakout peak/trough wick, and Take Profit targeting the broken structural level (1:5 to 1:8 RR).
    3. Retest Continuation - Enters after pullback retests the broken level and validates absorption with rejection wicks.
    """
    if len(bars_m5) < 50:
        return []

    df = pd.DataFrame(bars_m5).sort_values('time').reset_index(drop=True)
    df['time'] = df['time'].astype(int)
    n = len(df)

    # True Range & ATR calculation for dynamic per-symbol volatility
    df['tr'] = np.maximum(df['high'] - df['low'], 
                          np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                     abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(14).mean().bfill()

    # Symbol-specific calibrations based on MT5 market profiles
    sym_clean = symbol.replace('_', ' ')
    if 'SFX Vol 40' in sym_clean or 'SFX_Vol_40' in symbol:
        spread_pad = 25.0; min_stop = 35.0; max_stop = 700.0; pt_val = 0.01
    elif 'FX Vol 40' in sym_clean or 'FX_Vol_40' in symbol:
        spread_pad = 12.0; min_stop = 25.0; max_stop = 800.0; pt_val = 0.01
    elif 'FX Vol 60' in sym_clean or 'FX_Vol_60' in symbol:
        spread_pad = 6.0; min_stop = 15.0; max_stop = 400.0; pt_val = 0.01
    elif 'FX Vol 20' in sym_clean or 'FX_Vol_20' in symbol:
        spread_pad = 5.0; min_stop = 12.0; max_stop = 350.0; pt_val = 0.01
    elif 'SFX Vol 20' in sym_clean or 'SFX_Vol_20' in symbol:
        spread_pad = 4.0; min_stop = 8.0; max_stop = 150.0; pt_val = 0.01
    elif 'FlipX 2' in sym_clean or 'FlipX_2' in symbol:
        spread_pad = 2.0; min_stop = 5.0; max_stop = 120.0; pt_val = 0.01
    elif 'FlipX 1' in sym_clean or 'FlipX_1' in symbol:
        spread_pad = 1.5; min_stop = 3.5; max_stop = 80.0; pt_val = 0.01
    else:
        spread_pad = 5.0; min_stop = 10.0; max_stop = 400.0; pt_val = 0.01

    # Detect fractal swing points (window = 8 for clean structural pivots)
    window = 8
    swings_high = {} # idx -> high price
    swings_low = {}  # idx -> low price

    for idx in range(window, n - window):
        if df['high'].iloc[idx] == df['high'].iloc[idx-window:idx+window+1].max():
            swings_high[idx] = float(df['high'].iloc[idx])
        if df['low'].iloc[idx] == df['low'].iloc[idx-window:idx+window+1].min():
            swings_low[idx] = float(df['low'].iloc[idx])

    trades = []
    last_trade_idx = -50

    i = 35
    while i < n - 15:
        if i - last_trade_idx < 3:
            i += 1
            continue

        bar = df.iloc[i]
        c = float(bar['close'])
        c_prev = float(df['close'].iloc[i-1])
        o = float(bar['open'])
        h = float(bar['high'])
        l = float(bar['low'])
        atr = float(df['atr'].iloc[i])
        c_range = max(1.0, h - l)

        trade = None

        recent_sh = [(s_idx, p) for s_idx, p in swings_high.items() if s_idx < i - 2 and (i - s_idx) <= 120]
        recent_sl = [(s_idx, p) for s_idx, p in swings_low.items() if s_idx < i - 2 and (i - s_idx) <= 120]

        # -------------------------------------------------------------
        # SETUP 1A: BREAKOUT EXPANSION (LONG - 1 Candle Post-Breakout)
        # -------------------------------------------------------------
        if recent_sh:
            last_sh_idx, res_price = recent_sh[-1]
            if c > res_price and c_prev <= res_price:
                entry = round(c, 2)
                sl = round(l - spread_pad, 2)
                stop_dist = round(entry - sl, 2)
                if min_stop <= stop_dist <= max_stop:
                    tp = round(entry + 2.5 * stop_dist, 2)
                    profit_dist = round(tp - entry, 2)
                    trade = {
                        'type': 'long-position',
                        'setup': 'Breakout Expansion (Long)',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'brokenLevel': res_price,
                        'stopDist': stop_dist,
                        'profitDist': profit_dist
                    }

        # -------------------------------------------------------------
        # SETUP 1B: BREAKDOWN EXPANSION (SHORT - 1 Candle Post-Breakdown)
        # -------------------------------------------------------------
        if not trade and recent_sl:
            last_sl_idx, sup_price = recent_sl[-1]
            if c < sup_price and c_prev >= sup_price:
                entry = round(c, 2)
                sl = round(h + spread_pad, 2)
                stop_dist = round(sl - entry, 2)
                if min_stop <= stop_dist <= max_stop:
                    tp = round(entry - 2.5 * stop_dist, 2)
                    profit_dist = round(entry - tp, 2)
                    trade = {
                        'type': 'short-position',
                        'setup': 'Breakdown Expansion (Short)',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'brokenLevel': sup_price,
                        'stopDist': stop_dist,
                        'profitDist': profit_dist
                    }

        # -------------------------------------------------------------
        # SETUP 2A: PULLBACK TO BROKEN RESISTANCE (SHORT)
        # -------------------------------------------------------------
        if not trade and recent_sh:
            last_sh_idx, res_price = recent_sh[-1]
            bo_bars = [b_idx for b_idx in range(max(last_sh_idx + 1, i - 14), i) 
                       if df['close'].iloc[b_idx] > res_price and df['close'].iloc[b_idx-1] <= res_price]
            if bo_bars:
                bo_idx = bo_bars[-1]
                impulse_bars = df.iloc[bo_idx:i+1]
                peak_high = float(impulse_bars['high'].max())
                peak_idx = bo_idx + impulse_bars['high'].values.argmax()
                impulse_dist = peak_high - res_price
                
                if impulse_dist >= 1.0 * atr and peak_idx <= i <= peak_idx + 2:
                    is_bear_exhaustion = (c < o) or ((h - max(o, c)) >= 0.35 * c_range)
                    if is_bear_exhaustion and c > res_price:
                        entry = round(c, 2)
                        sl = round(peak_high + spread_pad, 2) # Strictly above breakout peak wick
                        tp = round(res_price, 2) # Strictly at broken resistance
                        stop_dist = round(sl - entry, 2)
                        profit_dist = round(entry - tp, 2)
                        
                        if min_stop <= stop_dist <= max_stop and profit_dist >= stop_dist * 1.4:
                            trade = {
                                'type': 'short-position',
                                'setup': 'Pullback to Broken Resistance (Short)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': res_price,
                                'stopDist': stop_dist,
                                'profitDist': profit_dist
                            }

        # -------------------------------------------------------------
        # SETUP 2B: PULLBACK TO BROKEN SUPPORT (LONG)
        # -------------------------------------------------------------
        if not trade and recent_sl:
            last_sl_idx, sup_price = recent_sl[-1]
            bd_bars = [b_idx for b_idx in range(max(last_sl_idx + 1, i - 14), i) 
                       if df['close'].iloc[b_idx] < sup_price and df['close'].iloc[b_idx-1] >= sup_price]
            if bd_bars:
                bd_idx = bd_bars[-1]
                impulse_bars = df.iloc[bd_idx:i+1]
                trough_low = float(impulse_bars['low'].min())
                trough_idx = bd_idx + impulse_bars['low'].values.argmin()
                impulse_dist = sup_price - trough_low
                
                if impulse_dist >= 1.0 * atr and trough_idx <= i <= trough_idx + 2:
                    is_bull_exhaustion = (c > o) or ((min(o, c) - l) >= 0.35 * c_range)
                    if is_bull_exhaustion and c < sup_price:
                        entry = round(c, 2)
                        sl = round(trough_low - spread_pad, 2) # Strictly below breakdown trough wick
                        tp = round(sup_price, 2) # Strictly at broken support
                        stop_dist = round(entry - sl, 2)
                        profit_dist = round(tp - entry, 2)
                        
                        if min_stop <= stop_dist <= max_stop and profit_dist >= stop_dist * 1.4:
                            trade = {
                                'type': 'long-position',
                                'setup': 'Pullback to Broken Support (Long)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': sup_price,
                                'stopDist': stop_dist,
                                'profitDist': profit_dist
                            }

        # -------------------------------------------------------------
        # SETUP 3A: BREAKOUT RETEST CONTINUATION (LONG)
        # -------------------------------------------------------------
        if not trade and recent_sh:
            last_sh_idx, res_price = recent_sh[-1]
            bo_bars = [b_idx for b_idx in range(max(last_sh_idx + 1, i - 20), i - 2) 
                       if df['close'].iloc[b_idx] > res_price and df['close'].iloc[b_idx-1] <= res_price]
            if bo_bars:
                bo_idx = bo_bars[-1]
                between_bars = df.iloc[bo_idx+1:i+1]
                pb_low = float(between_bars['low'].min())
                if abs(pb_low - res_price) <= 0.45 * atr:
                    bull_retest = (c > o) and (c >= res_price)
                    if bull_retest:
                        peak_before = float(df.iloc[bo_idx:i]['high'].max())
                        entry = round(c, 2)
                        sl = round(pb_low - spread_pad, 2)
                        tp = round(max(peak_before, entry + 2.0 * (entry - sl)), 2)
                        stop_dist = round(entry - sl, 2)
                        profit_dist = round(tp - entry, 2)
                        if min_stop <= stop_dist <= max_stop and profit_dist >= stop_dist * 1.4:
                            trade = {
                                'type': 'long-position',
                                'setup': 'Breakout Retest Continuation (Long)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': res_price,
                                'stopDist': stop_dist,
                                'profitDist': profit_dist
                            }

        # -------------------------------------------------------------
        # SETUP 3B: BREAKDOWN RETEST CONTINUATION (SHORT)
        # -------------------------------------------------------------
        if not trade and recent_sl:
            last_sl_idx, sup_price = recent_sl[-1]
            bd_bars = [b_idx for b_idx in range(max(last_sl_idx + 1, i - 20), i - 2) 
                       if df['close'].iloc[b_idx] < sup_price and df['close'].iloc[b_idx-1] >= sup_price]
            if bd_bars:
                bd_idx = bd_bars[-1]
                between_bars = df.iloc[bd_idx+1:i+1]
                pb_high = float(between_bars['high'].max())
                if abs(pb_high - sup_price) <= 0.45 * atr:
                    bear_retest = (c < o) and (c <= sup_price)
                    if bear_retest:
                        trough_before = float(df.iloc[bd_idx:i]['low'].min())
                        entry = round(c, 2)
                        sl = round(pb_high + spread_pad, 2)
                        tp = round(min(trough_before, entry - 2.0 * (sl - entry)), 2)
                        stop_dist = round(sl - entry, 2)
                        profit_dist = round(entry - tp, 2)
                        if min_stop <= stop_dist <= max_stop and profit_dist >= stop_dist * 1.4:
                            trade = {
                                'type': 'short-position',
                                'setup': 'Breakdown Retest Continuation (Short)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': sup_price,
                                'stopDist': stop_dist,
                                'profitDist': profit_dist
                            }

        # Forward execution simulation: up to 100 bars
        if trade:
            tc = trade
            f_bars = df.iloc[i+1:min(n, i+100)]
            hit_tp = False; hit_sl = False
            exit_time = None

            if tc['type'] == 'long-position':
                for _, fb in f_bars.iterrows():
                    if fb['low'] <= tc['sl']: hit_sl = True; exit_time = int(fb['time']); break
                    if fb['high'] >= tc['tp']: hit_tp = True; exit_time = int(fb['time']); break
                pts = tc['profitDist'] if hit_tp else (-tc['stopDist'] if hit_sl else (float(f_bars.iloc[-1]['close']) - tc['entry']))
            else:
                for _, fb in f_bars.iterrows():
                    if fb['high'] >= tc['sl']: hit_sl = True; exit_time = int(fb['time']); break
                    if fb['low'] <= tc['tp']: hit_tp = True; exit_time = int(fb['time']); break
                pts = tc['profitDist'] if hit_tp else (-tc['stopDist'] if hit_sl else (tc['entry'] - float(f_bars.iloc[-1]['close'])))

            pnl_usd = round(pts * pt_val, 2)
            trades.append({
                'id': f"trade_{len(trades)+1}",
                'symbol': symbol,
                'type': tc['type'],
                'setup': tc['setup'],
                'entryTime': int(df['time'].iloc[i]),
                'exitTime': exit_time or int(df['time'].iloc[min(n-1, i+100)]),
                'entry': tc['entry'],
                'sl': tc['sl'],
                'tp': tc['tp'],
                'brokenLevel': tc.get('brokenLevel', tc['entry']),
                'stopDist': tc['stopDist'],
                'profitDist': tc['profitDist'],
                'win': bool(hit_tp),
                'points': round(pts, 2),
                'pnl_usd': pnl_usd,
                'rrr': round(tc['profitDist'] / max(1.0, tc['stopDist']), 2)
            })
            last_trade_idx = i
            i += 2
            continue

        i += 1

    return trades
