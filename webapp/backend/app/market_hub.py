import asyncio
import pandas as pd
from collections import defaultdict
from app.mt5_worker import mt5_worker

TF_MAP = {
    'M1': 1,      # mt5.TIMEFRAME_M1
    'M5': 5,
    'M15': 15,
    'M30': 30,
    'H1': 16385,  # mt5.TIMEFRAME_H1
    'H4': 16388,
    '1D': 16408
}

ALL_WELTRADE_SYMBOLS = [
    # FX Volatility Series
    'FX_Vol_20', 'FX_Vol_40', 'FX_Vol_60', 'FX_Vol_80', 'FX_Vol_99',
    # SFX Step-Vol Series
    'SFX_Vol_20', 'SFX_Vol_40', 'SFX_Vol_60', 'SFX_Vol_80', 'SFX_Vol_99',
    # GainX Series
    'GainX_400', 'GainX_600', 'GainX_800', 'GainX_999', 'GainX_1200',
    'MAX_GainX_1000', 'MAX_GainX_2000',
    # PainX Series
    'PainX_400', 'PainX_600', 'PainX_800', 'PainX_999', 'PainX_1200',
    'MAX_PainX_1000', 'MAX_PainX_2000',
    # FlipX Series
    'FlipX_1', 'FlipX_2', 'FlipX_3', 'FlipX_4', 'FlipX_5',
    # BreakX Series
    'BreakX_600', 'BreakX_1200', 'BreakX_1800',
    # SwitchX Series
    'SwitchX_600', 'SwitchX_1200', 'SwitchX_1800',
    # TrendX Series
    'TrendX_600', 'TrendX_1200', 'TrendX_1800',
    # Other Synthetics
    'FiboX', 'PlusX_1', 'QuadX'
]

WATCHLIST_SYMBOLS = list(ALL_WELTRADE_SYMBOLS)

