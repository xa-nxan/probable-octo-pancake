import pandas as pd
import numpy as np
import os

def find_swings_advanced(df, n):
    """
    Identifies swings based on window 'n'.
    Returns columns to append to the main dataframe.
    """
    highs = df['high'].rolling(window=2*n + 1, center=True).max()
    lows = df['low'].rolling(window=2*n + 1, center=True).min()
    
    is_swing_high = df['high'] == highs
    is_swing_low = df['low'] == lows
    
    types = pd.Series(index=df.index, dtype=object)
    
    last_high = -np.inf
    last_low = np.inf
    
    for idx in df.index[is_swing_high | is_swing_low]:
        if is_swing_high[idx]:
            if df.at[idx, 'high'] > last_high:
                types.at[idx] = 'HH'
            else:
                types.at[idx] = 'LH'
            last_high = df.at[idx, 'high']
            
        elif is_swing_low[idx]:
            if df.at[idx, 'low'] > last_low:
                types.at[idx] = 'HL'
            else:
                types.at[idx] = 'LL'
            last_low = df.at[idx, 'low']
            
    return is_swing_high, is_swing_low, types

def generate_structure_all_timeframes(data_dir="data"):
    symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
    timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', '1D']
    
    print("Generating Structure Parquets for all symbols and ALL timeframes...")

    for symbol in symbols:
        for tf in timeframes:
            file_path = os.path.join(data_dir, f"{symbol}_{tf}.parquet")
            
            if not os.path.exists(file_path):
                print(f"Skipping {symbol} {tf} - file not found.")
                continue
                
            print(f"Processing {symbol} [{tf}]...")
            df = pd.read_parquet(file_path)
            
            if df.empty:
                continue
            
            # Calculate Micro Structure (N=2)
            is_high_n2, is_low_n2, types_n2 = find_swings_advanced(df, n=2)
            df['is_high_micro'] = is_high_n2
            df['is_low_micro'] = is_low_n2
            df['struct_micro'] = types_n2
            
            # Calculate Macro Structure (N=5)
            is_high_n5, is_low_n5, types_n5 = find_swings_advanced(df, n=5)
            df['is_high_macro'] = is_high_n5
            df['is_low_macro'] = is_low_n5
            df['struct_macro'] = types_n5

            out_path = os.path.join(data_dir, f"{symbol}_{tf}_structure.parquet")
            df.to_parquet(out_path, index=False)
            
    print("\nSuccessfully generated structure parquets for all timeframes!")

if __name__ == "__main__":
    generate_structure_all_timeframes()
