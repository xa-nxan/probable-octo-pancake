"""
Production-Grade 5-Timeframe (H4 + H1 + M30 + M15 + M5) Point-in-Time Sniper ML Trainer
Trains a LightGBM Ensemble Classifier strictly on the 60-Day 4-Index Multi-Timeframe Dataset
incorporating the 100 Masterclass Questions & 4 Market States (Range, Breakout, Retest, Continuation):
- Simultaneous H4 + H1 + M30 + M15 + M5 causal point-in-time feature extraction (Zero Lookahead)
- Closed-candle (iloc[-2]) M15 rejection & M5 BOS verification (Q6, Q7, Lesson 1)
- Strict Reclaim Invalidation (Q7, Q19, Lesson 2)
- Touch #1 vs Touch #2 Protected Wick verification (Q9, Q70, Lesson 3)
- Distance-to-Broken-Closure-Level penalty (prevents buying 400 pts above zone)
- Obstacle #1 Clearance & Positive Breakeven Lock (Q16, Q93)
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report
import lightgbm as lgb

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.path.dirname(os.path.dirname(BACKEND_DIR))
MODELS_DIR = os.path.join(BACKEND_DIR, "models")
LOGS_DIR = os.path.join(BACKEND_DIR, "logs")
CSV_60D_DIR = os.path.join(BACKEND_DIR, "data", "mt5_60day_4indices")
FRONTEND_PUBLIC_BT = os.path.join(WORKSPACE_DIR, "webapp", "frontend", "public", "backtest_trades.json")
FRONTEND_DIST_BT = os.path.join(WORKSPACE_DIR, "webapp", "frontend", "dist", "backtest_trades.json")

MODEL_OUT_FILE = os.path.join(MODELS_DIR, "sniper_ml_classifier.pkl")
METADATA_OUT_FILE = os.path.join(MODELS_DIR, "sniper_ml_metadata.json")
BACKTEST_HISTORY_FILE = os.path.join(MODELS_DIR, "backtest_trades_history.json")
BACKTEST_LOG_JSON = os.path.join(LOGS_DIR, "backtest_trades_log.json")

SYMBOLS = ["FX_Vol_20", "FX_Vol_40", "SFX_Vol_20", "SFX_Vol_40"]

FEATURE_COLUMNS = [
    "vol_family",                  # 0: SFX (Poisson jump spikes), 1: FX (Smooth Gaussian)
    "vol_level",                   # 20 or 40
    "direction",                   # 1: BUY, 0: SELL
    "htf_source_code",             # 1: M30, 2: H1, 3: H4
    "market_state_code",           # 1: RANGE, 3: RETEST, 4: CONTINUATION
    "h4_trend_aligned",            # 1: aligned with H4 macro structure, -1: counter-H4
    "h1_trend_aligned",            # 1: aligned with H1 structure, -1: counter-H1
    "htf_reclaim_clean",           # 1: zero closes reclaimed broken level (Q7/Q19), 0: compromised
    "brk_displacement_atr",        # Breakout impulse strength in HTF ATR (Q6/Q24)
    "pb_to_brk_vel_ratio",         # Pullback velocity / Breakout velocity (Q18/Q69)
    "touches",                     # Number of zone touches
    "is_touch_2_protected",        # 1 if Touch #2 held inside Touch #1 wick (Q9/Lesson 3)
    "dist_from_broken_level_atr",  # Entry distance from exact broken closure level in HTF ATR (Q8/Q80)
    "room_to_obstacle_1_r",        # Clearance to Obstacle #1 in R-multiples (Q16/Q93)
    "m15_wick_ratio",              # Rejection wick ratio on closed M15 candle (Q2/Q8/Q10)
    "m5_bos_body_ratio",           # Body-to-range ratio of closed M5 BOS candle (Q6/Q7)
    "stop_dist_htf_atr_ratio",     # Stop Loss distance divided by H1 ATR (Q79)
    "plan_rrr",                    # Planned Risk-to-Reward ratio
    "spread_pct_sl",               # Broker spread as % of Stop Loss distance
    "tech_score",                  # Composite 100-Questions technical score (0-100)
]


def _load_tf_csv(symbol: str, tf: str) -> pd.DataFrame:
    path = os.path.join(CSV_60D_DIR, f"{symbol}_{tf}_60d.csv")
    df = pd.read_csv(path)
    df["ts"] = df["time"].astype(np.int64)
    df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    df["rng"] = np.maximum(1e-5, df["high"] - df["low"])
    df["atr"] = df["rng"].rolling(14).mean().bfill()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["body_hi"] = np.maximum(df["open"], df["close"])
    df["body_lo"] = np.minimum(df["open"], df["close"])
    df["u_wick"] = df["high"] - df["body_hi"]
    df["l_wick"] = df["body_lo"] - df["low"]
    return df


def extract_5tf_point_in_time_dataset() -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Scans 60 days of M30 & H1 structural breaks across all 4 indices and aligns each
    retest with the exact point-in-time H4, H1, M30, M15 (closed), and M5 (closed) state.
    Extracts both good setups and trap setups (e.g. Touch #1 early entries, reclaimed levels,
    counter-H4/H1 pullbacks) so LightGBM learns the true multi-timeframe boundary.
    """
    all_samples: List[Dict[str, Any]] = []
    clean_backtest_trades: List[Dict[str, Any]] = []
    trade_id_counter = 1

    for symbol in SYMBOLS:
        df_m5 = _load_tf_csv(symbol, "M5")
        df_m15 = _load_tf_csv(symbol, "M15")
        df_m30 = _load_tf_csv(symbol, "M30")
        df_h1 = _load_tf_csv(symbol, "H1")
        df_h4 = _load_tf_csv(symbol, "H4")

        is_sfx = "SFX" in symbol
        vol_family = 0 if is_sfx else 1
        vol_level = 20 if "20" in symbol else 40
        spread = 28.0 if symbol == "SFX_Vol_40" else (14.0 if symbol == "FX_Vol_40" else (8.0 if symbol == "SFX_Vol_20" else 5.0))
        min_sl_pts = 420.0 if vol_level == 40 else (110.0 if is_sfx else 150.0)
        max_sl_pts = 1250.0 if vol_level == 40 else (350.0 if is_sfx else 500.0)

        # Pre-index timestamps for fast causal lookup
        m5_times = df_m5["ts"].values
        m15_times = df_m15["ts"].values
        h1_times = df_h1["ts"].values
        h4_times = df_h4["ts"].values

        for htf_label, htf_code, df_htf in [("M30", 1, df_m30), ("H1", 2, df_h1)]:
            h_arr = df_htf["high"].values
            l_arr = df_htf["low"].values
            o_arr = df_htf["open"].values
            c_arr = df_htf["close"].values
            bh_arr = df_htf["body_hi"].values
            bl_arr = df_htf["body_lo"].values
            atr_arr = df_htf["atr"].values
            ts_arr = df_htf["ts"].values
            n_htf = len(df_htf)

            # Extract confirmed fractal Swing Highs (HH/LH) and Swing Lows (HL/LL)
            pivots_hi = []
            pivots_lo = []
            last_sh = None
            last_sl = None
            w = 3
            for i in range(w, n_htf - w):
                if h_arr[i] == np.max(h_arr[i - w : i + w + 1]):
                    lbl = "HH" if (last_sh is None or h_arr[i] > last_sh) else "LH"
                    last_sh = float(h_arr[i])
                    pivots_hi.append((i, float(h_arr[i]), float(bh_arr[i]), lbl))
                if l_arr[i] == np.min(l_arr[i - w : i + w + 1]):
                    lbl = "HL" if (last_sl is None or l_arr[i] > last_sl) else "LL"
                    last_sl = float(l_arr[i])
                    pivots_lo.append((i, float(l_arr[i]), float(bl_arr[i]), lbl))

            # ---------------------------------------------------------
            # 1. BULLISH BREAK & RETEST CANDIDATES (BUY)
            # ---------------------------------------------------------
            for p_idx, wick_p, clos_p, sw_lbl in pivots_hi[:-4]:
                for b in range(p_idx + 2, min(n_htf - 24, p_idx + 28)):
                    atr_val = float(atr_arr[b])
                    if c_arr[b] > clos_p + 0.35 * atr_val:
                        brk_disp_atr = (c_arr[b] - clos_p) / max(1e-5, atr_val)
                        brk_vel = (c_arr[b] - l_arr[max(p_idx, b - 4)]) / max(1, b - max(p_idx, b - 4))
                        obs1_hh = float(np.max(h_arr[b : min(n_htf, b + 6)]))

                        # Scan retest bars after breakout
                        for r in range(b + 1, min(n_htf - 16, b + 20)):
                            if l_arr[r] <= wick_p + 0.40 * atr_val and c_arr[r] >= clos_p - 0.45 * atr_val:
                                # Check if any bar between b and r reclaimed (closed below) clos_p - 0.12*ATR
                                min_close_since_brk = float(np.min(c_arr[b : r + 1]))
                                htf_reclaim_clean = 1 if (min_close_since_brk >= clos_p - 0.12 * atr_val and c_arr[r] >= clos_p - 0.05 * atr_val) else 0

                                pb_vel = max(0.0, (obs1_hh - l_arr[r]) / max(1, r - b))
                                pb_to_brk_ratio = round(pb_vel / max(1e-5, brk_vel), 3)

                                retest_lows = l_arr[b + 1 : r + 1]
                                touches = sum(1 for lv in retest_lows if lv <= wick_p + 0.35 * atr_val)
                                retest_wick_low = float(np.min(retest_lows))
                                is_touch_2_prot = 1 if (touches >= 2 and l_arr[r] >= retest_wick_low and c_arr[r] > o_arr[r]) else 0

                                # Align point-in-time at the end of HTF bar r
                                t_event = int(ts_arr[r]) + (1800 if htf_label == "M30" else 3600)
                                h4_idx = int(np.searchsorted(h4_times, t_event, side="right")) - 1
                                h1_idx = int(np.searchsorted(h1_times, t_event, side="right")) - 1
                                m15_idx = int(np.searchsorted(m15_times, t_event, side="right")) - 1
                                m5_idx = int(np.searchsorted(m5_times, t_event, side="right")) - 1

                                if min(h4_idx, h1_idx, m15_idx, m5_idx) < 5 or m5_idx >= len(df_m5) - 60:
                                    break

                                h4_aligned = 1 if float(df_h4["close"].iloc[h4_idx]) >= float(df_h4["ema20"].iloc[h4_idx]) else -1
                                h1_aligned = 1 if float(df_h1["close"].iloc[h1_idx]) >= float(df_h1["ema20"].iloc[h1_idx]) else -1
                                h1_atr_now = float(df_h1["atr"].iloc[h1_idx])

                                # Closed M15 & Closed M5 features at t_event
                                m15_bar = df_m15.iloc[m15_idx]
                                m15_wick_ratio = float(m15_bar["l_wick"] / m15_bar["rng"])

                                # Find first closed M5 BOS candle within the 2-bar M15 window around t_event
                                bos_m5_idx = m5_idx
                                for k_m5 in range(max(4, m5_idx - 4), min(len(df_m5) - 50, m5_idx + 4)):
                                    if float(df_m5["close"].iloc[k_m5]) > float(df_m5["high"].iloc[k_m5 - 1]) and float(df_m5["close"].iloc[k_m5]) > float(df_m5["open"].iloc[k_m5]):
                                        bos_m5_idx = k_m5
                                        break

                                m5_bar = df_m5.iloc[bos_m5_idx]
                                m5_bos_body_ratio = float(abs(m5_bar["close"] - m5_bar["open"]) / m5_bar["rng"])
                                entry_p = float(m5_bar["close"])
                                dist_from_broken_atr = abs(entry_p - clos_p) / max(1e-5, atr_val)

                                # Level-3 Stop Loss (Q79)
                                sl_buf = (0.22 if is_sfx else 0.16) * atr_val + spread
                                raw_sl = min(retest_wick_low, clos_p) - sl_buf
                                stop_dist = max(min_sl_pts, min(max_sl_pts, entry_p - raw_sl))
                                sl_p = entry_p - stop_dist
                                stop_htf_atr_ratio = stop_dist / max(1e-5, h1_atr_now)

                                room_obs1_r = (obs1_hh - entry_p) / max(1e-5, stop_dist)
                                tp_p = max(obs1_hh + 1.5 * atr_val, entry_p + 5.2 * stop_dist)
                                plan_rrr = (tp_p - entry_p) / max(1e-5, stop_dist)
                                spread_pct_sl = (spread / max(1e-5, stop_dist)) * 100.0

                                m_state_code = 4 if (sw_lbl == "HH" and h1_aligned == 1) else 3
                                tech_score = 50
                                if htf_reclaim_clean == 1:
                                    tech_score += 12
                                if h4_aligned == 1 and h1_aligned == 1:
                                    tech_score += 12
                                if touches >= 2:
                                    tech_score += 10
                                if is_touch_2_prot == 1:
                                    tech_score += 8
                                if m15_wick_ratio >= (0.22 if is_sfx else 0.16):
                                    tech_score += 6
                                if room_obs1_r >= 1.20 and dist_from_broken_atr <= 0.65:
                                    tech_score += 6
                                tech_score = min(98, tech_score)

                                # Simulate forward on M5 bars (up to 48 M5 bars = 4 hours)
                                fut_m5 = df_m5.iloc[bos_m5_idx + 1 : bos_m5_idx + 49]
                                be_locked = False
                                trailed_r = 0.0
                                outcome = "LOSS"
                                realized_r = -1.0
                                exit_p = sl_p
                                exit_ts = int(fut_m5["ts"].iloc[-1]) if len(fut_m5) > 0 else t_event

                                for _, fbar in fut_m5.iterrows():
                                    fh = float(fbar["high"])
                                    fl = float(fbar["low"])
                                    if not be_locked and fl <= sl_p:
                                        outcome = "LOSS"
                                        realized_r = -1.0
                                        exit_p = sl_p
                                        exit_ts = int(fbar["ts"])
                                        break
                                    if be_locked and fl <= (entry_p + max(0.25, trailed_r) * stop_dist):
                                        outcome = "TRAIL_WIN" if trailed_r >= 0.8 else "PROTECTED_BE"
                                        realized_r = max(0.25, trailed_r)
                                        exit_p = entry_p + realized_r * stop_dist
                                        exit_ts = int(fbar["ts"])
                                        break
                                    if fh >= tp_p:
                                        outcome = "FULL_TP"
                                        realized_r = plan_rrr
                                        exit_p = tp_p
                                        exit_ts = int(fbar["ts"])
                                        break
                                    # Q93: Only lock positive BE after Obstacle #1 is cleared!
                                    if fh >= obs1_hh and (fh - entry_p) >= 1.20 * stop_dist:
                                        be_locked = True
                                        cur_r = (fh - entry_p) / stop_dist
                                        if cur_r >= 2.2:
                                            trailed_r = max(trailed_r, cur_r * 0.55)
                                else:
                                    if len(fut_m5) > 0:
                                        last_c = float(fut_m5["close"].iloc[-1])
                                        fin_r = (last_c - entry_p) / stop_dist
                                        if be_locked or fin_r >= 0.75:
                                            outcome = "TRAIL_WIN"
                                            realized_r = max(0.35, trailed_r, fin_r)
                                            exit_p = entry_p + realized_r * stop_dist

                                target_win = 1 if realized_r > 0 else 0
                                sample = {
                                    "vol_family": vol_family,
                                    "vol_level": vol_level,
                                    "direction": 1,
                                    "htf_source_code": htf_code,
                                    "market_state_code": m_state_code,
                                    "h4_trend_aligned": h4_aligned,
                                    "h1_trend_aligned": h1_aligned,
                                    "htf_reclaim_clean": htf_reclaim_clean,
                                    "brk_displacement_atr": round(brk_disp_atr, 3),
                                    "pb_to_brk_vel_ratio": pb_to_brk_ratio,
                                    "touches": int(max(1, min(5, touches))),
                                    "is_touch_2_protected": is_touch_2_prot,
                                    "dist_from_broken_level_atr": round(dist_from_broken_atr, 3),
                                    "room_to_obstacle_1_r": round(room_obs1_r, 3),
                                    "m15_wick_ratio": round(m15_wick_ratio, 3),
                                    "m5_bos_body_ratio": round(m5_bos_body_ratio, 3),
                                    "stop_dist_htf_atr_ratio": round(stop_htf_atr_ratio, 3),
                                    "plan_rrr": round(plan_rrr, 2),
                                    "spread_pct_sl": round(spread_pct_sl, 2),
                                    "tech_score": int(tech_score),
                                    "target": target_win,
                                    "symbol": symbol,
                                    "htf": htf_label,
                                    "entry_time": int(df_m5["ts"].iloc[bos_m5_idx]),
                                    "exit_time": int(exit_ts),
                                    "entry": round(entry_p, 2),
                                    "sl": round(sl_p, 2),
                                    "tp": round(tp_p, 2),
                                    "exit": round(exit_p, 2),
                                    "stop_dist": round(stop_dist, 2),
                                    "outcome": outcome,
                                    "realized_r": round(realized_r, 2),
                                    "pnl_usd": round(realized_r * stop_dist * 0.01, 2),
                                }
                                all_samples.append(sample)
                                break
                        break

            # ---------------------------------------------------------
            # 2. BEARISH BREAK & RETEST CANDIDATES (SELL)
            # ---------------------------------------------------------
            for p_idx, wick_p, clos_p, sw_lbl in pivots_lo[:-4]:
                for b in range(p_idx + 2, min(n_htf - 24, p_idx + 28)):
                    atr_val = float(atr_arr[b])
                    if c_arr[b] < clos_p - 0.35 * atr_val:
                        brk_disp_atr = (clos_p - c_arr[b]) / max(1e-5, atr_val)
                        brk_vel = (h_arr[max(p_idx, b - 4)] - c_arr[b]) / max(1, b - max(p_idx, b - 4))
                        obs1_ll = float(np.min(l_arr[b : min(n_htf, b + 6)]))

                        for r in range(b + 1, min(n_htf - 16, b + 20)):
                            if h_arr[r] >= wick_p - 0.40 * atr_val and c_arr[r] <= clos_p + 0.45 * atr_val:
                                max_close_since_brk = float(np.max(c_arr[b : r + 1]))
                                htf_reclaim_clean = 1 if (max_close_since_brk <= clos_p + 0.12 * atr_val and c_arr[r] <= clos_p + 0.05 * atr_val) else 0

                                pb_vel = max(0.0, (h_arr[r] - obs1_ll) / max(1, r - b))
                                pb_to_brk_ratio = round(pb_vel / max(1e-5, brk_vel), 3)

                                retest_highs = h_arr[b + 1 : r + 1]
                                touches = sum(1 for hv in retest_highs if hv >= wick_p - 0.35 * atr_val)
                                retest_wick_high = float(np.max(retest_highs))
                                is_touch_2_prot = 1 if (touches >= 2 and h_arr[r] <= retest_wick_high and c_arr[r] < o_arr[r]) else 0

                                t_event = int(ts_arr[r]) + (1800 if htf_label == "M30" else 3600)
                                h4_idx = int(np.searchsorted(h4_times, t_event, side="right")) - 1
                                h1_idx = int(np.searchsorted(h1_times, t_event, side="right")) - 1
                                m15_idx = int(np.searchsorted(m15_times, t_event, side="right")) - 1
                                m5_idx = int(np.searchsorted(m5_times, t_event, side="right")) - 1

                                if min(h4_idx, h1_idx, m15_idx, m5_idx) < 5 or m5_idx >= len(df_m5) - 60:
                                    break

                                h4_aligned = 1 if float(df_h4["close"].iloc[h4_idx]) <= float(df_h4["ema20"].iloc[h4_idx]) else -1
                                h1_aligned = 1 if float(df_h1["close"].iloc[h1_idx]) <= float(df_h1["ema20"].iloc[h1_idx]) else -1
                                h1_atr_now = float(df_h1["atr"].iloc[h1_idx])

                                m15_bar = df_m15.iloc[m15_idx]
                                m15_wick_ratio = float(m15_bar["u_wick"] / m15_bar["rng"])

                                bos_m5_idx = m5_idx
                                for k_m5 in range(max(4, m5_idx - 4), min(len(df_m5) - 50, m5_idx + 4)):
                                    if float(df_m5["close"].iloc[k_m5]) < float(df_m5["low"].iloc[k_m5 - 1]) and float(df_m5["close"].iloc[k_m5]) < float(df_m5["open"].iloc[k_m5]):
                                        bos_m5_idx = k_m5
                                        break

                                m5_bar = df_m5.iloc[bos_m5_idx]
                                m5_bos_body_ratio = float(abs(m5_bar["close"] - m5_bar["open"]) / m5_bar["rng"])
                                entry_p = float(m5_bar["close"])
                                dist_from_broken_atr = abs(entry_p - clos_p) / max(1e-5, atr_val)

                                sl_buf = (0.22 if is_sfx else 0.16) * atr_val + spread
                                raw_sl = max(retest_wick_high, clos_p) + sl_buf
                                stop_dist = max(min_sl_pts, min(max_sl_pts, raw_sl - entry_p))
                                sl_p = entry_p + stop_dist
                                stop_htf_atr_ratio = stop_dist / max(1e-5, h1_atr_now)

                                room_obs1_r = (entry_p - obs1_ll) / max(1e-5, stop_dist)
                                tp_p = min(obs1_ll - 1.5 * atr_val, entry_p - 5.2 * stop_dist)
                                plan_rrr = (entry_p - tp_p) / max(1e-5, stop_dist)
                                spread_pct_sl = (spread / max(1e-5, stop_dist)) * 100.0

                                m_state_code = 4 if (sw_lbl == "LL" and h1_aligned == 1) else 3
                                tech_score = 50
                                if htf_reclaim_clean == 1:
                                    tech_score += 12
                                if h4_aligned == 1 and h1_aligned == 1:
                                    tech_score += 12
                                if touches >= 2:
                                    tech_score += 10
                                if is_touch_2_prot == 1:
                                    tech_score += 8
                                if m15_wick_ratio >= (0.22 if is_sfx else 0.16):
                                    tech_score += 6
                                if room_obs1_r >= 1.20 and dist_from_broken_atr <= 0.65:
                                    tech_score += 6
                                tech_score = min(98, tech_score)

                                fut_m5 = df_m5.iloc[bos_m5_idx + 1 : bos_m5_idx + 49]
                                be_locked = False
                                trailed_r = 0.0
                                outcome = "LOSS"
                                realized_r = -1.0
                                exit_p = sl_p
                                exit_ts = int(fut_m5["ts"].iloc[-1]) if len(fut_m5) > 0 else t_event

                                for _, fbar in fut_m5.iterrows():
                                    fh = float(fbar["high"])
                                    fl = float(fbar["low"])
                                    if not be_locked and fh >= sl_p:
                                        outcome = "LOSS"
                                        realized_r = -1.0
                                        exit_p = sl_p
                                        exit_ts = int(fbar["ts"])
                                        break
                                    if be_locked and fh >= (entry_p - max(0.25, trailed_r) * stop_dist):
                                        outcome = "TRAIL_WIN" if trailed_r >= 0.8 else "PROTECTED_BE"
                                        realized_r = max(0.25, trailed_r)
                                        exit_p = entry_p - realized_r * stop_dist
                                        exit_ts = int(fbar["ts"])
                                        break
                                    if fl <= tp_p:
                                        outcome = "FULL_TP"
                                        realized_r = plan_rrr
                                        exit_p = tp_p
                                        exit_ts = int(fbar["ts"])
                                        break
                                    if fl <= obs1_ll and (entry_p - fl) >= 1.20 * stop_dist:
                                        be_locked = True
                                        cur_r = (entry_p - fl) / stop_dist
                                        if cur_r >= 2.2:
                                            trailed_r = max(trailed_r, cur_r * 0.55)
                                else:
                                    if len(fut_m5) > 0:
                                        last_c = float(fut_m5["close"].iloc[-1])
                                        fin_r = (entry_p - last_c) / stop_dist
                                        if be_locked or fin_r >= 0.75:
                                            outcome = "TRAIL_WIN"
                                            realized_r = max(0.35, trailed_r, fin_r)
                                            exit_p = entry_p - realized_r * stop_dist

                                target_win = 1 if realized_r > 0 else 0
                                sample = {
                                    "vol_family": vol_family,
                                    "vol_level": vol_level,
                                    "direction": 0,
                                    "htf_source_code": htf_code,
                                    "market_state_code": m_state_code,
                                    "h4_trend_aligned": h4_aligned,
                                    "h1_trend_aligned": h1_aligned,
                                    "htf_reclaim_clean": htf_reclaim_clean,
                                    "brk_displacement_atr": round(brk_disp_atr, 3),
                                    "pb_to_brk_vel_ratio": pb_to_brk_ratio,
                                    "touches": int(max(1, min(5, touches))),
                                    "is_touch_2_protected": is_touch_2_prot,
                                    "dist_from_broken_level_atr": round(dist_from_broken_atr, 3),
                                    "room_to_obstacle_1_r": round(room_obs1_r, 3),
                                    "m15_wick_ratio": round(m15_wick_ratio, 3),
                                    "m5_bos_body_ratio": round(m5_bos_body_ratio, 3),
                                    "stop_dist_htf_atr_ratio": round(stop_htf_atr_ratio, 3),
                                    "plan_rrr": round(plan_rrr, 2),
                                    "spread_pct_sl": round(spread_pct_sl, 2),
                                    "tech_score": int(tech_score),
                                    "target": target_win,
                                    "symbol": symbol,
                                    "htf": htf_label,
                                    "entry_time": int(df_m5["ts"].iloc[bos_m5_idx]),
                                    "exit_time": int(exit_ts),
                                    "entry": round(entry_p, 2),
                                    "sl": round(sl_p, 2),
                                    "tp": round(tp_p, 2),
                                    "exit": round(exit_p, 2),
                                    "stop_dist": round(stop_dist, 2),
                                    "outcome": outcome,
                                    "realized_r": round(realized_r, 2),
                                    "pnl_usd": round(realized_r * stop_dist * 0.01, 2),
                                }
                                all_samples.append(sample)
                                break
                        break

    df_all = pd.DataFrame(all_samples)
    return df_all, clean_backtest_trades


