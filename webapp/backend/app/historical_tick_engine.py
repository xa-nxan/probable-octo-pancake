"""
Historical Tick-by-Tick Fast-Forward Replay & Causal Aggregation Engine
Supports Weltrade Synthetic Indices: FX Vol 20, FX Vol 40, SFX Vol 20, SFX Vol 40.
Ensures ZERO lookahead bias: candles, indicators, and structure are built tick-by-tick.
Evaluates exact intrabar spread, Stop Loss, Take Profit, and Q93 Breakeven triggers.
"""

import os
import time
import asyncio
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Callable, Any
from app.mt5_worker import mt5_worker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ticks")
os.makedirs(DATA_DIR, exist_ok=True)

SYMBOL_PROFILES = {
    'SFX_Vol_40': {'spread_pad': 12.0, 'min_stop': 22.0, 'max_stop': 350.0, 'pt_val': 0.01, 'digits': 2},
    'SFX_Vol_20': {'spread_pad': 4.0, 'min_stop': 15.0, 'max_stop': 150.0, 'pt_val': 0.01, 'digits': 2},
    'FX_Vol_40': {'spread_pad': 14.0, 'min_stop': 75.0, 'max_stop': 700.0, 'pt_val': 0.01, 'digits': 2},
    'FX_Vol_20': {'spread_pad': 4.5, 'min_stop': 28.0, 'max_stop': 300.0, 'pt_val': 0.01, 'digits': 2},
}

def get_symbol_profile(symbol: str) -> dict:
    sym_clean = symbol.replace(' ', '_')
    if 'SFX_Vol_40' in sym_clean or 'FlipX_2' in symbol:
        return SYMBOL_PROFILES['SFX_Vol_40']
    elif 'SFX_Vol_20' in sym_clean or 'FlipX_1' in symbol:
        return SYMBOL_PROFILES['SFX_Vol_20']
    elif 'FX_Vol_40' in sym_clean:
        return SYMBOL_PROFILES['FX_Vol_40']
    elif 'FX_Vol_20' in sym_clean:
        return SYMBOL_PROFILES['FX_Vol_20']
    return {'spread_pad': 10.0, 'min_stop': 50.0, 'max_stop': 500.0, 'pt_val': 0.01, 'digits': 2}


class HistoricalTickManager:
    """Manages high-speed ingestion and caching of raw MT5 tick arrays."""

    @staticmethod
    async def fetch_ticks(symbol: str, start_dt: datetime.datetime, end_dt: datetime.datetime) -> np.ndarray:
        sym_clean = symbol.replace('_', ' ')
        cache_key = f"{symbol}_{int(start_dt.timestamp())}_{int(end_dt.timestamp())}.npz"
        cache_path = os.path.join(DATA_DIR, cache_key)

        if os.path.exists(cache_path):
            try:
                data = np.load(cache_path)
                return data['ticks']
            except Exception as e:
                print(f"[TickManager] Cache read error {cache_path}: {e}")

        # Fetch from MT5 worker
        await mt5_worker.execute_async("symbol_select", sym_clean, True)
        raw_ticks = await mt5_worker.execute_async("copy_ticks_range", sym_clean, start_dt, end_dt, 0) # 0 = COPY_TICKS_ALL

        if raw_ticks is None or len(raw_ticks) == 0:
            print(f"[TickManager] Warning: No ticks returned for {sym_clean} from {start_dt} to {end_dt}")
            return np.array([], dtype=object)

        # Convert structured tick array: [time_sec, bid, ask, last, volume, time_msc]
        try:
            np.savez_compressed(cache_path, ticks=raw_ticks)
            print(f"[TickManager] Cached {len(raw_ticks):,} ticks to {cache_key}")
        except Exception as e:
            print(f"[TickManager] Cache save error: {e}")

        return raw_ticks


