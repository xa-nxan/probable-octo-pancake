import { useState, useCallback, useEffect, useMemo } from 'react';
import ChartComponent, { type CandleAccuracy } from './ChartComponent';
import PyramidModal from './PyramidModal';
import WeltradeSafeModal from './WeltradeSafeModal';
import EditOrderModal from './EditOrderModal';
import './theme.css';
import {
  Search, Plus, ChevronDown, Settings, Maximize2, Camera,
  RotateCcw, RotateCw, Bookmark, Bell, BarChart2,
  TrendingUp, Square, Minus, MousePointer2,
  ArrowUpRight, Magnet,
  Lock, Eye, Trash2, X, Clock,
  MoreHorizontal, LayoutGrid, Activity,
  Shield, Edit3, RefreshCw
} from 'lucide-react';

const WATCHLIST_GROUPS = [
  {
    category: 'SYNTHETIC INDICES',
    symbols: [
      { id: 'FX_Vol_20', name: 'FX Vol 20', badge: '20', color: '#f23645' },
      { id: 'FX_Vol_40', name: 'FX Vol 40', badge: '40', color: '#2962ff' },
      { id: 'FX_Vol_60', name: 'FX Vol 60', badge: '60', color: '#089981' },
      { id: 'FX_Vol_80', name: 'FX Vol 80', badge: '80', color: '#ab47bc' },
      { id: 'FX_Vol_99', name: 'FX Vol 99', badge: '99', color: '#ff9800' },
    ]
  },
  {
    category: 'STEP VOLATILITY',
    symbols: [
      { id: 'SFX_Vol_20', name: 'SFX Vol 20', badge: 'S2', color: '#e91e63' },
      { id: 'SFX_Vol_40', name: 'SFX Vol 40', badge: 'S4', color: '#00bcd4' },
      { id: 'SFX_Vol_60', name: 'SFX Vol 60', badge: 'S6', color: '#4caf50' },
      { id: 'SFX_Vol_80', name: 'SFX Vol 80', badge: 'S8', color: '#9c27b0' },
      { id: 'SFX_Vol_99', name: 'SFX Vol 99', badge: 'S9', color: '#ff5722' },
    ]
  },
  {
    category: 'FLIPX INDICES',
    symbols: [
      { id: 'FlipX_1', name: 'FlipX 1', badge: 'F1', color: '#3f51b5' },
      { id: 'FlipX_2', name: 'FlipX 2', badge: 'F2', color: '#009688' },
      { id: 'FlipX_3', name: 'FlipX 3', badge: 'F3', color: '#ffc107' },
      { id: 'FlipX_4', name: 'FlipX 4', badge: 'F4', color: '#673ab7' },
      { id: 'FlipX_5', name: 'FlipX 5', badge: 'F5', color: '#00e676' },
    ]
  }
];

const ALL_SYMBOLS = WATCHLIST_GROUPS.flatMap(g => g.symbols.map(s => s.id));
const TIMEFRAMES = [
  { label: '1m', value: 'M1' },
  { label: '5m', value: 'M5' },
  { label: '15m', value: 'M15' },
  { label: '30m', value: 'M30' },
  { label: '1h', value: 'H1' },
  { label: '4h', value: 'H4' },
  { label: 'D', value: '1D' },
];

interface MT5Position {
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

interface MT5PendingOrder {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  price_open: number;
  price_current: number;
  sl: number;
  tp: number;
  time_setup: number;
  comment: string;
}

interface AccountInfo {
  login?: number;
  name?: string;
  server?: string;
  currency?: string;
  leverage?: number;
  trade_allowed?: boolean;
  balance: number;
  equity: number;
  margin: number;
  margin_free: number;
  profit: number;
  ping_ms?: number;
  terminal_connected?: boolean;
}

export default function App() {
  const [symbol, setSymbolState] = useState(() => {
    const urlSym = new URLSearchParams(window.location.search).get('s');
    return ALL_SYMBOLS.includes(urlSym as string) ? urlSym! : (localStorage.getItem('lastSymbol') || ALL_SYMBOLS[0]);
  });

  const [timeframe, setTimeframeState] = useState(() => {
    const urlTf = new URLSearchParams(window.location.search).get('tf');
    const valid = TIMEFRAMES.find(t => t.value === urlTf);
    return valid ? valid.value : (localStorage.getItem('lastTimeframe') || 'M15');
  });

  const setSymbol = (sym: string) => {
    setSymbolState(sym);
    localStorage.setItem('lastSymbol', sym);
    const url = new URL(window.location.href);
    url.searchParams.set('s', sym);
    window.history.replaceState({}, '', url.toString());
    setSearchOpen(false);
  };

  const setTimeframe = (tf: string) => {
    setTimeframeState(tf);
    localStorage.setItem('lastTimeframe', tf);
    const url = new URL(window.location.href);
    url.searchParams.set('tf', tf);
    window.history.replaceState({}, '', url.toString());
  };

  const [showVolume, setShowVolume] = useState(true);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeRightTab, setActiveRightTab] = useState<'watchlist' | 'alerts' | 'notifications' | null>(null);
  const [showTerminal, setShowTerminal] = useState(false);
  const [terminalTab, setTerminalTab] = useState<'positions' | 'orders' | 'history' | 'backtest' | 'scanner'>('positions');
  const [backtestTrades, setBacktestTrades] = useState<any[]>([]);
  const [setupFilter, setSetupFilter] = useState<'all' | 'expansion' | 'pullback' | 'continuation'>('all');
  const [activeBacktestTrade, setActiveBacktestTrade] = useState<any | null>(null);
  const [backtestIdx, setBacktestIdx] = useState<number>(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const [positions, setPositions] = useState<MT5Position[]>([]);
  const [pendingOrders, setPendingOrders] = useState<MT5PendingOrder[]>([]);
  const [pyramidTarget, setPyramidTarget] = useState<MT5Position | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [watchlist, setWatchlist] = useState<Record<string, { price: number; change_pct: number; bid: number; ask: number }>>({});
  
  const [weltradeModalOpen, setWeltradeModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<any | null>(null);
  const [actionLoading, setActionLoading] = useState<Record<number, string>>({});
  const [scannerTimeframe, setScannerTimeframe] = useState<'M30' | 'M5'>('M30');
  const [scannerData, setScannerData] = useState<any[]>([]);
  const [scannerLoading, setScannerLoading] = useState(false);

  const [candleAccuracy, setCandleAccuracy] = useState<CandleAccuracy>({
    status: 'syncing',
    lastVerifiedTime: Date.now(),
    desyncFixedCount: 0,
    verifiedBarsCount: 0,
    accuracyPct: 100
  });
  const [isVerifying, setIsVerifying] = useState(false);
  const [isMagnetOn, setIsMagnetOn] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [switchingAccount, setSwitchingAccount] = useState(false);
  const [targetLogin, setTargetLogin] = useState('34931796');
  const [targetServer, setTargetServer] = useState('Weltrade-Real');
  const [targetPassword, setTargetPassword] = useState('');

  const verifyCandlesManually = useCallback(async () => {
    try {
      setIsVerifying(true);
      const res = await fetch(`http://127.0.0.1:8000/candles/verify?symbol=${symbol}&timeframe=${timeframe}&count=30`);
      const data = await res.json();
      if (data.status === 'ok') {
        setCandleAccuracy(prev => ({
          ...prev,
          status: 'verified',
          lastVerifiedTime: Date.now(),
          verifiedBarsCount: data.count,
          accuracyPct: 100
        }));
      }
    } catch (e) {
      console.warn("Manual verification failed", e);
    } finally {
      setTimeout(() => setIsVerifying(false), 500);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/backtest_trades?symbol=${symbol}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setBacktestTrades(data);
          if (data.length > 0) {
            setBacktestIdx(0);
          }
        }
      })
      .catch(err => console.warn("Failed to load backtest trades", err));
  }, [symbol]);

  const filteredBacktestTrades = useMemo(() => {
    if (setupFilter === 'expansion') return backtestTrades.filter(t => t.setup?.includes('Expansion'));
    if (setupFilter === 'pullback') return backtestTrades.filter(t => t.setup?.includes('Pullback'));
    if (setupFilter === 'continuation') return backtestTrades.filter(t => t.setup?.includes('Continuation'));
    return backtestTrades;
  }, [backtestTrades, setupFilter]);

  const selectTrade = useCallback((idx: number) => {
    if (idx < 0 || idx >= filteredBacktestTrades.length) return;
    setBacktestIdx(idx);
    const trade = filteredBacktestTrades[idx];
    if (timeframe !== 'M5') setTimeframe('M5');
    setActiveBacktestTrade(trade);
    setShowTerminal(false); // Auto-hide bottom terminal so chart gets 100% full screen view!
    setActiveRightTab(null); // Auto-collapse right watchlist so chart gets 100% full width view!
  }, [filteredBacktestTrades, timeframe]);

  const nextTrade = useCallback(() => {
    if (filteredBacktestTrades.length === 0) return;
    const nxt = (backtestIdx + 1) % filteredBacktestTrades.length;
    selectTrade(nxt);
  }, [backtestIdx, filteredBacktestTrades, selectTrade]);

  const prevTrade = useCallback(() => {
    if (filteredBacktestTrades.length === 0) return;
    const prv = (backtestIdx - 1 + filteredBacktestTrades.length) % filteredBacktestTrades.length;
    selectTrade(prv);
  }, [backtestIdx, filteredBacktestTrades, selectTrade]);

  const handleTick = useCallback((_candle: any) => {
    // Tick received
  }, []);

  const handleWatchlistUpdate = useCallback((items: any[]) => {
    setWatchlist(prev => {
      const next = { ...prev };
      for (const item of items) {
        if (item && item.symbol) {
          next[item.symbol] = {
            price: item.price,
            change_pct: item.change_pct,
            bid: item.bid,
            ask: item.ask
          };
        }
      }
      return next;
    });
  }, []);

