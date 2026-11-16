import pandas as pd
import os
from lightweight_charts import Chart

def get_data(symbol, tf):
    file_path = f"data/{symbol}_{tf}_structure.parquet"
    if not os.path.exists(file_path):
        return pd.DataFrame()
    
    df = pd.read_parquet(file_path)
    
    # lightweight-charts expects lowercase columns: time, open, high, low, close, volume
    # Our parquet already has time, open, high, low, close, tick_volume
    df = df.rename(columns={'tick_volume': 'volume'})
    
    # For performance, let's load just the last 1000 candles for visualization
    df = df.tail(1000).reset_index(drop=True)
    return df

def set_markers(chart, df):
    # Filter the dataframe for where structural points exist
    # We will use Macro structure (N=5) to avoid clutter
    struct_df = df.dropna(subset=['struct_macro'])
    
    for _, row in struct_df.iterrows():
        stype = row['struct_macro']
        if stype in ['HH', 'LH']:
            chart.marker(
                time=row['time'],
                position='above',
                shape='arrow_down',
                color='red' if stype == 'LH' else 'blue',
                text=stype
            )
        elif stype in ['HL', 'LL']:
            chart.marker(
                time=row['time'],
                position='below',
                shape='arrow_up',
                color='blue' if stype == 'HL' else 'red',
                text=stype
            )

if __name__ == '__main__':
    chart = Chart(toolbox=True)
    chart.legend(visible=True)
    
    current_symbol = 'FX_Vol_20'
    current_tf = 'M15'
    
    df = get_data(current_symbol, current_tf)
    chart.set(df)
    set_markers(chart, df)
    
    chart.watermark(f'{current_symbol} | {current_tf} | Macro Structure')
    
    # The block() command starts the local web server and opens the chart in the browser
    print("Opening TradingView-like chart in your browser...")
    chart.show(block=True)
