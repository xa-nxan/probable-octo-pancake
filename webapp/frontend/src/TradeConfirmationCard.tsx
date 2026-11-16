import { useState, useEffect, useRef } from 'react';
import { CheckCircle2, AlertCircle, X, Loader2, Minimize2, Maximize2 } from 'lucide-react';

export interface PositionTradeState {
  id: string;
  kind: 'long-position' | 'short-position';
  entry: number;
  sl: number;
  tp: number;
  stopLevel: number;
  profitLevel: number;
}

interface TradeConfirmationCardProps {
  position: PositionTradeState;
  symbol: string;
  timeframe?: string;
  initialVolume?: string;
  positions?: any[];
  onUpdateSl: (newSl: number) => void;
  onUpdateTp: (newTp: number) => void;
  onUpdateEntry: (newEntry: number) => void;
  onDelete: () => void;
  onClose: () => void;
  onOrderSuccess?: (ticket: number, comment?: string) => void;
}

type OrderKind = 'stop' | 'market' | 'limit' | 'close';

export default function TradeConfirmationCard({
  position,
  symbol,
  timeframe = 'M30',
  initialVolume = '0.01',
  positions,
  onUpdateSl,
  onUpdateTp,
  onUpdateEntry,
  onDelete,
  onClose,
  onOrderSuccess
}: TradeConfirmationCardProps) {
  const isLong = position.kind === 'long-position';
  const sideColor = isLong ? '#089981' : '#f23645';
  const symClean = symbol.replace('_', ' ');
  const activeParent = positions?.find(
    (p: any) => (p.symbol === symClean || p.symbol === symbol) && p.tp > 0
  );

  const [orderTf, setOrderTf] = useState(timeframe);
  const [orderType, setOrderType] = useState<OrderKind>('stop');
  const [volume, setVolume] = useState(initialVolume || '0.01');
  const [riskMode, setRiskMode] = useState<'lots' | 'usd' | 'pct'>('lots');
  const [targetRiskUsd, setTargetRiskUsd] = useState('1.00');
  const [targetRiskPct, setTargetRiskPct] = useState('1.0');
  const [submitting, setSubmitting] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [risk, setRisk] = useState<{ slUsd: number; tpUsd: number; margin: number; balance: number } | null>(null);

  const stopDist = Math.abs(position.stopLevel);
  const profitDist = Math.abs(position.profitLevel);
  const rr = stopDist > 0 ? (profitDist / stopDist).toFixed(2) : '0.00';

  // Quick Take Profit Snapping to exact R:R multiples (1:2, 1:3, 1:5, 1:10)
  const snapRR = (targetRR: number) => {
    const entry = position.entry;
    const sl = position.sl;
    const riskDiff = Math.abs(entry - sl);
    if (riskDiff <= 0) return;
    const targetTp = isLong ? entry + riskDiff * targetRR : entry - riskDiff * targetRR;
    onUpdateTp(parseFloat(targetTp.toFixed(2)));
  };

  // Auto Lot Calculation when in Dollar Risk or Percent Risk mode
  useEffect(() => {
    if (riskMode === 'lots') return;
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/order/calc_lot_by_risk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol,
            action: isLong ? 'Buy' : 'Sell',
            entry: Number(position.entry.toFixed(2)),
            sl: Number(position.sl.toFixed(2)),
            target_risk_usd: riskMode === 'usd' ? parseFloat(targetRiskUsd) || 1.0 : undefined,
            target_risk_pct: riskMode === 'pct' ? parseFloat(targetRiskPct) || 1.0 : undefined
          })
        });
        if (!active || !res.ok) return;
        const d = await res.json();
        if (d.calculated_volume && active) {
          setVolume(d.calculated_volume.toFixed(2));
        }
      } catch (e) {
        // Fallback gracefully to existing volume
      }
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [riskMode, targetRiskUsd, targetRiskPct, position.entry, position.sl, symbol, isLong]);

  const orderLabel =
    orderType === 'stop' ? (isLong ? 'BUY STOP' : 'SELL STOP')
    : orderType === 'limit' ? (isLong ? 'BUY LIMIT' : 'SELL LIMIT')
    : orderType === 'close' ? (isLong ? `BUY ON ${orderTf} CLOSE` : `SELL ON ${orderTf} CLOSE`)
    : (isLong ? 'BUY' : 'SELL');

  const mt5OrderType =
    orderType === 'stop' ? (isLong ? 'Buy Stop' : 'Sell Stop')
    : orderType === 'limit' ? (isLong ? 'Buy Limit' : 'Sell Limit')
    : orderType === 'close' ? 'On Close'
    : 'Market';

  // Exact $ risk / reward / margin straight from MT5 (debounced while dragging)
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/order/calc_risk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol,
            action: isLong ? 'Buy' : 'Sell',
            volume: parseFloat(volume) || 0.01,
            entry: Number(position.entry.toFixed(2)),
            sl: Number(position.sl.toFixed(2)),
            tp: Number(position.tp.toFixed(2))
          })
        });
        if (!active || !res.ok) return;
        const d = await res.json();
        setRisk({ slUsd: d.sl_usd ?? 0, tpUsd: d.tp_usd ?? 0, margin: d.margin ?? 0, balance: d.balance ?? 0 });
      } catch {
        if (active) setRisk(null);
      }
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [position.entry, position.sl, position.tp, volume, symbol, isLong]);

  // One plain-English problem, if any
  let problem: string | null = null;
  if (risk) {
    if (risk.margin > risk.balance) {
      problem = `Not enough money. This trade needs $${risk.margin.toFixed(2)} margin, your balance is $${risk.balance.toFixed(2)}.`;
    } else if (Math.abs(risk.slUsd) > risk.balance) {
      problem = `Your stop loss would lose $${Math.abs(risk.slUsd).toFixed(2)}, more than your $${risk.balance.toFixed(2)} balance.`;
    }
  }

  const submittingRef = useRef(false);

  const handlePlaceOrder = async () => {
    if (submittingRef.current || submitting) return;
    submittingRef.current = true;
    setSubmitting(true);
    setResult(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          timeframe: orderTf,
          action: isLong ? 'Buy' : 'Sell',
          order_type: mt5OrderType,
          price: Number(position.entry.toFixed(2)),
          volume: parseFloat(volume) || 0.01,
          sl: Number(position.sl.toFixed(2)),
          tp: Number(position.tp.toFixed(2))
        })
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        const msg = data.action === 'ARMED_CLOSE'
          ? `Armed for ${orderTf} candle close (#${data.ticket})`
          : `Order placed. Ticket #${data.ticket}`;
        setResult({ success: true, message: msg });
        onOrderSuccess?.(data.ticket, data.comment);
      } else {
        setResult({ success: false, message: data.detail || 'MT5 rejected the order.' });
      }
    } catch (err: any) {
      setResult({ success: false, message: err.message || 'Cannot reach backend.' });
    } finally {
      setSubmitting(false);
      setTimeout(() => { submittingRef.current = false; }, 1500);
    }
  };

  const adjustVolume = (delta: number) => {
    const cur = parseFloat(volume) || 0.01;
    setVolume(Math.max(0.01, Math.round((cur + delta) * 100) / 100).toFixed(2));
  };

  const iconBtn: React.CSSProperties = { background: 'transparent', border: 'none', color: '#787b86', cursor: 'pointer', padding: 2, display: 'flex' };

  if (minimized) {
    return (
      <div style={{
        position: 'absolute', top: 60, left: 60, zIndex: 25,
        background: '#181b27', border: `1px solid ${sideColor}`, borderRadius: 6,
        padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 10,
        color: '#d1d4dc', fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.6)'
      }}>
        <b style={{ color: sideColor }}>{orderLabel} {volume}</b>
        <span>@ {position.entry.toFixed(2)}</span>
        {risk && <span style={{ color: '#f23645' }}>-${Math.abs(risk.slUsd).toFixed(2)}</span>}
        {risk && <span style={{ color: '#089981' }}>+${risk.tpUsd.toFixed(2)}</span>}
        <button onClick={() => setMinimized(false)} style={iconBtn} title="Expand"><Maximize2 size={14} /></button>
        <button onClick={onClose} style={iconBtn} title="Close"><X size={14} /></button>
      </div>
    );
  }

  const priceRow = (
    label: string,
    color: string,
    value: number,
    onChange: (v: number) => void,
    money: string | null,
    extra?: React.ReactNode
  ) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #2a2e39' }}>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ color, fontSize: 11, fontWeight: 700 }}>{label} {extra}</span>
        {money && <span style={{ color, fontSize: 11, opacity: 0.85 }}>{money}</span>}
      </div>
      <input
        type="number"
        step="0.1"
        value={value.toFixed(2)}
        onChange={(e) => onChange(parseFloat(e.target.value) || value)}
        style={{ background: 'transparent', border: 'none', color, fontWeight: 700, fontSize: 13, textAlign: 'right', width: 100 }}
      />
    </div>
  );

  return (
    <div style={{
      position: 'absolute', top: 60, left: 60, width: 260, zIndex: 25,
      background: '#181b27', border: `1px solid ${sideColor}66`, borderRadius: 8,
      padding: 12, color: '#d1d4dc', fontSize: 12,
      display: 'flex', flexDirection: 'column', gap: 10,
      boxShadow: '0 12px 32px rgba(0,0,0,0.7)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, color: sideColor }}>{isLong ? 'BUY' : 'SELL'} · <span style={{ color: '#fff' }}>{symClean}</span></span>
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={() => setMinimized(true)} style={iconBtn} title="Minimize"><Minimize2 size={14} /></button>
          <button onClick={onClose} style={iconBtn} title="Close"><X size={14} /></button>
        </div>
      </div>

      {/* Order type */}
      <div style={{ display: 'flex', background: '#131722', borderRadius: 6, padding: 2, gap: 2 }}>
        {(['close', 'limit', 'stop', 'market'] as OrderKind[]).map(t => (
          <button
            key={t}
            onClick={() => setOrderType(t)}
            style={{
              flex: 1, padding: '5px 0', border: 'none', borderRadius: 4, cursor: 'pointer',
              fontSize: 11, fontWeight: 700,
              background: orderType === t ? sideColor : 'transparent',
              color: orderType === t ? '#fff' : '#b2b5be'
            }}
          >
            {t === 'close' ? 'On Close' : t === 'stop' ? 'Stop' : t === 'market' ? 'Market' : 'Limit'}
          </button>
        ))}
      </div>

      {/* When On Close is selected: explicitly select trigger timeframe */}
      {orderType === 'close' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '3px 6px', background: '#131722', borderRadius: 4 }}>
          <span style={{ fontSize: 10, color: '#787b86', fontWeight: 600 }}>ARMED TF:</span>
          <div style={{ display: 'flex', gap: 3 }}>
            {['M1', 'M5', 'M15', 'M30'].map(tf => (
              <button
                key={tf}
                onClick={() => setOrderTf(tf)}
                style={{
                  background: orderTf === tf ? sideColor : '#1e222d',
                  color: orderTf === tf ? '#fff' : '#848e9c',
                  border: 'none',
                  borderRadius: 3,
                  padding: '2px 6px',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Sizing Mode Toggle: Manual Lots vs $ Risk vs % Equity */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', background: '#131722', borderRadius: 4, padding: 2, gap: 2 }}>
          <button
            onClick={() => setRiskMode('lots')}
            style={{
              flex: 1, padding: '3px 0', border: 'none', borderRadius: 3, cursor: 'pointer',
              fontSize: 10, fontWeight: 700,
              background: riskMode === 'lots' ? '#2962ff' : 'transparent',
              color: riskMode === 'lots' ? '#fff' : '#787b86'
            }}
          >
            Fixed Lots
          </button>
          <button
            onClick={() => setRiskMode('usd')}
            style={{
              flex: 1, padding: '3px 0', border: 'none', borderRadius: 3, cursor: 'pointer',
              fontSize: 10, fontWeight: 700,
              background: riskMode === 'usd' ? '#2962ff' : 'transparent',
              color: riskMode === 'usd' ? '#fff' : '#787b86'
            }}
          >
            $ Risk
          </button>
          <button
            onClick={() => setRiskMode('pct')}
            style={{
              flex: 1, padding: '3px 0', border: 'none', borderRadius: 3, cursor: 'pointer',
              fontSize: 10, fontWeight: 700,
              background: riskMode === 'pct' ? '#2962ff' : 'transparent',
              color: riskMode === 'pct' ? '#fff' : '#787b86'
            }}
          >
            % Equity
          </button>
        </div>

        {/* Dynamic Risk Inputs */}
        {riskMode === 'usd' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#1e222d', padding: '4px 8px', borderRadius: 4 }}>
            <span style={{ fontSize: 11, color: '#787b86' }}>Target Loss:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ color: '#f23645', fontWeight: 700 }}>$</span>
              <input
                type="number"
                step="0.5"
                min="0.1"
                value={targetRiskUsd}
                onChange={(e) => setTargetRiskUsd(e.target.value)}
                style={{ width: 55, height: 22, background: '#131722', border: '1px solid #2a2e39', borderRadius: 3, color: '#f23645', textAlign: 'center', fontWeight: 700, fontSize: 11 }}
              />
              <span style={{ fontSize: 11, color: '#787b86' }}>&rarr; <b style={{ color: '#fff' }}>{volume} lot</b></span>
            </div>
          </div>
        )}

        {riskMode === 'pct' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#1e222d', padding: '4px 8px', borderRadius: 4 }}>
            <span style={{ fontSize: 11, color: '#787b86' }}>Account Risk:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <input
                type="number"
                step="0.5"
                min="0.1"
                max="10"
                value={targetRiskPct}
                onChange={(e) => setTargetRiskPct(e.target.value)}
                style={{ width: 50, height: 22, background: '#131722', border: '1px solid #2a2e39', borderRadius: 3, color: '#f23645', textAlign: 'center', fontWeight: 700, fontSize: 11 }}
              />
              <span style={{ color: '#f23645', fontWeight: 700 }}>%</span>
              <span style={{ fontSize: 11, color: '#787b86' }}>&rarr; <b style={{ color: '#fff' }}>{volume} lot</b></span>
            </div>
          </div>
        )}

        {/* Manual Lots Controls */}
        {riskMode === 'lots' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ color: '#787b86', fontSize: 11, width: 30 }}>Lots</span>
            <button onClick={() => adjustVolume(-0.01)} style={{ width: 26, height: 26, background: '#2a2e39', border: 'none', borderRadius: 4, color: '#fff', cursor: 'pointer' }}>-</button>
            <input
              type="number" step="0.01" min="0.01" value={volume}
              onChange={(e) => setVolume(e.target.value)}
              style={{ flex: 1, height: 26, background: '#131722', border: '1px solid #2a2e39', borderRadius: 4, color: '#fff', textAlign: 'center', fontWeight: 600 }}
            />
            <button onClick={() => adjustVolume(0.01)} style={{ width: 26, height: 26, background: '#2a2e39', border: 'none', borderRadius: 4, color: '#fff', cursor: 'pointer' }}>+</button>
          </div>
        )}
      </div>

      {/* Prices */}
      <div>
        {priceRow(
          orderType === 'market' ? 'ENTRY (market)' : orderType === 'close' ? `ENTRY (${timeframe} close)` : 'ENTRY',
          '#fff', position.entry, onUpdateEntry, null
        )}
        {priceRow('STOP LOSS', '#f23645', position.sl, onUpdateSl, risk ? `-$${Math.abs(risk.slUsd).toFixed(2)}` : null)}
        {priceRow(
          'TAKE PROFIT', '#089981', position.tp, onUpdateTp,
          risk ? `+$${risk.tpUsd.toFixed(2)}` : null,
          activeParent && Math.abs(position.tp - activeParent.tp) >= 0.05 ? (
            <button
              onClick={() => onUpdateTp(activeParent.tp)}
              style={{ marginLeft: 4, background: 'transparent', border: '1px solid #089981', color: '#089981', borderRadius: 3, fontSize: 9, padding: '0 4px', cursor: 'pointer' }}
              title={`Use same TP as open trade #${activeParent.ticket}`}
            >
              match #{activeParent.ticket}
            </button>
          ) : null
        )}

        {/* Quick R:R Target Snap Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0 2px 0' }}>
          <span style={{ fontSize: 10, color: '#787b86', fontWeight: 600 }}>SNAP TP:</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {[
              { label: '1:2', rr: 2 },
              { label: '1:3', rr: 3 },
              { label: '1:5', rr: 5 },
              { label: '1:10', rr: 10 }
            ].map(item => (
              <button
                key={item.label}
                onClick={() => snapRR(item.rr)}
                style={{
                  background: '#1e222d',
                  color: '#089981',
                  border: '1px solid rgba(8,153,129,0.35)',
                  borderRadius: 3,
                  padding: '2px 6px',
                  fontSize: 10,
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
                title={`Snap Take Profit to 1:${item.rr} R:R`}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(8,153,129,0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#1e222d'}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary */}
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#787b86' }}>
        <span>R:R <b style={{ color: parseFloat(rr) >= 1.5 ? '#089981' : '#ff9800' }}>1:{rr}</b></span>
        <span>Margin <b style={{ color: '#d1d4dc' }}>{risk ? `$${risk.margin.toFixed(2)}` : '…'}</b></span>
      </div>

      {/* Single warning */}
      {problem && (
        <div style={{ display: 'flex', gap: 6, padding: 8, borderRadius: 4, background: 'rgba(255,152,0,0.12)', color: '#ff9800', fontSize: 11 }}>
          <AlertCircle size={14} style={{ flexShrink: 0 }} />
          <span>{problem}</span>
        </div>
      )}

      {/* Result */}
      {result && (
        <div style={{
          display: 'flex', gap: 6, padding: 8, borderRadius: 4, fontSize: 11,
          background: result.success ? 'rgba(8,153,129,0.15)' : 'rgba(242,54,69,0.15)',
          color: result.success ? '#089981' : '#f23645'
        }}>
          {result.success ? <CheckCircle2 size={14} style={{ flexShrink: 0 }} /> : <AlertCircle size={14} style={{ flexShrink: 0 }} />}
          <span style={{ wordBreak: 'break-word' }}>{result.message}</span>
        </div>
      )}

      {/* Actions */}
      <button
        onClick={handlePlaceOrder}
        disabled={submitting}
        style={{
          background: sideColor, color: '#fff', border: 'none', borderRadius: 5,
          padding: '9px 0', fontWeight: 700, fontSize: 13,
          cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1,
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6
        }}
      >
        {submitting ? <><Loader2 size={14} className="spin" /> Sending…</> : `${orderLabel} ${volume} @ ${position.entry.toFixed(2)}`}
      </button>
      <button
        onClick={onDelete}
        style={{ background: 'transparent', border: 'none', color: '#787b86', fontSize: 11, cursor: 'pointer' }}
      >
        Cancel plan
      </button>
    </div>
  );
}
