import os
import json
import time
import asyncio
import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.mt5_worker import mt5_worker
from app.market_hub import market_hub
from app.weltrade_bridge import weltrade_bridge
from app.live_cache import fast_cache
from app.scanner_engine import scan_11_universe, get_backtest_audit_proof


@asynccontextmanager
async def lifespan(app: FastAPI):
    mt5_worker.start()
    guardian_task = asyncio.create_task(_auto_position_guardian_loop())
    yield
    guardian_task.cancel()
    mt5_worker.execute("STOP")


app = FastAPI(title="Weltrade Synthetics MT5 Trading Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TF_MAP = {
    'M1': mt5.TIMEFRAME_M1,
    'M5': mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H4': mt5.TIMEFRAME_H4,
    '1D': mt5.TIMEFRAME_D1
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


@app.get("/symbols")
async def get_all_symbols():
    """
    Returns full list of available Weltrade Synthetics with metadata and categorization.
    """
    symbols = await mt5_worker.execute_async('symbols_get')
    if symbols is None:
        # Fallback to predefined list
        result = []
        for sym_id in ALL_WELTRADE_SYMBOLS:
            name = sym_id.replace('_', ' ')
            result.append({
                "id": sym_id,
                "name": name,
                "category": "Weltrade Synthetics",
                "digits": 2,
                "point": 0.01,
            })
        return result

    def get_cat(name: str) -> tuple[str, str, str]:
        if name.startswith('FX Vol'): return 'FX Volatility Series', 'FX Vol', '#2962ff'
        if name.startswith('SFX Vol'): return 'SFX Step-Vol Series', 'SFX Vol', '#089981'
        if 'GainX' in name: return 'GainX Series', 'GainX', '#26a69a'
        if 'PainX' in name: return 'PainX Series', 'PainX', '#ef5350'
        if name.startswith('FlipX'): return 'FlipX Series', 'FlipX', '#ff9800'
        if name.startswith('BreakX'): return 'BreakX Series', 'BreakX', '#00bcd4'
        if name.startswith('SwitchX'): return 'SwitchX Series', 'SwitchX', '#ab47bc'
        if name.startswith('TrendX'): return 'TrendX Series', 'TrendX', '#4caf50'
        return 'Other Synthetics', 'Other', '#9c27b0'

    result = []
    for s in symbols:
        name = s.name
        # Match only Weltrade Synthetics
        if any(x in name for x in ['Vol', 'Flip', 'Pain', 'Gain', 'Break', 'Switch', 'Trend', 'Fibo', 'Plus', 'Quad']):
            cat_name, group_code, color = get_cat(name)
            sym_id = name.replace(' ', '_')
            result.append({
                "id": sym_id,
                "name": name,
                "category": cat_name,
                "group": group_code,
                "color": color,
                "digits": s.digits,
                "point": s.point,
                "trade_stops_level": s.trade_stops_level,
                "volume_min": s.volume_min,
                "volume_max": s.volume_max,
                "volume_step": s.volume_step,
            })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 1. ACCOUNT & SWITCHING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/account")
async def get_account():
    cached = fast_cache.get_account(max_age_sec=1.0)
    if cached:
        return cached
    info = await mt5_worker.execute_async('account_info')
    term = await mt5_worker.execute_async('terminal_info')
    if info is None:
        return {
            "balance": 0, "equity": 0, "margin": 0, "margin_free": 0, "profit": 0
        }
    res = {
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
        "ping_ms": round(term.ping_last / 1000.0, 1) if term else 0,
        "terminal_connected": term.connected if term else False
    }
    fast_cache.set_account(res)
    return res


class AccountSwitchRequest(BaseModel):
    login: int
    server: str = "Weltrade-Real"
    password: str = ""


SAVED_MT5_CREDENTIALS = {
    34967194: ("E)6cGp!8", "Weltrade-Real"),
    43373678: ("", "Weltrade-Demo"),
}


@app.post("/account/switch")
async def switch_account(req: AccountSwitchRequest):
    pwd = req.password
    srv = req.server
    if not pwd and req.login in SAVED_MT5_CREDENTIALS:
        saved_pwd, saved_srv = SAVED_MT5_CREDENTIALS[req.login]
        if saved_pwd:
            pwd = saved_pwd
        if not srv:
            srv = saved_srv

    kwargs: Dict[str, Any] = {"server": srv}
    if pwd:
        kwargs["password"] = pwd

    ok = await mt5_worker.execute_async('login', req.login, **kwargs)
    if not ok:
        ok = await mt5_worker.execute_async('initialize', login=req.login, **kwargs)

    if not ok:
        err = mt5_worker.get_last_error()
        raise HTTPException(
            status_code=400,
            detail=f"MT5 Login to #{req.login} ({req.server}) failed. Please enter password or ensure credentials are saved in MT5 terminal. Error: {err}"
        )

    await asyncio.sleep(0.5)
    info = await mt5_worker.execute_async('account_info')
    if info is None or info.login != req.login:
        raise HTTPException(status_code=400, detail=f"Failed to verify login to #{req.login}.")

    fast_cache.invalidate_history()
    return {
        "status": "switched",
        "login": info.login,
        "server": info.server,
        "balance": info.balance,
        "equity": info.equity,
        "currency": info.currency
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. POSITIONS, HISTORY & PENDING ORDERS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/positions")
async def get_positions():
    cached = fast_cache.get_positions(max_age_sec=0.6)
    if cached is not None:
        return cached
    positions = await mt5_worker.execute_async('positions_get')
    if positions is None:
        return []
    res = []
    for p in positions:
        res.append({
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
    fast_cache.set_positions(res)
    return res


@app.get("/history")
async def get_history():
    cached = fast_cache.get_history(max_age_sec=10.0)
    if cached is not None:
        return cached
    now = datetime.datetime.now()
    from_date = now - datetime.timedelta(days=30)
    deals = await mt5_worker.execute_async('history_deals_get', from_date, now)
    if deals is None:
        return []
    res = []
    for d in reversed(deals):
        # Include closed trade exits (DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT)
        if d.entry in (1, 2):
            res.append({
                "ticket": d.ticket,
                "order": d.order,
                "position_id": d.position_id,
                "symbol": d.symbol,
                "type": "Sell" if d.type == 0 else "Buy",  # Closing deal is opposite of position type
                "volume": d.volume,
                "price": d.price,
                "profit": round(d.profit + d.commission + d.swap + d.fee, 2),
                "time": d.time,
                "comment": d.comment
            })
    res_slice = res[:100]
    fast_cache.set_history(res_slice)
    return res_slice


# Active server-side "On Candle Close" armed orders
ARMED_CLOSE_ORDERS: Dict[int, Dict[str, Any]] = {}
_NEXT_VIRTUAL_TICKET = 900000


@app.get("/orders")
async def get_orders():
    orders = await mt5_worker.execute_async('orders_get')
    res = []

    # 1. Include server-side armed "On Candle Close" orders first
    for v_ticket, ao in list(ARMED_CLOSE_ORDERS.items()):
        res.append({
            "ticket": v_ticket,
            "symbol": ao["symbol"],
            "type": f"{ao['action']} on {ao['timeframe']} Close",
            "volume": ao["volume"],
            "price_open": ao["price"],
            "price_current": ao.get("current_price", ao["price"]),
            "sl": ao["sl"],
            "tp": ao["tp"],
            "time_setup": ao["time_setup"],
            "comment": f"Armed: {ao['action']} if {ao['timeframe']} closes {'>=' if ao['action'] == 'Buy' else '<='} {ao['price']}"
        })

    # 2. Include standard MT5 pending orders
    if orders is not None:
        type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: "Buy Limit",
            mt5.ORDER_TYPE_SELL_LIMIT: "Sell Limit",
            mt5.ORDER_TYPE_BUY_STOP: "Buy Stop",
            mt5.ORDER_TYPE_SELL_STOP: "Sell Stop",
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: "Buy Stop Limit",
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: "Sell Stop Limit"
        }
        for o in orders:
            res.append({
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": type_map.get(o.type, f"Pending ({o.type})"),
                "volume": getattr(o, 'volume_current', getattr(o, 'volume_initial', 0.0)),
                "price_open": o.price_open,
                "price_current": o.price_current,
                "sl": o.sl,
                "tp": o.tp,
                "time_setup": o.time_setup,
                "comment": o.comment
            })
    return res


# ─────────────────────────────────────────────────────────────────────────────
# 3. RISK CALCULATION, SYMBOL DETAILS & ORDER EXECUTION
# ─────────────────────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    symbol: str
    timeframe: str = "M30"
    action: str               # "Buy" or "Sell"
    order_type: str = "Market"  # "Market", "Buy Stop", "Sell Stop", "Buy Limit", "Sell Limit", "On Close"
    volume: float = 0.01
    price: float = 0.0        # Required for Stop / Limit / On Close orders
    sl: float = 0.0
    tp: float = 0.0


class RiskCalcRequest(BaseModel):
    symbol: str
    action: str        # "Buy" or "Sell"
    volume: float = 0.01
    entry: float
    sl: float
    tp: float


class LotSizeByRiskRequest(BaseModel):
    symbol: str
    action: str        # "Buy" or "Sell"
    entry: float
    sl: float
    target_risk_usd: Optional[float] = None
    target_risk_pct: Optional[float] = None


@app.post("/order/calc_lot_by_risk")
async def calc_lot_by_risk(req: LotSizeByRiskRequest):
    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', sym, True)

    s_info = await mt5_worker.execute_async('symbol_info', sym)
    if s_info is None:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

    acc = await mt5_worker.execute_async('account_info')
    equity = float(acc.equity) if acc else 100.0
    balance = float(acc.balance) if acc else 100.0

    # Determine desired dollar risk
    if req.target_risk_usd is not None and req.target_risk_usd > 0:
        target_risk = float(req.target_risk_usd)
    elif req.target_risk_pct is not None and req.target_risk_pct > 0:
        target_risk = (req.target_risk_pct / 100.0) * equity
    else:
        target_risk = 0.01 * equity  # Default 1% risk

    mt5_type = mt5.ORDER_TYPE_BUY if req.action.lower() == 'buy' else mt5.ORDER_TYPE_SELL
    entry = float(req.entry)
    sl = float(req.sl)

    if sl <= 0 or abs(entry - sl) < 1e-6:
        return {
            "calculated_volume": s_info.volume_min,
            "target_risk_usd": round(target_risk, 2),
            "estimated_loss_usd": 0.0,
            "volume_min": s_info.volume_min,
            "volume_max": s_info.volume_max,
            "equity": round(equity, 2)
        }

    # Calculate loss for min lot (e.g. 0.01)
    base_vol = s_info.volume_min
    loss_base = await mt5_worker.execute_async('order_calc_profit', mt5_type, sym, base_vol, entry, sl)
    loss_base_abs = abs(float(loss_base)) if loss_base else 0.0

    if loss_base_abs <= 0:
        calc_vol = s_info.volume_min
    else:
        needed_vol = (target_risk / loss_base_abs) * base_vol
        step = s_info.volume_step if s_info.volume_step > 0 else 0.01
        steps = round(needed_vol / step)
        calc_vol = max(s_info.volume_min, min(s_info.volume_max, steps * step))
        calc_vol = round(calc_vol, 2)

    actual_loss = await mt5_worker.execute_async('order_calc_profit', mt5_type, sym, calc_vol, entry, sl)
    actual_margin = await mt5_worker.execute_async('order_calc_margin', mt5_type, sym, calc_vol, entry)

    return {
        "calculated_volume": calc_vol,
        "target_risk_usd": round(target_risk, 2),
        "estimated_loss_usd": round(abs(float(actual_loss)) if actual_loss else 0.0, 2),
        "estimated_margin_usd": round(float(actual_margin) if actual_margin else 0.0, 2),
        "volume_min": s_info.volume_min,
        "volume_max": s_info.volume_max,
        "volume_step": s_info.volume_step,
        "equity": round(equity, 2),
        "balance": round(balance, 2)
    }


@app.post("/order/calc_risk")
async def calc_order_risk(req: RiskCalcRequest):
    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', sym, True)

    mt5_type = mt5.ORDER_TYPE_BUY if req.action.lower() == 'buy' else mt5.ORDER_TYPE_SELL
    vol = round(float(req.volume), 2)
    entry = float(req.entry)
    sl = float(req.sl)
    tp = float(req.tp)

    sl_usd = await mt5_worker.execute_async('order_calc_profit', mt5_type, sym, vol, entry, sl) if sl > 0 else 0.0
    tp_usd = await mt5_worker.execute_async('order_calc_profit', mt5_type, sym, vol, entry, tp) if tp > 0 else 0.0
    margin = await mt5_worker.execute_async('order_calc_margin', mt5_type, sym, vol, entry)
    acc = await mt5_worker.execute_async('account_info')

    return {
        "sl_usd": round(sl_usd or 0.0, 2),
        "tp_usd": round(tp_usd or 0.0, 2),
        "margin": round(margin or 0.0, 2),
        "balance": round(acc.balance if acc else 0.0, 2),
        "equity": round(acc.equity if acc else 0.0, 2),
        "free_margin": round(acc.margin_free if acc else 0.0, 2)
    }


@app.get("/symbol_details")
async def get_symbol_details(symbol: str = "FX_Vol_20"):
    sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', sym, True)
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    if s_info is None:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

    ask = float(tick.ask) if tick else 0.0
    bid = float(tick.bid) if tick else 0.0
    margin_001 = await mt5_worker.execute_async('order_calc_margin', mt5.ORDER_TYPE_BUY, sym, 0.01, ask)

    return {
        "symbol": sym,
        "digits": s_info.digits,
        "point": s_info.point,
        "trade_stops_level": s_info.trade_stops_level,
        "min_stop_distance_price": round(s_info.trade_stops_level * s_info.point, s_info.digits),
        "volume_min": s_info.volume_min,
        "volume_max": s_info.volume_max,
        "volume_step": s_info.volume_step,
        "trade_contract_size": s_info.trade_contract_size,
        "trade_tick_value": s_info.trade_tick_value,
        "trade_tick_size": s_info.trade_tick_size,
        "spread_points": s_info.spread,
        "spread_price": round(ask - bid, s_info.digits) if (ask and bid) else 0.0,
        "bid": bid,
        "ask": ask,
        "margin_per_001_lot": round(margin_001, 2) if margin_001 is not None else 0.0
    }


@app.post("/order/check")
async def check_order_pretrade(req: OrderRequest):
    """
    Runs real-time MT5 order_check + margin + profit/loss calculation before placing an order.
    Surfaces exact broker validation reasons (No money, Invalid stops, Market closed, etc.).
    """
    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', sym, True)
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    acc = await mt5_worker.execute_async('account_info')

    if s_info is None or tick is None or acc is None:
        raise HTTPException(status_code=400, detail="MT5 symbol or account unavailable")

    digits = s_info.digits
    point = s_info.point
    min_stop_dist = s_info.trade_stops_level * point
    is_buy = req.action.lower() == 'buy'
    ot = req.order_type.lower().strip()
    is_pending = ot in ('buy stop', 'sell stop', 'buy limit', 'sell limit', 'stop', 'limit')

    market_price = float(tick.ask if is_buy else tick.bid)
    exec_price = round(req.price, digits) if (is_pending and req.price > 0) else round(market_price, digits)

    if not is_pending:
        trade_action = mt5.TRADE_ACTION_DEAL
        mt5_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    else:
        trade_action = mt5.TRADE_ACTION_PENDING
        if 'stop' in ot:
            mt5_type = mt5.ORDER_TYPE_BUY_STOP if is_buy else mt5.ORDER_TYPE_SELL_STOP
        else:
            mt5_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT

    calc_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
    vol = round(float(req.volume), 2)
    sl_val = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp_val = round(float(req.tp), digits) if req.tp > 0 else 0.0

    req_margin = await mt5_worker.execute_async('order_calc_margin', calc_type, sym, vol, exec_price)
    sl_profit = await mt5_worker.execute_async('order_calc_profit', calc_type, sym, vol, exec_price, sl_val) if sl_val > 0 else 0.0
    tp_profit = await mt5_worker.execute_async('order_calc_profit', calc_type, sym, vol, exec_price, tp_val) if tp_val > 0 else 0.0

    check_req = {
        "action": trade_action,
        "symbol": sym,
        "volume": vol,
        "type": mt5_type,
        "price": exec_price,
        "sl": sl_val,
        "tp": tp_val,
        "deviation": 50,
        "magic": 777000,
        "comment": "PreCheck",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    chk = await mt5_worker.execute_async('order_check', check_req)

    warnings = []
    if is_pending:
        if 'stop' in ot:
            if is_buy and exec_price <= tick.ask + min_stop_dist:
                warnings.append(f"Buy Stop trigger ({exec_price}) must be above current Ask ({tick.ask:.2f}) -> will auto-convert to Market or adjust.")
            elif (not is_buy) and exec_price >= tick.bid - min_stop_dist:
                warnings.append(f"Sell Stop trigger ({exec_price}) must be below current Bid ({tick.bid:.2f}) -> will auto-convert to Market or adjust.")
        elif 'limit' in ot:
            if is_buy and exec_price >= tick.ask - min_stop_dist:
                warnings.append(f"Buy Limit price ({exec_price}) must be below current Ask ({tick.ask:.2f}).")
            elif (not is_buy) and exec_price <= tick.bid + min_stop_dist:
                warnings.append(f"Sell Limit price ({exec_price}) must be above current Bid ({tick.bid:.2f}).")

    if sl_val > 0:
        if is_buy and sl_val >= exec_price - min_stop_dist:
            warnings.append(f"Buy SL ({sl_val}) must be at least {min_stop_dist} pts below entry ({exec_price}).")
        elif (not is_buy) and sl_val <= exec_price + min_stop_dist:
            warnings.append(f"Sell SL ({sl_val}) must be at least {min_stop_dist} pts above entry ({exec_price}).")

    if tp_val > 0:
        if is_buy and tp_val <= exec_price + min_stop_dist:
            warnings.append(f"Buy TP ({tp_val}) must be at least {min_stop_dist} pts above entry ({exec_price}).")
        elif (not is_buy) and tp_val >= exec_price - min_stop_dist:
            warnings.append(f"Sell TP ({tp_val}) must be at least {min_stop_dist} pts below entry ({exec_price}).")

    retcode = chk.retcode if chk else -1
    comment = chk.comment if chk else "Order check failed"
    margin_ok = (req_margin or 0) <= acc.margin_free
    if not margin_ok:
        warnings.append(f"Insufficient Free Margin: Requires ${req_margin:.2f}, but Free Margin is ${acc.margin_free:.2f}.")

    return {
        "valid": (retcode == 0) and margin_ok and len(warnings) == 0,
        "retcode": retcode,
        "comment": comment,
        "required_margin": round(req_margin or 0.0, 2),
        "free_margin": round(acc.margin_free, 2),
        "balance": round(acc.balance, 2),
        "equity": round(acc.equity, 2),
        "margin_after": round(chk.margin_free if chk else 0.0, 2),
        "margin_level_pct": round(chk.margin_level if chk else 0.0, 1),
        "sl_risk_usd": round(sl_profit or 0.0, 2),
        "tp_reward_usd": round(tp_profit or 0.0, 2),
        "risk_pct_of_balance": round((abs(sl_profit or 0.0) / acc.balance * 100.0), 2) if acc.balance > 0 else 0.0,
        "reward_pct_of_balance": round(((tp_profit or 0.0) / acc.balance * 100.0), 2) if acc.balance > 0 else 0.0,
        "min_stop_distance": round(min_stop_dist, digits),
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "spread_price": round(float(tick.ask - tick.bid), digits),
        "exec_price": exec_price,
        "warnings": warnings
    }


async def _watch_armed_close_order(v_ticket: int):
    """
    Background monitor for an armed 'On Candle Close' order:
    Watches the specified symbol & timeframe. As soon as a candle closes
    beyond the trigger level (close >= price for Buy, close <= price for Sell),
    it fires a live MT5 Market Order with the user's SL & TP.
    """
    ao = ARMED_CLOSE_ORDERS.get(v_ticket)
    if not ao:
        return

    sym = ao["symbol"]
    tf_str = ao["timeframe"]
    mt5_tf = TF_MAP.get(tf_str, mt5.TIMEFRAME_M30)
    is_buy = ao["action"].lower() == "buy"
    trigger_price = ao["price"]

    rates = await mt5_worker.execute_async('copy_rates_from_pos', sym, mt5_tf, 0, 2)
    last_bar_time = int(rates[-1]['time']) if (rates is not None and len(rates) > 0) else 0

    while v_ticket in ARMED_CLOSE_ORDERS:
        await asyncio.sleep(1.0)
        ao = ARMED_CLOSE_ORDERS.get(v_ticket)
        if not ao:
            break

        tick = await mt5_worker.execute_async('symbol_info_tick', sym)
        if tick:
            ao["current_price"] = round(float(tick.ask if is_buy else tick.bid), 2)

        rates = await mt5_worker.execute_async('copy_rates_from_pos', sym, mt5_tf, 0, 2)
        if rates is None or len(rates) < 2:
            continue

        current_bar_time = int(rates[-1]['time'])
        if last_bar_time == 0:
            last_bar_time = current_bar_time
            continue

        if current_bar_time > last_bar_time:
            closed_bar = rates[-2]
            closed_close = float(closed_bar['close'])
            last_bar_time = current_bar_time

            condition_met = (closed_close >= trigger_price) if is_buy else (closed_close <= trigger_price)
            if condition_met:
                print(f"[Armed Close #{v_ticket}] {sym} {tf_str} candle closed at {closed_close} (trigger {trigger_price}). Executing {ao['action']}!")
                ARMED_CLOSE_ORDERS.pop(v_ticket, None)
                try:
                    await place_order(OrderRequest(
                        symbol=sym,
                        timeframe=tf_str,
                        action=ao["action"],
                        order_type="Market",
                        volume=ao["volume"],
                        price=0.0,
                        sl=ao["sl"],
                        tp=ao["tp"]
                    ))
                except Exception as e:
                    print(f"[Armed Close #{v_ticket}] Market execution failed: {e}")
                break


def sanitize_comment(c: str) -> str:
    """
    MetaTrader 5 Python C extension strictly rejects comment strings longer than 27 characters
    or containing non-ascii characters with: (-2, 'Invalid "comment" argument').
    """
    if not c:
        return ""
    clean = str(c).encode('ascii', 'ignore').decode('ascii')
    return clean[:27].strip()


@app.post("/order")
async def place_order(req: OrderRequest):
    global _NEXT_VIRTUAL_TICKET
    sym = req.symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', sym, True)

    s_info = await mt5_worker.execute_async('symbol_info', sym)
    digits = s_info.digits if s_info else 2
    point = s_info.point if s_info else 0.01
    min_stop_dist = (s_info.trade_stops_level * point) if s_info else 0.0

    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    if tick is None:
        raise HTTPException(status_code=400, detail=f"Failed to get live tick for {sym}")

    is_buy = req.action.lower() == 'buy'
    ot = req.order_type.lower().strip()

    # Handle "On Candle Close" Armed Order
    if ot in ('on close', 'close', 'candle close'):
        _NEXT_VIRTUAL_TICKET += 1
        v_ticket = _NEXT_VIRTUAL_TICKET
        trigger_p = round(req.price if req.price > 0 else (tick.ask if is_buy else tick.bid), digits)
        ARMED_CLOSE_ORDERS[v_ticket] = {
            "ticket": v_ticket,
            "symbol": sym,
            "timeframe": req.timeframe,
            "action": "Buy" if is_buy else "Sell",
            "volume": round(float(req.volume), 2),
            "price": trigger_p,
            "current_price": round(float(tick.ask if is_buy else tick.bid), digits),
            "sl": round(float(req.sl), digits) if req.sl > 0 else 0.0,
            "tp": round(float(req.tp), digits) if req.tp > 0 else 0.0,
            "time_setup": int(time.time())
        }
        asyncio.create_task(_watch_armed_close_order(v_ticket))
        return {
            "status": "placed",
            "ticket": v_ticket,
            "action": "ARMED_CLOSE",
            "price": trigger_p,
            "volume": round(float(req.volume), 2),
            "comment": f"Armed for {req.timeframe} candle close {'>=' if is_buy else '<='} {trigger_p}"
        }

    is_pending = ot in ('buy stop', 'sell stop', 'buy limit', 'sell limit', 'stop', 'limit', 'pending')

    # Determine MT5 action and order type
    if not is_pending:
        trade_action = mt5.TRADE_ACTION_DEAL
        mt5_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        exec_price = round(tick.ask if is_buy else tick.bid, digits)
        comment_str = "Webapp Market"
    else:
        # STRICT PENDING ORDER: Preserve exact target entry, NEVER convert to market deal!
        trade_action = mt5.TRADE_ACTION_PENDING
        exec_price = round(req.price, digits)
        if exec_price <= 0:
            raise HTTPException(status_code=400, detail="Pending order requires a valid entry price.")

        min_allowed_dist = max(min_stop_dist, point * 3)

        if is_buy:
            # Buy Pending Orders
            price_diff = exec_price - tick.ask
            if abs(price_diff) < min_allowed_dist:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pending BUY entry {exec_price:.2f} is within {min_allowed_dist:.2f} pts of live Ask ({tick.ask:.2f}). Adjust price away from market."
                )
            if exec_price > tick.ask:
                mt5_type = mt5.ORDER_TYPE_BUY_STOP
                comment_str = "Webapp Buy Stop"
            else:
                mt5_type = mt5.ORDER_TYPE_BUY_LIMIT
                comment_str = "Webapp Buy Limit"
        else:
            # Sell Pending Orders
            price_diff = exec_price - tick.bid
            if abs(price_diff) < min_allowed_dist:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pending SELL entry {exec_price:.2f} is within {min_allowed_dist:.2f} pts of live Bid ({tick.bid:.2f}). Adjust price away from market."
                )
            if exec_price < tick.bid:
                mt5_type = mt5.ORDER_TYPE_SELL_STOP
                comment_str = "Webapp Sell Stop"
            else:
                mt5_type = mt5.ORDER_TYPE_SELL_LIMIT
                comment_str = "Webapp Sell Limit" 

    # Ensure SL and TP respect broker minimum stop distance relative to exec_price
    sl_val = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp_val = round(float(req.tp), digits) if req.tp > 0 else 0.0
    safe_pad = max(min_stop_dist + 2 * point, 5 * point)

    if is_buy:
        if sl_val > 0 and sl_val >= exec_price - safe_pad:
            sl_val = round(exec_price - safe_pad, digits)
        if tp_val > 0 and tp_val <= exec_price + safe_pad:
            tp_val = round(exec_price + safe_pad, digits)
    else:
        if sl_val > 0 and sl_val <= exec_price + safe_pad:
            sl_val = round(exec_price + safe_pad, digits)
        if tp_val > 0 and tp_val >= exec_price - safe_pad:
            tp_val = round(exec_price - safe_pad, digits)

    vol = round(float(req.volume), 2)
    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    res = None

    for fill_mode in filling_modes:
        request = {
            "action": trade_action,
            "symbol": sym,
            "volume": vol,
            "type": mt5_type,
            "price": exec_price,
            "sl": sl_val,
            "tp": tp_val,
            "deviation": 50,
            "magic": 777000,
            "comment": sanitize_comment(comment_str),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }
        res = await mt5_worker.execute_async('order_send', request)
        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
            break
        if res is not None and res.retcode != 10030:
            break

    if res is None:
        err = mt5_worker.get_last_error()
        raise HTTPException(status_code=400, detail=f"MT5 order_send returned None. Last error: {err}")

    if res.retcode != mt5.TRADE_RETCODE_DONE:
        raise HTTPException(status_code=400, detail=f"MT5 Order Rejected: {res.comment} (code {res.retcode})")

    return {
        "status": "placed",
        "ticket": res.order,
        "action": "PENDING" if trade_action == mt5.TRADE_ACTION_PENDING else "DEAL",
        "price": res.price if res.price > 0 else exec_price,
        "volume": res.volume,
        "comment": comment_str
    }


@app.post("/order/cancel/{ticket}")
async def cancel_pending_order(ticket: int):
    if ticket in ARMED_CLOSE_ORDERS:
        ARMED_CLOSE_ORDERS.pop(ticket, None)
        return {"status": "cancelled", "ticket": ticket}

    orders = await mt5_worker.execute_async('orders_get', ticket=ticket)
    if not orders:
        raise HTTPException(status_code=404, detail=f"Pending order {ticket} not found")

    request = {
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
    }
    res = await mt5_worker.execute_async('order_send', request)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Cancel failed: {comment} ({code})")

    return {"status": "cancelled", "ticket": ticket}


@app.post("/close/{ticket}")
async def close_position(ticket: int):
    positions = await mt5_worker.execute_async('positions_get', ticket=ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position {ticket} not found")

    pos = positions[0]
    sym = pos.symbol
    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    if tick is None:
        raise HTTPException(status_code=400, detail=f"No tick for {sym}")

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    res = None
    for fill_mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 50,
            "magic": 777000,
            "comment": "Webapp Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }
        res = await mt5_worker.execute_async('order_send', request)
        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
            break
        if res is not None and res.retcode != 10030:
            break

    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Close failed: {comment} ({code})")

    fast_cache.invalidate_history()
    return {"status": "closed", "ticket": ticket}


# ─────────────────────────────────────────────────────────────────────────────
# 4. POSITION & PENDING ORDER MODIFICATION & PROFIT PROTECTION
# ─────────────────────────────────────────────────────────────────────────────

class ModifyPositionRequest(BaseModel):
    ticket: int
    sl: float = 0.0
    tp: float = 0.0


@app.post("/position/modify")
async def modify_position(req: ModifyPositionRequest):
    """Updates Stop Loss (SL) and/or Take Profit (TP) on an active open MT5 position."""
    positions = await mt5_worker.execute_async('positions_get', ticket=req.ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Open position #{req.ticket} not found")

    pos = positions[0]
    sym = pos.symbol
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    digits = s_info.digits if s_info else 2

    sl_val = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp_val = round(float(req.tp), digits) if req.tp > 0 else 0.0

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": pos.ticket,
        "symbol": sym,
        "sl": sl_val,
        "tp": tp_val,
    }
    res = await mt5_worker.execute_async('order_send', request)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Failed to modify position SL/TP: {comment} ({code})")

    return {
        "status": "modified",
        "ticket": pos.ticket,
        "sl": sl_val,
        "tp": tp_val
    }


class ModifyPendingOrderRequest(BaseModel):
    ticket: int
    price: float
    sl: float = 0.0
    tp: float = 0.0


@app.post("/order/modify")
async def modify_pending_order(req: ModifyPendingOrderRequest):
    """Updates Trigger Price, Stop Loss (SL), and Take Profit (TP) on an active Pending Order or Armed Close Order."""
    if req.ticket in ARMED_CLOSE_ORDERS:
        ao = ARMED_CLOSE_ORDERS[req.ticket]
        if req.price > 0:
            ao["price"] = round(float(req.price), 2)
        ao["sl"] = round(float(req.sl), 2) if req.sl > 0 else 0.0
        ao["tp"] = round(float(req.tp), 2) if req.tp > 0 else 0.0
        return {
            "status": "modified",
            "ticket": req.ticket,
            "price": ao["price"],
            "sl": ao["sl"],
            "tp": ao["tp"]
        }

    orders = await mt5_worker.execute_async('orders_get', ticket=req.ticket)
    if not orders:
        raise HTTPException(status_code=404, detail=f"Pending order #{req.ticket} not found")

    ord_obj = orders[0]
    sym = ord_obj.symbol
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    digits = s_info.digits if s_info else 2

    price_val = round(float(req.price), digits) if req.price > 0 else round(float(ord_obj.price_open), digits)
    sl_val = round(float(req.sl), digits) if req.sl > 0 else 0.0
    tp_val = round(float(req.tp), digits) if req.tp > 0 else 0.0

    request = {
        "action": mt5.TRADE_ACTION_MODIFY,
        "order": ord_obj.ticket,
        "symbol": sym,
        "price": price_val,
        "sl": sl_val,
        "tp": tp_val,
        "type_time": ord_obj.type_time,
        "expiration": ord_obj.time_expiration,
    }
    res = await mt5_worker.execute_async('order_send', request)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Failed to modify pending order: {comment} ({code})")

    return {
        "status": "modified",
        "ticket": ord_obj.ticket,
        "price": price_val,
        "sl": sl_val,
        "tp": tp_val
    }


class PartialCloseRequest(BaseModel):
    ticket: int
    pct: float = 50.0  # e.g. 50% partial close


@app.post("/position/partial_close")
async def partial_close_position(req: PartialCloseRequest):
    """Closes a percentage (e.g. 50%) of an open position's volume to bank partial profits."""
    positions = await mt5_worker.execute_async('positions_get', ticket=req.ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position #{req.ticket} not found")

    pos = positions[0]
    sym = pos.symbol
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    vol_min = s_info.volume_min if s_info else 0.01
    vol_step = s_info.volume_step if s_info else 0.01

    if pos.volume <= vol_min:
        raise HTTPException(
            status_code=400,
            detail=f"Position volume ({pos.volume} lots) is already at minimum lot size ({vol_min}). Use 'Bank & Ride' or 'Lock +Margin' instead!"
        )

    raw_close_vol = pos.volume * (req.pct / 100.0)
    steps = max(1, round(raw_close_vol / vol_step))
    close_vol = round(min(pos.volume - vol_min, steps * vol_step), 2)

    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    if tick is None:
        raise HTTPException(status_code=400, detail=f"No live tick for {sym}")

    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    res = None
    for fill_mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": close_vol,
            "type": close_type,
            "position": req.ticket,
            "price": price,
            "deviation": 50,
            "magic": 777000,
            "comment": f"Partial Close {int(req.pct)}%",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }
        res = await mt5_worker.execute_async('order_send', request)
        if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
            break
        if res is not None and res.retcode != 10030:
            break

    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Partial close failed: {comment} ({code})")

    fast_cache.invalidate_history()
    return {
        "status": "partial_closed",
        "ticket": req.ticket,
        "closed_volume": close_vol,
        "remaining_volume": round(pos.volume - close_vol, 2)
    }


class BankAndReopenRequest(BaseModel):
    ticket: int


@app.post("/position/bank_and_reopen")
async def bank_and_reopen_position(req: BankAndReopenRequest):
    """
    For 0.01 minimum-lot positions (or any size):
    1. Closes the profitable trade immediately to bank 100% of floating profit into Account Balance.
    2. Immediately re-opens a fresh position in the same direction with the same TP and protective SL.
    """
    positions = await mt5_worker.execute_async('positions_get', ticket=req.ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position #{req.ticket} not found")

    pos = positions[0]
    sym = pos.symbol
    is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
    vol = pos.volume
    old_tp = pos.tp
    old_open = pos.price_open
    banked_profit = pos.profit

    # 1. Close current position to realize profit
    await close_position(req.ticket)

    # 2. Re-open immediately in same direction, setting SL at old entry (or tight structure buffer)
    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    s_info = await mt5_worker.execute_async('symbol_info', sym)
    digits = s_info.digits if s_info else 2
    point = s_info.point if s_info else 0.01
    min_stop = (s_info.trade_stops_level * point) if s_info else 1.0

    new_entry = tick.ask if is_buy else tick.bid
    if is_buy:
        safe_sl = round(min(old_open, new_entry - max(min_stop * 2, 15.0 * point)), digits) if old_open < new_entry else round(pos.sl, digits)
    else:
        safe_sl = round(max(old_open, new_entry + max(min_stop * 2, 15.0 * point)), digits) if old_open > new_entry else round(pos.sl, digits)

    new_order = await place_order(OrderRequest(
        symbol=sym,
        action="Buy" if is_buy else "Sell",
        order_type="Market",
        volume=vol,
        price=0.0,
        sl=safe_sl,
        tp=old_tp
    ))

    return {
        "status": "banked_and_reopened",
        "old_ticket": req.ticket,
        "banked_profit_usd": round(banked_profit, 2),
        "new_ticket": new_order.get("ticket"),
        "new_entry": new_order.get("price"),
        "sl": safe_sl,
        "tp": old_tp
    }


class LockProfitRequest(BaseModel):
    ticket: int
    lock_type: str = "margin"  # "breakeven" or "margin"


@app.post("/position/lock_profit")
async def lock_position_profit(req: LockProfitRequest):
    """
    Moves Stop Loss into profit so that:
    - 'breakeven': SL is placed at Entry Price + small spread buffer ($0.05+).
    - 'margin': SL is placed in profit by an amount equal to the required margin for the position
      (guaranteed 'Free Ride' + Margin Covered!).
    """
    positions = await mt5_worker.execute_async('positions_get', ticket=req.ticket)
    if not positions:
        raise HTTPException(status_code=404, detail=f"Position #{req.ticket} not found")

    pos = positions[0]
    sym = pos.symbol
    is_buy = (pos.type == mt5.ORDER_TYPE_BUY)

    s_info = await mt5_worker.execute_async('symbol_info', sym)
    tick = await mt5_worker.execute_async('symbol_info_tick', sym)
    if not s_info or not tick:
        raise HTTPException(status_code=400, detail=f"Symbol info unavailable for {sym}")

    digits = s_info.digits
    point = s_info.point
    min_stop_dist = max(s_info.trade_stops_level * point, 2 * point)

    req_margin = await mt5_worker.execute_async(
        'order_calc_margin',
        mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        sym,
        pos.volume,
        pos.price_open
    )
    margin_usd = float(req_margin) if req_margin else 0.50

    test_move = 10.0
    test_target = pos.price_open + test_move if is_buy else pos.price_open - test_move
    usd_for_10pts = await mt5_worker.execute_async(
        'order_calc_profit',
        mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        sym,
        pos.volume,
        pos.price_open,
        test_target
    )
    usd_per_point = (abs(usd_for_10pts) / test_move) if (usd_for_10pts and abs(usd_for_10pts) > 0) else (pos.volume * 0.1)

    if req.lock_type == "breakeven":
        target_usd = 0.05
    else:
        target_usd = max(margin_usd, 0.25)

    points_needed = target_usd / usd_per_point

    if is_buy:
        desired_sl = round(pos.price_open + points_needed, digits)
        max_allowed_sl = round(tick.bid - min_stop_dist, digits)
        if desired_sl > max_allowed_sl:
            if pos.price_open <= max_allowed_sl:
                desired_sl = max_allowed_sl
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Trade needs to move a bit further into profit before locking {req.lock_type} (Current Bid: {tick.bid:.2f}, Entry: {pos.price_open:.2f})."
                )
    else:
        desired_sl = round(pos.price_open - points_needed, digits)
        min_allowed_sl = round(tick.ask + min_stop_dist, digits)
        if desired_sl < min_allowed_sl:
            if pos.price_open >= min_allowed_sl:
                desired_sl = min_allowed_sl
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Trade needs to move a bit further into profit before locking {req.lock_type} (Current Ask: {tick.ask:.2f}, Entry: {pos.price_open:.2f})."
                )

    mod_req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": pos.ticket,
        "symbol": sym,
        "sl": desired_sl,
        "tp": pos.tp,
    }
    res = await mt5_worker.execute_async('order_send', mod_req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else "None"
        code = res.retcode if res else -1
        raise HTTPException(status_code=400, detail=f"Lock profit failed: {comment} ({code})")

    locked_usd = await mt5_worker.execute_async(
        'order_calc_profit',
        mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
        sym,
        pos.volume,
        pos.price_open,
        desired_sl
    )

    return {
        "status": "locked",
        "ticket": pos.ticket,
        "lock_type": req.lock_type,
        "new_sl": desired_sl,
        "locked_profit_usd": round(locked_usd or 0.0, 2),
        "margin_usd": round(margin_usd, 2)
    }


@app.post("/positions/close_all")
async def close_all_positions():
    """Panic Flatten: Closes all open positions on the MT5 account immediately."""
    positions = await mt5_worker.execute_async('positions_get')
    if not positions:
        return {"status": "all_closed", "closed_count": 0}

    closed = []
    errors = []
    for p in positions:
        try:
            await close_position(p.ticket)
            closed.append(p.ticket)
        except Exception as e:
            errors.append({"ticket": p.ticket, "error": str(e)})

    return {
        "status": "all_closed",
        "closed_count": len(closed),
        "closed_tickets": closed,
        "errors": errors
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTO-POSITION GUARDIAN (BREAKEVEN & M5 SWING TRAILING RATCHET)
# ─────────────────────────────────────────────────────────────────────────────

AUTO_GUARDIAN_ENABLED = True
GUARDIAN_EVENTS: list = []


async def _auto_position_guardian_loop():
    """
    Monitors all open MT5 positions every 2 seconds:
    1. Auto-Breakeven Lock: When an open position reaches >= +1.8R in profit
       (or >= 35% of the distance to TP if SL wasn't set), automatically moves SL
       to Entry + Spread buffer so a winning trade never turns into a full loss.
    2. Structural Trailing Ratchet: Once a position is >= +2.0R in profit, trails SL
       behind the most recent closed M5 fractal swing low (for Buy) or swing high (for Sell)
       so winners ride to full TP while locking in structural gains.
    """
    while True:
        await asyncio.sleep(2.0)
        if not AUTO_GUARDIAN_ENABLED:
            continue
        try:
            positions = await mt5_worker.execute_async('positions_get')
            if not positions:
                continue

            for pos in positions:
                sym = pos.symbol
                is_buy = (pos.type == mt5.ORDER_TYPE_BUY)
                entry = float(pos.price_open)
                cur = float(pos.price_current)
                sl = float(pos.sl)
                tp = float(pos.tp)

                s_info = await mt5_worker.execute_async('symbol_info', sym)
                tick = await mt5_worker.execute_async('symbol_info_tick', sym)
                if not s_info or not tick:
                    continue

                digits = s_info.digits
                point = s_info.point
                min_stop = max(s_info.trade_stops_level * point, 5 * point)
                spread = max(float(tick.ask - tick.bid), 2 * point)

                # Calculate initial 1R distance
                if sl > 0 and ((is_buy and sl < entry) or ((not is_buy) and sl > entry)):
                    risk_dist = abs(entry - sl)
                elif tp > 0:
                    risk_dist = abs(tp - entry) / 3.0
                else:
                    risk_dist = max(spread * 4.0, entry * 0.002)

                if risk_dist <= 0:
                    continue

                fav_move = (cur - entry) if is_buy else (entry - cur)
                current_r = fav_move / risk_dist

                # Check if SL is already at or better than Breakeven
                already_be = (sl >= entry) if is_buy else (sl > 0 and sl <= entry)

                new_sl = None
                reason = ""

                # Stage 1: +1.8R reached -> Lock Protected Breakeven (Entry + 0.15R buffer)
                if not already_be and current_r >= 1.8:
                    be_buffer = max(spread * 1.2, risk_dist * 0.15)
                    candidate_sl = round(entry + be_buffer, digits) if is_buy else round(entry - be_buffer, digits)
                    if is_buy and candidate_sl < (tick.bid - min_stop):
                        new_sl = candidate_sl
                        reason = f"Auto-BE locked at +{current_r:.1f}R"
                    elif (not is_buy) and candidate_sl > (tick.ask + min_stop):
                        new_sl = candidate_sl
                        reason = f"Auto-BE locked at +{current_r:.1f}R"

                # Stage 2: +2.0R reached -> Trail behind latest M5 3-bar swing low/high
                if current_r >= 2.0:
                    rates = await mt5_worker.execute_async('copy_rates_from_pos', sym, mt5.TIMEFRAME_M5, 1, 12)
                    if rates is not None and len(rates) >= 5:
                        lows = [float(r['low']) for r in rates]
                        highs = [float(r['high']) for r in rates]
                        if is_buy:
                            swing_lows = [
                                lows[i] for i in range(1, len(lows) - 1)
                                if lows[i] <= lows[i - 1] and lows[i] <= lows[i + 1]
                            ]
                            if swing_lows:
                                latest_hl = swing_lows[-1] - spread * 0.5
                                trail_sl = round(max(entry + spread, latest_hl), digits)
                                if trail_sl > sl and trail_sl < (tick.bid - min_stop):
                                    new_sl = trail_sl
                                    reason = f"M5 Swing Trail at +{current_r:.1f}R"
                        else:
                            swing_highs = [
                                highs[i] for i in range(1, len(highs) - 1)
                                if highs[i] >= highs[i - 1] and highs[i] >= highs[i + 1]
                            ]
                            if swing_highs:
                                latest_lh = swing_highs[-1] + spread * 0.5
                                trail_sl = round(min(entry - spread, latest_lh), digits)
                                if (sl == 0 or trail_sl < sl) and trail_sl > (tick.ask + min_stop):
                                    new_sl = trail_sl
                                    reason = f"M5 Swing Trail at +{current_r:.1f}R"

                if new_sl is not None and abs(new_sl - sl) > point:
                    mod_req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "symbol": sym,
                        "sl": new_sl,
                        "tp": tp,
                    }
                    res = await mt5_worker.execute_async('order_send', mod_req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        evt = {
                            "time": int(time.time()),
                            "ticket": pos.ticket,
                            "symbol": sym,
                            "new_sl": new_sl,
                            "reason": reason
                        }
                        GUARDIAN_EVENTS.insert(0, evt)
                        if len(GUARDIAN_EVENTS) > 30:
                            GUARDIAN_EVENTS.pop()
                        print(f"[Guardian] #{pos.ticket} {sym}: {reason} -> SL={new_sl}")
        except Exception as e:
            print(f"[Guardian Loop Error]: {e}")


@app.get("/guardian/status")
async def get_guardian_status():
    return {
        "enabled": AUTO_GUARDIAN_ENABLED,
        "recent_events": GUARDIAN_EVENTS[:10]
    }


@app.post("/guardian/toggle")
async def toggle_guardian():
    global AUTO_GUARDIAN_ENABLED
    AUTO_GUARDIAN_ENABLED = not AUTO_GUARDIAN_ENABLED
    return {"enabled": AUTO_GUARDIAN_ENABLED}


# ─────────────────────────────────────────────────────────────────────────────
# 6. WELTRADE SAFE VAULT & CABINET BRIDGE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class WeltradeCredsRequest(BaseModel):
    email: str
    password: str = ""


class WeltradeTransferRequest(BaseModel):
    from_account: str
    amount: float


@app.get("/weltrade/status")
async def get_weltrade_status():
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, weltrade_bridge.check_session_status)
    return res


@app.post("/weltrade/open_login")
async def open_weltrade_login():
    return weltrade_bridge.open_login_window()


@app.post("/weltrade/save_credentials")
async def save_weltrade_creds(req: WeltradeCredsRequest):
    return weltrade_bridge.save_credentials(req.email, req.password)


@app.post("/weltrade/transfer_to_safe")
async def transfer_to_weltrade_safe(req: WeltradeTransferRequest):
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, weltrade_bridge.transfer_to_safe, req.from_account, req.amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("detail", "Transfer failed"))
    return res


# ─────────────────────────────────────────────────────────────────────────────
# 7. ORDERFLOW, BARS, CANDLE VERIFICATION & LIVE WEBSOCKET
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/orderflow")
async def get_orderflow(symbol: str = "Step_Index", lookback_hours: int = 24):
    raw_sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', raw_sym, True)
    bars_count = min(lookback_hours * 60, 5000)
    rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, mt5.TIMEFRAME_M1, 0, bars_count)

    if rates is None or len(rates) == 0:
        return {"poc": 0, "vah": 0, "val": 0, "profile": [], "delta": []}

    df = pd.DataFrame(rates)
    df['time'] = df['time'].astype(int)

    min_p = df['low'].min()
    max_p = df['high'].max()
    if max_p == min_p:
        return {"poc": min_p, "vah": max_p, "val": min_p, "profile": [], "delta": []}

    num_bins = 40
    bins = np.linspace(min_p, max_p, num_bins + 1)
    df['typical'] = (df['high'] + df['low'] + df['close']) / 3.0
    df['bin'] = np.digitize(df['typical'], bins) - 1
    df['bin'] = df['bin'].clip(0, num_bins - 1)

    df['is_up'] = df['close'] >= df['open']
    df['buy_vol'] = np.where(df['is_up'], df['tick_volume'], 0)
    df['sell_vol'] = np.where(~df['is_up'], df['tick_volume'], 0)

    profile = []
    total_vol = df['tick_volume'].sum()
    max_bin_vol = 0
    poc_price = min_p

    bin_vols = []
    for i in range(num_bins):
        sub = df[df['bin'] == i]
        b_vol = int(sub['buy_vol'].sum())
        s_vol = int(sub['sell_vol'].sum())
        t_vol = b_vol + s_vol
        p_level = float((bins[i] + bins[i + 1]) / 2.0)
        if t_vol > max_bin_vol:
            max_bin_vol = t_vol
            poc_price = p_level
        bin_vols.append((p_level, t_vol, b_vol, s_vol))

    sorted_bins = sorted(bin_vols, key=lambda x: x[1], reverse=True)
    cum_vol = 0
    va_prices = []
    for p_level, t_vol, _, _ in sorted_bins:
        cum_vol += t_vol
        va_prices.append(p_level)
        if cum_vol >= total_vol * 0.70:
            break

    vah = max(va_prices) if va_prices else max_p
    val = min(va_prices) if va_prices else min_p

    for p_level, t_vol, b_vol, s_vol in bin_vols:
        profile.append({
            "price": round(p_level, 2),
            "vol": t_vol,
            "buy_vol": b_vol,
            "sell_vol": s_vol,
            "pct": round(t_vol / max_bin_vol * 100, 1) if max_bin_vol > 0 else 0,
            "is_poc": p_level == poc_price,
            "in_va": val <= p_level <= vah
        })

    df['bar_delta'] = np.where(
        df['high'] != df['low'],
        ((df['close'] - df['open']) / (df['high'] - df['low'])) * df['tick_volume'],
        0
    )
    df['cvd'] = df['bar_delta'].cumsum()
    recent_delta = df.tail(120)[['time', 'bar_delta', 'cvd']].to_dict(orient='records')

    return {
        "poc": round(poc_price, 2),
        "vah": round(vah, 2),
        "val": round(val, 2),
        "profile": profile,
        "delta": recent_delta
    }


