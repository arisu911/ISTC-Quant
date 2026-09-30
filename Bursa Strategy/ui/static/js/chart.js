/**
 * Bursa Strategy - TradingView Lightweight Charts Canvas Engine
 * Strict TradingView Palette Alignment, Multi-Timeframe Architecture, and Shaded Kumo Cloud Canvas Overlay.
 * Fully compatible with Microsoft Edge and Brave Browser (Shields safe).
 */

// Global single-source-of-truth references for desk_sync.js and direct console control
window.chart = null;
window.candlestickSeries = null;
window.volumeSeries = null;
window.tenkanSeries = null;
window.kijunSeries = null;
window.chikouSeries = null;
window.spanASeries = null;
window.spanBSeries = null;
window.avwapSeries = null;
window.currentSpanAData = [];
window.currentSpanBData = [];
window.currentActiveTicker = "5211.KL";
window.activeTimeframe = "1d";

// Global Shaded Kumo Cloud Canvas Renderer
function drawKumoCloud(spanADataArg, spanBDataArg) {
    if (spanADataArg && Array.isArray(spanADataArg)) window.currentSpanAData = spanADataArg;
    if (spanBDataArg && Array.isArray(spanBDataArg)) window.currentSpanBData = spanBDataArg;
    const spanAData = window.currentSpanAData || [];
    const spanBData = window.currentSpanBData || [];

    const chartContainer = document.getElementById('tradingview-main-canvas');
    if (!chartContainer || !window.chart) return;
    if (!window.spanASeries || !window.spanBSeries) return;
    if (!spanAData.length || !spanBData.length) return;

    let kumoCanvas = document.getElementById('kumo-overlay-canvas');
    if (!kumoCanvas) {
        kumoCanvas = document.createElement('canvas');
        kumoCanvas.id = 'kumo-overlay-canvas';
        kumoCanvas.style.position = 'absolute';
        kumoCanvas.style.top = '0';
        kumoCanvas.style.left = '0';
        kumoCanvas.style.width = '100%';
        kumoCanvas.style.height = '100%';
        kumoCanvas.style.pointerEvents = 'none';
        kumoCanvas.style.zIndex = '1';
        chartContainer.style.position = 'relative';
        chartContainer.appendChild(kumoCanvas);
    }

    const ctx = kumoCanvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const clientW = chartContainer.clientWidth;
    const clientH = chartContainer.clientHeight;

    if (clientW <= 0 || clientH <= 0) return;

    if (kumoCanvas.width !== clientW * dpr || kumoCanvas.height !== clientH * dpr) {
        kumoCanvas.width = clientW * dpr;
        kumoCanvas.height = clientH * dpr;
    }

    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, clientW, clientH);

    // Map shared timestamps
    const spanBMap = new Map(spanBData.map(d => [d.time, d.value]));
    const points = [];

    for (let i = 0; i < spanAData.length; i++) {
        const a = spanAData[i];
        if (spanBMap.has(a.time)) {
            const bVal = spanBMap.get(a.time);
            const x = window.chart.timeScale().timeToCoordinate(a.time);
            const yA = window.spanASeries.priceToCoordinate(a.value);
            const yB = window.spanBSeries.priceToCoordinate(bVal);
            if (x !== null && yA !== null && yB !== null && !isNaN(x) && !isNaN(yA) && !isNaN(yB)) {
                points.push({ x, yA, yB, isBullish: a.value >= bVal });
            }
        }
    }

    if (points.length >= 2) {
        // Draw segment polygons between adjacent points
        for (let i = 0; i < points.length - 1; i++) {
            const p1 = points[i];
            const p2 = points[i + 1];

            ctx.beginPath();
            ctx.moveTo(p1.x, p1.yA);
            ctx.lineTo(p2.x, p2.yA);
            ctx.lineTo(p2.x, p2.yB);
            ctx.lineTo(p1.x, p1.yB);
            ctx.closePath();

            // TradingView standard cloud colors
            ctx.fillStyle = p1.isBullish 
                ? 'rgba(76, 175, 80, 0.18)'   // Translucent Green for Bullish Cloud
                : 'rgba(239, 83, 80, 0.18)';  // Translucent Red for Bearish Cloud
            ctx.fill();
        }
    }

    ctx.restore();
}
window.drawKumoCloud = drawKumoCloud;

function renderKumoCloud(spanAData, spanBData) {
    drawKumoCloud(spanAData, spanBData);
}
window.renderKumoCloud = renderKumoCloud;

// Animation Frame Throttling with flag to prevent redundant draw calls in same repaint cycle
let isRenderPending = false;

