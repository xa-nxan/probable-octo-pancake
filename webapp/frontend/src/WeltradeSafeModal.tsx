import { useState, useEffect } from 'react';
import { Shield, Key, ExternalLink, ArrowRightLeft, CheckCircle2, AlertCircle, Loader2, X, Lock, RefreshCw, DollarSign } from 'lucide-react';

interface WeltradeSafeModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeAccountLogin?: number;
  balance?: number;
  onTransferSuccess?: () => void;
}

export default function WeltradeSafeModal({
  isOpen,
  onClose,
  activeAccountLogin,
  balance = 0,
  onTransferSuccess
}: WeltradeSafeModalProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [amount, setAmount] = useState('1.00');
  const [fromAccount, setFromAccount] = useState(activeAccountLogin ? String(activeAccountLogin) : '34821009');
  
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<{
    logged_in: boolean;
    saved_email?: string;
    safe_balance?: string;
    error?: string;
  } | null>(null);

  const [savingCreds, setSavingCreds] = useState(false);
  const [credSavedMsg, setCredSavedMsg] = useState<string | null>(null);

  const [launchingBrowser, setLaunchingBrowser] = useState(false);
  const [transferring, setTransferring] = useState(false);
  const [transferResult, setTransferResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    if (activeAccountLogin) {
      setFromAccount(String(activeAccountLogin));
    }
  }, [activeAccountLogin]);

  const checkStatus = async () => {
    try {
      setLoadingStatus(true);
      const res = await fetch('http://127.0.0.1:8000/weltrade/status');
      const data = await res.json();
      setSessionStatus(data);
      if (data.saved_email && !email) {
        setEmail(data.saved_email);
      }
    } catch (e: any) {
      setSessionStatus({ logged_in: false, error: e.message });
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      checkStatus();
      setCredSavedMsg(null);
      setTransferResult(null);
    }
  }, [isOpen]);

  const handleSaveCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingCreds(true);
    setCredSavedMsg(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/weltrade/save_credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok) {
        setCredSavedMsg('Credentials saved securely on your PC! You will never need to re-enter them.');
        setPassword('');
        checkStatus();
      } else {
        alert(data.detail || 'Failed to save credentials.');
      }
    } catch (e: any) {
      alert(`Save error: ${e.message}`);
    } finally {
      setSavingCreds(false);
    }
  };

  const handleOpenBrowser = async () => {
    setLaunchingBrowser(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/weltrade/open_login', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Could not launch browser.');
      }
    } catch (e: any) {
      alert(`Launch error: ${e.message}`);
    } finally {
      setTimeout(() => setLaunchingBrowser(false), 2000);
    }
  };

  const handleTransferToSafe = async () => {
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) {
      alert('Please enter a valid transfer amount.');
      return;
    }
    setTransferring(true);
    setTransferResult(null);
    try {
      const res = await fetch('http://127.0.0.1:8000/weltrade/transfer_to_safe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          from_account: fromAccount,
          amount: amt
        })
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        setTransferResult({
          success: true,
          message: `Transferred $${amt.toFixed(2)} from #${fromAccount} to Weltrade Safe Box!`
        });
        onTransferSuccess?.();
      } else {
        setTransferResult({
          success: false,
          message: data.message || data.detail || 'Transfer failed or requires manual cabinet verification.'
        });
      }
    } catch (e: any) {
      setTransferResult({
        success: false,
        message: `Transfer error: ${e.message}`
      });
    } finally {
      setTransferring(false);
    }
  };

  if (!isOpen) return null;

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
        borderRadius: '10px',
        width: '540px',
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
          padding: '14px 18px',
          borderBottom: '1px solid #2a2e39',
          backgroundColor: '#131722'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              backgroundColor: 'rgba(8, 153, 129, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#089981'
            }}>
              <Shield size={18} />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px', color: '#fff' }}>Weltrade Safe Vault & Cabinet</div>
              <div style={{ fontSize: '11px', color: '#787b86' }}>Zero-fee profit vaulting & persistent session bridge</div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#787b86', cursor: 'pointer', padding: '4px' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '80vh', overflowY: 'auto' }}>
          
          {/* Status Banner */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 14px',
            borderRadius: '6px',
            backgroundColor: sessionStatus?.logged_in ? 'rgba(8, 153, 129, 0.12)' : 'rgba(255, 152, 0, 0.12)',
            border: `1px solid ${sessionStatus?.logged_in ? 'rgba(8, 153, 129, 0.35)' : 'rgba(255, 152, 0, 0.35)'}`
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: sessionStatus?.logged_in ? '#089981' : '#ff9800',
                boxShadow: sessionStatus?.logged_in ? '0 0 8px #089981' : '0 0 8px #ff9800'
              }} />
              <div>
                <div style={{ fontSize: '12px', fontWeight: 700, color: sessionStatus?.logged_in ? '#089981' : '#ff9800' }}>
                  {loadingStatus ? 'Checking Weltrade Session...' : sessionStatus?.logged_in ? 'Connected to Weltrade Cabinet' : 'Session Inactive / Setup Required'}
                </div>
                <div style={{ fontSize: '11px', color: '#787b86' }}>
                  {sessionStatus?.saved_email ? `Saved Profile: ${sessionStatus.saved_email}` : 'Profile stores cookies locally on your PC'}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                type="button"
                onClick={checkStatus}
                disabled={loadingStatus}
                style={{
                  background: '#2a2e39',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#d1d4dc',
                  padding: '4px 8px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px'
                }}
                title="Refresh session status"
              >
                <RefreshCw size={12} className={loadingStatus ? 'spin' : ''} />
                <span>Verify</span>
              </button>
              <button
                type="button"
                onClick={handleOpenBrowser}
                disabled={launchingBrowser}
                style={{
                  backgroundColor: '#2962ff',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#fff',
                  padding: '4px 10px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '11px',
                  fontWeight: 600
                }}
                title="Open persistent browser window to login or view cabinet"
              >
                <ExternalLink size={12} />
                <span>{launchingBrowser ? 'Opening...' : 'Open Cabinet'}</span>
              </button>
            </div>
          </div>

          {/* Transfer to Safe Box Card */}
          <div style={{
            backgroundColor: '#131722',
            border: '1px solid #2a2e39',
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fff', fontWeight: 700, fontSize: '13px' }}>
                <ArrowRightLeft size={16} color="#089981" />
                <span>Vault Funds to Safe Box</span>
              </div>
              <div style={{ fontSize: '11px', color: '#787b86' }}>
                Account Balance: <strong style={{ color: '#089981' }}>${balance.toFixed(2)}</strong>
              </div>
            </div>

            <div style={{ fontSize: '11px', color: '#787b86', lineHeight: 1.4 }}>
              Instantly secure your profits into your interest-bearing Weltrade Safe Box with zero fees. 
              Protected from market volatility while keeping your account risk-free.
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#787b86', marginBottom: '4px' }}>
                  Source MT5 Account
                </label>
                <input
                  type="text"
                  value={fromAccount}
                  onChange={(e) => setFromAccount(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#181b27',
                    border: '1px solid #2a2e39',
                    borderRadius: '4px',
                    padding: '6px 10px',
                    color: '#fff',
                    fontSize: '12px',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', color: '#787b86', marginBottom: '4px' }}>
                  Transfer Amount ($ USD)
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="number"
                    step="0.10"
                    min="0.10"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#181b27',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      padding: '6px 10px 6px 24px',
                      color: '#089981',
                      fontSize: '13px',
                      fontWeight: 700,
                      boxSizing: 'border-box'
                    }}
                  />
                  <DollarSign size={14} color="#787b86" style={{ position: 'absolute', left: '8px', top: '9px' }} />
                </div>
              </div>
            </div>

            {/* Quick Amount Chips */}
            <div style={{ display: 'flex', gap: '6px' }}>
              {[
                { label: '$1.00', val: '1.00' },
                { label: '$5.00', val: '5.00' },
                { label: '$10.00', val: '10.00' },
                { label: '50% Balance', val: (Math.max(0.1, balance * 0.5)).toFixed(2) },
                { label: 'All Profits', val: (Math.max(0.1, balance)).toFixed(2) }
              ].map(chip => (
                <button
                  key={chip.label}
                  type="button"
                  onClick={() => setAmount(chip.val)}
                  style={{
                    flex: 1,
                    backgroundColor: '#1e222d',
                    border: '1px solid #2a2e39',
                    borderRadius: '4px',
                    color: '#d1d4dc',
                    padding: '3px 0',
                    fontSize: '10px',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  {chip.label}
                </button>
              ))}
            </div>

            {/* Transfer Result Banner */}
            {transferResult && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                borderRadius: '4px',
                backgroundColor: transferResult.success ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)',
                border: `1px solid ${transferResult.success ? '#089981' : '#f23645'}`,
                color: transferResult.success ? '#089981' : '#f23645',
                fontSize: '11px'
              }}>
                {transferResult.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span>{transferResult.message}</span>
              </div>
            )}

            <button
              type="button"
              onClick={handleTransferToSafe}
              disabled={transferring}
              style={{
                backgroundColor: '#089981',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '9px 0',
                fontWeight: 700,
                fontSize: '12px',
                cursor: transferring ? 'not-allowed' : 'pointer',
                opacity: transferring ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
            >
              {transferring ? (
                <>
                  <Loader2 size={14} className="spin" />
                  <span>Transferring to Weltrade Safe Box...</span>
                </>
              ) : (
                <>
                  <Shield size={14} />
                  <span>Execute Vault Transfer (${amount})</span>
                </>
              )}
            </button>
          </div>

          {/* Save Credentials (Never Re-Enter Password) */}
          <div style={{
            backgroundColor: '#131722',
            border: '1px solid #2a2e39',
            borderRadius: '8px',
            padding: '14px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fff', fontWeight: 700, fontSize: '13px' }}>
              <Key size={15} color="#2962ff" />
              <span>Password Autofill & Persistent Session</span>
            </div>
            
            <div style={{ fontSize: '11px', color: '#787b86', lineHeight: 1.4 }}>
              Save your Weltrade email and password once. They are stored locally in your computer's encrypted workspace directory so you never have to re-enter your password again.
            </div>

            <form onSubmit={handleSaveCredentials} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#787b86', marginBottom: '3px' }}>
                    Weltrade Email
                  </label>
                  <input
                    type="email"
                    placeholder="user@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#181b27',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      padding: '6px 10px',
                      color: '#fff',
                      fontSize: '12px',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '11px', color: '#787b86', marginBottom: '3px' }}>
                    Password (Stored locally)
                  </label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={{
                      width: '100%',
                      backgroundColor: '#181b27',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      padding: '6px 10px',
                      color: '#fff',
                      fontSize: '12px',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>
              </div>

              {credSavedMsg && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: '#089981',
                  fontSize: '11px',
                  backgroundColor: 'rgba(8, 153, 129, 0.12)',
                  padding: '6px 10px',
                  borderRadius: '4px'
                }}>
                  <CheckCircle2 size={14} />
                  <span>{credSavedMsg}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={savingCreds}
                style={{
                  alignSelf: 'flex-start',
                  backgroundColor: '#2a2e39',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '6px 14px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Lock size={12} />
                <span>{savingCreds ? 'Saving...' : 'Save & Remember Credentials'}</span>
              </button>
            </form>
          </div>

        </div>

        {/* Footer */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '12px 18px',
          borderTop: '1px solid #2a2e39',
          backgroundColor: '#131722'
        }}>
          <button
            onClick={onClose}
            style={{
              backgroundColor: '#2a2e39',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 16px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
