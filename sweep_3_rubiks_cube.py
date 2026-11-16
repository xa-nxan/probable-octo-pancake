import pandas as pd
import numpy as np
import os
import math

def align_timeframes(ltf_df, htf_df, htf_name):
    ltf_df = ltf_df.sort_values('time')
    htf_df = htf_df.sort_values('time')
    
    htf_renamed = htf_df[['time', 'Struct', 'PH', 'PL']].rename(columns={
        'Struct': f'HTF_Struct_{htf_name}',
        'PH': f'HTF_PH_{htf_name}',
        'PL': f'HTF_PL_{htf_name}'
    })
    
    htf_renamed[f'HTF_Struct_{htf_name}'] = htf_renamed[f'HTF_Struct_{htf_name}'].ffill()
    htf_renamed[f'HTF_PH_{htf_name}'] = htf_renamed[f'HTF_PH_{htf_name}'].ffill()
    htf_renamed[f'HTF_PL_{htf_name}'] = htf_renamed[f'HTF_PL_{htf_name}'].ffill()

    merged = pd.merge_asof(ltf_df, htf_renamed, on='time', direction='backward')
    return merged

def run_rubiks_cube(symbol='FX_Vol_20'):
    print("--- Starting Rubik's Cube Engine (Win Rate Analysis) ---")
    
    ltf_file = f'data/classified_{symbol}_M5.parquet'
    print(f"Base Execution Timeframe: M5 (Loaded from {ltf_file})")
    
    if not os.path.exists(ltf_file):
        print(f"Error: {ltf_file} not found. Please run classify_all_structure.py first.")
        return

    m5_df = pd.read_parquet(ltf_file)
    m5_df['time'] = pd.to_datetime(m5_df['time'])
    
    htf_list = ['M15', 'M30', 'H1', 'H4']
    
    for htf in htf_list:
        htf_file = f'data/classified_{symbol}_{htf}.parquet'
        
        if not os.path.exists(htf_file):
            print(f"\n[Notice] {htf_file} not found.")
            continue
            
        print(f"\nAnalyzing Combination: Context = {htf} | Execution = M5")
        htf_df = pd.read_parquet(htf_file)
        htf_df['time'] = pd.to_datetime(htf_df['time'])
        
        cube_df = align_timeframes(m5_df, htf_df, htf)
        
        # Isolate only rows where M5 actually formed a structural pivot
        struct_df = cube_df.dropna(subset=['Struct']).copy()
        struct_df.reset_index(inplace=True, drop=True)
        
        total_setups = 0
        winning_setups = 0
        
        points = struct_df.to_dict('records')
        
        for i in range(1, len(points) - 1):
            prev_m5 = points[i-1]
            curr_m5 = points[i]
            next_m5 = points[i+1]
            
            # Setup Condition: 
            # 1. HTF is firmly in a Bullish Trend (Higher High)
            # 2. M5 just formed a Higher Low (The Retest/Pullback execution entry)
            # 3. Previous M5 was a Higher High (confirming M5 is aligned with HTF)
            if curr_m5[f'HTF_Struct_{htf}'] == 'HH':
                if prev_m5['Struct'] == 'HH' and curr_m5['Struct'] == 'HL':
                    total_setups += 1
                    
                    # Win Condition:
                    # The VERY NEXT structural point on M5 is a new Higher High that breaks above the previous HH
                    # (This is the 'Continuation' phase)
                    if next_m5['Struct'] == 'HH' and next_m5['PH'] > prev_m5['PH']:
                        winning_setups += 1
                        
        if total_setups > 0:
            win_rate = (winning_setups / total_setups) * 100
            print(f"-> Setups Found: {total_setups}")
            print(f"-> Successful Continuations (Wins): {winning_setups}")
            print(f"-> Win Rate: {win_rate:.2f}%")
        else:
            print("-> No valid setups found.")

if __name__ == '__main__':
    run_rubiks_cube()
