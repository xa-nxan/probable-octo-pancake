"""
Quantitative Factor Attribution & Statistical Separation:
Comparing Winners vs Losers across 11 Synthetics over Historical MT5 Data.
Standard: /quant-analyst
"""

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from scipy import stats as sp_stats

TARGET_UNIVERSE = [
    'FX Vol 20', 'FX Vol 40', 'FX Vol 60',
    'SFX Vol 20', 'SFX Vol 40', 'SFX Vol 60',
    'FlipX 1', 'FlipX 2', 'FlipX 3', 'FlipX 4', 'FlipX 5'
]

def run_winner_loser_analysis():
    if not mt5.initialize():
        print("MT5 initialization failed")
        return

    print("=" * 110)
    print("QUANT FACTOR ATTRIBUTION: WHAT DIFFERENTIATES WINNING TRADES FROM LOSERS?")
    print("Statistical Factor Analysis across 11 Synthetics | Standard: /quant-analyst")
    print("=" * 110)

    dataset = []

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
        ema20_h1 = pd.Series(c_h1).ewm(span=20, adjust=False).mean().values
        h1_dict = {t_h1[k]: (c_h1[k], ema20_h1[k]) for k in range(len(t_h1))}

        # M15 ATR(14)
        tr = np.maximum(h_m15[1:] - l_m15[1:], np.maximum(np.abs(h_m15[1:] - c_m15[:-1]), np.abs(l_m15[1:] - c_m15[:-1])))
        atr_arr = np.zeros(len(c_m15))
        for k in range(14, len(c_m15)):
            atr_arr[k] = np.mean(tr[k-14:k])

        ema20_m15 = pd.Series(c_m15).ewm(span=20, adjust=False).mean().values
        ema50_m15 = pd.Series(c_m15).ewm(span=50, adjust=False).mean().values

        # Find 5-bar fractal swings
        high_swings = []
        low_swings = []
        for i in range(2, len(c_m15) - 2):
            if h_m15[i] > h_m15[i-1] and h_m15[i] > h_m15[i-2] and h_m15[i] > h_m15[i+1] and h_m15[i] > h_m15[i+2]:
                high_swings.append({'idx': i, 'price': round(float(h_m15[i]), digits)})
            if l_m15[i] < l_m15[i-1] and l_m15[i] < l_m15[i-2] and l_m15[i] < l_m15[i+1] and l_m15[i] < l_m15[i+2]:
                low_swings.append({'idx': i, 'price': round(float(l_m15[i]), digits)})

        active_shelves = []

        for i in range(100, len(c_m15) - 50):
            curr_t = t_m15[i]
            curr_c = c_m15[i]
            curr_h = h_m15[i]
            curr_l = l_m15[i]
            curr_o = o_m15[i]
            curr_atr = max(atr_arr[i], spread * 2.0)

            h1_bar_time = curr_t - (curr_t % 3600)
            h1_info = h1_dict.get(h1_bar_time)
            if not h1_info:
                continue
            h1_c, h1_ema = h1_info
            h1_bull = h1_c > h1_ema
            h1_bear = h1_c < h1_ema

            m15_bull = curr_c > ema20_m15[i]
            m15_bear = curr_c < ema20_m15[i]

            # Register breakouts
            if h1_bull and m15_bull:
                recent_highs = [s for s in high_swings if s['idx'] < i and s['idx'] > i - 60]
                for s in recent_highs[-2:]:
                    sh_p = s['price']
                    if curr_c > sh_p + 0.10 * curr_atr and c_m15[i-1] <= sh_p:
                        sl_p = round(curr_l - 0.15 * curr_atr, digits)
                        active_shelves.append({
                            'type': 'BUY',
                            'shelf': sh_p,
                            'break_i': i,
                            'sl': sl_p,
                            'obs1': round(curr_h, digits),
                            'evaluated': False
                        })

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
                            'evaluated': False
                        })

            # Evaluate test
            for sh in list(active_shelves):
                if i - sh['break_i'] > 40:
                    active_shelves.remove(sh)
                    continue

                sh_p = sh['shelf']
                is_buy = sh['type'] == 'BUY'

                # Invalidation
                if is_buy and curr_c < sh_p - 0.40 * curr_atr:
                    active_shelves.remove(sh)
                    continue
                if not is_buy and curr_c > sh_p + 0.40 * curr_atr:
                    active_shelves.remove(sh)
                    continue

                # Check if price tests shelf zone
                if is_buy:
                    at_zone = (curr_l <= sh_p + 0.35 * curr_atr) and (curr_h >= sh_p - 0.20 * curr_atr)
                else:
                    at_zone = (curr_h >= sh_p - 0.35 * curr_atr) and (curr_l <= sh_p + 0.20 * curr_atr)

                if at_zone and not sh['evaluated']:
                    sh['evaluated'] = True

                    # Extract quantitative features
                    bars_to_retest = i - sh['break_i']
                    bar_rng = max(1e-4, curr_h - curr_l)
                    
                    if is_buy:
                        wick_ratio = (min(curr_o, curr_c) - curr_l) / bar_rng
                        penetration_atr = (sh_p - curr_l) / curr_atr
                        runway_pts = sh['obs1'] - curr_c
                    else:
                        wick_ratio = (curr_h - max(curr_o, curr_c)) / bar_rng
                        penetration_atr = (curr_h - sh_p) / curr_atr
                        runway_pts = curr_c - sh['obs1']

                    body_ratio = abs(curr_c - curr_o) / bar_rng
                    h1_dist_pct = abs(h1_c - h1_ema) / h1_ema * 100.0
                    m15_ema_slope = (ema20_m15[i] - ema20_m15[i-5]) / (5 * curr_atr)
                    
                    # Risk and target
                    entry_p = sh_p # testing limit execution @ shelf
                    sl_p = sh['sl']
                    risk = abs(entry_p - sl_p)
                    if risk <= spread * 1.5:
                        continue

                    runway_r = runway_pts / risk
                    tp_p = round(entry_p + 3.2 * risk if is_buy else entry_p - 3.2 * risk, digits)

                    # Simulate outcome
                    outcome, max_adverse_r, max_favorable_r = eval_trade_with_mfe_mae(
                        is_buy, entry_p, sl_p, tp_p, h_m15, l_m15, c_m15, i, 48
                    )

                    dataset.append({
                        'symbol': sym,
                        'outcome': outcome, # WIN, BE, LOSS
                        'is_win': 1 if outcome == 'WIN' else 0,
                        'is_loss': 1 if outcome == 'LOSS' else 0,
                        'bars_to_retest': bars_to_retest,
                        'penetration_atr': penetration_atr,
                        'wick_ratio': wick_ratio,
                        'body_ratio': body_ratio,
                        'runway_r': runway_r,
                        'h1_dist_pct': h1_dist_pct,
                        'm15_ema_slope': m15_ema_slope,
                        'max_adverse_r': max_adverse_r,
                        'max_favorable_r': max_favorable_r
                    })

    mt5.shutdown()
    analyze_quant_features(pd.DataFrame(dataset))

