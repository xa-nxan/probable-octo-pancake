import { useState, useEffect } from 'react';
import { X, Layers, CheckCircle2, AlertCircle, Loader2, ArrowUpRight, ArrowDownRight, ShieldCheck } from 'lucide-react';

export interface MT5Position {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  profit: number;
  time: number;
}

interface PyramidModalProps {
  position: MT5Position;
  onClose: () => void;
  onSuccess: (ticket: number, comment?: string) => void;
}

export default function PyramidModal({ position, onClose, onSuccess }: PyramidModalProps) {
  const isBuy = position.type.toLowerCase() === 'buy';
  const [orderType, setOrderType] = useState<'market' | 'stop' | 'limit'>('stop');
  const [volume, setVolume] = useState('0.01');
  const [entryPrice, setEntryPrice] = useState(
    position.price_current ? position.price_current.toFixed(2) : position.price_open.toFixed(2)
  );
  
  // Default SL to parent entry price (Risk-free breakeven for parent!)
  const [sl, setSl] = useState(
    position.price_open > 0 ? position.price_open.toFixed(2) : (position.sl > 0 ? position.sl.toFixed(2) : '')
  );
  
  // TP is strictly locked to parent TP
  const parentTp = position.tp;

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string; ticket?: number } | null>(null);

  // Set default entry price when switching order types
  useEffect(() => {
    if (orderType === 'stop') {
      const offset = isBuy ? 50 : -50;
      setEntryPrice((position.price_current + offset).toFixed(2));
    } else if (orderType === 'limit') {
      const offset = isBuy ? -50 : 50;
      setEntryPrice((position.price_current + offset).toFixed(2));
    } else {
      setEntryPrice(position.price_current.toFixed(2));
    }
  }, [orderType, isBuy, position.price_current]);

  const adjustVolume = (delta: number) => {
    const cur = parseFloat(volume) || 0.01;
    const next = Math.max(0.01, Math.round((cur + delta) * 100) / 100);
    setVolume(next.toFixed(2));
  };

  const handlePlacePyramid = async () => {
    setSubmitting(true);
    setResult(null);

    const vol = parseFloat(volume) || 0.01;
    let finalOrderType = 'Market';
    if (orderType === 'stop') {
      finalOrderType = isBuy ? 'Buy Stop' : 'Sell Stop';
    } else if (orderType === 'limit') {
      finalOrderType = isBuy ? 'Buy Limit' : 'Sell Limit';
    }

    const priceNum = orderType === 'market' ? 0.0 : (parseFloat(entryPrice) || position.price_current);
    const slNum = parseFloat(sl) || 0.0;

    const body = {
      symbol: position.symbol.replace(' ', '_'),
      action: isBuy ? 'Buy' : 'Sell',
      order_type: finalOrderType,
      volume: vol,
      price: priceNum,
      sl: slNum,
      tp: parentTp
    };

    try {
      const res = await fetch('http://127.0.0.1:8000/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = await res.json().catch(() => ({}));

      if (res.ok) {
        setResult({
          success: true,
          message: `Pyramid ${finalOrderType} placed! Ticket #${data.ticket}`,
          ticket: data.ticket
        });
        setTimeout(() => {
          onSuccess(data.ticket, data.comment);
          onClose();
        }, 1200);
      } else {
        setResult({
          success: false,
          message: data.detail || 'Failed to place MT5 pyramid order.'
        });
      }
    } catch (err: any) {
      setResult({
        success: false,
        message: err.message || 'Cannot reach MT5 backend.'
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '380px',
          backgroundColor: '#181b27',
          border: '1px solid #2962ff',
          borderRadius: '8px',
          boxShadow: '0 16px 40px rgba(0, 0, 0, 0.8)',
          padding: '16px',
          color: '#d1d4dc',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif',
          fontSize: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              backgroundColor: 'rgba(41, 98, 255, 0.2)',
              color: '#2962ff',
              padding: '4px 8px',
              borderRadius: '4px',
              fontWeight: 700,
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <Layers size={14} />
              <span>PYRAMID POSITION</span>
            </div>
            <span style={{ fontWeight: 600, color: '#fff' }}>{position.symbol}</span>
          </div>

          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#787b86', cursor: 'pointer', padding: '2px' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Parent Position Context Card */}
        <div style={{
          backgroundColor: '#131722',
          border: '1px solid #2a2e39',
          borderRadius: '6px',
          padding: '8px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#787b86' }}>Parent Trade Ticket:</span>
            <strong style={{ color: '#fff' }}>#{position.ticket}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#787b86' }}>Parent Type & Entry:</span>
            <span style={{ color: isBuy ? '#089981' : '#f23645', fontWeight: 600 }}>
              {position.type} {position.volume.toFixed(2)} @ {position.price_open.toFixed(2)}
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
            <span style={{ color: '#787b86' }}>Floating Profit:</span>
            <strong style={{ color: position.profit >= 0 ? '#089981' : '#f23645' }}>
              {position.profit >= 0 ? `+$${position.profit.toFixed(2)}` : `-$${Math.abs(position.profit).toFixed(2)}`}
            </strong>
          </div>
        </div>

        {/* Locked Take Profit Notice */}
        <div style={{
          backgroundColor: 'rgba(8, 153, 129, 0.12)',
          border: '1px solid #089981',
          borderRadius: '6px',
          padding: '8px 10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ color: '#089981', fontWeight: 700, fontSize: '11px' }}>
              🎯 SHARED TAKE PROFIT (LOCKED)
            </div>
            <div style={{ color: '#d1d4dc', fontSize: '10px' }}>
              Shares the exact same target as parent position #{position.ticket}
            </div>
          </div>
          <strong style={{ color: '#089981', fontSize: '13px' }}>
            {parentTp > 0 ? parentTp.toFixed(2) : 'Open / Unset'}
          </strong>
        </div>

        {/* Order Execution Type Tabs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#787b86' }}>
            <span>Pyramid Order Type</span>
            <span style={{ color: '#2962ff', fontWeight: 600 }}>
              {orderType === 'stop' ? (isBuy ? 'Buy Stop' : 'Sell Stop') : orderType === 'limit' ? (isBuy ? 'Buy Limit' : 'Sell Limit') : 'Instant Market'}
            </span>
          </div>
          <div style={{
            display: 'flex',
            backgroundColor: '#131722',
            borderRadius: '6px',
            padding: '3px',
            gap: '4px',
            border: '1px solid #2a2e39'
          }}>
            <button
              type="button"
              onClick={() => setOrderType('stop')}
              style={{
                flex: 1,
                padding: '6px 0',
                backgroundColor: orderType === 'stop' ? (isBuy ? '#089981' : '#f23645') : 'transparent',
                color: orderType === 'stop' ? '#fff' : '#b2b5be',
                border: 'none',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              🛑 {isBuy ? 'Buy Stop' : 'Sell Stop'}
            </button>
            <button
              type="button"
              onClick={() => setOrderType('market')}
              style={{
                flex: 1,
                padding: '6px 0',
                backgroundColor: orderType === 'market' ? 'var(--tv-accent)' : 'transparent',
                color: orderType === 'market' ? '#fff' : '#b2b5be',
                border: 'none',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              ⚡ Market
            </button>
            <button
              type="button"
              onClick={() => setOrderType('limit')}
              style={{
                flex: 1,
                padding: '6px 0',
                backgroundColor: orderType === 'limit' ? '#2962ff' : 'transparent',
                color: orderType === 'limit' ? '#fff' : '#b2b5be',
                border: 'none',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              🎯 {isBuy ? 'Buy Limit' : 'Sell Limit'}
            </button>
          </div>
        </div>

        {/* Volume Selector */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#787b86' }}>
            <span>Pyramid Volume</span>
            <span>Lots</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              type="button"
              onClick={() => adjustVolume(-0.01)}
              style={{
                width: '28px',
                height: '28px',
                background: '#2a2e39',
                border: 'none',
                borderRadius: '4px',
                color: '#fff',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              -
            </button>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={volume}
              onChange={(e) => setVolume(e.target.value)}
              style={{
                flex: 1,
                height: '28px',
                backgroundColor: '#131722',
                border: '1px solid #2a2e39',
                borderRadius: '4px',
                color: '#fff',
                textAlign: 'center',
                fontWeight: 600,
                fontSize: '12px'
              }}
            />
            <button
              type="button"
              onClick={() => adjustVolume(0.01)}
              style={{
                width: '28px',
                height: '28px',
                background: '#2a2e39',
                border: 'none',
                borderRadius: '4px',
                color: '#fff',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              +
            </button>
          </div>
          <div style={{ display: 'flex', gap: '4px', marginTop: '2px' }}>
            {['0.01', '0.02', '0.03', '0.05'].map(val => (
              <button
                key={val}
                type="button"
                onClick={() => setVolume(val)}
                style={{
                  flex: 1,
                  padding: '2px 0',
                  background: volume === val ? 'var(--tv-accent)' : '#2a2e39',
                  border: 'none',
                  borderRadius: '3px',
                  color: volume === val ? '#fff' : '#b2b5be',
                  fontSize: '10px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                {val}
              </button>
            ))}
          </div>
        </div>

        {/* Trigger Price (if Stop or Limit) */}
        {orderType !== 'market' && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: '#131722',
            border: '1px solid #2a2e39',
            borderRadius: '4px',
            padding: '6px 8px'
          }}>
            <div>
              <div style={{ color: '#fff', fontSize: '11px', fontWeight: 700 }}>
                {orderType === 'stop' ? (isBuy ? 'BUY STOP TRIGGER' : 'SELL STOP TRIGGER') : (isBuy ? 'BUY LIMIT PRICE' : 'SELL LIMIT PRICE')}
              </div>
              <div style={{ color: '#787b86', fontSize: '10px' }}>
                {orderType === 'stop' ? `Triggers when price ${isBuy ? 'rises to' : 'drops to'} level` : 'Fills on pullback bounce'}
              </div>
            </div>
            <input
              type="number"
              step="0.1"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fff',
                fontWeight: 700,
                fontSize: '13px',
                textAlign: 'right',
                width: '100px'
              }}
            />
          </div>
        )}

        {/* Stop Loss (SL) with Breakeven Quick Preset */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'rgba(242, 54, 69, 0.08)',
            border: '1px solid rgba(242, 54, 69, 0.3)',
            borderRadius: '4px',
            padding: '6px 8px'
          }}>
            <div>
              <div style={{ color: '#f23645', fontSize: '11px', fontWeight: 700 }}>STOP LOSS (SL)</div>
              <div style={{ color: '#787b86', fontSize: '10px' }}>Risk protection level</div>
            </div>
            <input
              type="number"
              step="0.1"
              value={sl}
              onChange={(e) => setSl(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#f23645',
                fontWeight: 700,
                fontSize: '13px',
                textAlign: 'right',
                width: '100px'
              }}
            />
          </div>
          {/* Quick Preset Buttons for SL */}
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              type="button"
              onClick={() => setSl(position.price_open.toFixed(2))}
              style={{
                flex: 1,
                padding: '3px 0',
                background: 'rgba(8, 153, 129, 0.15)',
                border: '1px solid #089981',
                borderRadius: '3px',
                color: '#089981',
                fontSize: '10px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '3px'
              }}
            >
              <ShieldCheck size={12} />
              <span>Breakeven ({position.price_open.toFixed(2)})</span>
            </button>
            {position.sl > 0 && (
              <button
                type="button"
                onClick={() => setSl(position.sl.toFixed(2))}
                style={{
                  flex: 1,
                  padding: '3px 0',
                  background: '#2a2e39',
                  border: 'none',
                  borderRadius: '3px',
                  color: '#b2b5be',
                  fontSize: '10px',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Same as Parent SL ({position.sl.toFixed(2)})
              </button>
            )}
          </div>
        </div>

        {/* Result Message */}
        {result && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px',
            borderRadius: '4px',
            backgroundColor: result.success ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)',
            border: `1px solid ${result.success ? '#089981' : '#f23645'}`,
            color: result.success ? '#089981' : '#f23645',
            fontSize: '11px'
          }}>
            {result.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span style={{ flex: 1, wordBreak: 'break-word' }}>{result.message}</span>
          </div>
        )}

        {/* Action Button */}
        <button
          type="button"
          onClick={handlePlacePyramid}
          disabled={submitting}
          style={{
            backgroundColor: isBuy ? '#089981' : '#f23645',
            color: '#fff',
            border: 'none',
            borderRadius: '5px',
            padding: '10px 0',
            fontWeight: 700,
            fontSize: '13px',
            cursor: submitting ? 'not-allowed' : 'pointer',
            opacity: submitting ? 0.7 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            marginTop: '4px'
          }}
        >
          {submitting ? (
            <>
              <Loader2 size={16} className="spin" />
              <span>Placing Pyramid on MT5...</span>
            </>
          ) : (
            <>
              {isBuy ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
              <span>
                Confirm Pyramid {isBuy ? 'BUY' : 'SELL'} ({volume} Lots, Same TP)
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
