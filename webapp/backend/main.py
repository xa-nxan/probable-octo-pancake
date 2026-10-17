from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import asyncio
import datetime
import pandas as pd
import os
import MetaTrader5 as mt5

from app.mt5_worker import mt5_worker
from app.market_hub import market_hub
from app.weltrade_bridge import weltrade_bridge

class OrderRequest(BaseModel):
    symbol: str
    action: str  # 'Buy' or 'Sell'
    volume: float
    order_type: str = 'Market'  # 'Market', 'Stop', 'Limit', 'On Close', etc.
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    timeframe: str = 'M30'

class RiskCalcRequest(BaseModel):
    symbol: str
    action: str  # 'Buy' or 'Sell'
    volume: float = 0.01
    entry: float
    sl: float = 0.0
    tp: float = 0.0

class ModifyPositionRequest(BaseModel):
    ticket: int
    sl: float = 0.0
    tp: float = 0.0

class PartialCloseRequest(BaseModel):
    ticket: int
    volume: float = 0.0
    pct: float = 50.0  # default 50%

class BankReopenRequest(BaseModel):
    ticket: int
    lock_profit_pts: float = 0.0

class LockProfitRequest(BaseModel):
    ticket: int
    lock_type: str = "margin"  # "margin" (lock amount equal to margin) or "breakeven"

class ModifyOrderRequest(BaseModel):
    ticket: int
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0

class AccountLoginRequest(BaseModel):
    login: int
    password: str = ""
    server: str = "Weltrade-Real"

class WeltradeCredentialsRequest(BaseModel):
    email: str
    password: str = ""

class WeltradeTransferRequest(BaseModel):
    from_account: str
    amount: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    mt5_worker.start()
    await asyncio.sleep(1)
    yield
    await mt5_worker.execute_async("shutdown")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TF_MAP = {
    'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30,
    'H1': 16385, 'H4': 16388, '1D': 16408
}

# Structure parquet files live in <project root>/data (two levels up from this file).
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

ALLOWED_SYMBOLS = {
    'FX_Vol_20', 'FX_Vol_40', 'FX_Vol_60', 'FX_Vol_80', 'FX_Vol_99',
    'SFX_Vol_20', 'SFX_Vol_40', 'SFX_Vol_60', 'SFX_Vol_80', 'SFX_Vol_99',
    'FlipX_1', 'FlipX_2', 'FlipX_3', 'FlipX_4', 'FlipX_5',
}

# Trading is enabled by default for local MT5 operations; set LIVE_TRADING_ENABLED=false to disable.
LIVE_TRADING_ENABLED = os.environ.get("LIVE_TRADING_ENABLED", "true").lower() == "true"

def require_trading_enabled():
    if not LIVE_TRADING_ENABLED:
        raise HTTPException(status_code=403, detail="Trading is disabled (LIVE_TRADING_ENABLED is false).")

def mt5_error_detail(prefix: str, result) -> str:
    if result is None:
        code, msg = mt5_worker.get_last_error()
        return f"{prefix}: MT5 returned no result (error {code}: {msg})"
    return f"{prefix}: retcode {result.retcode} - {result.comment}"

@app.get("/account")
async def get_account():
    info = await mt5_worker.execute_async("account_info")
    if info is None:
        raise HTTPException(status_code=500, detail="Failed to get account info")
    
    term = await mt5_worker.execute_async("terminal_info")
    ping_ms = round(term.ping_last / 1000.0, 1) if term and hasattr(term, 'ping_last') else 0.0

    return {
        "login": info.login,
        "name": info.name,
        "server": info.server,
        "currency": info.currency,
        "leverage": info.leverage,
        "trade_allowed": info.trade_allowed,
        "balance": info.balance,
        "equity": info.equity,
        "margin": info.margin,
        "margin_free": info.margin_free,
        "profit": info.profit,
        "ping_ms": ping_ms,
        "terminal_connected": term.connected if term else False
    }

@app.post("/account/switch")
async def switch_account(req: AccountLoginRequest):
    kwargs = {"login": req.login}
    if req.password:
        kwargs["password"] = req.password
    if req.server:
        kwargs["server"] = req.server
        
    success = await mt5_worker.execute_async("login", **kwargs)
    if not success:
        code, msg = mt5_worker.get_last_error()
        raise HTTPException(status_code=400, detail=f"Failed to switch account to {req.login}: error {code} - {msg}")
        
    info = await mt5_worker.execute_async("account_info")
    return {
        "status": "switched",
        "login": info.login if info else req.login,
        "balance": info.balance if info else 0.0,
        "equity": info.equity if info else 0.0,
        "server": info.server if info else req.server
    }

@app.get("/positions")
async def get_positions():
    pos = await mt5_worker.execute_async("positions_get")
    if pos is None:
        return []
    
    result = []
    for p in pos:
        result.append({
            "ticket": p.ticket,
            "symbol": p.symbol,
            "type": "Buy" if p.type == mt5.ORDER_TYPE_BUY else "Sell",
            "volume": p.volume,
            "price_open": p.price_open,
            "price_current": p.price_current,
            "sl": p.sl,
            "tp": p.tp,
            "profit": p.profit,
            "time": p.time
        })
    return result

