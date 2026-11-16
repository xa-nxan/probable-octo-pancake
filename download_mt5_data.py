import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import os

# Create data directory
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Initialize connection
if not mt5.initialize():
    print("initialize() failed, error code =", mt5.last_error())
    quit()

symbols = ['FX Vol 20', 'FX Vol 40', 'FlipX 1', 'FlipX 2']
timeframes = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "1D": mt5.TIMEFRAME_D1,
}

# Calculate date range (approx 10 months ago)
date_to = datetime.now()
date_from = date_to - timedelta(days=300)

print(f"Downloading data from {date_from.date()} to {date_to.date()}")

for symbol in symbols:
    print(f"\nProcessing {symbol}...")
    
    # 1. Download Timeframe Data (Rates)
    for tf_name, tf_code in timeframes.items():
        print(f"  Fetching {tf_name} rates...")
        rates = mt5.copy_rates_range(symbol, tf_code, date_from, date_to)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            file_path = os.path.join(data_dir, f"{symbol.replace(' ', '_')}_{tf_name}.parquet")
            df.to_parquet(file_path, index=False)
            print(f"    Saved {len(df)} rows to {file_path}")
        else:
            print(f"    No data found or error: {mt5.last_error()}")
            
    # 2. Download Tick Data
    # Downloading 10 months of ticks at once might be too large, so we split by month
    print("  Fetching tick data (chunked by 30-day periods)...")
    tick_dfs = []
    chunk_start = date_from
    while chunk_start < date_to:
        chunk_end = min(chunk_start + timedelta(days=30), date_to)
        print(f"    Fetching ticks from {chunk_start.date()} to {chunk_end.date()}...")
        ticks = mt5.copy_ticks_range(symbol, chunk_start, chunk_end, mt5.COPY_TICKS_ALL)
        if ticks is not None and len(ticks) > 0:
            df_ticks = pd.DataFrame(ticks)
            tick_dfs.append(df_ticks)
        chunk_start = chunk_end
        
    if tick_dfs:
        final_tick_df = pd.concat(tick_dfs, ignore_index=True)
        final_tick_df['time'] = pd.to_datetime(final_tick_df['time'], unit='s')
        file_path = os.path.join(data_dir, f"{symbol.replace(' ', '_')}_ticks.parquet")
        final_tick_df.to_parquet(file_path, index=False)
        print(f"  Saved total {len(final_tick_df)} ticks to {file_path}")
    else:
        print("  No tick data found.")

mt5.shutdown()
print("\nData download complete.")