def eval_trade_with_mfe_mae(is_buy, entry, sl, tp, h_arr, l_arr, c_arr, start_idx, max_bars):
    risk = abs(entry - sl)
    be_price = entry + 0.10 * risk if is_buy else entry - 0.10 * risk
    be_active = False
    cur_sl = sl

    max_fav = 0.0
    max_adv = 0.0

    end_idx = min(len(h_arr), start_idx + max_bars)
    for k in range(start_idx, end_idx):
        kh = h_arr[k]
        kl = l_arr[k]
        kc = c_arr[k]

        if is_buy:
            adv = max(0.0, (entry - kl) / risk)
            fav = max(0.0, (kh - entry) / risk)
            max_adv = max(max_adv, adv)
            max_fav = max(max_fav, fav)

            if kl <= cur_sl:
                return ('BE' if be_active else 'LOSS'), max_adv, max_fav
            if kh >= tp:
                return 'WIN', max_adv, max_fav
            if not be_active and kc >= entry + 1.3 * risk:
                be_active = True
                cur_sl = be_price
        else:
            adv = max(0.0, (kh - entry) / risk)
            fav = max(0.0, (entry - kl) / risk)
            max_adv = max(max_adv, adv)
            max_fav = max(max_fav, fav)

            if kh >= cur_sl:
                return ('BE' if be_active else 'LOSS'), max_adv, max_fav
            if kl <= tp:
                return 'WIN', max_adv, max_fav
            if not be_active and kc <= entry - 1.3 * risk:
                be_active = True
                cur_sl = be_price

    return ('BE' if be_active else 'LOSS'), max_adv, max_fav

