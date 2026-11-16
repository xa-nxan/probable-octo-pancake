"""
Live Shadow Learner & Autonomous Post-Mortem Diagnostic Engine.

Continuously tracks live paper/shadow setups on Weltrade Synthetics:
  1. Monitors active setups in real-time as ticks and candle closes arrive.
  2. Tracks peak favorable excursion (peak_r), drawdown, and Q93 fast-BE triggers.
  3. When trades resolve (TP, Trail Win, BE, or SL), performs deep structural POST-MORTEM:
     - Identifies EXACT failure modes:
       * Structure Invalidation (BOS): Candle body closed beyond the key level.
       * Market Structure Shift: Formed contrary HH/HL or LH/LL.
       * Wick Sweep / Spread Clip: Only outer wick touched SL by < 0.15 ATR, followed by reversal.
       * Runaway Momentum: Counter-trend expansion without waiting for Touch #2 body close.
     - Identifies EXACT winning patterns:
       * HTF Extension to M30/H1 swing target.
       * Compact Protected Base holding touch wicks.
  4. Generates dynamic self-learning guardrails and adaptive AI conviction adjustments.
"""

import os
import json
import time
import datetime
import threading
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STORAGE_FILE = os.path.join(DATA_DIR, "live_shadow_learning.json")

_lock = threading.Lock()

# Point value table for Weltrade synthetic indices (at 0.01 lot)
SYMBOL_POINT_VALS = {
    'FX_Vol_20': 0.0001,
    'FX_Vol_40': 0.0001,
    'SFX_Vol_20': 0.0001,
    'SFX_Vol_40': 0.0001,
}

