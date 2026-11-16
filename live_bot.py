import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
from datetime import datetime

# --- Configuration ---
SYMBOL = "FX_Vol_20"
HTF = mt5.TIMEFRAME_H1
LTF = mt5.TIMEFRAME_M5
PIVOT_LENGTH = 5
CANDLES_TO_FETCH = 200 # Enough to establish recent structure

# --- Core Math Functions ---
def calc_pivots(df, length=5):
    ph_mask = pd.Series(True, index=df.index)
    pl_mask = pd.Series(True, index=df.index)
    for i in range(1, length + 1):
        ph_mask &= (df['high'] > df['high'].shift(i)) & (df['high'] > df['high'].shift(-i))
        pl_mask &= (df['low'] < df['low'].shift(i)) & (df['low'] < df['low'].shift(-i))
    df['PH'] = np.where(ph_mask, df['high'], np.nan)
    df['PL'] = np.where(pl_mask, df['low'], np.nan)
    return df

def map_structure(df):
    points = []
    for idx, row in df.iterrows():
        if pd.notna(row['PH']): points.append({'index': idx, 'type': 'PH', 'price': row['PH']})
        if pd.notna(row['PL']): points.append({'index': idx, 'type': 'PL', 'price': row['PL']})
            
    last_ph, last_pl = None, None
    df['Struct'] = None
    
    for p in points:
        idx = p['index']
        if p['type'] == 'PH':
            df.at[idx, 'Struct'] = 'HH' if (last_ph and p['price'] > last_ph) else 'LH'
            last_ph = p['price']
        elif p['type'] == 'PL':
            df.at[idx, 'Struct'] = 'HL' if (last_pl and p['price'] > last_pl) else 'LL'
            last_pl = p['price']
    
    # Forward fill the last known structural point for live scanning
    df['Last_Struct'] = df['Struct'].ffill()
    df['Last_PH'] = df['PH'].ffill()
    df['Last_PL'] = df['PL'].ffill()
    return df

def get_data(symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = calc_pivots(df, PIVOT_LENGTH)
    df = map_structure(df)
    return df

# --- The Rubik's Cube Engine ---
def scan_live_market():
    if not mt5.initialize():
        print("Failed to connect to MetaTrader 5. Please ensure the terminal is open.")
        return

    print(f"\n--- RUBIK'S CUBE LIVE SCANNER [{datetime.now().strftime('%H:%M:%S')}] ---")
    print(f"Monitoring: {SYMBOL} | Context: H1 | Execution: M5")
    
    # 1. Fetch Live Data
    htf_df = get_data(SYMBOL, HTF, CANDLES_TO_FETCH)
    ltf_df = get_data(SYMBOL, LTF, CANDLES_TO_FETCH)
    
    if htf_df is None or ltf_df is None:
        print("Failed to pull live market data.")
        mt5.shutdown()
        return

    # 2. Get the current state (the most recent completed structural pivots)
    htf_current = htf_df.iloc[-1]
    ltf_current = ltf_df.iloc[-1]
    
    print(f"\n[LIVE HTF STATE (H1)]")
    print(f"Current Price: {htf_current['close']}")
    print(f"Last Structure: {htf_current['Last_Struct']}")
    print(f"Last Pivot High: {htf_current['Last_PH']}")
    print(f"Last Pivot Low: {htf_current['Last_PL']}")
    
    print(f"\n[LIVE LTF STATE (M5)]")
    print(f"Last Structure: {ltf_current['Last_Struct']}")
    
    print("\n[ALGORITHMIC DECISION]")
    
    # 3. The Trade Logic (Mesh of Probabilities)
    
    # Setup 1: Resistance Rejection
    if abs(htf_current['close'] - htf_current['Last_PH']) / htf_current['Last_PH'] < 0.002:
        print(">>> ALERT: HTF is at major Resistance.")
        if ltf_current['Last_Struct'] == 'LH':
            print(">>> EXECUTE: M5 has confirmed a Lower High. Fire SHORT order! (Setup 1)")
        else:
            print(">>> WAIT: Waiting for M5 to print a Lower High (LH) to short.")
            
    # Setup 2: The Magnet Pullback (Shorting into support)
    elif htf_current['Last_Struct'] == 'HH' and htf_current['close'] > htf_current['Last_PH'] * 1.002:
        print(">>> ALERT: H1 just broke out (HH), leaving a gap down to resistance.")
        if ltf_current['Last_Struct'] in ['LH', 'LL']:
            print(">>> EXECUTE: M5 is bearish. Fire SHORT order targeting H1 broken resistance! (Setup 2 - Magnet)")
        else:
            print(">>> WAIT: Waiting for M5 to turn bearish to short the pullback.")
            
    # Setup 4: Trend Continuation
    elif htf_current['Last_Struct'] == 'HL':
        print(">>> ALERT: HTF is in a massive Bullish Trend (just printed HL).")
        if ltf_current['Last_Struct'] == 'HH':
            print(">>> EXECUTE: M5 just printed a Higher High. Fire LONG order! (Setup 4)")
        else:
            print(">>> WAIT: Waiting for M5 to print a Breakout (HH) to join the trend.")
            
    else:
        print(">>> NEUTRAL: No immediate Rubik's Cube alignment. Waiting for market to develop structure.")

    mt5.shutdown()

if __name__ == "__main__":
    scan_live_market()
