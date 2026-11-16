import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import type { IChartApi, ISeriesApi } from 'lightweight-charts';
import { DrawingManager } from 'lightweight-charts-drawing';
import DrawingToolbar, { type DrawingFormatState } from './DrawingToolbar';
import TradeConfirmationCard, { type PositionTradeState } from './TradeConfirmationCard';

export interface CandleAccuracy {
  status: 'verified' | 'reconciling' | 'syncing';
  lastVerifiedTime: number; // Unix timestamp in ms
  desyncFixedCount: number;
  verifiedBarsCount: number;
  accuracyPct: number;
}

interface ChartProps {
  symbol: string;
  timeframe: string;
  showVolume: boolean;
  showMarketStructure?: boolean;
  activeTool?: string | null;
  onToolDeactivate?: () => void;
  onDrawingsUpdate?: (drawings: any[], symbol: string) => void;
  onTick?: (candle: any) => void;
  onWatchlistUpdate?: (data: any[]) => void;
  onOrderSuccess?: (ticket: number, comment?: string) => void;
  positions?: any[];
  pendingOrders?: any[];
  onCandleAccuracyUpdate?: (accuracy: CandleAccuracy) => void;
  isMagnetOn?: boolean;
  suggestedTrade?: { kind: 'long-position' | 'short-position'; entry: number; sl: number; tp: number; id?: string; symbol?: string; name?: string; shelf_level?: number; obstacle_1?: number; rrr?: number; risk_usd?: number; reward_usd?: number } | null;
}

interface LegendData {
  open: number;
  high: number;
  low: number;
  close: number;
  change: number;
  changePct: number;
}

const getBarIntervalSeconds = (tf: string): number => {
  const map: Record<string, number> = {
    'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800,
    'H1': 3600, 'H4': 14400, '1D': 86400
  };
  return map[tf] || 900;
};