@app.get("/history")
async def get_history(days: int = 30):
    now = datetime.datetime.now()
    from_date = now - datetime.timedelta(days=days)
    to_date = now + datetime.timedelta(days=1)
    
    deals = await mt5_worker.execute_async("history_deals_get", from_date, to_date)
    if deals is None:
        return []

    result = []
    for d in sorted(deals, key=lambda x: x.time, reverse=True):
        if d.entry in (1, 2, 3) or d.profit != 0:
            result.append({
                "ticket": d.ticket,
                "order": d.order,
                "symbol": d.symbol,
                "type": "Buy" if d.type == mt5.DEAL_TYPE_BUY else "Sell",
                "volume": d.volume,
                "price": d.price,
                "profit": round(float(d.profit), 2),
                "commission": round(float(d.commission), 2),
                "swap": round(float(d.swap), 2),
                "fee": round(float(d.fee), 2),
                "time": int(d.time),
                "comment": d.comment or ""
            })
    return result

@app.post("/order/calc_risk")
async def calculate_order_risk(req: RiskCalcRequest):
    if req.symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} is not allowed")

    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not info or not tick:
        raise HTTPException(status_code=400, detail=f"Cannot get symbol info for {sym}")
        
    is_buy = req.action.lower() == 'buy'
    digits = info.digits
    volume = round(float(req.volume), 2)
    entry = round(float(req.entry), digits)
    sl = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp = round(float(req.tp), digits) if req.tp > 0 else 0.0

    action_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL

    sl_usd = 0.0
    if sl > 0:
        raw_sl_profit = await mt5_worker.execute_async("order_calc_profit", action_type, sym, volume, entry, sl)
        if raw_sl_profit is not None:
            sl_usd = round(float(raw_sl_profit), 2)
            
    tp_usd = 0.0
    if tp > 0:
        raw_tp_profit = await mt5_worker.execute_async("order_calc_profit", action_type, sym, volume, entry, tp)
        if raw_tp_profit is not None:
            tp_usd = round(float(raw_tp_profit), 2)

    margin = 0.0
    raw_margin = await mt5_worker.execute_async("order_calc_margin", action_type, sym, volume, entry)
    if raw_margin is not None:
        margin = round(float(raw_margin), 2)

    acc = await mt5_worker.execute_async("account_info")
    balance = acc.balance if acc else 0.0
    sl_pct = round((abs(sl_usd) / balance * 100.0), 1) if balance > 0 else 0.0
    tp_pct = round((tp_usd / balance * 100.0), 1) if balance > 0 else 0.0

    spread_pts = round(float(info.spread * info.trade_tick_size), digits)
    stops_level_pts = round(float(info.trade_stops_level * info.trade_tick_size), digits)

    return {
        "symbol": req.symbol,
        "volume": volume,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "sl_usd": sl_usd,
        "tp_usd": tp_usd,
        "sl_pct_balance": sl_pct,
        "tp_pct_balance": tp_pct,
        "margin": margin,
        "balance": balance,
        "spread_pts": spread_pts,
        "stops_level_pts": stops_level_pts,
        "digits": digits
    }

@app.get("/symbol_details")
async def get_symbol_details(symbol: str):
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is not allowed")

    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not info or not tick:
        raise HTTPException(status_code=400, detail=f"Cannot get details for {sym}")
        
    digits = info.digits
    spread_pts = round(float(info.spread * info.trade_tick_size), digits)
    stops_level_pts = round(float(info.trade_stops_level * info.trade_tick_size), digits)
    margin_001 = await mt5_worker.execute_async("order_calc_margin", mt5.ORDER_TYPE_BUY, sym, 0.01, tick.ask)

    return {
        "symbol": symbol,
        "digits": digits,
        "bid": round(float(tick.bid), digits),
        "ask": round(float(tick.ask), digits),
        "spread_pts": spread_pts,
        "stops_level_pts": stops_level_pts,
        "freeze_level_pts": round(float(info.trade_freeze_level * info.trade_tick_size), digits),
        "volume_min": info.volume_min,
        "volume_max": info.volume_max,
        "volume_step": info.volume_step,
        "margin_001": round(float(margin_001), 2) if margin_001 is not None else 0.0
    }

