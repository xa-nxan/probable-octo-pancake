import { useState, useCallback, useEffect, useRef } from 'react';
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
  Shield, Edit3, Cloud, Columns, Volume2, Target, Award, Zap, RefreshCw
} from 'lucide-react';

export interface SymbolItem {
  id: string;
  name: string;
  badge: string;
  color: string;
  group: string;
  category: string;
}

export interface WatchlistGroup {
  category: string;
  group: string;
  symbols: SymbolItem[];
}

const WATCHLIST_GROUPS: WatchlistGroup[] = [
  {
    category: 'FX VOLATILITY',
    group: 'FX Vol',
    symbols: [
      { id: 'FX_Vol_20', name: 'FX Vol 20', badge: '20', color: '#f23645', group: 'FX Vol', category: 'FX Volatility' },
      { id: 'FX_Vol_40', name: 'FX Vol 40', badge: '40', color: '#2962ff', group: 'FX Vol', category: 'FX Volatility' },
      { id: 'FX_Vol_60', name: 'FX Vol 60', badge: '60', color: '#089981', group: 'FX Vol', category: 'FX Volatility' },
      { id: 'FX_Vol_80', name: 'FX Vol 80', badge: '80', color: '#ff9800', group: 'FX Vol', category: 'FX Volatility' },
      { id: 'FX_Vol_99', name: 'FX Vol 99', badge: '99', color: '#9c27b0', group: 'FX Vol', category: 'FX Volatility' },
    ]
  },
  {
    category: 'SFX STEP-VOLATILITY',
    group: 'SFX Vol',
    symbols: [
      { id: 'SFX_Vol_20', name: 'SFX Vol 20', badge: 'S2', color: '#089981', group: 'SFX Vol', category: 'SFX Step-Vol' },
      { id: 'SFX_Vol_40', name: 'SFX Vol 40', badge: 'S4', color: '#ff9800', group: 'SFX Vol', category: 'SFX Step-Vol' },
      { id: 'SFX_Vol_60', name: 'SFX Vol 60', badge: 'S6', color: '#e91e63', group: 'SFX Vol', category: 'SFX Step-Vol' },
      { id: 'SFX_Vol_80', name: 'SFX Vol 80', badge: 'S8', color: '#3f51b5', group: 'SFX Vol', category: 'SFX Step-Vol' },
      { id: 'SFX_Vol_99', name: 'SFX Vol 99', badge: 'S9', color: '#00bcd4', group: 'SFX Vol', category: 'SFX Step-Vol' },
    ]
  },
  {
    category: 'GAINX BOOM / SPIKE SERIES',
    group: 'GainX',
    symbols: [
      { id: 'GainX_400', name: 'GainX 400', badge: 'G4', color: '#26a69a', group: 'GainX', category: 'GainX Series' },
      { id: 'GainX_600', name: 'GainX 600', badge: 'G6', color: '#00b0ff', group: 'GainX', category: 'GainX Series' },
      { id: 'GainX_800', name: 'GainX 800', badge: 'G8', color: '#7c4dff', group: 'GainX', category: 'GainX Series' },
      { id: 'GainX_999', name: 'GainX 999', badge: 'G9', color: '#00e676', group: 'GainX', category: 'GainX Series' },
      { id: 'GainX_1200', name: 'GainX 1200', badge: 'G12', color: '#1de9b6', group: 'GainX', category: 'GainX Series' },
      { id: 'MAX_GainX_1000', name: 'MAX GainX 1000', badge: 'MG1', color: '#00e5ff', group: 'GainX', category: 'GainX Series' },
      { id: 'MAX_GainX_2000', name: 'MAX GainX 2000', badge: 'MG2', color: '#651fff', group: 'GainX', category: 'GainX Series' },
    ]
  },
  {
    category: 'PAINX CRASH / DROP SERIES',
    group: 'PainX',
    symbols: [
      { id: 'PainX_400', name: 'PainX 400', badge: 'P4', color: '#ef5350', group: 'PainX', category: 'PainX Series' },
      { id: 'PainX_600', name: 'PainX 600', badge: 'P6', color: '#ff5722', group: 'PainX', category: 'PainX Series' },
      { id: 'PainX_800', name: 'PainX 800', badge: 'P8', color: '#ff1744', group: 'PainX', category: 'PainX Series' },
      { id: 'PainX_999', name: 'PainX 999', badge: 'P9', color: '#d50000', group: 'PainX', category: 'PainX Series' },
      { id: 'PainX_1200', name: 'PainX 1200', badge: 'P12', color: '#c51162', group: 'PainX', category: 'PainX Series' },
      { id: 'MAX_PainX_1000', name: 'MAX PainX 1000', badge: 'MP1', color: '#aa00ff', group: 'PainX', category: 'PainX Series' },
      { id: 'MAX_PainX_2000', name: 'MAX PainX 2000', badge: 'MP2', color: '#ff4081', group: 'PainX', category: 'PainX Series' },
    ]
  },
  {
    category: 'FLIPX JUMP SERIES',
    group: 'FlipX',
    symbols: [
      { id: 'FlipX_1', name: 'FlipX 1', badge: 'F1', color: '#ffd600', group: 'FlipX', category: 'FlipX Series' },
      { id: 'FlipX_2', name: 'FlipX 2', badge: 'F2', color: '#ffab00', group: 'FlipX', category: 'FlipX Series' },
      { id: 'FlipX_3', name: 'FlipX 3', badge: 'F3', color: '#ff6d00', group: 'FlipX', category: 'FlipX Series' },
      { id: 'FlipX_4', name: 'FlipX 4', badge: 'F4', color: '#dd2c00', group: 'FlipX', category: 'FlipX Series' },
      { id: 'FlipX_5', name: 'FlipX 5', badge: 'F5', color: '#ff3d00', group: 'FlipX', category: 'FlipX Series' },
    ]
  },
  {
    category: 'BREAKX BREAKOUT SERIES',
    group: 'BreakX',
    symbols: [
      { id: 'BreakX_600', name: 'BreakX 600', badge: 'B6', color: '#26c6da', group: 'BreakX', category: 'BreakX Series' },
      { id: 'BreakX_1200', name: 'BreakX 1200', badge: 'B12', color: '#0097a7', group: 'BreakX', category: 'BreakX Series' },
      { id: 'BreakX_1800', name: 'BreakX 1800', badge: 'B18', color: '#006064', group: 'BreakX', category: 'BreakX Series' },
    ]
  },
  {
    category: 'SWITCHX REVERSAL SERIES',
    group: 'SwitchX',
    symbols: [
      { id: 'SwitchX_600', name: 'SwitchX 600', badge: 'SW6', color: '#ab47bc', group: 'SwitchX', category: 'SwitchX Series' },
      { id: 'SwitchX_1200', name: 'SwitchX 1200', badge: 'SW12', color: '#8e24aa', group: 'SwitchX', category: 'SwitchX Series' },
      { id: 'SwitchX_1800', name: 'SwitchX 1800', badge: 'SW18', color: '#4a148c', group: 'SwitchX', category: 'SwitchX Series' },
    ]
  },
  {
    category: 'TRENDX MOMENTUM SERIES',
    group: 'TrendX',
    symbols: [
      { id: 'TrendX_600', name: 'TrendX 600', badge: 'TX6', color: '#66bb6a', group: 'TrendX', category: 'TrendX Series' },
      { id: 'TrendX_1200', name: 'TrendX 1200', badge: 'TX12', color: '#43a047', group: 'TrendX', category: 'TrendX Series' },
      { id: 'TrendX_1800', name: 'TrendX 1800', badge: 'TX18', color: '#1b5e20', group: 'TrendX', category: 'TrendX Series' },
    ]
  },
  {
    category: 'OTHER SYNTHETICS',
    group: 'Other',
    symbols: [
      { id: 'FiboX', name: 'FiboX', badge: 'FB', color: '#ffca28', group: 'Other', category: 'Other Synthetics' },
      { id: 'PlusX_1', name: 'PlusX 1', badge: 'PX1', color: '#29b6f6', group: 'Other', category: 'Other Synthetics' },
      { id: 'QuadX', name: 'QuadX', badge: 'QX', color: '#7e57c2', group: 'Other', category: 'Other Synthetics' },
    ]
  }
];

const ALL_SYMBOLS = WATCHLIST_GROUPS.flatMap(g => g.symbols.map(s => s.id));
const ALL_SYMBOLS_MAP: Record<string, SymbolItem> = WATCHLIST_GROUPS.flatMap(g => g.symbols).reduce((acc, s) => {
  acc[s.id] = s;
  acc[s.name] = s;
  return acc;
}, {} as Record<string, SymbolItem>);

const SYMBOL_CATEGORIES = [
  'ALL',
  'GainX',
  'PainX',
  'FlipX',
  'SFX Vol',
  'FX Vol',
  'BreakX',
  'SwitchX',
  'TrendX',
  'Other'
];
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

// ─────────────────────────────────────────────────────────────────────────────
// Synthesized Audio & Voice Alerts for TP Hit, Fills, and Price Levels
// ─────────────────────────────────────────────────────────────────────────────
function playTone(freq = 587.33, type: OscillatorType = 'sine', duration = 0.2, startTime = 0) {
  try {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime + startTime);
    gain.gain.setValueAtTime(0.2, ctx.currentTime + startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + startTime + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime + startTime);
    osc.stop(ctx.currentTime + startTime + duration);
  } catch (e) {
    // Ignore audio context restrictions
  }
}

// 2-Tone Ascending Success Chime (D5 -> A5)
export function playChime() {
  playTone(587.33, 'triangle', 0.18, 0);
  playTone(880.00, 'triangle', 0.35, 0.14);
}

// Dedicated Suggester Audio Notification (Crisp metallic 3-bell chime)
const suggesterAudio = typeof Audio !== 'undefined' ? new Audio('/suggestion_alert.wav') : null;
if (suggesterAudio) {
  suggesterAudio.preload = 'auto';
}

export function playSuggesterAlertAudio() {
  try {
    if (suggesterAudio) {
      suggesterAudio.currentTime = 0;
      suggesterAudio.volume = 0.85;
      const promise = suggesterAudio.play();
      if (promise !== undefined) {
        promise.catch(() => {
          playTone(659.25, 'sine', 0.22, 0.35);
          setTimeout(() => playTone(880.00, 'sine', 0.25, 0.35), 110);
          setTimeout(() => playTone(1318.51, 'sine', 0.35, 0.35), 230);
        });
      }
    } else {
      playTone(659.25, 'sine', 0.22, 0.35);
      setTimeout(() => playTone(880.00, 'sine', 0.25, 0.35), 110);
      setTimeout(() => playTone(1318.51, 'sine', 0.35, 0.35), 230);
    }
  } catch (e) {
    console.warn('Suggester audio play exception', e);
  }
}

// User-Uploaded Custom "Order filled" Audio Sound Effect
const orderFilledAudio = typeof Audio !== 'undefined' ? new Audio('/order_filled.mp3') : null;
if (orderFilledAudio) {
  orderFilledAudio.preload = 'auto';
}

export function playOrderFilledAudio() {
  try {
    if (orderFilledAudio) {
      orderFilledAudio.currentTime = 0;
      const promise = orderFilledAudio.play();
      if (promise !== undefined) {
        promise.catch(err => console.warn('Order filled audio play error:', err));
      }
    }
  } catch (e) {
    console.warn('Audio play exception', e);
  }
}

// Speak text clearly via Web SpeechSynthesis API
export function speakText(text: string) {
  try {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  } catch (e) {
    console.warn('Speech synthesis error', e);
  }
}

