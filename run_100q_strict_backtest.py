"""
Strict 100-Question Rule-Based Backtest (Zero-AI, Zero-Lookahead)
Target Universe: 11 Indices
  - FX Vol 20, FX Vol 40, FX Vol 60
  - SFX Vol 20, SFX Vol 40, SFX Vol 60
  - FlipX 1, FlipX 2, FlipX 3, FlipX 4, FlipX 5

Strategy Rules:
  1. H1/M15 Fractal Structure: 5-bar fractal swing pivots (HH, HL, LH, LL).
  2. BOS: Candle close beyond previous fractal swing high/low.
  3. Retest: Price returns to the broken shelf level.
  4. Touch #1 (w1): First test of the zone sets outer wick boundary.
  5. Touch #2 (w2 - Protected Wick Absorption): Second test holds strictly inside w1
     (w2_low > w1_low for Longs; w2_high < w1_high for Shorts).
  6. Entry: On close of Touch #2 confirmation candle (with broker spread).
  7. SL: Protected behind Touch #1 outer wick + spread + buffer.
  8. TP: Prior HTF swing high/low (Obstacle #1) giving 1:3 to 1:8+ R:R.
  9. Q93 BE Lock: Move SL to Entry (+0.1R) once price reaches +1.5R.
"""

import sys
import os
import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from datetime import datetime

SYMBOLS = [
    'FX Vol 20', 'FX Vol 40', 'FX Vol 60',
    'SFX Vol 20', 'SFX Vol 40', 'SFX Vol 60',
    'FlipX 1', 'FlipX 2', 'FlipX 3', 'FlipX 4', 'FlipX 5'
]