@app.post("/order/check")
async def check_order(req: OrderRequest):
    if req.symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} is not allowed")

    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not tick:
        raise HTTPException(status_code=400, detail=f"Cannot get tick for {sym}")
        
    is_buy = req.action.lower() == 'buy'
    digits = info.digits if info else 2
    volume = round(float(req.volume), 2)
    sl = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp = round(float(req.tp), digits) if req.tp > 0 else 0.0

    order_type_str = req.order_type.strip().lower()
    is_stop = 'stop' in order_type_str
    is_limit = 'limit' in order_type_str

    if is_stop:
        action = mt5.TRADE_ACTION_PENDING
        order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        price = round(float(req.price), digits) if req.price > 0 else (round(tick.ask, digits) if is_buy else round(tick.bid, digits))
        type_filling = mt5.ORDER_FILLING_RETURN
    elif is_limit:
        action = mt5.TRADE_ACTION_PENDING
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
        price = round(float(req.price), digits) if req.price > 0 else (round(tick.ask, digits) if is_buy else round(tick.bid, digits))
        type_filling = mt5.ORDER_FILLING_RETURN
    else:
        action = mt5.TRADE_ACTION_DEAL
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        raw_price = tick.ask if is_buy else tick.bid
        price = round(raw_price, digits)
        type_filling = mt5.ORDER_FILLING_FOK
        if info:
            if info.filling_mode & 1:
                type_filling = mt5.ORDER_FILLING_FOK
            elif info.filling_mode & 2:
                type_filling = mt5.ORDER_FILLING_IOC
            else:
                type_filling = mt5.ORDER_FILLING_RETURN

    request = {
        "action": action,
        "symbol": sym,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }
    
    result = await mt5_worker.execute_async("order_check", request)
    if result is None:
        code, msg = mt5_worker.get_last_error()
        return {"valid": False, "retcode": code, "comment": f"Check error: {msg}", "margin_required": 0.0, "margin_free_after": 0.0}
        
    return {
        "valid": result.retcode == 0,
        "retcode": result.retcode,
        "comment": result.comment,
        "margin_required": round(float(result.margin), 2),
        "margin_free_after": round(float(result.margin_free), 2),
        "equity_after": round(float(result.equity), 2),
        "balance": round(float(result.balance), 2),
        "margin_level": round(float(result.margin_level), 2) if result.margin_level else 0.0
    }

ARMED_CLOSE_ORDERS: dict[int, dict] = {}
_NEXT_ARMED_TICKET = 900001

async def _watch_armed_close_order(ticket: int):
    while ticket in ARMED_CLOSE_ORDERS:
        await asyncio.sleep(1.0)
        order = ARMED_CLOSE_ORDERS.get(ticket)
        if not order:
            break
        try:
            sym = order["symbol"]
            tf_code = order["tf_code"]
            digits = order["digits"]
            is_buy = order["is_buy"]

            tick = await mt5_worker.execute_async("symbol_info_tick", sym)
            if tick:
                order["price_current"] = round(float(tick.ask if is_buy else tick.bid), digits)

            rates = await mt5_worker.execute_async("copy_rates_from_pos", sym, tf_code, 0, 2)
            if rates is None or len(rates) < 2:
                continue

            cur_bar_time = int(rates[-1]["time"])
            if cur_bar_time <= order["armed_bar_time"]:
                continue

            # The candle we were waiting on (rates[-2]) has officially closed!
            closed_bar = rates[-2]
            c_close = float(closed_bar["close"])
            c_low = float(closed_bar["low"])
            c_high = float(closed_bar["high"])
            sl = float(order["sl"])
            tp = float(order["tp"])
            entry_lvl = float(order["price_open"])
            base_span = abs(entry_lvl - sl) if sl > 0 else 0.0

            if is_buy:
                held_sl = (sl <= 0) or (c_low > sl and c_close > sl)
                held_base = c_close >= (entry_lvl - 0.5 * base_span) if base_span > 0 else (c_close >= entry_lvl)
                valid_close = held_sl and held_base
            else:
                held_sl = (sl <= 0) or (c_high < sl and c_close < sl)
                held_base = c_close <= (entry_lvl + 0.5 * base_span) if base_span > 0 else (c_close <= entry_lvl)
                valid_close = held_sl and held_base

            ARMED_CLOSE_ORDERS.pop(ticket, None)
            if not valid_close:
                # Base broke or SL violated on the candle — auto-cancel to prevent a loss!
                break

            info = await mt5_worker.execute_async("symbol_info", sym)
            tick = await mt5_worker.execute_async("symbol_info_tick", sym)
            if not tick:
                break

            exec_price = round(float(tick.ask if is_buy else tick.bid), digits)
            type_filling = mt5.ORDER_FILLING_FOK
            if info:
                if info.filling_mode & 1:
                    type_filling = mt5.ORDER_FILLING_FOK
                elif info.filling_mode & 2:
                    type_filling = mt5.ORDER_FILLING_IOC
                else:
                    type_filling = mt5.ORDER_FILLING_RETURN

            req_dict = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym,
                "volume": float(order["volume"]),
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": exec_price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": f"AG {order['timeframe']} Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
            }
            await mt5_worker.execute_async("order_send", req_dict)
            break
        except Exception:
            await asyncio.sleep(1.0)

