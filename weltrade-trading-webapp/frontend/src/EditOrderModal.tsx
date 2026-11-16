import { useState } from 'react';
import { X, Check, Loader2 } from 'lucide-react';

interface EditOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  target: {
    kind: 'position' | 'pending';
    ticket: number;
    symbol: string;
    type: string;
    volume: number;
    price: number;
    sl: number;
    tp: number;
  } | null;
  onSuccess: () => void;
}

export default function EditOrderModal({
  isOpen,
  onClose,
  target,
  onSuccess
}: EditOrderModalProps) {
  if (!isOpen || !target) return null;

  const isPosition = target.kind === 'position';
  const [price, setPrice] = useState(target.price ? target.price.toFixed(2) : '0');
  const [sl, setSl] = useState(target.sl ? target.sl.toFixed(2) : '0');
  const [tp, setTp] = useState(target.tp ? target.tp.toFixed(2) : '0');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const slVal = parseFloat(sl) || 0;
    const tpVal = parseFloat(tp) || 0;
    const priceVal = parseFloat(price) || 0;

    try {
      if (isPosition) {
        const res = await fetch('http://127.0.0.1:8000/position/modify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket: target.ticket,
            sl: slVal,
            tp: tpVal
          })
        });
        const data = await res.json();
        if (res.ok) {
          onSuccess();
          onClose();
        } else {
          setError(data.detail || 'Failed to modify position SL/TP.');
        }
      } else {
        const res = await fetch('http://127.0.0.1:8000/order/modify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket: target.ticket,
            price: priceVal,
            sl: slVal,
            tp: tpVal
          })
        });
        const data = await res.json();
        if (res.ok) {
          onSuccess();
          onClose();
        } else {
          setError(data.detail || 'Failed to modify pending order.');
        }
      }
    } catch (e: any) {
      setError(`Network error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(3px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#181b27',
        border: '1px solid #2a2e39',
        borderRadius: '8px',
        width: '380px',
        maxWidth: '100%',
        boxShadow: '0 16px 48px rgba(0,0,0,0.8)',
        color: '#d1d4dc',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid #2a2e39',
          backgroundColor: '#131722'
        }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: '13px', color: '#fff' }}>
              {isPosition ? `Modify Position #${target.ticket}` : `Modify Pending Order #${target.ticket}`}
            </div>
            <div style={{ fontSize: '11px', color: '#787b86' }}>
              {target.symbol} · {target.type} · {target.volume} Lots
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#787b86', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {!isPosition && (
            <div>
              <label style={{ display: 'block', fontSize: '11px', color: '#787b86', marginBottom: '4px' }}>
                Trigger Price
              </label>
              <input
                type="number"
                step="0.01"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: '#131722',
                  border: '1px solid #2a2e39',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: '13px',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#f23645', marginBottom: '4px', fontWeight: 600 }}>
              Stop Loss (SL)
            </label>
            <input
              type="number"
              step="0.01"
              value={sl}
              onChange={(e) => setSl(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'rgba(242, 54, 69, 0.08)',
                border: '1px solid rgba(242, 54, 69, 0.4)',
                borderRadius: '4px',
                padding: '6px 10px',
                color: '#f23645',
                fontWeight: 600,
                fontSize: '13px',
                boxSizing: 'border-box'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '11px', color: '#089981', marginBottom: '4px', fontWeight: 600 }}>
              Take Profit (TP)
            </label>
            <input
              type="number"
              step="0.01"
              value={tp}
              onChange={(e) => setTp(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'rgba(8, 153, 129, 0.08)',
                border: '1px solid rgba(8, 153, 129, 0.4)',
                borderRadius: '4px',
                padding: '6px 10px',
                color: '#089981',
                fontWeight: 600,
                fontSize: '13px',
                boxSizing: 'border-box'
              }}
            />
          </div>

          {error && (
            <div style={{
              color: '#f23645',
              fontSize: '11px',
              backgroundColor: 'rgba(242, 54, 69, 0.15)',
              padding: '6px 10px',
              borderRadius: '4px'
            }}>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1,
                backgroundColor: '#2a2e39',
                color: '#d1d4dc',
                border: 'none',
                borderRadius: '4px',
                padding: '8px 0',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                flex: 1,
                backgroundColor: 'var(--tv-accent)',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                padding: '8px 0',
                fontSize: '12px',
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px'
              }}
            >
              {loading ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
              <span>{loading ? 'Updating...' : 'Save Changes'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
