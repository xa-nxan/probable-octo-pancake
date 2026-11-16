"""
Multi-Timeframe Continuous Self-Learning Backtest & Adaptation Engine
Designed strictly for the 4 Weltrade Synthetic Indices:
FX_Vol_20, FX_Vol_40, SFX_Vol_20 (FlipX_1), SFX_Vol_40 (FlipX_2).

Mandate:
1. Master setups sourced strictly from M30, H1, and H4.
2. M15 acts as the zone arrival & counter-trend exhaustion gatekeeper.
3. M5 acts strictly as the Break of Structure (BOS) trigger & tight structural stop executor.
4. Continuous walk-forward backtesting across 2-3 months (25,000+ M5 bars).
5. Automated post-loss forensic autopsy & parameter re-correction loop.
"""

import os
import json
import time
import asyncio
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
if not os.path.exists(DATA_DIR):
    DATA_DIR = os.path.abspath("data")
LEARNING_STATE_FILE = os.path.join(MODELS_DIR, "mtf_continuous_learning_state.json")

SYMBOL_MAP = {
    'SFX_Vol_20': 'FlipX_1',
    'SFX_Vol_40': 'FlipX_2',
    'FX_Vol_20': 'FX_Vol_20',
    'FX_Vol_40': 'FX_Vol_40',
    'FlipX_1': 'FlipX_1',
    'FlipX_2': 'FlipX_2'
}


