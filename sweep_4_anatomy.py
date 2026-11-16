import pandas as pd
import numpy as np
import os

def analyze_candle_anatomy(symbol='FX_Vol_20'):
    print(f"--- Dissecting the Rubik's Cube: Anatomy of {symbol} ---")
    
    h1_file = f'data/classified_{symbol}_H1.parquet'
    m5_file = f'data/classified_{symbol}_M5.parquet'
    
    if not os.path.exists(h1_file) or not os.path.exists(m5_file):
        print("Data files not found.")
        return
        
    h1_df = pd.read_parquet(h1_file)
    m5_df = pd.read_parquet(m5_file)
    
    # Calculate H1 candle anatomy (Wicks and Bodies)
    h1_df['total_range'] = h1_df['high'] - h1_df['low']
    h1_df['body_top'] = np.maximum(h1_df['open'], h1_df['close'])
    h1_df['body_bottom'] = np.minimum(h1_df['open'], h1_df['close'])
    h1_df['upper_wick'] = h1_df['high'] - h1_df['body_top']
    h1_df['lower_wick'] = h1_df['body_bottom'] - h1_df['low']
    
    # Find H1 candles with a massive upper wick (Rejection / Pin Bar)
    # Let's say the upper wick is > 50% of the total candle range
    rejection_candles = h1_df[h1_df['upper_wick'] > (0.5 * h1_df['total_range'])]
    
    print(f"Found {len(rejection_candles)} H1 candles with massive upper wicks (Rejections).")
    print("Let's look inside them on the M5 timeframe...\n")
    
    # Sample the first few massive rejections
    sample = rejection_candles.head(3)
    
    for idx, h1_candle in sample.iterrows():
        h1_start_time = h1_candle['time']
        # H1 candle lasts 1 hour. So M5 candles from start_time to start_time + 1 hour
        h1_end_time = h1_start_time + pd.Timedelta(hours=1)
        
        print(f"[{h1_start_time}] H1 Candle Analysis:")
        print(f"  - Total Range: {h1_candle['total_range']:.2f}")
        print(f"  - Upper Wick: {h1_candle['upper_wick']:.2f} (This looks just like a wick on H1)")
        
        # Extract the M5 candles inside this exact H1 candle
        m5_inside = m5_df[(m5_df['time'] >= h1_start_time) & (m5_df['time'] < h1_end_time)]
        
        # Count structural pivots inside the wick
        m5_structs = m5_inside.dropna(subset=['Struct'])['Struct'].tolist()
        
        print(f"  - Dropping down to M5... we find {len(m5_inside)} M5 candles.")
        print(f"  - M5 Structure formed inside this single H1 wick: {m5_structs}")
        if 'HH' in m5_structs and 'LL' in m5_structs:
            print("  - CONCLUSION: The M5 trended UP (HH), hit resistance, and crashed DOWN (LL) all while the H1 was just drawing a single wick!\n")
        else:
            print("\n")

if __name__ == '__main__':
    analyze_candle_anatomy()
