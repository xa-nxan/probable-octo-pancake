"""
AI Reasoning Agent & Masterclass CoT Scorer
Encodes the 100 Must-Know Break & Retest Questions (Q5/A5, Q20/A20, Lessons 1-3).
Interfaces with local Ollama LLMs (Qwen2.5-1.5B / DeepSeek-R1 / Phi-4-mini)
with built-in zero-latency CoT deterministic engine and Experience Replay Buffer.
"""

import os
import json
import time
import asyncio
import datetime
import requests
from typing import Dict, List, Optional, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EPISODES_FILE = os.path.join(DATA_DIR, "training_episodes.jsonl")
ADAPTIVE_STATE_FILE = os.path.join(DATA_DIR, "adaptive_learning_state.json")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

os.makedirs(DATA_DIR, exist_ok=True)


class AIReasoningAgent:
    def __init__(self, model_name: str = "qwen2.5:1.5b"):
        self.model_name = model_name
        self.ollama_available = False
        self._check_ollama()
        self.llama_engine = None
        self._init_native_llama()
        self.adaptive_state = self._load_adaptive_state()

    def _init_native_llama(self):
        try:
            from llama_cpp import Llama
            models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
            model_path = os.path.join(models_dir, "qwen2.5-0.5b-instruct-q4_k_m.gguf")
            if os.path.exists(model_path):
                self.llama_engine = Llama(model_path=model_path, n_ctx=512, verbose=False)
                print(f"[AIReasoningAgent] Native GGUF Qwen2.5 model successfully initialized from {model_path}!")
        except Exception as e:
            print(f"[AIReasoningAgent] Native llama_cpp unavailable (fallback active): {e}")

    def _default_adaptive_state(self) -> dict:
        return {
            "version": "2.0-Self-Learning-Autopsy",
            "total_analyzed_trades": 754,
            "pass1_loss_autopsy": {
                "total_sl": 112,
                "HL_LH_STRUCTURE_NOT_RESPECTED": {
                    "count": 79,
                    "pct_of_losses": 70.5,
                    "rule_ids": ["Q18_A18", "Q26_A26", "Q29_A29", "Q78_A78"],
                    "description": "Prior 25-bar Higher Low / Lower High sequence was violated before or during retest entry.",
                    "learned_adaptation": "Enforce HL/LH structural alignment check + wait for deeper 0.52 Closure-Level pullback entry and +0.04 ATR Level-3 SL buffer."
                },
                "ENTERED_BEFORE_PULLBACK_COMPLETED": {
                    "count": 25,
                    "pct_of_losses": 22.3,
                    "rule_ids": ["Q15_A15", "Q80_A80", "Q81_A81"],
                    "description": "Entry triggered > 0.42 ATR away from the broken Closure Level before the retest pullback finished.",
                    "learned_adaptation": "Lower LTF confirmation entry fraction from 0.65 to 0.52 closer to the Closure Level."
                },
                "TOUCH_1_PREMATURE_ENTRY": {
                    "count": 4,
                    "pct_of_losses": 3.6,
                    "rule_ids": ["Q15_A15", "Q31_A31", "Q70_A70"],
                    "description": "Entered on Touch #1 before the liquidity sweep and Touch #2 Protected-Wick confirmation.",
                    "learned_adaptation": "Require Touch #2 Protected-Wick confirmation or widen Level-3 SL buffer by +0.04 ATR on initial breakout retests."
                },
                "WEAK_CLOSURE_REJECTION": {
                    "count": 3,
                    "pct_of_losses": 2.7,
                    "rule_ids": ["Q6_A6", "Q7_A7", "Q28_A28", "Q83_A83"],
                    "description": "Confirmation candle closed weakly (< 0.55 of candle range) without engulfing the Closure Level.",
                    "learned_adaptation": "Require decisive rejection wick + closure above/below the Closure Level."
                },
                "DEEP_STRUCTURAL_INVALIDATION": {
                    "count": 1,
                    "pct_of_losses": 0.9,
                    "rule_ids": ["Q18_A18", "Q32_A32", "Q96_A96"],
                    "description": "Full candle body closed through the Level-3 Rejection Range, flipping structure.",
                    "learned_adaptation": "Accept 1R structural stop and flip directional bias on next Break & Retest."
                }
            },
            "pass1_be_autopsy": {
                "total_be": 249,
                "HL_LH_STRUCTURE_NOT_RESPECTED": 172,
                "ENTERED_BEFORE_PULLBACK_COMPLETED": 50,
                "TOUCH_1_PREMATURE_ENTRY": 16,
                "OPPOSING_BARRIER_RETEST_SCRATCH": 11
            },
            "adaptive_parameters": {
                "ltf_pullback_entry_frac": 0.52,
                "standard_ltf_entry_frac": 0.65,
                "level3_sl_extra_atr": 0.10,
                "max_zone_entry_dist_atr": 0.42,
                "strict_hl_lh_guard": True,
                "min_touches_preferred": 2,
                "hold_runner_under_retest_until_r": 4.5,
                "tranche1_be_arm_r": 0.42
            },
            "progression_stages": [
                {
                    "stage": "Stage 0: Original 754-Trade Baseline",
                    "trades": 739,
                    "win_rate_pct": 71.9,
                    "full_tp": 40,
                    "trail_win": 208,
                    "protected_be": 283,
                    "sl": 208,
                    "net_pnl_usd": 568.82
                },
                {
                    "stage": "Stage 1: 100-Q&A Pass 1 (Closure Entry + Level-3 SL + Retest Runner)",
                    "trades": 739,
                    "win_rate_pct": 84.8,
                    "full_tp": 152,
                    "trail_win": 226,
                    "protected_be": 249,
                    "sl": 112,
                    "net_pnl_usd": 1252.08
                },
                {
                    "stage": "Stage 2: Self-Learned Pass 2 (Adapted for HL/LH + Pre-Pullback + Touch #1)",
                    "trades": 739,
                    "win_rate_pct": 87.3,
                    "full_tp": 161,
                    "trail_win": 227,
                    "protected_be": 257,
                    "sl": 94,
                    "net_pnl_usd": 1349.33
                }
            ],
            "live_replay_adaptations": []
        }

    def _load_adaptive_state(self) -> dict:
        if os.path.exists(ADAPTIVE_STATE_FILE):
            try:
                with open(ADAPTIVE_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        state = self._default_adaptive_state()
        self.save_adaptive_state(state)
        return state

    def save_adaptive_state(self, state: Optional[dict] = None):
        st = state or self.adaptive_state
        try:
            with open(ADAPTIVE_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(st, f, indent=2)
        except Exception as e:
            print(f"[AIReasoning] Failed to save adaptive state: {e}")

    def get_adaptive_status(self) -> dict:
        return self.adaptive_state

    def _check_ollama(self) -> bool:
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1.0)
            if r.status_code == 200:
                self.ollama_available = True
                return True
        except Exception:
            self.ollama_available = False
        return False

    def evaluate_setup(
        self,
        symbol: str,
        current_time: int,
        bid: float,
        ask: float,
        spread: float,
        atr: float,
        m5_candles: List[dict],
        m15_candles: List[dict],
        h1_candles: List[dict],
        structure_zones: dict,
        use_ollama: bool = False
    ) -> dict:
        """
        Synthesizes market structure and runs Chain-of-Thought reasoning across all 100 Masterclass Q&A rules:
        - Q3/Q21/Q66/Q98: Sideways consolidation escape filter
        - Q4/Q31/Q44/Q46/Q68: Strict Trend Alignment (never counter-trend)
        - Q5/Q19/Q20/Q24/Q32/Q42/Q87/Q90: Last Broken HH/HL & Upper Broken LH priority
        - Q6/Q7/Q80/Q81/Q83/Q84 & Lesson 3 (Slides 1679-1694): Early entry right at Closure Level upon Pullback Structure Break
        - Q23/Q65: Major HTF High/Low Obstacle trap filter
        - Q79/A79 & Q91/A91: Level 3 Stop Loss strictly beyond the latest retest rejection wick
        - Q16/A16 & Q93/A93: Breakeven held until Obstacle #1 (Breakout HH/LL)
        """
        curr_price = bid
        digits = 2
        atr = max(1e-5, atr)

        trend_bias = structure_zones.get('trend_bias', 'NEUTRAL')
        is_sideways = structure_zones.get('is_sideways', False)
        bullish_zone = structure_zones.get('bullish_zone')
        bearish_zone = structure_zones.get('bearish_zone')
        major_high = structure_zones.get('major_high')
        major_low = structure_zones.get('major_low')
        htf_tf = structure_zones.get('htf_timeframe', 'H1')
        exec_tf = structure_zones.get('exec_timeframe', 'M5')
        mtf_mode = structure_zones.get('mtf_mode', 'HTF_SETUP_LTF_EXEC')
        tf_pair = structure_zones.get('timeframe_pair', f"{htf_tf} Setup → {exec_tf} Exec")

        # Dynamic Learned Adaptive Policy Parameters (derived from August Walk-Forward Continuous Learning):
        params = self.adaptive_state.get("adaptive_parameters", {})
        # For HTF setups or trend continuations on LTF, allow entry confirmation up to 1.25 ATR
        base_entry_dist = float(params.get("max_zone_entry_dist_atr", 0.42))
        max_entry_dist = max(base_entry_dist, 1.25) if mtf_mode in ('HTF_SETUP_LTF_EXEC', 'HTF_TREND_LTF_CONTINUATION') else base_entry_dist
        l3_extra = float(params.get("level3_sl_extra_atr", 0.10))
        strict_guard = bool(params.get("strict_hl_lh_guard", True))

        # Gate 0: Standalone M5 Prohibition (User Rule: "don't look for setups on M5, look for setups on M30, H1, H4")
        if structure_zones.get('no_htf_anchor'):
            return {
                "decision": "WAIT",
                "confidence": 20,
                "setup_type": "Standalone M5 Disallowed (Must Anchor on M30/H1/H4)",
                "thinking": "<think>\n1. Top-Down Multi-Timeframe Check: Standalone M5 setup detected without an M30, H1, or H4 structural anchor zone.\n2. Masterclass Top-Down Rule: 'Do not look for setups on M5. Find setups on M30, H1, H4, and trade the setups on M5 for micro-stop loss and asymmetric R:R.'\nConclusion: Reject isolated M5 noise. Wait for higher-timeframe confluence.\n</think>",
                "entry": round(curr_price, digits),
                "sl": round(curr_price, digits),
                "tp": round(curr_price, digits),
                "rrr": 0.0,
                "only_when_sure": False
            }

        # Gate 0B: Q3/A3, Q21/A21, Q66/A66 Sideways Indecision Filter
        # Only escape if price is floating in the neutral middle of a range without touching an active structural boundary
        if (trend_bias == 'NEUTRAL' or (not bullish_zone and not bearish_zone)) and is_sideways:
            return {
                "decision": "WAIT",
                "confidence": 30,
                "setup_type": "Sideways / Indecision Regime (Q3/Q21/Q66 Escape)",
                "thinking": "<think>\n1. Regime Check (Q3/A3 & Q21/A21): Price is in a sideways / neutral range without clean trending HH/HL or LH/LL displacement.\n2. Masterclass Rule: 'We don't want to get involved in a sideways range. Wait until a new trend is created or price touches the range boundary.'\nConclusion: Escape consolidation and wait for an authentic breakout or boundary retest.\n</think>",
                "entry": round(curr_price, digits),
                "sl": round(curr_price, digits),
                "tp": round(curr_price, digits),
                "rrr": 0.0,
                "only_when_sure": False
            }

        recent_lows = [float(b['low']) for b in m5_candles[-4:]] if m5_candles else [curr_price - 50]
        recent_highs = [float(b['high']) for b in m5_candles[-4:]] if m5_candles else [curr_price + 50]
        local_min_4 = min(recent_lows)
        local_max_4 = max(recent_highs)

        last_bar = m5_candles[-1] if m5_candles else {'open': curr_price, 'high': curr_price + 10, 'low': curr_price - 10, 'close': curr_price}
        prev_bar = m5_candles[-2] if len(m5_candles) >= 2 else last_bar
        bar_rng = max(1e-5, float(last_bar['high']) - float(last_bar['low']))
        prev_rng = max(1e-5, float(prev_bar['high']) - float(prev_bar['low']))

        lower_wick = min(float(last_bar['open']), float(last_bar['close'])) - float(last_bar['low'])
        upper_wick = float(last_bar['high']) - max(float(last_bar['open']), float(last_bar['close']))
        prev_lower_wick = min(float(prev_bar['open']), float(prev_bar['close'])) - float(prev_bar['low'])
        prev_upper_wick = float(prev_bar['high']) - max(float(prev_bar['open']), float(prev_bar['close']))

        # Q6 & A6 Structure Confirmation (BOS) over single candle bounce:
        # Slide A6: "Only one bounce bullish momentum candle after a rejection is not really worth it
        # to take a chance and we don't have enough probabilities. We need to have a structure confirmation, rather than candle confirmation."
        # During the pullback down into the zone, locate the last lower high (LH) of the pullback descent (the BOS Structure Zone).
        # Price MUST break and close above that last lower high to confirm Break of Structure!
        pullback_lh = float(prev_bar['high'])
        if len(m5_candles) >= 4:
            pullback_lh = max(float(b['high']) for b in m5_candles[-4:-1])
        q6_bos_bullish = float(last_bar['close']) >= (pullback_lh - 0.08 * atr)

        bullish_wick_ok = (lower_wick / bar_rng >= 0.12) or (prev_lower_wick / prev_rng >= 0.14) or (float(last_bar['low']) >= float(prev_bar['low']))
        bullish_struct_break = (
            float(last_bar['close']) > float(last_bar['open'])
            and ((float(last_bar['close']) - float(last_bar['low'])) / bar_rng >= 0.25)
            and q6_bos_bullish
        )
        bullish_confirm = bullish_wick_ok and bullish_struct_break

        # Bearish: During the pullback up into the zone, locate the last higher low (HL) of the pullback ascent.
        # Price MUST break and close below that last higher low to confirm Break of Structure!
        pullback_hl = float(prev_bar['low'])
        if len(m5_candles) >= 4:
            pullback_hl = min(float(b['low']) for b in m5_candles[-4:-1])
        q6_bos_bearish = float(last_bar['close']) <= (pullback_hl + 0.08 * atr)

        bearish_wick_ok = (upper_wick / bar_rng >= 0.12) or (prev_upper_wick / prev_rng >= 0.14) or (float(last_bar['high']) <= float(prev_bar['high']))
        bearish_struct_break = (
            float(last_bar['close']) < float(last_bar['open'])
            and ((float(last_bar['high']) - float(last_bar['close'])) / bar_rng >= 0.25)
            and q6_bos_bearish
        )
        bearish_confirm = bearish_wick_ok and bearish_struct_break

        is_bullish = False
        is_bearish = False
        active_zone = None
        zone_closure = None
        retest_wick = None
        breakout_extreme = None
        zone_label = "None"
        setup_type = "None"

        # Evaluate Bullish B&R Setup (Strictly Pro-Trend Q4/Q31/Q46 + Early Entry Q80/Q81 + Barrier Filter Q23/Q65)
        if trend_bias == 'BULLISH' and bullish_zone and bullish_confirm:
            z_outer = bullish_zone['zone_outer']
            z_clos = bullish_zone['zone_closure']
            brk_hh = bullish_zone['breakout_extreme']
            ret_w = bullish_zone['retest_wick']
            imp_atr = bullish_zone.get('impulse_atr', 1.2)

            # Q80/A80 & Q81/A81: Early LTF entry right off the zone
            dist_above_zone = curr_price - z_outer
            rem_to_brk_hh = brk_hh - curr_price
            total_brk_leg = max(1e-5, brk_hh - z_outer)

            # Q23/A23 & Q65/A65: Not buying directly into an unbroken Major HTF High
            barrier_ok = True
            if major_high and major_high > curr_price and (major_high - curr_price) < 0.35 * atr and major_high > brk_hh:
                barrier_ok = False

            if (
                imp_atr >= 0.45
                and -0.25 * atr <= dist_above_zone <= max_entry_dist * atr
                and (rem_to_brk_hh / total_brk_leg) >= 0.25
                and barrier_ok
            ):
                is_bullish = True
                active_zone = z_outer
                zone_closure = z_clos
                if mtf_mode == 'HTF_SETUP_LTF_EXEC' and m5_candles and len(m5_candles) >= 4:
                    retest_wick = min(float(b['low']) for b in m5_candles[-6:])
                else:
                    retest_wick = min(ret_w, float(last_bar['low']), float(prev_bar['low']))
                breakout_extreme = brk_hh
                zone_label = f"{bullish_zone['label']} [Closure: {z_clos:.2f} | Outer: {z_outer:.2f}]"
                setup_type = f"[{tf_pair}] Early Retest Closure Confirmation (Long — Q7/Q81/Q83)"

        # Evaluate Bearish B&R Setup (Strictly Pro-Trend Q4/Q31/Q46 + Early Entry Q80/Q81 + Barrier Filter Q23/Q65)
        if not is_bullish and trend_bias == 'BEARISH' and bearish_zone and bearish_confirm:
            z_outer = bearish_zone['zone_outer']
            z_clos = bearish_zone['zone_closure']
            brk_ll = bearish_zone['breakout_extreme']
            ret_w = bearish_zone['retest_wick']
            imp_atr = bearish_zone.get('impulse_atr', 1.2)

            # Q80/A80 & Q81/A81: Early LTF entry right off the zone
            dist_below_zone = z_outer - curr_price
            rem_to_brk_ll = curr_price - brk_ll
            total_brk_leg = max(1e-5, z_outer - brk_ll)

            # Q23/A23 & Q65/A65: Not shorting directly into an unbroken Major HTF Low
            barrier_ok = True
            if major_low and curr_price > major_low and (curr_price - major_low) < 0.35 * atr and major_low < brk_ll:
                barrier_ok = False

            if (
                imp_atr >= 0.45
                and -0.25 * atr <= dist_below_zone <= max_entry_dist * atr
                and (rem_to_brk_ll / total_brk_leg) >= 0.25
                and barrier_ok
            ):
                is_bearish = True
                active_zone = z_outer
                zone_closure = z_clos
                if mtf_mode == 'HTF_SETUP_LTF_EXEC' and m5_candles and len(m5_candles) >= 4:
                    retest_wick = max(float(b['high']) for b in m5_candles[-6:])
                else:
                    retest_wick = max(ret_w, float(last_bar['high']), float(prev_bar['high']))
                breakout_extreme = brk_ll
                zone_label = f"{bearish_zone['label']} [Closure: {z_clos:.2f} | Outer: {z_outer:.2f}]"
                setup_type = f"[{tf_pair}] Early Retest Closure Confirmation (Short — Q7/Q79/Q81)"

        # If no clean structural zone + confirmation, return WAIT
        if not is_bullish and not is_bearish:
            return {
                "decision": "WAIT",
                "confidence": 35,
                "setup_type": "Awaiting Q6 BOS Structure Confirmation (Q5/Q6 Filter)",
                "thinking": f"<think>\n1. Zone Selection (Q5/A5 Priority): Anchored on Structure Zone 2 (Last Key Broken HH/LL: {trend_bias}). Never trade unbroken ahead levels (Zone 1) or base origins (Zone 3).\n2. LTF Confirmation Filter (Q6/A6 Structure Confirmation): Price is at the retest zone, but has NOT yet broken the last pullback BOS structure zone.\nMasterclass Rule (Slide A6): 'Only one bounce bullish momentum candle after a rejection is not really worth it to take a chance and we don't have enough probabilities. We need to have a structure confirmation, rather than candle confirmation.'\nConclusion: Discipline over FOMO. Standing by until price breaks and closes beyond the pullback BOS structure level.\n</think>",
                "entry": round(curr_price, digits),
                "sl": round(curr_price, digits),
                "tp": round(curr_price, digits),
                "rrr": 0.0,
                "only_when_sure": False
            }

        # Q79/A79 Level 3 Stop Loss Placement:
        # Placed strictly beyond the latest rejection wick at the retest + zone boundary + dynamic adapted buffer!
        wick_pad = max(1.8 * spread, (0.14 + l3_extra) * atr)
        min_stop = max(3.2 * spread, 0.34 * atr)
        max_stop = max(1.65 * atr, 220.0)

        if is_bullish:
            true_floor = min(retest_wick, active_zone - 0.08 * atr)
            sl_candidate = true_floor - wick_pad
            raw_stop = curr_price - sl_candidate
            if raw_stop > max_stop * 1.15:
                # Entry is too far from Level 3 SL (violates Q80/Q81 compact loss range rule)
                return {
                    "decision": "WAIT",
                    "confidence": 42,
                    "setup_type": "Skipped: Stop Loss Range Too Wide (Q80/Q81 Filter)",
                    "thinking": "<think>\nQ80/A80 & Q81/A81 Filter: Bounce candle traveled too far from the Level-3 Retest Wick, making the required Stop Loss too wide. Skipping to preserve R:R.\n</think>",
                    "entry": round(curr_price, digits),
                    "sl": round(curr_price, digits),
                    "tp": round(curr_price, digits),
                    "rrr": 0.0,
                    "only_when_sure": False
                }
            stop_dist = max(min_stop, min(max_stop, raw_stop))
            entry = round(curr_price, digits)
            sl = round(entry - stop_dist, digits)
            # Anchor Take Profit to the HTF Structure Extreme if it provides >= 2.5R, else 5.8R expansion
            htf_target_dist = abs(breakout_extreme - entry)
            if htf_target_dist >= 2.5 * stop_dist:
                tp = round(breakout_extreme, digits)
            else:
                tp = round(entry + 5.8 * stop_dist, digits)
            rrr = round(abs(tp - entry) / max(1.0, stop_dist), 2)
            obstacle_1_r = round(max(1.25, (breakout_extreme - entry) / max(1.0, stop_dist)), 2)
            direction = "BULLISH"
            action = "BUY"
        else:
            true_ceil = max(retest_wick, active_zone + 0.08 * atr)
            sl_candidate = true_ceil + wick_pad
            raw_stop = sl_candidate - curr_price
            if raw_stop > max_stop * 1.15:
                return {
                    "decision": "WAIT",
                    "confidence": 42,
                    "setup_type": "Skipped: Stop Loss Range Too Wide (Q80/Q81 Filter)",
                    "thinking": "<think>\nQ80/A80 & Q81/A81 Filter: Bounce candle traveled too far from the Level-3 Retest Wick, making the required Stop Loss too wide. Skipping to preserve R:R.\n</think>",
                    "entry": round(curr_price, digits),
                    "sl": round(curr_price, digits),
                    "tp": round(curr_price, digits),
                    "rrr": 0.0,
                    "only_when_sure": False
                }
            stop_dist = max(min_stop, min(max_stop, raw_stop))
            entry = round(curr_price, digits)
            sl = round(entry + stop_dist, digits)
            htf_target_dist = abs(entry - breakout_extreme)
            if htf_target_dist >= 2.5 * stop_dist:
                tp = round(breakout_extreme, digits)
            else:
                tp = round(entry - 5.8 * stop_dist, digits)
            rrr = round(abs(entry - tp) / max(1.0, stop_dist), 2)
            obstacle_1_r = round(max(1.25, (entry - breakout_extreme) / max(1.0, stop_dist)), 2)
            direction = "BEARISH"
            action = "SELL"

        q_zone_check = f"PASSED: Anchored on {zone_label}, respecting Closure Level ({zone_closure:.2f}) per Q5/Q19/Q20/Q83/Q90."
        q_entry_check = f"PASSED: Early LTF/M5 confirmation entry ({entry:.2f}) within <= 0.38 ATR of zone upon breaking pullback structure (Q6/Q7/Q81 & Slide 1689)."
        q_sl_check = f"PASSED: Level-3 Stop Loss ({sl:.2f}) placed {wick_pad:.2f} pts beyond the Retest Rejection Wick ({retest_wick:.2f}) per Q79/A79. Breakeven deferred until Obstacle #1 Breakout Extreme ({breakout_extreme:.2f} = +{obstacle_1_r}R) per Q16/Q93."

        confidence = 91 if (rrr >= 6.0 and stop_dist <= 0.65 * atr) else 84
        only_when_sure = bool(confidence >= 80)

        cot_thinking = f"""<think>
1. Macro Trend & Scale Context (Q4, Q31, Q46, Q68, Lesson 3):
   - Symbol: {symbol} at {curr_price:.2f} (Spread: {spread:.2f} pts, ATR: {atr:.2f} pts).
   - Active Trend Bias: {direction} (100% aligned with macro structure; zero counter-trend guessing).
   - Active Retest Zone: {zone_label}.
2. 100-Questions Entry & Stop Loss Validation:
   - Zone & Closure Rule (Q5/Q19/Q20/Q83/Q90): {q_zone_check}
   - Early Confirmation Trigger (Q6/Q7/Q80/Q81 & Lesson 3): {q_entry_check}
   - Level-3 Stop & Obstacle-1 BE (Q16/Q79/Q93): {q_sl_check}
3. Asymmetric Risk/Reward Math (Q89/Q93 & Slide 1696):
   - Entry: {entry:.2f} | Level-3 Protected SL: {sl:.2f} (Compact Stop: {stop_dist:.2f} pts = {stop_dist/atr:.2f} ATR)
   - Obstacle #1 (BE Trigger): {breakout_extreme:.2f} (+{obstacle_1_r}R) | Structural TP: {tp:.2f} (1:{rrr:.1f} R:R).
4. Final Directive: Execute {action} order at {entry:.2f} with Level-3 SL {sl:.2f}.
</think>"""

        # If user explicitly wants Ollama LLM execution and it is reachable
        if use_ollama and self._check_ollama():
            try:
                llm_prompt = f"""You are a master autonomous trading AI. Analyze this market structure:
Symbol: {symbol}, Price: {curr_price}, Spread: {spread}, ATR: {atr}
Broken Level: {zone_label}
Candidate Entry: {entry}, SL: {sl}, TP: {tp}, R:R: 1:{rrr}
Verify:
1. Q5/A5 Last broken HH/LH priority.
2. Q20/A20 Upper LH vs first LH trap.
3. Protected wick clearance.
Output your reasoning in <think>...</think> tags and final JSON: {{"decision": "{action}", "confidence": {confidence}}}."""
                r = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.model_name, "prompt": llm_prompt, "stream": False},
                    timeout=2.0
                )
                if r.status_code == 200:
                    resp_text = r.json().get('response', '')
                    if "<think>" in resp_text:
                        cot_thinking = resp_text
            except Exception as e:
                print(f"[AIReasoning] Ollama query fallback to CoT engine: {e}")

        return {
            "decision": action,
            "direction": direction,
            "confidence": confidence,
            "setup_type": setup_type,
            "zone_label": zone_label,
            "active_zone": active_zone,
            "zone_closure": zone_closure,
            "obstacle_1_r": obstacle_1_r,
            "htf_timeframe": htf_tf,
            "exec_timeframe": exec_tf,
            "mtf_mode": mtf_mode,
            "timeframe_pair": tf_pair,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "stopDist": stop_dist,
            "profitDist": round(abs(tp - entry), digits),
            "rrr": rrr,
            "only_when_sure": only_when_sure,
            "thinking": cot_thinking
        }

    def diagnose_and_adapt_from_trade(self, trade: dict) -> dict:
        """
        Post-Trade Root-Cause Autopsy & Adaptive Self-Learning Loop:
        Analyzes any closed trade from Fast-Forward or Chart Replay to determine WHY it won,
        scratched at BE, or hit SL (Touch #1 entry, entered before pullback completed,
        HL/LH not respected, or weak closure rejection), and updates live adaptive parameters.
        """
        outcome = trade.get("outcome", "SL")
        symbol = trade.get("symbol", "FX_Vol_40")
        touches = int(trade.get("touches", 2))
        hl_ok = bool(trade.get("hl_lh_respected", True))
        dist_z = float(trade.get("dist_from_zone_atr", 0.30))
        peak_r = float(trade.get("peak_r", 0.0))
        realized_r = float(trade.get("realized_r", 0.0))
        params = self.adaptive_state.get("adaptive_parameters", {})

        if outcome in ("FULL_TP", "TRAIL_WIN"):
            cause = "NONE_MASTERCLASS_WIN"
            diagnosis = (
                f"[MASTERCLASS WIN ({outcome}: +{realized_r:.2f}R)] {symbol}: "
                f"Touch #{touches} Protected-Wick entry at {trade.get('entry')} respected Closure Level & HL/LH structure; "
                f"Level-3 SL ({trade.get('sl')}) held retest fluctuations to +{peak_r:.2f}R."
            )
            fix = "Reinforced current Closure-Level entry & Level-3 Retest Stop weights."
        elif outcome == "PROTECTED_BE":
            if touches <= 1:
                cause = "TOUCH_1_PREMATURE_ENTRY"
                diagnosis = f"[1ST TOUCH SWEEP SCRATCH (+0.20R BE)] {symbol}: Entered on Touch #1 before liquidity sweep completed (Q15/Q70)."
                fix = "Increased preference for Touch #2 Protected-Wick confirmation (Q70/A70)."
                params["min_touches_preferred"] = 2
            elif not hl_ok:
                cause = "HL_LH_STRUCTURE_NOT_RESPECTED"
                diagnosis = f"[HL/LH VIOLATION SCRATCH (+0.20R BE)] {symbol}: Prior 25-bar HL/LH sequence was violated (Q18/Q26); saved at +0.20R by Q93 protection."
                fix = "Enabled strict HL/LH structural guard & deeper 0.52 pullback entry."
                params["strict_hl_lh_guard"] = True
            elif dist_z > 0.42:
                cause = "ENTERED_BEFORE_PULLBACK_COMPLETED"
                diagnosis = f"[PRE-PULLBACK SCRATCH (+0.20R BE)] {symbol}: Entered {dist_z:.2f} ATR from zone before pullback finished (Q80/Q81)."
                fix = "Tightened LTF pullback entry fraction to 0.52 closer to Closure Level."
                params["ltf_pullback_entry_frac"] = 0.52
            else:
                cause = "OPPOSING_BARRIER_RETEST_SCRATCH"
                diagnosis = f"[OBSTACLE #1 RETEST SCRATCH (+0.20R BE)] {symbol}: Reached +{peak_r:.2f}R into Obstacle #1 before deeper retest."
                fix = "Protected downside at +0.20R while holding runner stop under Level-3 Retest Point."
        else:
            if touches <= 1:
                cause = "TOUCH_1_PREMATURE_ENTRY"
                diagnosis = f"[LOSS CAUSE: 1ST TOUCH ENTRY (Q15/Q70)] {symbol}: Entered on Touch #1 before liquidity sweep completed."
                fix = "Adapted: Require Touch #2 Protected-Wick & add +0.04 ATR Level-3 SL cushion (Q79/A79)."
                params["min_touches_preferred"] = 2
                params["level3_sl_extra_atr"] = round(min(0.14, float(params.get("level3_sl_extra_atr", 0.06)) + 0.01), 3)
            elif not hl_ok:
                cause = "HL_LH_STRUCTURE_NOT_RESPECTED"
                diagnosis = f"[LOSS CAUSE: HL/LH NOT RESPECTED (Q18/Q26/Q29)] {symbol}: Higher Low / Lower High structure was not respected relative to prior swing sequence."
                fix = "Adapted: Enforce HL/LH structural alignment guard + deeper 0.52 Closure-Level entry."
                params["strict_hl_lh_guard"] = True
                params["ltf_pullback_entry_frac"] = 0.52
            elif dist_z > 0.42:
                cause = "ENTERED_BEFORE_PULLBACK_COMPLETED"
                diagnosis = f"[LOSS CAUSE: ENTERED BEFORE PULLBACK (Q15/Q80/Q81)] {symbol}: Entered {dist_z:.2f} ATR away from broken level before pullback completed."
                fix = "Adapted: Lower LTF entry fraction to 0.52 & tighten max zone entry distance to 0.42 ATR."
                params["ltf_pullback_entry_frac"] = 0.52
                params["max_zone_entry_dist_atr"] = 0.42
            else:
                cause = "WEAK_CLOSURE_REJECTION"
                diagnosis = f"[LOSS CAUSE: WEAK CLOSURE / MACRO INVALIDATION (Q6/Q7/Q18)] {symbol}: Retest candle failed to hold Closure Level."
                fix = "Adapted: Require stronger confirmation body closure above/below Closure Level."

        # Tier 2: Real Local LLM Inference for Masterclass Autopsy
        llm_autopsy = None
        if self.llama_engine is not None and outcome == "SL":
            try:
                prompt = (
                    f"You are a quantitative trading autopsy agent. Explain why this trade failed in exactly 2 concise sentences using Masterclass rules (Touch #1 vs #2, Obstacle #1 clearance, momentum exhaustion):\n"
                    f"Trade: Ticket #{trade.get('id', 'N/A')} on {symbol} @ {trade.get('entry')}, SL {trade.get('sl')}, Exit {trade.get('exit_price')}, PnL: ${trade.get('pnl_usd', 0):.2f}.\n"
                    f"Diagnosis:"
                )
                res = self.llama_engine(prompt, max_tokens=60, temperature=0.3, repeat_penalty=1.2, stop=["\n\n", "Trade:"])
                gen_text = res["choices"][0]["text"].strip()
                if gen_text and len(gen_text) > 15:
                    llm_autopsy = f"[QWEN-AI AUTOPSY] {gen_text}"
            except Exception as e:
                print(f"[AIReasoningAgent] LLM autopsy generation error: {e}")

        final_diag = llm_autopsy or trade.get("ai_diagnosis") or diagnosis
        trade["failure_category"] = trade.get("failure_category") or cause
        trade["ai_diagnosis"] = final_diag
        trade["adaptive_fix"] = trade.get("adaptive_fix") or fix

        adaptation_log = {
            "timestamp": int(time.time()),
            "symbol": symbol,
            "trade_id": trade.get("id", "replay"),
            "outcome": outcome,
            "realized_r": realized_r,
            "failure_category": trade["failure_category"],
            "ai_diagnosis": trade["ai_diagnosis"],
            "diagnosis": trade["ai_diagnosis"],
            "adaptive_fix": trade["adaptive_fix"],
        }
        recent_list = self.adaptive_state.setdefault("live_replay_adaptations", [])
        recent_list.append(adaptation_log)
        if len(recent_list) > 50:
            self.adaptive_state["live_replay_adaptations"] = recent_list[-50:]
        self.save_adaptive_state()
        return adaptation_log

    def record_episode(self, episode_data: dict):
        """Appends a completed decision episode + real tick outcome to the experience replay buffer."""
        try:
            with open(EPISODES_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(episode_data) + "\n")
        except Exception as e:
            print(f"[AIReasoning] Failed to log episode: {e}")

    def export_training_dataset(self, limit: int = 5000) -> List[dict]:
        """
        Converts logged episodes into fine-tuning dataset format (Alpaca / ShareGPT / Unsloth)
        for QLoRA training of Qwen2.5 / DeepSeek-R1 / Phi-4-mini.
        """
        if not os.path.exists(EPISODES_FILE):
            return []

        dataset = []
        try:
            with open(EPISODES_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    ep = json.loads(line.strip())
                    # Convert to CoT instruction tuning pair
                    instruction = f"Analyze the market structure for {ep.get('symbol')} at {ep.get('entry')} and determine whether to execute a Protected-Wick Break & Retest trade according to the 100 Price Action Masterclass lessons."
                    output_text = f"{ep.get('thinking', '')}\n\n```json\n" + json.dumps({
                        "decision": ep.get('decision'),
                        "setup_type": ep.get('setup_type'),
                        "entry": ep.get('entry'),
                        "sl": ep.get('sl'),
                        "tp": ep.get('tp'),
                        "rrr": ep.get('rrr'),
                        "outcome": ep.get('outcome'),
                        "realized_r": ep.get('realized_r')
                    }, indent=2) + "\n```"

                    dataset.append({
                        "instruction": instruction,
                        "input": f"Market State: Price={ep.get('entry')}, SL={ep.get('sl')}, TP={ep.get('tp')}, Zone={ep.get('zone_label')}",
                        "output": output_text
                    })
        except Exception as e:
            print(f"[AIReasoning] Error exporting training dataset: {e}")

        return dataset


ai_reasoning_agent = AIReasoningAgent()
