import pandas as pd
import numpy as np

def align_tick_to_timeframes(df_ticks: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a dataframe of raw ticks and hierarchically aligns every single tick 
    to its parent candle across all timeframes.
    
    Expected input: df_ticks with a 'time' column (datetime).
    """
    df = df_ticks.copy()
    
    # Ensure 'time' is datetime
    if not pd.api.types.is_datetime64_any_dtype(df['time']):
        df['time'] = pd.to_datetime(df['time'])

    # 1. Map Tick -> M1 (Floor to the nearest minute)
    df['M1_candle'] = df['time'].dt.floor('1min')
    
    # 2. Map M1 -> M5 (Floor to the nearest 5 minutes)
    df['M5_candle'] = df['time'].dt.floor('5min')
    
    # 3. Map M5 -> M15
    df['M15_candle'] = df['time'].dt.floor('15min')
    
    # 4. Map M15 -> M30
    df['M30_candle'] = df['time'].dt.floor('30min')
    
    # 5. Map M30 -> H1
    df['H1_candle'] = df['time'].dt.floor('1h')
    
    # 6. Map H1 -> H4
    # H4 requires standard MT5 alignment (usually anchored to 00:00)
    df['H4_candle'] = df['time'].dt.floor('4h')
    
    # 7. Map H4 -> 1D
    df['D1_candle'] = df['time'].dt.floor('1d')
    
    return df

def get_candle_anatomy(tick_time, df_aligned: pd.DataFrame):
    """
    Example function to get the exact state of all parent candles
    for a specific tick time.
    """
    pass

if __name__ == "__main__":
    print("Testing the hierarchical alignment logic...")
    # Create dummy tick data
    dummy_ticks = pd.DataFrame({
        'time': [
            '2026-10-07 14:32:45',
            '2026-10-07 14:34:10',
            '2026-10-07 15:01:20'
        ],
        'bid': [1.05, 1.06, 1.07],
        'ask': [1.051, 1.061, 1.071]
    })
    
    aligned_df = align_tick_to_timeframes(dummy_ticks)
    
    # Display the alignment for the first tick
    tick = aligned_df.iloc[0]
    print(f"Raw Tick Time: {tick['time']}")
    print(f" -> belongs to M1 candle at:  {tick['M1_candle'].time()}")
    print(f" -> belongs to M5 candle at:  {tick['M5_candle'].time()}")
    print(f" -> belongs to M15 candle at: {tick['M15_candle'].time()}")
    print(f" -> belongs to M30 candle at: {tick['M30_candle'].time()}")
    print(f" -> belongs to H1 candle at:  {tick['H1_candle'].time()}")
    print(f" -> belongs to H4 candle at:  {tick['H4_candle'].time()}")
    print(f" -> belongs to D1 candle at:  {tick['D1_candle'].date()}")
