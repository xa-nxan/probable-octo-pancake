import pandas as pd
import os
import time
from lightweight_charts import Chart

class MiniTradingView:
    def __init__(self, data_dir="data", default_bars=5000):
        self.data_dir = data_dir
        self.default_bars = default_bars
        self.current_symbol = 'FX_Vol_20'
        self.current_tf = 'M15'
        
        self.zone_mode = None
        self.zone_start = None
        self.custom_boxes_data = [] 
        self.drawn_box_objects = [] # Store drawing objects so we can delete them
        
        # Cache dictionaries
        self.cache_df = {}
        self.cache_markers = {}
        
        self.chart = Chart(toolbox=True)
        self.chart.layout(background_color='#131722', text_color='#d1d4dc')
        self.chart.legend(visible=True)
        self.chart.crosshair(mode='normal', vert_color='#9598a1', horz_color='#9598a1')
        self.chart.grid(vert_enabled=False, horz_enabled=False)
        self.chart.volume_config(scale_margin_top=0.85, scale_margin_bottom=0.0)
        self.show_volume = True

        self.setup_topbar()
        self.chart.events.click += self.on_chart_click
        self.load_chart()

    def setup_topbar(self):
        symbols = ['FX_Vol_20', 'FX_Vol_40', 'FlipX_1', 'FlipX_2']
        timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', '1D']
        
        self.chart.topbar.switcher('symbol_switcher', options=tuple(symbols), default=self.current_symbol, func=self.on_symbol_change)
        self.chart.toolbox.save_drawings_under(self.chart.topbar['symbol_switcher'])

        self.chart.topbar.switcher('tf_switcher', options=tuple(timeframes), default=self.current_tf, func=self.on_tf_change)
        self.chart.topbar.button('vol_toggle', button_text='Toggle Volume', func=self.on_volume_toggle)
        self.chart.topbar.button('long_tool', 'Long Tool', func=self.enable_long_tool)
        self.chart.topbar.button('short_tool', 'Short Tool', func=self.enable_short_tool)

        if os.path.exists('drawings.json'):
            try: self.chart.toolbox.import_drawings('drawings.json')
            except: pass

    def enable_long_tool(self, chart):
        self.zone_mode = 'Long'
        self.zone_clicks = []
        print("Long Tool: Click Entry, then Stop Loss, then Target.")

    def enable_short_tool(self, chart):
        self.zone_mode = 'Short'
        self.zone_clicks = []
        print("Short Tool: Click Entry, then Stop Loss, then Target.")

    def on_chart_click(self, chart, time, price):
        if not self.zone_mode: return
        
        self.zone_clicks.append((time, price))
        
        if len(self.zone_clicks) == 1:
            print(f"Entry set at {price:.2f}. Now click Stop Loss.")
        elif len(self.zone_clicks) == 2:
            print(f"Stop Loss set at {price:.2f}. Now click Target.")
        elif len(self.zone_clicks) == 3:
            entry_time, entry_px = self.zone_clicks[0]
            _, sl_px = self.zone_clicks[1]
            end_time, tp_px = self.zone_clicks[2]
            
            # Validate ordering
            if self.zone_mode == 'Long' and not (tp_px > entry_px > sl_px):
                print("Invalid Long! Must be Target > Entry > Stop. Try again.")
                self.zone_clicks = []
                return
            elif self.zone_mode == 'Short' and not (sl_px > entry_px > tp_px):
                print("Invalid Short! Must be Stop > Entry > Target. Try again.")
                self.zone_clicks = []
                return
                
            self.create_trade_position(entry_time, end_time, entry_px, sl_px, tp_px, self.zone_mode)
            self.zone_mode = None
            self.zone_clicks = []

    def create_trade_position(self, start_time, end_time, entry_px, sl_px, tp_px, direction):
        trade = {
            'direction': direction,
            'start_time': start_time,
            'end_time': end_time,
            'entry': entry_px,
            'sl': sl_px,
            'tp': tp_px,
            'boxes': []
        }
        self.custom_boxes_data.append(trade)
        self.render_trade_visuals(trade)

    def render_trade_visuals(self, trade):
        for b in trade['boxes']:
            if hasattr(b, 'delete'): b.delete()
        trade['boxes'].clear()
        
        entry, sl, tp = trade['entry'], trade['sl'], trade['tp']
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > 0 else 0
        qty = 1000
        
        fill_green = 'rgba(8, 153, 129, 0.2)'  # TV green
        fill_red = 'rgba(242, 54, 69, 0.2)'    # TV red
        border_green = 'rgba(8, 153, 129, 0.8)'
        border_red = 'rgba(242, 54, 69, 0.8)'
        
        tp_text = f"Target: {reward:.2f} | Amount: {reward*qty:.2f}"
        sl_text = f"Stop: {risk:.2f} | Amount: {risk*qty:.2f}"
        mid_text = f"Risk/reward ratio: {rr:.2f}"

        # Target Box
        b1 = self.chart.box(
            trade['start_time'], entry, trade['end_time'], tp,
            color=border_green, fill_color=fill_green,
            text=tp_text, text_position='top', text_placement='outside', text_color='#fff'
        )
        
        # Stop Box
        b2 = self.chart.box(
            trade['start_time'], entry, trade['end_time'], sl,
            color=border_red, fill_color=fill_red,
            text=sl_text, text_position='bottom', text_placement='outside', text_color='#fff'
        )
        
        # Middle line box (fake pill badge for RR)
        b3 = self.chart.box(
            trade['start_time'], entry, trade['end_time'], entry,
            color='#131722', fill_color='#131722',
            text=mid_text, text_position='center', text_placement='inside', text_color='#fff'
        )
        
        trade['boxes'].extend([b1, b2, b3])

    def draw_custom_box(self, box_data):
        # We intercept this to handle the legacy loading, but now box_data is a trade dict
        if 'direction' in box_data:
            self.render_trade_visuals(box_data)

    def save_drawings(self, chart):
        pass # self.chart.toolbox.export_drawings('drawings.json')

    def on_symbol_change(self, chart):
        self.current_symbol = chart.topbar['symbol_switcher'].value
        self.load_chart()

    def on_tf_change(self, chart):
        self.current_tf = chart.topbar['tf_switcher'].value
        self.load_chart()

    def on_volume_toggle(self, chart):
        self.show_volume = not self.show_volume
        self.load_chart()

    def load_data(self):
        cache_key = f"{self.current_symbol}_{self.current_tf}"
        if cache_key in self.cache_df:
            df = self.cache_df[cache_key].copy()
        else:
            file_path = os.path.join(self.data_dir, f"{self.current_symbol}_{self.current_tf}_structure.parquet")
            if not os.path.exists(file_path): return pd.DataFrame()
            
            # Optimization: Read only needed rows if possible (pyarrow dataset) or just load and tail
            # Since pandas read_parquet loads the whole file, we can optimize later with pyarrow
            df = pd.read_parquet(file_path)
            df = df.rename(columns={'tick_volume': 'volume'})
            
            bars_to_load = self.default_bars
            if self.current_tf in ['M1', 'M5']: bars_to_load = min(self.default_bars, 2000)
            
            df = df.tail(bars_to_load).reset_index(drop=True)
            self.cache_df[cache_key] = df.copy()

        if not self.show_volume:
            df['volume'] = 0
        return df

    def get_cached_markers(self, df):
        cache_key = f"{self.current_symbol}_{self.current_tf}"
        if cache_key in self.cache_markers:
            return self.cache_markers[cache_key]
            
        # Vectorized marker building
        struct_df = df.dropna(subset=['struct_macro']).copy()
        markers = []
        for row in struct_df.itertuples():
            stype = getattr(row, 'struct_macro')
            time_val = getattr(row, 'time')
            if stype in ['HH', 'LH']:
                markers.append(self.chart.marker(time=time_val, position='above', shape='arrow_down', color='red' if stype == 'LH' else 'blue', text=stype))
            elif stype in ['HL', 'LL']:
                markers.append(self.chart.marker(time=time_val, position='below', shape='arrow_up', color='blue' if stype == 'HL' else 'red', text=stype))
                
        self.cache_markers[cache_key] = markers
        return markers

    def load_chart(self):
        t0 = time.perf_counter()
        
        df = self.load_data()
        t_data = time.perf_counter()
        
        if df.empty: return
            
        self.chart.watermark(f"{self.current_symbol} | {self.current_tf} | Macro Structure", color='rgba(255, 255, 255, 0.1)')
        
        # Only pass the strict OHLCV columns to the chart renderer to avoid JSON serialization errors on custom structural datetimes
        render_df = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
        
        # set data, keep toolbox drawings natively
        self.chart.set(render_df, keep_drawings=True)
        t_set = time.perf_counter()
        
        # Apply markers
        markers = self.get_cached_markers(df)
        if hasattr(self.chart, 'marker_list'):
             # Vectorized marker list (only if API supports it, falling back if not)
             pass 
        # Note: the python-lightweight-charts API handles chart.marker_list(markers_list of dicts)
        # Let's rebuild the markers to use marker_list if possible.
        # Actually, let's keep the cache but use marker_list format
        # If cache contains dictionaries:
        if not markers:
            struct_df = df.dropna(subset=['struct_macro'])
            marker_dicts = []
            # We will use vectorization
            for row in struct_df.itertuples():
                stype = getattr(row, 'struct_macro')
                time_val = getattr(row, 'time')
                pos = 'above' if stype in ['HH', 'LH'] else 'below'
                shape = 'arrowDown' if stype in ['HH', 'LH'] else 'arrowUp'
                color = 'blue' if stype in ['HH', 'HL'] else 'red'
                marker_dicts.append({'time': time_val, 'position': pos, 'shape': shape, 'color': color, 'text': stype})
            
            if hasattr(self.chart, 'marker_list'):
                self.chart.marker_list(marker_dicts)
            else:
                self.chart.set_markers(marker_dicts) # fallback
                
        t_markers = time.perf_counter()
        
        # Clear old programmatic boxes
        for box_obj in self.drawn_box_objects:
            if hasattr(box_obj, 'delete'): box_obj.delete()
        self.drawn_box_objects.clear()
        
        for box in self.custom_boxes_data:
            self.draw_custom_box(box)
            
        t_drawings = time.perf_counter()
        
        print(f"Timing | Load Data: {(t_data-t0)*1000:.1f}ms | Chart Set: {(t_set-t_data)*1000:.1f}ms | Markers: {(t_markers-t_set)*1000:.1f}ms | Drawings: {(t_drawings-t_markers)*1000:.1f}ms")

    def run(self):
        self.chart.show(block=True)

if __name__ == "__main__":
    app = MiniTradingView()
    app.run()