@app.get("/bars")
async def get_bars(symbol: str = "Volatility_75_Index", timeframe: str = "M15", limit: int = 1500):
    mt5_tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_M15)
    raw_sym = symbol.replace('_', ' ')

    cached_df = fast_cache.get_rates(raw_sym, mt5_tf)
    if cached_df is not None and len(cached_df) >= limit:
        return cached_df.iloc[-limit:].to_dict(orient='records')

    await mt5_worker.execute_async('symbol_select', raw_sym, True)
    rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, mt5_tf, 0, limit)

    if rates is None or len(rates) == 0:
        return []

    df = pd.DataFrame(rates)
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
    df['time'] = df['time'].astype(int)

    fast_cache.set_rates(raw_sym, mt5_tf, df, ttl_sec=0.8)
    return df.to_dict(orient='records')


@app.get("/candles/verify")
async def verify_candles_with_mt5(symbol: str = "FX_Vol_20", timeframe: str = "M15", count: int = 20):
    """
    Fetches the latest `count` bars directly from the live MT5 terminal (bypassing all caches)
    so the frontend can verify 100% OHLCV & timestamp parity with MT5.
    """
    mt5_tf = TF_MAP.get(timeframe, mt5.TIMEFRAME_M15)
    raw_sym = symbol.replace('_', ' ')
    await mt5_worker.execute_async('symbol_select', raw_sym, True)
    rates = await mt5_worker.execute_async('copy_rates_from_pos', raw_sym, mt5_tf, 0, min(count, 100))

    if rates is None or len(rates) == 0:
        return {"status": "error", "symbol": symbol, "timeframe": timeframe, "bars": []}

    df = pd.DataFrame(rates)
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(columns={'tick_volume': 'volume'})
    df['time'] = df['time'].astype(int)
    bars = df.to_dict(orient='records')

    return {
        "status": "ok",
        "symbol": symbol,
        "mt5_symbol": raw_sym,
        "timeframe": timeframe,
        "verified_at": int(time.time() * 1000),
        "count": len(bars),
        "bars": bars
    }


