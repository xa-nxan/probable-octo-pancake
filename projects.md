# Algorithmic Trading Bot Project Memory

## Project Overview
This document serves as the core memory for the development of our algorithmic trading bot. It will be updated as the project evolves to keep track of goals, broker details, target instruments, and strategies.

## Target Environment
*   **Broker**: Weltrade (Note: Initially referred to as "WorldTrade").
*   **Asset Class / Division**: SyntX / Synthetic Indices (Note: Initially referred to as "Synthetix").
*   **Platform**: MetaTrader 5 (MT5), which is the standard platform for Weltrade's SyntX and supports algorithmic trading via Expert Advisors (EAs).

## Primary Instruments of Focus
Our bot will specifically target the following synthetic indices:

1.  **FX Vol 20**: A synthetic index designed to simulate a financial market with a fixed, constant annualized volatility of 20%. It operates 24/7 and is not affected by real-world economic news.
2.  **FX Vol 40**: Similar to FX Vol 20, but programmed to maintain a higher fixed annualized volatility of 40%, offering larger price swings.
3.  **FlipX 1** (Referred to as "Flippex 1"): A proprietary index that operates on a "50/50" step-by-step logic. There is a 50% probability that the price direction will change at a certain fixed step, avoiding sudden spikes.
4.  **FlipX 2** (Referred to as "Flippex 2"): Another variant in the FlipX series, sharing the same 50/50 step-by-step logic but with different specific trading conditions/limits.

## Deprioritized Instruments
While the bot focuses on the four indices above, the following SyntX instruments were acknowledged but are currently out of scope:
*   **GainX (Gain)**: Generally moves downward and jumps periodically.
*   **PainX (Pain)**: Generally moves upward and drops periodically.
*   **SFX Vols**: Synthetic FX instruments.
*   **FiboX (Fiboex)**: Based on the Fibonacci sequence, where market progression follows an accelerating growth pattern.

## Development Roadmap
*(To be populated as development begins)*
*   [ ] Connect to Weltrade MT5 via an API or bridge (e.g., Python `MetaTrader5` library or MQL5).
*   [ ] Retrieve historical data for FX Vol 20, FX Vol 40, FlipX 1, and FlipX 2.
*   [ ] Design and backtest trading strategies specific to the fixed-volatility and step-logic nature of these synthetics.
*   [ ] Implement live trading execution and risk management.

## Strategy Concepts & Data Architecture

### Core Trading Philosophy
1.  **Market Structure**: Identification of Higher Highs (HH), Higher Lows (HL), Lower Highs (LH), and Lower Lows (LL) is foundational to the bot's logic.
2.  **Fractal Candle Anatomy**:
    *   Higher timeframe candles dictate lower timeframe behavior (e.g., an H4 candle determines the bias/shape of an M5 trade).
    *   A wick on a higher timeframe (e.g., H1) is viewed as a full trend on a lower timeframe (e.g., M5).
3.  **Candle Range Limits**: Recognizing that every candle (from M1 to D1) has a typical statistical range. Once a candle fulfills its maximum range, it is expected to pull back or stall because it lacks the momentum to continue until the next candle opens. (This is especially predictable in fixed-volatility synthetics).

### Hierarchical Data Alignment
To properly execute the multi-timeframe anatomy logic, the bot's data architecture must be perfectly aligned hierarchically. The system will map timeframes from the bottom up:
*   **Tick** -> mapped to -> **M1** candle
*   **M1** -> mapped to -> **M5** candle
*   **M5** -> mapped to -> **M15** candle
*   **M15** -> mapped to -> **M30** candle
*   **M30** -> mapped to -> **H1** candle
*   **H1** -> mapped to -> **H4** candle
*   **H4** -> mapped to -> **1D** candle
This ensures that at any given tick, the bot knows exactly where it is positioned inside the anatomy of the current Daily, H4, H1, etc., candles.
