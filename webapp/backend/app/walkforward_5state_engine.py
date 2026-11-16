"""
Walk-Forward 5-State Strategy Engine & Real-Time WebSocket Simulator
Simulates real-time market execution without lookahead bias across Weltrade Synthetic Indices.
Detects:
1. Resistance / Support Consolidation Base
2. Breakout Impulse
3. Retest Pullback
4. Continuation Shelf (M5 trigger with protected rejection wick)
5. Reversal / Invalidation
"""

import os
import asyncio
import time
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from app.market_hub import market_hub

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data")
if not os.path.exists(DATA_DIR):
    DATA_DIR = os.path.abspath("data")

SYMBOL_PARAMS = {
    'FX_Vol_20': {'spread': 4.5, 'pt_val': 0.01, 'min_sl': 20.0, 'max_sl': 85.0, 'target_rrr': 4.0},
    'FX_Vol_40': {'spread': 14.0, 'pt_val': 0.01, 'min_sl': 35.0, 'max_sl': 110.0, 'target_rrr': 4.0},
    'SFX_Vol_20': {'spread': 4.0, 'pt_val': 0.01, 'min_sl': 15.0, 'max_sl': 75.0, 'target_rrr': 4.0},
    'SFX_Vol_40': {'spread': 12.0, 'pt_val': 0.01, 'min_sl': 30.0, 'max_sl': 95.0, 'target_rrr': 4.0},
}

