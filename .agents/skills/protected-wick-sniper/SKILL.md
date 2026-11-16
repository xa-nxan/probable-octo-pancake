---
name: protected-wick-sniper
description: >-
  3-Step Protected-Wick Break & Retest AI/ML Sniper strategy for Weltrade Synthetic
  Indices (FX Vol 20, FX Vol 40, SFX Vol 20, SFX Vol 40). Encodes the 100 Must-Know
  Break & Retest Questions, 3 Price Action Masterclass Lessons, and walk-forward
  AI/ML conviction scoring for 70%+ Protected Win Rate and 1:5 to 1:11+ R:R setups
  resolving within 1 to 3 H1 candles.
risk: safe
source: workspace
---

# Protected-Wick AI/ML Sniper (`FX Vol 20`, `FX Vol 40`, `SFX Vol 20`, `SFX Vol 40`)

## Scope & Universe
- **Strictly Restricted Universe:** `FX_Vol_20`, `FX_Vol_40`, `SFX_Vol_20`, `SFX_Vol_40`. Never include `FlipX` or `Vol 60/80/99`.
- **Target Outcome:**
  - **Risk-to-Reward (`R:R`):** `1 : 5.0` to `1 : 11.5+` (sized on `M5`/`M15` Protected-Wick base, targeting `H1`/`M30` swing extremes).
  - **Resolution Time:** `1 to 3 H1 candles` (`7 to 36 M5 candles` or `3 to 12 M15 candles`).
  - **Protected Win / Non-Loss Rate:** `70%+` (`72.1%–87.5%+` in the Top AI/ML Conviction Tier) with `4 to 8` high-conviction trades per day across all 4 indices combined ("Only When Sure").

## The 3-Step Protected-Wick Anatomy (100 Q&A + Lessons 1–3)
1. **Step 1 — Prior Impulse Break & Touch #1 Boundary Wick (`Q6`, `Q13`, `Q70`):**
   - Price makes an impulsive move ($\ge 1.2 \times \text{ATR}$) aligned with `H1`/`M30` structure.
   - The first pullback prints **Touch #1 (`w1_low` or `w1_high`)** and bounces away ($\ge 1.1 \times \text{ATR}$).
2. **Step 2 — Touch #2 Protected-Wick Absorption (`Q79 Level 3` + Lesson 2):**
   - Price returns 3–18 bars later to retest the zone.
   - **Protected Wick Rule:** Touch #2's wick holds **strictly inside Touch #1's wick** (`Touch #2 Low > Touch #1 Low` for Longs; `Touch #2 High < Touch #1 High` for Shorts), proving counter-trend exhaustion.
   - Candle bodies close inside the **Closure Level (`zone_closure`)**, creating a compact `[Wick Tip .. Closure Level]` base (`Risk <= 0.65 × ATR`).
3. **Step 3 — Precision Entry (`On Close` or Closure-Level Retest) & `Q93` Fast Breakeven Lock:**
   - **Entry:** At the `zone_closure` floor/ceiling or `On Close` of the rejection candle (`Entry = c[i] ± spread`).
   - **Stop Loss (`SL`):** Tucked strictly behind Touch #1's outer wick (`w1_low - spread - buffer` or `w1_high + spread + buffer`).
   - **Take Profit (`TP`):** Prior `H1` / 48-to-60 bar swing extreme ($\ge 5\text{R}$ to $12\text{R}$).
   - **Fast Breakeven Protection (`Q93`):** Lock SL at Breakeven (`+0.05R` to `+0.15R`) as soon as the first ignition push reaches `+0.50R` to `+0.85R`.