@app.websocket("/replay/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    current_sym = None
    current_tf = None

    market_hub.register_client(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            sym = msg.get("symbol", "FX_Vol_20")
            tf = msg.get("timeframe", "M15")

            if current_sym and current_tf:
                market_hub.unsubscribe(websocket, current_sym, current_tf)

            current_sym = sym
            current_tf = tf
            market_hub.subscribe(websocket, current_sym, current_tf)

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket.")
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        market_hub.unregister_client(websocket)


# =====================================================================
# 100-QUESTION RULE-BASED MTF SCANNER & SUGGESTER (11 SYNTHETICS)
# =====================================================================

@app.get("/scanner/signals")
@app.get("/scanner/live")
async def get_scanner_signals(force_refresh: bool = False):
    """
    Returns real-time 100-Question Rule-Based setups and trade suggestions
    for the exact 11 requested synthetics:
    FX Vol 20, 40, 60; SFX Vol 20, 40, 60; FlipX 1, 2, 3, 4, 5.
    """
    signals = await scan_11_universe(force_refresh=force_refresh)
    return {"status": "ok", "count": len(signals), "signals": signals}


@app.get("/scanner/backtest_proof")
async def get_scanner_backtest_proof():
    """
    Returns verified 6-month, 16,180-trade backtest audit metrics across the 11 synthetics.
    """
    return get_backtest_audit_proof()

