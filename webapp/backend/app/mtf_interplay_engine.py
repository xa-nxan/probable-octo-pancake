"""
Multi-Timeframe Fractal Interplay Engine (HTF Power & LTF Conviction)
Encodes the Masterclass 100-Questions, 3 Price Action Lessons, and the 4 Market States:
  - STATE 1: RANGE (Box Boundary Rotation — Q3, Q13, Q70; never trade mid-range)
  - STATE 2: BREAKOUT (Impulse Displacement >= 1.0 ATR — Q6, Q15, Q24; alert only, never chase!)
  - STATE 3: RETEST (Pullback to Last Broken HH/HL/LH/LL Closure Level — Q5, Q8, Q20, Q31, Q79, Q93)
  - STATE 4: CONTINUATION (Trend Staircase HH/HL or LL/LH + Retest Pyramiding — Q9, Q12, Q18, Q24, Q31)

Hierarchy:
  1. H4, H1 & M30: Master Structure & 4-State Classifier (HH, HL, LH, LL, Closure Level, Obstacle #1)
  2. M15: Two-Sided Zone Arrival Box + Counter-Trend Exhaustion Gatekeeper (Q2, Q8, Q10, Q98)
  3. M5: Sniper Break-of-Structure (BOS) Trigger & Level-3 Protected Stop Loss (Q6, Q7, Q31, Q79)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

try:
    from app.backtest_engine import _get_symbol_profile
except ImportError:
    try:
        from webapp.backend.app.backtest_engine import _get_symbol_profile
    except ImportError:
        from backtest_engine import _get_symbol_profile

try:
    from app.train_sniper_ml_model import SniperPredictor
except ImportError:
    try:
        from webapp.backend.app.train_sniper_ml_model import SniperPredictor
    except ImportError:
        from train_sniper_ml_model import SniperPredictor

_sniper_predictor = SniperPredictor()


# Structural Stop Loss, Target Bounds & 60-Day Empirical 100-Questions Calibration per Symbol Profile
# FX (smooth random-walk, M5 P99/Median=2.05x) vs SFX (Poisson jump-diffusion spikes, M5 P99/Median=4.05x-4.13x)
STRUCTURAL_BOUNDS = {
    'SFX_Vol_20': {
        'min_sl_pts': 110.0, 'max_sl_pts': 350.0, 'default_tp_pts': 750.0, 'max_risk_usd': 3.50,
        'zone_box_atr': 0.42, 'min_wick_ratio': 0.22, 'sl_atr_buf': 0.22, 'min_obs1_r': 1.25
    },
    'FX_Vol_20': {
        'min_sl_pts': 150.0, 'max_sl_pts': 500.0, 'default_tp_pts': 1100.0, 'max_risk_usd': 5.00,
        'zone_box_atr': 0.35, 'min_wick_ratio': 0.16, 'sl_atr_buf': 0.16, 'min_obs1_r': 1.15
    },
    'SFX_Vol_40': {
        'min_sl_pts': 420.0, 'max_sl_pts': 1250.0, 'default_tp_pts': 4500.0, 'max_risk_usd': 12.50,
        'zone_box_atr': 0.42, 'min_wick_ratio': 0.22, 'sl_atr_buf': 0.22, 'min_obs1_r': 1.25
    },
    'FX_Vol_40': {
        'min_sl_pts': 420.0, 'max_sl_pts': 1250.0, 'default_tp_pts': 4500.0, 'max_risk_usd': 12.50,
        'zone_box_atr': 0.35, 'min_wick_ratio': 0.16, 'sl_atr_buf': 0.16, 'min_obs1_r': 1.15
    },
}


def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < 2:
        return 50.0
    highs = df['high'].astype(float).values
    lows = df['low'].astype(float).values
    closes = df['close'].astype(float).values
    tr = np.maximum(
        highs - lows,
        np.maximum(
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1))
        )
    )
    tr[0] = highs[0] - lows[0]
    return float(pd.Series(tr).rolling(period).mean().bfill().iloc[-1])


def analyze_structure_and_4states(df: pd.DataFrame, curr_price: float) -> Dict[str, Any]:
    """
    Deterministic 100-Questions Swing Structure & 4-State Classifier:
    1. Extracts fractal Swing Highs (HH / LH) and Swing Lows (HL / LL) with both
       Wick Tip and Candle Closure Level (Q6, Q8, Q79).
    2. Identifies the LAST broken structure zone (Q5, Q20, Q24) and Obstacle #1
       (Breakout HH / Breakout LL — Q16, Q93).
    3. Classifies market into one of the 4 States:
       - RANGE (State 1)
       - BREAKOUT (State 2)
       - RETEST (State 3)
       - CONTINUATION (State 4)
       - NO_TRADE (when mid-air or conflicting)
    """
    if df is None or len(df) < 24:
        return {
            'state': 'NO_TRADE',
            'direction': None,
            'trend_bias': 'NEUTRAL',
            'broken_level': curr_price,
            'broken_wick': curr_price,
            'obstacle_1': curr_price,
            'structural_tp': curr_price,
            'sl_anchor': curr_price,
            'touches': 1,
            'protected_wick': False,
            'hl_lh_respected': False,
            'atr': 100.0,
            'swing_high': curr_price,
            'swing_low': curr_price,
            'last_swing_label': 'NONE',
            'setup_name': 'NO_SETUP_ACTIVE',
            'q_rules_passed': []
        }

    highs = df['high'].astype(float).values
    lows = df['low'].astype(float).values
    opens = df['open'].astype(float).values
    closes = df['close'].astype(float).values
    body_hi = np.maximum(opens, closes)
    body_lo = np.minimum(opens, closes)
    atr = max(1e-5, calculate_atr(df, 14))
    n = len(df)

    # 1. Extract confirmed fractal pivots (window=2 on each side, zero lookahead beyond n-2)
    w = 2
    pivots_hi = []  # (idx, wick_hi, closure_hi)
    pivots_lo = []  # (idx, wick_lo, closure_lo)
    for i in range(w, n - w):
        if highs[i] == np.max(highs[i - w:i + w + 1]):
            pivots_hi.append((i, float(highs[i]), float(body_hi[i])))
        if lows[i] == np.min(lows[i - w:i + w + 1]):
            pivots_lo.append((i, float(lows[i]), float(body_lo[i])))

    sw_hi_24 = float(np.max(highs[-min(30, n):]))
    sw_lo_24 = float(np.min(lows[-min(30, n):]))
    span_24 = sw_hi_24 - sw_lo_24

    # Label HH / LH and HL / LL
    hh_count = sum(1 for k in range(1, len(pivots_hi[-4:])) if pivots_hi[-4:][k][1] > pivots_hi[-4:][k - 1][1])
    lh_count = sum(1 for k in range(1, len(pivots_hi[-4:])) if pivots_hi[-4:][k][1] < pivots_hi[-4:][k - 1][1])
    hl_count = sum(1 for k in range(1, len(pivots_lo[-4:])) if pivots_lo[-4:][k][1] > pivots_lo[-4:][k - 1][1])
    ll_count = sum(1 for k in range(1, len(pivots_lo[-4:])) if pivots_lo[-4:][k][1] < pivots_lo[-4:][k - 1][1])

    is_uptrend_structure = (hh_count >= 1 and hl_count >= 1) and (closes[-1] >= np.mean(closes[-20:]))
    is_downtrend_structure = (ll_count >= 1 and lh_count >= 1) and (closes[-1] <= np.mean(closes[-20:]))

    # 2. Scan for the LAST Broken Structure Zone (Q5, Q20, Q24)
    # Bullish Break: candle body closed above a recent Swing High (HH or Upper LH)
    bull_broken = None
    for idx_p, wick_p, clos_p in reversed(pivots_hi[-8:]):
        if idx_p >= n - 2:
            continue
        post_closes = closes[idx_p + 1:]
        post_highs = highs[idx_p + 1:]
        post_lows = lows[idx_p + 1:]
        if len(post_closes) == 0:
            continue
        peak_after = float(np.max(post_highs))
        # Q6/Q24: Must have broken above closure level with displacement >= 0.55 ATR
        if peak_after >= clos_p + 0.55 * atr and np.any(post_closes > clos_p):
            break_offset = int(np.argmax(post_closes > clos_p))
            break_idx = idx_p + 1 + break_offset
            # Q7/Q19/Lesson 2: Structure is INVALIDATED (reclaimed) if any subsequent candle body closes below clos_p - 0.12*ATR
            # AND the latest closed candle (closes[-2]) must still be holding above the broken closure level!
            after_break_closes = closes[break_idx:]
            if np.min(after_break_closes) >= clos_p - 0.12 * atr and closes[-2] >= clos_p - 0.05 * atr:
                # Count retest touches after peak and check Touch #2 Protected Wick
                peak_idx = idx_p + 1 + int(np.argmax(post_highs))
                retest_bars_lows = lows[peak_idx:] if peak_idx < n else lows[-3:]
                retest_wick_low = float(np.min(retest_bars_lows))
                touches = sum(1 for lv in retest_bars_lows if lv <= wick_p + 0.35 * atr)
                protected_wick = (touches >= 2) and (lows[-2] >= retest_wick_low) and (lows[-1] >= retest_wick_low)
                bull_broken = {
                    'pivot_idx': idx_p,
                    'break_idx': break_idx,
                    'broken_level': clos_p,
                    'broken_wick': wick_p,
                    'obstacle_1': peak_after,
                    'retest_wick_low': retest_wick_low,
                    'touches': max(1, int(touches)),
                    'protected_wick': bool(protected_wick),
                }
                break

    # Bearish Break: candle body closed below a recent Swing Low (LL or HL)
    bear_broken = None
    for idx_p, wick_p, clos_p in reversed(pivots_lo[-8:]):
        if idx_p >= n - 2:
            continue
        post_closes = closes[idx_p + 1:]
        post_lows = lows[idx_p + 1:]
        post_highs = highs[idx_p + 1:]
        if len(post_closes) == 0:
            continue
        trough_after = float(np.min(post_lows))
        if trough_after <= clos_p - 0.55 * atr and np.any(post_closes < clos_p):
            break_offset = int(np.argmax(post_closes < clos_p))
            break_idx = idx_p + 1 + break_offset
            # Q7/Q19/Lesson 2: Structure is INVALIDATED (reclaimed) if any subsequent candle body closes above clos_p + 0.12*ATR
            # AND the latest closed candle (closes[-2]) must still be holding below the broken closure level!
            after_break_closes = closes[break_idx:]
            if np.max(after_break_closes) <= clos_p + 0.12 * atr and closes[-2] <= clos_p + 0.05 * atr:
                trough_idx = idx_p + 1 + int(np.argmin(post_lows))
                retest_bars_highs = highs[trough_idx:] if trough_idx < n else highs[-3:]
                retest_wick_high = float(np.max(retest_bars_highs))
                touches = sum(1 for hv in retest_bars_highs if hv >= wick_p - 0.35 * atr)
                protected_wick = (touches >= 2) and (highs[-2] <= retest_wick_high) and (highs[-1] <= retest_wick_high)
                bear_broken = {
                    'pivot_idx': idx_p,
                    'break_idx': break_idx,
                    'broken_level': clos_p,
                    'broken_wick': wick_p,
                    'obstacle_1': trough_after,
                    'retest_wick_high': retest_wick_high,
                    'touches': max(1, int(touches)),
                    'protected_wick': bool(protected_wick),
                }
                break

    # Pick the most recent valid structural break
    active_break = None
    direction = None
    if bull_broken and bear_broken:
        if bull_broken['break_idx'] >= bear_broken['break_idx']:
            active_break = bull_broken
            direction = 'BUY'
        else:
            active_break = bear_broken
            direction = 'SELL'
    elif bull_broken:
        active_break = bull_broken
        direction = 'BUY'
    elif bear_broken:
        active_break = bear_broken
        direction = 'SELL'

    q_rules = []
    state = 'NO_TRADE'
    setup_name = 'NO_SETUP_ACTIVE'
    broken_level = curr_price
    broken_wick = curr_price
    obstacle_1 = curr_price
    sl_anchor = curr_price
    structural_tp = curr_price
    touches = 1
    protected_wick = False

    # Check if we are in a clean bounded Range (State 1)
    is_range_box = (span_24 <= 4.2 * atr) and not (is_uptrend_structure or is_downtrend_structure)

    if active_break is not None and direction == 'BUY':
        broken_level = active_break['broken_level']
        broken_wick = active_break['broken_wick']
        obstacle_1 = active_break['obstacle_1']
        touches = active_break['touches']
        protected_wick = active_break['protected_wick']
        # Level-3 SL anchor: strictly below the retest wick low and the broken level (Q31, Q79, Q93)
        sl_anchor = min(broken_level - 0.15 * atr, active_break['retest_wick_low'])
        # Measured move / Higher High structural target (1:6 to 1:8+ potential)
        wave_height = max(obstacle_1 - sw_lo_24, 3.5 * atr)
        structural_tp = max(obstacle_1 + 0.65 * wave_height, curr_price + 4.5 * atr)

        # Distance from broken zone (two-sided!)
        dist_from_zone = abs(curr_price - broken_level)
        room_to_obstacle_1 = obstacle_1 - curr_price

        # Are we chasing at the top near Obstacle #1 without a pullback? (State 2: BREAKOUT)
        if curr_price > broken_wick + 0.45 * atr or room_to_obstacle_1 < 0.35 * atr:
            state = 'BREAKOUT'
            setup_name = 'STATE_2_BULLISH_BREAKOUT_AWAITING_RETEST'
            q_rules = ['Q6_A6', 'Q15_A15', 'Q16_A16']
        # Are we inside the two-sided Retest Zone around the broken HH/LH? (State 3 or 4)
        elif (broken_level - 0.40 * atr) <= curr_price <= (broken_wick + 0.45 * atr):
            if is_uptrend_structure and hh_count >= 2:
                state = 'CONTINUATION'
                setup_name = 'STATE_4_BULLISH_CONTINUATION_RETEST'
                q_rules = ['Q5_A5', 'Q8_A8', 'Q12_A12', 'Q18_A18', 'Q79_A79', 'Q93_A93']
            else:
                state = 'RETEST'
                setup_name = 'STATE_3_BULLISH_BREAK_AND_RETEST'
                q_rules = ['Q5_A5', 'Q8_A8', 'Q9_A9', 'Q20_A20', 'Q79_A79', 'Q93_A93']
        else:
            state = 'NO_TRADE'
            setup_name = 'MID_STRUCTURE_WAIT'

    elif active_break is not None and direction == 'SELL':
        broken_level = active_break['broken_level']
        broken_wick = active_break['broken_wick']
        obstacle_1 = active_break['obstacle_1']
        touches = active_break['touches']
        protected_wick = active_break['protected_wick']
        # Level-3 SL anchor: strictly above the retest wick high and the broken level (Q31, Q79, Q93)
        sl_anchor = max(broken_level + 0.15 * atr, active_break['retest_wick_high'])
        wave_height = max(sw_hi_24 - obstacle_1, 3.5 * atr)
        structural_tp = min(obstacle_1 - 0.65 * wave_height, curr_price - 4.5 * atr)

        room_to_obstacle_1 = curr_price - obstacle_1

        # Are we chasing at the bottom near Obstacle #1 without a pullback? (State 2: BREAKOUT)
        if curr_price < broken_wick - 0.45 * atr or room_to_obstacle_1 < 0.35 * atr:
            state = 'BREAKOUT'
            setup_name = 'STATE_2_BEARISH_BREAKDOWN_AWAITING_RETEST'
            q_rules = ['Q6_A6', 'Q15_A15', 'Q16_A16']
        # Are we inside the two-sided Retest Zone around the broken LL/HL? (State 3 or 4)
        elif (broken_wick - 0.45 * atr) <= curr_price <= (broken_level + 0.40 * atr):
            if is_downtrend_structure and ll_count >= 2:
                state = 'CONTINUATION'
                setup_name = 'STATE_4_BEARISH_CONTINUATION_RETEST'
                q_rules = ['Q5_A5', 'Q10_A10', 'Q24_A24', 'Q31_A31', 'Q79_A79', 'Q93_A93']
            else:
                state = 'RETEST'
                setup_name = 'STATE_3_BEARISH_BREAK_AND_RETEST'
                q_rules = ['Q5_A5', 'Q10_A10', 'Q13_A13', 'Q24_A24', 'Q79_A79', 'Q93_A93']
        else:
            state = 'NO_TRADE'
            setup_name = 'MID_STRUCTURE_WAIT'

    elif is_range_box:
        # State 1: RANGE — only trade outer 22% boundaries, never middle 56% (Q3)
        if curr_price >= sw_hi_24 - 0.22 * span_24:
            state = 'RANGE'
            direction = 'SELL'
            broken_level = sw_hi_24
            broken_wick = sw_hi_24
            obstacle_1 = sw_hi_24 - 0.50 * span_24
            sl_anchor = sw_hi_24
            structural_tp = sw_lo_24 + 0.10 * span_24
            touches = sum(1 for hv in highs[-24:] if hv >= sw_hi_24 - 0.15 * atr)
            protected_wick = (touches >= 2) and (highs[-1] <= sw_hi_24)
            setup_name = 'STATE_1_RANGE_CEILING_ROTATION'
            q_rules = ['Q3_A3', 'Q13_A13', 'Q70_A70', 'Q79_A79']
        elif curr_price <= sw_lo_24 + 0.22 * span_24:
            state = 'RANGE'
            direction = 'BUY'
            broken_level = sw_lo_24
            broken_wick = sw_lo_24
            obstacle_1 = sw_lo_24 + 0.50 * span_24
            sl_anchor = sw_lo_24
            structural_tp = sw_hi_24 - 0.10 * span_24
            touches = sum(1 for lv in lows[-24:] if lv <= sw_lo_24 + 0.15 * atr)
            protected_wick = (touches >= 2) and (lows[-1] >= sw_lo_24)
            setup_name = 'STATE_1_RANGE_FLOOR_ROTATION'
            q_rules = ['Q3_A3', 'Q13_A13', 'Q70_A70', 'Q79_A79']

    trend_bias = 'BULLISH' if (direction == 'BUY' or is_uptrend_structure) else ('BEARISH' if (direction == 'SELL' or is_downtrend_structure) else 'NEUTRAL')
    hl_lh_respected = is_uptrend_structure if direction == 'BUY' else (is_downtrend_structure if direction == 'SELL' else False)

    return {
        'state': state,
        'direction': direction,
        'trend_bias': trend_bias,
        'broken_level': float(broken_level),
        'broken_wick': float(broken_wick),
        'obstacle_1': float(obstacle_1),
        'structural_tp': float(structural_tp),
        'sl_anchor': float(sl_anchor),
        'touches': int(touches),
        'protected_wick': bool(protected_wick),
        'hl_lh_respected': bool(hl_lh_respected),
        'atr': float(atr),
        'swing_high': float(sw_hi_24),
        'swing_low': float(sw_lo_24),
        'setup_name': setup_name,
        'q_rules_passed': q_rules
    }


def analyze_mtf_fractal_interplay(
    symbol: str,
    tf_dfs: Dict[str, pd.DataFrame],
    curr_price: Optional[float] = None,
    digits: int = 2
) -> Dict[str, Any]:
    """
    Synthesizes H4, H1, M30, M15, and M5 simultaneously using the 4 Market States
    (RANGE, BREAKOUT, RETEST, CONTINUATION) and the 100 Masterclass Questions.
    """
    prof = _get_symbol_profile(symbol)
    bounds = STRUCTURAL_BOUNDS.get(symbol, {
        'min_sl_pts': 150.0, 'max_sl_pts': 600.0, 'default_tp_pts': 1200.0, 'max_risk_usd': 6.00
    })

    df_m5 = tf_dfs.get('M5')
    if df_m5 is not None and len(df_m5) > 0 and curr_price is None:
        curr_price = float(df_m5['close'].iloc[-1])
    elif curr_price is None:
        curr_price = 0.0
    curr_price = round(curr_price, digits)

    df_h4 = tf_dfs.get('H4')
    df_h1 = tf_dfs.get('H1')
    df_m30 = tf_dfs.get('M30')
    df_m15 = tf_dfs.get('M15')

    # -------------------------------------------------------------
    # TIER 1, 2 & 3: H4, H1, M30 4-STATE STRUCTURE ANALYSIS
    # Setups originate strictly from M30, H1, and H4!
    # -------------------------------------------------------------
    s_h4 = analyze_structure_and_4states(df_h4, curr_price)
    s_h1 = analyze_structure_and_4states(df_h1, curr_price)
    s_m30 = analyze_structure_and_4states(df_m30, curr_price)
    s_m15 = analyze_structure_and_4states(df_m15, curr_price)

    # Select primary tradeable setup across M30, H1, H4, plus H1+M30-Shielded M15 Pro-Trend Continuation
    # Must NOT conflict with H4/H1 macro trend (HTF Regime Shift Shield: never trade against H1 trend bias!)
    chosen = None
    chosen_tf = 'H4'
    # NOTE: M15 tier disabled for live trading — honest (no look-ahead) 60d audit shows negative expectancy (E[R] -0.05 to -0.14).
    # Re-enable only after it proves positive expectancy on out-of-sample data.
    ENABLE_M15_TIER = False
    tier_candidates = [('M30', s_m30), ('H1', s_h1), ('H4', s_h4)] + ([('M15', s_m15)] if ENABLE_M15_TIER else [])
    for tf_label, cand in tier_candidates:
        if cand['state'] in ('RETEST', 'CONTINUATION', 'RANGE'):
            # Enforce Q4 / Q12 / Q31 Macro Trend Confluence: do not fight an active H4 RETEST/CONTINUATION
            if s_h4['state'] in ('RETEST', 'CONTINUATION') and s_h4['direction'] and cand['direction'] != s_h4['direction']:
                continue
            # HTF Regime Shift Shield on M30: M30 cannot trade against H1 trend bias
            if tf_label == 'M30':
                if cand['direction'] == 'SELL' and s_h1['trend_bias'] == 'BULLISH':
                    continue
                if cand['direction'] == 'BUY' and s_h1['trend_bias'] == 'BEARISH':
                    continue
            # Lower-Timeframe (M15 -> M5) Fractal Scaling Law: only allow M15 RETEST/CONTINUATION when BOTH H1 and M30 are aligned!
            if tf_label == 'M15':
                if cand['state'] not in ('RETEST', 'CONTINUATION'):
                    continue
                req_bias = 'BULLISH' if cand['direction'] == 'BUY' else 'BEARISH'
                if s_h1['trend_bias'] != req_bias or s_m30['trend_bias'] != req_bias:
                    continue
                if s_h1['state'] in ('RETEST', 'CONTINUATION') and s_h1['direction'] and s_h1['direction'] != cand['direction']:
                    continue
            chosen = cand
            chosen_tf = tf_label
            break

    # If none is in RETEST/CONTINUATION/RANGE, check if one is in BREAKOUT (alert state)
    if chosen is None:
        for tf_label, cand in [('M30', s_m30), ('H1', s_h1), ('H4', s_h4)]:
            if cand['state'] == 'BREAKOUT':
                chosen = cand
                chosen_tf = tf_label
                break

    active_state = chosen['state'] if chosen else 'NO_TRADE'
    active_htf_setup = f"{chosen_tf}_{chosen['setup_name']}" if (chosen and chosen['state'] != 'NO_TRADE') else None
    setup_direction = chosen['direction'] if chosen else None
    setup_target_level = chosen['broken_level'] if chosen else curr_price
    setup_obstacle_1 = chosen['obstacle_1'] if chosen else curr_price
    setup_sl_anchor = chosen['sl_anchor'] if chosen else curr_price
    setup_touches = chosen['touches'] if chosen else 1
    setup_protected_wick = chosen['protected_wick'] if chosen else False
    setup_q_rules = chosen['q_rules_passed'] if chosen else []

    # Macro target: use largest aligned structural target across M30 / H1 / H4 (stretching winners like Images 1-3!)
    if setup_direction == 'BUY':
        candidates_tp = [x['structural_tp'] for x in (s_m30, s_h1, s_h4) if x['direction'] == 'BUY' and x['structural_tp'] > curr_price]
        setup_tp = round(max(candidates_tp) if candidates_tp else (curr_price + bounds['default_tp_pts']), digits)
    elif setup_direction == 'SELL':
        candidates_tp = [x['structural_tp'] for x in (s_m30, s_h1, s_h4) if x['direction'] == 'SELL' and x['structural_tp'] < curr_price]
        setup_tp = round(min(candidates_tp) if candidates_tp else (curr_price - bounds['default_tp_pts']), digits)
    else:
        setup_tp = curr_price

    h4_analysis = {
        'timeframe': 'H4',
        'bias': s_h4['trend_bias'],
        'market_state': s_h4['state'],
        'prediction_move': f"H4 {s_h4['trend_bias']} ({s_h4['state']}: {s_h4['setup_name']})",
        'macro_target': round(s_h4['structural_tp'], digits),
        'swing_high': round(s_h4['swing_high'], digits),
        'swing_low': round(s_h4['swing_low'], digits),
        'structure': f"H4 {s_h4['state']} ({s_h4['trend_bias']})",
        'atr': round(s_h4['atr'], digits),
        'htf_setup_type': s_h4['setup_name']
    }

    h1_pullback_bars = 0
    if df_h1 is not None and len(df_h1) >= 5 and setup_direction:
        h1_c = df_h1['close'].astype(float).values
        h1_o = df_h1['open'].astype(float).values
        h1_pullback_bars = sum(1 for i in range(-3, 0) if (h1_c[i] > h1_o[i] if setup_direction == 'SELL' else h1_c[i] < h1_o[i]))

    h1_analysis = {
        'timeframe': 'H1',
        'bias': s_h1['trend_bias'],
        'market_state': s_h1['state'],
        'broken_level': round(setup_target_level, digits),
        'level_role': f"{chosen_tf} Broken Structure ({active_state})" if active_htf_setup else 'Awaiting Break & Retest',
        'pullback_behavior': f"H1 Pullback: {h1_pullback_bars} counter-bars testing zone",
        'status': s_h1['state'],
        'structural_tp': round(setup_tp, digits),
        'atr': round(s_h1['atr'], digits),
        'htf_setup_type': active_htf_setup or 'NO_SETUP_ACTIVE'
    }

    m30_analysis = {
        'timeframe': 'M30',
        'market_state': s_m30['state'],
        'phase': f"{active_state} @ {setup_target_level:.2f}" if active_htf_setup else 'IN_BETWEEN_LEVELS',
        'pullback_candles_count': h1_pullback_bars * 2,
        'structural_target': round(setup_tp, digits),
        'status': s_m30['setup_name'],
        'atr': round(s_m30['atr'], digits),
        'narrative': f"M30 State: {s_m30['state']} | Broken Zone: {setup_target_level:.2f} | Obstacle #1: {setup_obstacle_1:.2f} | Target: {setup_tp:.2f}"
    }

    # -------------------------------------------------------------
    # TIER 4: M15 TWO-SIDED ZONE ARRIVAL & EXHAUSTION GATEKEEPER
    # Fixes the one-sided >= / <= bug that bought ceilings & sold floors!
    # -------------------------------------------------------------
    m15_analysis = {
        'timeframe': 'M15',
        'status': 'WAIT_FOR_HTF_ARRIVAL',
        'zone_tested': False,
        'exhaustion_confirmed': False,
        'touches': setup_touches,
        'protected_wick': setup_protected_wick,
        'upper_wick_ratio': 0.0,
        'lower_wick_ratio': 0.0,
        'atr': 22.0
    }

    m15_zone_arrived = False
    m15_exhaustion_confirmed = False
    m15_opposing_expansion = False
    m15_high_val = curr_price
    m15_low_val = curr_price
    m15_retest_extreme = curr_price

    if df_m15 is not None and len(df_m15) >= 6 and active_htf_setup:
        m15_atr = calculate_atr(df_m15, 14)
        m15_analysis['atr'] = round(m15_atr, digits)
        # Q6/Q8/Lesson 1: Evaluate the LAST CLOSED M15 candle (iloc[-2]) for rejection confirmation,
        # while checking iloc[-1] to ensure no opposing mid-bar breakdown is occurring!
        closed_m15 = df_m15.iloc[-2]
        live_m15 = df_m15.iloc[-1]
        m15_high_val = float(closed_m15['high'])
        m15_low_val = float(closed_m15['low'])
        m15_open = float(closed_m15['open'])
        m15_close = float(closed_m15['close'])

        m15_rng = max(1e-5, m15_high_val - m15_low_val)
        m15_u_wick = m15_high_val - max(m15_open, m15_close)
        m15_l_wick = min(m15_open, m15_close) - m15_low_val
        m15_u_ratio = m15_u_wick / m15_rng
        m15_l_ratio = m15_l_wick / m15_rng

        m15_analysis['upper_wick_ratio'] = round(m15_u_ratio, 2)
        m15_analysis['lower_wick_ratio'] = round(m15_l_ratio, 2)

        # Two-sided zone box around the HTF broken level (Q8, Q15, Q80) calibrated per index (60d empirical)
        z_mult = float(bounds.get('zone_box_atr', 0.38))
        min_w_ratio = float(bounds.get('min_wick_ratio', 0.20))
        zone_box = z_mult * max(s_m30['atr'], m15_atr * 1.4)

        m15_highs_6 = df_m15['high'].astype(float).values[-6:]
        m15_lows_6 = df_m15['low'].astype(float).values[-6:]

        if setup_direction == 'SELL':
            m15_retest_extreme = float(np.max(m15_highs_6))
            m15_touches_in_zone = sum(1 for hv in m15_highs_6 if hv >= setup_target_level - zone_box)
            # TWO-SIDED CHECK: M15 high touched up into the zone AND current price is near the zone (NOT 450 pts away!)
            m15_zone_arrived = (
                active_state in ('RETEST', 'CONTINUATION', 'RANGE')
                and (m15_retest_extreme >= setup_target_level - zone_box)
                and (abs(curr_price - setup_target_level) <= zone_box * 0.95)
            )
            # Closed M15 bar must show upper wick rejection or bearish close respecting the broken level,
            # AND for SFX jump-diffusion indices, require >= 2 M15/HTF touches (Protected Wick Q9/Lesson 3)!
            touch_2_ok = (setup_touches >= 2 or m15_touches_in_zone >= 2) if 'SFX' in symbol else True
            m15_exhaustion_confirmed = (
                touch_2_ok
                and ((m15_u_ratio >= min_w_ratio) or (m15_close < m15_open and m15_close <= setup_target_level + 0.10 * zone_box))
                and (float(live_m15['high']) <= m15_retest_extreme)
            )
            live_rng = max(1e-5, float(live_m15['high']) - float(live_m15['low']))
            m15_opposing_expansion = (float(live_m15['close']) > float(live_m15['open'])) and ((float(live_m15['close']) - float(live_m15['open'])) > 0.60 * live_rng)

        elif setup_direction == 'BUY':
            m15_retest_extreme = float(np.min(m15_lows_6))
            m15_touches_in_zone = sum(1 for lv in m15_lows_6 if lv <= setup_target_level + zone_box)
            # TWO-SIDED CHECK: M15 low touched down into the zone AND current price is near the zone (NOT 450 pts above!)
            m15_zone_arrived = (
                active_state in ('RETEST', 'CONTINUATION', 'RANGE')
                and (m15_retest_extreme <= setup_target_level + zone_box)
                and (abs(curr_price - setup_target_level) <= zone_box * 0.95)
            )
            touch_2_ok = (setup_touches >= 2 or m15_touches_in_zone >= 2) if 'SFX' in symbol else True
            m15_exhaustion_confirmed = (
                touch_2_ok
                and ((m15_l_ratio >= min_w_ratio) or (m15_close > m15_open and m15_close >= setup_target_level - 0.10 * zone_box))
                and (float(live_m15['low']) >= m15_retest_extreme)
            )
            live_rng = max(1e-5, float(live_m15['high']) - float(live_m15['low']))
            m15_opposing_expansion = (float(live_m15['close']) < float(live_m15['open'])) and ((float(live_m15['open']) - float(live_m15['close'])) > 0.60 * live_rng)

        m15_analysis['zone_tested'] = m15_zone_arrived
        m15_analysis['exhaustion_confirmed'] = m15_exhaustion_confirmed
        if active_state == 'BREAKOUT':
            m15_analysis['status'] = f"BREAKOUT_EXPANSION (Do Not Chase — Wait for Retest @ {setup_target_level:.2f})"
        elif not m15_zone_arrived:
            m15_analysis['status'] = f"AWAITING_RETEST_BOX (Target Zone: {setup_target_level:.2f})"
        elif m15_opposing_expansion:
            m15_analysis['status'] = "OPPOSING_MOMENTUM_BLOCKED (Q98 Anti-Suicide)"
        elif m15_exhaustion_confirmed:
            m15_analysis['status'] = "REJECTION_CONFIRMED (Ready for M5 BOS Trigger)"
        else:
            m15_analysis['status'] = "AT_RETEST_ZONE_WAITING_WICK"

    # Anti-Suicide Counter-Momentum Filter (Q98)
    has_opposite_momentum = m15_opposing_expansion
    if df_m5 is not None and len(df_m5) >= 5 and active_htf_setup:
        m5_closes = df_m5['close'].astype(float).values
        m5_opens = df_m5['open'].astype(float).values
        if setup_direction == 'SELL':
            if sum(1 for i in range(1, 4) if m5_closes[-i] > m5_opens[-i]) >= 3:
                has_opposite_momentum = True
        elif setup_direction == 'BUY':
            if sum(1 for i in range(1, 4) if m5_closes[-i] < m5_opens[-i]) >= 3:
                has_opposite_momentum = True

    # -------------------------------------------------------------
    # TIER 5: M5 SNIPER BOS TRIGGER, LEVEL-3 SL & OBSTACLE #1 CHECK
    # -------------------------------------------------------------
    m5_analysis = {
        'timeframe': 'M5',
        'trigger_status': 'WAIT_FOR_HTF_SETUP',
        'rejection_wick_size': 0.0,
        'rejection_wick_ratio': 0.0,
        'micro_entry': curr_price,
        'micro_sl': curr_price,
        'obstacle_1': round(setup_obstacle_1, digits),
        'stop_dist_pts': bounds['min_sl_pts'],
        'reward_pts': bounds['default_tp_pts'],
        'rrr': 5.0,
        'risk_usd_0_01': round(bounds['min_sl_pts'] * 0.01, 2),
        'reward_usd_0_01': round(bounds['default_tp_pts'] * 0.01, 2),
        'reward_usd_pyramid_0_03': round((bounds['default_tp_pts'] * 0.01) * 2.4, 2),
        'ignition_candle_confirmed': False,
        'atr': 15.0
    }

    m5_fired = False
    obstacle_1_blocked = False

    if df_m5 is not None and len(df_m5) >= 6 and active_htf_setup and setup_direction:
        m5_highs = df_m5['high'].astype(float).values
        m5_lows = df_m5['low'].astype(float).values
        m5_atr = calculate_atr(df_m5, 14)

        # Q6/Q7/Lesson 1: Evaluate the LAST CLOSED M5 bar (iloc[-2]) against iloc[-3] for BOS confirmation,
        # while verifying that the live M5 bar (iloc[-1]) is still holding the breakout direction!
        live_b = df_m5.iloc[-1]
        closed_b = df_m5.iloc[-2]
        prev_closed_b = df_m5.iloc[-3]
        last_rng = max(1e-5, float(closed_b['high']) - float(closed_b['low']))
        upper_wick = float(closed_b['high']) - max(float(closed_b['open']), float(closed_b['close']))
        lower_wick = min(float(closed_b['open']), float(closed_b['close'])) - float(closed_b['low'])
        upper_wick_ratio = upper_wick / last_rng
        lower_wick_ratio = lower_wick / last_rng

        # Scale Level-3 SL ATR buffer by M15/M5 structural volatility so SFX spikes cannot clip stops by 8 points!
        ref_atr_for_sl = max(float(m15_analysis.get('atr', m5_atr)) * 0.65, m5_atr * 1.45)
        sl_atr_buf = float(bounds.get('sl_atr_buf', 0.18)) * ref_atr_for_sl
        min_obs1_r = float(bounds.get('min_obs1_r', 1.15))
        eff_spread = max(prof.get('spread_pad', 10.0), 14.0) + sl_atr_buf

        if setup_direction == 'SELL':
            # Q6/Q7: Closed M5 candle broke below previous M5 candle low AND live price is still holding bearish
            m5_bos = (
                (float(closed_b['close']) < float(prev_closed_b['low']))
                and (float(closed_b['close']) < float(closed_b['open']))
                and (curr_price <= float(closed_b['close']) + 0.15 * m5_atr)
            )
            # Q31/Q79 Level-3 Stop Loss: strictly behind HTF sl_anchor, M15 retest wick, and M5 swing high + spread + index ATR buffer
            m5_recent_high = float(np.max(m5_highs[-6:]))
            sl_ceiling = max(setup_sl_anchor, m15_retest_extreme, m5_recent_high)
            raw_stop_dist = (sl_ceiling + eff_spread) - curr_price
            stop_dist = max(bounds['min_sl_pts'], min(bounds['max_sl_pts'], raw_stop_dist))
            structural_sl = round(curr_price + stop_dist, digits)

            # Q16/Q93 Obstacle #1 Clearance Check: never sell right into the Breakout LL floor!
            room_to_obs1 = curr_price - setup_obstacle_1 if setup_obstacle_1 < curr_price else stop_dist * 2.0
            if room_to_obs1 < min_obs1_r * stop_dist:
                obstacle_1_blocked = True

            reward_dist = max(bounds['default_tp_pts'], abs(curr_price - setup_tp))
            rrr = round(reward_dist / max(1.0, stop_dist), 2)

            m5_fired = (
                m15_zone_arrived
                and m15_exhaustion_confirmed
                and m5_bos
                and not has_opposite_momentum
                and not obstacle_1_blocked
                and (raw_stop_dist <= bounds['max_sl_pts'])
                and (rrr >= 4.5)
            )

            m5_analysis = {
                'timeframe': 'M5',
                'trigger_status': 'SNIPER_SELL_TRIGGERED' if m5_fired else (
                    'BLOCKED_TOO_CLOSE_TO_OBSTACLE_1' if obstacle_1_blocked else (
                        'WAITING_M5_BOS' if (m15_zone_arrived and m15_exhaustion_confirmed) else (
                            'AT_HTF_ZONE_WAITING_M15_WICK' if m15_zone_arrived else 'AWAITING_HTF_RETEST_ZONE'
                        )
                    )
                ),
                'rejection_wick_size': round(upper_wick, digits),
                'rejection_wick_ratio': round(upper_wick_ratio, 2),
                'micro_entry': curr_price,
                'micro_sl': structural_sl,
                'obstacle_1': round(setup_obstacle_1, digits),
                'tp1_obstacle_usd_0_01': round(max(0.0, curr_price - setup_obstacle_1) * 0.01, 2),
                'stop_dist_pts': round(stop_dist, digits),
                'reward_pts': round(reward_dist, digits),
                'rrr': rrr,
                'risk_usd_0_01': round(stop_dist * 0.01, 2),
                'reward_usd_0_01': round(reward_dist * 0.01, 2),
                'reward_usd_pyramid_0_03': round(reward_dist * 0.01 * 2.35, 2),
                'ignition_candle_confirmed': m5_fired,
                'atr': round(m5_atr, digits)
            }

        elif setup_direction == 'BUY':
            # Q6/Q7: Closed M5 candle broke above previous M5 candle high AND live price is still holding bullish
            m5_bos = (
                (float(closed_b['close']) > float(prev_closed_b['high']))
                and (float(closed_b['close']) > float(closed_b['open']))
                and (curr_price >= float(closed_b['close']) - 0.15 * m5_atr)
            )
            m5_recent_low = float(np.min(m5_lows[-6:]))
            sl_floor = min(setup_sl_anchor, m15_retest_extreme, m5_recent_low)
            raw_stop_dist = curr_price - (sl_floor - eff_spread)
            stop_dist = max(bounds['min_sl_pts'], min(bounds['max_sl_pts'], raw_stop_dist))
            structural_sl = round(curr_price - stop_dist, digits)

            # Q16/Q93 Obstacle #1 Clearance Check: never buy right into the Breakout HH ceiling!
            room_to_obs1 = setup_obstacle_1 - curr_price if setup_obstacle_1 > curr_price else stop_dist * 2.0
            if room_to_obs1 < min_obs1_r * stop_dist:
                obstacle_1_blocked = True

            reward_dist = max(bounds['default_tp_pts'], abs(setup_tp - curr_price))
            rrr = round(reward_dist / max(1.0, stop_dist), 2)

            m5_fired = (
                m15_zone_arrived
                and m15_exhaustion_confirmed
                and m5_bos
                and not has_opposite_momentum
                and not obstacle_1_blocked
                and (raw_stop_dist <= bounds['max_sl_pts'])
                and (rrr >= 4.5)
            )

            m5_analysis = {
                'timeframe': 'M5',
                'trigger_status': 'SNIPER_BUY_TRIGGERED' if m5_fired else (
                    'BLOCKED_TOO_CLOSE_TO_OBSTACLE_1' if obstacle_1_blocked else (
                        'WAITING_M5_BOS' if (m15_zone_arrived and m15_exhaustion_confirmed) else (
                            'AT_HTF_ZONE_WAITING_M15_WICK' if m15_zone_arrived else 'AWAITING_HTF_RETEST_ZONE'
                        )
                    )
                ),
                'rejection_wick_size': round(lower_wick, digits),
                'rejection_wick_ratio': round(lower_wick_ratio, 2),
                'micro_entry': curr_price,
                'micro_sl': structural_sl,
                'obstacle_1': round(setup_obstacle_1, digits),
                'tp1_obstacle_usd_0_01': round(max(0.0, setup_obstacle_1 - curr_price) * 0.01, 2),
                'stop_dist_pts': round(stop_dist, digits),
                'reward_pts': round(reward_dist, digits),
                'rrr': rrr,
                'risk_usd_0_01': round(stop_dist * 0.01, 2),
                'reward_usd_0_01': round(reward_dist * 0.01, 2),
                'reward_usd_pyramid_0_03': round(reward_dist * 0.01 * 2.35, 2),
                'ignition_candle_confirmed': m5_fired,
                'atr': round(m5_atr, digits)
            }

    # -------------------------------------------------------------
    # TIER 6: 100-QUESTIONS CONVICTION SCORER & UNIFIED VERDICT
    # No more hardcoded touches=2 or tech_score=85!
    # -------------------------------------------------------------
    computed_tech_score = 50
    if active_state in ('RETEST', 'CONTINUATION'):
        computed_tech_score += 18
    elif active_state == 'RANGE':
        computed_tech_score += 12
    if setup_touches >= 2:
        computed_tech_score += 12
    if setup_protected_wick:
        computed_tech_score += 10
    if m15_zone_arrived and m15_exhaustion_confirmed:
        computed_tech_score += 10
    if not obstacle_1_blocked and m5_analysis['rrr'] >= 5.5:
        computed_tech_score += 8
    computed_tech_score = min(98, computed_tech_score)

    if not active_htf_setup or active_state == 'NO_TRADE':
        action = 'WAIT'
        verdict = "NO_TRADE STATE: Price Mid-Structure (Awaiting 4-State Setup)"
        status_color = '#787b86'
        confidence = 40
        actionable_plan = (
            f"Market State: NO_TRADE (H4 Bias: {h4_analysis['bias']}). "
            f"Price is floating between structural swings without a confirmed Range boundary or Broken HH/HL/LH/LL retest. "
            f"100-Questions Rule (Q3/Q11): Standing strictly aside until a clean Breakout & Retest forms."
        )

    elif active_state == 'BREAKOUT':
        action = 'ARMED_WAIT'
        verdict = f"STATE 2 BREAKOUT: Impulse Active — Waiting for Retest @ {setup_target_level:.2f} (Q15)"
        status_color = '#2962ff'
        confidence = 68
        actionable_plan = (
            f"Market State: BREAKOUT ({active_htf_setup}). "
            f"Price broke structure at {setup_target_level:.2f} and reached Obstacle #1 @ {setup_obstacle_1:.2f}. "
            f"100-Questions Rule (Q15): Never chase a breakout impulse! Waiting for pullback retest of {setup_target_level:.2f}."
        )

    elif obstacle_1_blocked:
        action = 'ARMED_WAIT'
        verdict = f"BLOCKED BY Q16/Q93: Too Close to Obstacle #1 ({setup_obstacle_1:.2f})"
        status_color = '#ff9800'
        confidence = 62
        actionable_plan = (
            f"Active Setup: {active_htf_setup}, but current price ({curr_price:.2f}) is right up against "
            f"Obstacle #1 (Breakout HH/LL @ {setup_obstacle_1:.2f}). "
            f"100-Questions Rule (Q16/Q93): Never enter into the face of Obstacle #1 where Double Tops/Bottoms occur. "
            f"Wait for deeper pullback to {setup_target_level:.2f} or a confirmed breakout & retest above Obstacle #1."
        )

    elif has_opposite_momentum:
        action = 'ARMED_WAIT'
        verdict = "HTF LEVEL REACHED: Awaiting Momentum Exhaustion (Q98 Anti-Suicide)"
        status_color = '#f23645'
        confidence = 65
        actionable_plan = (
            f"Active Setup: {active_htf_setup} @ {setup_target_level:.2f}. "
            f"Opposing candle momentum is still expanding. "
            f"100-Questions Rule (Q2/Q10/Q98): Wait for momentum absorption and rejection wick before entering."
        )

    elif m5_fired:
        effective_touches = max(2, setup_touches) if (active_state in ('RETEST', 'CONTINUATION') and m15_exhaustion_confirmed) else setup_touches
        # Compute live 20-feature 5-Timeframe (H4+H1+M30+M15+M5) vector for the trained LightGBM Ensemble
        h4_align_val = 1 if ((setup_direction == 'BUY' and s_h4['trend_bias'] == 'BULLISH') or (setup_direction == 'SELL' and s_h4['trend_bias'] == 'BEARISH')) else -1
        h1_align_val = 1 if ((setup_direction == 'BUY' and s_h1['trend_bias'] == 'BULLISH') or (setup_direction == 'SELL' and s_h1['trend_bias'] == 'BEARISH')) else -1
        chosen_atr = max(1e-5, float(chosen['atr']) if chosen else s_h1['atr'])
        dist_from_lvl_atr = abs(curr_price - setup_target_level) / chosen_atr
        room_obs1_r_val = abs(setup_obstacle_1 - curr_price) / max(1.0, float(m5_analysis['stop_dist_pts']))
        m15_w_ratio = float(m15_analysis['lower_wick_ratio'] if setup_direction == 'BUY' else m15_analysis['upper_wick_ratio'])
        m5_closed_b = df_m5.iloc[-2] if (df_m5 is not None and len(df_m5) >= 2) else None
        m5_body_rat = (abs(float(m5_closed_b['close']) - float(m5_closed_b['open'])) / max(1e-5, float(m5_closed_b['high']) - float(m5_closed_b['low']))) if m5_closed_b is not None else 0.55

        pred = _sniper_predictor.predict(
            symbol=symbol,
            direction=setup_direction,
            stop_dist_pts=m5_analysis['stop_dist_pts'],
            reward_dist_pts=m5_analysis['reward_pts'],
            touches=effective_touches,
            is_range_boundary=(active_state == 'RANGE'),
            tech_score=computed_tech_score,
            htf_source=chosen_tf,
            market_state=active_state,
            h4_aligned=h4_align_val,
            h1_aligned=h1_align_val,
            htf_reclaim_clean=1,
            brk_displacement_atr=round(abs(setup_obstacle_1 - setup_target_level) / chosen_atr, 3),
            pb_to_brk_vel_ratio=0.62,
            is_touch_2_protected=1 if setup_protected_wick or effective_touches >= 2 else 0,
            dist_from_broken_level_atr=round(dist_from_lvl_atr, 3),
            room_to_obstacle_1_r=round(room_obs1_r_val, 3),
            m15_wick_ratio=round(m15_w_ratio, 3),
            m5_bos_body_ratio=round(m5_body_rat, 3),
            h1_atr=float(s_h1['atr']),
        )

        if not pred['execute']:
            action = 'ARMED_WAIT'
            verdict = f"HTF LEVEL REACHED: Vetoed by 100-Q Sniper AI ({pred['reasons'][0]})"
            status_color = '#ff9800'
            confidence = pred['confidence_pct']
            actionable_plan = (
                f"Active Setup: {active_htf_setup} @ {setup_target_level:.2f}. "
                f"Sniper ML Veto (Win Prob: {pred['win_probability']*100:.0f}%, Tech Score: {computed_tech_score}%). "
                f"Reason: {pred['reasons'][0]}"
            )
        else:
            action = setup_direction
            verdict = f"{active_state} TRIGGERED: {active_htf_setup} ({action} @ {curr_price:.2f})"
            status_color = '#089981' if action == 'BUY' else '#f23645'
            confidence = max(pred['confidence_pct'], computed_tech_score)
            actionable_plan = (
                f"1. 4-STATE SETUP ({active_state}): {active_htf_setup} at Closure Level {setup_target_level:.2f} (Rules: {', '.join(setup_q_rules)}).\n"
                f"2. OBSTACLE #1 CLEARANCE (Q16/Q93): Breakout extreme @ {setup_obstacle_1:.2f} cleared for BE ratchet.\n"
                f"3. M15 + M5 CONVICTION (Q6/Q7/Q8): M15 absorbed pullback into zone; M5 broke pullback structure.\n"
                f"4. LEVEL-3 EXECUTION (Q31/Q79): {action} @ {curr_price:.2f} | Structural SL: {m5_analysis['micro_sl']:.2f} "
                f"(-${m5_analysis['risk_usd_0_01']:.2f} on 0.01 lot) | TP: {setup_tp:.2f} (+${m5_analysis['reward_usd_0_01']:.2f}, 1:{m5_analysis['rrr']:.1f} R:R, +${m5_analysis['reward_usd_pyramid_0_03']:.2f} with Retest Pyramiding)."
            )

    else:
        action = 'ARMED_WAIT'
        if not m15_zone_arrived:
            verdict = f"{active_state} ARMED: Awaiting Retest Arrival @ {setup_target_level:.2f} (Q5/Q80)"
            status_color = '#2962ff'
            confidence = 72
            actionable_plan = (
                f"Active 4-State Setup: {active_htf_setup} @ {setup_target_level:.2f}.\n"
                f"Price is currently at {curr_price:.2f}. Strict 100-Questions discipline (Q15/Q80): "
                f"Wait for price to enter the retest box around {setup_target_level:.2f} before looking for M15/M5 triggers."
            )
        elif not m15_exhaustion_confirmed:
            verdict = f"{active_state} ZONE REACHED: Awaiting M15 Rejection Wick (Q2/Q8/Q10)"
            status_color = '#ffb703'
            confidence = 76
            actionable_plan = (
                f"Active 4-State Setup: {active_htf_setup} @ {setup_target_level:.2f}.\n"
                f"Price is inside the retest zone! Waiting for M15 counter-trend exhaustion (wick >= 25% or closure respecting {setup_target_level:.2f})."
            )
        else:
            verdict = f"M15 REJECTION CONFIRMED: Awaiting M5 BOS Trigger (Q6/Q7)"
            status_color = '#00bcd4'
            confidence = 82
            actionable_plan = (
                f"Active 4-State Setup: {active_htf_setup} @ {setup_target_level:.2f}.\n"
                f"M15 rejection confirmed! Waiting for M5 candle to break pullback structure (BOS) per Q6/Q7."
            )

    predicted_span = abs(setup_tp - curr_price) if setup_tp > 0 else bounds['default_tp_pts']
    step_pts = round(predicted_span / 3.0, digits)
    p1_entry = curr_price
    p2_entry = round(curr_price + (step_pts if setup_direction == 'BUY' else -step_pts), digits)
    p3_entry = round(curr_price + (2.0 * step_pts if setup_direction == 'BUY' else -2.0 * step_pts), digits)

    fractal_magnifier = {
        'htf_setup_name': active_htf_setup or 'NONE',
        'market_state': active_state,
        'h1_predicted_move_pts': round(predicted_span, digits),
        'h1_bars_count': 4,
        'm5_swing_bars_count': 48,
        'stop_breathing_pts': m5_analysis['stop_dist_pts'],
        'pyramid_milestones': {
            'stage_1_base': {'entry': p1_entry, 'status': f'INITIAL_{active_state}_ENTRY', 'lot': 0.01},
            'stage_2_pullback': {'entry': p2_entry, 'status': 'ADD_AFTER_OBSTACLE_1_BE_LOCK', 'lock_p1': 'BE+0.15R', 'lot': 0.01},
            'stage_3_runner': {'entry': p3_entry, 'status': 'ADD_ON_CONTINUATION_RETEST', 'lock_all': 'TRAIL_STRUCTURAL_HL_LH', 'lot': 0.01}
        },
        'philosophy': '4 Market States (Range, Breakout, Retest, Continuation) + 100 Questions (Closure Level, Level-3 SL, Obstacle #1 BE Lock, Retest Pyramiding).'
    }

    interplay_matrix = [
        {
            'relation': 'H4/H1/M30 → 4-State Classifier',
            'rule': f"State: {active_state} ({', '.join(setup_q_rules) if setup_q_rules else 'Q3/Q11 Standby'})",
            'effect': f"Identifies HH/HL/LH/LL swings, Last Broken Zone ({setup_target_level:.2f}), and Obstacle #1 ({setup_obstacle_1:.2f})."
        },
        {
            'relation': 'M15 → Two-Sided Zone Box & Exhaustion',
            'rule': 'Q2 / Q8 / Q10 / Q80 Gatekeeper',
            'effect': f"Blocks mid-air entries and requires M15 arrival at {setup_target_level:.2f} + wick exhaustion."
        },
        {
            'relation': 'M5 → BOS Trigger & Level-3 Stop Loss',
            'rule': 'Q6 / Q7 / Q31 / Q79 Execution',
            'effect': f"Triggers on M5 BOS with Level-3 SL ({m5_analysis['micro_sl']:.2f}, -${m5_analysis['risk_usd_0_01']:.2f}) targeting {setup_tp:.2f} (+${m5_analysis['reward_usd_0_01']:.2f})."
        },
        {
            'relation': 'M15/M5 → Continuation Retest Pyramiding',
            'rule': 'Q16 / Q93 Free-Roll Scaling ($200/Day Engine)',
            'effect': f"Locks BE after Obstacle #1 ({setup_obstacle_1:.2f}) and adds 0.01 tranches on continuation retests (up to +${m5_analysis['reward_usd_pyramid_0_03']:.2f}/wave)."
        }
    ]

    return {
        'status': 'success',
        'symbol': symbol,
        'current_price': curr_price,
        'market_state': active_state,
        'verdict': verdict,
        'action': action,
        'status_color': status_color,
        'confidence': confidence,
        'obstacle_1': m5_analysis.get('obstacle_1', curr_price),
        'q_rules_passed': setup_q_rules,
        'actionable_plan': actionable_plan,
        'fractal_magnifier': fractal_magnifier,
        'timeframes': {
            'H4': h4_analysis,
            'H1': h1_analysis,
            'M30': m30_analysis,
            'M15': m15_analysis,
            'M5': m5_analysis,
        },
        'interplay_matrix': interplay_matrix
    }