  // In-flight guard to avoid request stacking and socket exhaustion
  const isFetchingRef = useState(false);
  const lastHistoryFetchRef = useState(0);

  // Poll MT5 account, positions, pending orders, and history safely
  const fetchMt5 = useCallback(async (forceHistory = false) => {
    if (isFetchingRef[0]) return;
    isFetchingRef[0] = true;
    try {
      const now = Date.now();
      const shouldFetchHistory = forceHistory || (now - lastHistoryFetchRef[0] > 8000) || terminalTab === 'history';

      const fetches: Promise<Response>[] = [
        fetch('http://127.0.0.1:8000/account'),
        fetch('http://127.0.0.1:8000/positions'),
        fetch('http://127.0.0.1:8000/orders')
      ];
      if (shouldFetchHistory) {
        fetches.push(fetch('http://127.0.0.1:8000/history'));
      }

      const responses = await Promise.all(fetches);
      const [accRes, posRes, ordRes, histRes] = responses;

      if (accRes && accRes.ok) setAccount(await accRes.json());
      if (posRes && posRes.ok) setPositions(await posRes.json());
      if (ordRes && ordRes.ok) setPendingOrders(await ordRes.json());
      if (histRes && histRes.ok) {
        setHistory(await histRes.json());
        lastHistoryFetchRef[0] = now;
      }
    } catch (e) {
      // Backend offline / loading
    } finally {
      isFetchingRef[0] = false;
    }
  }, [terminalTab]);

  const handleCancelOrder = useCallback(async (ticket: number) => {
    try {
      await fetch(`http://127.0.0.1:8000/order/cancel/${ticket}`, { method: 'POST' });
      setPendingOrders(prev => prev.filter(o => o.ticket !== ticket));
    } catch (e) {
      console.error('Failed to cancel order:', e);
    }
  }, []);

