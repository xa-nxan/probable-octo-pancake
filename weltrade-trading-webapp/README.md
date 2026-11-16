# Weltrade Synthetics Trading Terminal (Standalone Webapp)

A clean, self-contained **MetaTrader 5 + Weltrade Synthetics Trading Webapp** containing **100% of the live trading, charting, order execution, position management, and Weltrade Safe Vault features** without any AI/ML/backtest demo files.

---

## Quick Start (One-Click Install & Launch)

1. **Install all dependencies (Python + Playwright Chromium + Node.js):**
   Double-click **`install.bat`** (or run `.\install.ps1` in PowerShell).
2. **Launch the Trading Terminal:**
   Double-click **`start.bat`**.
   - **Backend API & WebSocket:** `http://127.0.0.1:8000`
   - **Frontend Trading UI:** `http://localhost:5173`

> **Note:** This folder is 100% portable. You can copy or move `weltrade-trading-webapp` anywhere on your PC and run `install.bat` and `start.bat`.

---

## Included Features

### 1. Live MT5 Streaming & Zero-Lag Caching
- **`backend/app/mt5_worker.py`**: Dedicated single-thread MetaTrader 5 C-API executor (`mt5_exec`) preventing GIL deadlocks, with native **Account Switching** between **Weltrade-Real (`#34967194`)** and **Weltrade-Demo (`#43373678`)**, real-time symbol resolution (`FX Vol 20`, `FX Vol 40`, `SFX Vol 20`, `SFX Vol 40`, `FlipX 1-5`, `PainX`, `GainX`, etc.), risk & lot sizing calculator, and position/order management.
- **`backend/app/live_cache.py`**: Sub-millisecond background poller (250ms ticks, account & position state, and 700-bar OHLCV timeframe cache across `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`).
- **`backend/app/market_hub.py`**: Real-time WebSocket broadcaster (`/replay/ws`) streaming live ticks, candle countdowns, account metrics, positions, pending orders, and continuous **Candle Integrity Verification & Auto-Healing** against MT5.

### 2. Full Order Execution & Position Management (`backend/main.py` & `frontend/src/`)
- **Interactive On-Chart Execution**:
  - **1-Click Quick Buy / Sell** buttons directly on the chart.
  - **Interactive Risk Projection Tool (`LONG` / `SHRT` & Trade Drawer)**: Drag Entry, Stop Loss, and Take Profit lines directly on the chart; auto-detects **Market**, **Stop**, or **Limit** orders based on price relative to current Bid/Ask.
  - **Armed On-Candle-Close Execution**: Option to wait for a candle (`M1`, `M5`, `M15`, `M30`, `H1`, `H4`) to close beyond your trigger price before firing the MT5 market order, with live SL distance validation.
  - **Draggable Live Positions & Pending Orders**: Drag SL, TP, or Pending Entry lines directly on the chart to modify MT5 orders in real time.
- **Advanced Position Controls**:
  - **⚡ Pyramid (`PyramidModal.tsx`)**: Scale into winning trades by locking a shared Take Profit and moving existing + new positions to a protected Breakeven/Lock price.
  - **🛡️ Lock +Margin**: One-click SL lock that guarantees a minimum `+$0.50` net profit buffer above entry.
  - **Lock BE**: One-click move Stop Loss to exact entry price.
  - **50% Partial Close**: Close half of your running volume immediately to bank profit.
  - **💰 Bank & Ride**: Close the full position to realize profits into your balance and immediately reopen a fresh rider position with the same SL/TP.
  - **Edit SL/TP (`EditOrderModal.tsx`)**: Fine-tune price, points, and dollar risk/reward on any open position or pending order.
  - **🚨 PANIC: Flatten All**: Emergency 1-click button that closes all open positions and cancels all pending/armed orders simultaneously.
  - **🛡️ Auto-Position Guardian (`GUARDIAN BE` toggle)**: Background guardian loop that automatically locks Breakeven at `+1.8R` and trails M5 structural swings at `+2.0R+`.

### 3. Weltrade Safe Vault Integration (`backend/app/weltrade_bridge.py` & `WeltradeSafeModal.tsx`)
- Direct in-app **Safe Vault Deposit & Withdrawal** modal connected to your Weltrade Personal Area (`MT5 <-> Safe Vault` transfers), with 2FA OTP support and persistent browser session caching.

### 4. Charting & Drawing Suite (`ChartComponent.tsx` & `DrawingToolbar.tsx`)
- Full TradingView Lightweight Charts terminal with **EMA 20 / 50 / 200**, **Session High/Low levels**, **Orderflow Delta Pressure**, **Bar Replay Mode**, and persistent per-symbol **Drawing Tools** (Horizontal Ray, Trendline, Rectangle Zone, Callout, Long/Short Projection, Lock, Hide, Clear).