def analyze_quant_features(df):
    if len(df) == 0:
        print("No trades found.")
        return

    wins = df[df['outcome'] == 'WIN']
    losses = df[df['outcome'] == 'LOSS']
    bes = df[df['outcome'] == 'BE']

    print(f"\nTOTAL EVALUATED TRADES IN STATISTICAL SAMPLE: {len(df)}")
    print(f"Clean Target Wins (>= 3.2R):  {len(wins)} ({len(wins)/len(df)*100:.1f}%)")
    print(f"Breakeven Locks (Q93):        {len(bes)} ({len(bes)/len(df)*100:.1f}%)")
    print(f"Full Losses:                  {len(losses)} ({len(losses)/len(df)*100:.1f}%)")
    print(f"Protected Non-Loss Rate:      {(len(wins)+len(bes))/len(df)*100:.1f}%\n")

    features = [
        ('bars_to_retest', 'Bars to Retest (Wait Time)', 'bars'),
        ('penetration_atr', 'Shelf Penetration Depth', 'ATR'),
        ('wick_ratio', 'Rejection Wick Ratio', '%'),
        ('body_ratio', 'Candle Body Ratio', '%'),
        ('runway_r', 'Runway to Obstacle #1', 'R'),
        ('h1_dist_pct', 'H1 Macro Trend Distance', '%'),
        ('m15_ema_slope', 'M15 Trend Momentum Slope', 'slope'),
        ('max_adverse_r', 'Max Adverse Excursion (Drawdown)', 'R')
    ]

    print("=" * 110)
    print(f"{'FACTOR / METRIC':<34} | {'WINNERS (MEAN)':<16} | {'LOSERS (MEAN)':<16} | {'DIFFERENCE':<14} | {'STAT SIG (P-VAL)':<16}")
    print("-" * 110)

    for col, name, unit in features:
        w_vals = wins[col].dropna()
        l_vals = losses[col].dropna()

        w_mean = w_vals.mean()
        l_mean = l_vals.mean()
        diff = w_mean - l_mean

        # Welch t-test
        t_stat, p_val = sp_stats.ttest_ind(w_vals, l_vals, equal_var=False)

        sig_stars = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "n.s."))
        unit_str = f" {unit}" if unit != '%' else "%"
        
        if unit == '%':
            w_disp = f"{w_mean*100:.1f}%" if col in ('wick_ratio', 'body_ratio') else f"{w_mean:.2f}%"
            l_disp = f"{l_mean*100:.1f}%" if col in ('wick_ratio', 'body_ratio') else f"{l_mean:.2f}%"
            diff_disp = f"{diff*100:+.1f}%" if col in ('wick_ratio', 'body_ratio') else f"{diff:+.2f}%"
        else:
            w_disp = f"{w_mean:.2f}{unit_str}"
            l_disp = f"{l_mean:.2f}{unit_str}"
            diff_disp = f"{diff:+.2f}{unit_str}"

        p_disp = f"p={p_val:.4f} {sig_stars}" if p_val >= 0.0001 else f"p < 0.0001 {sig_stars}"
        print(f"{name:<34} | {w_disp:<16} | {l_disp:<16} | {diff_disp:<14} | {p_disp:<16}")

    print("=" * 110)
    print("Significance Legend: *** p < 0.001 (Dominant Factor) | ** p < 0.01 | * p < 0.05 | n.s. Not Significant")

if __name__ == '__main__':
    run_winner_loser_analysis()
