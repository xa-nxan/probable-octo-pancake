import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# Connect to MT5
if not mt5.initialize():
    print("MT5 initialize() failed, error code =", mt5.last_error())
    quit()

symbol = "FX Vol 40"
timeframe = mt5.TIMEFRAME_M15
num_candles = 5

print(f"==================================================")
print(f"   MT5 CANDLE ALIGNMENT CROSS-CHECK")
print(f"==================================================")
print(f"Symbol:    {symbol}")
print(f"Timeframe: M15")
print(f"Fetching last {num_candles} closed/live candles...\n")

rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)

if rates is None or len(rates) == 0:
    print(f"Failed to fetch data for {symbol}. Error:", mt5.last_error())
else:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    for i, row in df.iterrows():
        status = " (LIVE FORMING)" if i == len(df)-1 else ""
        print(f"Time:  {row['time']}{status}")
        print(f"Open:  {row['open']:.2f}")
        print(f"High:  {row['high']:.2f}")
        print(f"Low:   {row['low']:.2f}")
        print(f"Close: {row['close']:.2f}")
        print(f"Vol:   {row['tick_volume']}")
        print("-" * 40)
        
print("\nCross-check complete. Compare these exact prices and timestamps with your MT5 Terminal.")
mt5.shutdown()