export default function ChartComponent({
  symbol,
  timeframe,
  showVolume,
  showMarketStructure = true,
  activeTool,
  onToolDeactivate,
  onDrawingsUpdate,
  onTick,
  onWatchlistUpdate,
  onOrderSuccess,
  positions,
  pendingOrders,
  onCandleAccuracyUpdate,
  isMagnetOn = false,
  suggestedTrade
}: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  
  const cbRef = useRef({ onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol });
  useEffect(() => {
    cbRef.current = { onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol };
  }, [onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol]);

  const wsRef = useRef<WebSocket | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const drawingManagerRef = useRef<any>(null);
  const livePriceLinesRef = useRef<any[]>([]);
  
  const isRestoring = useRef(false);
  const syncTimeout = useRef<any>(null);
  const isHoveringRef = useRef(false);

  const [legend, setLegend] = useState<LegendData | null>(null);
  const [bidAsk, setBidAsk] = useState<{ bid: number; ask: number }>({ bid: 0, ask: 0 });
  const [lotSize, setLotSize] = useState('0.01');
  const [showOrderStrip] = useState(true);
  const [selectedDrawing, setSelectedDrawing] = useState<DrawingFormatState | null>(null);
  const [candleCountdown, setCandleCountdown] = useState<string>('00:00');

  useEffect(() => {
    const updateCountdown = () => {
      const intervalSec = getBarIntervalSeconds(timeframe);
      const nowSec = Math.floor(Date.now() / 1000);
      const secRemaining = intervalSec - (nowSec % intervalSec);
      const mins = Math.floor(secRemaining / 60);
      const secs = secRemaining % 60;
      setCandleCountdown(`${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`);
    };
    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [timeframe]);

  const selectedPositionRef = useRef<PositionTradeState | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<PositionTradeState | null>(null);
  const latestBarRef = useRef<{ time: number; close: number } | null>(null);
  const totalDesyncHealedRef = useRef<number>(0);
  const lastVerifiedTimeRef = useRef<number>(0);
  const barsDataRef = useRef<any[]>([]);
  const bosPriceLineRef = useRef<any>(null);

  const updateMarketStructure = useCallback((bars: any[]) => {
    if (!seriesRef.current || !showMarketStructure) {
      if (seriesRef.current) {
        try { (seriesRef.current as any).setMarkers([]); } catch (e) {}
      }
      if (bosPriceLineRef.current && seriesRef.current) {
        try { seriesRef.current.removePriceLine(bosPriceLineRef.current); } catch (e) {}
        bosPriceLineRef.current = null;
      }
      return;
    }

    if (!bars || bars.length < 10) return;
    const markers: any[] = [];
    const swingHighs: { time: number; price: number; isHH: boolean }[] = [];
    const swingLows: { time: number; price: number; isHL: boolean }[] = [];

    const k = 2; // 5-bar fractal window (2 left, 1 center, 2 right)
    for (let i = k; i < bars.length - k; i++) {
      const b = bars[i];
      let isH = true;
      let isL = true;
      for (let j = 1; j <= k; j++) {
        if (bars[i - j].high >= b.high || bars[i + j].high >= b.high) isH = false;
        if (bars[i - j].low <= b.low || bars[i + j].low <= b.low) isL = false;
      }
      if (isH) {
        const prev = swingHighs[swingHighs.length - 1];
        const isHH = !prev || b.high > prev.price;
        swingHighs.push({ time: b.time, price: b.high, isHH });
        markers.push({
          time: b.time,
          position: 'aboveBar',
          color: isHH ? '#089981' : '#f23645',
          shape: 'circle',
          text: isHH ? 'HH' : 'LH'
        });
      }
      if (isL) {
        const prev = swingLows[swingLows.length - 1];
        const isHL = !prev || b.low > prev.price;
        swingLows.push({ time: b.time, price: b.low, isHL });
        markers.push({
          time: b.time,
          position: 'belowBar',
          color: isHL ? '#089981' : '#f23645',
          shape: 'circle',
          text: isHL ? 'HL' : 'LL'
        });
      }
    }

    // Set markers on candle series
    try {
      (seriesRef.current as any).setMarkers(markers);
    } catch (e) {}

    // Update active Break of Structure (BOS) Level Price Line
    const lastBar = bars[bars.length - 1];
    const lastHigh = swingHighs[swingHighs.length - 1];
    const lastLow = swingLows[swingLows.length - 1];

    if (bosPriceLineRef.current && seriesRef.current) {
      try { seriesRef.current.removePriceLine(bosPriceLineRef.current); } catch (e) {}
      bosPriceLineRef.current = null;
    }

    if (seriesRef.current) {
      if (lastHigh && lastBar && lastBar.close > lastHigh.price) {
        bosPriceLineRef.current = seriesRef.current.createPriceLine({
          price: lastHigh.price,
          color: '#089981',
          lineWidth: 1,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: `BOS BREAK ${lastHigh.price.toFixed(2)}`
        });
      } else if (lastLow && lastBar && lastBar.close < lastLow.price) {
        bosPriceLineRef.current = seriesRef.current.createPriceLine({
          price: lastLow.price,
          color: '#f23645',
          lineWidth: 1,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: `BOS BREAK ${lastLow.price.toFixed(2)}`
        });
      }
    }
  }, [showMarketStructure]);

  useEffect(() => {
    if (barsDataRef.current && barsDataRef.current.length > 0) {
      updateMarketStructure(barsDataRef.current);
    }
  }, [showMarketStructure, updateMarketStructure]);

  const updateSelectedPositionState = useCallback((pos: PositionTradeState | null) => {
    selectedPositionRef.current = pos;
    setSelectedPosition(pos);
  }, []);

  const suggestedDrawingIdRef = useRef<string | null>(null);
  const suggestedEntryLineRef = useRef<any>(null);
  const suggestedSlLineRef = useRef<any>(null);
  const suggestedTpLineRef = useRef<any>(null);

  const clearSuggestedDemarcation = useCallback(() => {
    if (seriesRef.current) {
      if (suggestedEntryLineRef.current) {
        try { seriesRef.current.removePriceLine(suggestedEntryLineRef.current); } catch (e) {}
        suggestedEntryLineRef.current = null;
      }
      if (suggestedSlLineRef.current) {
        try { seriesRef.current.removePriceLine(suggestedSlLineRef.current); } catch (e) {}
        suggestedSlLineRef.current = null;
      }
      if (suggestedTpLineRef.current) {
        try { seriesRef.current.removePriceLine(suggestedTpLineRef.current); } catch (e) {}
        suggestedTpLineRef.current = null;
      }
    }
    if (drawingManagerRef.current && suggestedDrawingIdRef.current) {
      try { drawingManagerRef.current.remove(suggestedDrawingIdRef.current); } catch (e) {}
      suggestedDrawingIdRef.current = null;
      drawingManagerRef.current.redraw();
    }
  }, []);

  const applySuggestedTrade = useCallback((trade: any) => {
    if (!trade || !seriesRef.current) return;
    const series = seriesRef.current;
    const dm = drawingManagerRef.current;

    const isLong = trade.kind === 'long-position';
    const entry = Number(trade.entry);
    const sl = Number(trade.sl);
    const tp = Number(trade.tp);
    const stopDist = Number(Math.max(0.1, isLong ? entry - sl : sl - entry).toFixed(2));
    const profitDist = Number(Math.max(0.1, isLong ? tp - entry : entry - tp).toFixed(2));
    const rrr = (profitDist / Math.max(0.01, stopDist)).toFixed(1);

    // 1. Clear previous suggested price lines & drawings
    clearSuggestedDemarcation();

    // 2. Create distinct, labeled price lines on price axis
    suggestedEntryLineRef.current = series.createPriceLine({
      price: entry,
      color: '#2962ff',
      lineWidth: 2,
      lineStyle: 0, // Solid
      axisLabelVisible: true,
      title: `🎯 ${isLong ? 'BUY' : 'SELL'} ENTRY ${entry.toFixed(2)}`
    });

    suggestedSlLineRef.current = series.createPriceLine({
      price: sl,
      color: '#f23645',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: `🛑 STRUCTURAL SL ${sl.toFixed(2)}`
    });

    suggestedTpLineRef.current = series.createPriceLine({
      price: tp,
      color: '#089981',
      lineWidth: 2,
      lineStyle: 2, // Dashed
      axisLabelVisible: true,
      title: `🏆 TARGET TP ${tp.toFixed(2)} (1:${rrr} R:R)`
    });

    // 3. Add interactive LONG/SHRT position drawing box to DrawingManager canvas
    let newId = trade.id || `sug-${Date.now()}`;
    if (dm) {
      const barData = (series.data() as any[]) || [];
      const lastBar = barData[barData.length - 1];
      const currentTime = lastBar?.time || latestBarRef.current?.time || Math.floor(Date.now() / 1000);
      const barInterval = getBarIntervalSeconds(timeframe);
      const futureTime = currentTime + barInterval * 16;

      newId = dm.add({
        kind: trade.kind,
        points: [
          { time: currentTime as any, price: entry },
          { time: futureTime as any, price: entry }
        ],
        style: {
          stopLevel: stopDist,
          profitLevel: profitDist
        }
      });
      suggestedDrawingIdRef.current = newId;
      dm.select([newId]);
      dm.redraw();
    }

    // 4. Update position state with exact distance values so card calculates risk & RR accurately
    updateSelectedPositionState({
      id: newId,
      kind: trade.kind,
      entry,
      sl,
      tp,
      stopLevel: stopDist,
      profitLevel: profitDist
    });

    // 5. Scroll time scale to realtime so user immediately sees setup demarcated
    if (chartRef.current) {
      try {
        chartRef.current.timeScale().scrollToRealTime();
      } catch (e) {}
    }
  }, [timeframe, clearSuggestedDemarcation, updateSelectedPositionState]);

  useEffect(() => {
    if (suggestedTrade) {
      applySuggestedTrade(suggestedTrade);
    } else {
      clearSuggestedDemarcation();
    }
  }, [suggestedTrade, applySuggestedTrade, clearSuggestedDemarcation]);

  const prevSymbolRef = useRef<string>(symbol);

  useEffect(() => {
    if (!drawingManagerRef.current) {
      prevSymbolRef.current = symbol;
      return;
    }

    // If switching to a DIFFERENT symbol: persist previous symbol's drawings, then load new symbol's
    if (prevSymbolRef.current !== symbol) {
      if (!isRestoring.current) {
        try {
          const oldDrawings = drawingManagerRef.current.exportJSON();
          localStorage.setItem(`drawings_${prevSymbolRef.current}`, oldDrawings);
        } catch (e) {
          console.warn("Failed to export drawings on symbol switch", e);
        }
      }

      isRestoring.current = true;
      drawingManagerRef.current.clear();
      const newSaved = localStorage.getItem(`drawings_${symbol}`);
      if (newSaved) {
        try { drawingManagerRef.current.importJSON(newSaved); } catch(e){}
      }
      drawingManagerRef.current.redraw();
      prevSymbolRef.current = symbol;
      setTimeout(() => { isRestoring.current = false; }, 200);
    }
  }, [symbol]);

  const handleDrawingChange = useCallback((changes: Partial<DrawingFormatState>) => {
    setSelectedDrawing(prev => {
      if (!prev || !drawingManagerRef.current) return null;
      const next = { ...prev, ...changes };
      const d = drawingManagerRef.current.get(next.id) as any;
      if (d) {
        const updated: any = {
          ...d,
          text: next.text,
          locked: next.locked,
          style: {
            ...d.style,
            backgroundColor: next.fillColor,
            transparency: 100 - next.fillOpacity,
            fillBackground: next.fillOpacity > 0,
            color: next.borderColor,
            width: next.borderWidth,
            text: next.text,
            textColor: next.textColor,
            fontSize: next.fontSize,
            bold: next.bold,
            showText: Boolean(next.text)
          }
        };
        drawingManagerRef.current.update(updated);
      }
      return next;
    });
  }, []);

  const handleDrawingDelete = useCallback(() => {
    if (selectedDrawing && drawingManagerRef.current) {
      drawingManagerRef.current.remove(selectedDrawing.id);
      setSelectedDrawing(null);
    }
  }, [selectedDrawing]);

  const spawnPosition = useCallback((side: 'Buy' | 'Sell') => {
    if (!drawingManagerRef.current) return;
    const dm = drawingManagerRef.current;
    const isLong = side === 'Buy';
    const kind = isLong ? 'long-position' : 'short-position';

    const currentPrice = Number(((isLong ? (bidAsk.ask > 0 ? bidAsk.ask : 0) : (bidAsk.bid > 0 ? bidAsk.bid : 0)) ||
      latestBarRef.current?.close || (legend ? legend.close : 1000)).toFixed(2));
    const currentTime = latestBarRef.current?.time || Math.floor(Date.now() / 1000);

    const barData = (seriesRef.current?.data() as any[]) || [];
    const recent14 = barData.slice(-14);
    const recent5 = barData.slice(-5);
    const recent2 = barData.slice(-2);
    const recent60 = barData.slice(-60);
    let stopD = Math.max(10, Number((currentPrice * 0.0025).toFixed(2)));
    let profitD = Number((stopD * 5.5).toFixed(2));

    if (recent14.length > 0 && recent5.length > 0) {
      const avgRange = recent14.reduce((acc: number, b: any) => acc + Math.max(1, Number(b.high) - Number(b.low)), 0) / recent14.length;
      const minStopDist = Math.max(8, Number((0.40 * avgRange).toFixed(2)));
      const maxStopDist = Math.max(minStopDist * 1.6, Number((0.88 * avgRange).toFixed(2)));
      const wickPad = Math.max(3, Number((0.15 * avgRange).toFixed(2)));
      if (isLong) {
        const recentLow5 = Math.min(...recent5.map((b: any) => Number(b.low)));
        const recentLow2 = Math.min(...recent2.map((b: any) => Number(b.low)));
        const boundedSl = Math.max(Math.min(recentLow5 - wickPad, currentPrice - minStopDist), currentPrice - maxStopDist);
        const slPrice = Math.min(boundedSl, recentLow2 - wickPad, currentPrice - minStopDist);
        stopD = Math.max(minStopDist, Number((currentPrice - slPrice).toFixed(2)));
        const structHigh = recent60.length > 0 ? Math.max(...recent60.map((b: any) => Number(b.high))) : currentPrice + 5.8 * stopD;
        profitD = Number(Math.min(Math.max(structHigh - currentPrice, 5.2 * stopD), 9.2 * stopD).toFixed(2));
      } else {
        const recentHigh5 = Math.max(...recent5.map((b: any) => Number(b.high)));
        const recentHigh2 = Math.max(...recent2.map((b: any) => Number(b.high)));
        const boundedSl = Math.min(Math.max(recentHigh5 + wickPad, currentPrice + minStopDist), currentPrice + maxStopDist);
        const slPrice = Math.max(boundedSl, recentHigh2 + wickPad, currentPrice + minStopDist);
        stopD = Math.max(minStopDist, Number((slPrice - currentPrice).toFixed(2)));
        const structLow = recent60.length > 0 ? Math.min(...recent60.map((b: any) => Number(b.low))) : currentPrice - 5.8 * stopD;
        profitD = Number(Math.min(Math.max(currentPrice - structLow, 5.2 * stopD), 9.2 * stopD).toFixed(2));
      }
    }

    const barInterval = getBarIntervalSeconds(timeframe);
    const futureTime = currentTime + barInterval * 12;

    const newId = dm.add({
      kind,
      points: [
        { time: currentTime as any, price: currentPrice },
        { time: futureTime as any, price: currentPrice }
      ],
      style: {
        stopLevel: stopD,
        profitLevel: profitD
      }
    });

    const slPrice = Number((isLong ? currentPrice - stopD : currentPrice + stopD).toFixed(2));
    const tpPrice = Number((isLong ? currentPrice + profitD : currentPrice - profitD).toFixed(2));

    dm.select([newId]);
    dm.redraw();
    updateSelectedPositionState({
      id: newId,
      kind,
      entry: currentPrice,
      sl: slPrice,
      tp: tpPrice,
      stopLevel: stopD,
      profitLevel: profitD
    });
  }, [bidAsk, legend, timeframe, updateSelectedPositionState]);

  const handleUpdateSl = useCallback((newSl: number) => {
    setSelectedPosition(prev => {
      if (!prev || !drawingManagerRef.current) return null;
      const dm = drawingManagerRef.current;
      const d = dm.get(prev.id) as any;
      if (!d) return prev;
      const isLong = prev.kind === 'long-position';
      const newStopDist = isLong ? Math.max(0.1, prev.entry - newSl) : Math.max(0.1, newSl - prev.entry);
      const updated = {
        ...d,
        style: {
          ...d.style,
          stopLevel: newStopDist
        }
      };
      dm.update(updated);
      dm.redraw();
      const next = {
        ...prev,
        stopLevel: newStopDist,
        sl: newSl
      };
      selectedPositionRef.current = next;
      return next;
    });
  }, []);

  const handleUpdateTp = useCallback((newTp: number) => {
    setSelectedPosition(prev => {
      if (!prev || !drawingManagerRef.current) return null;
      const dm = drawingManagerRef.current;
      const d = dm.get(prev.id) as any;
      if (!d) return prev;
      const isLong = prev.kind === 'long-position';
      const newProfitDist = isLong ? Math.max(0.1, newTp - prev.entry) : Math.max(0.1, prev.entry - newTp);
      const updated = {
        ...d,
        style: {
          ...d.style,
          profitLevel: newProfitDist
        }
      };
      dm.update(updated);
      dm.redraw();
      const next = {
        ...prev,
        profitLevel: newProfitDist,
        tp: newTp
      };
      selectedPositionRef.current = next;
      return next;
    });
  }, []);

  const handleUpdateEntry = useCallback((newEntry: number) => {
    setSelectedPosition(prev => {
      if (!prev || !drawingManagerRef.current) return null;
      const dm = drawingManagerRef.current;
      const d = dm.get(prev.id) as any;
      if (!d) return prev;
      const isLong = prev.kind === 'long-position';
      const updated = {
        ...d,
        points: [
          { ...d.points[0], price: newEntry },
          { ...d.points[1], price: newEntry }
        ]
      };
      dm.update(updated);
      dm.redraw();
      const sl = isLong ? (newEntry - prev.stopLevel) : (newEntry + prev.stopLevel);
      const tp = isLong ? (newEntry + prev.profitLevel) : (newEntry - prev.profitLevel);
      const next = {
        ...prev,
        entry: newEntry,
        sl,
        tp
      };
      selectedPositionRef.current = next;
      return next;
    });
  }, []);

  const handleDeletePosition = useCallback(() => {
    if (selectedPosition && drawingManagerRef.current) {
      drawingManagerRef.current.remove(selectedPosition.id);
      updateSelectedPositionState(null);
    }
  }, [selectedPosition, updateSelectedPositionState]);

  const handleClosePositionCard = useCallback(() => {
    updateSelectedPositionState(null);
    drawingManagerRef.current?.select([]);
  }, [updateSelectedPositionState]);

  const reconcileWithMt5 = useCallback((mt5Bars: any[]) => {
    if (!seriesRef.current || !volumeSeriesRef.current || !mt5Bars || mt5Bars.length === 0) return;
    
    const currentSeries = seriesRef.current;
    const currentVolumeSeries = volumeSeriesRef.current;
    const currentData = (currentSeries.data() as any[]) || [];
    if (currentData.length === 0) return;

    const currentVolData = (currentVolumeSeries.data() as any[]) || [];

    let desyncDetected = false;
    let olderBarsChanged = false;
    let fixedCount = 0;

    const timeToIndex = new Map<number, number>();
    for (let i = 0; i < currentData.length; i++) {
      timeToIndex.set(Number(currentData[i].time), i);
    }

    const lastChartBarTime = Number(currentData[currentData.length - 1].time);
    const updatedData = [...currentData];
    const updatedVolData = [...currentVolData];

    for (const bar of mt5Bars) {
      const barTime = Number(bar.time);
      const existingIdx = timeToIndex.get(barTime);

      if (existingIdx !== undefined) {
        const existing = updatedData[existingIdx];
        const isDifferent =
          Math.abs(existing.open - bar.open) > 1e-4 ||
          Math.abs(existing.high - bar.high) > 1e-4 ||
          Math.abs(existing.low - bar.low) > 1e-4 ||
          Math.abs(existing.close - bar.close) > 1e-4;

        if (isDifferent) {
          desyncDetected = true;
          fixedCount++;
          updatedData[existingIdx] = {
            time: bar.time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close
          };

          if (existingIdx !== currentData.length - 1) {
            olderBarsChanged = true;
          }

          if (existingIdx < updatedVolData.length) {
            updatedVolData[existingIdx] = {
              time: bar.time,
              value: bar.volume ?? 0,
              color: bar.close >= bar.open ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)'
            };
          }
        }
      } else if (barTime > lastChartBarTime) {
        desyncDetected = true;
        fixedCount++;
        try {
          currentSeries.update(bar);
          currentVolumeSeries.update({
            time: bar.time,
            value: bar.volume ?? 0,
            color: bar.close >= bar.open ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)'
          });
        } catch (e) {
          console.warn("Failed to append missing MT5 bar", e);
        }
      }
    }

    if (olderBarsChanged) {
      console.info(`[MT5 Accuracy Reconciler] Healed ${fixedCount} historical bar discrepancy(s) with MT5 truth.`);
      currentSeries.setData(updatedData);
      currentVolumeSeries.setData(updatedVolData);
    } else if (desyncDetected) {
      const latestVerified = mt5Bars[mt5Bars.length - 1];
      currentSeries.update(latestVerified);
      currentVolumeSeries.update({
        time: latestVerified.time,
        value: latestVerified.volume ?? 0,
        color: latestVerified.close >= latestVerified.open ? 'rgba(8, 153, 129, 0.35)' : 'rgba(242, 54, 69, 0.35)'
      });
    }

    totalDesyncHealedRef.current += fixedCount;
    lastVerifiedTimeRef.current = Date.now();

    cbRef.current.onCandleAccuracyUpdate?.({
      status: 'verified',
      lastVerifiedTime: Date.now(),
      desyncFixedCount: totalDesyncHealedRef.current,
      verifiedBarsCount: mt5Bars.length,
      accuracyPct: 100
    });
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // TradingView Dark theme layout
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#131722' },
        textColor: '#787b86',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0.4)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.4)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: '#787b86',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1e222d',
        },
        horzLine: {
          color: '#787b86',
          width: 1,
          style: 3,
          labelBackgroundColor: '#1e222d',
        },
      },
      rightPriceScale: {
        borderColor: '#2a2e39',
        scaleMargins: {
          top: 0.1,
          bottom: 0.15,
        },
      },
      timeScale: {
        borderColor: '#2a2e39',
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: any) => {
          if (!time) return '';
          const d = new Date(time * 1000);
          return d.toLocaleTimeString('en-US', { timeZone: 'UTC', hour12: false, hour: '2-digit', minute: '2-digit' });
        }
      },
      localization: {
        timeFormatter: (time: any) => {
          if (!time) return '';
          const d = new Date(time * 1000);
          return d.toLocaleString('en-US', { timeZone: 'UTC', hour12: false, month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        }
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
    });
    
    chartRef.current = chart;

    // Authentic TradingView Candle Colors
    const mainSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#089981',
      downColor: '#f23645',
      borderVisible: true,
      borderUpColor: '#089981',
      borderDownColor: '#f23645',
      wickUpColor: '#089981',
      wickDownColor: '#f23645',
    });
    seriesRef.current = mainSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: 'rgba(8, 153, 129, 0.15)',
      priceFormat: { type: 'volume' },
      priceScaleId: '', 
    });
    
    chart.priceScale('').applyOptions({
      scaleMargins: { top: 0.90, bottom: 0 },
    });
    volumeSeriesRef.current = volumeSeries;

    try {
      const dm = new DrawingManager(chart, mainSeries, { magnet: isMagnetOn ? 'weak' : 'off' });
      dm.setInterval(undefined);
      drawingManagerRef.current = dm;
      
      // Load saved drawings for initial symbol
      const initialSaved = localStorage.getItem(`drawings_${symbol}`);
      if (initialSaved) {
        isRestoring.current = true;
        try {
          dm.importJSON(initialSaved);
        } catch (e) {
          console.warn("Initial drawings import failed", e);
        }
        setTimeout(() => { isRestoring.current = false; }, 200);
      }

      const handleChange = () => {
        if (isRestoring.current) return;

        // Keep active position trade parameters synced in real-time as user drags anchors
        if (selectedPositionRef.current && drawingManagerRef.current) {
          const d = drawingManagerRef.current.get(selectedPositionRef.current.id) as any;
          if (d && (d.kind === 'long-position' || d.kind === 'short-position')) {
            const isLong = d.kind === 'long-position';
            const entry = d.points?.[0]?.price ?? 0;
            const stopDist = d.style?.stopLevel ?? (d.points?.[1] ? Math.abs(d.points[1].price - entry) : 20);
            const profitDist = d.style?.profitLevel ?? (stopDist * 2);
            const sl = isLong ? (entry - stopDist) : (entry + stopDist);
            const tp = isLong ? (entry + profitDist) : (entry - profitDist);
            updateSelectedPositionState({
              id: d.id,
              kind: d.kind,
              entry,
              sl,
              tp,
              stopLevel: stopDist,
              profitLevel: profitDist
            });
          }
        }

        if (syncTimeout.current) clearTimeout(syncTimeout.current);
        
        syncTimeout.current = setTimeout(() => {
          if (isRestoring.current) return;
          const { symbol: currentSymbol, onDrawingsUpdate } = cbRef.current;
          const drawingsStr = dm.exportJSON();
          try {
            const drawingsArr = JSON.parse(drawingsStr);
            if (!isRestoring.current) {
              localStorage.setItem(`drawings_${currentSymbol}`, drawingsStr); 
              onDrawingsUpdate?.(drawingsArr, currentSymbol);
            }
          } catch (e) { 
            console.warn('Failed to parse or persist drawings', e); 
          }
        }, 150);
      };

      dm.on('change', handleChange);
      
      dm.on('add', (d: any) => {
        if (d && (d.kind === 'long-position' || d.kind === 'short-position')) {
          dm.select([d.id]);
        }
        cbRef.current.onToolDeactivate?.();
      });

      dm.on('selection', (ids) => {
        if (!ids || ids.length === 0) {
          setSelectedDrawing(null);
          updateSelectedPositionState(null);
          return;
        }
        const d = dm.get(ids[0]) as any;
        if (!d) {
          setSelectedDrawing(null);
          updateSelectedPositionState(null);
          return;
        }

        if (d.kind === 'long-position' || d.kind === 'short-position') {
          const isLong = d.kind === 'long-position';
          const entry = d.points?.[0]?.price ?? 0;
          const stopDist = d.style?.stopLevel ?? (d.points?.[1] ? Math.abs(d.points[1].price - entry) : 20);
          const profitDist = d.style?.profitLevel ?? (stopDist * 2);
          const sl = isLong ? (entry - stopDist) : (entry + stopDist);
          const tp = isLong ? (entry + profitDist) : (entry - profitDist);
          updateSelectedPositionState({
            id: d.id,
            kind: d.kind,
            entry,
            sl,
            tp,
            stopLevel: stopDist,
            profitLevel: profitDist
          });
          setSelectedDrawing(null);
          return;
        }

        updateSelectedPositionState(null);
        const trans = d.style?.transparency ?? 50;
        const opacity = Math.round(100 - trans);
        setSelectedDrawing({
          id: d.id,
          kind: d.kind,
          fillColor: d.style?.backgroundColor || d.style?.color || '#ffd700',
          fillOpacity: d.style?.fillBackground !== false ? opacity : 0,
          borderColor: d.style?.color || '#ffffff',
          borderWidth: d.style?.width || 2,
          text: d.text || d.style?.text || '',
          textColor: d.style?.textColor || '#ffffff',
          fontSize: d.style?.fontSize || 14,
          bold: Boolean(d.style?.bold),
          locked: Boolean(d.locked)
        });
      });

    } catch(e) {
      console.error("Drawing Manager init failed", e);
    }

    // Subscribe to crosshair hover for live OHLC legend
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData) {
        isHoveringRef.current = false;
        return;
      }
      isHoveringRef.current = true;
      const data = param.seriesData.get(mainSeries) as any;
      if (data && data.open !== undefined) {
        const chg = data.close - data.open;
        const pct = data.open ? (chg / data.open) * 100 : 0;
        setLegend({
          open: data.open,
          high: data.high,
          low: data.low,
          close: data.close,
          change: chg,
          changePct: pct
        });
      }
    });

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (syncTimeout.current) clearTimeout(syncTimeout.current);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({ visible: showVolume });
    }
  }, [showVolume]);

  useEffect(() => {
    if (drawingManagerRef.current) {
      if (activeTool) {
        drawingManagerRef.current.setTool(activeTool);
      } else {
        drawingManagerRef.current.setTool(null);
      }
    }
  }, [activeTool]);

  useEffect(() => {
    if (drawingManagerRef.current) {
      try {
        drawingManagerRef.current.setMagnet(isMagnetOn ? 'weak' : 'off');
      } catch (e) {
        console.warn("Failed to set magnet mode", e);
      }
    }
  }, [isMagnetOn]);

  // Draw live MT5 open positions, pending orders, and live Ask line on chart
  useEffect(() => {
    if (!seriesRef.current) return;
    
    // Clear previous live price lines
    livePriceLinesRef.current.forEach(l => {
      try { seriesRef.current?.removePriceLine(l); } catch(e){}
    });
    livePriceLinesRef.current = [];

    const symClean = symbol.replace(/_/g, ' ');

    // 1. Render Open Positions
    if (positions && positions.length > 0) {
      const symbolPos = positions.filter((p: any) => p.symbol === symClean || p.symbol === symbol || p.symbol.replace(/_/g, ' ') === symClean);

      symbolPos.forEach((p: any) => {
        if (!seriesRef.current) return;
        const isBuy = p.type === 'Buy';
        const pnlPrefix = p.profit >= 0 ? '+' : '';
        
        try {
          // Entry price line
          const entryLine = seriesRef.current.createPriceLine({
            price: p.price_open,
            color: isBuy ? '#2962ff' : '#f23645',
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: `#${p.ticket} ${p.type.toUpperCase()} ${p.volume} (${pnlPrefix}$${p.profit.toFixed(2)})`,
          });
          livePriceLinesRef.current.push(entryLine);

          // Stop Loss line
          if (p.sl > 0) {
            const slLine = seriesRef.current.createPriceLine({
              price: p.sl,
              color: '#f23645',
              lineWidth: 1,
              lineStyle: 2, // Dashed
              axisLabelVisible: true,
              title: `SL #${p.ticket} (${p.sl.toFixed(2)})`,
            });
            livePriceLinesRef.current.push(slLine);
          }

          // Take Profit line
          if (p.tp > 0) {
            const tpLine = seriesRef.current.createPriceLine({
              price: p.tp,
              color: '#089981',
              lineWidth: 1,
              lineStyle: 2, // Dashed
              axisLabelVisible: true,
              title: `TP #${p.ticket} (${p.tp.toFixed(2)})`,
            });
            livePriceLinesRef.current.push(tpLine);
          }
        } catch (err) {
          console.warn("Failed to create position price line", err);
        }
      });
    }

    // 2. Render Pending Orders (Buy Stop, Sell Stop, Buy Limit, Sell Limit, On Close)
    if (pendingOrders && pendingOrders.length > 0) {
      const symbolOrders = pendingOrders.filter((o: any) => o.symbol === symClean || o.symbol === symbol || o.symbol.replace(/_/g, ' ') === symClean);

      symbolOrders.forEach((o: any) => {
        if (!seriesRef.current) return;
        const isStop = o.type.toLowerCase().includes('stop');
        const isBuy = o.type.toLowerCase().includes('buy');
        const orderColor = isStop ? (isBuy ? '#089981' : '#f23645') : (isBuy ? '#2962ff' : '#ff9800');

        try {
          // Trigger price line (dashed)
          const triggerLine = seriesRef.current.createPriceLine({
            price: o.price_open,
            color: orderColor,
            lineWidth: 2,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: `🛑 #${o.ticket} ${o.type.toUpperCase()} ${o.volume}L @ ${o.price_open.toFixed(2)}`,
          });
          livePriceLinesRef.current.push(triggerLine);

          // Pending SL line
          if (o.sl > 0) {
            const slLine = seriesRef.current.createPriceLine({
              price: o.sl,
              color: '#f23645',
              lineWidth: 1,
              lineStyle: 3, // Dotted
              axisLabelVisible: true,
              title: `SL #${o.ticket} (${o.sl.toFixed(2)})`,
            });
            livePriceLinesRef.current.push(slLine);
          }

          // Pending TP line
          if (o.tp > 0) {
            const tpLine = seriesRef.current.createPriceLine({
              price: o.tp,
              color: '#089981',
              lineWidth: 1,
              lineStyle: 3, // Dotted
              axisLabelVisible: true,
              title: `TP #${o.ticket} (${o.tp.toFixed(2)})`,
            });
            livePriceLinesRef.current.push(tpLine);
          }
        } catch (err) {
          console.warn("Failed to create pending order price line", err);
        }
      });
    }

    // 3. Live Ask line for real-time spread gap visualization
    if (bidAsk.ask > 0 && seriesRef.current) {
      try {
        const askLine = seriesRef.current.createPriceLine({
          price: bidAsk.ask,
          color: 'rgba(242, 54, 69, 0.45)',
          lineWidth: 1,
          lineStyle: 3, // Dotted
          axisLabelVisible: true,
          title: `Ask ${bidAsk.ask.toFixed(2)}`,
        });
        livePriceLinesRef.current.push(askLine);
      } catch (e) {}
    }

    return () => {
      livePriceLinesRef.current.forEach(l => {
        try { seriesRef.current?.removePriceLine(l); } catch(e){}
      });
      livePriceLinesRef.current = [];
    };
  }, [positions, pendingOrders, symbol, bidAsk.ask]);

  // Persistent WebSocket stream: single connection, never torn down on timeframe switches
  useEffect(() => {
    let reconnectTimer: any = null;
    let isMounted = true;

    function connectWs() {
      if (!isMounted) return;
      if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
        return;
      }
      const ws = new WebSocket('ws://127.0.0.1:8000/replay/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        ws.send(JSON.stringify({ symbol: cbRef.current.symbol, timeframe }));
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'watchlist' && Array.isArray(msg.data)) {
            cbRef.current.onWatchlistUpdate?.(msg.data);
            const curSymClean = (cbRef.current.symbol || '').replace(/_/g, ' ');
            const currentItem = msg.data.find((x: any) => x.symbol === cbRef.current.symbol || (x.symbol && x.symbol.replace(/_/g, ' ') === curSymClean));
            if (currentItem) {
              setBidAsk({ bid: currentItem.bid, ask: currentItem.ask });
            }
            return;
          }

          if (msg.type === 'candles_verify' && Array.isArray(msg.bars)) {
            reconcileWithMt5(msg.bars);
            return;
          }

          const candle = msg.candle || (Array.isArray(msg.bars) ? msg.bars[msg.bars.length - 1] : msg);
          if (candle && candle.time && candle.close !== undefined) {
            latestBarRef.current = { time: candle.time, close: candle.close };
            try {
              seriesRef.current?.update(candle);
              if (barsDataRef.current.length > 0) {
                const lastIdx = barsDataRef.current.length - 1;
                if (barsDataRef.current[lastIdx].time === candle.time) {
                  barsDataRef.current[lastIdx] = candle;
                } else if (candle.time > barsDataRef.current[lastIdx].time) {
                  barsDataRef.current.push(candle);
                }
              }
              volumeSeriesRef.current?.update({
                time: candle.time,
                value: candle.volume ?? 0,
                color: candle.close >= candle.open ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)'
              });
              cbRef.current.onTick?.(candle);

              if (!isHoveringRef.current) {
                const chg = candle.close - candle.open;
                const pct = candle.open ? (chg / candle.open) * 100 : 0;
                setLegend({
                  open: candle.open,
                  high: candle.high,
                  low: candle.low,
                  close: candle.close,
                  change: chg,
                  changePct: pct
                });
              }
            } catch (updateErr) {
              console.warn("Chart series update error:", updateErr);
            }
          }
        } catch (e) {
          console.error("WS Parse error", e);
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        reconnectTimer = setTimeout(connectWs, 2000);
      };

      ws.onerror = () => {
        try { ws.close(); } catch(e){}
      };
    }

    connectWs();

    return () => {
      isMounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch(e){}
        wsRef.current = null;
      }
    };
  }, []);

  // Update stream subscription on symbol / timeframe switch without closing WebSocket
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ symbol, timeframe }));
    }
  }, [symbol, timeframe]);

  // Fast candle loading and timeline lock on symbol / timeframe change
  useEffect(() => {
    let active = true;
    const abortController = new AbortController();

    if (drawingManagerRef.current) {
      drawingManagerRef.current.setInterval(undefined);
    }

    async function loadData() {
      let targetCenterTime: number | null = null;
      let wasAtRealTime = false;
      if (chartRef.current) {
        try {
          const ts = chartRef.current.timeScale();
          const vr = ts.getVisibleRange();
          const sp = ts.scrollPosition();
          const lastLoadedTime = latestBarRef.current?.time || (barsDataRef.current.length > 0 ? barsDataRef.current[barsDataRef.current.length - 1].time : 0);
          
          wasAtRealTime = Boolean((sp !== null && sp >= -4 && sp <= 6) || (vr && vr.to && lastLoadedTime > 0 && Number(vr.to) >= (lastLoadedTime - 7200)));
          if (vr && vr.from && vr.to) {
            targetCenterTime = Math.floor((Number(vr.from) + Number(vr.to)) / 2);
          }
        } catch(e) {}
      }

      try {
        isRestoring.current = true;
        const resBars = await fetch(`http://127.0.0.1:8000/bars?symbol=${symbol}&timeframe=${timeframe}&limit=2500`, { signal: abortController.signal });
        const data = await resBars.json().catch(() => []);
        
        if (!active) return;

        if (Array.isArray(data) && data.length > 0) {
          const bars = data.map((d: any) => ({
            time: d.time,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
          }));
          
          const volumes = data.map((d: any) => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(8, 153, 129, 0.15)' : 'rgba(242, 54, 69, 0.15)'
          }));

          seriesRef.current?.setData(bars);
          volumeSeriesRef.current?.setData(volumes);
          barsDataRef.current = bars;
          updateMarketStructure(bars);
          if (suggestedTrade) {
            setTimeout(() => { applySuggestedTrade(suggestedTrade); }, 80);
          }
          
          if (chartRef.current) {
            try {
              const ts = chartRef.current.timeScale();
              const barInterval = getBarIntervalSeconds(timeframe);
              if (wasAtRealTime || !targetCenterTime) {
                ts.scrollToRealTime();
              } else {
                const span = barInterval * 80;
                const newFrom = Math.max(bars[0].time, targetCenterTime - Math.floor(span / 2));
                const newTo = Math.min(bars[bars.length - 1].time + barInterval * 5, targetCenterTime + Math.floor(span / 2));
                if (newTo > newFrom) {
                  ts.setVisibleRange({ from: newFrom as any, to: newTo as any });
                } else {
                  ts.scrollToRealTime();
                }
              }
            } catch(e) {}
          }
          
          // Initialize legend with last bar
          const lastBar = bars[bars.length - 1];
          if (lastBar) {
            latestBarRef.current = { time: lastBar.time, close: lastBar.close };
            const chg = lastBar.close - lastBar.open;
            const pct = lastBar.open ? (chg / lastBar.open) * 100 : 0;
            setLegend({
              open: lastBar.open,
              high: lastBar.high,
              low: lastBar.low,
              close: lastBar.close,
              change: chg,
              changePct: pct
            });
          }

          if (drawingManagerRef.current) {
            if (drawingManagerRef.current.drawings().length === 0) {
              const saved = localStorage.getItem(`drawings_${symbol}`);
              if (saved) {
                try {
                  drawingManagerRef.current.importJSON(saved);
                } catch (e) {
                  console.warn("Drawings importJSON failed", e);
                }
              }
            }
            drawingManagerRef.current.redraw();
            setTimeout(() => { isRestoring.current = false; }, 150);
          } else {
            setTimeout(() => { isRestoring.current = false; }, 150);
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.error("Failed to load bars", err);
        }
      }
    }

    loadData();

    return () => {
      active = false;
      abortController.abort();
    };
  }, [symbol, timeframe]);

  const isUp = legend ? legend.change >= 0 : true;
  const spreadPoints = bidAsk.bid && bidAsk.ask ? (bidAsk.ask - bidAsk.bid).toFixed(1) : '10.0';

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      
      {/* Top-Left Chart Legend (TradingView Style) */}
      <div style={{
        position: 'absolute',
        top: '12px',
        left: '16px',
        zIndex: 5,
        pointerEvents: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        fontSize: '12px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif'
      }}>
        {/* Symbol header & live dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600 }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: '#089981',
            boxShadow: '0 0 6px #089981'
          }} />
          <span style={{ color: '#d1d4dc', fontSize: '13px' }}>
            {symbol.replace('_', ' ')} · {timeframe} · Weltrade Synthetics
          </span>
          <span style={{
            fontSize: '10px',
            padding: '1px 5px',
            borderRadius: '3px',
            backgroundColor: '#2a2e39',
            color: '#787b86'
          }}>
            INDEX
          </span>
        </div>

        {/* OHLC Values Bar with Live Bar Countdown */}
        {legend && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#787b86', fontSize: '12px', flexWrap: 'wrap' }}>
            <span>O <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.open.toFixed(2)}</span></span>
            <span>H <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.high.toFixed(2)}</span></span>
            <span>L <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.low.toFixed(2)}</span></span>
            <span>C <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.close.toFixed(2)}</span></span>
            <span style={{ color: isUp ? '#089981' : '#f23645', fontWeight: 600 }}>
              {isUp ? '+' : ''}{legend.change.toFixed(2)} ({isUp ? '+' : ''}{legend.changePct.toFixed(2)}%)
            </span>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '1px 6px',
              borderRadius: '4px',
              backgroundColor: 'rgba(41, 98, 255, 0.12)',
              border: '1px solid rgba(41, 98, 255, 0.3)',
              color: '#2962ff',
              fontSize: '11px',
              fontWeight: 700,
              fontFamily: 'monospace'
            }} title="Time remaining until current bar close">
              ⏱ {candleCountdown}
            </span>
          </div>
        )}

        {/* TradingView Floating Quick Order Strip */}
        {showOrderStrip && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginTop: '6px',
            pointerEvents: 'auto',
            background: '#131722',
            border: '1px solid #2a2e39',
            borderRadius: '6px',
            padding: '2px',
            boxShadow: '0 4px 14px rgba(0,0,0,0.45)',
            width: 'fit-content'
          }}>
            {/* SELL Button */}
            <button
              onClick={() => spawnPosition('Sell')}
              style={{
                background: '#f23645',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 12px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: '76px',
                transition: 'opacity 0.15s'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.88')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              title="Create Short / Sell Plan with Visual SL & TP"
            >
              <span style={{ fontSize: '13px', fontWeight: 800, fontFamily: 'monospace' }}>
                {bidAsk.bid > 0 ? bidAsk.bid.toFixed(2) : (legend ? legend.close.toFixed(2) : '-')}
              </span>
              <span style={{ fontSize: '9px', opacity: 0.9, fontWeight: 700, letterSpacing: '0.5px' }}>SELL</span>
            </button>

            {/* Lot size & spread in middle */}
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '0 8px',
              minWidth: '55px'
            }}>
              <input
                type="text"
                value={lotSize}
                onChange={(e) => setLotSize(e.target.value)}
                style={{
                  width: '42px',
                  background: '#1e222d',
                  border: '1px solid #363a45',
                  borderRadius: '3px',
                  color: '#d1d4dc',
                  fontSize: '11px',
                  fontWeight: 600,
                  textAlign: 'center',
                  padding: '2px 0'
                }}
                title="Lot Size"
              />
              <span style={{ fontSize: '9px', color: '#787b86', marginTop: '2px', fontFamily: 'monospace' }}>
                {spreadPoints}
              </span>
            </div>

            {/* BUY Button */}
            <button
              onClick={() => spawnPosition('Buy')}
              style={{
                background: '#2962ff',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 12px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: '76px',
                transition: 'opacity 0.15s'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.88')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              title="Create Long / Buy Plan with Visual SL & TP"
            >
              <span style={{ fontSize: '13px', fontWeight: 800, fontFamily: 'monospace' }}>
                {bidAsk.ask > 0 ? bidAsk.ask.toFixed(2) : (legend ? (legend.close + 2).toFixed(2) : '-')}
              </span>
              <span style={{ fontSize: '9px', opacity: 0.9, fontWeight: 700, letterSpacing: '0.5px' }}>BUY</span>
            </button>
          </div>
        )}
      </div>

      {/* Visual Trade Plan Demarcation Banner */}
      {suggestedTrade && selectedPosition && (
        <div style={{
          position: 'absolute',
          top: '12px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 14,
          backgroundColor: 'rgba(19, 23, 34, 0.96)',
          border: `1px solid ${selectedPosition.kind === 'long-position' ? '#089981' : '#f23645'}`,
          borderRadius: '6px',
          padding: '5px 14px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          fontSize: '11px',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{
              backgroundColor: selectedPosition.kind === 'long-position' ? '#089981' : '#f23645',
              color: '#fff',
              borderRadius: '3px',
              padding: '1px 6px',
              fontWeight: 800,
              fontSize: '10px'
            }}>
              {selectedPosition.kind === 'long-position' ? 'LONG PLAN' : 'SHORT PLAN'}
            </span>
            <span style={{ color: '#fff', fontWeight: 700 }}>{symbol.replace('_', ' ')}</span>
          </div>
          <span style={{ color: '#787b86' }}>|</span>
          <div><span style={{ color: '#787b86' }}>ENTRY: </span><span style={{ color: '#2962ff', fontWeight: 700 }}>{selectedPosition.entry.toFixed(2)}</span></div>
          <div><span style={{ color: '#787b86' }}>SL: </span><span style={{ color: '#f23645', fontWeight: 700 }}>{selectedPosition.sl.toFixed(2)}</span></div>
          <div><span style={{ color: '#787b86' }}>TP: </span><span style={{ color: '#089981', fontWeight: 700 }}>{selectedPosition.tp.toFixed(2)}</span></div>
          <span style={{
            backgroundColor: 'rgba(8, 153, 129, 0.18)',
            color: '#089981',
            borderRadius: '4px',
            padding: '2px 8px',
            fontWeight: 800
          }}>
            1 : {selectedPosition.stopLevel > 0 ? (selectedPosition.profitLevel / selectedPosition.stopLevel).toFixed(1) : '3.5'} R:R
          </span>
          <button
            onClick={() => {
              clearSuggestedDemarcation();
              updateSelectedPositionState(null);
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#787b86',
              cursor: 'pointer',
              padding: '2px 4px',
              fontSize: '12px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center'
            }}
            title="Clear Plan Demarcation Lines"
          >
            ✕
          </button>
        </div>
      )}

      {/* TradingView Right-Scale Floating Candle Countdown Pill */}
      <div style={{
        position: 'absolute',
        right: '72px',
        top: '12px',
        zIndex: 15,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        backgroundColor: '#131722',
        border: '1px solid #2a2e39',
        borderRadius: '4px',
        padding: '3px 8px',
        color: '#089981',
        fontSize: '11px',
        fontWeight: 700,
        fontFamily: 'monospace',
        boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
        pointerEvents: 'none'
      }}>
        <span style={{ color: '#787b86', fontSize: '10px' }}>CLOSE IN:</span>
        <span style={{ color: '#089981' }}>{candleCountdown}</span>
      </div>

      {/* Floating TradingView Drawing Formatting Toolbar */}
      {selectedDrawing && (
        <DrawingToolbar
          drawing={selectedDrawing}
          onChange={handleDrawingChange}
          onDelete={handleDrawingDelete}
          onClose={() => {
            setSelectedDrawing(null);
            drawingManagerRef.current?.select([]);
          }}
        />
      )}

      {/* Floating TradingView Trade Confirmation Card for Position Tools */}
      {selectedPosition && (
        <TradeConfirmationCard
          position={selectedPosition}
          symbol={symbol}
          timeframe={timeframe}
          initialVolume={lotSize}
          positions={positions}
          onUpdateSl={handleUpdateSl}
          onUpdateTp={handleUpdateTp}
          onUpdateEntry={handleUpdateEntry}
          onDelete={handleDeletePosition}
          onClose={handleClosePositionCard}
          onOrderSuccess={(ticket, comment) => onOrderSuccess?.(ticket, comment)}
        />
      )}

      {/* Main Chart Container */}
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
    </div>
  );
}