export interface PriceAlert {
  id: string;
  symbol: string;
  targetPrice: number;
  condition: 'above' | 'below';
  label: string;
  active: boolean;
  createdAt: number;
}

export interface AlertToast {
  id: number;
  title: string;
  message: string;
  time: string;
  type: 'success' | 'info' | 'danger';
}

export interface TriggeredAlert {
  id: number;
  title: string;
  symbol: string;
  detail: string;
  time: string;
  kind: 'tp' | 'sl' | 'price' | 'fill';
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

  const [openTabs, setOpenTabs] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('weltrade_open_tabs');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch (e) {}
    return ['SFX_Vol_40', 'GainX_400', 'PainX_400', 'FlipX_1', 'FX_Vol_20'];
  });

  const [searchCategory, setSearchCategory] = useState<string>('ALL');
  const [collapsedCategories, setCollapsedCategories] = useState<Record<string, boolean>>({});

  const setSymbol = (sym: string) => {
    setSymbolState(sym);
    localStorage.setItem('lastSymbol', sym);
    const url = new URL(window.location.href);
    url.searchParams.set('s', sym);
    window.history.replaceState({}, '', url.toString());
    setSearchOpen(false);

    setOpenTabs(prev => {
      if (prev.includes(sym)) return prev;
      const next = [...prev, sym];
      try { localStorage.setItem('weltrade_open_tabs', JSON.stringify(next)); } catch (e) {}
      return next;
    });
  };

  const closeTab = (e: React.MouseEvent, symToClose: string) => {
    e.stopPropagation();
    if (openTabs.length <= 1) return;
    const nextTabs = openTabs.filter(s => s !== symToClose);
    setOpenTabs(nextTabs);
    try { localStorage.setItem('weltrade_open_tabs', JSON.stringify(nextTabs)); } catch (e) {}
    if (symbol === symToClose) {
      const nextActive = nextTabs[nextTabs.length - 1];
      setSymbol(nextActive);
    }
  };

  const toggleCategoryCollapse = (cat: string) => {
    setCollapsedCategories(prev => ({
      ...prev,
      [cat]: !prev[cat]
    }));
  };

  const setTimeframe = (tf: string) => {
    setTimeframeState(tf);
    localStorage.setItem('lastTimeframe', tf);
    const url = new URL(window.location.href);
    url.searchParams.set('tf', tf);
    window.history.replaceState({}, '', url.toString());
  };

  const [showVolume, setShowVolume] = useState(true);
  const [showMarketStructure, setShowMarketStructure] = useState(true);
  const [indicatorsMenuOpen, setIndicatorsMenuOpen] = useState(false);
  const [layoutMode, setLayoutMode] = useState<'single' | 'dual'>(() => {
    return localStorage.getItem('weltrade_layout_mode') === 'dual' ? 'dual' : 'single';
  });
  const [htfTimeframe, setHtfTimeframe] = useState('H1');
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeRightTab, setActiveRightTab] = useState<'watchlist' | 'alerts' | 'notifications' | null>(null);
  const [showTerminal, setShowTerminal] = useState(false);
  const [terminalTab, setTerminalTab] = useState<'positions' | 'orders' | 'history' | 'radar' | 'suggester'>('suggester');
  const [scannerSignals, setScannerSignals] = useState<any[]>([]);
  const [scannerLoading, setScannerLoading] = useState<boolean>(false);
  const [showBacktestModal, setShowBacktestModal] = useState<boolean>(false);
  const [backtestProofData, setBacktestProofData] = useState<any>(null);
  const [suggestedTrade, setSuggestedTrade] = useState<{ kind: 'long-position' | 'short-position'; entry: number; sl: number; tp: number; id?: string; symbol?: string; name?: string; shelf_level?: number; obstacle_1?: number; rrr?: number; risk_usd?: number; reward_usd?: number } | null>(null);
  const [prevConfirmedCount, setPrevConfirmedCount] = useState<number>(0);
  const [radarSearchQuery, setRadarSearchQuery] = useState('');
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

  // Voice & Audio Alerts ("Order filled" on TP Hit & Price Triggers)
  const [voiceAlertsEnabled, setVoiceAlertsEnabled] = useState(() => {
    return localStorage.getItem('weltrade_voice_alerts') !== 'false';
  });
  const [soundAlertsEnabled, setSoundAlertsEnabled] = useState(() => {
    return localStorage.getItem('weltrade_sound_alerts') !== 'false';
  });
  const [priceAlerts, setPriceAlerts] = useState<PriceAlert[]>(() => {
    try {
      const saved = localStorage.getItem('weltrade_price_alerts');
      return saved ? JSON.parse(saved) : [];
    } catch (e) { return []; }
  });
  const [newAlertPrice, setNewAlertPrice] = useState('');
  const [newAlertCondition, setNewAlertCondition] = useState<'above' | 'below'>('above');
  const [newAlertLabel, setNewAlertLabel] = useState('');
  const [alertToasts, setAlertToasts] = useState<AlertToast[]>([]);
  const [triggeredAlerts, setTriggeredAlerts] = useState<TriggeredAlert[]>([]);
  const prevPositionsRef = useRef<Record<number, MT5Position>>({});
  const hasInitializedPositionsRef = useRef(false);

  useEffect(() => {
    if (alertToasts.length === 0) return;
    const timer = setTimeout(() => {
      setAlertToasts(prev => prev.slice(0, prev.length - 1));
    }, 6000);
    return () => clearTimeout(timer);
  }, [alertToasts]);

  const handleCreatePriceAlert = () => {
    const p = parseFloat(newAlertPrice);
    if (!p || isNaN(p) || p <= 0) {
      alert("Please enter a valid price for the alert.");
      return;
    }
    const alertItem: PriceAlert = {
      id: `alert_${Date.now()}`,
      symbol,
      targetPrice: p,
      condition: newAlertCondition,
      label: newAlertLabel.trim(),
      active: true,
      createdAt: Date.now()
    };
    const nextAlerts = [alertItem, ...priceAlerts];
    setPriceAlerts(nextAlerts);
    try { localStorage.setItem('weltrade_price_alerts', JSON.stringify(nextAlerts)); } catch (e) {}
    setNewAlertPrice('');
    setNewAlertLabel('');
    if (soundAlertsEnabled) playTone(440, 'triangle', 0.15);
  };

  const handleDeletePriceAlert = (id: string) => {
    const nextAlerts = priceAlerts.filter(a => a.id !== id);
    setPriceAlerts(nextAlerts);
    try { localStorage.setItem('weltrade_price_alerts', JSON.stringify(nextAlerts)); } catch (e) {}
  };

    // 100-Question Rule-Based Sniper Scanner & Suggester
  const fetchScannerSignals = useCallback(async (force = false) => {
    try {
      setScannerLoading(true);
      const res = await fetch(`http://127.0.0.1:8000/scanner/signals?force_refresh=${force}`);
      if (res.ok) {
        const data = await res.json();
        const sigs = data.signals || [];
        setScannerSignals(sigs);

        const confirmed = sigs.filter((s: any) => s.status === 'CONFIRMED SIGNAL').length;
        if (confirmed > prevConfirmedCount && soundAlertsEnabled) {
          playSuggesterAlertAudio();
        }
        setPrevConfirmedCount(confirmed);
      }
    } catch (e) {
      console.warn('Failed to fetch scanner signals:', e);
    } finally {
      setScannerLoading(false);
    }
  }, [soundAlertsEnabled, prevConfirmedCount]);

  const fetchBacktestProof = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/scanner/backtest_proof');
      if (res.ok) {
        const data = await res.json();
        setBacktestProofData(data);
        setShowBacktestModal(true);
      }
    } catch (e) {
      console.warn('Failed to fetch backtest proof:', e);
    }
  }, []);

  const handleLoadTradePlan = (sig: any) => {
    setSymbol(sig.symbol);
    setTimeframe('M15');
    const isBuy = sig.direction === 'BUY';
    setSuggestedTrade({
      id: `plan-${sig.symbol}-${Date.now()}`,
      kind: isBuy ? 'long-position' : 'short-position',
      entry: Number(sig.entry),
      sl: Number(sig.sl),
      tp: Number(sig.tp),
      symbol: sig.symbol,
      name: sig.name,
      shelf_level: Number(sig.shelf_level),
      obstacle_1: Number(sig.obstacle_1),
      rrr: Number(sig.rrr)
    });
    playSuggesterAlertAudio();
    setShowTerminal(false);
  };

  useEffect(() => {
    fetchScannerSignals(true);
  }, []);

  useEffect(() => {
    if (showTerminal && terminalTab === 'suggester') {
      const interval = setInterval(() => {
        fetchScannerSignals(false);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [showTerminal, terminalTab, fetchScannerSignals]);

  // Auto-Position Guardian (Breakeven & M5 Swing Trailing Ratchet)
  const [guardianEnabled, setGuardianEnabled] = useState(true);
  const [guardianLoading, setGuardianLoading] = useState(false);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/guardian/status')
      .then(res => res.json())
      .then(data => {
        if (typeof data.enabled === 'boolean') {
          setGuardianEnabled(data.enabled);
        }
      })
      .catch(() => {});
  }, []);

  const toggleGuardian = async () => {
    if (guardianLoading) return;
    setGuardianLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/guardian/toggle', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setGuardianEnabled(!!data.enabled);
      }
    } catch (e) {
      console.error('Failed to toggle Position Guardian:', e);
    } finally {
      setGuardianLoading(false);
    }
  };

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
  const [targetLogin, setTargetLogin] = useState('34967194');
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

          // Check live price alerts
          setPriceAlerts(existingAlerts => {
            let triggeredCount = 0;
            const updated = existingAlerts.map(a => {
              if (!a.active || a.symbol !== item.symbol) return a;
              const hit = (a.condition === 'above' && item.price >= a.targetPrice) ||
                          (a.condition === 'below' && item.price <= a.targetPrice);
              if (hit) {
                triggeredCount++;
                if (voiceAlertsEnabled) {
                  speakText(`Price alert: ${a.symbol.replace(/_/g, ' ')} reached ${a.targetPrice}`);
                }
                if (soundAlertsEnabled) {
                  playChime();
                }
                setAlertToasts(toasts => [{
                  id: Date.now() + Math.random(),
                  title: "🔔 Price Alert Triggered!",
                  message: `${a.symbol.replace(/_/g, ' ')} ${a.condition === 'above' ? 'rose above' : 'dropped below'} ${a.targetPrice}`,
                  time: new Date().toLocaleTimeString(),
                  type: 'info'
                }, ...toasts.slice(0, 4)]);
                setTriggeredAlerts(t => [{
                  id: Date.now() + Math.random(),
                  title: `Price Alert: ${a.symbol.replace(/_/g, ' ')} @ ${a.targetPrice}`,
                  symbol: a.symbol,
                  detail: a.label || `Target ${a.condition === 'above' ? '≥' : '≤'} ${a.targetPrice} hit`,
                  time: new Date().toLocaleTimeString(),
                  kind: 'price'
                }, ...t]);
                return { ...a, active: false };
              }
              return a;
            });
            if (triggeredCount > 0) {
              try { localStorage.setItem('weltrade_price_alerts', JSON.stringify(updated)); } catch (e) {}
            }
            return updated;
          });
        }
      }
      return next;
    });
  }, [voiceAlertsEnabled, soundAlertsEnabled]);

  const isFetchingRef = useRef(false);
  const lastHistoryFetchRef = useRef(0);

  // Poll MT5 account, positions, pending orders, and history safely
  const fetchMt5 = useCallback(async (forceHistory = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      const now = Date.now();
      const shouldFetchHistory = forceHistory || (now - lastHistoryFetchRef.current > 8000) || terminalTab === 'history';

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
      if (ordRes && ordRes.ok) setPendingOrders(await ordRes.json());
      
      let fetchedHistory: any[] | null = null;
      if (histRes && histRes.ok) {
        fetchedHistory = await histRes.json();
        setHistory(fetchedHistory || []);
        lastHistoryFetchRef.current = now;
      }

      if (posRes && posRes.ok) {
        const newPos: MT5Position[] = await posRes.json();
        setPositions(newPos);

        if (!hasInitializedPositionsRef.current) {
          hasInitializedPositionsRef.current = true;
        } else {
          const prevMap = prevPositionsRef.current;

          // 1. Detect when a Trade Starts (BuyStop, SellStop, Limit hits or new Market fill!)
          for (const p of newPos) {
            if (!prevMap[p.ticket]) {
              // ⚡ ORDER FILLED: A trade has started!
              if (soundAlertsEnabled) {
                playOrderFilledAudio();
              }
              setAlertToasts(prev => [{
                id: Date.now() + Math.random(),
                title: "⚡ ORDER FILLED: Trade Started",
                message: `#${p.ticket} ${p.symbol} • ${p.type.toUpperCase()} ${p.volume.toFixed(2)} @ ${p.price_open.toFixed(2)}`,
                time: new Date().toLocaleTimeString(),
                type: 'success'
              }, ...prev.slice(0, 4)]);
              setTriggeredAlerts(prev => [{
                id: Date.now() + Math.random(),
                title: `Order Filled: ${p.type} ${p.symbol}`,
                symbol: p.symbol,
                detail: `#${p.ticket} triggered & filled @ ${p.price_open.toFixed(2)} (Vol: ${p.volume.toFixed(2)})`,
                time: new Date().toLocaleTimeString(),
                kind: 'fill'
              }, ...prev]);
            }
          }

          // 2. Detect when an active trade closes (TP or SL)
          if (prevMap && Object.keys(prevMap).length > 0) {
            for (const tStr of Object.keys(prevMap)) {
              const ticket = Number(tStr);
              const wasOpen = prevMap[ticket];
              const isStillOpen = newPos.some(p => p.ticket === ticket);

              if (!isStillOpen) {
                // Position closed! Fetch latest history if not yet loaded
                let histSource = fetchedHistory;
                if (!histSource) {
                  try {
                    const hRes = await fetch('http://127.0.0.1:8000/history');
                    if (hRes.ok) {
                      histSource = await hRes.json();
                      setHistory(histSource || []);
                    }
                  } catch (e) {}
                }

                const closedDeal = histSource?.find((h: any) => h.ticket === ticket || h.ticket === wasOpen.ticket);
                const profit = closedDeal ? closedDeal.profit : 0;
                const comment = closedDeal?.comment?.toLowerCase() || '';
                const isTpHit = comment.includes('tp') || (wasOpen.tp > 0 && profit > 0);

                if (isTpHit || profit > 0) {
                  // Take Profit reached: play success chime (old "Order filled" speech removed)
                  if (soundAlertsEnabled) {
                    playChime();
                  }
                  setAlertToasts(prev => [{
                    id: Date.now() + Math.random(),
                    title: "🎯 TAKE PROFIT HIT: Trade Won",
                    message: `#${ticket} ${wasOpen.symbol} • Realized Profit +$${profit.toFixed(2)}`,
                    time: new Date().toLocaleTimeString(),
                    type: 'success'
                  }, ...prev.slice(0, 4)]);
                  setTriggeredAlerts(prev => [{
                    id: Date.now() + Math.random(),
                    title: `Take Profit Hit (#${ticket})`,
                    symbol: wasOpen.symbol,
                    detail: `${wasOpen.symbol} closed @ profit +$${profit.toFixed(2)}`,
                    time: new Date().toLocaleTimeString(),
                    kind: 'tp'
                  }, ...prev]);
                } else {
                  if (soundAlertsEnabled) {
                    playTone(320, 'sine', 0.25);
                  }
                  setAlertToasts(prev => [{
                    id: Date.now() + Math.random(),
                    title: "Position Closed",
                    message: `#${ticket} ${wasOpen.symbol} closed. PnL: $${profit.toFixed(2)}`,
                    time: new Date().toLocaleTimeString(),
                    type: 'info'
                  }, ...prev.slice(0, 4)]);
                }
              }
            }
          }
        }

        const nextMap: Record<number, MT5Position> = {};
        for (const p of newPos) {
          nextMap[p.ticket] = p;
        }
        prevPositionsRef.current = nextMap;
      }
    } catch (e) {
      // Backend offline / loading
    } finally {
      isFetchingRef.current = false;
    }
  }, [terminalTab, voiceAlertsEnabled, soundAlertsEnabled]);

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
        if (data.account) {
          setAccount(data.account);
        }
        await fetchMt5(true);
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
    if (comment && (comment.toLowerCase().includes('stop') || comment.toLowerCase().includes('limit') || comment.toLowerCase().includes('armed'))) {
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

  // Filtered symbols for search modal with category tabs and fast fuzzy matching
  const filteredSymbols = WATCHLIST_GROUPS.flatMap(g => g.symbols).filter(s => {
    const matchesCat = searchCategory === 'ALL' || s.group === searchCategory;
    if (!matchesCat) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().replace(/_/g, ' ').trim();
    const sName = s.name.toLowerCase();
    const sId = s.id.toLowerCase().replace(/_/g, ' ');
    const sCat = s.category.toLowerCase();
    return sName.includes(q) || sId.includes(q) || sCat.includes(q);
  });

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

        {/* Indicators Dropdown Button */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setIndicatorsMenuOpen(prev => !prev)}
            style={{
              background: indicatorsMenuOpen ? 'var(--tv-bg-hover)' : 'transparent',
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
            title="Indicators & Market Structure"
          >
            <span style={{ color: 'var(--tv-accent)', fontWeight: 'bold' }}>fx</span>
            <span>Indicators</span>
            <ChevronDown size={12} color="var(--tv-text-secondary)" />
          </button>

          {/* Indicators Popover Menu */}
          {indicatorsMenuOpen && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              marginTop: '4px',
              width: '230px',
              backgroundColor: 'var(--tv-bg-secondary)',
              border: '1px solid var(--tv-border)',
              borderRadius: '6px',
              padding: '6px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              zIndex: 100,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div
                onClick={() => setShowMarketStructure(prev => !prev)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '7px 10px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  backgroundColor: showMarketStructure ? 'rgba(8,153,129,0.12)' : 'transparent',
                  color: showMarketStructure ? 'var(--tv-up)' : 'var(--tv-text-secondary)',
                  fontSize: '12px',
                  fontWeight: 600
                }}
              >
                <span>Structure (HH/HL/LL & BOS)</span>
                <span style={{ fontSize: '11px', color: showMarketStructure ? 'var(--tv-up)' : 'var(--tv-text-muted)' }}>
                  {showMarketStructure ? 'ON' : 'OFF'}
                </span>
              </div>

              <div
                onClick={() => setShowVolume(prev => !prev)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '7px 10px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  backgroundColor: showVolume ? 'rgba(41,98,255,0.12)' : 'transparent',
                  color: showVolume ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                  fontSize: '12px',
                  fontWeight: 600
                }}
              >
                <span>Volume Histogram</span>
                <span style={{ fontSize: '11px', color: showVolume ? 'var(--tv-accent)' : 'var(--tv-text-muted)' }}>
                  {showVolume ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Compact Layout Toggle Button */}
        <button
          onClick={() => {
            const nextMode = layoutMode === 'single' ? 'dual' : 'single';
            setLayoutMode(nextMode);
            localStorage.setItem('weltrade_layout_mode', nextMode);
          }}
          style={{
            background: layoutMode === 'dual' ? 'rgba(41, 98, 255, 0.18)' : 'transparent',
            border: layoutMode === 'dual' ? '1px solid var(--tv-accent)' : '1px solid transparent',
            color: layoutMode === 'dual' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
            padding: '5px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            fontSize: '12px',
            fontWeight: 600,
            transition: 'all 0.15s ease'
          }}
          title={layoutMode === 'dual' ? "Multi-Chart: Dual Active (Click to switch to 1-Chart)" : "Multi-Chart: Click to Split Screen (HTF + LTF)"}
        >
          <Columns size={14} />
          <span>{layoutMode === 'dual' ? 'Dual' : 'Split'}</span>
        </button>

        {/* 100Q Suggester Quick Access Button */}
        <button
          onClick={() => {
            setShowTerminal(true);
            setTerminalTab('suggester');
            fetchScannerSignals(true);
          }}
          style={{
            background: terminalTab === 'suggester' && showTerminal ? 'rgba(8, 153, 129, 0.22)' : 'rgba(255, 255, 255, 0.04)',
            border: terminalTab === 'suggester' && showTerminal ? '1px solid #089981' : '1px solid #2a2e39',
            color: '#089981',
            padding: '5px 9px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: 700,
            transition: 'all 0.15s ease'
          }}
          title="Open 100-Question Rule-Based Trade Suggester (11 Synthetics)"
        >
          <Target size={14} color="#089981" />
          <span>🎯 Suggester (11)</span>
          {scannerSignals.filter(s => s.status === 'CONFIRMED SIGNAL').length > 0 && (
            <span style={{
              backgroundColor: '#089981',
              color: '#fff',
              borderRadius: '10px',
              padding: '1px 5px',
              fontSize: '10px',
              fontWeight: 800,
              boxShadow: '0 0 6px #089981'
            }}>
              {scannerSignals.filter(s => s.status === 'CONFIRMED SIGNAL').length} LIVE
            </span>
          )}
        </button>

        {/* Alert Button (TradingView Style) */}
        <button
          onClick={() => setActiveRightTab(prev => prev === 'alerts' ? null : 'alerts')}
          style={{
            background: activeRightTab === 'alerts' ? 'var(--tv-accent-bg)' : 'transparent',
            border: 'none',
            color: activeRightTab === 'alerts' ? 'var(--tv-accent)' : 'var(--tv-text-primary)',
            padding: '6px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            fontSize: '13px',
            fontWeight: 500,
            transition: 'background-color 0.15s'
          }}
          onMouseEnter={(e) => {
            if (activeRightTab !== 'alerts') e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)';
          }}
          onMouseLeave={(e) => {
            if (activeRightTab !== 'alerts') e.currentTarget.style.backgroundColor = 'transparent';
          }}
          title="Create Alert"
        >
          <Clock size={15} color="var(--tv-text-secondary)" />
          <span>Alert</span>
        </button>

        {/* Undo / Redo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px', marginLeft: '4px' }}>
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-muted)', padding: '5px', cursor: 'pointer' }} title="Undo">
            <RotateCcw size={15} />
          </button>
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-muted)', padding: '5px', cursor: 'pointer' }} title="Redo">
            <RotateCw size={15} />
          </button>
        </div>

        {/* Right side controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {/* Layout Name with Cloud Saved Indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'background-color 0.15s'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          title="Layout saved automatically"
          >
            <span style={{ fontSize: '13px', color: 'var(--tv-text-primary)', fontWeight: 600 }}>
              Weltrade Synthetics
            </span>
            <Cloud size={14} color="#089981" />
            <span style={{ fontSize: '10px', color: '#089981', fontWeight: 600 }}>Saved</span>
            <ChevronDown size={12} color="var(--tv-text-muted)" />
          </div>

          {/* Auto-Position Guardian Switch (Auto-BE at +1.8R & M5 Swing Trail at +2.0R) */}
          <div
            onClick={toggleGuardian}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#181b27',
              border: `1px solid ${guardianEnabled ? '#089981' : 'var(--tv-border)'}`,
              borderRadius: '16px',
              padding: '3px 8px 3px 5px',
              cursor: guardianLoading ? 'wait' : 'pointer',
              userSelect: 'none',
              boxShadow: guardianEnabled ? '0 0 10px rgba(8, 153, 129, 0.25)' : 'none',
              transition: 'all 0.2s ease-in-out'
            }}
            title={guardianEnabled ? "Position Guardian ON: Auto-locks Breakeven at +1.8R & trails M5 swings at +2.0R" : "Position Guardian OFF (Click to enable Auto-BE protection)"}
          >
            <div style={{
              width: '28px',
              height: '16px',
              borderRadius: '9px',
              backgroundColor: guardianEnabled ? '#089981' : '#363c4e',
              position: 'relative',
              transition: 'background-color 0.2s ease-in-out'
            }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: '#fff',
                position: 'absolute',
                top: '2px',
                left: guardianEnabled ? '14px' : '2px',
                transition: 'left 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                boxShadow: '0 1px 3px rgba(0,0,0,0.4)'
              }} />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Shield size={12} color={guardianEnabled ? '#089981' : '#787b86'} />
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                color: guardianEnabled ? '#089981' : '#787b86',
                letterSpacing: '0.3px'
              }}>
                {guardianEnabled ? 'GUARDIAN BE' : 'GUARDIAN OFF'}
              </span>
            </div>
          </div>

          {/* Weltrade Safe Box Button */}
          <button
            onClick={() => setWeltradeModalOpen(true)}
            style={{
              backgroundColor: 'transparent',
              color: '#089981',
              border: '1px solid rgba(8, 153, 129, 0.45)',
              borderRadius: '4px',
              padding: '4px 8px',
              fontWeight: 600,
              fontSize: '11px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'background-color 0.15s ease'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(8, 153, 129, 0.12)')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            title="Open Weltrade Safe Vault & Cabinet (Zero-Fee Internal Transfers)"
          >
            <Shield size={13} />
            <span>Safe Vault</span>
          </button>

          {/* Settings */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '5px', cursor: 'pointer' }} title="Chart settings">
            <Settings size={17} />
          </button>

          {/* Fullscreen */}
          <button
            onClick={() => {
              if (!document.fullscreenElement) document.documentElement.requestFullscreen();
              else document.exitFullscreen();
            }}
            style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '5px', cursor: 'pointer' }}
            title="Fullscreen"
          >
            <Maximize2 size={17} />
          </button>

          {/* Snapshot */}
          <button style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', padding: '5px', cursor: 'pointer' }} title="Take screenshot">
            <Camera size={17} />
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

          {/* Arrow */}
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

        {/* Center Chart Container with MT5 Multi-Index Tabs Strip */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          
          {/* Quick MT5 Chart Tabs Strip (Choose which index you want on main chart) */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--tv-bg-primary)',
            borderBottom: '1px solid var(--tv-border)',
            padding: '2px 8px 0 8px',
            overflowX: 'auto',
            scrollbarWidth: 'none',
            gap: '3px',
            height: '34px',
            flexShrink: 0
          }}>
            {openTabs.map(tabSym => {
              const isSelected = symbol === tabSym;
              const symInfo = ALL_SYMBOLS_MAP[tabSym] || { name: tabSym.replace(/_/g, ' '), badge: 'IDX', color: '#2962ff' };
              const tick = watchlist[tabSym];
              return (
                <div
                  key={tabSym}
                  onClick={() => setSymbol(tabSym)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    height: '28px',
                    backgroundColor: isSelected ? 'var(--tv-bg-secondary)' : 'transparent',
                    borderTop: isSelected ? '2px solid var(--tv-accent)' : '2px solid transparent',
                    borderLeft: isSelected ? '1px solid var(--tv-border)' : '1px solid transparent',
                    borderRight: isSelected ? '1px solid var(--tv-border)' : '1px solid transparent',
                    borderRadius: '4px 4px 0 0',
                    cursor: 'pointer',
                    color: isSelected ? 'var(--tv-text-primary)' : 'var(--tv-text-secondary)',
                    fontWeight: isSelected ? 600 : 500,
                    fontSize: '12px',
                    whiteSpace: 'nowrap',
                    userSelect: 'none',
                    transition: 'all 0.15s ease'
                  }}
                  title={`Switch chart to ${symInfo.name}`}
                >
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: symInfo.color,
                    display: 'inline-block',
                    flexShrink: 0
                  }} />
                  <span>{symInfo.name}</span>
                  {tick && (
                    <span style={{
                      fontSize: '11px',
                      color: tick.change_pct >= 0 ? 'var(--tv-bull)' : 'var(--tv-bear)',
                      fontWeight: 600,
                      marginLeft: '2px'
                    }}>
                      {tick.price.toFixed(2)}
                    </span>
                  )}
                  {openTabs.length > 1 && (
                    <span
                      onClick={(e) => closeTab(e, tabSym)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: '16px',
                        height: '16px',
                        borderRadius: '50%',
                        marginLeft: '4px',
                        color: 'var(--tv-text-muted)',
                        cursor: 'pointer',
                        fontSize: '14px',
                        lineHeight: 1
                      }}
                      title={`Close ${symInfo.name} tab`}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = '#fff';
                        e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.15)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--tv-text-muted)';
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      ×
                    </span>
                  )}
                </div>
              );
            })}
            <button
              onClick={() => setSearchOpen(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '26px',
                height: '26px',
                borderRadius: '4px',
                border: 'none',
                backgroundColor: 'transparent',
                color: 'var(--tv-text-secondary)',
                cursor: 'pointer',
                marginLeft: '4px',
                transition: 'background-color 0.15s'
              }}
              title="Add Weltrade index chart (Ctrl+K)"
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--tv-bg-hover)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
            >
              <Plus size={15} />
            </button>
          </div>

          {/* Center Chart Viewport (Single or Dual HTF+LTF Split) */}
          <div style={{ flex: 1, position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'row' }}>
            
            {/* If Dual Layout: Left Chart is HTF Structure (H1 / M30) */}
            {layoutMode === 'dual' && (
              <div style={{ flex: 1, position: 'relative', overflow: 'hidden', borderRight: '2px solid var(--tv-border)' }}>
                {/* HTF Ribbon */}
                <div style={{
                  position: 'absolute', top: 8, left: 12, zIndex: 20,
                  backgroundColor: 'rgba(19, 23, 34, 0.88)', backdropFilter: 'blur(4px)',
                  border: '1px solid var(--tv-border)', borderRadius: '4px',
                  padding: '3px 8px', fontSize: '11px', fontWeight: 700,
                  display: 'flex', alignItems: 'center', gap: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
                }}>
                  <span style={{ color: '#2962ff' }}>HTF STRUCTURE:</span>
                  <select
                    value={htfTimeframe}
                    onChange={(e) => setHtfTimeframe(e.target.value)}
                    style={{ background: '#1e222d', border: '1px solid #2a2e39', borderRadius: '3px', color: '#fff', fontWeight: 700, fontSize: '11px', padding: '1px 4px', cursor: 'pointer' }}
                  >
                    <option value="M15">M15</option>
                    <option value="M30">M30</option>
                    <option value="H1">H1</option>
                    <option value="H4">H4</option>
                  </select>
                </div>

                <ChartComponent
                  symbol={symbol}
                  timeframe={htfTimeframe}
                  showVolume={false}
                  showMarketStructure={true}
                  positions={positions}
                  pendingOrders={pendingOrders}
                />
              </div>
            )}

            {/* Right Execution Chart (LTF: M5 / M1 with Trade Tools) */}
            <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
              {layoutMode === 'dual' && (
                <div style={{
                  position: 'absolute', top: 8, left: 12, zIndex: 20,
                  backgroundColor: 'rgba(19, 23, 34, 0.88)', backdropFilter: 'blur(4px)',
                  border: '1px solid var(--tv-border)', borderRadius: '4px',
                  padding: '3px 8px', fontSize: '11px', fontWeight: 700, color: '#089981',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
                }}>
                  LTF SNIPER ({timeframe})
                </div>
              )}
              <ChartComponent
                symbol={symbol} 
                timeframe={timeframe} 
                showVolume={showVolume}
                showMarketStructure={showMarketStructure}
                activeTool={activeTool} 
                onToolDeactivate={handleToolDeactivate}
                onDrawingsUpdate={handleDrawingsUpdate}
                onTick={handleTick}
                onWatchlistUpdate={handleWatchlistUpdate}
                onOrderSuccess={handleOrderSuccess}
                positions={positions}
                pendingOrders={pendingOrders}
                onCandleAccuracyUpdate={setCandleAccuracy}
                isMagnetOn={isMagnetOn}
                suggestedTrade={suggestedTrade}
              />
            </div>
          </div>
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

            {/* Grouped Watchlist Items (All 41 Weltrade Synthetics) */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {WATCHLIST_GROUPS.map(group => {
                const isCollapsed = !!collapsedCategories[group.category];
                return (
                  <div key={group.category} style={{ borderBottom: '1px solid var(--tv-border-subtle)' }}>
                    <div
                      onClick={() => toggleCategoryCollapse(group.category)}
                      style={{
                        padding: '7px 14px',
                        fontSize: '11px',
                        color: 'var(--tv-text-secondary)',
                        fontWeight: 700,
                        letterSpacing: '0.5px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        backgroundColor: 'rgba(255, 255, 255, 0.02)',
                        userSelect: 'none'
                      }}
                      title="Click to expand/collapse"
                    >
                      <span>{group.category} ({group.symbols.length})</span>
                      <ChevronDown
                        size={13}
                        style={{
                          transform: isCollapsed ? 'rotate(-90deg)' : 'none',
                          transition: 'transform 0.15s ease'
                        }}
                      />
                    </div>

                    {!isCollapsed && group.symbols.map(s => {
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

                          <div style={{
                            flex: 1.2,
                            textAlign: 'right',
                            fontSize: '12px',
                            color: 'var(--tv-text-primary)',
                            fontVariantNumeric: 'tabular-nums'
                          }}>
                            {displayPrice}
                          </div>

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
                );
              })}
            </div>
          </div>
        )}

        {/* Right Alerts & Voice Manager Panel */}
        {activeRightTab === 'alerts' && (
          <div style={{
            width: '320px',
            borderLeft: '1px solid var(--tv-border)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: 'var(--tv-bg-card)',
            zIndex: 10,
            overflowY: 'auto'
          }}>
            {/* Header */}
            <div style={{
              padding: '12px 14px',
              borderBottom: '1px solid var(--tv-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--tv-bg-primary)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Clock size={16} color="var(--tv-accent)" />
                <span style={{ fontWeight: 700, fontSize: '13px', color: '#fff' }}>ALERTS & VOICE</span>
              </div>
              <button
                onClick={() => setActiveRightTab(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-secondary)', cursor: 'pointer', padding: 2 }}
                title="Close Alerts Panel"
              >
                <X size={15} />
              </button>
            </div>

            {/* Voice & Sound Announce Configuration Card */}
            <div style={{
              margin: '12px',
              padding: '12px',
              backgroundColor: '#181b27',
              borderRadius: '6px',
              border: '1px solid #2a2e39',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#fff' }}>"Order Filled" Sound Effect</div>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-secondary)' }}>Plays uploaded audio when trade starts (BuyStop/SellStop/Limit)</div>
                </div>
                <button
                  onClick={() => {
                    const next = !soundAlertsEnabled;
                    setSoundAlertsEnabled(next);
                    localStorage.setItem('weltrade_sound_alerts', String(next));
                  }}
                  style={{
                    background: soundAlertsEnabled ? 'rgba(8,153,129,0.2)' : 'rgba(255,255,255,0.06)',
                    color: soundAlertsEnabled ? '#089981' : 'var(--tv-text-muted)',
                    border: `1px solid ${soundAlertsEnabled ? '#089981' : '#363a45'}`,
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {soundAlertsEnabled ? 'ON' : 'OFF'}
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#fff' }}>Voice Price Announcer</div>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-secondary)' }}>Announce when target price is crossed</div>
                </div>
                <button
                  onClick={() => {
                    const next = !voiceAlertsEnabled;
                    setVoiceAlertsEnabled(next);
                    localStorage.setItem('weltrade_voice_alerts', String(next));
                  }}
                  style={{
                    background: voiceAlertsEnabled ? 'rgba(41,98,255,0.2)' : 'rgba(255,255,255,0.06)',
                    color: voiceAlertsEnabled ? 'var(--tv-accent)' : 'var(--tv-text-muted)',
                    border: `1px solid ${voiceAlertsEnabled ? 'var(--tv-accent)' : '#363a45'}`,
                    borderRadius: '4px',
                    padding: '3px 8px',
                    fontSize: '11px',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {voiceAlertsEnabled ? 'ON' : 'OFF'}
                </button>
              </div>

              {/* Test Audio Button */}
              <button
                onClick={() => {
                  playOrderFilledAudio();
                  setAlertToasts(prev => [{
                    id: Date.now() + Math.random(),
                    title: "⚡ Audio Test: Order Filled",
                    message: "Custom 'Order filled' audio played on your speakers.",
                    time: new Date().toLocaleTimeString(),
                    type: 'success'
                  }, ...prev.slice(0, 4)]);
                }}
                style={{
                  marginTop: '4px',
                  background: 'rgba(8, 153, 129, 0.15)',
                  color: '#089981',
                  border: '1px solid rgba(8, 153, 129, 0.35)',
                  borderRadius: '4px',
                  padding: '7px 10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <Volume2 size={14} />
                <span>Test "Order Filled" Audio</span>
              </button>
            </div>

            {/* Create Price Alert Card */}
            <div style={{
              margin: '0 12px 12px 12px',
              padding: '12px',
              backgroundColor: '#181b27',
              borderRadius: '6px',
              border: '1px solid #2a2e39',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#fff' }}>
                Create Price Alert on {symbol.replace(/_/g, ' ')}
              </div>

              <div style={{ display: 'flex', gap: '6px' }}>
                <input
                  type="number"
                  placeholder="Target Price..."
                  value={newAlertPrice}
                  onChange={(e) => setNewAlertPrice(e.target.value)}
                  style={{
                    flex: 1,
                    background: '#131722',
                    border: '1px solid #363a45',
                    borderRadius: '4px',
                    padding: '5px 8px',
                    color: '#fff',
                    fontSize: '11px'
                  }}
                />
                <select
                  value={newAlertCondition}
                  onChange={(e: any) => setNewAlertCondition(e.target.value)}
                  style={{
                    background: '#131722',
                    border: '1px solid #363a45',
                    borderRadius: '4px',
                    padding: '5px 8px',
                    color: '#fff',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  <option value="above">≥ Crosses Above</option>
                  <option value="below">≤ Crosses Below</option>
                </select>
              </div>

              <input
                type="text"
                placeholder="Alert Label (e.g. Structure High Breakout)"
                value={newAlertLabel}
                onChange={(e) => setNewAlertLabel(e.target.value)}
                style={{
                  background: '#131722',
                  border: '1px solid #363a45',
                  borderRadius: '4px',
                  padding: '5px 8px',
                  color: '#fff',
                  fontSize: '11px'
                }}
              />

              <button
                onClick={handleCreatePriceAlert}
                style={{
                  background: 'var(--tv-accent)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                + Set Price Alert
              </button>
            </div>

            {/* Active Price Alerts */}
            <div style={{ padding: '0 12px 12px 12px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--tv-text-secondary)', marginBottom: '6px' }}>
                ACTIVE PRICE ALERTS ({priceAlerts.filter(a => a.active).length})
              </div>
              {priceAlerts.filter(a => a.active).length === 0 ? (
                <div style={{ fontSize: '11px', color: 'var(--tv-text-muted)', fontStyle: 'italic', padding: '6px 0' }}>
                  No pending price alerts.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {priceAlerts.filter(a => a.active).map(a => (
                    <div key={a.id} style={{
                      background: '#181b27',
                      border: '1px solid #2a2e39',
                      borderRadius: '4px',
                      padding: '6px 8px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, color: '#fff' }}>
                          {a.symbol.replace(/_/g, ' ')} {a.condition === 'above' ? '≥' : '≤'} {a.targetPrice.toFixed(2)}
                        </div>
                        {a.label && <div style={{ fontSize: '10px', color: 'var(--tv-text-secondary)' }}>{a.label}</div>}
                      </div>
                      <button
                        onClick={() => handleDeletePriceAlert(a.id)}
                        style={{ background: 'transparent', border: 'none', color: '#f23645', cursor: 'pointer', padding: 2 }}
                        title="Delete Alert"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Triggered Events History */}
            <div style={{ padding: '0 12px 12px 12px', borderTop: '1px solid var(--tv-border)', paddingTop: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--tv-text-secondary)' }}>
                  TRIGGERED EVENTS ({triggeredAlerts.length})
                </span>
                {triggeredAlerts.length > 0 && (
                  <button
                    onClick={() => setTriggeredAlerts([])}
                    style={{ background: 'transparent', border: 'none', color: 'var(--tv-text-muted)', fontSize: '10px', cursor: 'pointer' }}
                  >
                    Clear
                  </button>
                )}
              </div>

              {triggeredAlerts.length === 0 ? (
                <div style={{ fontSize: '11px', color: 'var(--tv-text-muted)', fontStyle: 'italic', padding: '6px 0' }}>
                  No fills or triggered alerts yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '180px', overflowY: 'auto' }}>
                  {triggeredAlerts.map(t => (
                    <div key={t.id} style={{
                      background: t.kind === 'tp' ? 'rgba(8,153,129,0.1)' : 'rgba(255,255,255,0.03)',
                      borderLeft: `3px solid ${t.kind === 'tp' ? '#089981' : 'var(--tv-accent)'}`,
                      padding: '6px 8px',
                      borderRadius: '3px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: t.kind === 'tp' ? '#089981' : '#fff' }}>
                          {t.title}
                        </span>
                        <span style={{ fontSize: '9px', color: 'var(--tv-text-muted)' }}>{t.time}</span>
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--tv-text-secondary)', marginTop: '2px' }}>
                        {t.detail}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Far-Right Slim Navigation Rail */}
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
            title="Alerts & Voice (Toggle Panel)"
          >
            <Clock size={18} />
          </button>

          {/* Multi-Screen Split Button on Side Bar */}
          <button
            onClick={() => {
              const nextMode = layoutMode === 'single' ? 'dual' : 'single';
              setLayoutMode(nextMode);
              localStorage.setItem('weltrade_layout_mode', nextMode);
            }}
            style={{
              background: layoutMode === 'dual' ? 'rgba(41, 98, 255, 0.2)' : 'transparent',
              color: layoutMode === 'dual' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
              border: layoutMode === 'dual' ? '1px solid var(--tv-accent)' : 'none',
              padding: '8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.15s ease'
            }}
            title={layoutMode === 'dual' ? "Multi-Screen Active: Click to return to Single Chart" : "Split Screen: Dual HTF Structure + LTF Sniper"}
          >
            <Columns size={18} />
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
              onClick={() => {
                setTerminalTab('suggester');
                fetchScannerSignals(true);
              }}
              style={{
                padding: '8px 16px',
                background: terminalTab === 'suggester' ? 'rgba(8, 153, 129, 0.12)' : 'transparent',
                border: 'none',
                color: terminalTab === 'suggester' ? '#089981' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'suggester' ? '2px solid #089981' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>🎯 100Q Sniper Suggester (11)</span>
              {scannerSignals.filter(s => s.status === 'CONFIRMED SIGNAL').length > 0 ? (
                <span style={{
                  backgroundColor: '#089981',
                  color: '#fff',
                  borderRadius: '10px',
                  padding: '1px 6px',
                  fontSize: '10px',
                  fontWeight: 700,
                  boxShadow: '0 0 6px #089981'
                }}>
                  {scannerSignals.filter(s => s.status === 'CONFIRMED SIGNAL').length} LIVE
                </span>
              ) : (
                <span style={{
                  backgroundColor: 'rgba(255,255,255,0.08)',
                  color: 'var(--tv-text-secondary)',
                  borderRadius: '10px',
                  padding: '1px 5px',
                  fontSize: '10px'
                }}>
                  11
                </span>
              )}
            </button>
            <button
              onClick={() => setTerminalTab('radar')}
              style={{
                padding: '8px 16px',
                background: 'transparent',
                border: 'none',
                color: terminalTab === 'radar' ? 'var(--tv-accent)' : 'var(--tv-text-secondary)',
                borderBottom: terminalTab === 'radar' ? '2px solid var(--tv-accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <span>⚡ Synthetics Radar (41)</span>
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
                        No active pending orders (Buy Stop / Sell Stop / Limit / On Close).
                      </td>
                    </tr>
                  ) : (
                    pendingOrders.map(o => {
                      const isStop = o.type.toLowerCase().includes('stop');
                      const isClose = o.type.toLowerCase().includes('close');
                      const isBuy = o.type.toLowerCase().includes('buy');
                      const badgeColor = isClose ? '#ff9800' : isStop ? (isBuy ? '#089981' : '#f23645') : '#2962ff';
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
                              {isClose ? `⏱ ${o.type.toUpperCase()}` : isStop ? (isBuy ? '🛑 BUY STOP' : '🛑 SELL STOP') : (isBuy ? '🎯 BUY LIMIT' : '🎯 SELL LIMIT')}
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

{terminalTab === 'suggester' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
                {/* Suggester Header & Control Bar */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 16px',
                  backgroundColor: '#171b26',
                  borderBottom: '1px solid var(--tv-border)',
                  fontSize: '12px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Target size={16} color="#089981" />
                      <span style={{ fontWeight: 700, color: '#fff', fontSize: '13px' }}>
                        100-Question Rule-Based Trade Suggester
                      </span>
                    </div>
                    <span style={{
                      backgroundColor: 'rgba(8, 153, 129, 0.15)',
                      color: '#089981',
                      border: '1px solid rgba(8, 153, 129, 0.3)',
                      borderRadius: '4px',
                      padding: '2px 8px',
                      fontSize: '11px',
                      fontWeight: 600
                    }}>
                      Strict Zero-AI (11 Synthetics)
                    </span>
                    <span style={{ color: 'var(--tv-text-secondary)', fontSize: '11px' }}>
                      Monitoring: FX Vol 20/40/60 • SFX Vol 20/40/60 • FlipX 1 to 5
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <button
                      onClick={fetchBacktestProof}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        padding: '5px 12px',
                        backgroundColor: 'rgba(255, 179, 0, 0.15)',
                        border: '1px solid rgba(255, 179, 0, 0.4)',
                        borderRadius: '4px',
                        color: '#ffb300',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                      title="View Verified 6-Month Backtest Audit Proof (16,180 Trades, 73.1% Win Rate)"
                    >
                      <Award size={14} color="#ffb300" />
                      <span>📊 View Strict Backtest Proof (73.1% WR)</span>
                    </button>

                    <button
                      onClick={() => fetchScannerSignals(true)}
                      disabled={scannerLoading}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px',
                        padding: '5px 10px',
                        backgroundColor: '#1e222d',
                        border: '1px solid #2a2e39',
                        borderRadius: '4px',
                        color: '#fff',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      <RefreshCw size={12} className={scannerLoading ? 'spin' : ''} color={scannerLoading ? '#089981' : '#787b86'} />
                      <span>{scannerLoading ? 'Scanning 11 Synthetics...' : 'Refresh'}</span>
                    </button>
                  </div>
                </div>

                {/* Signals Table */}
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)', background: '#131722', height: '32px' }}>
                      <th style={{ padding: '6px 12px' }}>SYMBOL</th>
                      <th style={{ padding: '6px 12px' }}>STATUS</th>
                      <th style={{ padding: '6px 12px' }}>SETUP & BIAS</th>
                      <th style={{ padding: '6px 12px' }}>CURRENT PRICE</th>
                      <th style={{ padding: '6px 12px' }}>RETEST SHELF</th>
                      <th style={{ padding: '6px 12px' }}>PROPOSED TRADE PLAN</th>
                      <th style={{ padding: '6px 12px' }}>R:R RATIO</th>
                      <th style={{ padding: '6px 12px' }}>EST. P&L (0.01 LOT)</th>
                      <th style={{ padding: '6px 12px', textAlign: 'center' }}>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scannerSignals.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: 'center', padding: '36px', color: 'var(--tv-text-muted)' }}>
                          {scannerLoading ? 'Analyzing MT5 live candles and market structure across 11 synthetics...' : 'No signals found. Click Refresh to scan.'}
                        </td>
                      </tr>
                    ) : (
                      scannerSignals.map((item) => {
                        const isConfirmed = item.status === 'CONFIRMED SIGNAL';
                        const isAtZone = item.status === 'AT RETEST ZONE';
                        const isApproaching = item.status === 'APPROACHING';
                        const isBuy = item.direction === 'BUY';

                        return (
                          <tr
                            key={item.symbol}
                            style={{
                              borderBottom: '1px solid var(--tv-border)',
                              height: '44px',
                              backgroundColor: isConfirmed
                                ? 'rgba(8, 153, 129, 0.08)'
                                : isAtZone
                                ? 'rgba(255, 152, 0, 0.05)'
                                : 'transparent',
                              transition: 'background-color 0.15s ease'
                            }}
                          >
                            {/* Symbol & Category */}
                            <td style={{ padding: '8px 12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <div style={{
                                  width: '8px',
                                  height: '8px',
                                  borderRadius: '50%',
                                  backgroundColor: isConfirmed ? '#089981' : isAtZone ? '#ff9800' : isApproaching ? '#00bcd4' : '#787b86',
                                  boxShadow: isConfirmed ? '0 0 6px #089981' : 'none'
                                }} />
                                <div>
                                  <div style={{ fontWeight: 700, color: '#fff' }}>{item.name}</div>
                                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>{item.category}</div>
                                </div>
                              </div>
                            </td>

                            {/* Status Badge */}
                            <td style={{ padding: '8px 12px' }}>
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '3px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 700,
                                backgroundColor: isConfirmed
                                  ? 'rgba(8, 153, 129, 0.25)'
                                  : isAtZone
                                  ? 'rgba(255, 152, 0, 0.2)'
                                  : isApproaching
                                  ? 'rgba(0, 188, 212, 0.15)'
                                  : 'rgba(255, 255, 255, 0.05)',
                                color: isConfirmed
                                  ? '#089981'
                                  : isAtZone
                                  ? '#ff9800'
                                  : isApproaching
                                  ? '#00bcd4'
                                  : '#787b86',
                                border: `1px solid ${
                                  isConfirmed ? '#089981' : isAtZone ? '#ff9800' : isApproaching ? '#00bcd4' : 'transparent'
                                }`
                              }}>
                                {isConfirmed ? '⚡ CONFIRMED SIGNAL' : isAtZone ? '🟡 AT RETEST ZONE' : isApproaching ? '🔵 APPROACHING' : '⚪ SCANNING'}
                              </span>
                            </td>

                            {/* Setup & Bias */}
                            <td style={{ padding: '8px 12px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{
                                  padding: '2px 6px',
                                  borderRadius: '3px',
                                  fontSize: '11px',
                                  fontWeight: 800,
                                  backgroundColor: isBuy ? 'rgba(8, 153, 129, 0.2)' : 'rgba(242, 54, 69, 0.2)',
                                  color: isBuy ? '#089981' : '#f23645'
                                }}>
                                  {item.direction}
                                </span>
                                <span style={{ fontSize: '11px', color: 'var(--tv-text-secondary)' }}>
                                  {item.shelf_type}
                                </span>
                              </div>
                            </td>

                            {/* Price / Spread */}
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>
                              <div style={{ fontWeight: 600, color: '#fff' }}>{Number(item.current_price).toFixed(2)}</div>
                              <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>Spread: {Number(item.spread).toFixed(2)}</div>
                            </td>

                            {/* Retest Shelf */}
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>
                              <span style={{ color: '#ffb300', fontWeight: 600 }}>
                                {Number(item.shelf_level).toFixed(2)}
                              </span>
                            </td>

                            {/* Proposed Trade Plan */}
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: '11px' }}>
                              {item.entry != null ? (
                                <div>
                                  <span style={{ color: 'var(--tv-text-muted)' }}>{item.is_limit_plan ? 'Limit @ Shelf: ' : 'Entry: '}</span>
                                  <span style={{ color: item.is_limit_plan ? '#ffb300' : '#fff', fontWeight: 600 }}>{Number(item.entry).toFixed(2)}</span>
                                  <span style={{ color: 'var(--tv-text-muted)', margin: '0 4px' }}>|</span>
                                  <span style={{ color: 'var(--tv-text-muted)' }}>SL: </span>
                                  <span style={{ color: '#f23645', fontWeight: 600 }}>{Number(item.sl).toFixed(2)}</span>
                                  <span style={{ color: 'var(--tv-text-muted)', margin: '0 4px' }}>|</span>
                                  <span style={{ color: 'var(--tv-text-muted)' }}>TP: </span>
                                  <span style={{ color: '#089981', fontWeight: 600 }}>{Number(item.tp).toFixed(2)}</span>
                                </div>
                              ) : (
                                <span style={{ color: 'var(--tv-text-muted)', fontStyle: 'italic' }}>
                                  Awaiting Structural Breakout
                                </span>
                              )}
                              <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)', marginTop: '2px' }}>
                                Obstacle #1: {item.obstacle_1 ? Number(item.obstacle_1).toFixed(2) : '---'}
                              </div>
                            </td>

                            {/* R:R Ratio */}
                            <td style={{ padding: '8px 12px' }}>
                              {item.rrr > 0 ? (
                                <span style={{
                                  backgroundColor: 'rgba(8, 153, 129, 0.15)',
                                  color: '#089981',
                                  border: '1px solid rgba(8, 153, 129, 0.3)',
                                  borderRadius: '3px',
                                  padding: '2px 6px',
                                  fontWeight: 700,
                                  fontSize: '11px',
                                  fontFamily: 'monospace'
                                }}>
                                  1 : {item.rrr}
                                </span>
                              ) : (
                                <span style={{ color: 'var(--tv-text-muted)', fontSize: '11px' }}>---</span>
                              )}
                            </td>

                            {/* Est. USD P&L */}
                            <td style={{ padding: '8px 12px', fontFamily: 'monospace', fontSize: '11px' }}>
                              {item.risk_usd > 0 ? (
                                <>
                                  <span style={{ color: '#f23645' }}>-${Number(item.risk_usd).toFixed(2)}</span>
                                  <span style={{ color: 'var(--tv-text-muted)', margin: '0 4px' }}>/</span>
                                  <span style={{ color: '#089981', fontWeight: 600 }}>+${Number(item.reward_usd).toFixed(2)}</span>
                                </>
                              ) : (
                                <span style={{ color: 'var(--tv-text-muted)' }}>---</span>
                              )}
                            </td>

                            {/* Action Button */}
                            <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                              {isConfirmed ? (
                                <button
                                  onClick={() => handleLoadTradePlan(item)}
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '5px',
                                    padding: '5px 12px',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    backgroundColor: '#089981',
                                    color: '#fff',
                                    border: 'none',
                                    boxShadow: '0 0 10px rgba(8, 153, 129, 0.45)',
                                    transition: 'all 0.15s ease'
                                  }}
                                  title="Load confirmed rejection trade plan"
                                >
                                  <Zap size={13} />
                                  <span>⚡ Confirmed Plan</span>
                                </button>
                              ) : item.actionable && item.is_limit_plan ? (
                                <button
                                  onClick={() => handleLoadTradePlan(item)}
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '5px',
                                    padding: '5px 10px',
                                    borderRadius: '4px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                    backgroundColor: isAtZone ? 'rgba(255, 152, 0, 0.2)' : 'rgba(0, 188, 212, 0.2)',
                                    color: isAtZone ? '#ff9800' : '#00bcd4',
                                    border: `1px solid ${isAtZone ? '#ff9800' : '#00bcd4'}`,
                                    transition: 'all 0.15s ease'
                                  }}
                                  title={isAtZone ? 'In Retest Zone: Load passive Limit Order @ Shelf' : 'Approaching Zone: Pre-arm passive Limit Order @ Shelf'}
                                >
                                  <Target size={12} />
                                  <span>🎯 Limit @ Shelf</span>
                                </button>
                              ) : (
                                <button
                                  disabled
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '5px',
                                    padding: '5px 10px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontWeight: 600,
                                    backgroundColor: 'rgba(255, 255, 255, 0.04)',
                                    color: 'var(--tv-text-muted)',
                                    border: '1px solid var(--tv-border)',
                                    cursor: 'not-allowed'
                                  }}
                                  title="Scanning for structural breakout."
                                >
                                  <Clock size={12} />
                                  <span>⚪ Scanning</span>
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {terminalTab === 'radar' && (
              <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
                {/* Search & info banner */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  padding: '8px 16px',
                  backgroundColor: 'rgba(255,255,255,0.02)',
                  borderBottom: '1px solid var(--tv-border)',
                  fontSize: '12px'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: '#1e222d',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    border: '1px solid #2a2e39',
                    minWidth: '240px'
                  }}>
                    <Search size={14} color="#787b86" />
                    <input
                      type="text"
                      placeholder="Filter 41 Synthetics..."
                      value={radarSearchQuery}
                      onChange={(e) => setRadarSearchQuery(e.target.value)}
                      style={{ background: 'transparent', border: 'none', outline: 'none', color: '#fff', fontSize: '12px', width: '100%' }}
                    />
                    {radarSearchQuery && (
                      <span onClick={() => setRadarSearchQuery('')} style={{ cursor: 'pointer', color: '#787b86', fontSize: '11px' }}>✕</span>
                    )}
                  </div>
                  <span style={{ color: 'var(--tv-text-secondary)', fontSize: '11px' }}>
                    Live scanner across all 41 Weltrade Synthetics with real-time MT5 ticks, spreads, and 24h performance.
                  </span>
                </div>

                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--tv-bg-primary)', zIndex: 2 }}>
                    <tr style={{ color: 'var(--tv-text-secondary)', borderBottom: '1px solid var(--tv-border)' }}>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Symbol</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500 }}>Series</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>Last Price</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>24h Change</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>Bid / Ask</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'right' }}>Spread</th>
                      <th style={{ padding: '6px 14px', fontWeight: 500, textAlign: 'center' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {WATCHLIST_GROUPS.flatMap(g => g.symbols)
                      .filter(s => {
                        if (!radarSearchQuery.trim()) return true;
                        const q = radarSearchQuery.toLowerCase();
                        return s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q) || s.group.toLowerCase().includes(q);
                      })
                      .map(s => {
                        const item = watchlist[s.id];
                        const isCurrent = symbol === s.id;
                        const price = item?.price ? item.price.toFixed(2) : '-';
                        const changePct = item?.change_pct ?? 0;
                        const isUp = changePct >= 0;
                        const spread = item?.bid && item?.ask ? (item.ask - item.bid).toFixed(2) : '-';

                        return (
                          <tr
                            key={s.id}
                            style={{
                              borderBottom: '1px solid var(--tv-border-subtle)',
                              backgroundColor: isCurrent ? 'rgba(41, 98, 255, 0.08)' : 'transparent',
                              transition: 'background-color 0.15s'
                            }}
                            onMouseEnter={(e) => {
                              if (!isCurrent) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)';
                            }}
                            onMouseLeave={(e) => {
                              if (!isCurrent) e.currentTarget.style.backgroundColor = 'transparent';
                            }}
                          >
                            <td style={{ padding: '6px 14px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{
                                  backgroundColor: s.color,
                                  color: '#fff',
                                  fontSize: '10px',
                                  fontWeight: 800,
                                  padding: '1px 5px',
                                  borderRadius: '3px'
                                }}>
                                  {s.badge}
                                </span>
                                <span style={{ fontWeight: 600, color: isCurrent ? 'var(--tv-accent)' : '#fff' }}>
                                  {s.name}
                                </span>
                                {isCurrent && (
                                  <span style={{ fontSize: '9px', background: 'var(--tv-accent)', color: '#fff', padding: '0 4px', borderRadius: '2px', fontWeight: 700 }}>
                                    ACTIVE
                                  </span>
                                )}
                              </div>
                            </td>
                            <td style={{ padding: '6px 14px', color: 'var(--tv-text-secondary)', fontSize: '11px' }}>
                              {s.group}
                            </td>
                            <td style={{ padding: '6px 14px', textAlign: 'right', fontWeight: 700, fontFamily: 'monospace' }}>
                              {price}
                            </td>
                            <td style={{
                              padding: '6px 14px',
                              textAlign: 'right',
                              fontWeight: 700,
                              fontFamily: 'monospace',
                              color: isUp ? 'var(--tv-up)' : 'var(--tv-down)'
                            }}>
                              {isUp ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`}
                            </td>
                            <td style={{ padding: '6px 14px', textAlign: 'right', fontFamily: 'monospace', color: 'var(--tv-text-secondary)' }}>
                              {item?.bid ? `${item.bid.toFixed(2)} / ${item.ask.toFixed(2)}` : '-'}
                            </td>
                            <td style={{ padding: '6px 14px', textAlign: 'right', fontFamily: 'monospace', color: '#ff9800' }}>
                              {spread}
                            </td>
                            <td style={{ padding: '6px 14px', textAlign: 'center' }}>
                              <button
                                onClick={() => {
                                  setSymbol(s.id);
                                  if (!openTabs.includes(s.id)) {
                                    const nextTabs = [...openTabs, s.id];
                                    setOpenTabs(nextTabs);
                                    try { localStorage.setItem('weltrade_open_tabs', JSON.stringify(nextTabs)); } catch (e) {}
                                  }
                                }}
                                style={{
                                  backgroundColor: isCurrent ? 'rgba(41,98,255,0.2)' : 'var(--tv-bg-hover)',
                                  color: isCurrent ? 'var(--tv-accent)' : '#d1d4dc',
                                  border: `1px solid ${isCurrent ? 'var(--tv-accent)' : '#363a45'}`,
                                  borderRadius: '4px',
                                  padding: '3px 10px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: 'pointer'
                                }}
                              >
                                {isCurrent ? 'Active Chart' : 'Open Chart'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
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
          <span>{account?.server || 'Weltrade-Real'} {account?.login ? `(#${account.login})` : ''}</span>
          <button
            onClick={() => {
              setTargetLogin(account?.login ? String(account.login) : '34967194');
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
          STRICT 100-QUESTION BACKTEST AUDIT PROOF MODAL (11 SYNTHETICS)
      ───────────────────────────────────────────────────────────── */}
      {showBacktestModal && backtestProofData && (
        <div
          onClick={() => setShowBacktestModal(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '900px',
              maxWidth: '95vw',
              maxHeight: '90vh',
              backgroundColor: '#171b26',
              border: '1px solid #2a2e39',
              borderRadius: '8px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 16px 48px rgba(0,0,0,0.8)',
              overflow: 'hidden'
            }}
          >
            {/* Modal Header */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '16px 20px',
              borderBottom: '1px solid #2a2e39',
              background: '#131722'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Award size={20} color="#ffb300" />
                <div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff' }}>
                    Strict 100-Question Rule-Based Backtest Audit (6 Months)
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--tv-text-secondary)', marginTop: '2px' }}>
                    Zero-AI • Zero-Lookahead • Point-in-Time • Full Broker Spreads • Universe: 11 Synthetics
                  </div>
                </div>
              </div>
              <button
                onClick={() => setShowBacktestModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#787b86', cursor: 'pointer', padding: '4px' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
              {/* Top Summary Metrics */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(6, 1fr)',
                gap: '12px',
                marginBottom: '20px'
              }}>
                <div style={{ backgroundColor: '#1e222d', padding: '12px', borderRadius: '6px', border: '1px solid #2a2e39', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>TOTAL TRADES</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#fff', marginTop: '4px' }}>
                    {backtestProofData.total_trades.toLocaleString()}
                  </div>
                </div>
                <div style={{ backgroundColor: 'rgba(8, 153, 129, 0.12)', padding: '12px', borderRadius: '6px', border: '1px solid #089981', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: '#089981', fontWeight: 600 }}>PROTECTED WIN RATE</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#089981', marginTop: '4px' }}>
                    {backtestProofData.protected_win_rate_pct}%
                  </div>
                </div>
                <div style={{ backgroundColor: '#1e222d', padding: '12px', borderRadius: '6px', border: '1px solid #2a2e39', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>PROFIT FACTOR</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#ffb300', marginTop: '4px' }}>
                    {backtestProofData.profit_factor}
                  </div>
                </div>
                <div style={{ backgroundColor: '#1e222d', padding: '12px', borderRadius: '6px', border: '1px solid #2a2e39', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>NET REALIZED RETURN</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#089981', marginTop: '4px' }}>
                    +{backtestProofData.net_realized_r.toLocaleString()} R
                  </div>
                </div>
                <div style={{ backgroundColor: '#1e222d', padding: '12px', borderRadius: '6px', border: '1px solid #2a2e39', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>AVG PLANNED R:R</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#2962ff', marginTop: '4px' }}>
                    1 : {backtestProofData.avg_planned_rrr}
                  </div>
                </div>
                <div style={{ backgroundColor: '#1e222d', padding: '12px', borderRadius: '6px', border: '1px solid #2a2e39', textAlign: 'center' }}>
                  <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>MAX DRAWDOWN</div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#f23645', marginTop: '4px' }}>
                    -{backtestProofData.max_drawdown_r} R
                  </div>
                </div>
              </div>

              {/* Methodology Explanation */}
              <div style={{
                backgroundColor: 'rgba(41, 98, 255, 0.08)',
                border: '1px solid rgba(41, 98, 255, 0.25)',
                borderRadius: '6px',
                padding: '12px 16px',
                fontSize: '12px',
                color: '#d1d4dc',
                marginBottom: '20px',
                lineHeight: 1.5
              }}>
                <strong style={{ color: '#2962ff' }}>Strict 100-Question Rules Enforced:</strong>
                <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                  <li><strong>H1 Macro Trend (Q4/Q14):</strong> Trades only taken aligned with 20 EMA trend bias.</li>
                  <li><strong>M15 5-Bar Fractal Pivots (Q5/Q8/Q20):</strong> Support/Resistance shelves detected via HH/HL/LH/LL swings.</li>
                  <li><strong>Broken Shelf Retest (Q70/Q79):</strong> Previous resistance flipped to support (BUY) or support flipped to resistance (SELL).</li>
                  <li><strong>Touch #2 Protected Wick (Lesson 2):</strong> Absorption confirmed when Touch #2 holds strictly within Touch #1 outer wick tip.</li>
                  <li><strong>Structural SL (Q31):</strong> Stop Loss tucked behind wick tip + spread + 0.15 ATR buffer.</li>
                  <li><strong>Q93 Fast Breakeven Lock:</strong> SL moved to Breakeven (+0.1R) as soon as price reaches Obstacle #1 or +1.3R.</li>
                </ul>
              </div>

              {/* Quant Analyst: Approaching vs Confirmed Comparison */}
              {backtestProofData.quant_comparison && (
                <div style={{ marginBottom: '20px', border: '1px solid #00bcd4', borderRadius: '6px', overflow: 'hidden', backgroundColor: 'rgba(0, 188, 212, 0.04)' }}>
                  <div style={{ padding: '10px 14px', background: 'rgba(0, 188, 212, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 700, color: '#00bcd4', fontSize: '13px' }}>
                      🔬 Quant Analyst: "Approaching" Limit vs "Confirmed" Close Execution (7,662 Events Backtested)
                    </span>
                    <span style={{ fontSize: '11px', color: '#fff', background: '#1e222d', padding: '2px 8px', borderRadius: '3px' }}>
                      Shelf Reach Rate: {backtestProofData.quant_comparison.reached_shelf_pct}%
                    </span>
                  </div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#131722', color: 'var(--tv-text-secondary)', height: '32px', borderBottom: '1px solid #2a2e39' }}>
                        <th style={{ padding: '6px 14px' }}>EXECUTION STRATEGY</th>
                        <th style={{ padding: '6px 14px' }}>TOTAL TRADES</th>
                        <th style={{ padding: '6px 14px' }}>CLEAN WINS</th>
                        <th style={{ padding: '6px 14px' }}>Q93 BE LOCK</th>
                        <th style={{ padding: '6px 14px' }}>LOSSES</th>
                        <th style={{ padding: '6px 14px' }}>PROTECTED WR</th>
                        <th style={{ padding: '6px 14px' }}>NET RETURN</th>
                        <th style={{ padding: '6px 14px' }}>PROFIT FACTOR</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr style={{ borderBottom: '1px solid #2a2e39', background: 'rgba(0, 188, 212, 0.08)' }}>
                        <td style={{ padding: '8px 14px', fontWeight: 700, color: '#00bcd4' }}>
                          🎯 Limit Order @ Shelf (On Approach)
                        </td>
                        <td style={{ padding: '8px 14px' }}>{backtestProofData.quant_comparison.limit_at_shelf.trades}</td>
                        <td style={{ padding: '8px 14px', color: '#089981' }}>{backtestProofData.quant_comparison.limit_at_shelf.clean_wins} ({backtestProofData.quant_comparison.limit_at_shelf.win_rate_pct}%)</td>
                        <td style={{ padding: '8px 14px', color: '#ffb300' }}>{backtestProofData.quant_comparison.limit_at_shelf.be_protected}</td>
                        <td style={{ padding: '8px 14px', color: '#f23645' }}>{backtestProofData.quant_comparison.limit_at_shelf.losses}</td>
                        <td style={{ padding: '8px 14px', fontWeight: 700, color: '#00bcd4' }}>{backtestProofData.quant_comparison.limit_at_shelf.protected_win_rate_pct}%</td>
                        <td style={{ padding: '8px 14px', fontWeight: 800, color: '#089981' }}>+{backtestProofData.quant_comparison.limit_at_shelf.net_realized_r} R</td>
                        <td style={{ padding: '8px 14px', fontWeight: 800, color: '#ffb300' }}>{backtestProofData.quant_comparison.limit_at_shelf.profit_factor}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid #2a2e39' }}>
                        <td style={{ padding: '8px 14px', fontWeight: 600, color: '#fff' }}>
                          ⚡ Confirmed Rejection Close
                        </td>
                        <td style={{ padding: '8px 14px' }}>{backtestProofData.quant_comparison.confirmed_close.trades}</td>
                        <td style={{ padding: '8px 14px', color: '#089981' }}>{backtestProofData.quant_comparison.confirmed_close.clean_wins} ({backtestProofData.quant_comparison.confirmed_close.win_rate_pct}%)</td>
                        <td style={{ padding: '8px 14px', color: '#ffb300' }}>{backtestProofData.quant_comparison.confirmed_close.be_protected}</td>
                        <td style={{ padding: '8px 14px', color: '#f23645' }}>{backtestProofData.quant_comparison.confirmed_close.losses}</td>
                        <td style={{ padding: '8px 14px', fontWeight: 600 }}>{backtestProofData.quant_comparison.confirmed_close.protected_win_rate_pct}%</td>
                        <td style={{ padding: '8px 14px', color: '#f23645' }}>{backtestProofData.quant_comparison.confirmed_close.net_realized_r} R</td>
                        <td style={{ padding: '8px 14px' }}>{backtestProofData.quant_comparison.confirmed_close.profit_factor}</td>
                      </tr>
                      <tr style={{ borderBottom: '1px solid #2a2e39' }}>
                        <td style={{ padding: '8px 14px', fontWeight: 600, color: '#b2b5be' }}>
                          🟡 Zone Touch Market Entry
                        </td>
                        <td style={{ padding: '8px 14px' }}>{backtestProofData.quant_comparison.zone_touch.trades}</td>
                        <td style={{ padding: '8px 14px', color: '#089981' }}>{backtestProofData.quant_comparison.zone_touch.clean_wins} ({backtestProofData.quant_comparison.zone_touch.win_rate_pct}%)</td>
                        <td style={{ padding: '8px 14px', color: '#ffb300' }}>{backtestProofData.quant_comparison.zone_touch.be_protected}</td>
                        <td style={{ padding: '8px 14px', color: '#f23645' }}>{backtestProofData.quant_comparison.zone_touch.losses}</td>
                        <td style={{ padding: '8px 14px', fontWeight: 600 }}>{backtestProofData.quant_comparison.zone_touch.protected_win_rate_pct}%</td>
                        <td style={{ padding: '8px 14px', color: '#089981' }}>+{backtestProofData.quant_comparison.zone_touch.net_realized_r} R</td>
                        <td style={{ padding: '8px 14px' }}>{backtestProofData.quant_comparison.zone_touch.profit_factor}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* 11-Symbol Breakdown Table */}
              <div style={{ border: '1px solid #2a2e39', borderRadius: '6px', overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: '#131722', color: 'var(--tv-text-secondary)', height: '34px', borderBottom: '1px solid #2a2e39' }}>
                      <th style={{ padding: '6px 14px' }}>SYMBOL</th>
                      <th style={{ padding: '6px 14px' }}>COMPLETED TRADES</th>
                      <th style={{ padding: '6px 14px' }}>CLEAN WINS</th>
                      <th style={{ padding: '6px 14px' }}>Q93 BE PROTECTED</th>
                      <th style={{ padding: '6px 14px' }}>FULL LOSSES</th>
                      <th style={{ padding: '6px 14px' }}>PROTECTED WR %</th>
                      <th style={{ padding: '6px 14px' }}>PROFIT FACTOR</th>
                      <th style={{ padding: '6px 14px' }}>NET RETURN (R)</th>
                      <th style={{ padding: '6px 14px' }}>AVG R:R</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtestProofData.symbols && backtestProofData.symbols.map((sym: any) => (
                      <tr key={sym.symbol} style={{ borderBottom: '1px solid #1e222d', height: '36px' }}>
                        <td style={{ padding: '6px 14px', fontWeight: 700, color: '#fff' }}>{sym.symbol}</td>
                        <td style={{ padding: '6px 14px', fontFamily: 'monospace' }}>{sym.trades.toLocaleString()}</td>
                        <td style={{ padding: '6px 14px', fontFamily: 'monospace', color: '#089981' }}>{sym.wins}</td>
                        <td style={{ padding: '6px 14px', fontFamily: 'monospace', color: '#ffb300' }}>{sym.be}</td>
                        <td style={{ padding: '6px 14px', fontFamily: 'monospace', color: '#f23645' }}>{sym.losses}</td>
                        <td style={{ padding: '6px 14px', fontWeight: 700, color: sym.prot_wr >= 70 ? '#089981' : '#ff9800' }}>
                          {sym.prot_wr}%
                        </td>
                        <td style={{ padding: '6px 14px', fontWeight: 700, color: '#ffb300', fontFamily: 'monospace' }}>
                          {sym.pf}
                        </td>
                        <td style={{ padding: '6px 14px', fontWeight: 700, color: '#089981', fontFamily: 'monospace' }}>
                          +{sym.net_r} R
                        </td>
                        <td style={{ padding: '6px 14px', fontFamily: 'monospace' }}>
                          1 : {sym.avg_rr}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '12px 20px',
              borderTop: '1px solid #2a2e39',
              background: '#131722',
              display: 'flex',
              justifyContent: 'flex-end'
            }}>
              <button
                onClick={() => setShowBacktestModal(false)}
                style={{
                  padding: '6px 18px',
                  backgroundColor: '#2962ff',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  fontWeight: 600,
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                Close Audit Proof
              </button>
            </div>
          </div>
        </div>
      )}

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
                placeholder="Search symbol (e.g. FX Vol 20, SFX Vol 40)..."
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

            {/* Category Filter Chips Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              borderBottom: '1px solid var(--tv-border)',
              backgroundColor: 'var(--tv-bg-primary)',
              overflowX: 'auto',
              scrollbarWidth: 'none',
              flexShrink: 0
            }}>
              {SYMBOL_CATEGORIES.map(cat => {
                const isSelected = searchCategory === cat;
                const count = cat === 'ALL'
                  ? ALL_SYMBOLS.length
                  : WATCHLIST_GROUPS.filter(g => g.group === cat).flatMap(g => g.symbols).length;
                return (
                  <button
                    key={cat}
                    onClick={() => setSearchCategory(cat)}
                    style={{
                      background: isSelected ? 'var(--tv-accent)' : 'transparent',
                      color: isSelected ? '#fff' : 'var(--tv-text-secondary)',
                      border: '1px solid ' + (isSelected ? 'var(--tv-accent)' : 'var(--tv-border)'),
                      borderRadius: '14px',
                      padding: '3px 10px',
                      fontSize: '11px',
                      fontWeight: isSelected ? 700 : 500,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    {cat} ({count})
                  </button>
                );
              })}
            </div>

            {/* Symbol Results List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
              {filteredSymbols.map(s => {
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
                      padding: '10px 16px',
                      cursor: 'pointer',
                      backgroundColor: isSelected ? 'var(--tv-bg-hover)' : 'transparent',
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
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      backgroundColor: s.color,
                      color: '#fff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '11px',
                      marginRight: '12px',
                      flexShrink: 0
                    }}>
                      {s.badge}
                    </div>

                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--tv-text-primary)' }}>
                          {s.name}
                        </span>
                        <span style={{
                          fontSize: '10px',
                          color: 'var(--tv-text-muted)',
                          border: '1px solid var(--tv-border)',
                          borderRadius: '3px',
                          padding: '1px 4px'
                        }}>
                          {s.category}
                        </span>
                      </div>
                      {item && (
                        <div style={{ fontSize: '11px', color: 'var(--tv-text-muted)', marginTop: '2px' }}>
                          Bid: {item.bid.toFixed(2)} · Ask: {item.ask.toFixed(2)}
                        </div>
                      )}
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--tv-text-primary)' }}>
                        {displayPrice}
                      </div>
                      {changePct !== null && (
                        <div style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          color: isPos ? 'var(--tv-up)' : 'var(--tv-down)'
                        }}>
                          {isPos ? '+' : ''}{changePct.toFixed(2)}%
                        </div>
                      )}
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
                  setTargetLogin('43373678');
                  setTargetServer('Weltrade-Demo');
                  setTargetPassword('');
                }}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '5px',
                  border: targetLogin === '43373678' ? '1px solid #2962ff' : '1px solid var(--tv-border)',
                  backgroundColor: targetLogin === '43373678' ? 'rgba(41, 98, 255, 0.15)' : '#1e222d',
                  color: targetLogin === '43373678' ? '#2962ff' : '#d1d4dc',
                  fontWeight: 600,
                  fontSize: '11px',
                  cursor: 'pointer'
                }}
              >
                <div>Demo #43373678</div>
                <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>Weltrade-Demo</div>
              </button>

              <button
                onClick={() => {
                  setTargetLogin('34967194');
                  setTargetServer('Weltrade-Real');
                  setTargetPassword('E)6cGp!8');
                }}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '5px',
                  border: targetLogin === '34967194' ? '1px solid #089981' : '1px solid var(--tv-border)',
                  backgroundColor: targetLogin === '34967194' ? 'rgba(8, 153, 129, 0.15)' : '#1e222d',
                  color: targetLogin === '34967194' ? '#089981' : '#d1d4dc',
                  fontWeight: 600,
                  fontSize: '11px',
                  cursor: 'pointer'
                }}
              >
                <div>Real #34967194</div>
                <div style={{ fontSize: '10px', color: 'var(--tv-text-muted)' }}>Weltrade-Real</div>
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

      {/* Floating Alert Toasts (Top Right Overlay) */}
      <div style={{
        position: 'fixed',
        top: '55px',
        right: '50px',
        zIndex: 1000,
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        pointerEvents: 'none'
      }}>
        {alertToasts.map(toast => (
          <div key={toast.id} style={{
            pointerEvents: 'auto',
            backgroundColor: toast.type === 'success' ? '#132a22' : '#1e222d',
            border: `1px solid ${toast.type === 'success' ? '#089981' : 'var(--tv-accent)'}`,
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
            borderRadius: '6px',
            padding: '8px 12px',
            minWidth: '260px',
            maxWidth: '340px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '12px', color: toast.type === 'success' ? '#089981' : '#fff' }}>
                {toast.title}
              </span>
              <span
                onClick={() => setAlertToasts(prev => prev.filter(t => t.id !== toast.id))}
                style={{ cursor: 'pointer', color: '#787b86', fontSize: '12px', marginLeft: '8px' }}
              >
                ✕
              </span>
            </div>
            <div style={{ fontSize: '11px', color: '#d1d4dc', marginTop: '3px' }}>
              {toast.message}
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
