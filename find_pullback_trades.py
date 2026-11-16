import pandas as pd
import numpy as np
import os

def align_timeframes(ltf_df, htf_df, htf_name):
    ltf_df = ltf_df.sort_values('time')
    htf_df = htf_df.sort_values('time')
    
    htf_renamed = htf_df[['time', 'Struct', 'PH', 'PL']].rename(columns={
        'Struct': f'HTF_Struct_{htf_name}',
        'PH': f'HTF_PH_{htf_name}',
        'PL': f'HTF_PL_{htf_name}'
    })
    
    # Forward fill so every M5 candle knows the last confirmed HTF structure
    htf_renamed[f'HTF_Struct_{htf_name}'] = htf_renamed[f'HTF_Struct_{htf_name}'].ffill()
    htf_renamed[f'HTF_PH_{htf_name}'] = htf_renamed[f'HTF_PH_{htf_name}'].ffill()
    htf_renamed[f'HTF_PL_{htf_name}'] = htf_renamed[f'HTF_PL_{htf_name}'].ffill()

    merged = pd.merge_asof(ltf_df, htf_renamed, on='time', direction='backward')
    return merged

def find_htf_pullback_trades(symbol='FX_Vol_20'):
    print(f"--- Hunting for the 'Rubik's Cube' Pullback Trade on {symbol} ---")
    print("Logic: H1 Breaks Resistance -> Predict H1 Retest -> Short the M5 down to the H1 level.\n")
    
    m5_file = f'data/classified_{symbol}_M5.parquet'
    h1_file = f'data/classified_{symbol}_H1.parquet'
    
    if not os.path.exists(m5_file) or not os.path.exists(h1_file):
        print("Data files missing.")
        return

    m5_df = pd.read_parquet(m5_file)
    m5_df['time'] = pd.to_datetime(m5_df['time'])
    
    h1_df = pd.read_parquet(h1_file)
    h1_df['time'] = pd.to_datetime(h1_df['time'])
    
    # We need to know the *previous* H1 structure to know if a breakout happened
    h1_df['Prev_HTF_Struct'] = h1_df['Struct'].shift(1)
    h1_df['Prev_HTF_PH'] = h1_df['PH'].shift(1)
    
    cube_df = align_timeframes(m5_df, h1_df, 'H1')
    
    # Isolate rows where M5 formed a structural pivot
    struct_df = cube_df.dropna(subset=['Struct']).copy()
    struct_df.reset_index(inplace=True, drop=True)
    
    total_opportunities = 0
    
    points = struct_df.to_dict('records')
    
    for i in range(1, len(points)):
        curr_m5 = points[i]
        
        # 1. THE HTF BREAKOUT CONTEXT
        # Did H1 just form a Higher High (HH)?
        if curr_m5['HTF_Struct_H1'] == 'HH':
            
            # 2. THE PREDICTED RETEST (The Gap)
            # The broken resistance is the previous H1 Pivot High (PH).
            # If current price is significantly above that broken resistance, it has room to drop (retest).
            broken_resistance = curr_m5['HTF_PH_H1'] # In a real script, we'd track the exact LH it broke, but this approximates the zone
            
            # 3. THE LTF EXECUTION (Rubik's Cube rotation)
            # While H1 is "Bullish" (HH), we are looking to SHORT the M5.
            # We wait for the M5 to form a bearish structure (Lower High or Lower Low) 
            # indicating the pullback down to the H1 resistance has begun.
            if curr_m5['Struct'] in ['LH', 'LL']:
                
                # Check if there is enough "meat on the bone" to short down to the H1 resistance
                if curr_m5['close'] > broken_resistance * 1.001: # 0.1% buffer
                    total_opportunities += 1
                    
    print(f"Found {total_opportunities} instances where:")
    print(" 1. H1 broke out bullishly.")
    print(" 2. A massive gap was left down to the H1 resistance line.")
    print(" 3. The M5 chart turned bearish, giving you a perfect entry to SHORT the pullback.")

if __name__ == '__main__':
    find_htf_pullback_trades()