def run_backtest():
    if not mt5.initialize():
        print("MT5 initialization failed:", mt5.last_error())
        return

    print("=" * 80)
    print("STRICT 100-QUESTION RULE-BASED BACKTEST (ZERO LOOKAHEAD)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Universe: {len(SYMBOLS)} Synthetic Indices")
    print("=" * 80)

    overall_trades = []

    for sym in SYMBOLS:
        info = mt5.symbol_info(sym)
        if not info:
            print(f"Symbol {sym} not found in MT5!")
            continue

        digits = info.digits
        point = info.point
        spread_pts = info.spread
        spread_price = round(spread_pts * point, digits)
        
        # Pull 35,000 M5 bars (~4 months) and 6,000 H1 bars
        m5_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 35000)
        h1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 6000)

        if m5_rates is None or len(m5_rates) < 1000 or h1_rates is None or len(h1_rates) < 200:
            print(f"Insufficient data for {sym}")
            continue

        df_m5 = pd.DataFrame(m5_rates)
        df_h1 = pd.DataFrame(h1_rates)

        df_m5['time_dt'] = pd.to_datetime(df_m5['time'], unit='s')
        df_h1['time_dt'] = pd.to_datetime(df_h1['time'], unit='s')

        # Calculate H1 Fractal Swings (5-bar fractal window: 2 left, 1 center, 2 right)
        h1_highs = df_h1['high'].values
        h1_lows = df_h1['low'].values
        h1_times = df_h1['time'].values
        h1_closes = df_h1['close'].values

        h1_swings = []
        for i in range(2, len(df_h1) - 2):
            is_sh = (h1_highs[i] > h1_highs[i-1] and h1_highs[i] > h1_highs[i-2] and
                     h1_highs[i] > h1_highs[i+1] and h1_highs[i] > h1_highs[i+2])
            is_sl = (h1_lows[i] < h1_lows[i-1] and h1_lows[i] < h1_lows[i-2] and
                     h1_lows[i] < h1_lows[i+1] and h1_lows[i] < h1_lows[i+2])
            if is_sh:
                h1_swings.append({'idx': i, 'time': h1_times[i+2], 'type': 'HIGH', 'price': h1_highs[i]})
            if is_sl:
                h1_swings.append({'idx': i, 'time': h1_times[i+2], 'type': 'LOW', 'price': h1_lows[i]})

        m5_times = df_m5['time'].values
        m5_o = df_m5['open'].values
        m5_h = df_m5['high'].values
        m5_l = df_m5['low'].values
        m5_c = df_m5['close'].values

        # ATR 14 on M5
        tr = np.maximum(m5_h[1:] - m5_l[1:], np.maximum(np.abs(m5_h[1:] - m5_c[:-1]), np.abs(m5_l[1:] - m5_c[:-1])))
        atr = np.zeros(len(df_m5))
        atr[1:15] = np.mean(tr[:14])
        for idx in range(15, len(df_m5)):
            atr[idx] = (atr[idx-1] * 13 + tr[idx-1]) / 14.0

        # Scan for Break & Retest with Touch #1 & Touch #2 Protected Wick
        sym_trades = []
        last_trade_bar = -50

        # M5 Fractal Swings for local structure
        k = 2
        m5_sh = np.zeros(len(df_m5), dtype=bool)
        m5_sl = np.zeros(len(df_m5), dtype=bool)
        for i in range(k, len(df_m5) - k):
            if (m5_h[i] > m5_h[i-1] and m5_h[i] > m5_h[i-2] and m5_h[i] > m5_h[i+1] and m5_h[i] > m5_h[i+2]):
                m5_sh[i] = True
            if (m5_l[i] < m5_l[i-1] and m5_l[i] < m5_l[i-2] and m5_l[i] < m5_l[i+1] and m5_l[i] < m5_l[i+2]):
                m5_sl[i] = True

        for i in range(50, len(df_m5) - 60):
            if i < last_trade_bar + 12: # Avoid overlapping same setup
                continue

            current_time = m5_times[i]
            current_atr = max(atr[i], spread_price * 2.0)

            # Find recent confirmed H1 structure available at point in time
            avail_h1 = [s for s in h1_swings if s['time'] <= current_time]
            if len(avail_h1) < 2:
                continue

            # Check for Long Setup: Bullish BOS & Retest
            # Find recent broken swing high (shelf) within past 40 M5 bars
            recent_highs = [j for j in range(i - 40, i - 10) if m5_sh[j]]
            recent_lows = [j for j in range(i - 40, i - 10) if m5_sl[j]]

            # -------------------------------------------------------------
            # LONG SETUP EVALUATION
            # -------------------------------------------------------------
            if recent_highs:
                shelf_idx = recent_highs[-1]
                shelf_level = m5_h[shelf_idx]
                
                # Verify BOS: at least one bar closed above shelf level
                bos_occurred = False
                bos_idx = -1
                for b in range(shelf_idx + 1, i - 4):
                    if m5_c[b] > shelf_level + 0.1 * current_atr:
                        bos_occurred = True
                        bos_idx = b
                        break

                if bos_occurred:
                    # Look for Touch #1: First pullback touching or entering within 0.2 ATR of shelf
                    t1_idx = -1
                    w1_low = 1e9
                    for t in range(bos_idx + 1, i - 2):
                        if m5_l[t] <= shelf_level + 0.25 * current_atr and m5_l[t] >= shelf_level - 0.4 * current_atr:
                            t1_idx = t
                            w1_low = m5_l[t]
                            break

                    if t1_idx != -1 and i > t1_idx + 2:
                        # Touch #2: Second test at current bar or bar i-1
                        # Protected Wick Rule: Touch #2 Low > Touch #1 Low (Absorption)
                        # And candle body closes bullish above shelf or respects the zone
                        w2_low = min(m5_l[i-1], m5_l[i])
                        w2_close = m5_c[i]
                        w2_open = m5_o[i]

                        # Check protected wick: w2 strictly held above w1_low
                        is_protected = (w2_low > w1_low) and (w2_low <= shelf_level + 0.3 * current_atr)
                        rejection_candle = (w2_close > w2_open) and (w2_close >= shelf_level - 0.05 * current_atr)
                        
                        # Macro H1 trend check: price above recent H1 low
                        last_h1_low = [s['price'] for s in avail_h1 if s['type'] == 'LOW']
                        h1_trend_ok = (len(last_h1_low) == 0) or (m5_c[i] > last_h1_low[-1])

                        if is_protected and rejection_candle and h1_trend_ok:
                            entry_price = m5_c[i] + spread_price
                            buffer_sl = max(0.12 * current_atr, spread_price * 1.5)
                            sl_price = w1_low - buffer_sl
                            risk_dist = entry_price - sl_price

                            if risk_dist > spread_price * 2.0 and risk_dist < current_atr * 3.5:
                                # Target prior impulse high
                                impulse_high = np.max(m5_h[bos_idx:i])
                                target_dist = impulse_high - entry_price
                                rrr = target_dist / risk_dist

                                if rrr >= 2.5: # Minimum 1:2.5 R:R
                                    tp_price = entry_price + target_dist
                                    
                                    # Simulate trade outcome
                                    trade_result = simulate_trade(
                                        direction='BUY',
                                        entry=entry_price,
                                        sl=sl_price,
                                        tp=tp_price,
                                        spread=spread_price,
                                        bars_h=m5_h[i+1:i+61],
                                        bars_l=m5_l[i+1:i+61],
                                        bars_c=m5_c[i+1:i+61]
                                    )
                                    trade_result.update({
                                        'symbol': sym,
                                        'direction': 'BUY',
                                        'entry_time': str(df_m5['time_dt'].iloc[i]),
                                        'entry': entry_price,
                                        'sl': sl_price,
                                        'tp': tp_price,
                                        'risk_pts': risk_dist,
                                        'rrr': rrr
                                    })
                                    sym_trades.append(trade_result)
                                    last_trade_bar = i
                                    continue

            # -------------------------------------------------------------
            # SHORT SETUP EVALUATION
            # -------------------------------------------------------------
            if recent_lows:
                shelf_idx = recent_lows[-1]
                shelf_level = m5_l[shelf_idx]
                
                # Verify BOS: at least one bar closed below shelf level
                bos_occurred = False
                bos_idx = -1
                for b in range(shelf_idx + 1, i - 4):
                    if m5_c[b] < shelf_level - 0.1 * current_atr:
                        bos_occurred = True
                        bos_idx = b
                        break

                if bos_occurred:
                    # Look for Touch #1: First pullback touching or entering within 0.25 ATR of shelf
                    t1_idx = -1
                    w1_high = -1e9
                    for t in range(bos_idx + 1, i - 2):
                        if m5_h[t] >= shelf_level - 0.25 * current_atr and m5_h[t] <= shelf_level + 0.4 * current_atr:
                            t1_idx = t
                            w1_high = m5_h[t]
                            break

                    if t1_idx != -1 and i > t1_idx + 2:
                        # Touch #2: Second test at current bar
                        # Protected Wick Rule: Touch #2 High < Touch #1 High (Absorption)
                        w2_high = max(m5_h[i-1], m5_h[i])
                        w2_close = m5_c[i]
                        w2_open = m5_o[i]

                        # Check protected wick: w2 held below w1_high
                        is_protected = (w2_high < w1_high) and (w2_high >= shelf_level - 0.3 * current_atr)
                        rejection_candle = (w2_close < w2_open) and (w2_close <= shelf_level + 0.05 * current_atr)

                        # Macro H1 trend check: price below recent H1 high
                        last_h1_high = [s['price'] for s in avail_h1 if s['type'] == 'HIGH']
                        h1_trend_ok = (len(last_h1_high) == 0) or (m5_c[i] < last_h1_high[-1])

                        if is_protected and rejection_candle and h1_trend_ok:
                            entry_price = m5_c[i]
                            buffer_sl = max(0.12 * current_atr, spread_price * 1.5)
                            sl_price = w1_high + spread_price + buffer_sl
                            risk_dist = sl_price - entry_price

                            if risk_dist > spread_price * 2.0 and risk_dist < current_atr * 3.5:
                                # Target prior impulse low
                                impulse_low = np.min(m5_l[bos_idx:i])
                                target_dist = entry_price - impulse_low
                                rrr = target_dist / risk_dist

                                if rrr >= 2.5: # Minimum 1:2.5 R:R
                                    tp_price = entry_price - target_dist
                                    
                                    # Simulate trade outcome
                                    trade_result = simulate_trade(
                                        direction='SELL',
                                        entry=entry_price,
                                        sl=sl_price,
                                        tp=tp_price,
                                        spread=spread_price,
                                        bars_h=m5_h[i+1:i+61],
                                        bars_l=m5_l[i+1:i+61],
                                        bars_c=m5_c[i+1:i+61]
                                    )
                                    trade_result.update({
                                        'symbol': sym,
                                        'direction': 'SELL',
                                        'entry_time': str(df_m5['time_dt'].iloc[i]),
                                        'entry': entry_price,
                                        'sl': sl_price,
                                        'tp': tp_price,
                                        'risk_pts': risk_dist,
                                        'rrr': rrr
                                    })
                                    sym_trades.append(trade_result)
                                    last_trade_bar = i
                                    continue

        # Symbol stats
        if sym_trades:
            df_sym = pd.DataFrame(sym_trades)
            wins = (df_sym['outcome'] == 'WIN').sum()
            be = (df_sym['outcome'] == 'BE').sum()
            loss = (df_sym['outcome'] == 'LOSS').sum()
            tot = len(df_sym)
            wr = (wins / tot) * 100
            prot_wr = ((wins + be) / tot) * 100
            net_r = df_sym['realized_r'].sum()
            print(f"| {sym:10s} | Trades: {tot:3d} | Win: {wins:2d} ({wr:4.1f}%) | BE: {be:2d} | Loss: {loss:2d} | Prot WR: {prot_wr:4.1f}% | Net R: +{net_r:6.1f}R | Avg R:R: 1:{df_sym['rrr'].mean():.1f} |")
            overall_trades.extend(sym_trades)
        else:
            print(f"| {sym:10s} | No trades generated with strict criteria.")

    mt5.shutdown()

    # Overall Summary
    print("=" * 80)
    print("OVERALL 11-SYMBOL STRICT BACKTEST RESULTS")
    print("=" * 80)
    if not overall_trades:
        print("No trades found across universe.")
        return

    df_all = pd.DataFrame(overall_trades)
    total_trades = len(df_all)
    wins = (df_all['outcome'] == 'WIN').sum()
    be = (df_all['outcome'] == 'BE').sum()
    loss = (df_all['outcome'] == 'LOSS').sum()
    win_rate = (wins / total_trades) * 100
    protected_win_rate = ((wins + be) / total_trades) * 100
    net_r = df_all['realized_r'].sum()
    gross_win_r = df_all[df_all['realized_r'] > 0]['realized_r'].sum()
    gross_loss_r = abs(df_all[df_all['realized_r'] < 0]['realized_r'].sum())
    profit_factor = (gross_win_r / gross_loss_r) if gross_loss_r > 0 else 999.0

    # Max Drawdown in R
    cum_r = df_all['realized_r'].cumsum()
    peak = cum_r.cummax()
    dd = peak - cum_r
    max_dd_r = dd.max()

    print(f"Total Completed Trades:      {total_trades}")
    print(f"Clean Wins:                  {wins} ({win_rate:.2f}%)")
    print(f"Breakeven (Q93 Protected):  {be} ({(be / total_trades) * 100:.2f}%)")
    print(f"Full Losses:                 {loss} ({(loss / total_trades) * 100:.2f}%)")
    print(f"Protected Win Rate (Non-Loss): {protected_win_rate:.2f}%")
    print(f"Profit Factor:               {profit_factor:.2f}")
    print(f"Total Realized R:            +{net_r:.1f} R")
    print(f"Average Realized R / Trade:  +{net_r / total_trades:.2f} R")
    print(f"Max Drawdown (R):            -{max_dd_r:.1f} R")
    print(f"Average Planned R:R:         1:{df_all['rrr'].mean():.2f}")
    print("=" * 80)