@app.post("/order")
async def place_order(req: OrderRequest):
    global _NEXT_ARMED_TICKET
    require_trading_enabled()
    if req.symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} is not allowed")

    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not tick:
        raise HTTPException(status_code=400, detail=f"Cannot get tick for {sym}")
        
    is_buy = req.action.lower() == 'buy'
    digits = info.digits if info else 2
    volume = round(float(req.volume), 2)
    sl = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp = round(float(req.tp), digits) if req.tp > 0 else 0.0

    order_type_str = req.order_type.strip().lower()
    is_close = 'close' in order_type_str
    is_stop = 'stop' in order_type_str
    is_limit = 'limit' in order_type_str

    if is_close:
        tf_str = req.timeframe if req.timeframe in TF_MAP else 'M30'
        tf_code = TF_MAP[tf_str]
        rates = await mt5_worker.execute_async("copy_rates_from_pos", sym, tf_code, 0, 2)
        armed_bar_time = int(rates[-1]['time']) if (rates is not None and len(rates) > 0) else int(datetime.datetime.now().timestamp())
        price = round(float(req.price), digits) if req.price > 0 else (round(tick.ask, digits) if is_buy else round(tick.bid, digits))
        ticket = _NEXT_ARMED_TICKET
        _NEXT_ARMED_TICKET += 1
        ARMED_CLOSE_ORDERS[ticket] = {
            "ticket": ticket,
            "symbol": sym,
            "raw_symbol": req.symbol,
            "timeframe": tf_str,
            "tf_code": tf_code,
            "is_buy": is_buy,
            "type": f"Buy On {tf_str} Close" if is_buy else f"Sell On {tf_str} Close",
            "volume": volume,
            "price_open": price,
            "price_current": round(float(tick.ask if is_buy else tick.bid), digits),
            "sl": sl,
            "tp": tp,
            "digits": digits,
            "armed_bar_time": armed_bar_time,
            "time_setup": int(datetime.datetime.now().timestamp()),
            "comment": f"Wait {tf_str} close (hold base)"
        }
        asyncio.create_task(_watch_armed_close_order(ticket))
        return {
            "ticket": ticket,
            "comment": f"Armed for {tf_str} candle close",
            "action": "ARMED_CLOSE",
            "type": f"Buy On {tf_str} Close" if is_buy else f"Sell On {tf_str} Close",
            "price": price
        }

    if is_stop:
        action = mt5.TRADE_ACTION_PENDING
        order_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        price = round(float(req.price), digits) if req.price > 0 else (round(tick.ask, digits) if is_buy else round(tick.bid, digits))
        type_filling = mt5.ORDER_FILLING_RETURN
        comment = "Antigravity BuyStop" if is_buy else "Antigravity SellStop"
    elif is_limit:
        action = mt5.TRADE_ACTION_PENDING
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
        price = round(float(req.price), digits) if req.price > 0 else (round(tick.ask, digits) if is_buy else round(tick.bid, digits))
        type_filling = mt5.ORDER_FILLING_RETURN
        comment = "Antigravity BuyLimit" if is_buy else "Antigravity SellLimit"
    else:
        # Instant Market Deal
        action = mt5.TRADE_ACTION_DEAL
        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        raw_price = tick.ask if is_buy else tick.bid
        price = round(raw_price, digits)
        comment = "Antigravity UI"

        # Dynamically select filling mode based on symbol capabilities
        type_filling = mt5.ORDER_FILLING_FOK
        if info:
            if info.filling_mode & 1:
                type_filling = mt5.ORDER_FILLING_FOK
            elif info.filling_mode & 2:
                type_filling = mt5.ORDER_FILLING_IOC
            else:
                type_filling = mt5.ORDER_FILLING_RETURN

    request = {
        "action": action,
        "symbol": sym,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 234000,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": type_filling,
    }
    
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Order failed", result))
        
    return {
        "ticket": result.order,
        "comment": result.comment,
        "action": "PENDING" if (is_stop or is_limit) else "DEAL",
        "type": "Buy Stop" if (is_stop and is_buy) else "Sell Stop" if (is_stop and not is_buy) else "Buy Limit" if (is_limit and is_buy) else "Sell Limit" if (is_limit and not is_buy) else ("Buy" if is_buy else "Sell"),
        "price": price
    }

@app.get("/orders")
async def get_pending_orders():
    orders = await mt5_worker.execute_async("orders_get")
    
    type_names = {
        mt5.ORDER_TYPE_BUY_LIMIT: "Buy Limit",
        mt5.ORDER_TYPE_SELL_LIMIT: "Sell Limit",
        mt5.ORDER_TYPE_BUY_STOP: "Buy Stop",
        mt5.ORDER_TYPE_SELL_STOP: "Sell Stop",
        mt5.ORDER_TYPE_BUY_STOP_LIMIT: "Buy Stop Limit",
        mt5.ORDER_TYPE_SELL_STOP_LIMIT: "Sell Stop Limit",
    }
    
    result = []
    if orders:
        for o in orders:
            result.append({
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": type_names.get(o.type, f"Order {o.type}"),
                "volume": o.volume_current,
                "price_open": o.price_open,
                "price_current": o.price_current,
                "sl": o.sl,
                "tp": o.tp,
                "time_setup": o.time_setup,
                "comment": o.comment or ""
            })
    for armed in list(ARMED_CLOSE_ORDERS.values()):
        result.append({
            "ticket": armed["ticket"],
            "symbol": armed["symbol"],
            "type": armed["type"],
            "volume": armed["volume"],
            "price_open": armed["price_open"],
            "price_current": armed["price_current"],
            "sl": armed["sl"],
            "tp": armed["tp"],
            "time_setup": armed["time_setup"],
            "comment": armed["comment"]
        })
    return result

