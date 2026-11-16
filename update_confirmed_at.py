import pandas as pd
import os

def add_confirmation_times(data_dir="data"):
    symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
    timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', '1D']
    
    print("Updating Parquets with confirmed_at timestamps to prevent look-ahead bias...")
    
    for symbol in symbols:
        for tf in timeframes:
            file_path = os.path.join(data_dir, f"{symbol}_{tf}_structure.parquet")
            if not os.path.exists(file_path):
                continue
                
            print(f"Processing {symbol} [{tf}]...")
            df = pd.read_parquet(file_path)
            
            # The structure was calculated using a rolling window.
            # Micro (n=2) means the peak is confirmed 2 candles later.
            # Macro (n=5) means the peak is confirmed 5 candles later.
            
            # To get the confirmation time, we just shift the 'time' column backwards by N
            # So row i gets the time of row i+N
            df['confirmed_at_micro'] = df['time'].shift(-2)
            df['confirmed_at_macro'] = df['time'].shift(-5)
            
            # If a row is NOT a peak, it doesn't need a confirmation time
            df.loc[df['struct_micro'].isna(), 'confirmed_at_micro'] = pd.NaT
            df.loc[df['struct_macro'].isna(), 'confirmed_at_macro'] = pd.NaT
            
            df.to_parquet(file_path, index=False)
            
    print("\nSuccessfully added confirmed_at columns to all structure parquets!")

if __name__ == "__main__":
    add_confirmation_times()
