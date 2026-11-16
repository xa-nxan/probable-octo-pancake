import pandas as pd
import numpy as np

def replay_ticks_to_live_candles(df_ticks: pd.DataFrame, target_timeframe='5min'):
    """
    Simulates a live market replay. It takes raw ticks and builds the live, 
    evolving OHLC of a candle (e.g., M5) tick-by-tick, without looking ahead.
    """
    df = df_ticks.copy()
    
    # Define the container boundary for the requested timeframe
    df['candle_boundary'] = df['time'].dt.floor(target_timeframe)
    
    # We will build the OHLC progressively as if we are watching it live
    # Grouping by the boundary, we calculate the cumulative max/min up to that tick
    df['Live_Open'] = df.groupby('candle_boundary')['bid'].transform('first')
    df['Live_High'] = df.groupby('candle_boundary')['bid'].cummax()
    df['Live_Low'] = df.groupby('candle_boundary')['bid'].cummin()
    df['Live_Close'] = df['bid'] # The current tick is always the 'current close'
    
    return df

if __name__ == "__main__":
    print("Simulating a live tick feed...")
    
    # Dummy tick feed across a 5-minute window (e.g., 10:00 to 10:05)
    # Notice how the price goes up and down
    dummy_ticks = pd.DataFrame({
        'time': pd.to_datetime([
            '2026-10-07 10:00:05', # Tick 1
            '2026-10-07 10:01:30', # Tick 2 (price drops, creates lower low)
            '2026-10-07 10:03:45', # Tick 3 (price surges, creates new high)
            '2026-10-07 10:04:55'  # Tick 4 (price pulls back slightly before close)
        ]),
        'bid': [1.100, 1.090, 1.150, 1.130]
    })
    
    # Replay these ticks to see what the M5 candle looked like AT EACH TICK
    live_m5_replay = replay_ticks_to_live_candles(dummy_ticks, target_timeframe='5min')
    
    for index, row in live_m5_replay.iterrows():
        print(f"\n[Tick @ {row['time'].time()}] Current Price: {row['bid']}")
        print(f" -> M5 Candle State: O:{row['Live_Open']} | H:{row['Live_High']} | L:{row['Live_Low']} | C:{row['Live_Close']}")
        
        # Analyze the anatomy at this exact millisecond
        if row['Live_Close'] > row['Live_Open']:
            print(" -> Anatomy: Candle is GREEN.")
        else:
            print(" -> Anatomy: Candle is RED.")
            
        wick_top = row['Live_High'] - max(row['Live_Open'], row['Live_Close'])
        wick_bottom = min(row['Live_Open'], row['Live_Close']) - row['Live_Low']
        print(f" -> Current Top Wick Size: {wick_top:.3f}, Current Bottom Wick Size: {wick_bottom:.3f}")