@app.post("/order/cancel/{ticket}")
async def cancel_pending_order(ticket: int):
    require_trading_enabled()
    if ticket in ARMED_CLOSE_ORDERS:
        ARMED_CLOSE_ORDERS.pop(ticket, None)
        return {"ticket": ticket, "status": "cancelled", "comment": "Cancelled armed candle-close order"}

    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
        "magic": 234000,
        "comment": "Antigravity Cancel",
    }
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Cancel failed", result))
        
    return {"ticket": ticket, "status": "cancelled", "comment": result.comment}

@app.post("/close/{ticket}")
async def close_order(ticket: int):
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get", ticket=ticket)
    if not pos or len(pos) == 0:
        raise HTTPException(status_code=404, detail="Position not found")
        
    p = pos[0]
    sym = p.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not tick:
        raise HTTPException(status_code=400, detail="Cannot get tick")
        
    is_buy = p.type == mt5.ORDER_TYPE_BUY
    close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    raw_price = tick.bid if is_buy else tick.ask
    digits = info.digits if info else 2
    price = round(raw_price, digits)
    
    filling_type = mt5.ORDER_FILLING_FOK
    if info:
        if info.filling_mode & 1:
            filling_type = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & 2:
            filling_type = mt5.ORDER_FILLING_IOC
        else:
            filling_type = mt5.ORDER_FILLING_RETURN

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": p.volume,
        "type": close_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 234000,
        "comment": "Antigravity Close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }
    
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Close failed", result))
        
    return {"ticket": result.order, "comment": result.comment}

@app.post("/position/modify")
async def modify_position(req: ModifyPositionRequest):
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get", ticket=req.ticket)
    if not pos or len(pos) == 0:
        raise HTTPException(status_code=404, detail="Position not found")
    
    p = pos[0]
    sym = p.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    digits = info.digits if info else 2
    sl = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp = round(float(req.tp), digits) if req.tp > 0 else 0.0

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": req.ticket,
        "symbol": sym,
        "sl": sl,
        "tp": tp,
    }
    
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Modify SL/TP failed", result))
        
    return {
        "ticket": req.ticket,
        "status": "modified",
        "sl": sl,
        "tp": tp,
        "comment": result.comment
    }

