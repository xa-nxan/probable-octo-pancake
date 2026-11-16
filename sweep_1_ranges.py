import pandas as pd
import numpy as np
import os

def calculate_candle_ranges(data_dir="data"):
    symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
    timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', '1D']
    
    results = []

    print("Executing Sweep 1: Analyzing historical candle ranges...")

    for symbol in symbols:
        for tf in timeframes:
            file_path = os.path.join(data_dir, f"{symbol}_{tf}.parquet")
            
            if not os.path.exists(file_path):
                print(f"Warning: {file_path} not found.")
                continue
                
            df = pd.read_parquet(file_path)
            
            if df.empty:
                continue

            # Total Range (High - Low)
            df['total_range'] = df['high'] - df['low']
            # Body Range (abs(Open - Close))
            df['body_range'] = abs(df['open'] - df['close'])

            # Statistics
            mean_range = df['total_range'].mean()
            std_range = df['total_range'].std()
            var_range = df['total_range'].var()
            median_range = df['total_range'].median()
            p95_range = df['total_range'].quantile(0.95) # 95th percentile (exhaustion limit)

            mean_body = df['body_range'].mean()
            std_body = df['body_range'].std()

            results.append({
                'Symbol': symbol.replace('_', ' '),
                'Timeframe': tf,
                'Samples': len(df),
                'Mean_Total_Range': round(mean_range, 5),
                'Median_Total_Range': round(median_range, 5),
                'StdDev_Total_Range': round(std_range, 5),
                'Variance_Total_Range': round(var_range, 8),
                '95th_Percentile_Range': round(p95_range, 5), # Exhaustion marker
                'Mean_Body_Range': round(mean_body, 5),
                'StdDev_Body_Range': round(std_body, 5)
            })
            
    # Convert results to dataframe and save
    stats_df = pd.DataFrame(results)
    
    # Save to CSV
    output_csv = "candle_ranges_stats.csv"
    stats_df.to_csv(output_csv, index=False)
    
    print(f"\nSweep 1 complete! Statistics saved to {output_csv}")
    
    # Print a quick preview of the H1 and H4 stats which dictate market direction
    print("\n--- Preview: Higher Timeframe (H1 & H4) Range Exhaustion Limits ---")
    higher_tf = stats_df[stats_df['Timeframe'].isin(['H1', 'H4'])]
    for _, row in higher_tf.iterrows():
        print(f"[{row['Symbol']} - {row['Timeframe']}] Avg Range: {row['Mean_Total_Range']} | Exhaustion (95%): {row['95th_Percentile_Range']} | StdDev: {row['StdDev_Total_Range']}")

if __name__ == "__main__":
    calculate_candle_ranges()
