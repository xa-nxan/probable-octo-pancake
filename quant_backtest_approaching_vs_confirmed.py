"""
Quantitative Analysis: Approaching vs At Zone vs Confirmed Retest Backtest
Evaluating the 11 Synthetics over historical MT5 data:
- Baseline: Confirmed Rejection Close (current scanner rule)
- Strategy A: Limit Order @ Shelf on 'APPROACHING' state
- Strategy B: Zone Touch Market Entry on 'AT RETEST ZONE'
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from datetime import datetime

TARGET_UNIVERSE = [
    'FX Vol 20', 'FX Vol 40', 'FX Vol 60',
    'SFX Vol 20', 'SFX Vol 40', 'SFX Vol 60',
    'FlipX 1', 'FlipX 2', 'FlipX 3', 'FlipX 4', 'FlipX 5'
]

def run_quant_comparison():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    print("=" * 105)
    print("QUANTITATIVE COMPARISON: 'APPROACHING' LIMIT vs 'ZONE TOUCH' vs 'CONFIRMED CLOSE'")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Standard: /quant-analyst")
    print("=" * 105)

    stats = {
        'confirmed': {'trades': 0, 'wins': 0, 'be': 0, 'losses': 0, 'net_r': 0.0, 'gross_profit_r': 0.0, 'gross_loss_r': 0.0},
        'limit_at_shelf': {'trades': 0, 'wins': 0, 'be': 0, 'losses': 0, 'net_r': 0.0, 'gross_profit_r': 0.0, 'gross_loss_r': 0.0},
        'zone_touch': {'trades': 0, 'wins': 0, 'be': 0, 'losses': 0, 'net_r': 0.0, 'gross_profit_r': 0.0, 'gross_loss_r': 0.0},
        'transition': {'approaching_events': 0, 'reached_shelf': 0, 'reversed_early': 0, 'blew_through': 0}
    }

    for sym in TARGET_UNIVERSE:
        info = mt5.symbol_info(sym)
        if not info:
            continue

        digits = info.digits
        point = info.point
        spread = round(info.spread * point, digits)

        rates_m15 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 8000)
        rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 3000)

        if rates_m15 is None or rates_h1 is None or len(rates_m15) < 300:
            continue

        df_m15 = pd.DataFrame(rates_m15)
        df_h1 = pd.DataFrame(rates_h1)

        t_m15 = df_m15['time'].values
        o_m15 = df_m15['open'].values
        h_m15 = df_m15['high'].values
        l_m15 = df_m15['low'].values
        c_m15 = df_m15['close'].values

        t_h1 = df_h1['time'].values
        c_h1 = df_h1['close'].values
        ema20_h1_full = pd.Series(c_h1).ewm(span=20, adjust=False).mean().values

        # M15 ATR(14)
        tr = np.maximum(h_m15[1:] - l_m15[1:], np.maximum(np.abs(h_m15[1:] - c_m15[:-1]), np.abs(l_m15[1:] - c_m15[:-1])))
        atr_arr = np.zeros(len(c_m15))
        for k in range(14, len(c_m15)):
            atr_arr[k] = np.mean(tr[k-14:k])

        ema20_m15 = pd.Series(c_m15).ewm(span=20, adjust=False).mean().values

        # Find 5-bar fractal swings
        high_swings = []
        low_swings = []
        for i in range(2, len(c_m15) - 2):
            if h_m15[i] > h_m15[i-1] and h_m15[i] > h_m15[i-2] and h_m15[i] > h_m15[i+1] and h_m15[i] > h_m15[i+2]:
                high_swings.append({'idx': i, 'price': round(float(h_m15[i]), digits)})
            if l_m15[i] < l_m15[i-1] and l_m15[i] < l_m15[i-2] and l_m15[i] < l_m15[i+1] and l_m15[i] < l_m15[i+2]:
                low_swings.append({'idx': i, 'price': round(float(l_m15[i]), digits)})

        # Fast lookup
        h1_dict = {t_h1[k]: (c_h1[k], ema20_h1_full[k]) for k in range(len(t_h1))}

        # Scan for broken shelves and evaluate execution variants
        active_shelves = [] # list of {type, shelf_price, break_idx, broken_at, sl_price, target_price}
        
        # Track simulated positions
        # Simulate bar by bar from bar 100 to len-100
        for i in range(100, len(c_m15) - 50):
            curr_t = t_m15[i]
            curr_c = c_m15[i]
            curr_h = h_m15[i]
            curr_l = l_m15[i]
            curr_o = o_m15[i]
            curr_atr = max(atr_arr[i], spread * 2.0)

            # Find matching H1 trend
            h1_bar_time = curr_t - (curr_t % 3600)
            h1_info = h1_dict.get(h1_bar_time)
            if not h1_info:
                continue
            h1_c, h1_ema = h1_info
            h1_bull = h1_c > h1_ema
            h1_bear = h1_c < h1_ema

            m15_bull = curr_c > ema20_m15[i]
            m15_bear = curr_c < ema20_m15[i]

            # 1. Detect new breakout
            # Look at high swings broken upward for Long
            if h1_bull and m15_bull:
                recent_highs = [s for s in high_swings if s['idx'] < i and s['idx'] > i - 60]
                for s in recent_highs[-2:]:
                    sh_p = s['price']
                    # Candle broke above shelf
                    if curr_c > sh_p + 0.10 * curr_atr and c_m15[i-1] <= sh_p:
                        # Found breakout
                        sl_p = round(curr_l - 0.15 * curr_atr, digits)
                        active_shelves.append({
                            'type': 'BUY',
                            'shelf': sh_p,
                            'break_i': i,
                            'sl': sl_p,
                            'obs1': round(curr_h, digits),
                            'state': 'APPROACHING_INIT',
                            'evaluated_limit': False,
                            'evaluated_zone': False,
                            'evaluated_confirmed': False
                        })

            # Look at low swings broken downward for Short
            if h1_bear and m15_bear:
                recent_lows = [s for s in low_swings if s['idx'] < i and s['idx'] > i - 60]
                for s in recent_lows[-2:]:
                    sh_p = s['price']
                    if curr_c < sh_p - 0.10 * curr_atr and c_m15[i-1] >= sh_p:
                        sl_p = round(curr_h + spread + 0.15 * curr_atr, digits)
                        active_shelves.append({
                            'type': 'SELL',
                            'shelf': sh_p,
                            'break_i': i,
                            'sl': sl_p,
                            'obs1': round(curr_l, digits),
                            'state': 'APPROACHING_INIT',
                            'evaluated_limit': False,
                            'evaluated_zone': False,
                            'evaluated_confirmed': False
                        })

            # 2. Process active shelves
            for sh in list(active_shelves):
                if i - sh['break_i'] > 40: # Expired after 40 bars (10 hours)
                    active_shelves.remove(sh)
                    continue

                sh_p = sh['shelf']
                is_buy = sh['type'] == 'BUY'
                
                # Check Invalidation: if price closes too deep beyond shelf
                if is_buy and curr_c < sh_p - 0.35 * curr_atr:
                    active_shelves.remove(sh)
                    continue
                if not is_buy and curr_c > sh_p + 0.35 * curr_atr:
                    active_shelves.remove(sh)
                    continue

                # Check State: Is price APPROACHING the shelf?
                # For Buy: price is above shelf and descending towards it
                if is_buy:
                    dist_to_shelf = curr_l - sh_p
                    in_approaching_zone = (dist_to_shelf <= 1.25 * curr_atr) and (dist_to_shelf >= 0.0)
                    at_zone = (curr_l <= sh_p + 0.35 * curr_atr) and (curr_h >= sh_p - 0.20 * curr_atr)
                    reached_shelf = curr_l <= sh_p
                else:
                    dist_to_shelf = sh_p - curr_h
                    in_approaching_zone = (dist_to_shelf <= 1.25 * curr_atr) and (dist_to_shelf >= 0.0)
                    at_zone = (curr_h >= sh_p - 0.35 * curr_atr) and (curr_l <= sh_p + 0.20 * curr_atr)
                    reached_shelf = curr_h >= sh_p

                if in_approaching_zone and sh['state'] == 'APPROACHING_INIT':
                    stats['transition']['approaching_events'] += 1
                    sh['state'] = 'IN_APPROACH'

                # --- STRATEGY A: LIMIT ORDER PLACED AT SHELF WHEN APPROACHING ---
                if not sh['evaluated_limit'] and reached_shelf and sh['state'] == 'IN_APPROACH':
                    sh['evaluated_limit'] = True
                    stats['transition']['reached_shelf'] += 1
                    
                    entry_p = sh_p
                    sl_p = sh['sl']
                    risk = abs(entry_p - sl_p)
                    if risk > spread * 1.5:
                        tp_p = round(entry_p + 3.3 * risk if is_buy else entry_p - 3.3 * risk, digits)
                        # Evaluate outcome from bar i forward
                        res = eval_trade_outcome(is_buy, entry_p, sl_p, tp_p, h_m15, l_m15, c_m15, i, 48)
                        record_stats(stats['limit_at_shelf'], res)

                # --- STRATEGY B: ZONE TOUCH MARKET ENTRY ---
                if not sh['evaluated_zone'] and at_zone:
                    sh['evaluated_zone'] = True
                    entry_p = round(curr_c + spread if is_buy else curr_c, digits)
                    sl_p = sh['sl']
                    risk = abs(entry_p - sl_p)
                    if risk > spread * 1.5:
                        tp_p = round(entry_p + 3.0 * risk if is_buy else entry_p - 3.0 * risk, digits)
                        res = eval_trade_outcome(is_buy, entry_p, sl_p, tp_p, h_m15, l_m15, c_m15, i, 48)
                        record_stats(stats['zone_touch'], res)

                # --- BASELINE: CONFIRMED REJECTION CANDLE CLOSE ---
                if not sh['evaluated_confirmed'] and at_zone:
                    prev_o = o_m15[i-1]
                    prev_c = c_m15[i-1]
                    prev_h = h_m15[i-1]
                    prev_l = l_m15[i-1]
                    prev_rng = max(1e-4, prev_h - prev_l)
                    
                    if is_buy:
                        lower_wick = (min(prev_o, prev_c) - prev_l) / prev_rng
                        confirmed = (lower_wick >= 0.20) and (prev_c >= sh_p - 0.10 * curr_atr) and (prev_l <= sh_p + 0.35 * curr_atr)
                    else:
                        upper_wick = (prev_h - max(prev_o, prev_c)) / prev_rng
                        confirmed = (upper_wick >= 0.20) and (prev_c <= sh_p + 0.10 * curr_atr) and (prev_h >= sh_p - 0.35 * curr_atr)

                    if confirmed:
                        sh['evaluated_confirmed'] = True
                        entry_p = round(curr_c + spread if is_buy else curr_c, digits)
                        sl_p = round(prev_l - 0.15 * curr_atr if is_buy else prev_h + spread + 0.15 * curr_atr, digits)
                        risk = abs(entry_p - sl_p)
                        if risk > spread * 1.5:
                            tp_p = round(entry_p + 3.0 * risk if is_buy else entry_p - 3.0 * risk, digits)
                            res = eval_trade_outcome(is_buy, entry_p, sl_p, tp_p, h_m15, l_m15, c_m15, i, 48)
                            record_stats(stats['confirmed'], res)

    print_quant_results(stats)
    mt5.shutdown()

def eval_trade_outcome(is_buy, entry, sl, tp, h_arr, l_arr, c_arr, start_idx, max_bars):
    """Event driven trade evaluator with Q93 BE lock at +1.3R."""
    risk = abs(entry - sl)
    be_price = entry + 0.10 * risk if is_buy else entry - 0.10 * risk
    be_active = False
    cur_sl = sl

    end_idx = min(len(h_arr), start_idx + max_bars)
    for k in range(start_idx, end_idx):
        kh = h_arr[k]
        kl = l_arr[k]
        kc = c_arr[k]

        if is_buy:
            # Conservative: worst-case, check SL first
            if kl <= cur_sl:
                return 'BE' if be_active else 'LOSS'
            if kh >= tp:
                return 'WIN'
            # Check BE lock condition at bar close
            if not be_active and kc >= entry + 1.3 * risk:
                be_active = True
                cur_sl = be_price
        else:
            if kh >= cur_sl:
                return 'BE' if be_active else 'LOSS'
            if kl <= tp:
                return 'WIN'
            if not be_active and kc <= entry - 1.3 * risk:
                be_active = True
                cur_sl = be_price

    return 'BE' if be_active else 'TIMEOUT'

def record_stats(st, outcome):
    st['trades'] += 1
    if outcome == 'WIN':
        st['wins'] += 1
        st['net_r'] += 3.0
        st['gross_profit_r'] += 3.0
    elif outcome == 'BE':
        st['be'] += 1
        st['net_r'] += 0.1
        st['gross_profit_r'] += 0.1
    elif outcome == 'LOSS':
        st['losses'] += 1
        st['net_r'] -= 1.0
        st['gross_loss_r'] += 1.0

def print_quant_results(stats):
    print("\n" + "=" * 105)
    print("EMPIRICAL BACKTEST COMPARISON ACROSS 11 SYNTHETICS (8,000 M15 BARS PER SYMBOL)")
    print("=" * 105)

    headers = f"{'EXECUTION MODEL':<28} | {'TRADES':<7} | {'CLEAN WINS':<11} | {'BE (Q93)':<9} | {'LOSS':<7} | {'PROT WR %':<10} | {'NET R':<10} | {'PF':<6}"
    print(headers)
    print("-" * 105)

    for name, key in [
        ('1. Confirmed Rejection Close', 'confirmed'),
        ('2. Limit Order @ Shelf (Approach)', 'limit_at_shelf'),
        ('3. Zone Touch (Market Entry)', 'zone_touch')
    ]:
        d = stats[key]
        tot = d['trades']
        if tot == 0:
            continue
        wins = d['wins']
        be = d['be']
        loss = d['losses']
        prot_wr = ((wins + be) / tot) * 100
        net_r = d['net_r']
        pf = (d['gross_profit_r'] / max(1e-4, d['gross_loss_r']))
        print(f"{name:<28} | {tot:<7} | {wins} ({wins/tot*100:.1f}%) | {be:<9} | {loss:<7} | {prot_wr:.1f}%     | {net_r:+.1f} R   | {pf:.2f}")

    print("=" * 105)
    tr = stats['transition']
    tot_app = max(1, tr['approaching_events'])
    reached = tr['reached_shelf']
    print(f"STATE TRANSITION METRICS:")
    print(f"- Total 'APPROACHING' Events Recorded:  {tot_app}")
    print(f"- Probability Reached Retest Shelf:    {reached} / {tot_app} ({reached/tot_app*100:.1f}%)")
    print(f"- Probability Reversed Prematurely:    {tot_app - reached} / {tot_app} ({(tot_app-reached)/tot_app*100:.1f}%)")
    print("=" * 105)

if __name__ == '__main__':
    run_quant_comparison()