@app.post("/order/modify")
async def modify_pending_order(req: ModifyOrderRequest):
    require_trading_enabled()
    if req.ticket in ARMED_CLOSE_ORDERS:
        armed = ARMED_CLOSE_ORDERS[req.ticket]
        digits = armed["digits"]
        if req.price > 0:
            armed["price_open"] = round(float(req.price), digits)
        armed["sl"] = round(float(req.sl), digits) if req.sl > 0 else 0.0
        armed["tp"] = round(float(req.tp), digits) if req.tp > 0 else 0.0
        return {
            "ticket": req.ticket,
            "status": "modified",
            "price": armed["price_open"],
            "sl": armed["sl"],
            "tp": armed["tp"],
            "comment": "Modified armed candle-close order"
        }

    orders = await mt5_worker.execute_async("orders_get", ticket=req.ticket)
    if not orders or len(orders) == 0:
        raise HTTPException(status_code=404, detail="Pending order not found")
        
    o = orders[0]
    sym = o.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    digits = info.digits if info else 2
    price = round(float(req.price), digits) if req.price > 0 else o.price_open
    sl = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp = round(float(req.tp), digits) if req.tp > 0 else 0.0

    request = {
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": req.ticket,
        "symbol": sym,
        "price": price,
        "sl": sl,
        "tp": tp,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Modify pending order failed", result))
        
    return {
        "ticket": req.ticket,
        "status": "modified",
        "price": price,
        "sl": sl,
        "tp": tp,
        "comment": result.comment
    }

@app.post("/position/partial_close")
async def partial_close_position(req: PartialCloseRequest):
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get", ticket=req.ticket)
    if not pos or len(pos) == 0:
        raise HTTPException(status_code=404, detail="Position not found")
        
    p = pos[0]
    sym = p.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not tick:
        raise HTTPException(status_code=400, detail="Cannot get tick")
        
    is_buy = p.type == mt5.ORDER_TYPE_BUY
    close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    raw_price = tick.bid if is_buy else tick.ask
    digits = info.digits if info else 2
    price = round(raw_price, digits)
    
    vol_step = info.volume_step if info else 0.01
    min_vol = info.volume_min if info else 0.01
    if req.volume > 0:
        close_vol = min(p.volume, max(min_vol, round(req.volume, 2)))
    else:
        close_vol = round((p.volume * (req.pct / 100.0)) / vol_step) * vol_step
        close_vol = min(p.volume, max(min_vol, round(close_vol, 2)))
        
    if close_vol >= p.volume:
        close_vol = p.volume
        
    filling_type = mt5.ORDER_FILLING_FOK
    if info:
        if info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
        else: filling_type = mt5.ORDER_FILLING_RETURN

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": close_vol,
        "type": close_type,
        "position": req.ticket,
        "price": price,
        "deviation": 20,
        "magic": 234000,
        "comment": f"Antigravity Close {close_vol}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }
    
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Partial close failed", result))
        
    return {
        "ticket": req.ticket,
        "closed_volume": close_vol,
        "remaining_volume": round(p.volume - close_vol, 2),
        "comment": result.comment
    }

@app.post("/position/bank_and_reopen")
async def bank_profit_and_reopen(req: BankReopenRequest):
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get", ticket=req.ticket)
    if not pos or len(pos) == 0:
        raise HTTPException(status_code=404, detail="Position not found")
        
    p = pos[0]
    sym = p.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    tick = await mt5_worker.execute_async("symbol_info_tick", sym)
    if not tick:
        raise HTTPException(status_code=400, detail="Cannot get tick")
        
    is_buy = p.type == mt5.ORDER_TYPE_BUY
    digits = info.digits if info else 2
    
    close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    close_price = round(tick.bid if is_buy else tick.ask, digits)
    
    filling_type = mt5.ORDER_FILLING_FOK
    if info:
        if info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
        else: filling_type = mt5.ORDER_FILLING_RETURN

    close_req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": p.volume,
        "type": close_type,
        "position": req.ticket,
        "price": close_price,
        "deviation": 20,
        "magic": 234000,
        "comment": "Bank Profit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }
    close_res = await mt5_worker.execute_async("order_send", close_req)
    if close_res is None or close_res.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Bank profit close failed", close_res))

    new_entry_price = round(tick.ask if is_buy else tick.bid, digits)
    new_sl = round(p.price_open + (req.lock_profit_pts if is_buy else -req.lock_profit_pts), digits)
    new_tp = p.tp
    
    open_req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": p.volume,
        "type": p.type,
        "price": new_entry_price,
        "sl": new_sl,
        "tp": new_tp,
        "deviation": 20,
        "magic": 234000,
        "comment": "House Money Re-Open",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,
    }
    open_res = await mt5_worker.execute_async("order_send", open_req)
    new_ticket = open_res.order if open_res and open_res.retcode == mt5.TRADE_RETCODE_DONE else None
    
    return {
        "banked_ticket": req.ticket,
        "realized_profit": p.profit,
        "reopened_ticket": new_ticket,
        "new_sl": new_sl,
        "new_tp": new_tp,
        "status": "banked_and_riding_on_house_money"
    }

@app.post("/position/lock_profit")
async def lock_position_profit(req: LockProfitRequest):
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get", ticket=req.ticket)
    if not pos or len(pos) == 0:
        raise HTTPException(status_code=404, detail="Position not found")
        
    p = pos[0]
    sym = p.symbol
    info = await mt5_worker.execute_async("symbol_info", sym)
    digits = info.digits if info else 2
    is_buy = p.type == mt5.ORDER_TYPE_BUY
    
    if req.lock_type == "breakeven":
        target_sl = p.price_open
    else:
        margin = await mt5_worker.execute_async("order_calc_margin", p.type, sym, p.volume, p.price_open)
        margin_val = float(margin) if margin else 1.0
        tick_val = info.trade_tick_value if info and info.trade_tick_value else 0.01
        tick_size = info.trade_tick_size if info and info.trade_tick_size else 0.01
        pts = (margin_val / max(0.01, tick_val * (p.volume / 0.01))) * tick_size
        target_sl = p.price_open + pts if is_buy else p.price_open - pts

    target_sl = round(float(target_sl), digits)
    
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": req.ticket,
        "symbol": sym,
        "sl": target_sl,
        "tp": p.tp,
    }
    result = await mt5_worker.execute_async("order_send", request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=mt5_error_detail("Lock profit failed", result))
        
    return {
        "ticket": req.ticket,
        "locked_sl": target_sl,
        "type": req.lock_type,
        "comment": result.comment
    }