function requestKumoRedraw() {
    if (!isRenderPending) {
        isRenderPending = true;
        requestAnimationFrame(() => {
            drawKumoCloud();
            isRenderPending = false;
        });
    }
}
window.requestKumoRedraw = requestKumoRedraw;

function resetChartViewport() {
    const c = window.chart;
    if (!c) return;
    try {
        // 1. Force Y-axis price scale back to auto-scaling
        c.priceScale('right').applyOptions({
            autoScale: true,
        });
    } catch (e) {
        console.warn('[RESET VIEWPORT] Error resetting price scale autoScale:', e);
    }
    try {
        // 2. Auto-fit horizontal time scale
        c.timeScale().fitContent();
    } catch (e) {
        console.warn('[RESET VIEWPORT] Error fitting content:', e);
    }
    // 3. Immediately redraw Kumo cloud
    requestKumoRedraw();
}
window.resetChartViewport = resetChartViewport;

class BursaTradingChart {
    constructor(containerId) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.currentData = null;
        this.activeTimeframe = "1d";
        this.resizeObserver = null;

        this.init();
    }

    init() {
        if (!this.container) {
            console.error(`Chart container #${this.containerId} not found.`);
            return;
        }

        if (typeof LightweightCharts === 'undefined') {
            console.warn("LightweightCharts library not yet loaded. Retrying in 200ms...");
            setTimeout(() => this.init(), 200);
            return;
        }

        // Clear existing children and ensure relative positioning
        this.container.innerHTML = "";
        this.container.style.position = "relative";

        const parent = this.container.parentElement || this.container;
        const width = this.container.clientWidth || parent.clientWidth || 800;
        const height = this.container.clientHeight || parent.clientHeight || 500;

        // Initialize TradingView Lightweight Chart
        this.chart = LightweightCharts.createChart(this.container, {
            width: width,
            height: height,
            layout: {
                background: { type: 'solid', color: '#080c10' },
                textColor: '#8b9bb4',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                fontSize: 11
            },
            grid: {
                vertLines: { color: 'rgba(28, 39, 54, 0.4)' },
                horzLines: { color: 'rgba(28, 39, 54, 0.4)' }
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: '#2962FF',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#121922'
                },
                horzLine: {
                    color: '#2962FF',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#121922'
                }
            },
            rightPriceScale: {
                borderColor: '#1c2736',
                scaleMargins: {
                    top: 0.08,
                    bottom: 0.28
                }
            },
            timeScale: {
                borderColor: '#1c2736',
                timeVisible: true,
                secondsVisible: false
            }
        });
        window.chart = this.chart;

        // 1. Candlestick Series (Primary)
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#00ffaa',
            downColor: '#ff0055',
            borderUpColor: '#00ffaa',
            borderDownColor: '#ff0055',
            wickUpColor: '#00ffaa',
            wickDownColor: '#ff0055'
        });
        window.candlestickSeries = this.candleSeries;

        // 2. Volume Series (Sub-overlay with bottom margin)
        this.volumeSeries = this.chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume_scale',
            priceLineVisible: false
        });
        this.chart.priceScale('volume_scale').applyOptions({
            scaleMargins: {
                top: 0.75,
                bottom: 0.02
            }
        });
        window.volumeSeries = this.volumeSeries;

        // ====================================================================
        // Mandate 2: Exact TradingView Indicator Palette (Strict Purge of Old Hexes)
        // ====================================================================

        // Conversion Line (Tenkan-sen, 9) -> TradingView Royal Blue
        this.tenkanSeries = this.chart.addLineSeries({
            color: '#2962FF',
            lineWidth: 2,
            priceLineVisible: false,
            title: 'Tenkan (9)'
        });
        window.tenkanSeries = this.tenkanSeries;

        // Base Line (Kijun-sen, 26) -> TradingView Solid Red
        this.kijunSeries = this.chart.addLineSeries({
            color: '#D32F2F',
            lineWidth: 2,
            priceLineVisible: true,
            title: 'Kijun Trailing Stop'
        });
        window.kijunSeries = this.kijunSeries;

        // Lagging Span (Chikou Span) -> TradingView Forest Green
        this.chikouSeries = this.chart.addLineSeries({
            color: '#4CAF50',
            lineWidth: 1,
            priceLineVisible: false,
            title: 'Chikou'
        });
        window.chikouSeries = this.chikouSeries;

        // Leading Span A -> TradingView Light Green
        this.spanASeries = this.chart.addLineSeries({
            color: '#81C784',
            lineWidth: 1,
            priceLineVisible: false,
            title: 'Span A'
        });
        window.spanASeries = this.spanASeries;

        // Leading Span B -> TradingView Light Red / Salmon
        this.spanBSeries = this.chart.addLineSeries({
            color: '#E57373',
            lineWidth: 1,
            priceLineVisible: false,
            title: 'Span B'
        });
        window.spanBSeries = this.spanBSeries;

        // Anchored VWAP -> TradingView Yellow
        this.avwapSeries = this.chart.addLineSeries({
            color: '#FBC02D',
            lineWidth: 2,
            priceLineVisible: false,
            title: 'AVWAP'
        });
        window.avwapSeries = this.avwapSeries;

        // ====================================================================
        // Mandate 3: DOM Injection for Shaded Kumo Cloud Canvas Overlay
        // ====================================================================
        let kumoCanvas = document.getElementById('kumo-overlay-canvas');
        if (!kumoCanvas) {
            kumoCanvas = document.createElement('canvas');
            kumoCanvas.id = 'kumo-overlay-canvas';
            kumoCanvas.style.position = 'absolute';
            kumoCanvas.style.top = '0';
            kumoCanvas.style.left = '0';
            kumoCanvas.style.width = '100%';
            kumoCanvas.style.height = '100%';
            kumoCanvas.style.pointerEvents = 'none';
            kumoCanvas.style.zIndex = '1';
            this.container.style.position = 'relative';
            this.container.appendChild(kumoCanvas);
        }

        // Event Hooks for Kumo Cloud redraw
        this.chart.timeScale().subscribeVisibleLogicalRangeChange(requestKumoRedraw);
        if (typeof this.chart.timeScale().subscribeVisibleTimeRangeChange === 'function') {
            this.chart.timeScale().subscribeVisibleTimeRangeChange(requestKumoRedraw);
        }

        // 1. Redraw when dragging (catches both time scale and price scale drag)
        this.container.addEventListener('pointermove', (e) => {
            if (e.buttons > 0) { // Left-click or middle-click held down
                requestKumoRedraw();
            }
        });

        // 2. Redraw on mouse wheel (catches vertical and horizontal scroll zooming)
        this.container.addEventListener('wheel', () => {
            requestKumoRedraw();
        }, { passive: true });

        // 3. Redraw on crosshair movement over price scale boundaries
        this.chart.subscribeCrosshairMove(() => {
            requestKumoRedraw();
        });

        // 4. Double-click reset behavior on chart canvas / price scale
        this.container.addEventListener('dblclick', (e) => {
            e.preventDefault();
            resetChartViewport();
        });

        // Auto-resize listener
        const handleResize = () => {
            if (this.chart && this.container) {
                const parentEl = this.container.parentElement || this.container;
                const newWidth = this.container.clientWidth || parentEl.clientWidth;
                const newHeight = this.container.clientHeight || parentEl.clientHeight;
                if (newWidth > 0 && newHeight > 0) {
                    this.chart.applyOptions({
                        width: newWidth,
                        height: newHeight
                    });
                    requestKumoRedraw();
                }
            }
        };

        if (typeof ResizeObserver !== 'undefined') {
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }
            this.resizeObserver = new ResizeObserver(() => {
                handleResize();
            });
            const targetEl = this.container.parentElement || this.container;
            this.resizeObserver.observe(targetEl);
        }

        window.addEventListener('resize', () => {
            handleResize();
            requestKumoRedraw();
        });

        window.chartEngine = this;
    }

    async loadTickerData(symbol, timeframe = "1d") {
        const tf = (timeframe || "1d").toLowerCase();
        this.activeTimeframe = tf;
        window.activeTimeframe = tf;
        window.currentActiveTicker = symbol;

        try {
            const resp = await fetch(`/api/chart/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(tf)}`);
            if (!resp.ok) {
                console.error(`Failed to load chart data for ${symbol} (${tf}): ${resp.status}`);
                return;
            }
            const data = await resp.json();
            this.currentData = data;
            this.render(data);
            return data;
        } catch (e) {
            console.error(`Error fetching chart data for ${symbol} (${tf}):`, e);
        }
    }

    render(data) {
        if (!this.chart || !data) return;

        // Feed Candle bars
        if (data.candles && data.candles.length > 0) {
            this.candleSeries.setData(data.candles);
        } else {
            this.candleSeries.setData([]);
        }

        // Feed Volume bars
        if (data.volume && data.volume.length > 0) {
            this.volumeSeries.setData(data.volume);
        } else {
            this.volumeSeries.setData([]);
        }

        // Feed Indicators
        if (data.tenkan && data.tenkan.length > 0) {
            this.tenkanSeries.setData(data.tenkan);
        } else {
            this.tenkanSeries.setData([]);
        }

        if (data.kijun && data.kijun.length > 0) {
            this.kijunSeries.setData(data.kijun);
        } else {
            this.kijunSeries.setData([]);
        }

        if (data.chikou && data.chikou.length > 0) {
            this.chikouSeries.setData(data.chikou);
        } else {
            this.chikouSeries.setData([]);
        }

        if (data.span_a && data.span_a.length > 0) {
            this.spanASeries.setData(data.span_a);
        } else {
            this.spanASeries.setData([]);
        }

        if (data.span_b && data.span_b.length > 0) {
            this.spanBSeries.setData(data.span_b);
        } else {
            this.spanBSeries.setData([]);
        }

        if (data.avwap && data.avwap.length > 0) {
            this.avwapSeries.setData(data.avwap);
        } else {
            this.avwapSeries.setData([]);
        }

        // Cache span data globally for overlay Kumo renderer
        window.currentSpanAData = data.span_a || [];
        window.currentSpanBData = data.span_b || [];

        // Fit content into viewport & force Y-axis price scale auto-scaling
        resetChartViewport();

        // Render Shaded Kumo Cloud
        requestKumoRedraw();

        // Update header UI display elements
        this.updateHeaderUI(data);
    }

    updateTick(tick) {
        if (!this.chart || !this.candleSeries || !this.currentData) return;
        
        const tickSym = tick.ticker_symbol || tick.symbol || tick.ticker;
        if (tickSym && tickSym !== (this.currentData.ticker || this.currentData.symbol)) return;

        const price = typeof tick === 'number' ? tick : (tick.last_price || tick.price);
        if (!price || isNaN(price) || price <= 0) return;

        if (this.currentData.candles && this.currentData.candles.length > 0) {
            const lastCandle = this.currentData.candles[this.currentData.candles.length - 1];
            const updatedCandle = {
                time: lastCandle.time,
                open: lastCandle.open,
                high: Math.max(lastCandle.high, price),
                low: Math.min(lastCandle.low, price),
                close: price
            };

            lastCandle.high = updatedCandle.high;
            lastCandle.low = updatedCandle.low;
            lastCandle.close = updatedCandle.close;

            this.candleSeries.update(updatedCandle);
        }

        const vol = tick.volume;
        if (this.volumeSeries && vol !== undefined && this.currentData.volume && this.currentData.volume.length > 0) {
            const lastVol = this.currentData.volume[this.currentData.volume.length - 1];
            const lastCandle = this.currentData.candles[this.currentData.candles.length - 1];
            const isUp = price >= (lastCandle ? lastCandle.open : price);

            lastVol.value = vol;
            this.volumeSeries.update({
                time: lastVol.time,
                value: vol,
                color: isUp ? 'rgba(0, 255, 170, 0.4)' : 'rgba(255, 0, 85, 0.4)'
            });
        }

        const priceEl = document.getElementById("active-ticker-price");
        if (priceEl) {
            priceEl.textContent = `RM ${price.toFixed(3)}`;
        }

        requestKumoRedraw();
    }

    updateHeaderUI(data) {
        const symEl = document.getElementById("active-ticker-symbol");
        const nameEl = document.getElementById("active-ticker-name");
        const priceEl = document.getElementById("active-ticker-price");
        const watermarkEl = document.getElementById("chart-watermark");

        const sym = data.ticker || data.symbol;
        if (symEl) symEl.textContent = sym;
        if (nameEl) nameEl.textContent = data.name;
        if (priceEl && data.current_metrics) {
            priceEl.textContent = `RM ${data.current_metrics.last_price.toFixed(3)}`;
        }

        if (watermarkEl && data.current_metrics) {
            const m = data.current_metrics;
            const tfLabel = (this.activeTimeframe || "1D").toUpperCase();
            watermarkEl.innerHTML = `
                <div><strong>${data.full_name}</strong> (${sym}) [${tfLabel}]</div>
                <div>Tenkan (9): <span style="color:#2962FF">RM ${m.tenkan.toFixed(3)}</span> | Kijun (26): <span style="color:#D32F2F">RM ${m.kijun.toFixed(3)}</span></div>
                <div>AVWAP: <span style="color:#FBC02D">RM ${m.avwap.toFixed(3)}</span> | CMF-21: <span style="color:${m.cmf_21 > 0.1 ? '#00ffcc':'#8b9bb4'}">${m.cmf_21.toFixed(3)}</span></div>
                <div>Cloud: <span style="color:#f0f6fc">${m.cloud_state}</span> | Score: <strong>${data.current_score.toFixed(1)}/5.0</strong></div>
            `;
        }
    }
}