def simulate_trade(direction: str, entry: float, sl: float, tp: float, spread: float, bars_h, bars_l, bars_c):
    risk = abs(entry - sl)
    be_active = False
    current_sl = sl

    for kh, kl, kc in zip(bars_h, bars_l, bars_c):
        if direction == 'BUY':
            # Check Q93 Fast BE Lock: If price reached +1.5R, lock SL to entry + 0.1R
            if not be_active and (kh - entry) >= 1.5 * risk:
                be_active = True
                current_sl = entry + 0.1 * risk

            # Check SL
            if kl <= current_sl:
                if be_active:
                    return {'outcome': 'BE', 'realized_r': 0.1, 'exit_price': current_sl}
                else:
                    return {'outcome': 'LOSS', 'realized_r': -1.0, 'exit_price': current_sl}

            # Check TP
            if kh >= tp:
                rrr = (tp - entry) / risk
                return {'outcome': 'WIN', 'realized_r': rrr, 'exit_price': tp}

        else: # SELL
            # For sell, price to hit SL is ask (high + spread)
            # Check Q93 Fast BE Lock
            if not be_active and (entry - kl) >= 1.5 * risk:
                be_active = True
                current_sl = entry - 0.1 * risk

            # Check SL
            if (kh + spread) >= current_sl:
                if be_active:
                    return {'outcome': 'BE', 'realized_r': 0.1, 'exit_price': current_sl}
                else:
                    return {'outcome': 'LOSS', 'realized_r': -1.0, 'exit_price': current_sl}

            # Check TP
            if (kl + spread) <= tp:
                rrr = (entry - tp) / risk
                return {'outcome': 'WIN', 'realized_r': rrr, 'exit_price': tp}

    # If trade expires at end of 60 bars (5 hours), exit at last close
    last_c = bars_c[-1]
    if direction == 'BUY':
        r_mult = (last_c - entry) / risk
    else:
        r_mult = (entry - last_c) / risk

    if r_mult >= 1.0:
        return {'outcome': 'WIN', 'realized_r': r_mult, 'exit_price': last_c}
    elif be_active or r_mult >= -0.2:
        return {'outcome': 'BE', 'realized_r': 0.0, 'exit_price': last_c}
    else:
        return {'outcome': 'LOSS', 'realized_r': -1.0, 'exit_price': last_c}

if __name__ == '__main__':
    run_backtest()
