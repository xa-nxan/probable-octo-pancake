import pandas as pd
import numpy as np
import os

def align_timeframes(ltf_df, htf_df, htf_name):
    ltf_df = ltf_df.sort_values('time')
    htf_df = htf_df.sort_values('time')
    
    htf_renamed = htf_df[['time', 'Struct', 'PH', 'PL', 'high', 'low', 'close', 'Prev_PH', 'Prev_PL']].rename(columns={
        'Struct': f'HTF_Struct',
        'PH': f'HTF_PH',
        'PL': f'HTF_PL',
        'high': f'HTF_high',
        'low': f'HTF_low',
        'close': f'HTF_close',
        'Prev_PH': f'HTF_Prev_PH',
        'Prev_PL': f'HTF_Prev_PL'
    })
    
    htf_renamed = htf_renamed.ffill()
    merged = pd.merge_asof(ltf_df, htf_renamed, on='time', direction='backward')
    return merged

def run_full_matrix_winrate():
    print("=========================================================")
    print("  THE RUBIK'S CUBE: FULL MATRIX WINRATE (10 MONTHS)  ")
    print("=========================================================\n")
    
    symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
    
    cube_rotations = [
        ('H4', 'H1'),    
        ('H1', 'M15'),   
        ('M30', 'M5')    
    ]
    
    for symbol in symbols:
        print(f"\n>>> Analyzing Symbol: {symbol} <<<")
        
        for htf, ltf in cube_rotations:
            htf_file = f'data/classified_{symbol}_{htf}.parquet'
            ltf_file = f'data/classified_{symbol}_{ltf}.parquet'
            
            if not os.path.exists(htf_file) or not os.path.exists(ltf_file):
                continue
                
            htf_df = pd.read_parquet(htf_file)
            ltf_df = pd.read_parquet(ltf_file)
            
            htf_df['Prev_PH'] = htf_df['PH'].shift(1)
            htf_df['Prev_PL'] = htf_df['PL'].shift(1)
            
            cube_df = align_timeframes(ltf_df, htf_df, htf)
            
            struct_df = cube_df.dropna(subset=['Struct']).copy()
            struct_df.reset_index(inplace=True, drop=True)
            
            # Create columns for the NEXT LTF structure to verify wins
            struct_df['Next_Struct'] = struct_df['Struct'].shift(-1)
            
            # Setup 1: Resistance (Short). Win = Next point is LL (downtrend confirmed)
            res_mask = (struct_df['HTF_close'] >= struct_df['HTF_Prev_PH'] * 0.998) & \
                       (struct_df['HTF_close'] <= struct_df['HTF_Prev_PH'] * 1.002) & \
                       (struct_df['Struct'] == 'LH')
            res_trades = struct_df[res_mask]
            res_wins = len(res_trades[res_trades['Next_Struct'] == 'LL'])
            res_total = len(res_trades)
            
            # Setup 2: Breakout (Long). Win = Next point is HH (continuation)
            bo_mask = (struct_df['HTF_Struct'] == 'HH') & (struct_df['HTF_close'] > struct_df['HTF_Prev_PH']) & \
                      (struct_df['Struct'] == 'HH')
            bo_trades = struct_df[bo_mask]
            bo_wins = len(bo_trades[bo_trades['Next_Struct'] == 'HH'])
            bo_total = len(bo_trades)
            
            # Setup 3: Pullback (Short). Win = Next point is LL (price drops to the magnet)
            pb_mask = (struct_df['HTF_Struct'] == 'HH') & (struct_df['HTF_close'] > struct_df['HTF_Prev_PH']) & \
                      (struct_df['Struct'] == 'LL')
            pb_trades = struct_df[pb_mask]
            pb_wins = len(pb_trades[(pb_trades['Next_Struct'] == 'LH') | (pb_trades['Next_Struct'] == 'LL')])
            pb_total = len(pb_trades)
            
            # Setup 4: Continuation (Long). Win = Next point is HH
            cont_mask = (struct_df['HTF_Struct'] == 'HL') & (struct_df['Struct'] == 'HH')
            cont_trades = struct_df[cont_mask]
            cont_wins = len(cont_trades[cont_trades['Next_Struct'] == 'HH'])
            cont_total = len(cont_trades)
            
            total_trades = res_total + bo_total + pb_total + cont_total
            total_wins = res_wins + bo_wins + pb_wins + cont_wins
            
            print(f"  Rotation: {htf} Context -> {ltf} Execution")
            if total_trades > 0:
                overall_wr = (total_wins / total_trades) * 100
                print(f"    - Overall Rotation Win Rate: {overall_wr:.2f}% ({total_wins}/{total_trades})")
                
                if res_total > 0:
                    print(f"      * Resistance Bounces: {(res_wins/res_total)*100:.1f}% ({res_wins}/{res_total})")
                if bo_total > 0:
                    print(f"      * Breakouts         : {(bo_wins/bo_total)*100:.1f}% ({bo_wins}/{bo_total})")
                if pb_total > 0:
                    print(f"      * Pullbacks (Magnet): {(pb_wins/pb_total)*100:.1f}% ({pb_wins}/{pb_total})")
                if cont_total > 0:
                    print(f"      * Continuations     : {(cont_wins/cont_total)*100:.1f}% ({cont_wins}/{cont_total})")
            else:
                print("    - No pure setups found.")

if __name__ == '__main__':
    run_full_matrix_winrate()