class WalkForward5StateEngine:
    def __init__(self):
        self.status = "idle"  # "idle", "running", "paused", "completed"
        self.symbol = "FX_Vol_20"
        self.date_from = "2026-01-01"
        self.date_to = "2026-03-31"
        self.speed_ms = 40  # delay in ms per candle (40ms = 25 candles/sec)
        self.cancel_requested = False
        self.pause_requested = False
        self.active_task = None
        
        # State tracking
        self.current_sim_time = 0
        self.current_state_label = "Scanning Structure..."
        self.trades: List[Dict[str, Any]] = []
        self.active_trade: Optional[Dict[str, Any]] = None
        self.active_boxes: List[Dict[str, Any]] = []
        
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "net_pnl_usd": 0.0,
            "net_r": 0.0,
            "profit_factor": 0.0,
            "avg_sl_pts": 0.0,
            "progress_pct": 0.0
        }

    def stop(self):
        self.cancel_requested = True
        self.status = "idle"

    def pause(self):
        self.pause_requested = True
        self.status = "paused"

    def resume(self):
        self.pause_requested = False
        self.status = "running"

    def set_speed(self, delay_ms: int):
        self.speed_ms = max(5, min(2000, delay_ms))

    async def start(self, symbol: str, date_from: str = "2026-01-01", date_to: str = "2026-03-31", speed_ms: int = 40):
        if self.status == "running":
            self.stop()
            await asyncio.sleep(0.2)

        self.symbol = symbol
        self.date_from = date_from
        self.date_to = date_to
        self.speed_ms = speed_ms
        self.cancel_requested = False
        self.pause_requested = False
        self.status = "running"
        self.trades = []
        self.active_trade = None
        self.active_boxes = []
        self.stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "net_pnl_usd": 0.0,
            "net_r": 0.0,
            "profit_factor": 0.0,
            "avg_sl_pts": 0.0,
            "progress_pct": 0.0
        }

        self.active_task = asyncio.create_task(self._run_walkforward_loop())
        return {"status": "started", "symbol": symbol, "date_from": date_from, "date_to": date_to}

    def _load_datasets(self):
        sym_key = self.symbol
        parquet_sym = 'FlipX_1' if 'SFX_Vol_20' in sym_key else ('FlipX_2' if 'SFX_Vol_40' in sym_key else sym_key)
        
        m5_file = os.path.join(DATA_DIR, f"{parquet_sym}_M5.parquet")
        if not os.path.exists(m5_file):
            m5_file = os.path.join(DATA_DIR, f"classified_{parquet_sym}_M5.parquet")
        
        h1_file = os.path.join(DATA_DIR, f"{parquet_sym}_H1.parquet")
        if not os.path.exists(h1_file):
            h1_file = os.path.join(DATA_DIR, f"classified_{parquet_sym}_H1.parquet")

        df_m5 = pd.read_parquet(m5_file)
        df_m5['time'] = pd.to_datetime(df_m5['time'])
        df_m5 = df_m5.sort_values('time').reset_index(drop=True)
        
        mask = (df_m5['time'] >= self.date_from) & (df_m5['time'] <= self.date_to + " 23:59:59")
        df_m5_window = df_m5[mask].reset_index(drop=True)

        df_h1 = pd.read_parquet(h1_file)
        df_h1['time'] = pd.to_datetime(df_h1['time'])
        df_h1 = df_h1.sort_values('time').reset_index(drop=True)
        
        # Pre-warm H1 from 15 days prior to start date
        d_start_dt = pd.to_datetime(self.date_from) - pd.Timedelta(days=15)
        df_h1_window = df_h1[(df_h1['time'] >= d_start_dt) & (df_h1['time'] <= self.date_to + " 23:59:59")].reset_index(drop=True)

        df_h1_window['tr'] = np.maximum(
            df_h1_window['high'] - df_h1_window['low'],
            np.maximum(
                abs(df_h1_window['high'] - df_h1_window['close'].shift(1)),
                abs(df_h1_window['low'] - df_h1_window['close'].shift(1))
            )
        )
        df_h1_window['atr'] = df_h1_window['tr'].rolling(14).mean().fillna(80.0)

        return df_m5_window, df_h1_window

    async def _run_walkforward_loop(self):
        try:
            df_m5, df_h1 = self._load_datasets()
        except Exception as e:
            print(f"[WalkForward] Dataset load error: {e}")
            self.status = "error"
            return

        total_bars = len(df_m5)
        if total_bars == 0:
            print("[WalkForward] No bars found in selected date range.")
            self.status = "error"
            return

        params = SYMBOL_PARAMS.get(self.symbol, SYMBOL_PARAMS['FX_Vol_20'])
        spread = params['spread']
        pt_val = params['pt_val']
        min_sl = params['min_sl']
        max_sl = params['max_sl']
        target_rrr = params['target_rrr']

        m5_times = df_m5['time'].values
        m5_opens = df_m5['open'].values
        m5_highs = df_m5['high'].values
        m5_lows = df_m5['low'].values
        m5_closes = df_m5['close'].values
        m5_volumes = df_m5['volume'].values if 'volume' in df_m5.columns else np.ones(total_bars)

        h1_times = df_h1['time'].values
        h1_opens = df_h1['open'].values
        h1_highs = df_h1['high'].values
        h1_lows = df_h1['low'].values
        h1_closes = df_h1['close'].values
        h1_atrs = df_h1['atr'].values
        num_h1 = len(df_h1)

        h1_ptr = 0
        last_trade_time = np.datetime64('2020-01-01')

        print(f"[WalkForward] Starting real-time WebSocket walk-forward for {self.symbol}: {total_bars:,} bars...")

        # Broadcast initial walkforward start notification
        await market_hub.broadcast_all({
            "type": "walkforward_event",
            "action": "started",
            "symbol": self.symbol,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "total_bars": total_bars
        })

        for i in range(10, total_bars):
            if self.cancel_requested:
                print("[WalkForward] Replay stopped by user.")
                self.status = "idle"
                await market_hub.broadcast_all({"type": "walkforward_event", "action": "stopped"})
                return

            while self.pause_requested:
                await asyncio.sleep(0.1)
                if self.cancel_requested:
                    self.status = "idle"
                    return

            t_curr = m5_times[i]
            t_sec = int(pd.to_datetime(t_curr).timestamp())
            o_curr = float(m5_opens[i])
            h_curr = float(m5_highs[i])
            l_curr = float(m5_lows[i])
            c_curr = float(m5_closes[i])
            v_curr = float(m5_volumes[i])

            self.current_sim_time = t_sec
            self.stats["progress_pct"] = round((i / total_bars) * 100.0, 1)

            # 1. Update H1 closed-bar pointer strictly point-in-time
            while h1_ptr < num_h1 and h1_times[h1_ptr] + np.timedelta64(1, 'h') <= t_curr:
                h1_ptr += 1

            # 2. Check active trade outcome intrabar (Zero lookahead)
            if self.active_trade is not None:
                tr = self.active_trade
                if tr['direction'] == 'BUY':
                    if l_curr <= tr['sl']:
                        loss_pts = tr['entry'] - tr['sl']
                        tr['exit_time'] = t_sec
                        tr['exit_price'] = tr['sl']
                        tr['outcome'] = 'SL'
                        tr['pnl'] = round(-loss_pts * pt_val, 2)
                        tr['r_realized'] = -1.0
                        self.trades.append(tr)
                        self._update_stats_on_close(tr)
                        self.active_trade = None
                        await market_hub.broadcast_all({
                            "type": "walkforward_trade",
                            "action": "closed",
                            "trade": tr,
                            "stats": self.stats
                        })
                    elif h_curr >= tr['tp']:
                        win_pts = tr['tp'] - tr['entry']
                        tr['exit_time'] = t_sec
                        tr['exit_price'] = tr['tp']
                        tr['outcome'] = 'FULL_TP'
                        tr['pnl'] = round(win_pts * pt_val, 2)
                        tr['r_realized'] = tr['target_rrr']
                        self.trades.append(tr)
                        self._update_stats_on_close(tr)
                        self.active_trade = None
                        await market_hub.broadcast_all({
                            "type": "walkforward_trade",
                            "action": "closed",
                            "trade": tr,
                            "stats": self.stats
                        })
                    elif h_curr >= tr['entry'] + 2.5 * tr['sl_dist']:
                        new_sl = round(tr['entry'] + 1.0 * tr['sl_dist'], 2)
                        if new_sl > tr['sl']:
                            tr['sl'] = new_sl
                            await market_hub.broadcast_all({
                                "type": "walkforward_trade",
                                "action": "updated",
                                "trade": tr
                            })
                else: # SELL
                    if h_curr >= tr['sl']:
                        loss_pts = tr['sl'] - tr['entry']
                        tr['exit_time'] = t_sec
                        tr['exit_price'] = tr['sl']
                        tr['outcome'] = 'SL'
                        tr['pnl'] = round(-loss_pts * pt_val, 2)
                        tr['r_realized'] = -1.0
                        self.trades.append(tr)
                        self._update_stats_on_close(tr)
                        self.active_trade = None
                        await market_hub.broadcast_all({
                            "type": "walkforward_trade",
                            "action": "closed",
                            "trade": tr,
                            "stats": self.stats
                        })
                    elif l_curr <= tr['tp']:
                        win_pts = tr['entry'] - tr['tp']
                        tr['exit_time'] = t_sec
                        tr['exit_price'] = tr['tp']
                        tr['outcome'] = 'FULL_TP'
                        tr['pnl'] = round(win_pts * pt_val, 2)
                        tr['r_realized'] = tr['target_rrr']
                        self.trades.append(tr)
                        self._update_stats_on_close(tr)
                        self.active_trade = None
                        await market_hub.broadcast_all({
                            "type": "walkforward_trade",
                            "action": "closed",
                            "trade": tr,
                            "stats": self.stats
                        })
                    elif l_curr <= tr['entry'] - 2.5 * tr['sl_dist']:
                        new_sl = round(tr['entry'] - 1.0 * tr['sl_dist'], 2)
                        if new_sl < tr['sl']:
                            tr['sl'] = new_sl
                            await market_hub.broadcast_all({
                                "type": "walkforward_trade",
                                "action": "updated",
                                "trade": tr
                            })

            # 3. 5-State Detection Machine evaluation
            if self.active_trade is None and h1_ptr >= 16 and (t_curr - last_trade_time >= np.timedelta64(75, 'm')):
                # State 1: Base Detection (13 closed bars preceding the breakout)
                base_start_time = int(pd.to_datetime(h1_times[h1_ptr - 16]).timestamp())
                base_end_time = int(pd.to_datetime(h1_times[h1_ptr - 3]).timestamp())
                base_high = float(np.max(h1_highs[h1_ptr - 16 : h1_ptr - 3]))
                base_low = float(np.min(h1_lows[h1_ptr - 16 : h1_ptr - 3]))
                base_range = base_high - base_low
                h1_atr = float(h1_atrs[h1_ptr - 1])

                # State 2: Breakout Bar
                bk_time = int(pd.to_datetime(h1_times[h1_ptr - 3]).timestamp())
                bk_o = float(h1_opens[h1_ptr - 3])
                bk_c = float(h1_closes[h1_ptr - 3])
                bk_h = float(h1_highs[h1_ptr - 3])
                bk_l = float(h1_lows[h1_ptr - 3])

                # State 3: Retest Bars
                retest_start = int(pd.to_datetime(h1_times[h1_ptr - 2]).timestamp())
                retest_end = t_sec
                retest_high = float(np.max(h1_highs[h1_ptr - 2 : h1_ptr]))
                retest_low = float(np.min(h1_lows[h1_ptr - 2 : h1_ptr]))

                if 1.0 * h1_atr <= base_range <= 4.2 * h1_atr:
                    # Bullish 5-State Sequence
                    if bk_c > base_high + 0.15 * h1_atr and bk_c > bk_o:
                        self.current_state_label = f"State 2: Bullish Breakout above {base_high:.2f}"
                        broken_level = base_high
                        if broken_level - 0.40 * h1_atr <= retest_low <= broken_level + 0.50 * h1_atr:
                            self.current_state_label = f"State 3: Retesting Broken Resistance at {broken_level:.2f}"
                            
                            # State 4: Continuation Shelf check on M5
                            m5_prev_o = float(m5_opens[i-1])
                            m5_prev_c = float(m5_closes[i-1])
                            m5_prev_l = float(m5_lows[i-1])
                            body = abs(m5_prev_c - m5_prev_o)
                            lower_wick = min(m5_prev_o, m5_prev_c) - m5_prev_l
                            
                            m5_recent_lows = m5_lows[i-5:i-1]
                            is_hl = m5_prev_l >= np.min(m5_recent_lows)
                            
                            if (lower_wick >= 0.7 * body or m5_prev_c > m5_prev_o) and m5_prev_l >= broken_level - 0.28 * h1_atr and m5_prev_c >= broken_level and is_hl:
                                self.current_state_label = f"State 4: Continuation Shelf Formed! (BUY Triggered)"
                                entry = round(m5_prev_c + spread, 2)
                                sl_raw = round(float(np.min(m5_lows[i-5:i])) - spread, 2)
                                sl_dist = round(entry - sl_raw, 2)
                                
                                if min_sl <= sl_dist <= max_sl:
                                    tp = round(entry + target_rrr * sl_dist, 2)
                                    tr_obj = {
                                        'id': f"wf_tr_{len(self.trades) + 1}",
                                        'symbol': self.symbol,
                                        'direction': 'BUY',
                                        'type': 'long-position',
                                        'entry_time': t_sec,
                                        'entry': entry,
                                        'sl': sl_raw,
                                        'tp': tp,
                                        'sl_dist': sl_dist,
                                        'profit_dist': round(target_rrr * sl_dist, 2),
                                        'target_rrr': target_rrr,
                                        'broken_level': broken_level
                                    }
                                    self.active_trade = tr_obj
                                    last_trade_time = t_curr

                                    # Build 5-State Visual Boxes matching user's exact colors!
                                    self.active_boxes = [
                                        {
                                            "id": f"box_res_{t_sec}",
                                            "label": "Resistance",
                                            "startTime": base_start_time,
                                            "endTime": base_end_time,
                                            "priceHigh": base_high,
                                            "priceLow": base_low,
                                            "borderColor": "#ffffff",
                                            "fillColor": "#ffffff",
                                            "transparency": 85
                                        },
                                        {
                                            "id": f"box_bk_{t_sec}",
                                            "label": "Breakout",
                                            "startTime": bk_time,
                                            "endTime": retest_start,
                                            "priceHigh": max(bk_h, bk_c),
                                            "priceLow": min(bk_l, base_high),
                                            "borderColor": "#ffffff",
                                            "fillColor": "#b2b5be",
                                            "transparency": 75
                                        },
                                        {
                                            "id": f"box_ret_{t_sec}",
                                            "label": "Retest",
                                            "startTime": retest_start,
                                            "endTime": t_sec,
                                            "priceHigh": max(bk_c, retest_high),
                                            "priceLow": min(broken_level, retest_low),
                                            "borderColor": "#ab47bc",
                                            "fillColor": "#9c27b0",
                                            "transparency": 70
                                        },
                                        {
                                            "id": f"box_cont_{t_sec}",
                                            "label": "Continuation Shelf",
                                            "startTime": int(pd.to_datetime(m5_times[i-5]).timestamp()),
                                            "endTime": t_sec + 3600 * 3,
                                            "priceHigh": round(entry + sl_dist, 2),
                                            "priceLow": sl_raw,
                                            "borderColor": "#089981",
                                            "fillColor": "#089981",
                                            "transparency": 85
                                        }
                                    ]

                                    await market_hub.broadcast_all({
                                        "type": "walkforward_boxes",
                                        "boxes": self.active_boxes
                                    })
                                    await market_hub.broadcast_all({
                                        "type": "walkforward_trade",
                                        "action": "opened",
                                        "trade": tr_obj
                                    })

                    # Bearish 5-State Sequence
                    elif bk_c < base_low - 0.15 * h1_atr and bk_c < bk_o:
                        self.current_state_label = f"State 2: Bearish Breakout below {base_low:.2f}"
                        broken_level = base_low
                        if broken_level - 0.50 * h1_atr <= retest_high <= broken_level + 0.40 * h1_atr:
                            self.current_state_label = f"State 3: Retesting Broken Support at {broken_level:.2f}"
                            m5_prev_o = float(m5_opens[i-1])
                            m5_prev_c = float(m5_closes[i-1])
                            m5_prev_h = float(m5_highs[i-1])
                            body = abs(m5_prev_c - m5_prev_o)
                            upper_wick = m5_prev_h - max(m5_prev_o, m5_prev_c)
                            
                            m5_recent_highs = m5_highs[i-5:i-1]
                            is_lh = m5_prev_h <= np.max(m5_recent_highs)
                            
                            if (upper_wick >= 0.7 * body or m5_prev_c < m5_prev_o) and m5_prev_h <= broken_level + 0.28 * h1_atr and m5_prev_c <= broken_level and is_lh:
                                self.current_state_label = f"State 4: Continuation Shelf Formed! (SELL Triggered)"
                                entry = round(m5_prev_c - spread, 2)
                                sl_raw = round(float(np.max(m5_highs[i-5:i])) + spread, 2)
                                sl_dist = round(sl_raw - entry, 2)
                                
                                if min_sl <= sl_dist <= max_sl:
                                    tp = round(entry - target_rrr * sl_dist, 2)
                                    tr_obj = {
                                        'id': f"wf_tr_{len(self.trades) + 1}",
                                        'symbol': self.symbol,
                                        'direction': 'SELL',
                                        'type': 'short-position',
                                        'entry_time': t_sec,
                                        'entry': entry,
                                        'sl': sl_raw,
                                        'tp': tp,
                                        'sl_dist': sl_dist,
                                        'profit_dist': round(target_rrr * sl_dist, 2),
                                        'target_rrr': target_rrr,
                                        'broken_level': broken_level
                                    }
                                    self.active_trade = tr_obj
                                    last_trade_time = t_curr

                                    self.active_boxes = [
                                        {
                                            "id": f"box_res_{t_sec}",
                                            "label": "Resistance Base",
                                            "startTime": base_start_time,
                                            "endTime": base_end_time,
                                            "priceHigh": base_high,
                                            "priceLow": base_low,
                                            "borderColor": "#ffffff",
                                            "fillColor": "#ffffff",
                                            "transparency": 85
                                        },
                                        {
                                            "id": f"box_bk_{t_sec}",
                                            "label": "Breakout",
                                            "startTime": bk_time,
                                            "endTime": retest_start,
                                            "priceHigh": max(bk_h, base_low),
                                            "priceLow": min(bk_l, bk_c),
                                            "borderColor": "#ffffff",
                                            "fillColor": "#b2b5be",
                                            "transparency": 75
                                        },
                                        {
                                            "id": f"box_ret_{t_sec}",
                                            "label": "Retest",
                                            "startTime": retest_start,
                                            "endTime": t_sec,
                                            "priceHigh": max(retest_high, broken_level),
                                            "priceLow": min(bk_c, retest_low),
                                            "borderColor": "#ab47bc",
                                            "fillColor": "#9c27b0",
                                            "transparency": 70
                                        },
                                        {
                                            "id": f"box_cont_{t_sec}",
                                            "label": "Continuation Shelf",
                                            "startTime": int(pd.to_datetime(m5_times[i-5]).timestamp()),
                                            "endTime": t_sec + 3600 * 3,
                                            "priceHigh": sl_raw,
                                            "priceLow": round(entry - sl_dist, 2),
                                            "borderColor": "#f23645",
                                            "fillColor": "#f23645",
                                            "transparency": 85
                                        }
                                    ]

                                    await market_hub.broadcast_all({
                                        "type": "walkforward_boxes",
                                        "boxes": self.active_boxes
                                    })
                                    await market_hub.broadcast_all({
                                        "type": "walkforward_trade",
                                        "action": "opened",
                                        "trade": tr_obj
                                    })

            # 4. Stream forming candle over WebSocket
            candle_payload = {
                "type": "walkforward_candle",
                "symbol": self.symbol,
                "timeframe": "M5",
                "candle": {
                    "time": t_sec,
                    "open": o_curr,
                    "high": h_curr,
                    "low": l_curr,
                    "close": c_curr,
                    "volume": v_curr
                },
                "stats": {
                    **self.stats,
                    "sim_date_str": str(t_curr),
                    "current_state_label": self.current_state_label
                }
            }
            await market_hub.broadcast_all(candle_payload)

            # Throttle loop speed to match requested UI playback speed
            if self.speed_ms > 0:
                await asyncio.sleep(self.speed_ms / 1000.0)

        self.status = "completed"
        self.stats["progress_pct"] = 100.0
        print(f"[WalkForward] Completed playback for {self.symbol}! Total Trades: {self.stats['total_trades']}, WinRate: {self.stats['win_rate_pct']}%, Net R: +{self.stats['net_r']}R")
        await market_hub.broadcast_all({
            "type": "walkforward_event",
            "action": "completed",
            "stats": self.stats
        })

    def _update_stats_on_close(self, tr: dict):
        self.stats["total_trades"] += 1
        if tr['pnl'] > 0:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1
        self.stats["win_rate_pct"] = round((self.stats["wins"] / max(1, self.stats["total_trades"])) * 100.0, 1)
        self.stats["net_pnl_usd"] = round(self.stats["net_pnl_usd"] + tr['pnl'], 2)
        self.stats["net_r"] = round(self.stats["net_r"] + tr['r_realized'], 1)
        
        all_wins = [t['pnl'] for t in self.trades if t['pnl'] > 0]
        all_losses = [abs(t['pnl']) for t in self.trades if t['pnl'] <= 0]
        sum_wins = sum(all_wins)
        sum_losses = sum(all_losses)
        self.stats["profit_factor"] = round(sum_wins / max(0.01, sum_losses), 2)
        
        all_sls = [t['sl_dist'] for t in self.trades]
        self.stats["avg_sl_pts"] = round(float(np.mean(all_sls)), 1) if all_sls else 0.0

    def run_instant_audit(self, symbol: str, date_from: str = "2026-01-01", date_to: str = "2026-03-31") -> dict:
        """Runs the entire walkforward backtest causally in 0.5s and returns complete audit."""
        self.symbol = symbol
        self.date_from = date_from
        self.date_to = date_to
        df_m5, df_h1 = self._load_datasets()
        
        params = SYMBOL_PARAMS.get(symbol, SYMBOL_PARAMS['FX_Vol_20'])
        spread = params['spread']
        pt_val = params['pt_val']
        min_sl = params['min_sl']
        max_sl = params['max_sl']
        target_rrr = params['target_rrr']

        total_bars = len(df_m5)
        m5_times = df_m5['time'].values
        m5_opens = df_m5['open'].values
        m5_highs = df_m5['high'].values
        m5_lows = df_m5['low'].values
        m5_closes = df_m5['close'].values

        h1_times = df_h1['time'].values
        h1_opens = df_h1['open'].values
        h1_highs = df_h1['high'].values
        h1_lows = df_h1['low'].values
        h1_closes = df_h1['close'].values
        h1_atrs = df_h1['atr'].values
        num_h1 = len(df_h1)

        trades = []
        active = None
        h1_ptr = 0
        last_trade_time = np.datetime64('2020-01-01')

        for i in range(10, total_bars):
            t_curr = m5_times[i]
            t_sec = int(pd.to_datetime(t_curr).timestamp())
            h_curr = float(m5_highs[i])
            l_curr = float(m5_lows[i])

            while h1_ptr < num_h1 and h1_times[h1_ptr] + np.timedelta64(1, 'h') <= t_curr:
                h1_ptr += 1

            if active is not None:
                if active['direction'] == 'BUY':
                    if l_curr <= active['sl']:
                        loss_pts = active['entry'] - active['sl']
                        active['exit_time'] = t_sec
                        active['outcome'] = 'SL'
                        active['pnl'] = round(-loss_pts * pt_val, 2)
                        active['r_realized'] = -1.0
                        trades.append(active)
                        active = None
                    elif h_curr >= active['tp']:
                        win_pts = active['tp'] - active['entry']
                        active['exit_time'] = t_sec
                        active['outcome'] = 'FULL_TP'
                        active['pnl'] = round(win_pts * pt_val, 2)
                        active['r_realized'] = active['target_rrr']
                        trades.append(active)
                        active = None
                    elif h_curr >= active['entry'] + 2.5 * active['sl_dist']:
                        new_sl = round(active['entry'] + 1.0 * active['sl_dist'], 2)
                        if new_sl > active['sl']:
                            active['sl'] = new_sl
                else: # SELL
                    if h_curr >= active['sl']:
                        loss_pts = active['sl'] - active['entry']
                        active['exit_time'] = t_sec
                        active['outcome'] = 'SL'
                        active['pnl'] = round(-loss_pts * pt_val, 2)
                        active['r_realized'] = -1.0
                        trades.append(active)
                        active = None
                    elif l_curr <= active['tp']:
                        win_pts = active['entry'] - active['tp']
                        active['exit_time'] = t_sec
                        active['outcome'] = 'FULL_TP'
                        active['pnl'] = round(win_pts * pt_val, 2)
                        active['r_realized'] = active['target_rrr']
                        trades.append(active)
                        active = None
                    elif l_curr <= active['entry'] - 2.5 * active['sl_dist']:
                        new_sl = round(active['entry'] - 1.0 * active['sl_dist'], 2)
                        if new_sl < active['sl']:
                            active['sl'] = new_sl

            if active is None and h1_ptr >= 16 and (t_curr - last_trade_time >= np.timedelta64(75, 'm')):
                base_high = float(np.max(h1_highs[h1_ptr - 16 : h1_ptr - 3]))
                base_low = float(np.min(h1_lows[h1_ptr - 16 : h1_ptr - 3]))
                base_range = base_high - base_low
                h1_atr = float(h1_atrs[h1_ptr - 1])

                bk_o = float(h1_opens[h1_ptr - 3])
                bk_c = float(h1_closes[h1_ptr - 3])

                retest_high = float(np.max(h1_highs[h1_ptr - 2 : h1_ptr]))
                retest_low = float(np.min(h1_lows[h1_ptr - 2 : h1_ptr]))

                if 1.0 * h1_atr <= base_range <= 4.2 * h1_atr:
                    if bk_c > base_high + 0.15 * h1_atr and bk_c > bk_o:
                        broken_level = base_high
                        if broken_level - 0.40 * h1_atr <= retest_low <= broken_level + 0.50 * h1_atr:
                            m5_prev_o = float(m5_opens[i-1])
                            m5_prev_c = float(m5_closes[i-1])
                            m5_prev_l = float(m5_lows[i-1])
                            body = abs(m5_prev_c - m5_prev_o)
                            lower_wick = min(m5_prev_o, m5_prev_c) - m5_prev_l
                            m5_recent_lows = m5_lows[i-5:i-1]
                            is_hl = m5_prev_l >= np.min(m5_recent_lows)

                            if (lower_wick >= 0.7 * body or m5_prev_c > m5_prev_o) and m5_prev_l >= broken_level - 0.28 * h1_atr and m5_prev_c >= broken_level and is_hl:
                                entry = round(m5_prev_c + spread, 2)
                                sl_raw = round(float(np.min(m5_lows[i-5:i])) - spread, 2)
                                sl_dist = round(entry - sl_raw, 2)
                                if min_sl <= sl_dist <= max_sl:
                                    tp = round(entry + target_rrr * sl_dist, 2)
                                    active = {
                                        'id': f"audit_tr_{len(trades) + 1}",
                                        'symbol': symbol,
                                        'direction': 'BUY',
                                        'type': 'long-position',
                                        'entry_time': t_sec,
                                        'entry': entry,
                                        'sl': sl_raw,
                                        'tp': tp,
                                        'sl_dist': sl_dist,
                                        'profit_dist': round(target_rrr * sl_dist, 2),
                                        'target_rrr': target_rrr,
                                        'broken_level': broken_level
                                    }
                                    last_trade_time = t_curr
                    elif bk_c < base_low - 0.15 * h1_atr and bk_c < bk_o:
                        broken_level = base_low
                        if broken_level - 0.50 * h1_atr <= retest_high <= broken_level + 0.40 * h1_atr:
                            m5_prev_o = float(m5_opens[i-1])
                            m5_prev_c = float(m5_closes[i-1])
                            m5_prev_h = float(m5_highs[i-1])
                            body = abs(m5_prev_c - m5_prev_o)
                            upper_wick = m5_prev_h - max(m5_prev_o, m5_prev_c)
                            m5_recent_highs = m5_highs[i-5:i-1]
                            is_lh = m5_prev_h <= np.max(m5_recent_highs)

                            if (upper_wick >= 0.7 * body or m5_prev_c < m5_prev_o) and m5_prev_h <= broken_level + 0.28 * h1_atr and m5_prev_c <= broken_level and is_lh:
                                entry = round(m5_prev_c - spread, 2)
                                sl_raw = round(float(np.max(m5_highs[i-5:i])) + spread, 2)
                                sl_dist = round(sl_raw - entry, 2)
                                if min_sl <= sl_dist <= max_sl:
                                    tp = round(entry - target_rrr * sl_dist, 2)
                                    active = {
                                        'id': f"audit_tr_{len(trades) + 1}",
                                        'symbol': symbol,
                                        'direction': 'SELL',
                                        'type': 'short-position',
                                        'entry_time': t_sec,
                                        'entry': entry,
                                        'sl': sl_raw,
                                        'tp': tp,
                                        'sl_dist': sl_dist,
                                        'profit_dist': round(target_rrr * sl_dist, 2),
                                        'target_rrr': target_rrr,
                                        'broken_level': broken_level
                                    }
                                    last_trade_time = t_curr

        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        total = len(trades)
        net_pnl = sum(t['pnl'] for t in trades)
        net_r = sum(t['r_realized'] for t in trades)
        win_rate = (len(wins) / max(1, total)) * 100.0
        profit_factor = round(sum(t['pnl'] for t in wins) / max(0.01, abs(sum(t['pnl'] for t in losses))), 2)

        return {
            "symbol": symbol,
            "period": f"{date_from} to {date_to}",
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(win_rate, 1),
            "net_pnl_usd": round(net_pnl, 2),
            "net_r": round(net_r, 1),
            "profit_factor": profit_factor,
            "avg_sl_pts": round(float(np.mean([t['sl_dist'] for t in trades])), 1) if trades else 0.0,
            "trades": trades
        }

walkforward_5state_engine = WalkForward5StateEngine()
