import pandas as pd
import numpy as np
import os

def calc_pivots(df, length=5):
    ph_mask = pd.Series(True, index=df.index)
    pl_mask = pd.Series(True, index=df.index)
    
    for i in range(1, length + 1):
        ph_mask = ph_mask & (df['high'] > df['high'].shift(i)) & (df['high'] > df['high'].shift(-i))
        pl_mask = pl_mask & (df['low'] < df['low'].shift(i)) & (df['low'] < df['low'].shift(-i))
        
    df['PH'] = np.where(ph_mask, df['high'], np.nan)
    df['PL'] = np.where(pl_mask, df['low'], np.nan)
    return df

def map_structure(df):
    points = []
    for idx, row in df.iterrows():
        if pd.notna(row['PH']):
            points.append({'index': idx, 'type': 'PH', 'price': row['PH']})
        if pd.notna(row['PL']):
            points.append({'index': idx, 'type': 'PL', 'price': row['PL']})
            
    last_ph = None
    last_pl = None
    
    df['Struct'] = None
    
    for p in points:
        idx = p['index']
        if p['type'] == 'PH':
            if last_ph is None:
                df.at[idx, 'Struct'] = 'Initial High'
            elif p['price'] > last_ph:
                df.at[idx, 'Struct'] = 'HH'
            else:
                df.at[idx, 'Struct'] = 'LH'
            last_ph = p['price']
            
        elif p['type'] == 'PL':
            if last_pl is None:
                df.at[idx, 'Struct'] = 'Initial Low'
            elif p['price'] > last_pl:
                df.at[idx, 'Struct'] = 'HL'
            else:
                df.at[idx, 'Struct'] = 'LL'
            last_pl = p['price']
            
    return df

def batch_classify():
    data_dir = "data"
    symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
    timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', '1D']
    
    print("Starting Batch Classification (Pivots + HH/HL/LH/LL)")
    
    for symbol in symbols:
        for tf in timeframes:
            in_file = os.path.join(data_dir, f"{symbol}_{tf}.parquet")
            out_file = os.path.join(data_dir, f"classified_{symbol}_{tf}.parquet")
            
            if not os.path.exists(in_file):
                continue
                
            print(f"Processing {symbol} {tf}...")
            df = pd.read_parquet(in_file)
            
            # Ensure time is sorted and no duplicates just in case
            if 'time' in df.columns:
                df = df.sort_values('time').reset_index(drop=True)
                
            # 1. Calc Pivots
            df = calc_pivots(df, length=5)
            # 2. Map Structure
            df = map_structure(df)
            
            # Save
            df.to_parquet(out_file, index=False)
            
    print("\nBatch classification complete! All HTF and LTF layers are now ready for the Rubik's cube.")

if __name__ == "__main__":
    batch_classify()
