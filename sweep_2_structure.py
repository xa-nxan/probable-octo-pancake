import pandas as pd
import numpy as np
import os

def find_swings(df, n=2):
    """
    Finds Swing Highs and Swing Lows.
    n is the number of candles to the left and right that must be lower (for highs) or higher (for lows).
    """
    # Create rolling windows
    # For a high to be valid, it must be the max over a window of 2*n + 1
    # We use shift to align the windows
    
    highs = df['high'].rolling(window=2*n + 1, center=True).max()
    lows = df['low'].rolling(window=2*n + 1, center=True).min()
    
    # Check where the actual high equals the rolling max
    is_swing_high = df['high'] == highs
    is_swing_low = df['low'] == lows
    
    # Create a copy and mark them
    df_marked = df.copy()
    df_marked['is_high'] = is_swing_high
    df_marked['is_low'] = is_swing_low
    
    # Filter to get just the swings
    swings = df_marked[df_marked['is_high'] | df_marked['is_low']].copy()
    
    # Categorize as HH, LH, HL, LL
    swings['type'] = np.nan
    
    last_high = -np.inf
    last_low = np.inf
    
    for idx, row in swings.iterrows():
        if row['is_high']:
            if row['high'] > last_high:
                swings.at[idx, 'type'] = 'HH'
            else:
                swings.at[idx, 'type'] = 'LH'
            last_high = row['high']
            
        elif row['is_low']:
            if row['low'] > last_low:
                swings.at[idx, 'type'] = 'HL'
            else:
                swings.at[idx, 'type'] = 'LL'
            last_low = row['low']
            
    return swings.dropna(subset=['type'])

def test_market_structure(symbol="FX_Vol_20", timeframe="H4", data_dir="data"):
    print(f"Executing Sweep 2: Market Structure Test on {symbol} ({timeframe})")
    file_path = os.path.join(data_dir, f"{symbol}_{timeframe}.parquet")
    
    if not os.path.exists(file_path):
        print(f"Data file not found: {file_path}")
        return
        
    df = pd.read_parquet(file_path)
    
    # We will test N=2 (Standard 5-bar fractal) and N=5 (Macro swings, 11-bar fractal)
    print("\n--- Testing N=2 (Standard Fractal: 2 bars left, 2 bars right) ---")
    swings_n2 = find_swings(df, n=2)
    print(f"Total Structural Points Found: {len(swings_n2)}")
    print("Recent Sequence of Market Structure:")
    recent_n2 = swings_n2.tail(10)
    for idx, row in recent_n2.iterrows():
        print(f"  {row['time'].date()} | {row['type']} | Price: {row['high'] if row['is_high'] else row['low']}")
        
    print("\n--- Testing N=5 (Macro Fractal: 5 bars left, 5 bars right) ---")
    swings_n5 = find_swings(df, n=5)
    print(f"Total Structural Points Found: {len(swings_n5)}")
    print("Recent Sequence of Market Structure:")
    recent_n5 = swings_n5.tail(10)
    for idx, row in recent_n5.iterrows():
        print(f"  {row['time'].date()} | {row['type']} | Price: {row['high'] if row['is_high'] else row['low']}")
        
    # Let's see how well these structure points act as "magnets"
    # A magnet means price eventually re-visits or sweeps the high/low
    print("\nObservation:")
    print("Notice how N=5 filters out the noise and only identifies major turning points,")
    print("while N=2 gives us more frequent, micro structural points.")

if __name__ == "__main__":
    test_market_structure(symbol="FX_Vol_20", timeframe="H4")
    test_market_structure(symbol="FlipX_1", timeframe="H1")