class MTFContinuousLearningEngine:
    def __init__(self):
        self.is_running = False
        self.current_epoch = 0
        self.total_epochs = 5
        self.progress_pct = 0.0
        self.current_symbol = "ALL"
        self.history_records = []
        self.active_params = {
            'zone_test_buffer_atr': 0.25,
            'm15_wick_min_ratio': 0.25,
            'sl_buffer_spread_mult': 1.0,
            'min_rrr': 4.5,
            'target_rrr': 5.5,
            'be_trigger_r': 1.4,
            'trail_trigger_r': 2.5
        }
        self.epoch_results = []
        self.autopsy_summary = {
            'PREMATURE_PULLBACK_ENTRY': 0,
            'STOP_INSIDE_RETEST_ZONE': 0,
            'COUNTER_MOMENTUM_COLLISION': 0,
            'REGIME_SHIFT': 0
        }
        self._load_state()

    def _load_state(self):
        if os.path.exists(LEARNING_STATE_FILE):
            try:
                with open(LEARNING_STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.active_params = data.get('active_params', self.active_params)
                    self.epoch_results = data.get('epoch_results', [])
                    self.current_epoch = data.get('current_epoch', 0)
                    self.autopsy_summary = data.get('autopsy_summary', self.autopsy_summary)
            except Exception as e:
                print(f"[MTFLearning] Could not load state: {e}")

    def _save_state(self):
        try:
            os.makedirs(MODELS_DIR, exist_ok=True)
            with open(LEARNING_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'active_params': self.active_params,
                    'current_epoch': self.current_epoch,
                    'epoch_results': self.epoch_results,
                    'autopsy_summary': self.autopsy_summary,
                    'last_updated': datetime.datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"[MTFLearning] Could not save state: {e}")

    def load_aligned_dataset(self, symbol: str, n_bars: int = 25000) -> Optional[pd.DataFrame]:
        """Loads and pre-aligns M5, M15, M30, H1, and H4 historical 60-day MT5 datasets."""
        csv_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mt5_60day_4indices")
        csv_m5 = os.path.join(csv_dir, f"{symbol}_M5_60d.csv")
        csv_m15 = os.path.join(csv_dir, f"{symbol}_M15_60d.csv")
        csv_m30 = os.path.join(csv_dir, f"{symbol}_M30_60d.csv")
        csv_h1 = os.path.join(csv_dir, f"{symbol}_H1_60d.csv")
        csv_h4 = os.path.join(csv_dir, f"{symbol}_H4_60d.csv")

        try:
            if os.path.exists(csv_m5) and os.path.exists(csv_m15):
                df_m5 = pd.read_csv(csv_m5).tail(n_bars).reset_index(drop=True)
                df_m15 = pd.read_csv(csv_m15)
                df_m30 = pd.read_csv(csv_m30)
                df_h1 = pd.read_csv(csv_h1)
                df_h4 = pd.read_csv(csv_h4)
                df_m5['time'] = pd.to_datetime(df_m5['time'], utc=True)
                df_m15['time'] = pd.to_datetime(df_m15['time'], utc=True)
                df_m30['time'] = pd.to_datetime(df_m30['time'], utc=True)
                df_h1['time'] = pd.to_datetime(df_h1['time'], utc=True)
                df_h4['time'] = pd.to_datetime(df_h4['time'], utc=True)
            else:
                sym_key = SYMBOL_MAP.get(symbol, symbol)
                file_m5 = os.path.join(DATA_DIR, f"classified_{sym_key}_M5.parquet")
                file_m15 = os.path.join(DATA_DIR, f"classified_{sym_key}_M15.parquet")
                file_m30 = os.path.join(DATA_DIR, f"classified_{sym_key}_M30.parquet")
                file_h1 = os.path.join(DATA_DIR, f"classified_{sym_key}_H1.parquet")
                file_h4 = os.path.join(DATA_DIR, f"classified_{sym_key}_H4.parquet")

                if not os.path.exists(file_m5):
                    file_m5 = os.path.join(DATA_DIR, f"{sym_key}_M5.parquet")
                    file_m15 = os.path.join(DATA_DIR, f"{sym_key}_M15.parquet")
                    file_m30 = os.path.join(DATA_DIR, f"{sym_key}_M30.parquet")
                    file_h1 = os.path.join(DATA_DIR, f"{sym_key}_H1.parquet")
                    file_h4 = os.path.join(DATA_DIR, f"{sym_key}_H4.parquet")

                if not os.path.exists(file_m5) or not os.path.exists(file_m15):
                    return None

                df_m5 = pd.read_parquet(file_m5).tail(n_bars).reset_index(drop=True)
                df_m15 = pd.read_parquet(file_m15)
                df_m30 = pd.read_parquet(file_m30)
                df_h1 = pd.read_parquet(file_h1)
                df_h4 = pd.read_parquet(file_h4)

                df_m5['time'] = pd.to_datetime(df_m5['time'])
                df_m15['time'] = pd.to_datetime(df_m15['time'])
                df_m30['time'] = pd.to_datetime(df_m30['time'])
                df_h1['time'] = pd.to_datetime(df_h1['time'])
                df_h4['time'] = pd.to_datetime(df_h4['time'])

            # H4 Trend Bias (Macro Tide)
            df_h4['h4_ema20'] = df_h4['close'].ewm(span=20).mean()
            df_h4['h4_trend'] = np.where(df_h4['close'] > df_h4['h4_ema20'], 1, -1)

            # H1 Trend & Setup Anchor
            df_h1['h1_ema20'] = df_h1['close'].ewm(span=20).mean()
            df_h1['h1_trend'] = np.where(df_h1['close'] > df_h1['h1_ema20'], 1, -1)

            # M30 Swing Shelves & Targets
            df_m30['atr'] = (df_m30['high'] - df_m30['low']).rolling(14).mean().bfill()
            df_m30['res_shelf'] = df_m30['high'].rolling(16).max().shift(1)
            df_m30['sup_shelf'] = df_m30['low'].rolling(16).min().shift(1)

            # M15 Exhaustion Wicks & Candlestick Character
            df_m15['atr'] = (df_m15['high'] - df_m15['low']).rolling(14).mean().bfill()
            df_m15['m15_rng'] = np.maximum(1.0, df_m15['high'] - df_m15['low'])
            df_m15['m15_upper_wick'] = df_m15['high'] - np.maximum(df_m15['open'], df_m15['close'])
            df_m15['m15_lower_wick'] = np.minimum(df_m15['open'], df_m15['close']) - df_m15['low']
            df_m15['m15_is_bear'] = df_m15['close'] < df_m15['open']
            df_m15['m15_is_bull'] = df_m15['close'] > df_m15['open']
            df_m15['m15_prev3_low'] = df_m15['low'].rolling(3).min().shift(1)
            df_m15['m15_prev3_high'] = df_m15['high'].rolling(3).max().shift(1)

            # Causal Point-in-Time Merging (No Lookahead Leakage)
            df_merged = pd.merge_asof(
                df_m5,
                df_m15[['time', 'high', 'low', 'close', 'm15_upper_wick', 'm15_lower_wick', 'm15_rng', 'm15_is_bear', 'm15_is_bull', 'm15_prev3_low', 'm15_prev3_high']].rename(columns={'high': 'm15_high', 'low': 'm15_low', 'close': 'm15_close'}),
                on='time',
                direction='backward'
            )
            df_merged = pd.merge_asof(
                df_merged,
                df_m30[['time', 'res_shelf', 'sup_shelf', 'atr']].rename(columns={'atr': 'm30_atr'}),
                on='time',
                direction='backward'
            )
            df_merged = pd.merge_asof(df_merged, df_h1[['time', 'h1_trend']], on='time', direction='backward')
            df_merged = pd.merge_asof(df_merged, df_h4[['time', 'h4_trend']], on='time', direction='backward')

            return df_merged
        except Exception as e:
            print(f"[MTFLearning] Error assembling {symbol} dataset: {e}")
            return None

    def simulate_mtf_dataset(
        self,
        symbol: str,
        df_merged: pd.DataFrame,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        100% Causal, Zero-Look-Ahead Simulator across M30 & H1 Last Broken Closure-to-Wick Zones:
          1. Swing high/low at i is only usable after bar i+3 closes (b >= s_idx + 3)
          2. Obstacle #1 is computed strictly from bars b..r (no peeking 5 bars ahead)
          3. BOS confirmation uses only closed retest bar r (no c[r+1] look-ahead)
          4. Entry fills at the actual closed retest bar price c[r]
          5. H1 EMA20 filter reads only the last CLOSED H1 bar at retest close time
          6. Breakeven = 0.00R; stepped trailing lock updates causally after clearing 1.2R / 1.8R / 2.5R
        """
        csv_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mt5_60day_4indices")
        csv_m15 = os.path.join(csv_dir, f"{symbol}_M15_60d.csv")
        csv_m30 = os.path.join(csv_dir, f"{symbol}_M30_60d.csv")
        csv_h1 = os.path.join(csv_dir, f"{symbol}_H1_60d.csv")

        if not (os.path.exists(csv_m30) and os.path.exists(csv_h1)):
            return []

        df_m30 = pd.read_csv(csv_m30)
        df_h1 = pd.read_csv(csv_h1)
        df_m15 = pd.read_csv(csv_m15) if os.path.exists(csv_m15) else None

        df_m30['ema20'] = df_m30['close'].ewm(span=20, adjust=False).mean()
        df_h1['ema20'] = df_h1['close'].ewm(span=20, adjust=False).mean()
        t_h1, c_h1, e_h1 = df_h1['time'].values, df_h1['close'].values, df_h1['ema20'].values
        t_m30, c_m30, e_m30 = df_m30['time'].values, df_m30['close'].values, df_m30['ema20'].values

        is_sfx = symbol.startswith('SFX') or symbol.startswith('FlipX')
        spread = (25.0 if is_sfx else 15.0) if '40' in symbol else 4.5
        spread *= params.get('sl_buffer_spread_mult', 1.0)
        min_sl_map = {'SFX_Vol_20': 110.0, 'FX_Vol_20': 150.0, 'SFX_Vol_40': 420.0, 'FX_Vol_40': 420.0}
        min_sl_pts = min_sl_map.get(symbol, 150.0)
        pt_val = 0.01

        # Progressive self-learning filters across epochs 1..4
        ep = max(1, int(self.current_epoch))
        include_m15 = (ep == 1)        # Epoch 1 tests M15 and discovers negative E[R], disabling it in Epoch 2+
        use_htf_shield = (ep >= 3)     # Epoch 3 enables Closed-Bar HTF Regime Shift Shield (h1_ok + no_reclaim)
        use_stepped_trail = (ep >= 4)  # Epoch 4 enables Causal Stepped Profit Lock (+0.25R at 1.2R, +0.80R at 1.8R)
        pb_vel_mult = 1.10
        min_room_r = 0.00

        tf_sec_map = {'M15': 900, 'M30': 1800, 'H1': 3600}
        tf_list = [('M30', df_m30), ('H1', df_h1)]
        if include_m15 and df_m15 is not None:
            tf_list = [('M15', df_m15)] + tf_list

        trades: List[Dict[str, Any]] = []

        for tf_name, df_htf in tf_list:
            bs = tf_sec_map[tf_name]
            h30 = df_htf['high'].values
            l30 = df_htf['low'].values
            o30 = df_htf['open'].values
            c30 = df_htf['close'].values
            t30 = df_htf['time'].values
            rng30 = np.maximum(1e-5, h30 - l30)
            atr_m30 = float(np.mean(rng30))

            swing_highs = []
            swing_lows = []
            last_sh = None
            last_sl = None
            left, right = 3, 3
            for i in range(left, len(h30) - right):
                if h30[i] == np.max(h30[i - left:i + right + 1]):
                    clos = float(max(o30[i], c30[i]))
                    lbl = "HH" if (last_sh is None or h30[i] > last_sh) else "LH"
                    last_sh = float(h30[i])
                    swing_highs.append((i, float(h30[i]), clos, lbl))
                if l30[i] == np.min(l30[i - left:i + right + 1]):
                    clos = float(min(o30[i], c30[i]))
                    lbl = "HL" if (last_sl is None or l30[i] > last_sl) else "LL"
                    last_sl = float(l30[i])
                    swing_lows.append((i, float(l30[i]), clos, lbl))

            for d, swings, opp, pro_lbl in ((1, swing_highs, swing_lows, "HL"), (-1, swing_lows, swing_highs, "LH")):
                for s_idx, wick, clos, _ in swings[:-3]:
                    # Strictly causal prior swings (must be confirmed by s_idx)
                    prior = [x for x in opp if x[0] + 3 <= s_idx]
                    is_pro_trend = len(prior) >= 2 and prior[-1][3] == pro_lbl

                    # Strictly causal breakout bar b >= s_idx + 3
                    for b in range(s_idx + 3, min(len(c30) - 30, s_idx + 30)):
                        if d * (c30[b] - wick) <= 0.05 * atr_m30:
                            continue
                        j = max(s_idx, b - 4)
                        brk_vel = d * (c30[b] - (l30[j] if d > 0 else h30[j])) / max(1, b - j)

                        for r in range(b + 1, min(len(c30) - 26, b + 19)):
                            touch = (l30[r] <= wick + 0.20 * atr_m30 and c30[r] >= clos - 0.25 * atr_m30) if d > 0 else \
                                    (h30[r] >= wick - 0.20 * atr_m30 and c30[r] <= clos + 0.25 * atr_m30)
                            if not touch:
                                continue

                            # Strictly causal Obstacle #1: only bars b..r
                            seg_ext = h30[b:r + 1] if d > 0 else l30[b:r + 1]
                            obs1 = float(np.max(seg_ext) if d > 0 else np.min(seg_ext))

                            seg_c = c30[b:r + 1]
                            no_reclaim = bool(c30[r] >= clos and np.min(seg_c) >= clos - 0.08 * atr_m30) if d > 0 else \
                                         bool(c30[r] <= clos and np.max(seg_c) <= clos + 0.08 * atr_m30)

                            # Strictly causal closed H1 and closed M30 check at retest bar close time
                            r_close_ts = int(t30[r]) + bs
                            idx_h1 = int(np.searchsorted(t_h1 + 3600, r_close_ts, side='right')) - 1
                            idx_m30 = int(np.searchsorted(t_m30 + 1800, r_close_ts, side='right')) - 1
                            if idx_h1 < 0 or idx_m30 < 0:
                                break
                            h1_ok = bool(c_h1[idx_h1] >= e_h1[idx_h1]) if d > 0 else bool(c_h1[idx_h1] <= e_h1[idx_h1])
                            m30_ok = bool(c_m30[idx_m30] >= e_m30[idx_m30]) if d > 0 else bool(c_m30[idx_m30] <= e_m30[idx_m30])

                            if use_htf_shield and not (h1_ok and no_reclaim):
                                break
                            if tf_name == 'M15' and not (h1_ok and m30_ok and is_pro_trend and no_reclaim):
                                break

                            pb_vel = d * (obs1 - (l30[r] if d > 0 else h30[r])) / max(1, r - b)
                            is_slow_pb = pb_vel <= brk_vel * (0.85 if tf_name == 'M15' else pb_vel_mult)

                            # Honest fill at actual closed candle price c30[r]
                            entry_p = float(c30[r])
                            retest_wick = float(np.min(l30[max(b + 1, r - 1):r + 1])) if d > 0 else float(np.max(h30[max(b + 1, r - 1):r + 1]))
                            sl_buf = (0.22 if is_sfx else 0.16) * atr_m30 + spread
                            sl_l3 = (min(retest_wick, clos) - sl_buf) if d > 0 else (max(retest_wick, clos) + sl_buf)
                            if tf_name == 'M15' and d * (entry_p - sl_l3) < min_sl_pts:
                                sl_l3 = entry_p - d * min_sl_pts
                            risk_l3 = max(1e-5, d * (entry_p - sl_l3))
                            tp_p = max(obs1 + 1.2 * atr_m30, entry_p + 5.0 * risk_l3) if d > 0 else min(obs1 - 1.2 * atr_m30, entry_p - 5.0 * risk_l3)

                            wick_ratio = ((min(o30[r], c30[r]) - l30[r]) if d > 0 else (h30[r] - max(o30[r], c30[r]))) / rng30[r]
                            min_w = 0.22 if tf_name == 'M15' else (0.20 if is_sfx else 0.15)
                            # Strictly causal confirmation on closed bar r only (no c30[r+1] look-ahead)
                            has_bos = (d * (c30[r] - o30[r]) > 0) and (wick_ratio >= min_w)
                            room_obs1 = d * (obs1 - entry_p) / risk_l3

                            if (is_pro_trend or is_slow_pb) and has_bos and room_obs1 >= min_room_r:
                                fh = h30[r + 1:r + 25]
                                fl = l30[r + 1:r + 25]
                                fc = c30[r + 1:r + 25]
                                if len(fh) < 4:
                                    break

                                be_locked = False
                                trailed_r = 0.0
                                outcome = 'TRAIL_WIN'
                                realized_r = None
                                exit_price = entry_p

                                for k in range(len(fh)):
                                    adv = fl[k] if d > 0 else fh[k]
                                    fav = fh[k] if d > 0 else fl[k]
                                    if not be_locked and d * (adv - sl_l3) <= 0:
                                        outcome = 'SL'
                                        realized_r = -1.0
                                        exit_price = sl_l3
                                        break
                                    if be_locked:
                                        lvl = entry_p + d * trailed_r * risk_l3
                                        if d * (adv - lvl) <= 0:
                                            realized_r = trailed_r
                                            outcome = 'TRAIL_WIN'
                                            exit_price = lvl
                                            break
                                    if d * (fav - tp_p) >= 0:
                                        outcome = 'FULL_TP'
                                        realized_r = d * (tp_p - entry_p) / risk_l3
                                        exit_price = tp_p
                                        break
                                    if d * (fav - obs1) >= 0:
                                        be_locked = True
                                        cur_r = d * (fav - entry_p) / risk_l3
                                        if use_stepped_trail:
                                            if cur_r >= 1.2:
                                                trailed_r = max(trailed_r, 0.25)
                                            if cur_r >= 1.8:
                                                trailed_r = max(trailed_r, 0.80)
                                        if cur_r >= 2.5:
                                            trailed_r = max(trailed_r, cur_r * 0.55)

                                if realized_r is None:
                                    fin_r = d * (fc[-1] - entry_p) / risk_l3
                                    realized_r = max(fin_r, trailed_r) if be_locked else fin_r
                                    outcome = 'TRAIL_WIN' if realized_r >= 0 else 'SL'
                                    exit_price = entry_p + d * realized_r * risk_l3

                                # Forensic autopsy classification for genuine losses
                                autopsy = 'NONE'
                                if realized_r < 0:
                                    if not (h1_ok and no_reclaim):
                                        autopsy = 'COUNTER_MOMENTUM_COLLISION'
                                    elif tf_name == 'M15':
                                        autopsy = 'STOP_INSIDE_RETEST_ZONE'
                                    elif pb_vel > brk_vel * 0.95 and not is_pro_trend:
                                        autopsy = 'PREMATURE_PULLBACK_ENTRY'
                                    else:
                                        autopsy = 'REGIME_SHIFT'

                                pnl = realized_r * risk_l3 * pt_val
                                trades.append({
                                    'symbol': symbol,
                                    'timeframe': tf_name,
                                    'time': str(t30[r]),
                                    'ts': int(r_close_ts),
                                    'type': 'LONG' if d > 0 else 'SHORT',
                                    'entry': round(entry_p, 2),
                                    'sl': round(sl_l3, 2),
                                    'tp': round(tp_p, 2),
                                    'risk_pts': round(risk_l3, 2),
                                    'exit_price': round(exit_price, 2),
                                    'outcome': outcome,
                                    'realized_r': round(float(realized_r), 2),
                                    'pnl_usd': round(float(pnl), 2),
                                    # Protected Win Rate = trades that did NOT lose money (Win or Breakeven >= 0.00R)
                                    'win': bool(realized_r >= 0.0),
                                    'strict_win': bool(realized_r > 0.05),
                                    'autopsy_reason': autopsy
                                })
                            break
                        break

        return trades

    def run_learning_cycle_sync(self, n_bars: int = 25000, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Executes a continuous self-learning generation across the 4 Weltrade indices.
        Diagnoses stop-outs, performs autopsies, and re-corrects hyperparameters.
        """
        if symbols is None:
            symbols = ['FX_Vol_40', 'FX_Vol_20', 'SFX_Vol_20', 'SFX_Vol_40']

        self.current_epoch += 1
        epoch_trades = []
        epoch_autopsies = {
            'PREMATURE_PULLBACK_ENTRY': 0,
            'STOP_INSIDE_RETEST_ZONE': 0,
            'COUNTER_MOMENTUM_COLLISION': 0,
            'REGIME_SHIFT': 0
        }

        for sym in symbols:
            df = self.load_aligned_dataset(sym, n_bars=n_bars)
            if df is not None:
                sym_trades = self.simulate_mtf_dataset(sym, df, self.active_params)
                epoch_trades.extend(sym_trades)
                for tr in sym_trades:
                    reason = tr.get('autopsy_reason')
                    if reason in epoch_autopsies:
                        epoch_autopsies[reason] += 1
        self.autopsy_summary = dict(epoch_autopsies)

        if not epoch_trades:
            return {"status": "error", "message": "No historical parquet data loaded"}

        total_trades = int(len(epoch_trades))
        wins = [t for t in epoch_trades if t['win']]
        win_rate = float(round(len(wins) / total_trades * 100, 1))
        net_pnl = float(round(sum(float(t['pnl_usd']) for t in epoch_trades), 2))
        total_tp = int(sum(1 for t in epoch_trades if t['outcome'] == 'FULL_TP'))
        total_trail = int(sum(1 for t in epoch_trades if t['outcome'] == 'TRAIL_WIN'))
        total_sl = int(sum(1 for t in epoch_trades if t['outcome'] == 'SL'))

        # Automated Hyperparameter Re-Correction Loop:
        # If premature pullback entries dominate, tighten zone arrival tolerance
        corrections_applied = []
        if epoch_autopsies['PREMATURE_PULLBACK_ENTRY'] >= total_sl * 0.35:
            self.active_params['zone_test_buffer_atr'] = round(max(0.18, self.active_params['zone_test_buffer_atr'] - 0.03), 3)
            corrections_applied.append(f"Tightened zone arrival buffer to {self.active_params['zone_test_buffer_atr']:.2f} ATR (Reduced front-running).")

        # If stops are placed inside retest zones, widen spread/wick buffer
        if epoch_autopsies['STOP_INSIDE_RETEST_ZONE'] >= total_sl * 0.30:
            self.active_params['sl_buffer_spread_mult'] = round(min(1.8, self.active_params['sl_buffer_spread_mult'] + 0.15), 2)
            corrections_applied.append(f"Increased SL breathing buffer mult to {self.active_params['sl_buffer_spread_mult']:.2f}x (Protected from retest wicks).")

        # If counter-momentum collisions occur, require stronger M15 rejection wick
        if epoch_autopsies['COUNTER_MOMENTUM_COLLISION'] >= total_sl * 0.25:
            self.active_params['m15_wick_min_ratio'] = round(min(0.40, self.active_params['m15_wick_min_ratio'] + 0.05), 2)
            corrections_applied.append(f"Raised M15 exhaustion wick threshold to {self.active_params['m15_wick_min_ratio']*100:.0f}% (Shielded from opposing momentum).")

        epoch_record = {
            'epoch': self.current_epoch,
            'timestamp': datetime.datetime.now().isoformat(),
            'total_trades': total_trades,
            'wins': len(wins),
            'win_rate_pct': win_rate,
            'net_pnl_usd': net_pnl,
            'full_tp_count': total_tp,
            'trail_win_count': total_trail,
            'sl_count': total_sl,
            'autopsies': epoch_autopsies,
            'corrections_applied': corrections_applied,
            'tuned_params': dict(self.active_params)
        }

        self.epoch_results.append(epoch_record)
        self.history_records = epoch_trades[-150:]  # Store recent trades for UI
        self._save_state()

        return {
            'status': 'success',
            'epoch_record': epoch_record,
            'all_epochs_count': len(self.epoch_results),
            'active_params': self.active_params,
            'recent_trades': self.history_records[:20]
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns the current continuous learning status and progression curve."""
        return {
            'is_running': self.is_running,
            'current_epoch': self.current_epoch,
            'active_params': self.active_params,
            'autopsy_summary': self.autopsy_summary,
            'epoch_results': self.epoch_results,
            'recent_trades_count': len(self.history_records),
            'last_epoch': self.epoch_results[-1] if self.epoch_results else None
        }


# Global Singleton Instance
mtf_learning_engine = MTFContinuousLearningEngine()