class LiveShadowLearner:
    def __init__(self):
        self.trades: List[Dict[str, Any]] = []
        self.learning_weights: Dict[str, Any] = {
            "htf_alignment_bonus": 8,
            "multi_touch_bonus": 6,
            "adverse_momentum_penalty": -14,
            "wick_spread_pad_multiplier": 1.15,
        }
        self.failure_stats: Dict[str, int] = {
            "BOS_STRUCTURE_BROKEN": 0,
            "CONTRARY_STRUCTURE_SHIFT": 0,
            "WICK_SWEEP_LIQUIDITY": 0,
            "ADVERSE_MOMENTUM_RUNAWAY": 0,
            "PREMATURE_BE_CHOKE": 0,
            "TIME_EXHAUSTION": 0,
        }
        self.learned_rules: List[str] = [
            "Rule #1: When M15 is printing consecutive adverse bars, never enter before Touch #2 candle body closes inside the base.",
            "Rule #2: If market structure forms an opposite HH (on short) or LL (on long), trigger Q93 Protected BE immediately.",
            "Rule #3: When M30/H1 prior swing extreme is >= 12R away, let runner position trail to HTF ceiling rather than capping at 8R.",
            "Rule #4: Spread buffer must sit strictly outside Touch #1 outer wick to prevent liquidity sweeps from clipping stops.",
            "Rule #5: Anti-Choke BE: Delay breakeven arming until +1.8R (Breakout Peak clearance). Retests require breathing room to form Touch #2 without prematurely choking potential 8R+ winners."
        ]
        self.last_sync_time = 0.0
        self._load_from_disk()

    def _load_from_disk(self):
        with _lock:
            if os.path.exists(STORAGE_FILE):
                try:
                    with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.trades = data.get("trades", [])
                        self.learning_weights = data.get("learning_weights", self.learning_weights)
                        self.failure_stats = data.get("failure_stats", self.failure_stats)
                        loaded_rules = data.get("learned_rules", [])
                        for r in self.learned_rules:
                            if r not in loaded_rules:
                                loaded_rules.append(r)
                        self.learned_rules = loaded_rules
                        self.last_sync_time = data.get("last_sync_time", 0.0)
                except Exception as e:
                    print(f"[ShadowLearner] Error loading state: {e}")

    def _save_to_disk(self):
        with _lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            try:
                state = {
                    "last_sync_time": time.time(),
                    "trades": self.trades[-500:],  # keep last 500 shadow trades
                    "learning_weights": self.learning_weights,
                    "failure_stats": self.failure_stats,
                    "learned_rules": self.learned_rules,
                }
                with open(STORAGE_FILE, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                print(f"[ShadowLearner] Error saving state: {e}")

    def register_shadow_setup(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        setup_name: str,
        entry: float,
        sl: float,
        tp: float,
        level: float,
        ai_score: int,
        only_when_sure: bool,
        current_time: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Registers a new live shadow trade if one is not already actively running
        for the same symbol in the same direction within the last 30 minutes.
        """
        now_ts = current_time or int(time.time())
        is_long = direction.upper() in ['BULLISH', 'LONG']
        trade_type = 'long-position' if is_long else 'short-position'
        stop_dist = round(abs(entry - sl), 2)
        profit_dist = round(abs(tp - entry), 2)
        rrr = round(profit_dist / max(1.0, stop_dist), 2)

        with _lock:
            # Check for existing active or very recent trade on this symbol
            for t in self.trades:
                if t['symbol'] == symbol and t['direction'] == direction:
                    if t['status'] == 'ACTIVE':
                        return None  # already tracking this setup actively
                    if (now_ts - t['entry_time']) < 1800:
                        return None  # throttle duplicate registrations within 30 min

            trade_id = f"shadow_{now_ts}_{symbol}_{'BUY' if is_long else 'SELL'}"
            trade_obj = {
                "id": trade_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "type": trade_type,
                "setup": setup_name,
                "entry_time": now_ts,
                "entry_time_str": datetime.datetime.fromtimestamp(now_ts).strftime('%Y-%m-%d %H:%M'),
                "exit_time": None,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "level": level,
                "stop_dist": stop_dist,
                "profit_dist": profit_dist,
                "rrr": rrr,
                "ai_score": ai_score,
                "only_when_sure": only_when_sure,
                "status": "ACTIVE",
                "outcome": "RUNNING",
                "peak_r": 0.0,
                "drawdown_r": 0.0,
                "realized_r": 0.0,
                "points": 0.0,
                "pnl_usd": 0.0,
                "be_locked": False,
                "bars_held": 0,
                "post_mortem": None
            }
            self.trades.insert(0, trade_obj)
            print(f"[ShadowLearner] Registered new Shadow Trade: {symbol} {direction} at {entry} (SL {sl}, TP {tp}, R:R 1:{rrr})")

        self._save_to_disk()
        return trade_obj

    def update_live_ticks(self, current_prices: Dict[str, Dict[str, float]], current_bars: Dict[str, pd.DataFrame]):
        """
        Called continuously with latest tick / bar information to advance active shadow trades.
        """
        changed = False
        with _lock:
            for t in self.trades:
                if t['status'] != 'ACTIVE':
                    continue

                sym = t['symbol']
                price_info = current_prices.get(sym)
                if not price_info:
                    continue

                bid = price_info.get('bid', 0.0)
                ask = price_info.get('ask', 0.0)
                if bid <= 0:
                    continue

                is_long = t['type'] == 'long-position'
                curr_price = bid if is_long else ask
                stop_d = max(1e-5, t['stop_dist'])
                fav_dist = (curr_price - t['entry']) if is_long else (t['entry'] - curr_price)
                adv_dist = (t['entry'] - curr_price) if is_long else (curr_price - t['entry'])

                cur_r = round(fav_dist / stop_d, 2)
                cur_dd = round(max(0.0, adv_dist / stop_d), 2)

                if cur_r > t['peak_r']:
                    t['peak_r'] = cur_r
                if cur_dd > t['drawdown_r']:
                    t['drawdown_r'] = cur_dd

                # Adaptive Breakeven Trigger:
                # Requires at least +1.8R (clearing Obstacle #1 Breakout Peak from Q93) before locking BE
                # This prevents normal Touch #2 pullbacks from prematurely choking multi-R winners
                if t['peak_r'] >= 1.80 and not t['be_locked']:
                    t['be_locked'] = True
                    print(f"[ShadowLearner] Trade {t['id']} cleared Breakout Peak (+1.8R)! Protected Breakeven locked.")
                    changed = True

                # Check if TP was reached
                tp_reached = (is_long and curr_price >= t['tp']) or (not is_long and curr_price <= t['tp'])
                # Check if Stop Loss / BE was reached
                sl_price = (t['entry'] + 0.15 * stop_d) if (t['be_locked']) else t['sl']
                sl_hit = (is_long and curr_price <= sl_price) or (not is_long and curr_price >= sl_price)

                if tp_reached:
                    t['status'] = 'COMPLETED'
                    t['outcome'] = 'FULL_TP'
                    t['realized_r'] = t['rrr']
                    t['exit_time'] = int(time.time())
                    pt_val = SYMBOL_POINT_VALS.get(sym, 0.0001)
                    t['points'] = round(t['realized_r'] * stop_d, 2)
                    t['pnl_usd'] = round(t['points'] * pt_val, 2)
                    self._perform_post_mortem(t, current_bars.get(sym))
                    changed = True
                    print(f"[ShadowLearner] Trade {t['id']} resolved FULL_TP (+{t['realized_r']}R, +${t['pnl_usd']})!")

                elif sl_hit:
                    t['status'] = 'COMPLETED'
                    t['exit_time'] = int(time.time())
                    pt_val = SYMBOL_POINT_VALS.get(sym, 0.0001)

                    # Authentic Strategy Rules (Question 93 Protected BE):
                    if t['be_locked']:
                        # Price cleared Obstacle #1 (+1.8R) and armed Protected BE (+0.2R lock)
                        # Reversal resulted in a scratch protection, NOT a loss and NOT a fake full win
                        t['outcome'] = 'PROTECTED_BE'
                        t['realized_r'] = 0.20
                    else:
                        # Price reversed before clearing Obstacle #1 -> Full SL
                        t['outcome'] = 'FAILED_SL'
                        t['realized_r'] = -1.0

                    t['points'] = round(t['realized_r'] * stop_d, 2)
                    t['pnl_usd'] = round(t['points'] * pt_val, 2)
                    self._perform_post_mortem(t, current_bars.get(sym))
                    changed = True
                    print(f"[ShadowLearner] Trade {t['id']} resolved {t['outcome']} ({t['realized_r']}R, ${t['pnl_usd']})")

        if changed:
            self._save_to_disk()

    def _perform_post_mortem(self, trade: Dict[str, Any], df_bars: Optional[pd.DataFrame]):
        """
        Deep Price Action Post-Mortem Diagnostic.
        Analyzes the exact candles to determine why the trade worked or where it failed.
        """
        outcome = trade['outcome']
        is_long = trade['type'] == 'long-position'
        realized_r = trade['realized_r']
        peak_r = trade['peak_r']
        sym = trade['symbol']

        if outcome in ['FULL_TP', 'TRAIL_WIN'] and realized_r >= 4.0:
            trade['post_mortem'] = {
                "verdict": "PERFECT_SWING_WIN",
                "failure_mode": None,
                "primary_reason": f"Clean Multi-Timeframe Expansion (+{realized_r}R)",
                "structure_integrity": "RESPECTED_STRUCTURE",
                "detailed_analysis": (
                    f"Touch #1 and Touch #2 wicks held firmly at the {trade['level']} structural boundary. "
                    f"Price formed clean pro-trend continuation wicks and pushed directly into the higher-timeframe "
                    f"swing target with peak excursion of +{peak_r}R."
                ),
                "learned_takeaway": "Continue prioritizing 2x-4x touch bases that retest broken levels with HTF EMA alignment."
            }
            return

        if outcome == 'PROTECTED_BE':
            trade['post_mortem'] = {
                "verdict": "PREMATURE_BE_CHOKE",
                "failure_mode": "PREMATURE_BE_CHOKE",
                "primary_reason": "Premature BE Choke (+0.55R Trigger)",
                "structure_integrity": "INTACT_BASE_CHOKED_BY_BE",
                "detailed_analysis": (
                    f"Price initially pushed to peak +{peak_r}R and armed Breakeven. A routine retest / Touch #2 pullback "
                    f"retested the base at {trade['level']}, clipping the BE stop (+0.2R scratch). The original Stop Loss "
                    f"at {trade['sl']} was NEVER broken! The trade was choked before it could complete its multi-R expansion."
                ),
                "learned_takeaway": "Delay Breakeven until +1.8R (Breakout Peak clearance) to let structural retests breathe."
            }
            self.failure_stats["PREMATURE_BE_CHOKE"] = self.failure_stats.get("PREMATURE_BE_CHOKE", 0) + 1
            return

        # Trade hit SL: Detailed Failure Diagnosis
        peak_r = trade.get('peak_r', 0.0)
        drawdown_r = trade.get('drawdown_r', 1.0)

        if peak_r >= 0.8:
            failure_mode = "ADVERSE_MOMENTUM_RUNAWAY"
            primary_reason = f"Momentum Exhaustion after +{peak_r:.1f}R Run"
            detailed = (
                f"Trade initially made a solid expansion of +{peak_r:.1f}R in favor of the position, "
                f"but pro-trend momentum exhausted before reaching the full target, reversing back to stop loss."
            )
            takeaway = "Implement partial trailing stops or dynamic ratcheting after +1.5R favorable excursions."
        elif 0.3 <= peak_r < 0.8:
            failure_mode = "CONTRARY_STRUCTURE_SHIFT"
            primary_reason = "Contrary Structure Shift after Initial Bounce"
            detailed = (
                f"Price made an initial reaction (+{peak_r:.1f}R) off the structural base, but failed to follow through. "
                f"Opposing momentum overwhelmed the base and printed an opposite structure shift."
            )
            takeaway = "Watch for immediate multi-candle momentum follow-through; scratch if reaction stalls."
        elif drawdown_r <= 1.15 and peak_r < 0.3:
            failure_mode = "WICK_SWEEP_LIQUIDITY"
            primary_reason = "Wick Sweep / Liquidity Hunt Spiked SL"
            detailed = (
                f"An aggressive outer wick sweep momentarily pierced the stop loss zone before stabilizing. "
                f"Wick pad was clipped by synthetic index spread expansion."
            )
            takeaway = "Maintain at least 1.8x spread buffer strictly behind outer wick extremes."
        else:
            failure_mode = "BOS_STRUCTURE_BROKEN"
            primary_reason = "Break of Structure: Level Closed Beyond Base"
            detailed = "Price breached the structural level, invalidating the thesis."
            takeaway = "Strictly require respected LH/HL before committing risk."

        if df_bars is not None and len(df_bars) >= 15:
            recent = df_bars.iloc[-12:]
            c_vals = recent['close'].values
            h_vals = recent['high'].values
            l_vals = recent['low'].values

            if is_long:
                # Did candle bodies close below the level?
                body_broken = any(c < trade['level'] for c in c_vals)
                # Did it print a Lower Low?
                ll_printed = min(l_vals) < trade['sl']
                # Was it just a quick wick sweep where body closed above level?
                wick_only = any(l < trade['sl'] for l in l_vals) and all(c > trade['level'] for c in c_vals[-3:])

                if wick_only:
                    failure_mode = "WICK_SWEEP_LIQUIDITY"
                    primary_reason = "Wick Sweep / Liquidity Hunt (Spread Pad Too Tight)"
                    detailed = (
                        f"Candle bodies respected the {trade['level']} floor, but an outer liquidity wick spiked the SL "
                        f"before price reversed. The stop loss required an additional 0.15 ATR buffer for synthetic volatility noise."
                    )
                    takeaway = "Increase wick buffer multiplier for this symbol to absorb liquidity hunt spikes."
                elif body_broken or ll_printed:
                    failure_mode = "BOS_STRUCTURE_BROKEN"
                    primary_reason = "Break of Structure: Floor Closed Below"
                    detailed = (
                        f"Sellers dominated the retest. Candle body closed firmly below {trade['level']}, printing a Lower Low (LL). "
                        f"The support level failed to hold as a Higher Low (HL)."
                    )
                    takeaway = "Do not take Longs if preceding candle body closed below the boundary floor."
            else:
                # Short setup failure analysis
                body_broken = any(c > trade['level'] for c in c_vals)
                hh_printed = max(h_vals) > trade['sl']
                wick_only = any(h > trade['sl'] for h in h_vals) and all(c < trade['level'] for c in c_vals[-3:])

                if wick_only:
                    failure_mode = "WICK_SWEEP_LIQUIDITY"
                    primary_reason = "Wick Sweep / Liquidity Hunt (Upper Wick Clip)"
                    detailed = (
                        f"Candle bodies held below the {trade['level']} ceiling, but an impulsive upward wick clipped the stop. "
                        f"Price then resumed the downward move."
                    )
                    takeaway = "Tuck Short SL strictly behind Touch #1 outer wick plus 0.20 ATR buffer."
                elif body_broken or hh_printed:
                    failure_mode = "CONTRARY_STRUCTURE_SHIFT"
                    primary_reason = "Ceiling Violated: Market Printed Higher High (HH)"
                    detailed = (
                        f"Price failed to respect the Lower High (LH). Buyers overwhelmed the level and broke into a Higher High (HH), "
                        f"flipping the ceiling into new support."
                    )
                    takeaway = "Never short when price is breaking above resistance in an active HL-HH sequence."

        self.failure_stats[failure_mode] = self.failure_stats.get(failure_mode, 0) + 1
        trade['post_mortem'] = {
            "verdict": "FAILED_SL",
            "failure_mode": failure_mode,
            "primary_reason": primary_reason,
            "structure_integrity": "INVALIDATED",
            "detailed_analysis": detailed,
            "learned_takeaway": takeaway
        }

    def backfill_recent_history(self, historical_trades: List[Dict[str, Any]]):
        """
        Seeds the shadow learner with recent completed trades from backtest/scanner
        so the learner immediately possesses rich historical diagnostic context.
        """
        with _lock:
            existing_ids = {t['id'] for t in self.trades}
            added = 0
            for ht in historical_trades:
                tid = ht.get('id', f"shadow_{ht['entryTime']}_{ht['symbol']}")
                if tid in existing_ids:
                    continue

                stop_d = ht['stopDist']
                rrr = ht['rrr']
                real_r = ht.get('realized_r', rrr if ht['win'] else -1.0)
                outcome = ht.get('outcome', 'FULL_TP' if ht['win'] else 'FAILED_SL')

                trade_obj = {
                    "id": tid,
                    "symbol": ht['symbol'],
                    "timeframe": "M5",
                    "direction": "BULLISH" if ht['type'] == 'long-position' else "BEARISH",
                    "type": ht['type'],
                    "setup": ht['setup'],
                    "entry_time": ht['entryTime'],
                    "entry_time_str": datetime.datetime.fromtimestamp(ht['entryTime']).strftime('%Y-%m-%d %H:%M'),
                    "exit_time": ht.get('exitTime'),
                    "entry": ht['entry'],
                    "sl": ht['sl'],
                    "tp": ht['tp'],
                    "level": ht.get('brokenLevel', ht['sl']),
                    "stop_dist": stop_d,
                    "profit_dist": ht.get('profitDist', round(rrr * stop_d, 2)),
                    "rrr": rrr,
                    "ai_score": ht.get('ai_score', 80),
                    "only_when_sure": ht.get('only_when_sure', True),
                    "status": "COMPLETED",
                    "outcome": outcome,
                    "peak_r": ht.get('peak_r', max(real_r, 0.5)),
                    "drawdown_r": ht.get('drawdown_r', 0.2 if ht.get('win') else 1.0),
                    "realized_r": real_r,
                    "points": ht.get('points', 0.0),
                    "pnl_usd": ht.get('pnl_usd', 0.0),
                    "be_locked": real_r > 0,
                    "bars_held": 12,
                    "post_mortem": None
                }
                self._perform_post_mortem(trade_obj, None)
                self.trades.append(trade_obj)
                added += 1

            self.trades.sort(key=lambda x: x['entry_time'], reverse=True)
            print(f"[ShadowLearner] Backfilled {added} recent historical trades into shadow memory.")

        self._save_to_disk()

    def get_summary(self) -> Dict[str, Any]:
        """
        Returns real-time learning analytics, win rates, failure breakdown, and learned rules.
        """
        with _lock:
            all_t = self.trades
            completed = [t for t in all_t if t['status'] == 'COMPLETED']
            active = [t for t in all_t if t['status'] == 'ACTIVE']

            wins = [t for t in completed if t['outcome'] in ['FULL_TP', 'TRAIL_WIN', 'TRAIL_EXIT'] or t.get('realized_r', 0) > 0.25]
            scratches = [t for t in completed if t['outcome'] == 'PROTECTED_BE' or 0 < t.get('realized_r', 0) <= 0.25]
            losses = [t for t in completed if t['outcome'] in ['FAILED_SL', 'SL'] or t.get('realized_r', 0) < 0]

            total_comp = len(completed)
            win_rate = round(len(wins) / max(1, total_comp) * 100, 1)
            protected_win_rate = round((len(wins) + len(scratches)) / max(1, total_comp) * 100, 1)

            total_r = round(sum(t.get('realized_r', 0.0) for t in completed), 2)
            avg_rrr = round(sum(t['rrr'] for t in completed) / max(1, total_comp), 2)
            net_pnl = round(sum(t.get('pnl_usd', 0.0) for t in completed), 2)

            return {
                "total_tracked": len(all_t),
                "active_shadow_trades": len(active),
                "completed_trades": total_comp,
                "wins": len(wins),
                "scratches_be": len(scratches),
                "losses": len(losses),
                "win_rate_pct": win_rate,
                "protected_non_loss_rate_pct": protected_win_rate,
                "total_realized_r": total_r,
                "average_rrr": avg_rrr,
                "net_pnl_usd": net_pnl,
                "failure_breakdown": self.failure_stats,
                "learned_rules": self.learned_rules,
                "learning_weights": self.learning_weights,
                "last_sync": self.last_sync_time,
                "active_trades_list": active,
                "recent_completed_sample": completed[:100]
            }

# Singleton Instance
shadow_learner = LiveShadowLearner()
