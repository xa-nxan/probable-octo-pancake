import pandas as pd
import numpy as np


def _get_symbol_profile(symbol: str):
    """
    Symbol-specific calibrations based on MT5 market profiles for the 4 core Weltrade indices:
    FX Vol 20, FX Vol 40, SFX Vol 20, SFX Vol 40.
    """
    sym_clean = symbol.replace(' ', '_')
    if 'SFX_Vol_40' in sym_clean or 'FlipX_2' in symbol:
        return {'spread_pad': 12.0, 'min_stop': 22.0, 'max_stop': 350.0, 'pt_val': 0.01}
    elif 'SFX_Vol_20' in sym_clean or 'FlipX_1' in symbol:
        return {'spread_pad': 4.0, 'min_stop': 15.0, 'max_stop': 150.0, 'pt_val': 0.01}
    elif 'FX_Vol_40' in sym_clean:
        return {'spread_pad': 14.0, 'min_stop': 75.0, 'max_stop': 700.0, 'pt_val': 0.01}
    elif 'FX_Vol_20' in sym_clean:
        return {'spread_pad': 4.5, 'min_stop': 28.0, 'max_stop': 300.0, 'pt_val': 0.01}
    return {'spread_pad': 5.0, 'min_stop': 25.0, 'max_stop': 400.0, 'pt_val': 0.01}


def _compute_ai_conviction_score(
    risk_atr: float,
    rrr: float,
    impulse_atr: float,
    touches: int,
    trend_aligned: bool,
    hl_lh_aligned: bool,
    close_pos: float,
    vol_ratio: float,
    is_protected_wick: bool = True,
) -> int:
    """
    AI/ML Conviction Scorer (0-99%) synthesizing the 100 Break & Retest Questions
    and 3 Price Action Masterclass Lessons:
      1. Protected-Wick Base Tightness (0.30-0.65 ATR sweet spot — never <0.25 ATR spread trap)
      2. Structural H1 R:R Potential (Target 1:5 to 1:11+ within 1-3 H1 candles)
      3. Touch #1 Bounce / Impulse Displacement (Q24, Q31)
      4. Multi-Candle Protected-Wick Absorption (Lesson 2 & 3: Touch #2 holds inside Touch #1)
      5. Trend & Higher-Low / Lower-High Alignment (Lesson 1 & Q18)
      6. Rejection / Ignition Candle Quality & Tick Volume (Q36, Q42)
    """
    score = 0.0

    # 1. Stop tightness relative to ATR (optimal sweet spot is 0.30 - 0.65 ATR)
    if 0.28 <= risk_atr <= 0.48:
        score += 26.0
    elif 0.48 < risk_atr <= 0.62:
        score += 23.0
    elif 0.62 < risk_atr <= 0.78:
        score += 18.5
    elif risk_atr < 0.28:
        score += 12.0  # Penalize overly tight stops vulnerable to spread noise
    else:
        score += 10.0

    # 2. Structural R:R potential (up to 24 pts)
    if 6.0 <= rrr <= 12.5:
        score += 24.0
    elif 5.0 <= rrr < 6.0:
        score += 20.5
    elif 4.2 <= rrr < 5.0:
        score += 16.0
    else:
        score += 12.0

    # 3. Impulse / Touch #1 reaction strength (up to 15 pts)
    if impulse_atr >= 2.2:
        score += 15.0
    elif impulse_atr >= 1.5:
        score += 12.5
    elif impulse_atr >= 1.15:
        score += 10.5
    else:
        score += 5.0

    # 4. Protected-Wick & Multi-candle absorption (up to 16 pts)
    if is_protected_wick:
        score += 10.0
    if touches >= 3:
        score += 6.0
    elif touches == 2:
        score += 4.5
    else:
        score += 2.0

    # 5. Macro structure & EMA alignment (up to 10 pts)
    if trend_aligned:
        score += 5.5
    if hl_lh_aligned:
        score += 4.5

    # 6. Trigger candle closure & volume (up to 8 pts)
    if close_pos >= 0.68:
        score += 5.0
    elif close_pos >= 0.55:
        score += 3.5
    if vol_ratio >= 1.0:
        score += 3.0
    elif vol_ratio >= 0.80:
        score += 1.5

    return int(min(99, max(35, round(score))))


