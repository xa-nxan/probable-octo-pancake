import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi, ISeriesApi, SeriesMarker, Time } from 'lightweight-charts';
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
  activeTool: string | null;
  onToolDeactivate: () => void;
  onDrawingsUpdate: (drawings: any[], symbol: string) => void;
  onTick: (candle: any) => void;
  onWatchlistUpdate?: (data: any[]) => void;
  onOrderSuccess?: (ticket: number) => void;
  activeBacktestTrade?: any | null;
  positions?: any[];
  pendingOrders?: any[];
  onCandleAccuracyUpdate?: (accuracy: CandleAccuracy) => void;
  isMagnetOn?: boolean;
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
  activeTool,
  onToolDeactivate,
  onDrawingsUpdate,
  onTick,
  onWatchlistUpdate,
  onOrderSuccess,
  activeBacktestTrade,
  positions,
  pendingOrders,
  onCandleAccuracyUpdate,
  isMagnetOn = false
}: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  
  const cbRef = useRef({ onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol });
  useEffect(() => {
    cbRef.current = { onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol };
  }, [onToolDeactivate, onDrawingsUpdate, onTick, onWatchlistUpdate, onCandleAccuracyUpdate, symbol]);

  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const markersPluginRef = useRef<any>(null);
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

  const selectedPositionRef = useRef<PositionTradeState | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<PositionTradeState | null>(null);
  const latestBarRef = useRef<{ time: number; close: number } | null>(null);
  const totalDesyncHealedRef = useRef<number>(0);
  const lastVerifiedTimeRef = useRef<number>(0);

  const brokenLevelLineRef = useRef<any>(null);

  const updateSelectedPositionState = useCallback((pos: PositionTradeState | null) => {
    selectedPositionRef.current = pos;
    setSelectedPosition(pos);
  }, []);

  const drawBacktestTrade = useCallback((trade: any) => {
    if (!trade || !drawingManagerRef.current || !chartRef.current) return;
    const dm = drawingManagerRef.current;
    isRestoring.current = true;
    dm.clear();
    updateSelectedPositionState(null);

    const stopD = trade.stopDist || Math.abs(trade.sl - trade.entry);
    const profitD = trade.profitDist || Math.abs(trade.tp - trade.entry);
    const endTime = trade.exitTime || (trade.entryTime + 1800);

    dm.add({
      kind: trade.type,
      points: [
        { time: trade.entryTime as any, price: trade.entry },
        { time: endTime as any, price: trade.entry }
      ],
      style: {
        stopLevel: stopD,
        profitLevel: profitD
      }
    });

    // Keep selection unselected so TradeConfirmationCard live order popup never opens during replay
    dm.select([]);
    dm.redraw();
    setTimeout(() => { isRestoring.current = false; }, 100);

    // Draw horizontal dashed Broken Level line so the structural resistance/support is visible
    if (brokenLevelLineRef.current && seriesRef.current) {
      try { seriesRef.current.removePriceLine(brokenLevelLineRef.current); } catch(e){}
      brokenLevelLineRef.current = null;
    }
    if (trade.brokenLevel && seriesRef.current) {
      const isPullback = trade.setup?.includes('Pullback');
      const isShort = trade.type === 'short-position';
      const title = isPullback 
        ? (isShort ? '⚡ Broken Resistance (TP)' : '⚡ Broken Support (TP)')
        : (isShort ? '🔄 Broken Support' : '🔄 Broken Resistance');
      try {
        brokenLevelLineRef.current = seriesRef.current.createPriceLine({
          price: trade.brokenLevel,
          color: '#ff9800',
          lineWidth: 2,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: `${title} (${trade.brokenLevel.toFixed(2)})`
        });
      } catch(e){}
    }

    setTimeout(() => {
      if (!chartRef.current) return;
      try {
        const barInterval = getBarIntervalSeconds(timeframe);
        const margin = barInterval * 35;
        const tFrom = Math.max(0, trade.entryTime - margin);
        const tTo = (trade.exitTime || (trade.entryTime + barInterval * 12)) + margin;
        chartRef.current.timeScale().setVisibleRange({
          from: tFrom as any,
          to: tTo as any
        });
      } catch (e) {
        console.warn("setVisibleRange error", e);
      }
    }, 50);
  }, [timeframe, updateSelectedPositionState]);

  const prevSymbolRef = useRef<string>(symbol);
  const prevBacktestTradeRef = useRef<any>(null);

  useEffect(() => {
    if (activeBacktestTrade) {
      drawBacktestTrade(activeBacktestTrade);
      prevBacktestTradeRef.current = activeBacktestTrade;
      return;
    }

    // Clean up broken level line when exiting replay
    if (brokenLevelLineRef.current && seriesRef.current) {
      try { seriesRef.current.removePriceLine(brokenLevelLineRef.current); } catch(e){}
      brokenLevelLineRef.current = null;
    }

    if (!drawingManagerRef.current) {
      prevBacktestTradeRef.current = null;
      prevSymbolRef.current = symbol;
      return;
    }

    // If user just exited replay mode: restore user's own saved drawings
    if (prevBacktestTradeRef.current && !activeBacktestTrade) {
      isRestoring.current = true;
      drawingManagerRef.current.clear();
      const saved = localStorage.getItem(`drawings_${symbol}`);
      if (saved) {
        try { drawingManagerRef.current.importJSON(saved); } catch(e){}
      }
      drawingManagerRef.current.redraw();
      setTimeout(() => { isRestoring.current = false; }, 200);
      prevBacktestTradeRef.current = null;
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
  }, [activeBacktestTrade, symbol, drawBacktestTrade]);

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

    const currentPrice = (isLong ? (bidAsk.ask > 0 ? bidAsk.ask : 0) : (bidAsk.bid > 0 ? bidAsk.bid : 0)) ||
      latestBarRef.current?.close || (legend ? legend.close : 1000);
    const currentTime = latestBarRef.current?.time || Math.floor(Date.now() / 1000);

    const defaultDist = Math.max(1, Math.round(currentPrice * 0.003 * 100) / 100);
    const barInterval = getBarIntervalSeconds(timeframe);
    const futureTime = currentTime + barInterval * 12;

    const newId = dm.add({
      kind,
      points: [
        { time: currentTime as any, price: currentPrice },
        { time: futureTime as any, price: currentPrice }
      ],
      style: {
        stopLevel: defaultDist,
        profitLevel: Number((defaultDist * 2).toFixed(2))
      }
    });

    dm.select([newId]);
    dm.redraw();
  }, [bidAsk, legend, timeframe]);

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
              color: bar.close >= bar.open ? 'rgba(8, 153, 129, 0.35)' : 'rgba(242, 54, 69, 0.35)'
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
            color: bar.close >= bar.open ? 'rgba(8, 153, 129, 0.35)' : 'rgba(242, 54, 69, 0.35)'
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
        mode: 0, // Crosshair mode normal
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
      color: 'rgba(8, 153, 129, 0.35)',
      priceFormat: { type: 'volume' },
      priceScaleId: '', 
    });
    
    chart.priceScale('').applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volumeSeriesRef.current = volumeSeries;

    try {
      markersPluginRef.current = createSeriesMarkers(mainSeries, []);
    } catch (e) {
      console.warn("Markers plugin init failed", e);
    }

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
            if (!activeBacktestTrade && !isRestoring.current) {
              localStorage.setItem(`drawings_${currentSymbol}`, drawingsStr); 
              onDrawingsUpdate(drawingsArr, currentSymbol);
            }
          } catch (e) { 
            console.warn('Failed to parse or persist drawings', e); 
          }
        }, 150);
      };

      dm.on('change', handleChange);
      
      dm.on('add', (d: any) => {
        if (d && (d.kind === 'long-position' || d.kind === 'short-position')) {
          if (!activeBacktestTrade) {
            dm.select([d.id]);
          }
        }
        cbRef.current.onToolDeactivate();
      });

      dm.on('selection', (ids) => {
        if (!ids || ids.length === 0 || activeBacktestTrade) {
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

    // 2. Render Pending Orders (Buy Stop, Sell Stop, Buy Limit, Sell Limit)
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

  useEffect(() => {
    let active = true;
    const abortController = new AbortController();
    let ws: WebSocket | null = null;
    let currentUpdateMarkers: (() => void) | null = null;

    if (drawingManagerRef.current) {
      drawingManagerRef.current.setInterval(undefined);
    }

    async function loadData() {
      // Capture current visible center timestamp before fetching so view does not jump back weeks
      let targetCenterTime: number | null = null;
      let wasAtRealTime = false;
      if (chartRef.current) {
        try {
          const ts = chartRef.current.timeScale();
          const vr = ts.getVisibleRange();
          const sp = ts.scrollPosition();
          wasAtRealTime = sp !== null && Math.abs(sp) < 2.5;
          if (vr && vr.from && vr.to) {
            targetCenterTime = Math.floor((Number(vr.from) + Number(vr.to)) / 2);
          }
        } catch(e) {}
      }

      try {
        const [resBars, resStruct] = await Promise.all([
          fetch(`http://127.0.0.1:8000/bars?symbol=${symbol}&timeframe=${timeframe}&limit=3000`, { signal: abortController.signal }),
          fetch(`http://127.0.0.1:8000/structure?symbol=${symbol}&timeframe=${timeframe}`, { signal: abortController.signal })
        ]);
        
        const data = await resBars.json().catch(() => []);
        const structData = await resStruct.json().catch(() => []);
        
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
            color: d.close >= d.open ? 'rgba(8, 153, 129, 0.35)' : 'rgba(242, 54, 69, 0.35)'
          }));

          seriesRef.current?.setData(bars);
          volumeSeriesRef.current?.setData(volumes);
          
          // Restore visible timeline window so chart stays locked on the same time
          if (chartRef.current) {
            try {
              const ts = chartRef.current.timeScale();
              const barInterval = getBarIntervalSeconds(timeframe);
              if (activeBacktestTrade) {
                const margin = barInterval * 35;
                const tradeFrom = Math.max(bars[0].time, activeBacktestTrade.entryTime - margin);
                const tradeTo = Math.min(bars[bars.length - 1].time + barInterval * 5, (activeBacktestTrade.exitTime || (activeBacktestTrade.entryTime + barInterval * 12)) + margin);
                if (tradeTo > tradeFrom) {
                  ts.setVisibleRange({ from: tradeFrom as any, to: tradeTo as any });
                }
              } else if (wasAtRealTime || !targetCenterTime) {
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

          if (activeBacktestTrade) {
            drawBacktestTrade(activeBacktestTrade);
          } else if (drawingManagerRef.current) {
            // If canvas has no drawings currently loaded, check localStorage
            if (drawingManagerRef.current.drawings().length === 0) {
              const saved = localStorage.getItem(`drawings_${symbol}`);
              if (saved) {
                isRestoring.current = true;
                try {
                  drawingManagerRef.current.importJSON(saved);
                } catch (e) {
                  console.warn("Drawings importJSON failed", e);
                }
                setTimeout(() => { isRestoring.current = false; }, 200);
              }
            }
            drawingManagerRef.current.redraw();
          }
        }
        
        const structureList = Array.isArray(structData) ? structData : [];
        
        const updateMarkers = () => {
          if (!chartRef.current || !seriesRef.current || structureList.length === 0 || !markersPluginRef.current) return;
          const logicalRange = chartRef.current.timeScale().getVisibleLogicalRange();
          if (!logicalRange) return;
          
          const margin = 200; 
          const startIdx = Math.max(0, Math.floor(logicalRange.from - margin));
          const endIdx = Math.ceil(logicalRange.to + margin);

          const barData = seriesRef.current.data();
          const startTime = barData[startIdx]?.time;
          const endTime = barData[Math.min(endIdx, barData.length - 1)]?.time;

          if (!startTime || !endTime) return;

          const markers: SeriesMarker<Time>[] = [];
          for (const s of structureList) {
            if (s.time < startTime || s.time > endTime) continue;

            const label = s.struct_macro; 
            const isHigh = label === 'HH' || label === 'LH';
            const isUp = label === 'HH' || label === 'HL';
            
            markers.push({
              time: s.time as Time,
              position: isHigh ? 'aboveBar' : 'belowBar',
              color: isUp ? '#089981' : '#f23645',
              shape: isHigh ? 'arrowDown' : 'arrowUp',
              text: label,
              size: 1,
            });
          }
          
          try {
            markersPluginRef.current.setMarkers(markers);
          } catch(e) {
            console.warn("setMarkers failed", e);
          }
        };

        if (markersPluginRef.current) {
          updateMarkers();
          currentUpdateMarkers = updateMarkers;
          chartRef.current?.timeScale().subscribeVisibleLogicalRangeChange(currentUpdateMarkers);
        }

      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.error("Failed to load data", err);
        }
      }
    }

    loadData();

    ws = new WebSocket('ws://127.0.0.1:8000/replay/ws');
    ws.onopen = () => {
      ws?.send(JSON.stringify({ symbol, timeframe }));
    };
    
    ws.onmessage = (event) => {
      if (!active) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'watchlist' && Array.isArray(msg.data)) {
          cbRef.current.onWatchlistUpdate?.(msg.data);
          const currentItem = msg.data.find((x: any) => x.symbol === symbol);
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
            volumeSeriesRef.current?.update({
              time: candle.time,
              value: candle.volume ?? 0,
              color: candle.close >= candle.open ? 'rgba(8, 153, 129, 0.35)' : 'rgba(242, 54, 69, 0.35)'
            });
            cbRef.current.onTick(candle);

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

    return () => {
      active = false;
      abortController.abort();
      if (ws) ws.close();
      if (currentUpdateMarkers && chartRef.current) {
        try {
          chartRef.current.timeScale().unsubscribeVisibleLogicalRangeChange(currentUpdateMarkers);
        } catch(e) {
          console.warn("Unsubscribe error", e);
        }
      }
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

        {/* OHLC Values Bar */}
        {legend && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#787b86', fontSize: '12px' }}>
            <span>O <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.open.toFixed(2)}</span></span>
            <span>H <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.high.toFixed(2)}</span></span>
            <span>L <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.low.toFixed(2)}</span></span>
            <span>C <span style={{ color: isUp ? '#089981' : '#f23645' }}>{legend.close.toFixed(2)}</span></span>
            <span style={{ color: isUp ? '#089981' : '#f23645', fontWeight: 600 }}>
              {isUp ? '+' : ''}{legend.change.toFixed(2)} ({isUp ? '+' : ''}{legend.changePct.toFixed(2)}%)
            </span>
          </div>
        )}

        {/* TradingView Floating Quick Order Strip */}
        {showOrderStrip && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            marginTop: '4px',
            pointerEvents: 'auto',
            background: '#181b27',
            border: '1px solid #2a2e39',
            borderRadius: '6px',
            padding: '2px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
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
                padding: '4px 10px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: '70px',
                transition: 'opacity 0.15s'
              }}
              title="Create Short / Sell Plan with Visual SL & TP"
            >
              <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                {bidAsk.bid > 0 ? bidAsk.bid.toFixed(2) : (legend ? legend.close.toFixed(2) : '-')}
              </span>
              <span style={{ fontSize: '9px', opacity: 0.85, fontWeight: 600 }}>SELL</span>
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
                  background: '#131722',
                  border: '1px solid #2a2e39',
                  borderRadius: '3px',
                  color: '#d1d4dc',
                  fontSize: '11px',
                  textAlign: 'center',
                  padding: '2px 0'
                }}
                title="Lot Size"
              />
              <span style={{ fontSize: '9px', color: '#787b86', marginTop: '2px' }}>
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
                padding: '4px 10px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: '70px',
                transition: 'opacity 0.15s'
              }}
              title="Create Long / Buy Plan with Visual SL & TP"
            >
              <span style={{ fontSize: '12px', fontWeight: 'bold' }}>
                {bidAsk.ask > 0 ? bidAsk.ask.toFixed(2) : (legend ? (legend.close + 2).toFixed(2) : '-')}
              </span>
              <span style={{ fontSize: '9px', opacity: 0.85, fontWeight: 600 }}>BUY</span>
            </button>
          </div>
        )}
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
      {selectedPosition && !activeBacktestTrade && (
        <TradeConfirmationCard
          position={selectedPosition}
          symbol={symbol}
          timeframe={timeframe}
          positions={positions}
          onUpdateSl={handleUpdateSl}
          onUpdateTp={handleUpdateTp}
          onUpdateEntry={handleUpdateEntry}
          onDelete={handleDeletePosition}
          onClose={handleClosePositionCard}
          onOrderSuccess={(ticket) => onOrderSuccess?.(ticket)}
        />
      )}

      {/* Main Chart Container */}
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%', position: 'absolute' }} />
    </div>
  );
}
