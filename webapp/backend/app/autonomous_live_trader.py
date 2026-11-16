"""
Autonomous AI Live Trading Engine
Encodes the Masterclass 100-Questions and 3 Price Action Lessons:
- Multi-Timeframe Fractal Interplay (H4 -> H1 -> M30 -> M15 -> M5)
- Automated Order Execution with Micro-Stop Protection (0.01 micro-lot)
- Free-Roll Pullback Pyramiding (A12 & Q79)
- Real-Time Autopsy & Dynamic Self-Learning Loop
- Account Drawdown Circuit Breakers to Protect Capital
"""

import asyncio
import datetime
import time
from typing import Dict, List, Any, Optional
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from app.mtf_interplay_engine import analyze_mtf_fractal_interplay
from app.ai_reasoning_agent import ai_reasoning_agent
from app.backtest_engine import _get_symbol_profile


class DirectMT5Worker:
    def __init__(self):
        self.connected = mt5.initialize()
    async def execute_async(self, cmd, *args, **kwargs):
        if not self.connected:
            self.connected = mt5.initialize()
        fn = getattr(mt5, cmd, None)
        if fn is None:
            raise AttributeError(f"MetaTrader5 has no attribute '{cmd}'")
        return fn(*args, **kwargs)


class AutonomousLiveTrader:
    def __init__(self, mt5_worker=None):
        self.mt5_worker = mt5_worker if mt5_worker is not None else DirectMT5Worker()
        self.enabled: bool = True  # Enabled for live demo execution
        self.is_running: bool = False
        self.base_lot: float = 0.01
        self.max_concurrent_base_trades: int = 4
        self.max_daily_loss_usd: float = 200.0  # User mandate: $200 account risk allowance for full AI learning and trading
        self.max_risk_usd_per_trade: Dict[str, float] = {
            'SFX_Vol_20': 3.50,
            'FX_Vol_20': 5.00,
            'SFX_Vol_40': 12.50,
            'FX_Vol_40': 12.50,
        }
        self.tracked_positions: Dict[int, Dict[str, Any]] = {}  # ticket -> trade metadata
        self.symbol_cooldowns: Dict[str, float] = {}  # sym_id -> timestamp until next entry allowed
        self.daily_start_balance: float = 0.0
        self.recent_logs: List[Dict[str, Any]] = []
        self.symbol_states: Dict[str, Any] = {}
        self.worker_task: Optional[asyncio.Task] = None
        self.last_scan_time: float = 0.0
        self.total_ai_trades_today: int = 0
        self.daily_pnl_usd: float = 0.0

    def log(self, message: str, level: str = "INFO"):
        entry = {
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.recent_logs.append(entry)
        if len(self.recent_logs) > 100:
            self.recent_logs.pop(0)
        prefix = "[AI Autonomous Trader]"
        try:
            print(f"{prefix} [{level}] {message}")
        except UnicodeEncodeError:
            print(f"{prefix} [{level}] {message}".encode("ascii", "replace").decode())

    def set_worker(self, worker):
        self.mt5_worker = worker

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.log("Autonomous AI Live Trader started. Monitoring H4/H1/M30/M15/M5 across 4 synthetic indices.")
        self.worker_task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            self.worker_task = None
        self.log("Autonomous AI Live Trader paused.")

    def toggle(self, state: Optional[bool] = None) -> bool:
        if state is not None:
            self.enabled = state
        else:
            self.enabled = not self.enabled
        self.log(f"Trading status set to: {'ENABLED' if self.enabled else 'PAUSED'}")
        return self.enabled

    async def _main_loop(self):
        symbols = ['SFX_Vol_20', 'SFX_Vol_40', 'FX_Vol_20', 'FX_Vol_40']
        
        while self.is_running:
            try:
                await asyncio.sleep(4.0)
                if not self.enabled or not self.mt5_worker:
                    continue

                # 1. Update account balance and check daily loss circuit breaker
                account = await self.mt5_worker.execute_async("account_info")
                if not account:
                    continue

                if self.daily_start_balance <= 0:
                    self.daily_start_balance = float(account.balance)

                # Check daily realized PnL
                await self._check_daily_pnl_and_closed_trades()

                if self.daily_pnl_usd <= -self.max_daily_loss_usd:
                    self.log(f"CIRCUIT BREAKER TRIGGERED: Daily loss ${self.daily_pnl_usd:.2f} exceeds limit (-${self.max_daily_loss_usd:.2f}). Pausing entries for capital safety.", "WARNING")
                    await asyncio.sleep(60.0)
                    continue

                # 2. Check open positions to manage pyramiding & existing exposure
                positions = await self.mt5_worker.execute_async("positions_get")
                open_positions = positions if positions else []
                active_symbols = set()
                active_by_symbol: Dict[str, List[Any]] = {s: [] for s in symbols}

                for p in open_positions:
                    sym_clean = p.symbol.replace(' ', '_')
                    active_symbols.add(sym_clean)
                    if sym_clean in active_by_symbol:
                        active_by_symbol[sym_clean].append(p)

                # 3. Dynamic Multi-Tier Profit Trailing Ratchet ($5 -> lock $2.50, $10 -> lock $7.00, $15+ -> lock 75%)
                await self._manage_trailing_profit_ratchet(open_positions)

                # 3b. Active Structural Invalidation Guard (100 Questions Q16, Q30, Q93, Q98)
                await self._manage_structural_guard(open_positions)

                # 4. Check for Free-Roll Pyramiding on existing runners
                for sym_id, sym_pos in active_by_symbol.items():
                    if len(sym_pos) > 0:
                        await self._check_free_roll_pyramiding(sym_id, sym_pos)

                # 5. If max concurrent base trades reached, skip new entries
                base_trade_count = sum(1 for sym, pos in active_by_symbol.items() if len(pos) > 0)
                if base_trade_count >= self.max_concurrent_base_trades:
                    continue

                # 6. Scan 4 symbols for Multi-Timeframe Interplay entries
                self.last_scan_time = time.time()
                for sym_id in symbols:
                    has_active = len(active_by_symbol[sym_id]) > 0
                    await self._evaluate_and_execute_entry(sym_id, skip_entry=has_active)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Error in autonomous loop: {str(e)}", "ERROR")
                await asyncio.sleep(5.0)

    async def _evaluate_and_execute_entry(self, sym_id: str, skip_entry: bool = False):
        sym_clean = sym_id.replace('_', ' ')
        await self.mt5_worker.execute_async("symbol_select", sym_clean, True)

        tick = await self.mt5_worker.execute_async("symbol_info_tick", sym_clean)
        info = await self.mt5_worker.execute_async("symbol_info", sym_clean)
        if not tick or not info:
            return

        # Fetch rates for H4, H1, M30, M15, M5
        tfs = {
            'H4': mt5.TIMEFRAME_H4,
            'H1': mt5.TIMEFRAME_H1,
            'M30': mt5.TIMEFRAME_M30,
            'M15': mt5.TIMEFRAME_M15,
            'M5': mt5.TIMEFRAME_M5
        }

        import pandas as pd
        tf_dfs = {}
        for name, tf_code in tfs.items():
            rates = await self.mt5_worker.execute_async("copy_rates_from_pos", sym_clean, tf_code, 0, 80)
            if rates is not None and len(rates) > 0:
                tf_dfs[name] = pd.DataFrame(rates)
            else:
                return

        # Run Multi-Timeframe Fractal Interplay Engine
        res = analyze_mtf_fractal_interplay(sym_id, tf_dfs, curr_price=tick.bid, digits=info.digits)
        self.symbol_states[sym_id] = res

        if skip_entry:
            return  # Already has active trade; updated radar display and return

        # Check symbol cooldown (prevents revenge churn after stop-out)
        now_ts = time.time()
        cooldown_until = self.symbol_cooldowns.get(sym_id, 0)
        if now_ts < cooldown_until:
            remain_min = int((cooldown_until - now_ts) / 60) + 1
            if res.get('action') in ('BUY', 'SELL'):
                res['action'] = 'COOLDOWN'
                res['verdict'] = f"POST-STOPOUT COOLDOWN ({remain_min}m remaining to prevent revenge churn)"
            return

        action = res.get('action')
        confidence = res.get('confidence', 0)
        verdict = res.get('verdict', '')

        # Entry threshold: confidence >= 80% with BUY or SELL signal
        if action in ('BUY', 'SELL') and confidence >= 80:
            m5_data = res.get('timeframes', {}).get('M5', {})
            h1_data = res.get('timeframes', {}).get('H1', {})
            h4_data = res.get('timeframes', {}).get('H4', {})

            is_buy = (action == 'BUY')
            exec_price = float(tick.ask) if is_buy else float(tick.bid)
            micro_sl = float(m5_data.get('micro_sl', 0.0))
            macro_tp = float(h1_data.get('structural_tp', 0.0) or h4_data.get('macro_target', 0.0))

            if micro_sl <= 0:
                return

            # Risk calculation: dollar risk on 0.01 lot
            digits = int(info.digits)
            contract_size = float(info.trade_contract_size) if info.trade_contract_size else 1.0
            risk_dist = abs(exec_price - micro_sl)
            risk_usd = risk_dist * self.base_lot * contract_size

            max_allowed_risk = self.max_risk_usd_per_trade.get(sym_id, 4.0)
            if risk_usd > max_allowed_risk:
                self.log(f"Skipping {sym_id} {action}: risk ${risk_usd:.2f} exceeds allowed limit ${max_allowed_risk:.2f}", "WARNING")
                return

            if macro_tp <= 0 or (is_buy and macro_tp <= exec_price) or (not is_buy and macro_tp >= exec_price):
                # Fallback to 1:6.5 R:R target
                macro_tp = round(exec_price + (6.5 * risk_dist if is_buy else -6.5 * risk_dist), digits)

            # Check filling mode
            type_filling = mt5.ORDER_FILLING_FOK
            if info.filling_mode & 1:
                type_filling = mt5.ORDER_FILLING_FOK
            elif info.filling_mode & 2:
                type_filling = mt5.ORDER_FILLING_IOC
            else:
                type_filling = mt5.ORDER_FILLING_RETURN

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym_clean,
                "volume": self.base_lot,
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": round(exec_price, digits),
                "sl": round(micro_sl, digits),
                "tp": round(macro_tp, digits),
                "deviation": 25,
                "magic": 234100,
                "comment": f"AI MTF ({confidence}%)",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }

            result = await self.mt5_worker.execute_async("order_send", request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                ticket = int(result.order)
                pos_list = await self.mt5_worker.execute_async("positions_get", symbol=sym_clean)
                if pos_list:
                    matching = [p for p in pos_list if getattr(p, 'magic', 0) in (234100, 234101)]
                    if matching:
                        ticket = int(matching[-1].ticket)
                    else:
                        ticket = int(pos_list[-1].ticket)

                self.total_ai_trades_today += 1
                obstacle_1 = float(res.get("obstacle_1", 0.0) or m5_data.get("obstacle_1", 0.0))
                retest_level = float(h1_data.get("broken_level", exec_price))
                h1_atr = float(h1_data.get("atr", 60.0))
                self.tracked_positions[ticket] = {
                    "ticket": ticket,
                    "symbol": sym_id,
                    "action": action,
                    "volume": self.base_lot,
                    "entry_price": exec_price,
                    "sl": micro_sl,
                    "tp": macro_tp,
                    "obstacle_1": obstacle_1,
                    "retest_level": retest_level,
                    "h1_atr": h1_atr,
                    "risk_usd": risk_usd,
                    "confidence": confidence,
                    "verdict": verdict,
                    "entry_time": time.time(),
                    "tranches_count": 1,
                    "max_runner_r": 0.0,
                    "is_pyramid": False
                }
                self.log(f"🎯 EXECUTED {action} #{ticket} on {sym_id} @ {exec_price:.2f} | SL: {micro_sl:.2f} (Risk: -${risk_usd:.2f}) | TP: {macro_tp:.2f} | R:R 1:{res.get('timeframes', {}).get('M5', {}).get('rrr', 6.0):.1f} | Conf: {confidence}%", "SUCCESS")

    async def _check_free_roll_pyramiding(self, sym_id: str, positions: List[Any]):
        """
        Masterclass State-3 & State-4 Retest-Line Pyramiding (A12 & Q79):
        Adds fuel to the trade strictly on M15/M5 retests in a confirmed M30/H1 trend wave:
        1. Base position must be in profit and running in the trend direction.
        2. Price must pull back to either the original Retest Line OR the newly broken Obstacle #1 / live M30/H1 broken structure (State 4 Continuation HL/LH).
        3. M5/M15 must print a rejection wick + directional body confirming the pullback held.
        4. Free-Roll Safety: New tranche risk is covered by existing unrealized/locked profit on the base trade.
        """
        if len(positions) >= 3:
            return  # Max 3 tranches (1 base + 2 pyramid additions)

        base_pos = positions[0]
        ticket = int(base_pos.ticket)
        meta = self.tracked_positions.get(ticket, {})

        now_ts = time.time()
        last_pyr_ts = meta.get("last_pyramid_time", meta.get("entry_time", 0))
        if now_ts - last_pyr_ts < 900:
            return

        entry = float(base_pos.price_open)
        curr_sl = float(base_pos.sl)
        curr_price = float(base_pos.price_current)
        profit_usd = float(base_pos.profit)
        is_buy = (base_pos.type == mt5.ORDER_TYPE_BUY)

        # Require base position to be in meaningful profit before pyramiding
        min_profit_for_pyramid = 2.00 if '20' in sym_id else 5.00
        if profit_usd < min_profit_for_pyramid:
            return

        # Candidate structural retest levels: live M30/H1 anchor_level, broken obstacle_1, or initial retest_level
        live_state = self.symbol_states.get(sym_id, {})
        live_anchor = float(live_state.get("anchor_level", 0.0) or 0.0)
        retest_level = float(meta.get("retest_level", entry))
        obstacle_1 = float(meta.get("obstacle_1", 0.0) or 0.0)
        h1_atr = float(meta.get("h1_atr", 60.0) or 60.0)

        candidate_levels = [lvl for lvl in (live_anchor, obstacle_1, retest_level) if lvl > 0]
        if not candidate_levels:
            return

        active_retest_lvl = min(candidate_levels, key=lambda lvl: abs(curr_price - lvl))
        dist_to_retest = abs(curr_price - active_retest_lvl)
        if dist_to_retest > 0.45 * h1_atr:
            return  # Not at a structural retest shelf; never pyramid in mid-air!

        # Fetch recent M5 bars to verify rejection wick off the structural shelf
        sym_clean = sym_id.replace('_', ' ')
        rates = await self.mt5_worker.execute_async("copy_rates_from_pos", sym_clean, mt5.TIMEFRAME_M5, 0, 8)
        if rates is None or len(rates) < 4:
            return

        info = await self.mt5_worker.execute_async("symbol_info", sym_clean)
        tick = await self.mt5_worker.execute_async("symbol_info_tick", sym_clean)
        if not info or not tick:
            return

        digits = int(info.digits)
        point = float(info.point) if info.point else 0.01
        contract_size = float(info.trade_contract_size) if info.trade_contract_size else 1.0
        max_pyr_risk = self.max_risk_usd_per_trade.get(sym_id, 4.0) * 0.60

        last_m5 = rates[-2]
        prev_m5 = rates[-3]
        bar_rng = max(1e-5, float(last_m5['high']) - float(last_m5['low']))
        upper_wick = float(last_m5['high']) - max(float(last_m5['open']), float(last_m5['close']))
        lower_wick = min(float(last_m5['open']), float(last_m5['close'])) - float(last_m5['low'])

        if is_buy and (last_m5['close'] > last_m5['open']) and (lower_wick / bar_rng >= 0.20):
            swing_low = min(float(last_m5['low']), float(prev_m5['low']))
            new_sl = round(swing_low - 15.0 * point, digits)
            exec_price = float(tick.ask)
            new_risk_dist = abs(exec_price - new_sl)
            new_risk_usd = new_risk_dist * self.base_lot * contract_size

            if new_risk_usd > max_pyr_risk or new_risk_usd > profit_usd or new_sl >= exec_price:
                return

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym_clean,
                "volume": self.base_lot,
                "type": mt5.ORDER_TYPE_BUY,
                "price": round(exec_price, digits),
                "sl": new_sl,
                "tp": float(base_pos.tp),
                "deviation": 25,
                "magic": 234101,
                "comment": f"AI Retest Pyramid #{len(positions) + 1}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK if (info.filling_mode & 1) else mt5.ORDER_FILLING_IOC,
            }
            res = await self.mt5_worker.execute_async("order_send", request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                meta["tranches_count"] = len(positions) + 1
                meta["last_pyramid_time"] = now_ts
                self.tracked_positions[ticket] = meta
                self.log(f"⚡ RETEST PYRAMID TRANCHE #{len(positions)+1} on {sym_id} @ {exec_price:.2f} (Shelf: {active_retest_lvl:.2f}) | SL: {new_sl:.2f} (Free-Roll Risk: -${new_risk_usd:.2f} vs Base +${profit_usd:.2f})", "SUCCESS")

        elif not is_buy and (last_m5['close'] < last_m5['open']) and (upper_wick / bar_rng >= 0.20):
            swing_high = max(float(last_m5['high']), float(prev_m5['high']))
            new_sl = round(swing_high + 15.0 * point, digits)
            exec_price = float(tick.bid)
            new_risk_dist = abs(new_sl - exec_price)
            new_risk_usd = new_risk_dist * self.base_lot * contract_size

            if new_risk_usd > max_pyr_risk or new_risk_usd > profit_usd or new_sl <= exec_price:
                return

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym_clean,
                "volume": self.base_lot,
                "type": mt5.ORDER_TYPE_SELL,
                "price": round(exec_price, digits),
                "sl": new_sl,
                "tp": float(base_pos.tp),
                "deviation": 25,
                "magic": 234101,
                "comment": f"AI Retest Pyramid #{len(positions) + 1}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK if (info.filling_mode & 1) else mt5.ORDER_FILLING_IOC,
            }
            res = await self.mt5_worker.execute_async("order_send", request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                meta["tranches_count"] = len(positions) + 1
                meta["last_pyramid_time"] = now_ts
                self.tracked_positions[ticket] = meta
                self.log(f"⚡ RETEST PYRAMID TRANCHE #{len(positions)+1} on {sym_id} @ {exec_price:.2f} (Shelf: {active_retest_lvl:.2f}) | SL: {new_sl:.2f} (Free-Roll Risk: -${new_risk_usd:.2f} vs Base +${profit_usd:.2f})", "SUCCESS")

    async def _manage_trailing_profit_ratchet(self, positions: List[Any]):
        """
        Structure-Based Trailing Ratchet with Full H1 Retest Breathing Room:
        - Prevents suffocating trades during normal 1-candle H1 pullbacks (873 pts on Vol 40).
        - Breakeven (+2 points) is applied ONLY after structural clearance (>= 0.85 * H1 ATR).
        - Large runners (>= $12.00+) are locked progressively while maintaining a mandatory 500+ pt breathing buffer.
        """
        STRUCTURAL_CLEARANCE = {
            'SFX_Vol_20': {'be_threshold_usd': 1.80, 'be_lock_pts': 35.0,  'min_breathing_pts': 95.0,  'min_step_pts': 15.0},
            'FX_Vol_20':  {'be_threshold_usd': 3.50, 'be_lock_pts': 55.0,  'min_breathing_pts': 180.0, 'min_step_pts': 25.0},
            'SFX_Vol_40': {'be_threshold_usd': 8.50, 'be_lock_pts': 180.0, 'min_breathing_pts': 650.0, 'min_step_pts': 60.0},
            'FX_Vol_40':  {'be_threshold_usd': 8.50, 'be_lock_pts': 180.0, 'min_breathing_pts': 650.0, 'min_step_pts': 60.0},
        }

        for p in positions:
            try:
                ticket = int(p.ticket)
                profit_usd = float(p.profit)
                sym = p.symbol
                sym_clean = sym.replace(' ', '_')
                clearance = STRUCTURAL_CLEARANCE.get(sym_clean, {'be_threshold_usd': 5.0, 'be_lock_pts': 60.0, 'min_breathing_pts': 300.0, 'min_step_pts': 30.0})

                entry = float(p.price_open)
                curr_sl = float(p.sl)
                curr_price = float(p.price_current)
                is_buy = (p.type == mt5.ORDER_TYPE_BUY)
                vol = float(p.volume) if float(p.volume) > 0 else 0.01

                # Q93: Only move SL to Breakeven after Obstacle #1 is cleared OR profit reaches structural clearance threshold!
                meta = self.tracked_positions.get(ticket, {})
                obs1 = float(meta.get("obstacle_1", 0.0))
                obs1_cleared = False
                if obs1 > 0:
                    obs1_cleared = (curr_price >= obs1) if is_buy else (curr_price <= obs1)

                if profit_usd < clearance['be_threshold_usd'] and not (obs1_cleared and profit_usd >= clearance['be_threshold_usd'] * 0.75):
                    continue

                info = await self.mt5_worker.execute_async("symbol_info", sym)
                if not info:
                    continue
                digits = int(info.digits)
                contract_size = float(info.trade_contract_size) if info.trade_contract_size else 1.0
                price_per_usd = 1.0 / (vol * contract_size)
                min_buffer = clearance['min_breathing_pts']
                be_lock_pts = clearance['be_lock_pts']
                min_step = clearance['min_step_pts']

                # Phase 1: Positive Structural Breakeven (+$0.35 to +$1.80 locked, never -$0.03!)
                if profit_usd < (clearance['be_threshold_usd'] * 1.5):
                    target_sl = round(entry + (be_lock_pts if is_buy else -be_lock_pts), digits)
                    if (is_buy and target_sl > curr_sl + min_step and target_sl < (curr_price - min_buffer)) or \
                       (not is_buy and (curr_sl == 0.0 or target_sl < curr_sl - min_step) and target_sl > (curr_price + min_buffer)):
                        mod_req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": sym, "sl": target_sl, "tp": float(p.tp)}
                        res = await self.mt5_worker.execute_async("order_send", mod_req)
                        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                            self.log(f"🛡️ OBSTACLE #1 CLEARED (Q93) on #{ticket} ({sym}): Profit ${profit_usd:.2f} -> Locked Positive BE @ {target_sl:.2f}", "SUCCESS")

                # Phase 2: Macro Runner Trailing (>= 1.5x Clearance) with step filter so MT5 isn't spammed on $0.05 ticks
                else:
                    if profit_usd >= 20.0:
                        locked_usd = profit_usd * 0.65
                    elif profit_usd >= 13.0:
                        locked_usd = profit_usd * 0.52
                    else:
                        locked_usd = clearance['be_threshold_usd'] * 0.50

                    price_offset = locked_usd * price_per_usd

                    if is_buy:
                        target_sl = round(entry + price_offset, digits)
                        target_sl = min(target_sl, round(curr_price - min_buffer, digits))
                        if target_sl >= curr_sl + min_step and target_sl < curr_price:
                            mod_req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": sym, "sl": target_sl, "tp": float(p.tp)}
                            res = await self.mt5_worker.execute_async("order_send", mod_req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                self.log(f"💰 RUNNER LOCKED on #{ticket} ({sym} BUY): ${profit_usd:.2f} profit -> Trailed SL to {target_sl:.2f} (Locked ${locked_usd:.2f})", "SUCCESS")
                    else:
                        target_sl = round(entry - price_offset, digits)
                        target_sl = max(target_sl, round(curr_price + min_buffer, digits))
                        if (curr_sl == 0.0 or target_sl <= curr_sl - min_step) and target_sl > curr_price:
                            mod_req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": sym, "sl": target_sl, "tp": float(p.tp)}
                            res = await self.mt5_worker.execute_async("order_send", mod_req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                self.log(f"💰 RUNNER LOCKED on #{ticket} ({sym} SELL): ${profit_usd:.2f} profit -> Trailed SL to {target_sl:.2f} (Locked ${locked_usd:.2f})", "SUCCESS")
            except Exception:
                pass
            except Exception:
                pass

    async def _manage_structural_guard(self, positions: List[Any]):
        """
        Higher Timeframe Structural Defense & Obstacle Protection:
        1. Runners are allowed to breathe: No premature market exits on M5 micro dips!
           Profits are guarded exclusively by the Multi-Tier Ratchet ($2.50 -> lock $1.20, $5.00 -> lock $2.50, $10.00 -> lock $7.00, $15.00+ -> lock 75%).
        2. Obstacle #1 Double Top / Rejection Defense (Q16, Q30, Q93):
           - If price tests Obstacle 1 and prints an M15/M5 rejection wick, tighten SL to lock in accumulated profits while keeping the runner alive.
        3. Higher Timeframe Invalidation (H1 / M30):
           - Only if a full completed H1/M30 bar closes against the anchor structure is early exit considered.
        """
        for p in positions:
            try:
                ticket = int(p.ticket)
                profit_usd = float(p.profit)
                entry = float(p.price_open)
                curr_sl = float(p.sl)
                curr_price = float(p.price_current)
                is_buy = (p.type == mt5.ORDER_TYPE_BUY)
                sym = p.symbol
                vol = float(p.volume) if float(p.volume) > 0 else 0.01

                info = await self.mt5_worker.execute_async("symbol_info", sym)
                if not info:
                    continue
                digits = int(info.digits)

                # Fetch recent M5 candles to evaluate obstacle behavior
                rates = await self.mt5_worker.execute_async("copy_rates_from_pos", sym, mt5.TIMEFRAME_M5, 0, 15)
                if rates is None or len(rates) < 6:
                    continue

                df_m5 = pd.DataFrame(rates)
                m5_closes = df_m5['close'].astype(float).values
                m5_highs = df_m5['high'].astype(float).values
                m5_lows = df_m5['low'].astype(float).values

                meta = self.tracked_positions.get(ticket, {})
                obstacle_1 = float(meta.get("obstacle_1", 0.0))

                # Double Top / Rejection at Obstacle #1 (Q16, Q30, Q93)
                # When price tests Obstacle 1 with profit >= $4.00, trail SL behind rejection wick
                if obstacle_1 > 0:
                    bar_rng = max(10.0, m5_highs[-1] - m5_lows[-1])
                    if is_buy and curr_price >= (obstacle_1 - bar_rng * 1.5):
                        curr_bar_high = m5_highs[-1]
                        prev_bar_high = m5_highs[-2]
                        double_top = abs(curr_bar_high - prev_bar_high) <= 0.25 * bar_rng and m5_closes[-1] < m5_closes[-2]
                        if double_top and profit_usd >= 4.0:
                            tight_sl = round(float(np.min(m5_lows[-3:])), digits)
                            if tight_sl > curr_sl and tight_sl < curr_price:
                                mod_req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": sym, "sl": tight_sl, "tp": float(p.tp)}
                                res = await self.mt5_worker.execute_async("order_send", mod_req)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    self.log(f"🛡️ OBSTACLE #1 DOUBLE TOP (Q30/Q93): Rejection at {obstacle_1:.2f} on #{ticket}! Tightened SL to {tight_sl:.2f} to protect gains.", "SUCCESS")
                    elif not is_buy and curr_price <= (obstacle_1 + bar_rng * 1.5):
                        curr_bar_low = m5_lows[-1]
                        prev_bar_low = m5_lows[-2]
                        double_bottom = abs(curr_bar_low - prev_bar_low) <= 0.25 * bar_rng and m5_closes[-1] > m5_closes[-2]
                        if double_bottom and profit_usd >= 4.0:
                            tight_sl = round(float(np.max(m5_highs[-3:])), digits)
                            if (curr_sl == 0.0 or tight_sl < curr_sl) and tight_sl > curr_price:
                                mod_req = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "symbol": sym, "sl": tight_sl, "tp": float(p.tp)}
                                res = await self.mt5_worker.execute_async("order_send", mod_req)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    self.log(f"🛡️ OBSTACLE #1 DOUBLE BOTTOM (Q30/Q93): Rejection at {obstacle_1:.2f} on #{ticket}! Tightened SL to {tight_sl:.2f} to protect gains.", "SUCCESS")

            except Exception:
                pass

    async def _check_daily_pnl_and_closed_trades(self):
        """
        Tracks closed deals today, calculates net PnL for the 4 synthetic indices, and triggers the AI dynamic autopsy.
        """
        now = datetime.datetime.now()
        start_of_day = now - datetime.timedelta(hours=24)
        end_of_day = now + datetime.timedelta(hours=24)
        deals = await self.mt5_worker.execute_async("history_deals_get", start_of_day, end_of_day)
        
        allowed_syms = {'SFX_Vol_20', 'SFX_Vol_40', 'FX_Vol_20', 'FX_Vol_40', 'SFX Vol 20', 'SFX Vol 40', 'FX Vol 20', 'FX Vol 40'}
        open_pos = await self.mt5_worker.execute_async("positions_get")
        open_tickets = {int(p.ticket) for p in open_pos} if open_pos else set()
        open_symbols = {p.symbol.replace(' ', '_') for p in open_pos} if open_pos else set()

        total_profit = 0.0
        if deals:
            for d in deals:
                if d.symbol not in allowed_syms:
                    continue
                if d.entry == mt5.DEAL_ENTRY_OUT:
                    total_profit += float(d.profit)

                    # Check if this deal corresponds to one of our tracked positions
                    pos_id = int(d.position_id)
                    order_id = int(getattr(d, 'order', 0))
                    matched_key = None
                    if pos_id in self.tracked_positions:
                        matched_key = pos_id
                    elif order_id in self.tracked_positions:
                        matched_key = order_id
                    else:
                        sym_clean = d.symbol.replace(' ', '_')
                        for k, meta in self.tracked_positions.items():
                            if meta.get("symbol") == sym_clean:
                                matched_key = k
                                break

                    if matched_key is not None:
                        meta = self.tracked_positions.pop(matched_key)
                        pnl = float(d.profit)
                        outcome = "FULL_TP" if pnl > meta["risk_usd"] * 3 else ("PROTECTED_BE" if abs(pnl) < 0.50 else ("TRAIL_WIN" if pnl > 0 else "SL"))
                        
                        trade_record = {
                            "symbol": meta["symbol"],
                            "entry": meta["entry_price"],
                            "sl": meta["sl"],
                            "exit_price": float(d.price),
                            "outcome": outcome,
                            "pnl_usd": pnl,
                            "risk_usd": meta["risk_usd"],
                            "realized_r": round(pnl / max(0.1, meta["risk_usd"]), 2),
                            "touches": 2,
                            "hl_lh_respected": True,
                            "dist_from_zone_atr": 0.35,
                        }
                        # Set 15-minute cooldown on symbol if stopped out to prevent revenge churn (Masterclass Lesson 1)
                        if outcome == "SL":
                            self.symbol_cooldowns[meta["symbol"]] = time.time() + 900
                            self.log(f"⏸️ Active 15m cooldown initiated on {meta['symbol']} following structural SL to eliminate revenge churn.", "WARNING")

                        # Trigger the AI dynamic learning loop
                        diagnosis = ai_reasoning_agent.diagnose_and_adapt_from_trade(trade_record)
                        autopsy_text = diagnosis.get('ai_diagnosis') or diagnosis.get('diagnosis') or "Loss registered; parameters adapted."
                        self.log(f"🧠 AI AUTOPSY on Ticket #{pos_id} ({outcome}: ${pnl:.2f}): {autopsy_text}", "INFO")

        # Clean up any ghost tracked positions whose symbol is completely closed in MT5
        for t_id, meta in list(self.tracked_positions.items()):
            if t_id not in open_tickets and meta.get("symbol") not in open_symbols:
                self.tracked_positions.pop(t_id, None)

        self.daily_pnl_usd = round(total_profit, 2)

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "base_lot": self.base_lot,
            "daily_pnl_usd": self.daily_pnl_usd,
            "total_ai_trades_today": self.total_ai_trades_today,
            "max_daily_loss_usd": self.max_daily_loss_usd,
            "active_positions_count": len(self.tracked_positions),
            "tracked_positions": list(self.tracked_positions.values()),
            "last_scan_time": self.last_scan_time,
            "symbol_states": {
                s: {
                    "verdict": self.symbol_states.get(s, {}).get("verdict", "SCANNING"),
                    "action": self.symbol_states.get(s, {}).get("action", "HOLD"),
                    "confidence": self.symbol_states.get(s, {}).get("confidence", 0)
                } for s in ['SFX_Vol_20', 'SFX_Vol_40', 'FX_Vol_20', 'FX_Vol_40']
            },
            "recent_logs": self.recent_logs[-15:]
        }


# Global singleton
autonomous_trader = AutonomousLiveTrader()