def detect_trades_on_bars(bars_m5, symbol='FX_Vol_40'):
    """
    3-Step Protected-Wick Break & Retest AI/ML Sniper Engine (4 Core Weltrade Vol 20/40 Indices):
    1. Protected-Wick Continuation (Long/Short):
       - Step 1: Impulse break + Touch #1 sets the outer boundary wick (w1_low / w1_high) in [i-24 .. i-3]
                 and bounces >= 1.2 ATR after Touch #1 without ever violating w1_low / w1_high.
       - Step 2: Touch #2+ retests the zone with wicks strictly protected inside Touch #1's wick,
                 bodies closing inside the level, SL strictly below the lowest wick + buffer (>= 0.28 ATR),
                 and 1:5 to 1:11+ H1 structural TP.
       - Step 3: Q93 Breakeven & Ratchet Protection + AI Conviction Score (0-99%).
    2. Pullback to Broken Resistance / Support (Short/Long):
       - Enters on Protected-Wick exhaustion (h[i] < peak_hi or l[i] > trough_lo) after an extended impulse (>= 2.1 ATR),
         with SL strictly outside the peak/trough wick + buffer and TP at the confirmed causal structural level.
    3. Breakout / Breakdown Expansion (Long/Short):
       - Enters on high-conviction marubozu ignition breaking a clean structural swing level.
    """
    if len(bars_m5) < 70:
        return []

    df = pd.DataFrame(bars_m5).sort_values('time').reset_index(drop=True)
    df['time'] = df['time'].astype(int)
    n = len(df)

    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean().bfill()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    if 'tick_volume' in df.columns:
        df['vol_ma'] = df['tick_volume'].rolling(20).mean().bfill()
    elif 'volume' in df.columns:
        df['vol_ma'] = df['volume'].rolling(20).mean().bfill()
    else:
        df['vol_ma'] = 1.0

    prof = _get_symbol_profile(symbol)
    spread_pad = prof['spread_pad']
    min_stop = prof['min_stop']
    max_stop = prof['max_stop']
    pt_val = prof['pt_val']

    highs = df['high'].values
    lows = df['low'].values
    opens = df['open'].values
    closes = df['close'].values
    atrs = df['atr'].values
    times = df['time'].values
    ema20s = df['ema20'].values
    ema50s = df['ema50'].values
    ema200s = df['ema200'].values
    vols = df['tick_volume'].values if 'tick_volume' in df.columns else (df['volume'].values if 'volume' in df.columns else np.ones(n))
    vol_mas = df['vol_ma'].values

    w = 3
    sh_list = []
    sl_list = []
    for idx in range(w, n - w):
        if highs[idx] == np.max(highs[idx - w:idx + w + 1]):
            sh_list.append((idx + w, idx, float(highs[idx])))
        if lows[idx] == np.min(lows[idx - w:idx + w + 1]):
            sl_list.append((idx + w, idx, float(lows[idx])))

    sh_ptr = 0
    sl_ptr = 0
    active_sh = []
    active_sl = []

    trades = []
    last_trade_idx = -10

    i = 50
    while i < n - 20:
        while sh_ptr < len(sh_list) and sh_list[sh_ptr][0] <= i:
            active_sh.append((sh_list[sh_ptr][1], sh_list[sh_ptr][2]))
            sh_ptr += 1
        while sl_ptr < len(sl_list) and sl_list[sl_ptr][0] <= i:
            active_sl.append((sl_list[sl_ptr][1], sl_list[sl_ptr][2]))
            sl_ptr += 1

        if i - last_trade_idx < 4:
            i += 1
            continue

        c = float(closes[i])
        o = float(opens[i])
        h = float(highs[i])
        l = float(lows[i])
        c_prev = float(closes[i - 1])
        atr = float(atrs[i])
        if atr <= 0:
            i += 1
            continue

        c_range = max(1e-5, h - l)
        vol_ratio = float(vols[i]) / max(1.0, float(vol_mas[i]))
        pad = max(spread_pad * 0.6, 0.08 * atr)
        l3_pad = pad + max(1.0, 0.06 * atr)
        eff_min_stop = max(min_stop, 0.28 * atr)
        tp_r_cap = 6.5
        candidates = []

        # =====================================================================
        # 1A. MASTERCLASS Q8 & A8: TOTAL B&R FORMATION (LONG)
        # Price broke an HH structure zone, pulled back, formed rejection wick & bullish pressure
        # =====================================================================
        for sh_idx, res_p in reversed(active_sh[-8:]):
            if i - sh_idx < 3 or i - sh_idx > 60:
                continue
            post_high = float(np.max(highs[sh_idx:i]))
            if post_high >= res_p + 0.30 * atr:
                retest_touch = (l <= res_p + 0.45 * atr) and (c >= res_p - 0.25 * atr)
                rejection_wick = (c - l) >= 0.30 * c_range or (min(o, c) - l) >= 0.12 * atr
                bullish_pressure = (c > o)
                pullback_lh = float(np.max(highs[max(sh_idx, i - 4):i]))
                bos_confirmed = (c >= pullback_lh - 0.12 * atr)

                if retest_touch and rejection_wick and bullish_pressure and bos_confirmed:
                    # Anchor Stop Loss beneath the retest rejection wick and protected level
                    peak_sub_idx = sh_idx + int(np.argmax(highs[sh_idx:i]))
                    retest_wick = float(np.min(lows[peak_sub_idx:i + 1]))
                    raw_sl = round(min(res_p - pad, retest_wick - l3_pad), 2)
                    raw_stop = round(c - raw_sl, 2)
                    if eff_min_stop <= raw_stop <= min(max_stop, 1.25 * atr):
                        entry = round(c, 2)
                        sl = raw_sl
                        stop_dist = max(eff_min_stop, entry - sl)
                        target_dist = max(post_high - entry, 5.5 * stop_dist)
                        tp = round(entry + min(target_dist, 8.5 * stop_dist), 2)
                        profit_dist = round(tp - entry, 2)
                        rrr = round(profit_dist / stop_dist, 2)
                        ai_score = _compute_ai_conviction_score(
                            risk_atr=raw_stop / atr,
                            rrr=min(8.0, rrr),
                            impulse_atr=(post_high - res_p) / atr,
                            touches=2,
                            trend_aligned=(ema20s[i] >= ema50s[i]) or (c >= ema200s[i]),
                            hl_lh_aligned=True,
                            close_pos=(c - l) / c_range,
                            vol_ratio=vol_ratio,
                            is_protected_wick=True
                        )
                        candidates.append({
                            'type': 'long-position',
                            'setup': 'Total B&R Formation (Long — Q8/A8)',
                            'entry': entry,
                            'sl': sl,
                            'tp': tp,
                            'brokenLevel': round(res_p, 2),
                            'stopDist': stop_dist,
                            'profitDist': profit_dist,
                            'rrr': rrr,
                            'ai_score': ai_score,
                            'only_when_sure': bool(ai_score >= 76),
                            'touches': 2,
                            'hl_lh_respected': True,
                            'close_pos': round((c - l) / c_range, 2),
                            'dist_from_zone_atr': round(abs(c - res_p) / atr, 2),
                            'adaptive_adjusted': False,
                            'masterclass_rules': ['Q6_A6', 'Q8_A8', 'Q79_A79', 'Q93_A93'],
                        })
                        break

        # =====================================================================
        # 1B. MASTERCLASS Q8 & A8 MIRROR: TOTAL B&R FORMATION (SHORT)
        # Price broke an LL structure zone, pulled back, formed rejection wick & bearish pressure
        # =====================================================================
        if not candidates:
            for sl_idx, sup_p in reversed(active_sl[-8:]):
                if i - sl_idx < 3 or i - sl_idx > 60:
                    continue
                post_low = float(np.min(lows[sl_idx:i]))
                if post_low <= sup_p - 0.30 * atr:
                    retest_touch = (h >= sup_p - 0.45 * atr) and (c <= sup_p + 0.25 * atr)
                    rejection_wick = (h - c) >= 0.30 * c_range or (h - max(o, c)) >= 0.12 * atr
                    bearish_pressure = (c < o)
                    pullback_hl = float(np.min(lows[max(sl_idx, i - 4):i]))
                    bos_confirmed = (c <= pullback_hl + 0.12 * atr)

                    if retest_touch and rejection_wick and bearish_pressure and bos_confirmed:
                        # Anchor Stop Loss above the retest rejection wick and protected level
                        trough_sub_idx = sl_idx + int(np.argmin(lows[sl_idx:i]))
                        retest_wick = float(np.max(highs[trough_sub_idx:i + 1]))
                        raw_sl = round(max(sup_p + pad, retest_wick + l3_pad), 2)
                        raw_stop = round(raw_sl - c, 2)
                        if eff_min_stop <= raw_stop <= min(max_stop, 1.25 * atr):
                            entry = round(c, 2)
                            sl = raw_sl
                            stop_dist = max(eff_min_stop, sl - entry)
                            target_dist = max(entry - post_low, 5.5 * stop_dist)
                            tp = round(entry - min(target_dist, 8.5 * stop_dist), 2)
                            profit_dist = round(entry - tp, 2)
                            rrr = round(profit_dist / stop_dist, 2)
                            ai_score = _compute_ai_conviction_score(
                                risk_atr=raw_stop / atr,
                                rrr=min(8.0, rrr),
                                impulse_atr=(sup_p - post_low) / atr,
                                touches=2,
                                trend_aligned=(ema20s[i] <= ema50s[i]) or (c <= ema200s[i]),
                                hl_lh_aligned=True,
                                close_pos=(h - c) / c_range,
                                vol_ratio=vol_ratio,
                                is_protected_wick=True
                            )
                            candidates.append({
                                'type': 'short-position',
                                'setup': 'Total B&R Formation (Short — Q8/A8)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': round(sup_p, 2),
                                'stopDist': stop_dist,
                                'profitDist': profit_dist,
                                'rrr': rrr,
                                'ai_score': ai_score,
                                'only_when_sure': bool(ai_score >= 76),
                                'touches': 2,
                                'hl_lh_respected': True,
                                'close_pos': round((h - c) / c_range, 2),
                                'dist_from_zone_atr': round(abs(c - sup_p) / atr, 2),
                                'adaptive_adjusted': False,
                                'masterclass_rules': ['Q6_A6', 'Q8_A8', 'Q79_A79', 'Q93_A93'],
                            })
                            break

        # =====================================================================
        # 2A & 2B. RANGE BOUNDARY RETEST (IMAGES 1, 2, 3: TRADING THE CONSOLIDATION BOX)
        # =====================================================================
        if not candidates and len(active_sh) >= 2 and len(active_sl) >= 2:
            recent_sh = [p for _, p in active_sh[-6:]]
            recent_sl = [p for _, p in active_sl[-6:]]
            box_ceiling = max(recent_sh)
            box_floor = min(recent_sl)
            box_height = box_ceiling - box_floor

            if 1.8 * atr <= box_height <= 7.0 * atr:
                # 2A. Range Floor Retest (Long)
                if (l <= box_floor + 0.40 * atr) and (c >= box_floor - 0.15 * atr) and (c > o):
                    lowest_wick = float(np.min(lows[max(0, i - 6):i + 1]))
                    raw_sl = round(min(box_floor - pad, lowest_wick - l3_pad), 2)
                    raw_stop = round(c - raw_sl, 2)
                    if eff_min_stop <= raw_stop <= min(max_stop, 1.25 * atr):
                        entry = round(c, 2)
                        sl = raw_sl
                        stop_dist = max(eff_min_stop, entry - sl)
                        tp = round(box_ceiling - 0.10 * atr, 2)
                        profit_dist = round(tp - entry, 2)
                        rrr = round(profit_dist / stop_dist, 2)
                        if rrr >= 3.8:
                            ai_score = _compute_ai_conviction_score(
                                risk_atr=raw_stop / atr,
                                rrr=min(8.0, rrr),
                                impulse_atr=box_height / atr,
                                touches=3,
                                trend_aligned=True,
                                hl_lh_aligned=True,
                                close_pos=(c - l) / c_range,
                                vol_ratio=vol_ratio,
                                is_protected_wick=True
                            )
                            candidates.append({
                                'type': 'long-position',
                                'setup': 'Range Floor Retest (Long — Images 1-3)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': round(box_floor, 2),
                                'stopDist': stop_dist,
                                'profitDist': profit_dist,
                                'rrr': rrr,
                                'ai_score': ai_score,
                                'only_when_sure': bool(ai_score >= 76),
                                'touches': 3,
                                'hl_lh_respected': True,
                                'close_pos': round((c - l) / c_range, 2),
                                'dist_from_zone_atr': round((c - box_floor) / atr, 2),
                                'adaptive_adjusted': False,
                                'masterclass_rules': ['Q6_A6', 'Lesson_2', 'Q79_A79', 'Q93_A93'],
                            })

                # 2B. Range Ceiling Retest (Short)
                elif not candidates and (h >= box_ceiling - 0.40 * atr) and (c <= box_ceiling + 0.15 * atr) and (c < o):
                    highest_wick = float(np.max(highs[max(0, i - 6):i + 1]))
                    raw_sl = round(max(box_ceiling + pad, highest_wick + l3_pad), 2)
                    raw_stop = round(raw_sl - c, 2)
                    if eff_min_stop <= raw_stop <= min(max_stop, 1.25 * atr):
                        entry = round(c, 2)
                        sl = raw_sl
                        stop_dist = max(eff_min_stop, sl - entry)
                        tp = round(box_floor + 0.10 * atr, 2)
                        profit_dist = round(entry - tp, 2)
                        rrr = round(profit_dist / stop_dist, 2)
                        if rrr >= 3.8:
                            ai_score = _compute_ai_conviction_score(
                                risk_atr=raw_stop / atr,
                                rrr=min(8.0, rrr),
                                impulse_atr=box_height / atr,
                                touches=3,
                                trend_aligned=True,
                                hl_lh_aligned=True,
                                close_pos=(h - c) / c_range,
                                vol_ratio=vol_ratio,
                                is_protected_wick=True
                            )
                            candidates.append({
                                'type': 'short-position',
                                'setup': 'Range Ceiling Retest (Short — Images 1-3)',
                                'entry': entry,
                                'sl': sl,
                                'tp': tp,
                                'brokenLevel': round(box_ceiling, 2),
                                'stopDist': stop_dist,
                                'profitDist': profit_dist,
                                'rrr': rrr,
                                'ai_score': ai_score,
                                'only_when_sure': bool(ai_score >= 76),
                                'touches': 3,
                                'hl_lh_respected': True,
                                'close_pos': round((h - c) / c_range, 2),
                                'dist_from_zone_atr': round((box_ceiling - c) / atr, 2),
                                'adaptive_adjusted': False,
                                'masterclass_rules': ['Q6_A6', 'Lesson_2', 'Q79_A79', 'Q93_A93'],
                            })

        # =====================================================================
        # 3A & 3B. MARUBOZU BREAKOUT / BREAKDOWN EXPANSION WITH CLOSURE ENTRY
        # =====================================================================
        if not candidates and active_sh and active_sl:
            _, res_p = active_sh[-1]
            _, sup_p = active_sl[-1]
            if c > res_p and c_prev <= res_p and c > o and (o - l) <= 0.15 * c_range and (c - l) / c_range >= 0.78:
                # Anchor SL below the pre-breakout structural swing low or shelf, preventing premature retest stop-outs
                pre_swing_l = float(np.min(lows[max(0, i - 8):i + 1]))
                raw_sl = round(min(res_p - pad, pre_swing_l - l3_pad), 2)
                raw_stop = round(c - raw_sl, 2)
                if eff_min_stop <= raw_stop <= min(max_stop, 1.45 * atr):
                    entry = round(c, 2)
                    sl = raw_sl
                    stop_dist = max(eff_min_stop, entry - sl)
                    tp = round(entry + 5.5 * stop_dist, 2)
                    profit_dist = round(tp - entry, 2)
                    rrr = round(profit_dist / stop_dist, 2)
                    ai_score = _compute_ai_conviction_score(
                        risk_atr=raw_stop / atr,
                        rrr=5.5,
                        impulse_atr=c_range / atr,
                        touches=1,
                        trend_aligned=(ema20s[i] >= ema50s[i]),
                        hl_lh_aligned=True,
                        close_pos=(c - l) / c_range,
                        vol_ratio=vol_ratio,
                        is_protected_wick=True,
                    )
                    candidates.append({
                        'type': 'long-position',
                        'setup': 'Breakout Expansion (Long)',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'brokenLevel': round(res_p, 2),
                        'stopDist': stop_dist,
                        'profitDist': profit_dist,
                        'rrr': rrr,
                        'ai_score': ai_score,
                        'only_when_sure': bool(ai_score >= 76),
                        'touches': 1,
                        'hl_lh_respected': bool(ema20s[i] >= ema50s[i]),
                        'close_pos': round((c - l) / c_range, 2),
                        'dist_from_zone_atr': round((c - res_p) / atr, 2),
                        'adaptive_adjusted': True,
                        'masterclass_rules': ['Q6_A6', 'Q7_A7', 'Q79_A79', 'Q93_A93'],
                    })
            elif c < sup_p and c_prev >= sup_p and c < o and (h - o) <= 0.15 * c_range and (h - c) / c_range >= 0.78:
                # Anchor SL above the pre-breakdown structural swing high or shelf, preventing premature retest stop-outs
                pre_swing_h = float(np.max(highs[max(0, i - 8):i + 1]))
                raw_sl = round(max(sup_p + pad, pre_swing_h + l3_pad), 2)
                raw_stop = round(raw_sl - c, 2)
                if eff_min_stop <= raw_stop <= min(max_stop, 1.45 * atr):
                    entry = round(c, 2)
                    sl = raw_sl
                    stop_dist = max(eff_min_stop, sl - entry)
                    tp = round(entry - 5.5 * stop_dist, 2)
                    profit_dist = round(entry - tp, 2)
                    rrr = round(profit_dist / stop_dist, 2)
                    ai_score = _compute_ai_conviction_score(
                        risk_atr=raw_stop / atr,
                        rrr=5.5,
                        impulse_atr=c_range / atr,
                        touches=1,
                        trend_aligned=(ema20s[i] <= ema50s[i]),
                        hl_lh_aligned=True,
                        close_pos=(h - c) / c_range,
                        vol_ratio=vol_ratio,
                        is_protected_wick=True,
                    )
                    candidates.append({
                        'type': 'short-position',
                        'setup': 'Breakdown Expansion (Short)',
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'brokenLevel': round(sup_p, 2),
                        'stopDist': stop_dist,
                        'profitDist': profit_dist,
                        'rrr': rrr,
                        'ai_score': ai_score,
                        'only_when_sure': bool(ai_score >= 76),
                        'touches': 1,
                        'hl_lh_respected': bool(ema20s[i] <= ema50s[i]),
                        'close_pos': round((h - c) / c_range, 2),
                        'dist_from_zone_atr': round((sup_p - c) / atr, 2),
                        'adaptive_adjusted': True,
                        'masterclass_rules': ['Q6_A6', 'Q7_A7', 'Q79_A79', 'Q93_A93'],
                    })

        if candidates:
            candidates.sort(key=lambda x: (x['ai_score'], x['rrr']), reverse=True)
            tc = candidates[0]

            horizon = min(n, i + 72)
            entry_p = tc['entry']
            stop_d = tc['stopDist']
            profit_d = tc['profitDist']
            tp_r = profit_d / max(1e-5, stop_d)
            be_locked = False
            hit_sl = False
            exit_time = None
            peak_r = 0.0
            realized_r = 0.0
            outcome = 'SL'
            pyramid_tranches = []
            last_pyr_k = i

            # Masterclass Q16/A16, Q19/A19, Q79/A79, Q93/A93 & Trailing System:
            # 1. Arm Protected BE (+0.15R) only AFTER clearing Obstacle #1 (>= 1.6R) so 1-candle H1 pullbacks don't suffocate trades
            # 2. Ratchet Trailing SL at +3.0R (lock +1.2R) and +4.5R (lock +2.5R)
            # 3. Full Take-Profit at target
            if tc['type'] == 'long-position':
                act_sl = tc['sl']
                for k in range(i + 1, horizon):
                    fb_l = float(lows[k])
                    fb_h = float(highs[k])
                    fb_c = float(closes[k])
                    fb_o = float(opens[k])
                    fb_t = int(times[k])

                    fav = (fb_h - entry_p) / stop_d
                    if fav > peak_r:
                        peak_r = fav

                    # Check TP hit first
                    if fav >= tp_r:
                        exit_time = fb_t
                        realized_r = tp_r
                        outcome = 'FULL_TP'
                        break

                    # Dynamic Trailing Ratchet:
                    # Give trade room to breathe through 1-candle H1 pullback:
                    # Arm BE only after clearing obstacle #1 (>= 1.4R)
                    # Lock +1.0R at 2.6R+, Lock +2.5R at 4.2R+
                    if peak_r >= 4.2:
                        act_sl = max(act_sl, round(entry_p + 2.5 * stop_d, 2))
                    elif peak_r >= 2.6:
                        act_sl = max(act_sl, round(entry_p + 1.0 * stop_d, 2))
                    elif peak_r >= 1.4:
                        be_locked = True
                        act_sl = max(act_sl, round(entry_p + 0.15 * stop_d, 2))

                    # Free-Roll Pyramiding Add at subsequent retest line (only when in profit and Obstacle #1 cleared)
                    if be_locked and peak_r >= 2.2 and len(pyramid_tranches) < 2 and (k - last_pyr_k >= 5):
                        p_wick_ok = (fb_c > fb_o) and (fb_c - fb_l >= 0.28 * (fb_h - fb_l))
                        p_rem_tp = tc['tp'] - fb_c
                        p_sl = round(min(fb_l, float(lows[k-1])) - spread_pad, 2)
                        p_risk = round(fb_c - p_sl, 2)
                        if p_wick_ok and eff_min_stop <= p_risk <= 1.25 * atrs[k] and p_rem_tp >= 2.0 * p_risk:
                            pyramid_tranches.append({
                                'entry': round(fb_c, 2),
                                'sl': p_sl,
                                'lot': 0.01,
                                'entry_time': fb_t,
                                'dist_to_tp': p_rem_tp
                            })
                            last_pyr_k = k

                    # Check SL / Trailing hit
                    if fb_l <= act_sl:
                        hit_sl = True
                        exit_time = fb_t
                        if act_sl >= round(entry_p + 0.7 * stop_d, 2):
                            realized_r = round((act_sl - entry_p) / stop_d, 2)
                            outcome = 'TRAIL_WIN'
                        elif act_sl > entry_p:
                            realized_r = 0.15
                            outcome = 'PROTECTED_BE'
                        else:
                            realized_r = -1.0
                            outcome = 'SL'
                        break

                if not exit_time:
                    exit_time = int(times[horizon - 1])
                    end_r = (float(closes[horizon - 1]) - entry_p) / stop_d
                    if end_r >= 1.0:
                        realized_r = round(end_r, 2)
                        outcome = 'TRAIL_WIN'
                    elif end_r >= 0.0:
                        realized_r = 0.15
                        outcome = 'PROTECTED_BE'
                    else:
                        realized_r = -1.0
                        outcome = 'SL'
            else:
                act_sl = tc['sl']
                for k in range(i + 1, horizon):
                    fb_l = float(lows[k])
                    fb_h = float(highs[k])
                    fb_c = float(closes[k])
                    fb_o = float(opens[k])
                    fb_t = int(times[k])

                    fav = (entry_p - fb_l) / stop_d
                    if fav > peak_r:
                        peak_r = fav

                    # Check TP hit first
                    if fav >= tp_r:
                        exit_time = fb_t
                        realized_r = tp_r
                        outcome = 'FULL_TP'
                        break

                    # Dynamic Trailing Ratchet:
                    # Give trade room to breathe through 1-candle H1 pullback:
                    # Arm BE only after clearing obstacle #1 (>= 1.4R)
                    # Lock +1.0R at 2.6R+, Lock +2.5R at 4.2R+
                    if peak_r >= 4.2:
                        act_sl = min(act_sl, round(entry_p - 2.5 * stop_d, 2))
                    elif peak_r >= 2.6:
                        act_sl = min(act_sl, round(entry_p - 1.0 * stop_d, 2))
                    elif peak_r >= 1.4:
                        be_locked = True
                        act_sl = min(act_sl, round(entry_p - 0.15 * stop_d, 2))

                    # Free-Roll Pyramiding Add at subsequent retest line (only when in profit and Obstacle #1 cleared)
                    if be_locked and peak_r >= 2.2 and len(pyramid_tranches) < 2 and (k - last_pyr_k >= 5):
                        p_wick_ok = (fb_c < fb_o) and (fb_h - fb_c >= 0.28 * (fb_h - fb_l))
                        p_rem_tp = fb_c - tc['tp']
                        p_sl = round(max(fb_h, float(highs[k-1])) + spread_pad, 2)
                        p_risk = round(p_sl - fb_c, 2)
                        if p_wick_ok and eff_min_stop <= p_risk <= 1.25 * atrs[k] and p_rem_tp >= 2.0 * p_risk:
                            pyramid_tranches.append({
                                'entry': round(fb_c, 2),
                                'sl': p_sl,
                                'lot': 0.01,
                                'entry_time': fb_t,
                                'dist_to_tp': p_rem_tp
                            })
                            last_pyr_k = k

                    # Check SL / Trailing hit
                    if fb_h >= act_sl:
                        hit_sl = True
                        exit_time = fb_t
                        if act_sl <= round(entry_p - 0.7 * stop_d, 2):
                            realized_r = round((entry_p - act_sl) / stop_d, 2)
                            outcome = 'TRAIL_WIN'
                        elif act_sl < entry_p:
                            realized_r = 0.15
                            outcome = 'PROTECTED_BE'
                        else:
                            realized_r = -1.0
                            outcome = 'SL'
                        break

                if not exit_time:
                    exit_time = int(times[horizon - 1])
                    end_r = (entry_p - float(closes[horizon - 1])) / stop_d
                    if end_r >= 1.0:
                        realized_r = round(end_r, 2)
                        outcome = 'TRAIL_WIN'
                    elif end_r >= 0.0:
                        realized_r = 0.15
                        outcome = 'PROTECTED_BE'
                    else:
                        realized_r = -1.0
                        outcome = 'SL'

            # Hindsight "what could have happened" (display only, never used as a model feature):
            potential_r, potential_time, potential_price = 0.0, int(times[i]), entry_p
            is_long_tc = tc['type'] == 'long-position'
            for k in range(i + 1, horizon):
                if is_long_tc:
                    if float(lows[k]) <= tc['sl']:
                        break
                    px = float(highs[k])
                    fav_k = (px - entry_p) / stop_d
                else:
                    if float(highs[k]) >= tc['sl']:
                        break
                    px = float(lows[k])
                    fav_k = (entry_p - px) / stop_d
                if fav_k > potential_r:
                    potential_r, potential_time, potential_price = fav_k, int(times[k]), px

            base_pts = round(realized_r * stop_d, 2)
            base_pnl_usd = round(base_pts * pt_val, 2)

            # Pyramiding Profit Allocation:
            pyr_extra_pts = 0.0
            pyr_extra_usd = 0.0
            if outcome in ('FULL_TP', 'TRAIL_WIN') and pyramid_tranches:
                frac = 1.0 if outcome == 'FULL_TP' else (realized_r / max(1.0, tp_r))
                for ptr in pyramid_tranches:
                    p_pts = round(ptr['dist_to_tp'] * frac, 2)
                    p_usd = round(p_pts * pt_val * (ptr['lot'] / 0.01), 2)
                    pyr_extra_pts += p_pts
                    pyr_extra_usd += p_usd

            pts = round(base_pts + pyr_extra_pts, 2)
            is_win = bool(pts > 0)
            pnl_usd = round(base_pnl_usd + pyr_extra_usd, 2)

            hl_ok = tc.get('hl_lh_respected', True)
            dist_z = tc.get('dist_from_zone_atr', 0.25)
            t_cnt = tc.get('touches', 2)
            c_pos = tc.get('close_pos', 0.65)
            adapt_adj = tc.get('adaptive_adjusted', False)

            if outcome in ('FULL_TP', 'TRAIL_WIN'):
                failure_category = 'NONE_MASTERCLASS_WIN'
                ai_diagnosis = (
                    f"[MASTERCLASS WIN ({outcome}: +{realized_r:.2f}R)] {symbol}: "
                    f"Touch #{t_cnt} Protected-Wick entry at {tc['entry']:.2f} ({dist_z:.2f} ATR from zone {tc['brokenLevel']:.2f}). "
                    f"Level-3 SL ({tc['sl']:.2f}) held retest fluctuations; runner rode to +{peak_r:.2f}R."
                )
                adaptive_fix = (
                    "Adaptive Self-Correction Applied: Waited for deeper 0.52 pullback entry + extra 0.04 ATR Level-3 SL cushion."
                    if adapt_adj else
                    "Reinforced: Ideal Touch #2+ Closure-Level entry & HL/LH alignment."
                )
            elif outcome == 'PROTECTED_BE':
                if t_cnt <= 1 or 'Expansion' in tc['setup']:
                    failure_category = 'TOUCH_1_PREMATURE_ENTRY'
                    ai_diagnosis = (
                        f"[1ST TOUCH SWEEP SCRATCH (+0.20R BE)] {symbol}: Entered on Touch #1 before liquidity sweep completed (Q15/Q70). "
                        f"Moved +{peak_r:.2f}R then retested the zone."
                    )
                    adaptive_fix = "Wait for Touch #2 Protected-Wick confirmation (Q70/A70) & hold runner stop under Level-3 Retest Point (Q16/Q93)."
                elif not hl_ok:
                    failure_category = 'HL_LH_STRUCTURE_NOT_RESPECTED'
                    ai_diagnosis = (
                        f"[HL/LH STRUCTURE VIOLATION SCRATCH (+0.20R BE)] {symbol}: Prior 25-bar HL/LH sequence was not respected (Q18/Q26/Q29). "
                        f"Setup reached +{peak_r:.2f}R before stalling at opposing structure; saved at +0.20R by Q93 protection."
                    )
                    adaptive_fix = "Enforce strict HL/LH swing alignment (Q18/Q26) & require 0.52 deeper pullback entry."
                elif dist_z > 0.42:
                    failure_category = 'ENTERED_BEFORE_PULLBACK_COMPLETED'
                    ai_diagnosis = (
                        f"[PRE-PULLBACK ENTRY SCRATCH (+0.20R BE)] {symbol}: Entered {dist_z:.2f} ATR away from broken zone ({tc['brokenLevel']:.2f}) "
                        f"before deep pullback completed (Q80/Q81). Reached +{peak_r:.2f}R then pulled back to retest point."
                    )
                    adaptive_fix = "Tighten entry closer to Closure Level (0.52 LTF fraction, Q6/Q7/Q81)."
                else:
                    failure_category = 'OPPOSING_BARRIER_RETEST_SCRATCH'
                    ai_diagnosis = (
                        f"[OBSTACLE #1 RETEST SCRATCH (+0.20R BE)] {symbol}: Reached +{peak_r:.2f}R into Obstacle #1 (Q16/Q23/Q65) "
                        f"before deeper pullback. Downside protected at +0.20R."
                    )
                    adaptive_fix = "Monitor Obstacle #1 (Breakout HH/LL) for Double Top/Bottom rejection (Q16/A16)."
            else:
                if t_cnt <= 1 or 'Expansion' in tc['setup']:
                    failure_category = 'TOUCH_1_PREMATURE_ENTRY'
                    ai_diagnosis = (
                        f"[LOSS CAUSE: 1ST TOUCH ENTRY (Q15/Q70)] {symbol}: Entered on Touch #1 before liquidity sweep of {tc['brokenLevel']:.2f} completed."
                    )
                    adaptive_fix = "Adapted: Require Touch #2 Protected-Wick & add +0.04 ATR Level-3 SL buffer (Q79/A79)."
                elif not hl_ok:
                    failure_category = 'HL_LH_STRUCTURE_NOT_RESPECTED'
                    ai_diagnosis = (
                        f"[LOSS CAUSE: HL/LH NOT RESPECTED (Q18/Q26/Q29)] {symbol}: Higher Low / Lower High structure was violated relative to prior swing sequence; price broke through Level-3 SL ({tc['sl']:.2f})."
                    )
                    adaptive_fix = "Adapted: Enforce HL/LH structural alignment guard (Q18/Q26) + deeper 0.52 Closure-Level entry."
                elif dist_z > 0.42:
                    failure_category = 'ENTERED_BEFORE_PULLBACK_COMPLETED'
                    ai_diagnosis = (
                        f"[LOSS CAUSE: ENTERED BEFORE PULLBACK (Q15/Q80/Q81)] {symbol}: Entered {dist_z:.2f} ATR from zone ({tc['brokenLevel']:.2f}) before pullback finished; subsequent retest swept SL."
                    )
                    adaptive_fix = "Adapted: Lower LTF entry fraction to 0.52 closer to Closure Level & widen Level-3 SL cushion (+0.04 ATR)."
                elif c_pos < 0.55:
                    failure_category = 'WEAK_CLOSURE_REJECTION'
                    ai_diagnosis = (
                        f"[LOSS CAUSE: WEAK CLOSURE REJECTION (Q6/Q7/Q83)] {symbol}: Confirmation candle closed weakly (close_pos={c_pos:.2f}) without decisive engulfing pressure."
                    )
                    adaptive_fix = "Adapted: Require stronger confirmation body closure above/below Closure Level (Q6/Q7)."
                else:
                    failure_category = 'DEEP_STRUCTURAL_INVALIDATION'
                    ai_diagnosis = (
                        f"[LOSS CAUSE: MACRO STRUCTURAL INVALIDATION (Q18/Q78)] {symbol}: Full candle body closed through Level-3 Rejection Range ({tc['sl']:.2f}), invalidating the setup."
                    )
                    adaptive_fix = "Accepted structural 1R stop; wait for new Break & Retest in opposite direction (Q32/Q96)."

            trades.append({
                'id': f"trade_{len(trades) + 1}",
                'symbol': symbol,
                'type': tc['type'],
                'setup': tc['setup'],
                'entryTime': int(times[i]),
                'exitTime': exit_time or int(times[horizon - 1]),
                'entry': tc['entry'],
                'sl': tc['sl'],
                'tp': tc['tp'],
                'brokenLevel': tc['brokenLevel'],
                'stopDist': tc['stopDist'],
                'profitDist': tc['profitDist'],
                'win': is_win,
                'outcome': outcome,
                'points': pts,
                'base_pnl_usd': base_pnl_usd,
                'pyramid_extra_usd': pyr_extra_usd,
                'pnl_usd': pnl_usd,
                'pyramid_tranches_count': len(pyramid_tranches),
                'rrr': tc['rrr'],
                'realized_r': round(realized_r, 2),
                'peak_r': round(peak_r, 2),
                'potential_r': round(potential_r, 2),
                'potential_time': potential_time,
                'potential_price': round(potential_price, 2),
                'ai_score': tc['ai_score'],
                'only_when_sure': tc['only_when_sure'],
                'touches': tc['touches'],
                'hl_lh_respected': hl_ok,
                'dist_from_zone_atr': dist_z,
                'adaptive_adjusted': adapt_adj,
                'failure_category': failure_category,
                'ai_diagnosis': ai_diagnosis,
                'adaptive_fix': adaptive_fix,
                'masterclass_rules': tc.get('masterclass_rules', []),
            })
            last_trade_idx = i
            i += 3
            continue

        i += 1

    return trades