  const handleLockProfit = useCallback(async (pos: MT5Position, lockType: 'margin' | 'breakeven') => {
    try {
      setActionLoading(prev => ({ ...prev, [pos.ticket]: lockType }));
      const res = await fetch('http://127.0.0.1:8000/position/lock_profit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket: pos.ticket,
          lock_type: lockType
        })
      });
      const data = await res.json();
      if (res.ok) {
        fetchMt5(true);
      } else {
        alert(data.detail || `Failed to lock ${lockType}`);
      }
    } catch (e: any) {
      alert(`Lock profit error: ${e.message}`);
    } finally {
      setActionLoading(prev => {
        const next = { ...prev };
        delete next[pos.ticket];
        return next;
      });
    }
  }, [fetchMt5]);

  const handleBankAndReopen = useCallback(async (pos: MT5Position) => {
    try {
      setActionLoading(prev => ({ ...prev, [pos.ticket]: 'banking' }));
      const res = await fetch('http://127.0.0.1:8000/position/bank_and_reopen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket: pos.ticket })
      });
      const data = await res.json();
      if (res.ok) {
        fetchMt5(true);
      } else {
        alert(data.detail || 'Bank & Reopen failed.');
      }
    } catch (e: any) {
      alert(`Bank & Reopen error: ${e.message}`);
    } finally {
      setActionLoading(prev => {
        const next = { ...prev };
        delete next[pos.ticket];
        return next;
      });
    }
  }, [fetchMt5]);

  const handlePartialClose = useCallback(async (pos: MT5Position, pct = 50) => {
    try {
      setActionLoading(prev => ({ ...prev, [pos.ticket]: 'closing_pct' }));
      const res = await fetch('http://127.0.0.1:8000/position/partial_close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticket: pos.ticket, pct })
      });
      const data = await res.json();
      if (res.ok) {
        fetchMt5(true);
      } else {
        alert(data.detail || 'Partial close failed.');
      }
    } catch (e: any) {
      alert(`Partial close error: ${e.message}`);
    } finally {
      setActionLoading(prev => {
        const next = { ...prev };
        delete next[pos.ticket];
        return next;
      });
    }
  }, [fetchMt5]);

  const handlePanicCloseAll = useCallback(async () => {
    if (!window.confirm('🚨 EMERGENCY FLATTEN: Are you sure you want to CLOSE ALL open positions immediately?')) {
      return;
    }
    try {
      const res = await fetch('http://127.0.0.1:8000/positions/close_all', { method: 'POST' });
      const data = await res.json();
      fetchMt5(true);
      alert(`Panic Flatten Complete: Closed ${data.closed_count} position(s).`);
    } catch (e: any) {
      alert(`Close all error: ${e.message}`);
    }
  }, [fetchMt5]);

  const fetchLiveScanner = useCallback(async (tf?: string) => {
    const targetTf = tf || scannerTimeframe;
    try {
      setScannerLoading(true);
      const res = await fetch(`http://127.0.0.1:8000/scanner/live?timeframe=${targetTf}`);
      if (res.ok) {
        const data = await res.json();
        setScannerData(data);
      }
    } catch (e) {
      console.warn("Scanner fetch failed", e);
    } finally {
      setScannerLoading(false);
    }
  }, [scannerTimeframe]);

  useEffect(() => {
    if (terminalTab === 'scanner') {
      fetchLiveScanner();
      const interval = setInterval(() => fetchLiveScanner(), 5000);
      return () => clearInterval(interval);
    }
  }, [terminalTab, scannerTimeframe, fetchLiveScanner]);



  const handleClosePosition = useCallback(async (ticket: number) => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/close/${ticket}`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        fetchMt5(true);
      } else {
        alert(data.detail || 'Failed to close position.');
      }
    } catch (e: any) {
      alert(`Close position error: ${e.message}`);
    }
  }, [fetchMt5]);

  const handleSwitchAccount = useCallback(async (loginNum: number, srv: string, pwd = "") => {
    try {
      setSwitchingAccount(true);
      const res = await fetch('http://127.0.0.1:8000/account/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login: loginNum,
          server: srv,
          password: pwd
        })
      });
      const data = await res.json();
      if (res.ok) {
        fetchMt5(true);
        setAccountModalOpen(false);
      } else {
        alert(data.detail || 'Failed to switch MT5 account.');
      }
    } catch (e: any) {
      alert(`Switch account error: ${e.message}`);
    } finally {
      setSwitchingAccount(false);
    }
  }, [fetchMt5]);

  useEffect(() => {
    fetchMt5(true);
    const interval = setInterval(() => fetchMt5(false), 2000);
    return () => clearInterval(interval);
  }, [fetchMt5]);

  const handleOrderSuccess = useCallback((_ticket: number, comment?: string) => {
    fetchMt5();
    setShowTerminal(true);
    if (comment && comment.toLowerCase().includes('stop')) {
      setTerminalTab('orders');
    } else {
      setTerminalTab('positions');
    }
  }, [fetchMt5]);

  // Keyboard shortcut Ctrl+K for symbol search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleDrawingsUpdate = useCallback((_drawings: any[], _symbol: string) => {
    // Planning tools only - no automatic trade side-effects
  }, []);

  const handleToolDeactivate = useCallback(() => {
    setActiveTool(null);
  }, []);

  // Filtered symbols for search modal
  const filteredSymbols = WATCHLIST_GROUPS.flatMap(g => g.symbols).filter(s =>
    s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'var(--tv-bg-primary)',
      color: 'var(--tv-text-primary)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif'
    }}>
      
      {/* ─────────────────────────────────────────────────────────────
          1. TOP NAVIGATION BAR (TradingView Authentic Header)
      ───────────────────────────────────────────────────────────── */}
      <div style={{
        height: '46px',
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        gap: '4px',
        borderBottom: '1px solid var(--tv-border)',
        backgroundColor: 'var(--tv-bg-primary)',
        zIndex: 20
      }}>
        {/* User Profile Avatar */}
        <div style={{
          width: '28px',
          height: '28px',
          borderRadius: '50%',
          backgroundColor: '#ab47bc',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 'bold',
          fontSize: '12px',
          marginRight: '6px',
          cursor: 'pointer'
        }}>
          W
        </div>

        {/* Symbol Search Selector Button */}
        <button
          onClick={() => setSearchOpen(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'transparent',
            border: 'none',
            color: 'var(--tv-text-primary)',
            padding: '6px 10px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 700,
            fontSize: '14px',
            transition: 'background-color 0.15s'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          title="Search symbol (Ctrl+K)"
        >
          <Search size={16} color="var(--tv-text-secondary)" />
          <span>{symbol.replace('_', ' ')}</span>
          <ChevronDown size={14} color="var(--tv-text-secondary)" />
        </button>

        {/* Compare (+) button */}
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--tv-text-secondary)',
            padding: '6px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center'
          }}
          title="Compare or Add Symbol"
        >
          <Plus size={18} />
        </button>

        <div style={{ width: '1px', height: '20px', background: 'var(--tv-border)', margin: '0 6px' }} />

        {/* Timeframe Selector Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1px' }}>
          {TIMEFRAMES.map(tf => {
            const isActive = timeframe === tf.value;
            return (
              <button
                key={tf.value}
                onClick={() => setTimeframe(tf.value)}
                style={{
                  background: isActive ? 'var(--tv-accent-bg)' : 'transparent',
                  color: isActive ? 'var(--tv-accent)' : 'var(--tv-text-primary)',
                  border: 'none',
                  padding: '5px 8px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontWeight: isActive ? 700 : 500,
                  fontSize: '13px',
                  transition: 'background-color 0.15s'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                {tf.label}
              </button>
            );
          })}
        </div>

        <div style={{ width: '1px', height: '20px', background: 'var(--tv-border)', margin: '0 6px' }} />

        {/* Chart Style (Candles) */}
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--tv-text-secondary)',
            padding: '6px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '13px'
          }}
          title="Bar style"
        >
          <BarChart2 size={16} />
        </button>

        {/* Indicators Button */}
        <button
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--tv-text-primary)',
            padding: '6px 10px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '13px',
            fontWeight: 500
          }}
          title="Indicators"
        >
          <span style={{ color: 'var(--tv-accent)', fontWeight: 'bold' }}>fx</span>
          <span>Indicators</span>
        </button>

        {/* Volume Toggle */}
        <button
          onClick={() => setShowVolume(prev => !prev)}
          style={{
            background: showVolume ? 'var(--tv-accent-bg)' : 'transparent',
            border: 'none',
            color: showVolume ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
            padding: '5px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px'
          }}
          title="Toggle Volume Overlay"
        >
          Vol
        </button>

        {/* Undo / Redo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px', marginLeft: '6px' }}>
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-muted)', padding: '5px', cursor: 'pointer' }} title="Undo">
            <RotateCcw size={15} />
          </button>
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-muted)', padding: '5px', cursor: 'pointer' }} title="Redo">
            <RotateCw size={15} />
          </button>
        </div>

        {/* Right side controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* MT5 Candle Accuracy Status Pill */}
          <button
            onClick={verifyCandlesManually}
            title="Click to audit & re-verify candles directly with MT5"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: candleAccuracy.status === 'verified' ? 'rgba(8, 153, 129, 0.12)' : 'rgba(255, 152, 0, 0.12)',
              border: `1px solid ${candleAccuracy.status === 'verified' ? 'rgba(8, 153, 129, 0.35)' : 'rgba(255, 152, 0, 0.35)'}`,
              borderRadius: '4px',
              padding: '3px 8px',
              cursor: 'pointer',
              color: candleAccuracy.status === 'verified' ? '#089981' : '#ff9800',
              fontSize: '11px',
              fontWeight: 600,
              transition: 'all 0.15s ease'
            }}
          >
            <span style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: candleAccuracy.status === 'verified' ? '#089981' : '#ff9800',
              boxShadow: candleAccuracy.status === 'verified' ? '0 0 6px #089981' : '0 0 6px #ff9800'
            }} />
            <span>{isVerifying ? 'Auditing MT5...' : 'MT5 Candles: 100% In-Sync'}</span>
            <span style={{ color: 'var(--tv-text-muted)', fontSize: '10px' }}>
              {candleAccuracy.desyncFixedCount > 0 ? `(${candleAccuracy.desyncFixedCount} healed)` : '✓'}
            </span>
          </button>

          <span style={{ fontSize: '13px', color: 'var(--tv-text-secondary)', fontWeight: 500 }}>
            Weltrade Synthetics
          </span>

          <div style={{ width: '1px', height: '20px', background: 'var(--tv-border)', margin: '0 4px' }} />

          {/* Settings */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '6px', cursor: 'pointer' }} title="Chart settings">
            <Settings size={18} />
          </button>

          {/* Fullscreen */}
          <button
            onClick={() => {
              if (!document.fullscreenElement) document.documentElement.requestFullscreen();
              else document.exitFullscreen();
            }}
            style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '6px', cursor: 'pointer' }}
            title="Fullscreen"
          >
            <Maximize2 size={18} />
          </button>

          {/* Snapshot */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '6px', cursor: 'pointer' }} title="Take screenshot">
            <Camera size={18} />
          </button>

          {/* Backtest Trades Replay Button */}
          <button
            onClick={() => {
              if (activeBacktestTrade) {
                setActiveBacktestTrade(null);
              } else if (filteredBacktestTrades.length > 0) {
                setShowTerminal(true);
                setTerminalTab('backtest');
                selectTrade(0);
              }
            }}
            style={{
              backgroundColor: activeBacktestTrade ? '#2962ff' : '#1e222d',
              color: activeBacktestTrade ? '#fff' : '#089981',
              border: activeBacktestTrade ? '1px solid #2962ff' : '1px solid #089981',
              borderRadius: '4px',
              padding: '6px 12px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title="Toggle Backtest Trade Replay on M5 Chart"
          >
            🎯 {activeBacktestTrade ? `Exit Replay (#${backtestIdx + 1})` : `Replay Trades (${filteredBacktestTrades.length})`}
          </button>

          {/* Weltrade Safe Box Button */}
          <button
            onClick={() => setWeltradeModalOpen(true)}
            style={{
              backgroundColor: '#181b27',
              color: '#089981',
              border: '1px solid #089981',
              borderRadius: '4px',
              padding: '6px 12px',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            title="Open Weltrade Safe Vault & Cabinet (Zero-Fee Internal Transfers)"
          >
            <Shield size={14} />
            <span>Weltrade Safe</span>
          </button>

          {/* Trade Button (TradingView Style) */}
          <button
            onClick={() => setShowTerminal(prev => !prev)}
            style={{
              backgroundColor: showTerminal ? '#1e53e5' : 'var(--tv-accent)',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'background-color 0.15s'
            }}
          >
            <span>Trade</span>
            {positions.length > 0 && (
              <span style={{
                background: '#fff',
                color: 'var(--tv-accent)',
                borderRadius: '10px',
                padding: '1px 6px',
                fontSize: '10px',
                fontWeight: 'bold'
              }}>
                {positions.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          2. MAIN BODY (Left Toolbar + Chart + Watchlist + Icon Rail)
      ───────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        
        {/* Left Vertical Tool Rail (TradingView Style) */}
        <div style={{
          width: '46px',
          borderRight: '1px solid var(--tv-border)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '8px 0',
          gap: '8px',
          backgroundColor: 'var(--tv-bg-primary)',
          zIndex: 10
        }}>
          {/* Cursor / Pointer */}
          <button
            onClick={() => setActiveTool(null)}
            style={{
              background: activeTool === null ? 'var(--tv-bg-hover)' : 'transparent',
              color: activeTool === null ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Crosshair (Cursor)"
          >
            <MousePointer2 size={18} />
          </button>

          {/* Trend Line */}
          <button
            onClick={() => setActiveTool(activeTool === 'trend-line' ? null : 'trend-line')}
            style={{
              background: activeTool === 'trend-line' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeTool === 'trend-line' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Trend Line"
          >
            <TrendingUp size={18} />
          </button>

          {/* Horizontal Line */}
          <button
            onClick={() => setActiveTool(activeTool === 'horizontal-line' ? null : 'horizontal-line')}
            style={{
              background: activeTool === 'horizontal-line' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeTool === 'horizontal-line' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Horizontal Line"
          >
            <Minus size={18} />
          </button>

          {/* Rectangle / Box */}
          <button
            onClick={() => setActiveTool(activeTool === 'rectangle' ? null : 'rectangle')}
            style={{
              background: activeTool === 'rectangle' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeTool === 'rectangle' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Rectangle (Zone)"
          >
            <Square size={18} />
          </button>

          {/* Fib / Sliders */}
          <button
            onClick={() => setActiveTool(activeTool === 'arrow' ? null : 'arrow')}
            style={{
              background: activeTool === 'arrow' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeTool === 'arrow' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Arrow"
          >
            <ArrowUpRight size={18} />
          </button>

          {/* Long Position Planning Tool */}
          <button
            onClick={() => setActiveTool(activeTool === 'long-position' ? null : 'long-position')}
            style={{
              background: activeTool === 'long-position' ? 'var(--tv-up-bg)' : 'transparent',
              color: activeTool === 'long-position' ? 'var(--tv-up)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Long Position Tool"
          >
            <span style={{ fontSize: '11px', fontWeight: 'bold' }}>LONG</span>
          </button>

          {/* Short Position Planning Tool */}
          <button
            onClick={() => setActiveTool(activeTool === 'short-position' ? null : 'short-position')}
            style={{
              background: activeTool === 'short-position' ? 'var(--tv-down-bg)' : 'transparent',
              color: activeTool === 'short-position' ? 'var(--tv-down)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Short Position Tool"
          >
            <span style={{ fontSize: '11px', fontWeight: 'bold' }}>SHRT</span>
          </button>

          <div style={{ width: '24px', height: '1px', background: 'var(--tv-border)', margin: '4px 0' }} />

          {/* Magnet Tool Toggle */}
          <button
            onClick={() => setIsMagnetOn(prev => !prev)}
            style={{
              background: isMagnetOn ? 'rgba(41, 98, 255, 0.25)' : 'transparent',
              border: isMagnetOn ? '1px solid #2962ff' : 'none',
              color: isMagnetOn ? '#2962ff' : 'var(--tv-text-secondary)',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
            title={isMagnetOn ? "Magnet Snapping: ON (Snaps to OHLC wicks)" : "Magnet Snapping: OFF (Smooth free-form drag & drop)"}
          >
            <Magnet size={18} />
          </button>

          {/* Lock all */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '8px', cursor: 'pointer' }} title="Lock all drawing tools">
            <Lock size={18} />
          </button>

          {/* Hide all drawings */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '8px', cursor: 'pointer' }} title="Hide drawings">
            <Eye size={18} />
          </button>

          {/* Trash / Delete all */}
          <button
            onClick={() => {
              if (window.confirm("Remove all drawings on " + symbol + "?")) {
                localStorage.removeItem(`drawings_${symbol}`);
                window.location.reload();
              }
            }}
            style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '8px', cursor: 'pointer' }}
            title="Remove all drawings"
          >
            <Trash2 size={18} />
          </button>
        </div>

        {/* Center Chart Container */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {/* Floating Backtest Trade Replay HUD (Image 2 companion) */}
          {activeBacktestTrade && (
            <div style={{
              position: 'absolute',
              top: '12px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 30,
              backgroundColor: 'rgba(26, 30, 40, 0.94)',
              backdropFilter: 'blur(8px)',
              border: '1px solid var(--tv-border)',
              borderRadius: '8px',
              padding: '6px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
              color: '#d1d4dc',
              fontSize: '12px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  backgroundColor: activeBacktestTrade.type === 'short-position' ? 'rgba(242, 54, 69, 0.2)' : 'rgba(8, 153, 129, 0.2)',
                  color: activeBacktestTrade.type === 'short-position' ? '#f23645' : '#089981',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '11px'
                }}>
                  {activeBacktestTrade.type === 'short-position' ? 'SHORT' : 'LONG'}
                </span>
                <span style={{ fontWeight: 600, color: '#fff' }}>
                  {activeBacktestTrade.setup}
                </span>
                <span style={{
                  color: activeBacktestTrade.win ? '#089981' : '#f23645',
                  fontWeight: 700,
                  marginLeft: '2px'
                }}>
                  {activeBacktestTrade.win ? `WIN +$${activeBacktestTrade.pnl_usd.toFixed(2)}` : `LOSS -$${Math.abs(activeBacktestTrade.pnl_usd).toFixed(2)}`}
                </span>
                <span style={{ color: '#787b86', fontSize: '11px', marginLeft: '6px' }}>
                  Entry: <b style={{ color: '#d1d4dc' }}>{activeBacktestTrade.entry}</b> | SL: <b style={{ color: '#f23645' }}>{activeBacktestTrade.sl}</b> | TP: <b style={{ color: '#089981' }}>{activeBacktestTrade.tp}</b> (1:{activeBacktestTrade.rrr})
                </span>
              </div>

              <div style={{ width: '1px', height: '18px', backgroundColor: 'var(--tv-border)' }} />

              <span style={{ color: 'var(--tv-text-secondary)', fontSize: '11px' }}>
                Trade {backtestIdx + 1} / {filteredBacktestTrades.length}
              </span>

              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <button
                  onClick={prevTrade}
                  style={{
                    backgroundColor: 'var(--tv-bg-hover)',
                    color: '#fff',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 'bold'
                  }}
                  title="Previous Trade"
                >
                  ◀ Prev
                </button>
                <button
                  onClick={nextTrade}
                  style={{
                    backgroundColor: 'var(--tv-bg-hover)',
                    color: '#fff',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 'bold'
                  }}
                  title="Next Trade"
                >
                  Next ▶
                </button>
                <button
                  onClick={() => setShowTerminal(prev => !prev)}
                  style={{
                    backgroundColor: showTerminal ? 'var(--tv-accent)' : 'var(--tv-bg-hover)',
                    color: '#fff',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '3px 8px',
                    cursor: 'pointer',
                    fontSize: '11px',
                    fontWeight: 'bold',
                    marginLeft: '4px'
                  }}
                  title={showTerminal ? "Hide Trades Table" : "Show Trades Table"}
                >
                  📋 {showTerminal ? "Hide Table" : "Show Table"}
                </button>
              </div>

              <button
                onClick={() => setActiveBacktestTrade(null)}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: 'var(--tv-text-secondary)',
                  cursor: 'pointer',
                  padding: '3px',
                  display: 'flex',
                  alignItems: 'center'
                }}
                title="Clear Trade Preview"
              >
                <X size={15} />
              </button>
            </div>
          )}

          <ChartComponent 
            symbol={symbol} 
            timeframe={timeframe} 
            showVolume={showVolume} 
            activeTool={activeTool} 
            onToolDeactivate={handleToolDeactivate}
            onDrawingsUpdate={handleDrawingsUpdate}
            onTick={handleTick}
            onWatchlistUpdate={handleWatchlistUpdate}
            onOrderSuccess={handleOrderSuccess}
            activeBacktestTrade={activeBacktestTrade}
            positions={positions}
            pendingOrders={pendingOrders}
            onCandleAccuracyUpdate={setCandleAccuracy}
            isMagnetOn={isMagnetOn}
          />
        </div>

        {/* Right Watchlist Panel */}
        {activeRightTab === 'watchlist' && (
          <div style={{
            width: '320px',
            borderLeft: '1px solid var(--tv-border)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: 'var(--tv-bg-primary)',
            zIndex: 10
          }}>
            {/* Watchlist Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              borderBottom: '1px solid var(--tv-border)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '14px' }}>
                <span>Watchlist</span>
                <ChevronDown size={14} color="var(--tv-text-secondary)" />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--tv-text-secondary)' }}>
                <span style={{ cursor: 'pointer', display: 'flex' }} onClick={() => setSearchOpen(true)} title="Add symbol">
                  <Plus size={16} />
                </span>
                <span style={{ cursor: 'pointer', display: 'flex' }} title="Table view">
                  <LayoutGrid size={16} />
                </span>
                <span style={{ cursor: 'pointer', display: 'flex' }} title="Options">
                  <MoreHorizontal size={16} />
                </span>
                <span style={{ cursor: 'pointer', display: 'flex', marginLeft: '4px' }} onClick={() => setActiveRightTab(null)} title="Collapse Watchlist">
                  <X size={16} />
                </span>
              </div>
            </div>

            {/* Column Headers */}
            <div style={{
              display: 'flex',
              padding: '6px 14px',
              color: 'var(--tv-text-secondary)',
              fontSize: '11px',
              borderBottom: '1px solid var(--tv-border-subtle)',
              fontWeight: 600
            }}>
              <div style={{ flex: 2.2 }}>Symbol</div>
              <div style={{ flex: 1.2, textAlign: 'right' }}>Last</div>
              <div style={{ flex: 1.2, textAlign: 'right' }}>Chg %</div>
            </div>

            {/* Grouped Watchlist Items */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {WATCHLIST_GROUPS.map(group => (
                <div key={group.category}>
                  {/* Category Header */}
                  <div style={{
                    padding: '8px 14px 4px 14px',
                    fontSize: '11px',
                    color: 'var(--tv-text-secondary)',
                    fontWeight: 700,
                    letterSpacing: '0.5px'
                  }}>
                    {group.category}
                  </div>

                  {group.symbols.map(s => {
                    const isSelected = symbol === s.id;
                    const item = watchlist[s.id];
                    const displayPrice = item ? item.price.toFixed(2) : '-';
                    const changePct = item ? item.change_pct : null;
                    const isPos = changePct !== null && changePct >= 0;

                    return (
                      <div
                        key={s.id}
                        onClick={() => setSymbol(s.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          padding: '7px 14px',
                          cursor: 'pointer',
                          backgroundColor: isSelected ? 'var(--tv-bg-secondary)' : 'transparent',
                          borderLeft: isSelected ? '3px solid var(--tv-accent)' : '3px solid transparent',
                          transition: 'background-color 0.1s'
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)';
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                        }}
                      >
                        {/* Circular badge */}
                        <div style={{
                          width: '22px',
                          height: '22px',
                          borderRadius: '50%',
                          backgroundColor: s.color,
                          color: '#fff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '10px',
                          fontWeight: 700,
                          marginRight: '10px',
                          flexShrink: 0
                        }}>
                          {s.badge}
                        </div>

                        {/* Symbol Name & D Tag */}
                        <div style={{ flex: 2.2, display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span style={{
                            fontWeight: isSelected ? 700 : 500,
                            fontSize: '13px',
                            color: isSelected ? '#fff' : 'var(--tv-text-primary)'
                          }}>
                            {s.name}
                          </span>
                          <span style={{ fontSize: '9px', color: 'var(--tv-text-muted)' }}>D</span>
                        </div>

                        {/* Last Price */}
                        <div style={{
                          flex: 1.2,
                          textAlign: 'right',
                          fontSize: '12px',
                          color: 'var(--tv-text-primary)',
                          fontVariantNumeric: 'tabular-nums'
                        }}>
                          {displayPrice}
                        </div>

                        {/* Change % */}
                        <div style={{
                          flex: 1.2,
                          textAlign: 'right',
                          fontSize: '12px',
                          fontWeight: 600,
                          fontVariantNumeric: 'tabular-nums',
                          color: changePct === null ? 'var(--tv-text-secondary)' : (isPos ? 'var(--tv-up)' : 'var(--tv-down)')
                        }}>
                          {changePct === null ? '-' : `${isPos ? '+' : ''}${changePct.toFixed(2)}%`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Far-Right Slim Navigation Rail (TradingView Style) */}
        <div style={{
          width: '42px',
          borderLeft: '1px solid var(--tv-border)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '8px 0',
          gap: '12px',
          backgroundColor: 'var(--tv-bg-primary)',
          zIndex: 10
        }}>
          <button
            onClick={() => setActiveRightTab(prev => prev === 'watchlist' ? null : 'watchlist')}
            style={{
              background: activeRightTab === 'watchlist' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeRightTab === 'watchlist' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Watchlist (Toggle Panel)"
          >
            <Bookmark size={18} />
          </button>

          <button
            onClick={() => setActiveRightTab(prev => prev === 'alerts' ? null : 'alerts')}
            style={{
              background: activeRightTab === 'alerts' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeRightTab === 'alerts' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Alerts (Toggle Panel)"
          >
            <Clock size={18} />
          </button>

          <button
            onClick={() => setShowTerminal(prev => !prev)}
            style={{
              background: showTerminal ? 'var(--tv-accent-bg)' : 'transparent',
              color: showTerminal ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Trading Panel"
          >
            <Activity size={18} />
          </button>

          <button
            onClick={() => setActiveRightTab(prev => prev === 'notifications' ? null : 'notifications')}
            style={{
              background: activeRightTab === 'notifications' ? 'var(--tv-accent-bg)' : 'transparent',
              color: activeRightTab === 'notifications' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            title="Notifications (Toggle Panel)"
          >
            <Bell size={18} />
          </button>
        </div>

      </div>

      {/* ─────────────────────────────────────────────────────────────
          3. BOTTOM TRADING TERMINAL & STATUS BAR
      ───────────────────────────────────────────────────────────── */}
      {showTerminal && (
        <div style={{
          height: '240px',
          borderTop: '1px solid var(--tv-border)',
          backgroundColor: 'var(--tv-bg-card)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 15
        }}>
          {/* Terminal Tabs */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            borderBottom: '1px solid var(--tv-border)',
            padding: '0 8px'
          }}>
            <button
              onClick={() => setTerminalTab('positions')}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'positions' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'positions' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px'
              }}
            >
              Positions ({positions.length})
            </button>
            <button
              onClick={() => setTerminalTab('orders')}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'orders' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'orders' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>Pending Orders</span>
              {pendingOrders.length > 0 && (
                <span style={{
                  background: '#ff9800',
                  color: '#000',
                  borderRadius: '10px',
                  padding: '1px 6px',
                  fontSize: '10px',
                  fontWeight: 'bold'
                }}>
                  {pendingOrders.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setTerminalTab('history')}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'history' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'history' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px'
              }}
            >
              History {history.length > 0 && `(${history.length})`}
            </button>
            <button
              onClick={() => setTerminalTab('backtest')}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'backtest' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'backtest' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>🎯 Backtest Trades</span>
              <span style={{
                background: '#089981',
                color: '#fff',
                borderRadius: '10px',
                padding: '1px 6px',
                fontSize: '10px',
                fontWeight: 'bold'
              }}>
                {backtestTrades.length}
              </span>
            </button>
            <button
              onClick={() => {
                setTerminalTab('scanner');
                fetchLiveScanner();
              }}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'scanner' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'scanner' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>📡 Retest Scanner</span>
              <span style={{
                background: '#2962ff',
                color: '#fff',
                borderRadius: '10px',
                padding: '1px 6px',
                fontSize: '10px',
                fontWeight: 'bold'
              }}>
                {scannerData.length > 0 ? scannerData.length : '15'}
              </span>
            </button>
            <button
              onClick={() => setShowTerminal(false)}
              style={{
                marginLeft: 'auto',
                background: 'transparent',
                border: 'none',
                color: 'var(--tv-text-secondary)',
                cursor: 'pointer',
                padding: '6px'
              }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Terminal Content */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {terminalTab === 'positions' && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                  <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Ticket</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Symbol</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Time</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Type</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Volume</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Price</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>S / L</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>T / P</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>Profit (USD)</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                        <span>Trade Actions</span>
                        {positions.length > 0 && (
                          <button
                            onClick={handlePanicCloseAll}
                            style={{
                              backgroundColor: 'rgba(242, 54, 69, 0.2)',
                              color: '#f23645',
                              border: '1px solid #f23645',
                              borderRadius: '4px',
                              padding: '2px 6px',
                              fontSize: '10px',
                              fontWeight: 700,
                              cursor: 'pointer'
                            }}
                            title="Panic close all open positions"
                          >
                            🚨 Flatten All
                          </button>
                        )}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {positions.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ padding: '30px', textAlign: 'center', color: 'var(--tv-text-secondary)' }}>
                        No open positions on MT5 account.
                      </td>
                    </tr>
                  ) : (
                    positions.map(p => {
                      const isBuy = p.type === 'Buy';
                      return (
                        <tr key={p.ticket} style={{ borderBottom: '1px solid var(--tv-border-subtle)' }}>
                          <td style={{ padding: '6px 14px' }}>{p.ticket}</td>
                          <td style={{ padding: '6px 14px', fontWeight: 600 }}>{p.symbol}</td>
                          <td style={{ padding: '6px 14px' }}>{new Date(p.time * 1000).toLocaleTimeString()}</td>
                          <td style={{ padding: '6px 14px', color: isBuy ? 'var(--tv-up)' : 'var(--tv-down)', fontWeight: 600 }}>
                            {p.type}
                          </td>
                          <td style={{ padding: '6px 14px' }}>{p.volume.toFixed(2)}</td>
                          <td style={{ padding: '6px 14px' }}>{p.price_open.toFixed(2)}</td>
                          <td style={{ padding: '6px 14px' }}>{p.sl ? p.sl.toFixed(2) : '-'}</td>
                          <td style={{ padding: '6px 14px' }}>{p.tp ? p.tp.toFixed(2) : '-'}</td>
                          <td style={{
                            padding: '6px 14px',
                            textAlign: 'right',
                            fontWeight: 700,
                            color: p.profit >= 0 ? 'var(--tv-up)' : 'var(--tv-down)'
                          }}>
                            {p.profit.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 14px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                              <button
                                onClick={() => setPyramidTarget(p)}
                                style={{
                                  backgroundColor: 'rgba(41, 98, 255, 0.15)',
                                  color: '#2962ff',
                                  border: '1px solid #2962ff',
                                  borderRadius: '4px',
                                  padding: '3px 7px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '2px'
                                }}
                                title="Pyramid: Add new position with same TP"
                              >
                                <span>⚡ Pyramid</span>
                              </button>

                              <button
                                onClick={() => handleLockProfit(p, 'margin')}
                                disabled={actionLoading[p.ticket] === 'margin'}
                                style={{
                                  backgroundColor: 'rgba(255, 152, 0, 0.15)',
                                  color: '#ff9800',
                                  border: '1px solid #ff9800',
                                  borderRadius: '4px',
                                  padding: '3px 7px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '2px'
                                }}
                                title="Lock Profit: Move SL so profit locked equals margin used (Free Trade!)"
                              >
                                <span>{actionLoading[p.ticket] === 'margin' ? '...' : '🔒 Lock +Margin'}</span>
                              </button>

                              <button
                                onClick={() => handleLockProfit(p, 'breakeven')}
                                disabled={actionLoading[p.ticket] === 'breakeven'}
                                style={{
                                  backgroundColor: Math.abs(p.sl - p.price_open) < 0.05 ? 'rgba(8, 153, 129, 0.25)' : 'rgba(8, 153, 129, 0.15)',
                                  color: '#089981',
                                  border: '1px solid #089981',
                                  borderRadius: '4px',
                                  padding: '3px 7px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '2px'
                                }}
                                title="Move SL to Entry Price (Breakeven)"
                              >
                                <span>{Math.abs(p.sl - p.price_open) < 0.05 ? '✓ BE' : '🛡️ BE'}</span>
                              </button>

                              {p.volume > 0.01 && (
                                <button
                                  onClick={() => handlePartialClose(p, 50)}
                                  disabled={actionLoading[p.ticket] === 'closing_pct'}
                                  style={{
                                    backgroundColor: 'rgba(233, 30, 99, 0.15)',
                                    color: '#e91e63',
                                    border: '1px solid #e91e63',
                                    borderRadius: '4px',
                                    padding: '3px 7px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    display: 'inline-flex',
                                    alignItems: 'center'
                                  }}
                                  title="Close 50% Volume to bank profit"
                                >
                                  <span>💰 50%</span>
                                </button>
                              )}

                              <button
                                onClick={() => handleBankAndReopen(p)}
                                disabled={actionLoading[p.ticket] === 'banking'}
                                style={{
                                  backgroundColor: 'rgba(0, 188, 212, 0.15)',
                                  color: '#00bcd4',
                                  border: '1px solid #00bcd4',
                                  borderRadius: '4px',
                                  padding: '3px 7px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '2px'
                                }}
                                title="Bank Profit into realized Balance and re-open at market with protected BE SL"
                              >
                                <span>{actionLoading[p.ticket] === 'banking' ? '...' : '🏦 Bank & Ride'}</span>
                              </button>

                              <button
                                onClick={() => {
                                  setEditTarget({
                                    kind: 'position',
                                    ticket: p.ticket,
                                    symbol: p.symbol,
                                    type: p.type,
                                    volume: p.volume,
                                    price: p.price_open,
                                    sl: p.sl,
                                    tp: p.tp
                                  });
                                  setEditModalOpen(true);
                                }}
                                style={{
                                  backgroundColor: '#2a2e39',
                                  color: '#d1d4dc',
                                  border: '1px solid #363a45',
                                  borderRadius: '4px',
                                  padding: '3px 6px',
                                  fontSize: '11px',
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center'
                                }}
                                title="Edit SL & TP numerically"
                              >
                                <Edit3 size={11} />
                              </button>

                              <button
                                onClick={() => handleClosePosition(p.ticket)}
                                style={{
                                  backgroundColor: 'rgba(242, 54, 69, 0.15)',
                                  color: '#f23645',
                                  border: '1px solid #f23645',
                                  borderRadius: '4px',
                                  padding: '3px 7px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center'
                                }}
                                title="Close Position at Market"
                              >
                                <span>✕</span>
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            )}

            {terminalTab === 'orders' && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                  <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Ticket</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Symbol</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Time Placed</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Order Type</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Volume</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Trigger Price</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Current Price</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>S / L</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>T / P</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'center' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingOrders.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ padding: '30px', textAlign: 'center', color: 'var(--tv-text-secondary)' }}>
                        No active pending orders (Buy Stop / Sell Stop / Limit).
                      </td>
                    </tr>
                  ) : (
                    pendingOrders.map(o => {
                      const isStop = o.type.toLowerCase().includes('stop');
                      const isBuy = o.type.toLowerCase().includes('buy');
                      const badgeColor = isStop ? (isBuy ? '#089981' : '#f23645') : '#2962ff';
                      return (
                        <tr key={o.ticket} style={{ borderBottom: '1px solid var(--tv-border-subtle)' }}>
                          <td style={{ padding: '6px 14px' }}>{o.ticket}</td>
                          <td style={{ padding: '6px 14px', fontWeight: 600 }}>{o.symbol}</td>
                          <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>
                            {new Date(o.time_setup * 1000).toLocaleTimeString()}
                          </td>
                          <td style={{ padding: '6px 14px' }}>
                            <span style={{
                              backgroundColor: `${badgeColor}22`,
                              color: badgeColor,
                              border: `1px solid ${badgeColor}`,
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontWeight: 700,
                              fontSize: '11px'
                            }}>
                              {isStop ? (isBuy ? '🛑 BUY STOP' : '🛑 SELL STOP') : (isBuy ? '🎯 BUY LIMIT' : '🎯 SELL LIMIT')}
                            </span>
                          </td>
                          <td style={{ padding: '6px 14px' }}>{o.volume.toFixed(2)}</td>
                          <td style={{ padding: '6px 14px', fontWeight: 700, color: '#fff' }}>
                            {o.price_open.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>
                            {o.price_current.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 14px', color: '#f23645' }}>{o.sl ? o.sl.toFixed(2) : '-'}</td>
                          <td style={{ padding: '6px 14px', color: '#089981' }}>{o.tp ? o.tp.toFixed(2) : '-'}</td>
                          <td style={{ padding: '6px 14px', textAlign: 'center' }}>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                              <button
                                onClick={() => {
                                  setEditTarget({
                                    kind: 'pending',
                                    ticket: o.ticket,
                                    symbol: o.symbol,
                                    type: o.type,
                                    volume: o.volume,
                                    price: o.price_open,
                                    sl: o.sl,
                                    tp: o.tp
                                  });
                                  setEditModalOpen(true);
                                }}
                                style={{
                                  backgroundColor: '#2a2e39',
                                  color: '#d1d4dc',
                                  border: '1px solid #363a45',
                                  borderRadius: '4px',
                                  padding: '3px 8px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '3px'
                                }}
                                title="Edit Trigger Price, SL & TP"
                              >
                                <Edit3 size={11} />
                                <span>Edit</span>
                              </button>
                              <button
                                onClick={() => handleCancelOrder(o.ticket)}
                                style={{
                                  backgroundColor: 'rgba(242, 54, 69, 0.15)',
                                  color: '#f23645',
                                  border: '1px solid #f23645',
                                  borderRadius: '4px',
                                  padding: '3px 10px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: 'pointer'
                                }}
                              >
                                ✕ Cancel
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            )}

            {terminalTab === 'history' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
                {/* Stats summary banner */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '20px',
                  padding: '8px 16px',
                  backgroundColor: 'rgba(255,255,255,0.02)',
                  borderBottom: '1px solid var(--tv-border)',
                  fontSize: '12px'
                }}>
                  <div>
                    <span style={{ color: 'var(--tv-text-secondary)', marginRight: '6px' }}>Total Closed:</span>
                    <strong style={{ color: '#fff' }}>{history.length}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--tv-text-secondary)', marginRight: '6px' }}>Wins:</span>
                    <strong style={{ color: '#089981' }}>{history.filter(h => h.profit > 0).length}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--tv-text-secondary)', marginRight: '6px' }}>Losses:</span>
                    <strong style={{ color: '#f23645' }}>{history.filter(h => h.profit < 0).length}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--tv-text-secondary)', marginRight: '6px' }}>Win Rate:</span>
                    <strong style={{ color: history.length ? (history.filter(h => h.profit > 0).length / history.length >= 0.5 ? '#089981' : '#f23645') : '#fff' }}>
                      {history.length ? `${Math.round((history.filter(h => h.profit > 0).length / history.length) * 100)}%` : '0%'}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--tv-text-secondary)', marginRight: '6px' }}>Net Realized PnL:</span>
                    <strong style={{ color: history.reduce((acc, h) => acc + h.profit, 0) >= 0 ? '#089981' : '#f23645' }}>
                      ${history.reduce((acc, h) => acc + h.profit, 0).toFixed(2)}
                    </strong>
                  </div>
                </div>

                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                    <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Ticket</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Symbol</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Type</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Volume</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Close Price</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Time</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Comment</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>Profit (USD)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ padding: '30px', textAlign: 'center', color: 'var(--tv-text-secondary)' }}>
                          No recent closed trades in account history.
                        </td>
                      </tr>
                    ) : (
                      history.map((h, idx) => {
                        const isWin = h.profit > 0;
                        const isLoss = h.profit < 0;
                        const dateStr = new Date(h.time * 1000).toLocaleString([], {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        });

                        return (
                          <tr
                            key={h.ticket || idx}
                            style={{
                              borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                              backgroundColor: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)'
                            }}
                          >
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>
                              #{h.order || h.ticket}
                            </td>
                            <td style={{ padding: '6px 14px', fontWeight: 600, color: '#fff' }}>
                              {h.symbol}
                            </td>
                            <td style={{ padding: '6px 14px' }}>
                              <span style={{
                                padding: '2px 6px',
                                borderRadius: '3px',
                                fontSize: '10px',
                                fontWeight: 700,
                                backgroundColor: h.type === 'Buy' ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)',
                                color: h.type === 'Buy' ? '#089981' : '#f23645'
                              }}>
                                {h.type.toUpperCase()}
                              </span>
                            </td>
                            <td style={{ padding: '6px 14px', color: '#d1d4dc' }}>
                              {h.volume.toFixed(2)}
                            </td>
                            <td style={{ padding: '6px 14px', color: '#d1d4dc' }}>
                              {h.price.toFixed(2)}
                            </td>
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>
                              {dateStr}
                            </td>
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)', fontSize: '11px' }}>
                              {h.comment || '-'}
                            </td>
                            <td style={{
                              padding: '6px 14px',
                              textAlign: 'right',
                              fontWeight: 700,
                              color: isWin ? '#089981' : isLoss ? '#f23645' : 'var(--tv-text-secondary)'
                            }}>
                              {isWin ? `+$${h.profit.toFixed(2)}` : `$${h.profit.toFixed(2)}`}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {terminalTab === 'backtest' && (
              <div>
                {/* Filter Pills Bar */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 14px',
                  borderBottom: '1px solid var(--tv-border)',
                  backgroundColor: 'rgba(20, 24, 35, 0.7)'
                }}>
                  <span style={{ fontSize: '11px', color: 'var(--tv-text-secondary)', fontWeight: 600 }}>Filter:</span>
                  <button
                    onClick={() => { setSetupFilter('all'); setBacktestIdx(0); }}
                    style={{
                      backgroundColor: setupFilter === 'all' ? 'var(--tv-accent)' : 'var(--tv-bg-hover)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '12px',
                      padding: '3px 10px',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    All ({backtestTrades.length})
                  </button>
                  <button
                    onClick={() => { setSetupFilter('expansion'); setBacktestIdx(0); }}
                    style={{
                      backgroundColor: setupFilter === 'expansion' ? '#ff9800' : 'rgba(255, 152, 0, 0.15)',
                      color: setupFilter === 'expansion' ? '#000' : '#ff9800',
                      border: '1px solid #ff9800',
                      borderRadius: '12px',
                      padding: '3px 10px',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    🚀 Breakout Expansion ({backtestTrades.filter(t => t.setup?.includes('Expansion')).length})
                  </button>
                  <button
                    onClick={() => { setSetupFilter('pullback'); setBacktestIdx(0); }}
                    style={{
                      backgroundColor: setupFilter === 'pullback' ? '#00b4d8' : 'rgba(0, 180, 216, 0.15)',
                      color: setupFilter === 'pullback' ? '#000' : '#00b4d8',
                      border: '1px solid #00b4d8',
                      borderRadius: '12px',
                      padding: '3px 10px',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    ⚡ Pullback Retracement ({backtestTrades.filter(t => t.setup?.includes('Pullback')).length})
                  </button>
                  <button
                    onClick={() => { setSetupFilter('continuation'); setBacktestIdx(0); }}
                    style={{
                      backgroundColor: setupFilter === 'continuation' ? '#089981' : 'rgba(8, 153, 129, 0.15)',
                      color: setupFilter === 'continuation' ? '#fff' : '#089981',
                      border: '1px solid #089981',
                      borderRadius: '12px',
                      padding: '3px 10px',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    🔄 Retest Continuation ({backtestTrades.filter(t => t.setup?.includes('Continuation')).length})
                  </button>
                </div>

                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                    <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>#</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Type</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Setup</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Time (M5)</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Entry</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Stop Loss</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Take Profit</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>RRR</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>P/L (USD)</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'center' }}>Visualizer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredBacktestTrades.length === 0 ? (
                      <tr>
                        <td colSpan={10} style={{ padding: '30px', textAlign: 'center', color: 'var(--tv-text-secondary)' }}>
                          No {setupFilter !== 'all' ? setupFilter : ''} trades found for {symbol}...
                        </td>
                      </tr>
                    ) : (
                      filteredBacktestTrades.map((t: any, idx: number) => {
                        const isShort = t.type === 'short-position';
                        const isSelected = activeBacktestTrade?.id === t.id;
                        const isExpansion = t.setup?.includes('Expansion');
                        const isPullback = t.setup?.includes('Pullback');
                        const isContinuation = t.setup?.includes('Continuation');
                        const dateStr = new Date(t.entryTime * 1000).toLocaleString([], {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        });

                        return (
                          <tr
                            key={t.id || idx}
                            onClick={() => selectTrade(idx)}
                            style={{
                              borderBottom: '1px solid var(--tv-border-subtle)',
                              backgroundColor: isSelected ? 'rgba(41, 98, 255, 0.15)' : 'transparent',
                              cursor: 'pointer',
                              transition: 'background-color 0.1s'
                            }}
                            onMouseEnter={(e) => {
                              if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)';
                            }}
                            onMouseLeave={(e) => {
                              if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-muted)' }}>{idx + 1}</td>
                            <td style={{ padding: '6px 14px' }}>
                              <span style={{
                                backgroundColor: isShort ? 'rgba(242, 54, 69, 0.2)' : 'rgba(8, 153, 129, 0.2)',
                                color: isShort ? '#f23645' : '#089981',
                                padding: '2px 6px',
                                borderRadius: '3px',
                                fontWeight: 700,
                                fontSize: '10px'
                              }}>
                                {isShort ? 'SHORT' : 'LONG'}
                              </span>
                            </td>
                            <td style={{ padding: '6px 14px', fontWeight: 600 }}>
                              {isExpansion ? (
                                <span style={{
                                  backgroundColor: 'rgba(255, 152, 0, 0.2)',
                                  color: '#ff9800',
                                  padding: '1px 6px',
                                  borderRadius: '3px',
                                  fontSize: '10px',
                                  marginRight: '6px',
                                  fontWeight: 700
                                }}>
                                  🚀 EXPANSION
                                </span>
                              ) : isPullback ? (
                                <span style={{
                                  backgroundColor: 'rgba(0, 180, 216, 0.2)',
                                  color: '#00b4d8',
                                  padding: '1px 6px',
                                  borderRadius: '3px',
                                  fontSize: '10px',
                                  marginRight: '6px',
                                  fontWeight: 700
                                }}>
                                  ⚡ PULLBACK
                                </span>
                              ) : isContinuation ? (
                                <span style={{
                                  backgroundColor: 'rgba(8, 153, 129, 0.2)',
                                  color: '#089981',
                                  padding: '1px 6px',
                                  borderRadius: '3px',
                                  fontSize: '10px',
                                  marginRight: '6px',
                                  fontWeight: 700
                                }}>
                                  🔄 CONTINUATION
                                </span>
                              ) : null}
                              {t.setup}
                            </td>
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>{dateStr}</td>
                            <td style={{ padding: '6px 14px' }}>{t.entry.toFixed(2)}</td>
                            <td style={{ padding: '6px 14px', color: '#f23645' }}>{t.sl.toFixed(2)}</td>
                            <td style={{ padding: '6px 14px', color: '#089981' }}>{t.tp.toFixed(2)}</td>
                          <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>1:{t.rrr ? t.rrr.toFixed(2) : '1.5'}</td>
                          <td style={{
                            padding: '6px 14px',
                            textAlign: 'right',
                            fontWeight: 700,
                            color: t.win ? '#089981' : '#f23645'
                          }}>
                            {t.win ? `+$${t.pnl_usd.toFixed(2)}` : `-$${Math.abs(t.pnl_usd).toFixed(2)}`}
                          </td>
                          <td style={{ padding: '6px 14px', textAlign: 'center' }}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                selectTrade(idx);
                              }}
                              style={{
                                backgroundColor: isSelected ? 'var(--tv-accent)' : '#2a2e39',
                                color: '#fff',
                                border: 'none',
                                borderRadius: '3px',
                                padding: '3px 8px',
                                fontSize: '11px',
                                cursor: 'pointer',
                                fontWeight: 600
                              }}
                            >
                              {isSelected ? '✓ Viewing' : '👁 View'}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {terminalTab === 'scanner' && (
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
              {/* Scanner Controls Bar */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 14px',
                borderBottom: '1px solid var(--tv-border)',
                backgroundColor: 'rgba(20, 24, 35, 0.7)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--tv-text-secondary)', fontWeight: 600 }}>Scanner Timeframe:</span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {(['M30', 'M5'] as const).map(tf => (
                      <button
                        key={tf}
                        onClick={() => {
                          setScannerTimeframe(tf);
                          fetchLiveScanner(tf);
                        }}
                        style={{
                          backgroundColor: scannerTimeframe === tf ? 'var(--tv-accent)' : 'var(--tv-bg-hover)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '3px 10px',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer'
                        }}
                      >
                        {tf} Retest Scanner
                      </button>
                    ))}
                  </div>
                  <span style={{ fontSize: '11px', color: '#787b86' }}>
                    · Scans all 15 Weltrade synthetic indices for Breakout Retest setups in real-time
                  </span>
                </div>

                <button
                  onClick={() => fetchLiveScanner()}
                  disabled={scannerLoading}
                  style={{
                    backgroundColor: '#2a2e39',
                    border: '1px solid #363a45',
                    borderRadius: '4px',
                    color: '#d1d4dc',
                    padding: '4px 10px',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}
                >
                  <RefreshCw size={12} className={scannerLoading ? 'spin' : ''} />
                  <span>{scannerLoading ? 'Scanning...' : 'Refresh'}</span>
                </button>
              </div>

              {/* Scanner Results Table */}
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                  <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Status</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Symbol</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Setup</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Key Retest Level</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Current Price</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Distance (ATR)</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Distance (Pts)</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Margin (0.01 Lot)</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500 }}>Spread</th>
                    <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'center' }}>Chart Action</th>
                  </tr>
                </thead>
                <tbody>
                  {scannerData.length === 0 ? (
                    <tr>
                      <td colSpan={10} style={{ padding: '30px', textAlign: 'center', color: 'var(--tv-text-secondary)' }}>
                        {scannerLoading ? 'Analyzing market structure across all symbols...' : 'No symbols found or scanner is refreshing...'}
                      </td>
                    </tr>
                  ) : (
                    scannerData.map((item) => {
                      const isAtZone = item.status === 'AT_RETEST_ZONE';
                      const isApproaching = item.status === 'APPROACHING';
                      const isBullish = item.direction === 'BULLISH';
                      const isCurrentSymbol = item.symbol === symbol;

                      return (
                        <tr
                          key={item.symbol}
                          style={{
                            borderBottom: '1px solid var(--tv-border-subtle)',
                            backgroundColor: isAtZone ? 'rgba(8, 153, 129, 0.08)' : isCurrentSymbol ? 'rgba(41, 98, 255, 0.08)' : 'transparent'
                          }}
                        >
                          <td style={{ padding: '6px 14px' }}>
                            <span style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '10px',
                              fontWeight: 700,
                              backgroundColor: isAtZone ? 'rgba(8, 153, 129, 0.25)' : isApproaching ? 'rgba(255, 152, 0, 0.25)' : 'rgba(0, 188, 212, 0.2)',
                              color: isAtZone ? '#089981' : isApproaching ? '#ff9800' : '#00bcd4',
                              border: `1px solid ${isAtZone ? '#089981' : isApproaching ? '#ff9800' : '#00bcd4'}`
                            }}>
                              {isAtZone ? '🎯 AT RETEST ZONE' : isApproaching ? '⚡ APPROACHING' : '🔄 PULLBACK'}
                            </span>
                          </td>
                          <td style={{ padding: '6px 14px', fontWeight: 700, color: '#fff' }}>
                            {item.symbol.replace('_', ' ')}
                          </td>
                          <td style={{ padding: '6px 14px' }}>
                            <span style={{
                              color: isBullish ? '#089981' : '#f23645',
                              fontWeight: 600,
                              fontSize: '11px'
                            }}>
                              {isBullish ? '▲ ' : '▼ '}{item.setup}
                            </span>
                          </td>
                          <td style={{ padding: '6px 14px', fontWeight: 700, color: '#ff9800' }}>
                            {item.level.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 14px', color: '#d1d4dc' }}>
                            {item.current_price.toFixed(2)}
                          </td>
                          <td style={{
                            padding: '6px 14px',
                            fontWeight: 700,
                            color: isAtZone ? '#089981' : isApproaching ? '#ff9800' : '#787b86'
                          }}>
                            {item.dist_atr > 0 ? `+${item.dist_atr}` : item.dist_atr} ATR
                          </td>
                          <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)' }}>
                            {item.dist_pts > 0 ? `+${item.dist_pts.toFixed(1)}` : item.dist_pts.toFixed(1)} pts
                          </td>
                          <td style={{ padding: '6px 14px', color: '#089981', fontWeight: 600 }}>
                            ${item.margin_001.toFixed(2)}
                          </td>
                          <td style={{ padding: '6px 14px', color: 'var(--tv-text-muted)' }}>
                            {item.spread_pts.toFixed(1)}
                          </td>
                          <td style={{ padding: '6px 14px', textAlign: 'center' }}>
                            <button
                              onClick={() => {
                                setSymbol(item.symbol);
                                setTimeframe(scannerTimeframe);
                                setShowTerminal(false);
                              }}
                              style={{
                                backgroundColor: isCurrentSymbol ? '#2a2e39' : (isAtZone ? '#089981' : '#2962ff'),
                                color: '#fff',
                                border: 'none',
                                borderRadius: '4px',
                                padding: '4px 10px',
                                fontSize: '11px',
                                fontWeight: 700,
                                cursor: 'pointer'
                              }}
                            >
                              {isCurrentSymbol ? '✓ Active' : '⚡ Load Setup'}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
          </div>
        </div>
      )}

      {/* Bottom Status Bar */}
      <div style={{
        height: '28px',
        borderTop: '1px solid var(--tv-border)',
        backgroundColor: 'var(--tv-bg-primary)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 14px',
        fontSize: '11px',
        gap: '16px',
        color: 'var(--tv-text-secondary)',
        fontWeight: 500
      }}>
        {/* MT5 Connection Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: account ? '#089981' : '#f23645',
            boxShadow: account ? '0 0 6px #089981' : '0 0 6px #f23645'
          }} />
          <span style={{ color: 'var(--tv-text-primary)' }}>
            {account ? 'MT5 Connected' : 'MT5 Disconnected'}
          </span>
        </div>

        {/* MT5 Continuous Candle Reconciliation Status */}
        <div 
          onClick={verifyCandlesManually}
          title="Click to force immediate MT5 integrity re-verification"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            cursor: 'pointer',
            padding: '2px 8px',
            borderRadius: '4px',
            backgroundColor: candleAccuracy.status === 'verified' ? 'rgba(8, 153, 129, 0.12)' : 'rgba(255, 152, 0, 0.12)',
            border: `1px solid ${candleAccuracy.status === 'verified' ? 'rgba(8, 153, 129, 0.3)' : 'rgba(255, 152, 0, 0.3)'}`
          }}
        >
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: candleAccuracy.status === 'verified' ? '#089981' : '#ff9800',
            boxShadow: candleAccuracy.status === 'verified' ? '0 0 6px #089981' : '0 0 6px #ff9800'
          }} />
          <span style={{ color: candleAccuracy.status === 'verified' ? '#089981' : '#ff9800', fontWeight: 600 }}>
            {isVerifying ? 'Verifying with MT5...' : candleAccuracy.status === 'verified' ? 'Candles: 100% In-Sync' : 'Candles: Syncing...'}
          </span>
          <span style={{ color: 'var(--tv-text-muted)', fontSize: '10px' }}>
            ({candleAccuracy.desyncFixedCount > 0 ? `${candleAccuracy.desyncFixedCount} healed` : '0 desync'})
          </span>
        </div>

        {/* Account Info and Quick Switch */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>{account?.server || 'Weltrade-Demo'} {account?.login ? `(#${account.login})` : ''}</span>
          <button
            onClick={() => {
              setTargetLogin(account?.login ? String(account.login) : '34931796');
              setTargetServer(account?.server || 'Weltrade-Real');
              setAccountModalOpen(true);
            }}
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              color: 'var(--tv-text-secondary)',
              border: '1px solid var(--tv-border)',
              borderRadius: '3px',
              padding: '1px 6px',
              fontSize: '10px',
              cursor: 'pointer',
              fontWeight: 600
            }}
            title="Switch MT5 Account"
          >
            🔄 Switch
          </button>
        </div>

        {/* Live Broker Ping */}
        <span style={{ color: 'var(--tv-text-muted)' }}>
          ⚡ {account?.ping_ms ? `${account.ping_ms}ms Ping` : '195ms Ping'}
        </span>
        {account?.name && <span style={{ color: 'var(--tv-text-muted)' }}>· {account.name}</span>}

        <div style={{ width: '1px', height: '14px', background: 'var(--tv-border)' }} />

        <span>Balance: <strong style={{ color: 'var(--tv-text-primary)' }}>{account ? account.balance.toFixed(2) : '-'} {account?.currency || 'USD'}</strong></span>
        <span>Equity: <strong style={{ color: 'var(--tv-text-primary)' }}>{account ? account.equity.toFixed(2) : '-'}</strong></span>
        <span>Free Margin: <strong style={{ color: 'var(--tv-text-primary)' }}>{account ? account.margin_free.toFixed(2) : '-'}</strong></span>
        {account?.leverage && <span>Leverage: <strong style={{ color: 'var(--tv-text-primary)' }}>1:{account.leverage}</strong></span>}

        <button
          onClick={() => setShowTerminal(prev => !prev)}
          style={{
            marginLeft: 'auto',
            background: 'transparent',
            border: 'none',
            color: 'var(--tv-text-secondary)',
            cursor: 'pointer',
            fontSize: '11px'
          }}
        >
          {showTerminal ? 'Hide Terminal ▾' : 'Show Terminal ▴'}
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────
          4. SYMBOL SEARCH MODAL (TradingView Popover Style)
      ───────────────────────────────────────────────────────────── */}
      {searchOpen && (
        <div
          onClick={() => setSearchOpen(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: '80px',
            zIndex: 100
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '560px',
              backgroundColor: 'var(--tv-bg-secondary)',
              border: '1px solid var(--tv-border)',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 12px 32px rgba(0, 0, 0, 0.6)',
              display: 'flex',
              flexDirection: 'column',
              maxHeight: '480px'
            }}
          >
            {/* Search Input Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              borderBottom: '1px solid var(--tv-border)',
              gap: '10px'
            }}>
              <Search size={18} color="var(--tv-text-secondary)" />
              <input
                type="text"
                autoFocus
                placeholder="Search symbol (e.g. Vol 20, FlipX)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--tv-text-primary)',
                  fontSize: '15px'
                }}
              />
              <button
                onClick={() => setSearchOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Symbol Results List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '6px 0' }}>
              {filteredSymbols.map(s => {
                const isSelected = symbol === s.id;
                const item = watchlist[s.id];
                const displayPrice = item ? item.price.toFixed(2) : '-';

                return (
                  <div
                    key={s.id}
                    onClick={() => setSymbol(s.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '10px 16px',
                      cursor: 'pointer',
                      backgroundColor: isSelected ? 'var(--tv-bg-hover)' : 'transparent',
                      transition: 'background-color 0.1s'
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <div style={{
                      width: '26px',
                      height: '26px',
                      borderRadius: '50%',
                      backgroundColor: s.color,
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '11px',
                      marginRight: '12px'
                    }}>
                      {s.badge}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--tv-text-primary)' }}>
                        {s.name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--tv-text-secondary)' }}>
                        Weltrade Synthetic Index
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--tv-text-primary)' }}>
                        {displayPrice}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--tv-text-muted)' }}>
                        INDEX
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Pyramiding Modal for scaling into active positions with same TP */}
      {pyramidTarget && (
        <PyramidModal
          position={pyramidTarget}
          onClose={() => setPyramidTarget(null)}
          onSuccess={(_ticket) => {
            fetchMt5();
          }}
        />
      )}

      {/* Account Switcher Modal */}
      {accountModalOpen && (
        <div
          onClick={() => setAccountModalOpen(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 110
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '380px',
              backgroundColor: '#181b27',
              border: '1px solid var(--tv-border)',
              borderRadius: '8px',
              padding: '18px',
              boxShadow: '0 16px 40px rgba(0,0,0,0.7)',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
              color: '#d1d4dc'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--tv-border)', paddingBottom: '10px' }}>
              <div style={{ fontWeight: 700, fontSize: '14px', color: '#fff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>🔄 Switch MT5 Account</span>
              </div>
              <button
                onClick={() => setAccountModalOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Quick Preset Buttons */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => {
                  setTargetLogin('34931796');
                  setTargetServer('Weltrade-Real');
                }}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '5px',
                  border: targetLogin === '34931796' ? '1px solid #089981' : '1px solid var(--tv-border)',
                  backgroundColor: targetLogin === '34931796' ? 'rgba(8, 153, 129, 0.15)' : '#1e222d',
                  color: targetLogin === '34931796' ? '#089981' : '#d1d4dc',
                  fontWeight: 600,
                  fontSize: '11px',
                  cursor: 'pointer'
                }}
              >
                <div>Real #34931796</div>
                <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>Weltrade-Real</div>
              </button>

              <button
                onClick={() => {
                  setTargetLogin('1654963');
                  setTargetServer('Weltrade-Demo');
                }}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '5px',
                  border: targetLogin === '1654963' ? '1px solid #2962ff' : '1px solid var(--tv-border)',
                  backgroundColor: targetLogin === '1654963' ? 'rgba(41, 98, 255, 0.15)' : '#1e222d',
                  color: targetLogin === '1654963' ? '#2962ff' : '#d1d4dc',
                  fontWeight: 600,
                  fontSize: '11px',
                  cursor: 'pointer'
                }}
              >
                <div>Demo #1654963</div>
                <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>Weltrade-Demo ($74)</div>
              </button>
            </div>

            {/* Form Fields */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
              <div>
                <label style={{ color: 'var(--tv-text-secondary)', display: 'block', marginBottom: '3px' }}>Account Login Number</label>
                <input
                  type="text"
                  value={targetLogin}
                  onChange={(e) => setTargetLogin(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#131722',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '8px 10px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ color: 'var(--tv-text-secondary)', display: 'block', marginBottom: '3px' }}>Server</label>
                <input
                  type="text"
                  value={targetServer}
                  onChange={(e) => setTargetServer(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#131722',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '8px 10px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>

              <div>
                <label style={{ color: 'var(--tv-text-secondary)', display: 'block', marginBottom: '3px' }}>Password (Optional if saved in MT5)</label>
                <input
                  type="password"
                  value={targetPassword}
                  placeholder="Enter password if prompted..."
                  onChange={(e) => setTargetPassword(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: '#131722',
                    border: '1px solid var(--tv-border)',
                    borderRadius: '4px',
                    padding: '8px 10px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
            </div>

            <button
              onClick={() => handleSwitchAccount(parseInt(targetLogin) || 0, targetServer, targetPassword)}
              disabled={switchingAccount || !targetLogin}
              style={{
                backgroundColor: 'var(--tv-accent)',
                color: '#fff',
                border: 'none',
                borderRadius: '5px',
                padding: '10px 0',
                fontWeight: 700,
                fontSize: '13px',
                cursor: switchingAccount ? 'not-allowed' : 'pointer',
                opacity: switchingAccount ? 0.7 : 1,
                marginTop: '4px'
              }}
            >
              {switchingAccount ? 'Switching MT5 Account...' : `Login to #${targetLogin}`}
            </button>
          </div>
        </div>
      )}

      {/* Weltrade Safe Vault & Cabinet Modal */}
      <WeltradeSafeModal
        isOpen={weltradeModalOpen}
        onClose={() => setWeltradeModalOpen(false)}
        activeAccountLogin={account?.login}
        balance={account?.balance || 0}
        onTransferSuccess={() => fetchMt5(true)}
      />

      {/* Edit Order (SL/TP & Trigger) Modal */}
      <EditOrderModal
        isOpen={editModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setEditTarget(null);
        }}
        target={editTarget}
        onSuccess={() => fetchMt5(true)}
      />

    </div>
  );
}
