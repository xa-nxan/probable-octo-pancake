# Mini TradingView - WelTrade Algorithmic Engine

## Phase 0: Inspect & Assumptions
Based on the review of the dataset (`data/*.parquet`) and the initial draft (`visualizer.py`), the following observations and assumptions have been established:

### Data Schema & Characteristics
*   **Source Data**: The `data/` directory contains 4 indices (`FX_Vol_20`, `FX_Vol_40`, `FlipX_1`, `FlipX_2`) spanning 10 months.
*   **Timeframes**: Tick-level data (`_ticks.parquet`) alongside aggregated standard bars (`M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `1D`).
*   **Schema**: Standard OHLCV schema (`time`, `open`, `high`, `low`, `close`, `tick_volume`, `spread`, `real_volume`). Plus structural columns generated in our earlier sweep (`is_high_micro`, `struct_micro`, `is_high_macro`, `struct_macro`).
*   **Timezone**: The `time` column is timezone-naive (`None`). **Assumption**: All timestamps correspond exactly to the broker's (WelTrade) local server time, which operates 24/7 for synthetic indices. We will handle all times as naive local broker time to avoid timezone conversion headaches unless otherwise specified.
*   **Quality**: No duplicate timestamps and no missing values in the OHLC data. (Missing values in `struct` columns are expected and represent non-swing candles).

### Code Architecture Assumptions
*   **Separation of Concerns**: The analysis/trading engine logic (resampling, swing detection, order management) will be kept entirely separated from the UI logic (Qt / `lightweight-charts`), allowing for headless automated testing.
*   **Dependency Management**: We will continue using `pandas` (with `pyarrow` engine) for historical bulk manipulation and `lightweight-charts` for rendering. If any UI blocks occur, we will evaluate the maintained fork `python-lightweight-charts` as requested.

---
*(This README will be iteratively updated as we progress through the Development Phases)*
