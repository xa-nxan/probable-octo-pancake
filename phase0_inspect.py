import pandas as pd
import os
import glob

def inspect_data(data_dir="data"):
    print("--- Phase 0: Data Inspection ---")
    
    parquet_files = glob.glob(os.path.join(data_dir, "*.parquet"))
    
    if not parquet_files:
        print("No parquet files found.")
        return
        
    for file in parquet_files[:5]: # Inspect a sample of files (e.g. first 5)
        print(f"\nInspecting: {os.path.basename(file)}")
        df = pd.read_parquet(file)
        
        print(f"Row count: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        
        if 'time' in df.columns:
            print(f"Time range: {df['time'].min()} to {df['time'].max()}")
            print(f"Timezone: {df['time'].dt.tz}")
            
            # Check for duplicates
            dups = df.duplicated(subset=['time']).sum()
            print(f"Duplicate timestamps: {dups}")
            
            # Check for gaps (basic check on M1 for instance)
            if 'M1.' in file or 'M1_' in file:
                # Expected diff is 1 minute
                diffs = df['time'].diff()
                gaps = (diffs > pd.Timedelta(minutes=1)).sum()
                print(f"Gaps (>1min): {gaps}")
        
        print(f"Missing values:\n{df.isnull().sum()}")

if __name__ == "__main__":
    inspect_data()