class MarketHub:
    def __init__(self):
        self.subscriptions = defaultdict(set)
        self.all_clients = set()
        self.polling_tasks = {}
        self.watchlist_task = None
        self.d1_opens = {}
        self.last_d1_fetch = 0
        self.latest_candle_cache = {}
        self.latest_watchlist_payload = None

    def register_client(self, ws):
        self.all_clients.add(ws)
        if self.latest_watchlist_payload:
            try:
                asyncio.create_task(ws.send_json(self.latest_watchlist_payload))
            except Exception:
                pass
        if not self.watchlist_task or self.watchlist_task.done():
            self.watchlist_task = asyncio.create_task(self._poll_watchlist())

    def unregister_client(self, ws):
        self.all_clients.discard(ws)
        self.unsubscribe_all(ws)

    def subscribe(self, ws, symbol: str, timeframe: str):
        self.all_clients.add(ws)
        sub_key = (symbol, timeframe)
        self.subscriptions[sub_key].add(ws)
        
        # Fast Immediate Push: send latest cached candle in 0ms without waiting for loop sleep
        if sub_key in self.latest_candle_cache:
            try:
                asyncio.create_task(ws.send_json(self.latest_candle_cache[sub_key]))
            except Exception:
                pass

        # Ensure MT5 has the symbol in MarketWatch
        asyncio.create_task(mt5_worker.execute_async('symbol_select', symbol.replace('_', ' '), True))

        if sub_key not in self.polling_tasks or self.polling_tasks[sub_key].done():
            self.polling_tasks[sub_key] = asyncio.create_task(self._poll_market(symbol, timeframe))

        if not self.watchlist_task or self.watchlist_task.done():
            self.watchlist_task = asyncio.create_task(self._poll_watchlist())

    def unsubscribe(self, ws, symbol: str, timeframe: str):
        sub_key = (symbol, timeframe)
        if sub_key in self.subscriptions and ws in self.subscriptions[sub_key]:
            self.subscriptions[sub_key].remove(ws)
            if not self.subscriptions[sub_key]:
                del self.subscriptions[sub_key]
                if sub_key in self.polling_tasks:
                    self.polling_tasks[sub_key].cancel()
                    del self.polling_tasks[sub_key]

    def unsubscribe_all(self, ws):
        to_remove = [k for k, clients in self.subscriptions.items() if ws in clients]
        for sub_key in to_remove:
            self.unsubscribe(ws, sub_key[0], sub_key[1])

    async def broadcast_all(self, payload: dict):
        dead_sockets = set()
        for ws in list(self.all_clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.add(ws)
        for dead in dead_sockets:
            self.unregister_client(dead)

    async def broadcast_symbol(self, symbol: str, payload: dict):
        dead_sockets = set()
        for (sub_sym, sub_tf), clients in list(self.subscriptions.items()):
            if sub_sym == symbol:
                for ws in list(clients):
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead_sockets.add(ws)
        for dead in dead_sockets:
            self.unregister_client(dead)

    async def _poll_market(self, symbol: str, timeframe: str):
        mt5_tf = TF_MAP.get(timeframe, 15)
        raw_sym = symbol.replace('_', ' ')
        iteration = 0
        
        while True:
            try:
                # 1. High-frequency tick poll for current live candle (pos 0, count 1)
                rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, mt5_tf, 0, 1)
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
                    df['time'] = df['time'].astype(int)
                    
                    candle_data = df.iloc[-1].to_dict()
                    
                    payload = {
                        "type": "candle",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "time": candle_data["time"],
                        "open": candle_data["open"],
                        "high": candle_data["high"],
                        "low": candle_data["low"],
                        "close": candle_data["close"],
                        "volume": candle_data["volume"],
                        "candle": candle_data
                    }
                    
                    sub_key = (symbol, timeframe)
                    self.latest_candle_cache[sub_key] = payload

                    if sub_key in self.subscriptions:
                        dead_sockets = set()
                        for ws in list(self.subscriptions[sub_key]):
                            try:
                                await ws.send_json(payload)
                            except Exception:
                                dead_sockets.add(ws)
                        
                        for dead in dead_sockets:
                            self.unregister_client(dead)

                # 2. Continuous MT5 Candle Accuracy Verification (Every ~5s / 15 iterations)
                iteration += 1
                if iteration % 15 == 0:
                    # Fetch the last 8 bars directly from MT5 truth without pandas overhead
                    verified_rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, mt5_tf, 0, 8)
                    if verified_rates is not None and len(verified_rates) > 0:
                        verified_bars = [{
                            "time": int(r['time']),
                            "open": float(r['open']),
                            "high": float(r['high']),
                            "low": float(r['low']),
                            "close": float(r['close']),
                            "volume": float(r['tick_volume'])
                        } for r in verified_rates]
                        
                        v_payload = {
                            "type": "candles_verify",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "count": len(verified_bars),
                            "bars": verified_bars
                        }
                        
                        sub_key = (symbol, timeframe)
                        if sub_key in self.subscriptions:
                            dead_sockets = set()
                            for ws in list(self.subscriptions[sub_key]):
                                try:
                                    await ws.send_json(v_payload)
                                except Exception:
                                    dead_sockets.add(ws)
                            for dead in dead_sockets:
                                self.unregister_client(dead)
                            
                await asyncio.sleep(0.35)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"MarketHub Poll Error for {symbol} {timeframe}: {e}")
                await asyncio.sleep(1.0)

    async def _poll_watchlist(self):
        selected_symbols = set()
        while self.all_clients:
            try:
                now = asyncio.get_event_loop().time()
                # Ensure all symbols are selected in MT5 Market Watch (only once)
                if len(selected_symbols) < len(WATCHLIST_SYMBOLS):
                    for sym in WATCHLIST_SYMBOLS:
                        raw_sym = sym.replace('_', ' ')
                        if raw_sym not in selected_symbols:
                            await mt5_worker.execute_async('symbol_select', raw_sym, True)
                            selected_symbols.add(raw_sym)

                # Refresh D1 open prices every 60s
                if now - self.last_d1_fetch > 60:
                    for sym in WATCHLIST_SYMBOLS:
                        raw_sym = sym.replace('_', ' ')
                        rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, TF_MAP['1D'], 0, 1)
                        if rates is not None and len(rates) > 0:
                            self.d1_opens[sym] = float(rates[0]['open'])
                    self.last_d1_fetch = now

                # Gather ticks for all symbols calmly with low CPU
                items = []
                for sym in WATCHLIST_SYMBOLS:
                    raw_sym = sym.replace('_', ' ')
                    tick = await mt5_worker.execute_async('symbol_info_tick', raw_sym)
                    if tick:
                        price = float(tick.bid) if tick.bid else float(tick.last)
                        d1_open = self.d1_opens.get(sym, price)
                        change_pct = ((price - d1_open) / d1_open * 100.0) if d1_open else 0.0
                        items.append({
                            "symbol": sym,
                            "bid": float(tick.bid),
                            "ask": float(tick.ask),
                            "price": price,
                            "change_pct": round(change_pct, 2)
                        })

                if items and self.all_clients:
                    payload = {"type": "watchlist", "data": items}
                    self.latest_watchlist_payload = payload
                    dead = set()
                    for ws in list(self.all_clients):
                        try:
                            await ws.send_json(payload)
                        except Exception:
                            dead.add(ws)
                    for d in dead:
                        self.unregister_client(d)

                await asyncio.sleep(1.2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"MarketHub Watchlist Error: {e}")
                await asyncio.sleep(1)

market_hub = MarketHub()