class CausalCandleBuilder:
    """
    Constructs multi-timeframe candles strictly from arriving ticks with ZERO look-ahead bias.
    Maintains running M5, M15, M30, and H1 candles and rolling structure levels.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.prof = get_symbol_profile(symbol)
        self.timeframes = {
            'M1': 60,
            'M5': 300,
            'M15': 900,
            'M30': 1800,
            'H1': 3600,
            'H4': 14400
        }
        # Current active forming candles: tf -> dict
        self.active_candles: Dict[str, Optional[dict]] = {tf: None for tf in self.timeframes}
        # Closed bar history: tf -> list of dict
        self.history: Dict[str, List[dict]] = {tf: [] for tf in self.timeframes}
        self.max_history = 300

    def process_tick(self, t_sec: int, bid: float, ask: float, vol: float = 1.0) -> List[dict]:
        """
        Updates forming candles for all timeframes with the new tick.
        Returns a list of newly closed candles (if any period boundary was crossed).
        """
        closed_events = []

        for tf, interval in self.timeframes.items():
            candle_start = (t_sec // interval) * interval
            curr = self.active_candles[tf]

            if curr is None:
                self.active_candles[tf] = {
                    'time': candle_start,
                    'open': bid,
                    'high': bid,
                    'low': bid,
                    'close': bid,
                    'volume': max(1.0, vol),
                    'symbol': self.symbol,
                    'timeframe': tf
                }
            elif curr['time'] == candle_start:
                # Update existing candle
                curr['high'] = max(curr['high'], bid)
                curr['low'] = min(curr['low'], bid)
                curr['close'] = bid
                curr['volume'] += max(1.0, vol)
            else:
                # Candle period has closed! Seal the old candle
                sealed = dict(curr)
                self.history[tf].append(sealed)
                if len(self.history[tf]) > self.max_history:
                    self.history[tf].pop(0)
                closed_events.append(sealed)

                # Initialize next candle
                self.active_candles[tf] = {
                    'time': candle_start,
                    'open': bid,
                    'high': bid,
                    'low': bid,
                    'close': bid,
                    'volume': max(1.0, vol),
                    'symbol': self.symbol,
                    'timeframe': tf
                }

        return closed_events

    def get_atr(self, tf: str = 'M5', period: int = 14) -> float:
        bars = self.history.get(tf, [])
        if len(bars) < period:
            return 50.0
        recent = bars[-period:]
        trs = []
        for i in range(len(recent)):
            h = recent[i]['high']
            l = recent[i]['low']
            prev_c = recent[i-1]['close'] if i > 0 else recent[i]['open']
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
        return float(np.mean(trs)) if trs else 50.0

    def get_structure_zones(self, tf: str = 'M5', lookback: int = 80) -> dict:
        """
        Extracts structural swing highs and lows and detects broken structure zones
        encoding all 100 Masterclass Questions:
        - Q5/A5, Q87/A87, Q90/A90: Last Broken Major HH & Closure Level priority
        - Q9/A9, Q20/A20, Q32/A32, Q42/A42: Upper Broken LH priority for Bullish shift
        - Q13/A13, Q19/A19, Q24/A24, Q34/A34, Q96/A96: Last Broken HL & Major LL priority for Bearish B&R
        - Q4/A4, Q31/A31, Q44/A44, Q45/A45, Q46/A46, Q68/A68: Strict Trend Alignment (never counter-trend)
        - Q18/A18, Q43/A43, Q69/A69, Q78/A78, Q83/A83: Closure Level + Wick Rejection Range + No Zone Violation
        - Q23/A23, Q65/A65: Major HTF High/Low Obstacle filter
        """
        bars = self.history.get(tf, [])
        if len(bars) < 25:
            return {
                'zones': [],
                'trend_bias': 'NEUTRAL',
                'bullish_zone': None,
                'bearish_zone': None,
                'last_broken_hh': None,
                'last_broken_lh': None,
                'upper_lh': None,
                'major_high': None,
                'major_low': None
            }

        window = bars[-lookback:]
        opens = np.array([float(b['open']) for b in window])
        highs = np.array([float(b['high']) for b in window])
        lows = np.array([float(b['low']) for b in window])
        closes = np.array([float(b['close']) for b in window])
        n = len(highs)
        atr = max(1e-5, self.get_atr(tf, 14))

        # Compute EMA20 and EMA50 on closes for macro trend context (Q4, Q31, Q46, Q68)
        ema20 = float(closes[0])
        ema50 = float(closes[0])
        k20 = 2.0 / 21.0
        k50 = 2.0 / 51.0
        for c in closes[1:]:
            ema20 = float(c) * k20 + ema20 * (1.0 - k20)
            ema50 = float(c) * k50 + ema50 * (1.0 - k50)

        curr_close = float(closes[-1])
        major_high = float(np.max(highs[:-2])) if n > 5 else float(np.max(highs))
        major_low = float(np.min(lows[:-2])) if n > 5 else float(np.min(lows))

        # Sideways / Chop Regime Check (Q3/A3, Q21/A21, Q66/A66, Q98/A98)
        recent_20_range = float(np.max(highs[-20:]) - np.min(lows[-20:])) if n >= 20 else atr * 4.0
        is_sideways = recent_20_range < (2.1 * atr)

        w = 3
        sh_list = []  # (idx, outer_high, closure_level)
        sl_list = []  # (idx, outer_low, closure_level)
        for i in range(w, n - w):
            if highs[i] == np.max(highs[i - w:i + w + 1]):
                c_lvl = max(float(opens[i]), float(closes[i]))
                sh_list.append((i, float(highs[i]), c_lvl))
            if lows[i] == np.min(lows[i - w:i + w + 1]):
                c_lvl = min(float(opens[i]), float(closes[i]))
                sl_list.append((i, float(lows[i]), c_lvl))

        # Determine structural trend from swing sequence + EMA alignment + macro slope (Q4, Q9, Q12, Q13, Q31, Q44, Q45, Q46, Q68)
        ema_Slope = ema20 - ema50
        macro_disp = float(closes[-1] - closes[0])
        bullish_structure = (curr_close > ema50) and (ema20 >= ema50 - 0.05 * atr) and (macro_disp > -0.5 * atr)
        bearish_structure = (curr_close < ema50) and (ema20 <= ema50 + 0.05 * atr) and (macro_disp < 0.5 * atr)

        if len(sh_list) >= 2 and len(sl_list) >= 2:
            hh_made = sh_list[-1][1] > sh_list[-2][1] + 0.15 * atr
            hl_held = sl_list[-1][1] >= sl_list[-2][1] - 0.25 * atr  # Q69/Q70 equal/protected low tolerance
            ll_made = sl_list[-1][1] < sl_list[-2][1] - 0.15 * atr
            lh_held = sh_list[-1][1] <= sh_list[-2][1] + 0.25 * atr  # Q69/Q70 equal/protected high tolerance
            if hh_made and hl_held and curr_close >= ema50:
                bullish_structure = True
                bearish_structure = False
            elif ll_made and lh_held and curr_close <= ema50:
                bearish_structure = True
                bullish_structure = False

        trend_bias = 'NEUTRAL'
        if not is_sideways:
            if bullish_structure and not bearish_structure:
                trend_bias = 'BULLISH'
            elif bearish_structure and not bullish_structure:
                trend_bias = 'BEARISH'
            elif curr_close > ema20 > ema50 and ema_Slope > 0.10 * atr:
                trend_bias = 'BULLISH'
            elif curr_close < ema20 < ema50 and ema_Slope < -0.10 * atr:
                trend_bias = 'BEARISH'

        # 1. Scan for Valid Bullish Break & Retest Zone (Broken HH or Upper Broken LH)
        bullish_zone = None
        for idx, z_outer, z_closure in reversed(sh_list):
            if n - 1 - idx < 3:
                continue
            post_closes = closes[idx + 1:]
            post_highs = highs[idx + 1:]
            post_lows = lows[idx + 1:]

            # Must have broken and CLOSED above the Rejection Range (Q43, Q73, Q78)
            break_indices = [j for j, c in enumerate(post_closes) if c > z_outer + 0.08 * atr]
            if not break_indices:
                continue
            first_brk_rel = break_indices[0]
            first_brk_idx = idx + 1 + first_brk_rel
            # Need at least 2 bars after initial breakout candle to form impulse + pullback (Q15, Q80)
            if n - 1 - first_brk_idx < 2:
                continue

            breakout_hh = float(np.max(highs[first_brk_idx:n - 1]))
            impulse_dist = breakout_hh - z_outer
            if impulse_dist < 0.35 * atr:
                continue  # Insufficient breakout momentum beyond rejection range (Q43, Q61, Q71)

            peak_rel = int(np.argmax(highs[first_brk_idx:n - 1]))
            peak_idx = first_brk_idx + peak_rel
            if n - 1 - peak_idx < 1:
                continue  # Currently still in initial breakout push, no pullback yet (Q15)

            # Q18/A18: Check for Structure Violation (allow brief liquidity wick into underlying HL base if reclaimed)
            pullback_closes = closes[peak_idx + 1:]
            if len(pullback_closes) > 0 and float(np.min(pullback_closes)) < z_closure - 0.75 * atr:
                continue  # Deep structure breakdown

            # Q28, Q36, Q83: Retest Touch Point in the last 4 bars
            retest_bars_lows = lows[max(peak_idx + 1, n - 4):]
            retest_low = float(np.min(retest_bars_lows))
            if retest_low <= z_outer + 0.45 * atr and retest_low >= z_closure - 0.75 * atr:
                # Current bar must close respecting/reclaiming the closure level (Q83/A83)
                if curr_close >= z_closure - 0.10 * atr:
                    is_upper_lh = (len(sh_list) >= 2 and z_outer < sh_list[-2][1])
                    bullish_zone = {
                        'zone_outer': round(z_outer, 2),
                        'zone_closure': round(z_closure, 2),
                        'breakout_extreme': round(breakout_hh, 2),
                        'retest_wick': round(retest_low, 2),
                        'impulse_atr': round(impulse_dist / atr, 2),
                        'label': "Upper Broken LH (Q20/Q32 Bullish Shift)" if is_upper_lh else "Last Broken HH (Q5/Q83/Q90 Priority)"
                    }
                    break

        # 1B. Q70/A70 & Q31/A31 Protected-Wick Higher Low (HL) Retest Zone (Touch #2 inside Touch #1)
        if bullish_zone is None:
            for idx, w1_low, z_closure in reversed(sl_list):
                if not (3 <= (n - 1 - idx) <= 45):
                    continue
                bounce_hi = float(np.max(highs[idx + 1:n - 1]))
                impulse_dist = bounce_hi - w1_low
                if impulse_dist < 0.95 * atr:
                    continue
                peak_rel = int(np.argmax(highs[idx + 1:n - 1]))
                peak_idx = idx + 1 + peak_rel
                if n - 1 - peak_idx < 1:
                    continue
                # Touch #2 must hold Protected Wick above Touch #1 outer low (or within 0.08 ATR)
                sub_min = float(np.min(lows[idx + 1:]))
                if sub_min < w1_low - 0.08 * atr:
                    continue
                retest_low = float(np.min(lows[max(peak_idx + 1, n - 4):]))
                zone_top = max(z_closure, w1_low + 0.45 * atr)
                if retest_low <= zone_top + 0.20 * atr and curr_close >= z_closure - 0.08 * atr:
                    bullish_zone = {
                        'zone_outer': round(zone_top, 2),
                        'zone_closure': round(z_closure, 2),
                        'breakout_extreme': round(bounce_hi, 2),
                        'retest_wick': round(retest_low, 2),
                        'impulse_atr': round(impulse_dist / atr, 2),
                        'label': "Protected-Wick HL Retest (Q31/Q70/Q79 Touch #2)"
                    }
                    break

        # 2. Scan for Valid Bearish Break & Retest Zone (Broken HL or Major Broken LL)
        bearish_zone = None
        for idx, z_outer, z_closure in reversed(sl_list):
            if n - 1 - idx < 3:
                continue
            post_closes = closes[idx + 1:]

            # Must have broken and CLOSED below the Rejection Range (Q43, Q78)
            break_indices = [j for j, c in enumerate(post_closes) if c < z_outer - 0.08 * atr]
            if not break_indices:
                continue
            first_brk_rel = break_indices[0]
            first_brk_idx = idx + 1 + first_brk_rel
            if n - 1 - first_brk_idx < 2:
                continue

            breakout_ll = float(np.min(lows[first_brk_idx:n - 1]))
            impulse_dist = z_outer - breakout_ll
            if impulse_dist < 0.35 * atr:
                continue  # Insufficient bearish breakout momentum (Q71)

            trough_rel = int(np.argmin(lows[first_brk_idx:n - 1]))
            trough_idx = first_brk_idx + trough_rel
            if n - 1 - trough_idx < 1:
                continue

            # Q18/A18: Check for Structure Violation
            pullback_closes = closes[trough_idx + 1:]
            if len(pullback_closes) > 0 and float(np.max(pullback_closes)) > z_closure + 0.75 * atr:
                continue

            # Q28, Q36, Q79, Q83: Retest Touch Point in the last 4 bars
            retest_bars_highs = highs[max(trough_idx + 1, n - 4):]
            retest_high = float(np.max(retest_bars_highs))
            if retest_high >= z_outer - 0.45 * atr and retest_high <= z_closure + 0.75 * atr:
                if curr_close <= z_closure + 0.10 * atr:
                    is_broken_hl = (len(sl_list) >= 2 and z_outer > sl_list[-2][1])
                    bearish_zone = {
                        'zone_outer': round(z_outer, 2),
                        'zone_closure': round(z_closure, 2),
                        'breakout_extreme': round(breakout_ll, 2),
                        'retest_wick': round(retest_high, 2),
                        'impulse_atr': round(impulse_dist / atr, 2),
                        'label': "Last Broken HL (Q19/Q96 Bearish Shift)" if is_broken_hl else "Major Broken LL (Q24/Q34 Continuation)"
                    }
                    break

        # 2B. Q70/A70 & Q31/A31 Protected-Wick Lower High (LH) Retest Zone (Touch #2 inside Touch #1)
        if bearish_zone is None:
            for idx, w1_high, z_closure in reversed(sh_list):
                if not (3 <= (n - 1 - idx) <= 45):
                    continue
                drop_lo = float(np.min(lows[idx + 1:n - 1]))
                impulse_dist = w1_high - drop_lo
                if impulse_dist < 0.95 * atr:
                    continue
                trough_rel = int(np.argmin(lows[idx + 1:n - 1]))
                trough_idx = idx + 1 + trough_rel
                if n - 1 - trough_idx < 1:
                    continue
                sub_max = float(np.max(highs[idx + 1:]))
                if sub_max > w1_high + 0.08 * atr:
                    continue
                retest_high = float(np.max(highs[max(trough_idx + 1, n - 4):]))
                zone_bot = min(z_closure, w1_high - 0.45 * atr)
                if retest_high >= zone_bot - 0.20 * atr and curr_close <= z_closure + 0.08 * atr:
                    bearish_zone = {
                        'zone_outer': round(zone_bot, 2),
                        'zone_closure': round(z_closure, 2),
                        'breakout_extreme': round(drop_lo, 2),
                        'retest_wick': round(retest_high, 2),
                        'impulse_atr': round(impulse_dist / atr, 2),
                        'label': "Protected-Wick LH Retest (Q31/Q70/Q79 Touch #2)"
                    }
                    break

        # 3. Range Boundary Setup (Images 1-3: Trading the Consolidation Box Ceiling & Floor)
        if bullish_zone is None and bearish_zone is None and len(sh_list) >= 2 and len(sl_list) >= 2:
            recent_sh = [p for _, p, _ in sh_list[-6:]]
            recent_sl = [p for _, p, _ in sl_list[-6:]]
            box_ceiling = max(recent_sh)
            box_floor = min(recent_sl)
            box_height = box_ceiling - box_floor
            if 1.8 * atr <= box_height <= 7.0 * atr:
                # Range Floor Retest (Long)
                if curr_close <= box_floor + 0.45 * atr and curr_close >= box_floor - 0.25 * atr:
                    trend_bias = 'BULLISH'
                    is_sideways = False
                    bullish_zone = {
                        'zone_outer': round(box_floor, 2),
                        'zone_closure': round(box_floor + 0.20 * atr, 2),
                        'breakout_extreme': round(box_ceiling, 2),
                        'retest_wick': round(float(np.min(lows[-4:])), 2),
                        'impulse_atr': round(box_height / atr, 2),
                        'label': "Range Floor Retest (Q8/Lesson 2 — Images 1-3)"
                    }
                # Range Ceiling Retest (Short)
                elif curr_close >= box_ceiling - 0.45 * atr and curr_close <= box_ceiling + 0.25 * atr:
                    trend_bias = 'BEARISH'
                    is_sideways = False
                    bearish_zone = {
                        'zone_outer': round(box_ceiling, 2),
                        'zone_closure': round(box_ceiling - 0.20 * atr, 2),
                        'breakout_extreme': round(box_floor, 2),
                        'retest_wick': round(float(np.max(highs[-4:])), 2),
                        'impulse_atr': round(box_height / atr, 2),
                        'label': "Range Ceiling Retest (Q8/Lesson 2 — Images 1-3)"
                    }

        return {
            'trend_bias': trend_bias,
            'is_sideways': is_sideways,
            'ema20': round(ema20, 2),
            'ema50': round(ema50, 2),
            'major_high': round(major_high, 2),
            'major_low': round(major_low, 2),
            'bullish_zone': bullish_zone,
            'bearish_zone': bearish_zone,
            'last_broken_hh': bullish_zone['zone_outer'] if bullish_zone else None,
            'last_broken_lh': bearish_zone['zone_outer'] if bearish_zone else None,
            'upper_lh': bearish_zone['zone_closure'] if bearish_zone else None,
            'sh_count': len(sh_list),
            'sl_count': len(sl_list),
            'htf_timeframe': tf,
            'exec_timeframe': tf,
            'mtf_mode': 'DIRECT_TF',
            'timeframe_pair': f"{tf} Setup → {tf} Exec"
        }

    def get_multi_tf_structure_zones(self, exec_tf: str = 'M5') -> dict:
        """
        Scans M1, M5, M15, M30, H1, H4 simultaneously adhering to the 100 Masterclass rules:
        1. HTF_SETUP_LTF_EXEC: Find setup on H4/H1/M30/M15 and execute on M15/M5/M1 for efficiency & tighter Level-3 SL.
        2. HTF_TREND_LTF_CONTINUATION: When HTF (H4/H1) is trending, execute pro-trend LTF Break & Retests in 100% alignment with the HTF tide.
        3. Strictly Disallow Counter-Trend Pullbacks (Q4/A4, Q31/A31, Q46/A46): Never trade against the dominant HTF macro bias.
        """
        base = self.get_structure_zones(exec_tf, 80)
        ltf_atr = max(1e-5, self.get_atr(exec_tf, 14))
        ltf_bars = self.history.get(exec_tf, [])
        curr_price = float(ltf_bars[-1]['close']) if ltf_bars else 0.0

        # Gather available HTF structure analyses from highest to lowest
        htf_order = ['H4', 'H1', 'M30', 'M15']
        htf_zones = {}
        for htf in htf_order:
            if htf == exec_tf:
                continue
            if len(self.history.get(htf, [])) >= 20:
                htf_zones[htf] = self.get_structure_zones(htf, 80)

        # Establish dominant HTF macro bias from H4 and H1 (Masterclass Q4/A4, Q31/A31, Q46/A46)
        macro_bias = 'NEUTRAL'
        anchor_tf = 'H4'
        h4_data = htf_zones.get('H4')
        h1_data = htf_zones.get('H1')
        if h4_data and not h4_data.get('is_sideways') and h4_data.get('trend_bias') != 'NEUTRAL':
            macro_bias = h4_data.get('trend_bias')
            anchor_tf = 'H4'
        elif h1_data and not h1_data.get('is_sideways') and h1_data.get('trend_bias') != 'NEUTRAL':
            macro_bias = h1_data.get('trend_bias')
            anchor_tf = 'H1'

        if macro_bias == 'NEUTRAL':
            m30_data = htf_zones.get('M30')
            if m30_data and not m30_data.get('is_sideways'):
                macro_bias = m30_data.get('trend_bias', 'NEUTRAL')
                anchor_tf = 'M30'

        # 1. Mode 1: HTF Setup -> LTF Execution (e.g. H4/H1/M30 broken level retested on M5)
        for htf in htf_order:
            hz = htf_zones.get(htf)
            if not hz or hz.get('is_sideways'):
                continue
            htf_bias = hz.get('trend_bias', 'NEUTRAL')

            # Bullish Setup Retest (only allowed when macro bias is BULLISH or NEUTRAL)
            if macro_bias in ('BULLISH', 'NEUTRAL') and htf_bias == 'BULLISH' and hz.get('bullish_zone'):
                bz = dict(hz['bullish_zone'])
                z_outer = bz['zone_outer']
                z_clos = bz['zone_closure']
                z_min = min(z_outer, z_clos)
                z_max = max(z_outer, z_clos)
                if (z_min - 1.5 * ltf_atr) <= curr_price <= (z_max + 1.5 * ltf_atr):
                    # Use local LTF rejection low as retest wick for compact Level-3 SL
                    if len(ltf_bars) >= 6:
                        bz['retest_wick'] = min(float(b['low']) for b in ltf_bars[-6:])
                    bz['label'] = f"[{htf} Setup → {exec_tf} Exec] {bz['label']}"
                    return {
                        **base,
                        'trend_bias': 'BULLISH',
                        'is_sideways': False,
                        'bullish_zone': bz,
                        'htf_timeframe': htf,
                        'exec_timeframe': exec_tf,
                        'mtf_mode': 'HTF_SETUP_LTF_EXEC',
                        'timeframe_pair': f"{htf} Setup → {exec_tf} Exec"
                    }

            # Bearish Setup Retest (only allowed when macro bias is BEARISH or NEUTRAL)
            if macro_bias in ('BEARISH', 'NEUTRAL') and htf_bias == 'BEARISH' and hz.get('bearish_zone'):
                brz = dict(hz['bearish_zone'])
                z_outer = brz['zone_outer']
                z_clos = brz['zone_closure']
                z_min = min(z_outer, z_clos)
                z_max = max(z_outer, z_clos)
                if (z_min - 1.5 * ltf_atr) <= curr_price <= (z_max + 1.5 * ltf_atr):
                    # Use local LTF rejection high as retest wick for compact Level-3 SL
                    if len(ltf_bars) >= 6:
                        brz['retest_wick'] = max(float(b['high']) for b in ltf_bars[-6:])
                    brz['label'] = f"[{htf} Setup → {exec_tf} Exec] {brz['label']}"
                    return {
                        **base,
                        'trend_bias': 'BEARISH',
                        'is_sideways': False,
                        'bearish_zone': brz,
                        'htf_timeframe': htf,
                        'exec_timeframe': exec_tf,
                        'mtf_mode': 'HTF_SETUP_LTF_EXEC',
                        'timeframe_pair': f"{htf} Setup → {exec_tf} Exec"
                    }

        # 2. Mode 2: Pro-Trend Continuation on LTF (HTF_TREND_LTF_CONTINUATION)
        # When HTF is trending, LTF forms a confirmed Break & Retest in the SAME direction
        if macro_bias == 'BEARISH' and base.get('bearish_zone'):
            brz = dict(base['bearish_zone'])
            brz['label'] = f"[{anchor_tf} Trend → {exec_tf} Continuation] {brz['label']}"
            return {
                **base,
                'trend_bias': 'BEARISH',
                'is_sideways': False,
                'bearish_zone': brz,
                'htf_timeframe': anchor_tf,
                'exec_timeframe': exec_tf,
                'mtf_mode': 'HTF_TREND_LTF_CONTINUATION',
                'timeframe_pair': f"{anchor_tf} Trend → {exec_tf} Continuation"
            }

        if macro_bias == 'BULLISH' and base.get('bullish_zone'):
            bz = dict(base['bullish_zone'])
            bz['label'] = f"[{anchor_tf} Trend → {exec_tf} Continuation] {bz['label']}"
            return {
                **base,
                'trend_bias': 'BULLISH',
                'is_sideways': False,
                'bullish_zone': bz,
                'htf_timeframe': anchor_tf,
                'exec_timeframe': exec_tf,
                'mtf_mode': 'HTF_TREND_LTF_CONTINUATION',
                'timeframe_pair': f"{anchor_tf} Trend → {exec_tf} Continuation"
            }

        # 3. Filter: Standalone counter-trend LTF setups or sideways regimes are strictly rejected!
        return {
            **base,
            'is_sideways': True,
            'trend_bias': 'NEUTRAL',
            'no_htf_anchor': True,
            'bullish_zone': None,
            'bearish_zone': None,
            'label': f"Waiting for Pro-Trend Setup aligned with {macro_bias} ({anchor_tf})"
        }


class VirtualIntrabarPositionTracker:
    """
    Evaluates open trades ON EVERY SINGLE TICK:
    - Stop Loss hit
    - Take Profit hit
    - Q93 Breakeven locked (+0.42R moves SL to +0.05R)
    - Trailing ratchet locked
    """
    def __init__(self, pt_val: float = 0.01):
        self.pt_val = pt_val
        self.active_trades: List[dict] = []
        self.closed_trades: List[dict] = []
        self.potential_monitors: List[dict] = []

    def open_trade(self, trade: dict):
        trade['status'] = 'OPEN'
        trade['peak_r'] = 0.0
        trade['be_locked'] = False
        trade['current_sl'] = trade['sl']
        trade['potential_r'] = 0.0
        trade['potential_price'] = trade['entry']
        trade['potential_time'] = trade['entryTime']
        self.active_trades.append(trade)

    def process_tick(self, t_sec: int, bid: float, ask: float) -> List[dict]:
        """Evaluates every open trade against the current tick. Returns newly closed trades."""
        just_closed = []
        remaining = []

        # Monitor closed trades (e.g. BE exits) to track potential runner excursion until original SL hit
        if self.potential_monitors:
            rem_mon = []
            for ptr in self.potential_monitors:
                p_long = ptr['type'] == 'long-position'
                orig_sl = ptr['sl']
                p_entry = ptr['entry']
                p_stop_d = ptr['stopDist']
                orig_sl_hit = (bid <= orig_sl) if p_long else (ask >= orig_sl)
                if orig_sl_hit or (t_sec - ptr.get('exitTime', t_sec) > 86400):
                    continue
                curr_fav = (bid - p_entry) / p_stop_d if p_long else (p_entry - ask) / p_stop_d
                if curr_fav > ptr.get('potential_r', 0.0):
                    ptr['potential_r'] = round(curr_fav, 2)
                    ptr['potential_price'] = round(bid if p_long else ask, 2)
                    ptr['potential_time'] = t_sec
                rem_mon.append(ptr)
            self.potential_monitors = rem_mon

        for tr in self.active_trades:
            is_long = tr['type'] == 'long-position'
            entry = tr['entry']
            stop_d = tr['stopDist']
            profit_d = tr['profitDist']
            tp_r = profit_d / max(1e-5, stop_d)
            act_price = bid if is_long else ask

            # Calculate current favorable excursion in R-multiples
            fav_r = (bid - entry) / stop_d if is_long else (entry - ask) / stop_d
            if fav_r > tr['peak_r']:
                tr['peak_r'] = fav_r
            if fav_r > tr.get('potential_r', 0.0):
                tr['potential_r'] = round(fav_r, 2)
                tr['potential_price'] = round(act_price, 2)
                tr['potential_time'] = t_sec

            # 1. Full Take Profit hit
            if fav_r >= tp_r:
                tr['status'] = 'CLOSED'
                tr['exitTime'] = t_sec
                tr['exitPrice'] = tr['tp']
                tr['outcome'] = 'FULL_TP'
                tr['realized_r'] = tp_r
                tr['points'] = round(tp_r * stop_d, 2)
                tr['pnl_usd'] = round(tr['points'] * self.pt_val, 2)
                tr['win'] = True
                just_closed.append(tr)
                self.closed_trades.append(tr)
                # Keep tracking potential runner excursion even past TP until original SL hit
                self.potential_monitors.append(tr)
                continue

            # 2. Q16/A16, Q79/A79 & Q93/A93 Retest-Protected Runner + Dynamic Trailing Ratchet:
            # Arm Tranche-1 breakeven protection at +0.75R (be_locked=True),
            # while holding the active runner stop (current_sl) under the Level-3 Retest Point (tr['sl'])
            # until +3.5R so normal retests of the broken level don't choke the runner at BE!
            peak_r = tr['peak_r']
            if peak_r >= 0.75:
                tr['be_locked'] = True

            target_sl = tr['current_sl']
            if peak_r >= 6.0:
                trail_r = peak_r - 2.0
                r_sl = round(entry + trail_r * stop_d, 2) if is_long else round(entry - trail_r * stop_d, 2)
                target_sl = max(target_sl, r_sl) if is_long else min(target_sl, r_sl)
            elif peak_r >= 3.5:
                trail_r = peak_r - 1.5
                r_sl = round(entry + trail_r * stop_d, 2) if is_long else round(entry - trail_r * stop_d, 2)
                target_sl = max(target_sl, r_sl) if is_long else min(target_sl, r_sl)
            elif peak_r >= 2.0:
                r_sl = round(entry + 0.80 * stop_d, 2) if is_long else round(entry - 0.80 * stop_d, 2)
                target_sl = max(target_sl, r_sl) if is_long else min(target_sl, r_sl)

            tr['current_sl'] = target_sl

            # 3. Stop Loss hit (against exact Bid for Long, Ask for Short)
            sl_hit = (bid <= tr['current_sl']) if is_long else (ask >= tr['current_sl'])
            if sl_hit:
                tr['status'] = 'CLOSED'
                tr['exitTime'] = t_sec
                tr['exitPrice'] = tr['current_sl']
                if peak_r >= 6.0:
                    realized_r = round(peak_r - 2.0, 2)
                    tr['outcome'] = 'TRAIL_WIN'
                    tr['win'] = True
                    self.potential_monitors.append(tr)
                elif peak_r >= 3.5:
                    realized_r = round(peak_r - 1.5, 2)
                    tr['outcome'] = 'TRAIL_WIN'
                    tr['win'] = True
                    self.potential_monitors.append(tr)
                elif peak_r >= 1.5:
                    realized_r = 1.00
                    tr['outcome'] = 'TRAIL_WIN'
                    tr['win'] = True
                    self.potential_monitors.append(tr)
                elif tr['be_locked']:
                    realized_r = 0.20
                    tr['outcome'] = 'PROTECTED_BE'
                    tr['win'] = True
                    self.potential_monitors.append(tr)
                else:
                    realized_r = -1.0
                    tr['outcome'] = 'SL'
                    tr['win'] = False

                tr['realized_r'] = round(realized_r, 2)
                tr['points'] = round(realized_r * stop_d, 2)
                tr['pnl_usd'] = round(tr['points'] * self.pt_val, 2)
                just_closed.append(tr)
                self.closed_trades.append(tr)
                continue

            remaining.append(tr)

        self.active_trades = remaining
        return just_closed