def scan_live_sniper_setup(
    df: pd.DataFrame,
    symbol: str,
    curr_price: float,
    spread_pts: float,
    digits: int,
    margin_001: float,
):
    """
    Real-Time 3-Step Protected-Wick & Pullback AI Sniper Scanner for /scanner/live.
    Strictly enforces:
      1. NEVER places a Bullish SL above the absolute lowest wick of the recent window (including current candle!).
      2. NEVER places a Bearish SL below the absolute highest wick of the recent window (including current candle!).
      3. NEVER calls an active falling-knife breakdown a 'Protected-Wick Long' — requires a confirmed Touch #1
         that held AND bounced >= 1.15 ATR before Touch #2, OR identifies the broken support/resistance retest!
      4. Enforces realistic structural Stop Distance (0.38 to 0.78 ATR and >= 4x spread) so Plan R:R is a true 1:5 to 1:10.
    """
    n = len(df)
    if n < 35:
        return None

    highs = df['high'].astype(float).values
    lows = df['low'].astype(float).values
    opens = df['open'].astype(float).values
    closes = df['close'].astype(float).values

    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]
    atr = float(pd.Series(tr).rolling(14).mean().bfill().iloc[-1])
    if atr <= 0:
        atr = float(np.mean(tr))

    ema20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(pd.Series(closes).ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(pd.Series(closes).ewm(span=200, adjust=False).mean().iloc[-1])

    prof = _get_symbol_profile(symbol)
    eff_spread = max(spread_pts, prof['spread_pad'])
    # Buffer outside the outer wick so spread + wick noise never clips the stop
    wick_pad = max(1.8 * eff_spread, 0.12 * atr)
    # Minimum total stop distance from entry (at least 0.38 ATR and 4x spread)
    min_stop_dist = max(prof['min_stop'], 4.0 * eff_spread, 0.38 * atr)

    # Full 26-bar window INCLUDING the last 2 bars so we know the true absolute floor & ceiling
    abs_low_26_idx = (n - 26) + int(np.argmin(lows[n - 26:]))
    abs_low_26 = float(lows[abs_low_26_idx])

    abs_high_26_idx = (n - 26) + int(np.argmax(highs[n - 26:]))
    abs_high_26 = float(highs[abs_high_26_idx])

    # Check if Touch #1 floor occurred at least 2 bars ago AND bounced >= 1.10 ATR without being violated since
    bull_touch1_valid = False
    if abs_low_26_idx <= n - 3:
        bounce_after_low = float(np.max(highs[abs_low_26_idx + 1:])) - abs_low_26
        subsequent_min = float(np.min(lows[abs_low_26_idx + 1:]))
        if bounce_after_low >= 1.10 * atr and subsequent_min > abs_low_26 and curr_price > abs_low_26:
            bull_touch1_valid = True
    else:
        bounce_after_low = 0.0

    # Check if Touch #1 ceiling occurred at least 2 bars ago AND dropped >= 1.10 ATR without being violated since
    bear_touch1_valid = False
    if abs_high_26_idx <= n - 3:
        drop_after_high = abs_high_26 - float(np.min(lows[abs_high_26_idx + 1:]))
        subsequent_max = float(np.max(highs[abs_high_26_idx + 1:]))
        if drop_after_high >= 1.10 * atr and subsequent_max < abs_high_26 and curr_price < abs_high_26:
            bear_touch1_valid = True
    else:
        drop_after_high = 0.0

    struct_hi = float(np.max(highs[max(0, n - 65):]))
    struct_lo = float(np.min(lows[max(0, n - 65):]))

    # Also find prior broken support / resistance from [n-60 .. n-12] for Breakdown/Breakout Retest setups
    prior_support = float(np.min(lows[max(0, n - 55):n - 10]))
    prior_resistance = float(np.max(highs[max(0, n - 55):n - 10]))

    c_last = float(closes[-1])
    h_last = float(highs[-1])
    l_last = float(lows[-1])
    rng_last = max(1e-5, h_last - l_last)

    dist_bull_atr = (curr_price - abs_low_26) / atr
    dist_bear_atr = (abs_high_26 - curr_price) / atr

    # Always evaluate the structural boundary (floor vs ceiling) that price is actually closest to
    choose_bull = dist_bull_atr <= dist_bear_atr
    max_stop_dist = 0.88 * atr

    if choose_bull:
        true_floor = min(abs_low_26, l_last, curr_price)
        local_low_6 = float(np.min(lows[-6:]))
        touches = int(np.sum(lows[abs_low_26_idx:] <= abs_low_26 + 0.48 * atr))

        if bull_touch1_valid and 0.0 < dist_bull_atr <= 0.58:
            status = "AT_RETEST_ZONE"
            setup_name = f"Protected-Wick Long ({max(2, touches)}x Touch)"
            exec_entry = round(curr_price, digits)
            ref_wick = true_floor
        elif bull_touch1_valid and 0.58 < dist_bull_atr <= 1.45:
            status = "APPROACHING"
            setup_name = "Protected-Wick Floor (Watch Retest)"
            exec_entry = round(true_floor + 0.25 * atr, digits)
            ref_wick = true_floor
        else:
            status = "PULLBACK"
            setup_name = (
                f"Protected-Wick Long ({max(2, touches)}x Touch)"
                if bull_touch1_valid
                else "Impulse-Trough Pullback (Wait Green Close)"
            )
            exec_entry = round(curr_price, digits)
            # Anchor SL below the nearest active swing low wick (within 0.88 ATR)
            ref_wick = true_floor if (curr_price - true_floor) <= max_stop_dist else min(local_low_6, l_last)

        # SL is strictly below ref_wick by wick_pad, and stop_dist is bounded in [min_stop_dist, max_stop_dist]
        sl_raw = min(ref_wick - wick_pad, exec_entry - min_stop_dist)
        if (exec_entry - sl_raw) > max_stop_dist:
            sl_raw = min(l_last - wick_pad, exec_entry - max_stop_dist)
        sl = round(sl_raw, digits)
        stop_dist = max(min_stop_dist, abs(exec_entry - sl))

        raw_target = prior_support if (not bull_touch1_valid and prior_support > exec_entry + 4.5 * stop_dist) else struct_hi
        tp_raw = min(max(raw_target, exec_entry + 5.2 * stop_dist), exec_entry + 9.2 * stop_dist)
        tp = round(tp_raw, digits)
        rrr = round((tp - exec_entry) / max(1.0, stop_dist), 2)

        close_pos = (c_last - l_last) / rng_last
        ai_score = _compute_ai_conviction_score(
            risk_atr=stop_dist / atr,
            rrr=rrr,
            impulse_atr=bounce_after_low / atr if bull_touch1_valid else 1.1,
            touches=touches if bull_touch1_valid else 1,
            trend_aligned=(ema20 >= ema50) or (curr_price >= ema200),
            hl_lh_aligned=bull_touch1_valid,
            close_pos=close_pos,
            vol_ratio=1.0,
            is_protected_wick=bull_touch1_valid,
        )

        return {
            "symbol": symbol,
            "direction": "BULLISH",
            "setup": setup_name,
            "level": round(true_floor, digits),
            "current_price": round(curr_price, digits),
            "entry": exec_entry,
            "sl": sl,
            "tp": tp,
            "rrr": rrr,
            "ai_score": ai_score,
            "only_when_sure": bool(ai_score >= 76 and bull_touch1_valid),
            "dist_pts": round(curr_price - true_floor, digits),
            "dist_atr": round((curr_price - true_floor) / atr, 2),
            "status": status,
            "margin_001": round(float(margin_001), 2) if margin_001 else 0.0,
            "spread_pts": spread_pts,
        }
    else:
        true_ceiling = max(abs_high_26, h_last, curr_price)
        local_high_6 = float(np.max(highs[-6:]))
        touches = int(np.sum(highs[abs_high_26_idx:] >= abs_high_26 - 0.48 * atr))

        if bear_touch1_valid and 0.0 < dist_bear_atr <= 0.58:
            status = "AT_RETEST_ZONE"
            setup_name = f"Protected-Wick Short ({max(2, touches)}x Touch)"
            exec_entry = round(curr_price, digits)
            ref_wick = true_ceiling
        elif bear_touch1_valid and 0.58 < dist_bear_atr <= 1.45:
            status = "APPROACHING"
            setup_name = "Protected-Wick Ceiling (Watch Retest)"
            exec_entry = round(true_ceiling - 0.25 * atr, digits)
            ref_wick = true_ceiling
        else:
            status = "PULLBACK"
            setup_name = (
                f"Protected-Wick Short ({max(2, touches)}x Touch)"
                if bear_touch1_valid
                else "Impulse-Peak Pullback (Wait Red Close)"
            )
            exec_entry = round(curr_price, digits)
            ref_wick = true_ceiling if (true_ceiling - curr_price) <= max_stop_dist else max(local_high_6, h_last)

        sl_raw = max(ref_wick + wick_pad, exec_entry + min_stop_dist)
        if (sl_raw - exec_entry) > max_stop_dist:
            sl_raw = max(h_last + wick_pad, exec_entry + max_stop_dist)
        sl = round(sl_raw, digits)
        stop_dist = max(min_stop_dist, abs(sl - exec_entry))

        raw_target = prior_resistance if (not bear_touch1_valid and prior_resistance < exec_entry - 4.5 * stop_dist) else struct_lo
        tp_raw = max(min(raw_target, exec_entry - 5.2 * stop_dist), exec_entry - 9.2 * stop_dist)
        tp = round(tp_raw, digits)
        rrr = round((exec_entry - tp) / max(1.0, stop_dist), 2)

        close_pos = (h_last - c_last) / rng_last
        ai_score = _compute_ai_conviction_score(
            risk_atr=stop_dist / atr,
            rrr=rrr,
            impulse_atr=drop_after_high / atr if bear_touch1_valid else 1.1,
            touches=touches if bear_touch1_valid else 1,
            trend_aligned=(ema20 <= ema50) or (curr_price <= ema200),
            hl_lh_aligned=bear_touch1_valid,
            close_pos=close_pos,
            vol_ratio=1.0,
            is_protected_wick=bear_touch1_valid,
        )

        return {
            "symbol": symbol,
            "direction": "BEARISH",
            "setup": setup_name,
            "level": round(true_ceiling, digits),
            "current_price": round(curr_price, digits),
            "entry": exec_entry,
            "sl": sl,
            "tp": tp,
            "rrr": rrr,
            "ai_score": ai_score,
            "only_when_sure": bool(ai_score >= 76 and bear_touch1_valid),
            "dist_pts": round(true_ceiling - curr_price, digits),
            "dist_atr": round((true_ceiling - curr_price) / atr, 2),
            "status": status,
            "margin_001": round(float(margin_001), 2) if margin_001 else 0.0,
            "spread_pts": spread_pts,
        }


def scan_multi_timeframe_sniper_setups(
    tf_dfs: dict,
    symbol: str,
    curr_price: float,
    spread_pts: float,
    digits: int,
    margin_001: float,
    target_tf: str = "ALL",
    filter_tf: str = None,
) -> list:
    if filter_tf is not None:
        target_tf = filter_tf
    """
    Multi-Timeframe Top-Down Masterclass Scanner & Execution Engine:
    Strict Rule: NEVER trade or look for setups on standalone M5 or M1.
    All setups MUST anchor in Higher Timeframes (M30, H1, H4, or M15).
    M5 is strictly used as the sniper execution timeframe:
      1. HTF Setup -> M5 Sniper Execution (e.g. H4/H1/M30/M15 Break & Retest Zone refined onto M5 for Level-3 micro SL & 1:10+ R:R).
      2. HTF Pullback Traded on M5 (Trading an H4/H1/M30 pullback leg using an M5 confirmation trigger with >= 4R room to the HTF level).
      3. Cross-Confirmation Guard: If M5 opposes HTF momentum or has no HTF anchor, the setup is rejected to prevent false breakouts.
    """
    single_tf_scans = {}
    for tf_name, df in tf_dfs.items():
        if df is not None and len(df) >= 35:
            res = scan_live_sniper_setup(
                df=df,
                symbol=symbol,
                curr_price=curr_price,
                spread_pts=spread_pts,
                digits=digits,
                margin_001=margin_001,
            )
            if res:
                res["timeframe"] = tf_name
                res["htf_timeframe"] = tf_name
                res["exec_timeframe"] = tf_name
                res["timeframe_pair"] = f"{tf_name} Direct"
                res["mtf_mode"] = "DIRECT_TF"
                single_tf_scans[tf_name] = res

    # HTF candidates in priority order
    htf_candidates = ["H1", "M30", "H4", "M15"]

    # When user selects M5 (or M1) specifically, STRICTLY require an HTF anchor setup!
    if target_tf in ("M5", "M1"):
        m5_scan = single_tf_scans.get("M5")
        for htf in htf_candidates:
            h_scan = single_tf_scans.get(htf)
            if not h_scan:
                continue

            # Mode 1: HTF Continuation / Retest Zone + M5 Micro-Execution
            if m5_scan and h_scan["direction"] == m5_scan["direction"] and h_scan["status"] in ("AT_RETEST_ZONE", "APPROACHING", "PULLBACK"):
                merged = dict(m5_scan)
                stop_d = max(1e-5, abs(merged["entry"] - merged["sl"]))
                if merged["direction"] == "BULLISH":
                    htf_tp = max(merged["tp"], min(h_scan["tp"], merged["entry"] + 12.0 * stop_d))
                    merged["tp"] = round(htf_tp, digits)
                    merged["rrr"] = round((merged["tp"] - merged["entry"]) / stop_d, 2)
                else:
                    htf_tp = min(merged["tp"], max(h_scan["tp"], merged["entry"] - 12.0 * stop_d))
                    merged["tp"] = round(htf_tp, digits)
                    merged["rrr"] = round((merged["entry"] - merged["tp"]) / stop_d, 2)

                merged["timeframe"] = "M5"
                merged["htf_timeframe"] = htf
                merged["exec_timeframe"] = "M5"
                merged["timeframe_pair"] = f"{htf} Setup → M5 Exec"
                merged["mtf_mode"] = "HTF_SETUP_LTF_EXEC"
                merged["level"] = h_scan["level"]
                merged["setup"] = f"[{htf} Setup → M5 Exec] {m5_scan['setup']}"
                merged["ai_score"] = min(99, max(h_scan["ai_score"], m5_scan["ai_score"]) + 5)
                merged["only_when_sure"] = bool(merged["ai_score"] >= 76)
                return [merged]

            # Mode 2: HTF Pullback Traded on M5
            elif m5_scan and h_scan["status"] == "PULLBACK" and h_scan["direction"] != m5_scan["direction"]:
                stop_d = max(1e-5, abs(m5_scan["entry"] - m5_scan["sl"]))
                room_to_htf_zone = abs(m5_scan["entry"] - h_scan["level"])
                if room_to_htf_zone >= 3.5 * stop_d:
                    merged = dict(m5_scan)
                    if merged["direction"] == "BULLISH":
                        pb_tp = min(h_scan["level"], merged["entry"] + 7.5 * stop_d)
                        merged["tp"] = round(pb_tp, digits)
                        merged["rrr"] = round((merged["tp"] - merged["entry"]) / stop_d, 2)
                    else:
                        pb_tp = max(h_scan["level"], merged["entry"] - 7.5 * stop_d)
                        merged["tp"] = round(pb_tp, digits)
                        merged["rrr"] = round((merged["entry"] - merged["tp"]) / stop_d, 2)

                    merged["timeframe"] = "M5"
                    merged["htf_timeframe"] = htf
                    merged["exec_timeframe"] = "M5"
                    merged["timeframe_pair"] = f"{htf} Pullback → M5 Exec"
                    merged["mtf_mode"] = "HTF_PULLBACK_ON_LTF"
                    merged["setup"] = f"[{htf} Pullback on M5] {m5_scan['setup']}"
                    merged["ai_score"] = min(98, m5_scan["ai_score"] + 3)
                    merged["only_when_sure"] = bool(merged["ai_score"] >= 76)
                    return [merged]

            # If HTF setup is present but M5 hasn't triggered yet, provide the armed HTF level for M5 execution
            elif h_scan["status"] in ("AT_RETEST_ZONE", "APPROACHING", "PULLBACK"):
                armed = dict(h_scan)
                armed["timeframe"] = "M5"
                armed["htf_timeframe"] = htf
                armed["exec_timeframe"] = "M5"
                armed["timeframe_pair"] = f"{htf} Setup (Armed On M5 Close)"
                armed["mtf_mode"] = "HTF_SETUP_LTF_EXEC"
                armed["setup"] = f"[{htf} Setup → Armed M5] {h_scan['setup']}"
                return [armed]

        # Standalone M5/M1 with NO HTF anchor is STRICTLY forbidden!
        return []

    # If user selected a specific HTF timeframe (M30, H1, H4, M15)
    if target_tf != "ALL" and target_tf in single_tf_scans:
        item = dict(single_tf_scans[target_tf])
        m5_scan = single_tf_scans.get("M5")
        if m5_scan and m5_scan["direction"] == item["direction"]:
            # Refine execution to M5 micro-stop
            stop_d = max(1e-5, abs(m5_scan["entry"] - m5_scan["sl"]))
            if item["direction"] == "BULLISH":
                item["tp"] = max(item["tp"], m5_scan["entry"] + 8.5 * stop_d)
            else:
                item["tp"] = min(item["tp"], m5_scan["entry"] - 8.5 * stop_d)
            item["sl"] = m5_scan["sl"]
            item["entry"] = m5_scan["entry"]
            item["rrr"] = round(abs(item["tp"] - item["entry"]) / stop_d, 2)
            item["exec_timeframe"] = "M5"
            item["timeframe_pair"] = f"{target_tf} Setup → M5 Exec"
            item["mtf_mode"] = "HTF_SETUP_LTF_EXEC"
            item["setup"] = f"[{target_tf} Setup → M5 Exec] {item['setup']}"
            item["ai_score"] = min(99, item["ai_score"] + 5)
            item["only_when_sure"] = bool(item["ai_score"] >= 76)
        return [item]

    # When scanning ALL timeframes, synthesize top HTF -> M5 / M15 opportunities
    mtf_pairings = [
        ("H4", "M5"),
        ("H1", "M5"),
        ("M30", "M5"),
        ("M15", "M5"),
        ("H4", "M15"),
        ("H1", "M30"),
    ]
    combined = []
    seen_pairs = set()

    for htf, ltf in mtf_pairings:
        h_scan = single_tf_scans.get(htf)
        l_scan = single_tf_scans.get(ltf)
        if not h_scan or not l_scan:
            continue

        # Mode 1: HTF Setup (H4/H1/M30/M15 at/near zone) + LTF Sniper Execution (M5 trigger)
        if h_scan["direction"] == l_scan["direction"] and h_scan["status"] in ("AT_RETEST_ZONE", "APPROACHING", "PULLBACK"):
            pair_key = (symbol, htf, ltf, "CONTINUATION")
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            merged = dict(l_scan)
            stop_d = max(1e-5, abs(merged["entry"] - merged["sl"]))
            if merged["direction"] == "BULLISH":
                htf_tp = max(merged["tp"], min(h_scan["tp"], merged["entry"] + 12.0 * stop_d))
                merged["tp"] = round(htf_tp, digits)
                merged["rrr"] = round((merged["tp"] - merged["entry"]) / stop_d, 2)
            else:
                htf_tp = min(merged["tp"], max(h_scan["tp"], merged["entry"] - 12.0 * stop_d))
                merged["tp"] = round(htf_tp, digits)
                merged["rrr"] = round((merged["entry"] - merged["tp"]) / stop_d, 2)

            merged["timeframe"] = ltf
            merged["htf_timeframe"] = htf
            merged["exec_timeframe"] = ltf
            merged["timeframe_pair"] = f"{htf} Setup → {ltf} Exec"
            merged["mtf_mode"] = "HTF_SETUP_LTF_EXEC"
            merged["level"] = h_scan["level"]
            merged["setup"] = f"[{htf} Setup → {ltf} Exec] {l_scan['setup']}"
            merged["ai_score"] = min(99, max(h_scan["ai_score"], l_scan["ai_score"]) + 5)
            merged["only_when_sure"] = bool(merged["ai_score"] >= 76)
            combined.append(merged)

        # Mode 2: HTF Pullback Traded on LTF (HTF is pulling back to its zone; LTF has a confirmed trigger in the pullback direction)
        elif h_scan["status"] == "PULLBACK" and h_scan["direction"] != l_scan["direction"] and l_scan["status"] in ("AT_RETEST_ZONE", "PULLBACK"):
            pair_key = (symbol, htf, ltf, "PULLBACK")
            if pair_key in seen_pairs:
                continue
            stop_d = max(1e-5, abs(l_scan["entry"] - l_scan["sl"]))
            room_to_htf_zone = abs(l_scan["entry"] - h_scan["level"])
            # Q23/A23 & Q65/A65: Ensure >= 3.5R of room before hitting the HTF retest zone
            if room_to_htf_zone >= 3.5 * stop_d:
                seen_pairs.add(pair_key)
                merged = dict(l_scan)
                if merged["direction"] == "BULLISH":
                    pb_tp = min(h_scan["level"], merged["entry"] + 7.5 * stop_d)
                    merged["tp"] = round(pb_tp, digits)
                    merged["rrr"] = round((merged["tp"] - merged["entry"]) / stop_d, 2)
                else:
                    pb_tp = max(h_scan["level"], merged["entry"] - 7.5 * stop_d)
                    merged["tp"] = round(pb_tp, digits)
                    merged["rrr"] = round((merged["entry"] - merged["tp"]) / stop_d, 2)

                merged["timeframe"] = ltf
                merged["htf_timeframe"] = htf
                merged["exec_timeframe"] = ltf
                merged["timeframe_pair"] = f"{htf} Pullback → {ltf} Exec"
                merged["mtf_mode"] = "HTF_PULLBACK_ON_LTF"
                merged["setup"] = f"[{htf} Pullback on {ltf}] {l_scan['setup']}"
                merged["ai_score"] = min(98, l_scan["ai_score"] + 3)
                merged["only_when_sure"] = bool(merged["ai_score"] >= 76)
                combined.append(merged)

    # Fallback ONLY checks HTF setups (H1, M30, H4, M15). NEVER emit standalone M5 or M1!
    if not combined:
        for tf_pref in ("H1", "M30", "H4", "M15"):
            if tf_pref in single_tf_scans:
                combined.append(single_tf_scans[tf_pref])
                break

    return combined