@app.post("/positions/close_all")
async def close_all_positions():
    require_trading_enabled()
    pos = await mt5_worker.execute_async("positions_get")
    if not pos:
        return {"closed_count": 0, "results": []}
    
    results = []
    for p in pos:
        try:
            sym = p.symbol
            info = await mt5_worker.execute_async("symbol_info", sym)
            tick = await mt5_worker.execute_async("symbol_info_tick", sym)
            is_buy = p.type == mt5.ORDER_TYPE_BUY
            close_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            price = round(tick.bid if is_buy else tick.ask, info.digits if info else 2)
            
            filling_type = mt5.ORDER_FILLING_FOK
            if info:
                if info.filling_mode & 1: filling_type = mt5.ORDER_FILLING_FOK
                elif info.filling_mode & 2: filling_type = mt5.ORDER_FILLING_IOC
                else: filling_type = mt5.ORDER_FILLING_RETURN

            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": sym,
                "volume": p.volume,
                "type": close_type,
                "position": p.ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Panic Flatten",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
            }
            res = await mt5_worker.execute_async("order_send", req)
            results.append({"ticket": p.ticket, "success": res and res.retcode == mt5.TRADE_RETCODE_DONE})
        except Exception as e:
            results.append({"ticket": p.ticket, "success": False, "error": str(e)})
            
    return {"closed_count": len([r for r in results if r.get("success")]), "results": results}

@app.get("/scanner/live")
async def get_live_scanner(timeframe: str = "M30"):
    tf_val = TF_MAP.get(timeframe, 30)
    results = []
    
    for symbol in sorted(ALLOWED_SYMBOLS):
        raw_sym = symbol.replace('_', ' ')
        await mt5_worker.execute_async("symbol_select", raw_sym, True)
        rates = await mt5_worker.execute_async("copy_rates_from_pos", raw_sym, tf_val, 0, 80)
        tick = await mt5_worker.execute_async("symbol_info_tick", raw_sym)
        info = await mt5_worker.execute_async("symbol_info", raw_sym)
        
        if rates is None or len(rates) < 30 or not tick or not info:
            continue
            
        df = pd.DataFrame(rates)
        curr_price = tick.bid
        digits = info.digits
        
        hl = df['high'] - df['low']
        hc = (df['high'] - df['close'].shift()).abs()
        lc = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        if pd.isna(atr) or atr == 0: atr = tr.mean()
        
        w = 4
        sw_highs = []
        sw_lows = []
        n = len(df)
        for i in range(w, n - w):
            if df['high'].iloc[i] == df['high'].iloc[i-w:i+w+1].max():
                sw_highs.append(float(df['high'].iloc[i]))
            if df['low'].iloc[i] == df['low'].iloc[i-w:i+w+1].min():
                sw_lows.append(float(df['low'].iloc[i]))
                
        margin_001 = await mt5_worker.execute_async("order_calc_margin", mt5.ORDER_TYPE_BUY, raw_sym, 0.01, tick.ask)
        spread_pts = round(float(info.spread * info.trade_tick_size), digits)
        
        found = False
        if sw_highs:
            sh_price = sw_highs[-1]
            dist = curr_price - sh_price
            dist_atr = dist / atr if atr > 0 else 0
            if -0.4 <= dist_atr <= 0.4:
                status = "AT_RETEST_ZONE"
            elif 0.4 < dist_atr <= 1.5:
                status = "APPROACHING"
            else:
                status = "PULLBACK"
                
            results.append({
                "symbol": symbol,
                "direction": "BULLISH",
                "setup": "Resistance -> Support",
                "level": round(sh_price, digits),
                "current_price": round(curr_price, digits),
                "dist_pts": round(dist, digits),
                "dist_atr": round(dist_atr, 2),
                "status": status,
                "margin_001": round(float(margin_001), 2) if margin_001 else 0.0,
                "spread_pts": spread_pts
            })
            found = True
            
        if not found and sw_lows:
            sl_price = sw_lows[-1]
            dist = sl_price - curr_price
            dist_atr = dist / atr if atr > 0 else 0
            if -0.4 <= dist_atr <= 0.4:
                status = "AT_RETEST_ZONE"
            elif 0.4 < dist_atr <= 1.5:
                status = "APPROACHING"
            else:
                status = "PULLBACK"
                
            results.append({
                "symbol": symbol,
                "direction": "BEARISH",
                "setup": "Support -> Resistance",
                "level": round(sl_price, digits),
                "current_price": round(curr_price, digits),
                "dist_pts": round(dist, digits),
                "dist_atr": round(dist_atr, 2),
                "status": status,
                "margin_001": round(float(margin_001), 2) if margin_001 else 0.0,
                "spread_pts": spread_pts
            })

    order_prio = {"AT_RETEST_ZONE": 0, "APPROACHING": 1, "PULLBACK": 2}
    results.sort(key=lambda x: (order_prio.get(x["status"], 3), abs(x["dist_atr"])))
    return results

@app.get("/weltrade/status")
async def get_weltrade_status():
    return await asyncio.to_thread(weltrade_bridge.check_session_status)

@app.post("/weltrade/open_login")
async def open_weltrade_login():
    return await asyncio.to_thread(weltrade_bridge.open_login_window)