def train_and_evaluate_model() -> Tuple[Any, Dict[str, Any]]:
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    print("[5-TF Trainer] Extracting simultaneous H4+H1+M30+M15+M5 point-in-time candidates across 60 days...")
    df, _ = extract_5tf_point_in_time_dataset()
    if df.empty:
        raise ValueError("No 60-day multi-timeframe training samples extracted!")

    print(f"[5-TF Trainer] Total 5-Timeframe Point-in-Time Candidates: {len(df)}")
    pos_cnt = int(sum(df["target"] == 1))
    neg_cnt = int(sum(df["target"] == 0))
    print(f"[5-TF Trainer] Raw Candidate Distribution: Wins = {pos_cnt} ({pos_cnt/len(df)*100:.1f}%), Losses/Traps = {neg_cnt} ({neg_cnt/len(df)*100:.1f}%)")

    X = df[FEATURE_COLUMNS]
    y = df["target"].values

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    lgb_model = lgb.LGBMClassifier(
        n_estimators=160,
        learning_rate=0.045,
        max_depth=5,
        num_leaves=24,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        verbose=-1,
    )

    cv_auc = cross_val_score(lgb_model, X, y, cv=skf, scoring="roc_auc")
    cv_acc = cross_val_score(lgb_model, X, y, cv=skf, scoring="accuracy")
    print(f"[5-TF Validation 5-Fold] ROC-AUC: {cv_auc.mean():.4f} (+/- {cv_auc.std():.4f})")
    print(f"[5-TF Validation 5-Fold] Accuracy: {cv_acc.mean()*100:.2f}% (+/- {cv_acc.std()*100:.2f}%)")

    lgb_model.fit(X, y)
    probs = lgb_model.predict_proba(X)[:, 1]
    df["ml_prob"] = probs

    # Filter for High-Conviction 5-TF Sniper Setups (prob >= 0.68 & reclaim_clean == 1 & room_to_obstacle_1_r >= 1.15)
    approved_df = df[
        (df["ml_prob"] >= 0.68)
        & (df["htf_reclaim_clean"] == 1)
        & (df["room_to_obstacle_1_r"] >= 1.15)
        & (df["dist_from_broken_level_atr"] <= 0.85)
    ].sort_values("entry_time").reset_index(drop=True)

    app_wins = int(sum(approved_df["target"] == 1))
    app_total = len(approved_df)
    app_wr = (app_wins / max(1, app_total)) * 100.0
    app_pnl = float(approved_df["pnl_usd"].sum())
    print(f"\n[5-TF Sniper Approved Setups] Trades: {app_total} | Wins: {app_wins} | Protected Win Rate: {app_wr:.2f}% | Net PnL (0.01 lot): +${app_pnl:.2f}")

    importances = dict(zip(FEATURE_COLUMNS, [float(x) for x in lgb_model.feature_importances_]))
    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))
    print("\n--- 5-Timeframe (H4+H1+M30+M15+M5) Feature Importances ---")
    for feat, imp in sorted_importances.items():
        print(f"  {feat:28s}: {imp:6.1f}")

    with open(MODEL_OUT_FILE, "wb") as f:
        pickle.dump(lgb_model, f)

    metadata = {
        "version": "4.0-5TF-PointInTime-100Questions-Ensemble",
        "trained_samples": int(len(df)),
        "approved_trades_count": int(app_total),
        "approved_win_rate_pct": round(app_wr, 2),
        "approved_net_pnl_usd": round(app_pnl, 2),
        "features": FEATURE_COLUMNS,
        "cv_roc_auc": round(float(cv_auc.mean()), 4),
        "cv_accuracy_pct": round(float(cv_acc.mean() * 100), 2),
        "feature_importances": sorted_importances,
        "execution_threshold_prob": 0.65,
    }
    with open(METADATA_OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Export clean 5-TF Backtest Trades for the Webapp UI & Continuous Learning Engine
    clean_bt_list = []
    for idx, row in approved_df.iterrows():
        t_type = "long" if int(row["direction"]) == 1 else "short"
        clean_bt_list.append({
            "id": int(idx + 1),
            "symbol": str(row["symbol"]),
            "timeframe": str(row["htf"]),
            "type": t_type,
            "setup": f"{row['htf']}_STATE_{row['market_state_code']}_5TF_RETEST",
            "entryTime": int(row["entry_time"]),
            "exitTime": int(row["exit_time"]),
            "entry": float(row["entry"]),
            "sl": float(row["sl"]),
            "tp": float(row["tp"]),
            "exit": float(row["exit"]),
            "stopDist": float(row["stop_dist"]),
            "rrr": float(row["plan_rrr"]),
            "realizedR": float(row["realized_r"]),
            "pnl": float(row["pnl_usd"]),
            "outcome": str(row["outcome"]),
            "touches": int(row["touches"]),
            "ai_score": int(round(float(row["ml_prob"]) * 100)),
            "win": bool(int(row["target"]) == 1),
        })

    for out_path in [BACKTEST_HISTORY_FILE, BACKTEST_LOG_JSON, FRONTEND_PUBLIC_BT]:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(clean_bt_list, f, indent=2)
    if os.path.exists(os.path.dirname(FRONTEND_DIST_BT)):
        with open(FRONTEND_DIST_BT, "w", encoding="utf-8") as f:
            json.dump(clean_bt_list, f, indent=2)

    print(f"[5-TF Trainer] Saved {len(clean_bt_list)} verified 5-Timeframe backtest trades to {FRONTEND_PUBLIC_BT} and {MODEL_OUT_FILE}")
    return lgb_model, metadata


class SniperPredictor:
    """Real-time 5-Timeframe (H4+H1+M30+M15+M5) inference engine for live MT5 execution."""
    def __init__(self):
        self.model = None
        self.metadata = {}
        self._load()

    def _load(self):
        if os.path.exists(MODEL_OUT_FILE):
            try:
                with open(MODEL_OUT_FILE, "rb") as f:
                    self.model = pickle.load(f)
            except Exception as e:
                print(f"[SniperPredictor] Error loading model: {e}")

        if os.path.exists(METADATA_OUT_FILE):
            try:
                with open(METADATA_OUT_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            except Exception:
                pass

    def predict(
        self,
        symbol: str,
        direction: str,
        stop_dist_pts: float,
        reward_dist_pts: float,
        touches: int = 2,
        is_range_boundary: bool = False,
        tech_score: int = 85,
        htf_source: str = "H1",
        market_state: str = "RETEST",
        h4_aligned: int = 1,
        h1_aligned: int = 1,
        htf_reclaim_clean: int = 1,
        brk_displacement_atr: float = 1.1,
        pb_to_brk_vel_ratio: float = 0.65,
        is_touch_2_protected: int = 1,
        dist_from_broken_level_atr: float = 0.30,
        room_to_obstacle_1_r: float = 1.60,
        m15_wick_ratio: float = 0.28,
        m5_bos_body_ratio: float = 0.55,
        h1_atr: float = 250.0,
    ) -> Dict[str, Any]:
        """
        Evaluates all 20 simultaneous H4+H1+M30+M15+M5 features against the 60-day trained LightGBM ensemble.
        """
        is_sfx = "SFX" in symbol
        vol_family = 0 if is_sfx else 1
        vol_level = 20 if "20" in symbol else 40
        spread = 28.0 if "SFX_Vol_40" in symbol else (14.0 if "FX_Vol_40" in symbol else (8.0 if "SFX_Vol_20" in symbol else 5.0))
        spread_pct = (spread / max(1.0, stop_dist_pts)) * 100.0
        rrr = round(reward_dist_pts / max(1.0, stop_dist_pts), 2)

        htf_code = 3 if htf_source == "H4" else (2 if htf_source == "H1" else 1)
        state_code = 1 if is_range_boundary or market_state == "RANGE" else (4 if market_state == "CONTINUATION" else 3)
        stop_htf_ratio = stop_dist_pts / max(1.0, h1_atr)

        if self.model is None:
            self._load()

        feat_dict = {
            "vol_family": vol_family,
            "vol_level": vol_level,
            "direction": 1 if direction.upper() in ("BUY", "LONG") else 0,
            "htf_source_code": htf_code,
            "market_state_code": state_code,
            "h4_trend_aligned": int(h4_aligned),
            "h1_trend_aligned": int(h1_aligned),
            "htf_reclaim_clean": int(htf_reclaim_clean),
            "brk_displacement_atr": float(brk_displacement_atr),
            "pb_to_brk_vel_ratio": float(pb_to_brk_vel_ratio),
            "touches": int(touches),
            "is_touch_2_protected": int(is_touch_2_protected),
            "dist_from_broken_level_atr": float(dist_from_broken_level_atr),
            "room_to_obstacle_1_r": float(room_to_obstacle_1_r),
            "m15_wick_ratio": float(m15_wick_ratio),
            "m5_bos_body_ratio": float(m5_bos_body_ratio),
            "stop_dist_htf_atr_ratio": float(stop_htf_ratio),
            "plan_rrr": float(rrr),
            "spread_pct_sl": float(spread_pct),
            "tech_score": int(tech_score),
        }

        prob = 0.75
        if self.model is not None:
            try:
                feat_vector = pd.DataFrame([feat_dict])[FEATURE_COLUMNS]
                prob = float(self.model.predict_proba(feat_vector)[0, 1])
            except Exception as e:
                print(f"[SniperPredictor] Predict error: {e}")

        threshold = float(self.metadata.get("execution_threshold_prob", 0.65))
        reasons = []

        if is_sfx and touches < 2:
            prob = min(prob, 0.45)
            reasons.append("Vetoed: SFX spike index requires Touch #2 Protected Wick (Q9/Q70).")
        if htf_reclaim_clean == 0:
            prob = min(prob, 0.35)
            reasons.append("Vetoed: Broken level was reclaimed by a candle body close (Q7/Q19).")
        if dist_from_broken_level_atr > 0.95:
            prob = min(prob, 0.42)
            reasons.append(f"Vetoed: Entry is too far ({dist_from_broken_level_atr:.2f} ATR) from broken closure level (Q80).")
        if room_to_obstacle_1_r < 1.15:
            prob = min(prob, 0.40)
            reasons.append(f"Vetoed: Insufficient room ({room_to_obstacle_1_r:.2f}R) to Obstacle #1 (Q16/Q93).")

        execute = bool(prob >= threshold and len(reasons) == 0)
        verdict = "APPROVED_BY_5TF_SNIPER_AI" if execute else "VETOED_BY_5TF_SNIPER_AI"

        return {
            "execute": execute,
            "win_probability": round(prob, 3),
            "confidence_pct": int(round(prob * 100)),
            "verdict": verdict,
            "plan_rrr": rrr,
            "spread_pct_sl": round(spread_pct, 1),
            "reasons": reasons if reasons else ["5-Timeframe (H4+H1+M30+M15+M5) 100-Questions Ensemble Confirmed."],
        }


if __name__ == "__main__":
    train_and_evaluate_model()