@app.post("/weltrade/save_credentials")
async def save_weltrade_credentials(req: WeltradeCredentialsRequest):
    return await asyncio.to_thread(weltrade_bridge.save_credentials, req.email, req.password)

@app.post("/weltrade/transfer_to_safe")
async def transfer_to_weltrade_safe(req: WeltradeTransferRequest):
    return await asyncio.to_thread(weltrade_bridge.transfer_to_safe, req.from_account, req.amount)

@app.get("/orderflow")
async def get_orderflow(symbol: str, count: int = 500):
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is not allowed")
    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    now = datetime.datetime.now()
    ticks = await mt5_worker.execute_async("copy_ticks_from", sym, now - datetime.timedelta(minutes=30), count, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return {"symbol": symbol, "buy_volume": 0, "sell_volume": 0, "delta": 0, "total_ticks": 0}
        
    buy_vol = 0
    sell_vol = 0
    for t in ticks:
        flags = t[6] if len(t) > 6 else 0
        vol = t[4] if len(t) > 4 and t[4] > 0 else 1
        if flags & mt5.TICK_FLAG_BUY:
            buy_vol += vol
        elif flags & mt5.TICK_FLAG_SELL:
            sell_vol += vol
        else:
            buy_vol += vol / 2
            sell_vol += vol / 2
            
    return {
        "symbol": symbol,
        "total_ticks": len(ticks),
        "buy_volume": round(float(buy_vol), 2),
        "sell_volume": round(float(sell_vol), 2),
        "delta": round(float(buy_vol - sell_vol), 2),
        "imbalance_ratio": round(float(buy_vol / max(1.0, sell_vol)), 2)
    }

@app.get("/bars")
async def get_bars(symbol: str, timeframe: str, limit: int = 15000, end_time: int = None):
    if timeframe not in TF_MAP:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is not allowed")
    
    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    
    mt5_tf = TF_MAP[timeframe]
    
    if end_time:
        rates = await mt5_worker.execute_async("copy_rates_from", sym, mt5_tf, end_time, limit)
    else:
        rates = await mt5_worker.execute_async("copy_rates_from_pos", sym, mt5_tf, 0, limit)
        
    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
    df['time'] = df['time'].astype(int)
    
    return df.to_dict(orient='records')

@app.get("/candles/verify")
async def verify_candles(symbol: str, timeframe: str, count: int = 20):
    if timeframe not in TF_MAP:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is not allowed")
    
    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    mt5_tf = TF_MAP[timeframe]
    rates = await mt5_worker.execute_async("copy_rates_from_pos", sym, mt5_tf, 0, min(count, 100))
    if rates is None or len(rates) == 0:
        return {"status": "error", "symbol": symbol, "timeframe": timeframe, "bars": []}
        
    df = pd.DataFrame(rates)
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
    df['time'] = df['time'].astype(int)
    bars = df.to_dict(orient='records')
    
    return {
        "status": "ok",
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(bars),
        "server_time": int(datetime.datetime.utcnow().timestamp()),
        "bars": bars
    }

from app.backtest_engine import detect_trades_on_bars

@app.get("/backtest_trades")
async def get_backtest_trades(symbol: str = "FX_Vol_40", limit: int = 2000):
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} is not allowed")
    
    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async("symbol_select", sym, True)
    
    # Fetch M5 bars from MT5
    rates = await mt5_worker.execute_async("copy_rates_from_pos", sym, 5, 0, limit)
    if rates is None or len(rates) == 0:
        return []
        
    trades = detect_trades_on_bars(rates, symbol)
    return trades

@app.get("/structure")
async def get_structure(symbol: str, timeframe: str):
    if symbol not in ALLOWED_SYMBOLS or timeframe not in TF_MAP:
        return []

    file_path = os.path.join(DATA_DIR, f"{symbol}_{timeframe}_structure.parquet")
    if not os.path.exists(file_path):
        return []
    
    try:
        struct_df = pd.read_parquet(file_path)
        struct_df = struct_df[struct_df['struct_macro'].notna()]
        
        struct_df['time'] = struct_df['time'].astype('int64') // 10**9
        if 'confirmed_at_macro' in struct_df.columns:
            struct_df['confirmed_at_macro'] = struct_df['confirmed_at_macro'].astype('int64') // 10**9
            
        return struct_df[['time', 'struct_macro', 'confirmed_at_macro']].to_dict(orient='records')
    except Exception as e:
        print(f"Error reading structure {symbol} {timeframe}: {e}")
        return []

@app.websocket("/replay/ws")
async def websocket_replay(websocket: WebSocket):
    await websocket.accept()
    market_hub.register_client(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            sym = data.get('symbol')
            tf = data.get('timeframe') or data.get('tf')
            if sym and tf:
                if sym in ALLOWED_SYMBOLS and tf in TF_MAP:
                    market_hub.unsubscribe_all(websocket)
                    market_hub.subscribe(websocket, sym, tf)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error: {e}")
    finally:
        market_hub.unregister_client(websocket)
