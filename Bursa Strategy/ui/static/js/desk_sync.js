/**
 * Bursa Strategy - Display 2 (Desk) Client Synchronization
 * Coordinates TradingView Chart, 0.01 Fractional Unit Sizer, Rubric Badges, and Vim CLI.
 * Fully compatible with Microsoft Edge and Brave Browser (Shields safe).
 */

let activeTimeframe = '1d';
window.activeTimeframe = activeTimeframe;
window.currentActiveTicker = window.currentActiveTicker || "5211.KL";

async function reloadChartWithTimeframe(ticker, tf) {
    try {
        const selectedTf = (tf || activeTimeframe || '1d').toLowerCase();
        const selectedTicker = ticker || window.currentActiveTicker || '5211.KL';
        activeTimeframe = selectedTf;
        window.activeTimeframe = activeTimeframe;
        window.currentActiveTicker = selectedTicker;

        const res = await fetch(`/api/chart/${encodeURIComponent(selectedTicker)}?timeframe=${encodeURIComponent(selectedTf)}`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();

        // Series references from Lightweight Charts
        const candlestickSeries = window.candlestickSeries;
        const volumeSeries = window.volumeSeries;
        const tenkanSeries = window.tenkanSeries;
        const kijunSeries = window.kijunSeries;
        const chikouSeries = window.chikouSeries;
        const spanASeries = window.spanASeries;
        const spanBSeries = window.spanBSeries;
        const avwapSeries = window.avwapSeries;
        const chart = window.chart;

        // Load new series data into Lightweight Charts
        if (candlestickSeries && data.candles) candlestickSeries.setData(data.candles);
        if (volumeSeries && data.volume) volumeSeries.setData(data.volume);
        if (tenkanSeries && data.tenkan) tenkanSeries.setData(data.tenkan);
        if (kijunSeries && data.kijun) kijunSeries.setData(data.kijun);
        if (chikouSeries && data.chikou) chikouSeries.setData(data.chikou);
        if (spanASeries && data.span_a) spanASeries.setData(data.span_a);
        if (spanBSeries && data.span_b) spanBSeries.setData(data.span_b);
        if (avwapSeries && data.avwap) avwapSeries.setData(data.avwap);

        // Cache current span arrays for Kumo redraw
        window.currentSpanAData = data.span_a || [];
        window.currentSpanBData = data.span_b || [];
        if (typeof requestKumoRedraw === 'function') {
            requestKumoRedraw();
        } else if (typeof window.requestKumoRedraw === 'function') {
            window.requestKumoRedraw();
        } else if (typeof drawKumoCloud === 'function') {
            drawKumoCloud();
        } else if (typeof window.drawKumoCloud === 'function') {
            window.drawKumoCloud();
        }

        // Auto-fit contents and force Y-axis price scale auto-scaling
        if (typeof resetChartViewport === 'function') {
            resetChartViewport();
        } else if (typeof window.resetChartViewport === 'function') {
            window.resetChartViewport();
        } else if (chart) {
            try {
                chart.priceScale('right').applyOptions({ autoScale: true });
            } catch (e) {}
            chart.timeScale().fitContent();
        }

        // Sync button classes
        document.querySelectorAll('.btn-tf').forEach(b => {
            const bTf = b.getAttribute('data-tf') || b.innerText.toLowerCase().trim();
            if (bTf === activeTimeframe) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        // Update header UI & Watermark
        if (window.chartEngine) {
            window.chartEngine.currentData = data;
            window.chartEngine.activeTimeframe = activeTimeframe;
            window.chartEngine.updateHeaderUI(data);
        }

        // Keep Desk Client state and cost preview updated
        if (window.deskClient) {
            window.deskClient.activeTicker = selectedTicker;
            window.deskClient.activeTimeframe = activeTimeframe;
            if (data.current_metrics) {
                window.deskClient.activePrice = data.current_metrics.last_price;
                window.deskClient.updatePriceReference();
            }
            const amountInput = document.getElementById("sizer-amount-input");
            const currentRm = amountInput ? (parseFloat(amountInput.value) || 5.00) : 5.00;
            window.deskClient.applyPresetAllocation(currentRm);
        }

        return data;
    } catch (err) {
        console.error('[CHART TF ERROR]', err);
    }
}
window.reloadChartWithTimeframe = reloadChartWithTimeframe;

function bindTimeframeButtons() {
    document.querySelectorAll('.btn-tf').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const selectedTf = btn.getAttribute('data-tf') || btn.innerText.toLowerCase().trim();
            if (selectedTf === activeTimeframe) return;

            // Update active button state
            document.querySelectorAll('.btn-tf').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTimeframe = selectedTf;
            window.activeTimeframe = activeTimeframe;
            if (window.deskClient) window.deskClient.activeTimeframe = activeTimeframe;

            // Fetch and reload chart data for current ticker
            const targetTicker = window.currentActiveTicker || (window.deskClient ? window.deskClient.activeTicker : "5211.KL");
            if (targetTicker) {
                await reloadChartWithTimeframe(targetTicker, activeTimeframe);
            }
        });
    });
}

class DeskSyncClient {
    constructor() {
        this.ws = null;
        this.chartEngine = null;
        this.vimCli = null;
        this.activeTicker = "5211.KL";
        this.activeTimeframe = "1d";
        this.activePrice = 4.65;
        this.availableCash = 50.00;
        this.totalEquity = 50.00;
        this.rubricData = null;

        this.init();
    }

    async init() {
        // 1. Initialize Chart
        this.chartEngine = new BursaTradingChart("tradingview-main-canvas");
        
        // 2. Initialize Vim CLI
        this.vimCli = new VimCLI("vim-input-field", "vim-output-log", this);

        // 3. Initialize WebSocket
        this.initWebSocket();

        // 4. Bind Sizer controls and quick buttons
        this.bindSizerEvents();

        // 5. Bind Timeframe selector buttons (1H, 4H, 1D)
        this.bindTimeframeEvents();

        // 6. Load rubric metrics
        await this.loadRubricHUD();

        // 7. Load initial ticker with default timeframe
        await this.selectTicker(this.activeTicker, false);
    }

    initWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/channel`;

        console.log(`[DeskSync] Connecting WebSocket to ${wsUrl}...`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log("[DeskSync] WebSocket connected.");
            this.setConnectionStatus(true);
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.warn("[DeskSync] WS JSON error:", e);
            }
        };

        this.ws.onclose = () => {
            this.setConnectionStatus(false);
            console.log("[DeskSync] WebSocket disconnected. Reconnecting in 2s...");
            setTimeout(() => this.initWebSocket(), 2000);
        };

        this.ws.onerror = (err) => {
            console.warn("[DeskSync] WS error:", err);
        };
    }

    setConnectionStatus(connected) {
        const beacon = document.getElementById("desk-sync-beacon");
        const text = document.getElementById("desk-sync-text");
        if (beacon) {
            beacon.style.background = connected ? "var(--neon-teal)" : "var(--neon-pink)";
            beacon.style.boxShadow = connected ? "0 0 8px var(--neon-teal)" : "0 0 8px var(--neon-pink)";
        }
        if (text) {
            text.textContent = connected ? "DESK SYNC OK" : "RECONNECTING...";
            text.style.color = connected ? "var(--neon-teal)" : "var(--neon-pink)";
        }
    }

    async handleMessage(msg) {
        const ev = msg.event;

        if (ev === "TICKER_SELECT") {
            const sym = msg.ticker_symbol || msg.ticker;
            if (sym) {
                this.activeTicker = sym;
                window.currentActiveTicker = sym;
                await reloadChartWithTimeframe(sym, activeTimeframe);
                if (typeof window.resetChartViewport === 'function') {
                    window.resetChartViewport();
                }
            }
        } else if (ev === "STATE_SNAPSHOT") {
            if (msg.state) {
                const sym = msg.state.selected_ticker;
                if (sym && sym !== this.activeTicker) {
                    this.activeTicker = sym;
                    window.currentActiveTicker = sym;
                    await reloadChartWithTimeframe(sym, activeTimeframe);
                    if (typeof window.resetChartViewport === 'function') {
                        window.resetChartViewport();
                    }
                }
                if (msg.state.rubric) {
                    this.updateRubricHUD(msg.state.rubric);
                }
            }
        } else if (ev === "TICK_STREAM") {
            // Real-time tick stream from background polling loop
            if (msg.ticks && Array.isArray(msg.ticks)) {
                for (const t of msg.ticks) {
                    const sym = t.ticker_symbol || t.symbol || t.ticker;
                    if (sym === this.activeTicker) {
                        this.activePrice = t.price !== undefined ? t.price : t.last_price;
                        if (this.chartEngine) {
                            this.chartEngine.updateTick(t);
                        }
                        this.updatePriceReference();
                        this.syncCostPreview();
                        break;
                    }
                }
            }
        } else if (ev === "ORDER_EXECUTE" || ev === "PORTFOLIO_UPDATE") {
            if (msg.rubric) {
                this.updateRubricHUD(msg.rubric);
            }
        } else if (ev === "STOP_AUDIT") {
            if (msg.alerts && msg.alerts.length > 0 && this.vimCli) {
                this.vimCli.printLine(`⚠️ STOP AUDIT ALERT: ${msg.alerts.length} open positions breached Kijun-sen trailing stop!`, "err");
            }
        }
    }

    async selectTicker(symbol, broadcast = true) {
        this.activeTicker = symbol;
        window.currentActiveTicker = symbol;
        const data = await reloadChartWithTimeframe(symbol, activeTimeframe);
        if (typeof window.resetChartViewport === 'function') {
            window.resetChartViewport();
        }
        if (data && data.current_metrics) {
            this.activePrice = data.current_metrics.last_price;
        }

        this.updatePriceReference();
        this.syncTimeframeUI();
        
        // Active Ticker Switch Recalibration: Maintain current RM allocation and instantly recalculate fractional units
        const amountInput = document.getElementById("sizer-amount-input");
        const currentRm = amountInput ? (parseFloat(amountInput.value) || 5.00) : 5.00;
        this.applyPresetAllocation(currentRm);

        // Broadcast ticker selection to Tower screen if initiated from Desk
        if (broadcast && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                event: "TICKER_SELECT",
                ticker: symbol,
                ticker_symbol: symbol,
                name: data ? data.name : symbol
            }));
        }
    }

    bindTimeframeEvents() {
        bindTimeframeButtons();
    }

    syncTimeframeUI() {
        const tfButtons = document.querySelectorAll(".btn-tf");
        tfButtons.forEach(btn => {
            const bTf = btn.getAttribute("data-tf") || btn.innerText.toLowerCase().trim();
            if (bTf === activeTimeframe) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

    updatePriceReference() {
        const refEl = document.getElementById("sizer-price-ref");
        if (refEl) {
            refEl.textContent = `Ref Price: RM ${this.activePrice.toFixed(3)}`;
        }
        const activePriceEl = document.getElementById("active-ticker-price");
        if (activePriceEl) {
            activePriceEl.textContent = `RM ${this.activePrice.toFixed(3)}`;
        }
    }

    applyPresetAllocation(targetRm) {
        if (!this.activePrice || this.activePrice <= 0) return;
        const MAX_CAPITAL = 50.00;
        const allocation = Math.min(targetRm, MAX_CAPITAL);
        const calculatedUnits = allocation / this.activePrice;

        const amountInput = document.getElementById("sizer-amount-input");
        const unitsInput = document.getElementById("sizer-units-input");

        if (amountInput) amountInput.value = allocation.toFixed(2);
        if (unitsInput) unitsInput.value = calculatedUnits.toFixed(4);

        this.syncCostPreview();
    }

    applyPresetUnits(targetUnits) {
        if (!this.activePrice || this.activePrice <= 0) return;
        const MAX_CAPITAL = 50.00;
        const maxUnits = MAX_CAPITAL / this.activePrice;
        const units = Math.min(targetUnits, maxUnits);
        const allocation = units * this.activePrice;

        const amountInput = document.getElementById("sizer-amount-input");
        const unitsInput = document.getElementById("sizer-units-input");

        if (amountInput) amountInput.value = allocation.toFixed(2);
        if (unitsInput) unitsInput.value = units.toFixed(4);

        this.syncCostPreview();
    }

    bindSizerEvents() {
        const unitsInput = document.getElementById("sizer-units-input");
        const amountInput = document.getElementById("sizer-amount-input");

        // Bi-Directional Reactivity 1: Fractional Units input -> Recalculates Allocation RM
        if (unitsInput) {
            unitsInput.addEventListener("input", () => {
                let units = parseFloat(unitsInput.value);
                if (isNaN(units) || units < 0) units = 0.01;

                const price = this.activePrice > 0 ? this.activePrice : 1.0;
                
                // Dynamically cap so Units * Current Price <= RM 50.00
                const maxUnits = 50.00 / price;
                if (units > maxUnits) {
                    units = Math.floor(maxUnits * 10000) / 10000;
                    unitsInput.value = units.toFixed(4);
                }

                const allocation = units * price;
                if (amountInput) {
                    amountInput.value = allocation.toFixed(2);
                }

                this.syncCostPreview();
            });
        }

        // Bi-Directional Reactivity 2: Allocation RM input -> Recalculates Fractional Units
        if (amountInput) {
            amountInput.addEventListener("input", () => {
                let amt = parseFloat(amountInput.value);
                if (isNaN(amt) || amt < 0) amt = 0.05;

                // Max allocation capped at RM 50.00
                if (amt > 50.00) {
                    amt = 50.00;
                    amountInput.value = "50.00";
                }

                const price = this.activePrice > 0 ? this.activePrice : 1.0;
                const units = amt / price;

                if (unitsInput) {
                    unitsInput.value = units.toFixed(4);
                }

                this.syncCostPreview();
            });
        }

        // Calibrated Tournament Quick-Buttons (Unified Reactive Sizer Controller)
        // 0.01 Unit, 1.00 Unit, RM 5.00, RM 25.00, RM 50.00
        document.querySelectorAll(".btn-quick").forEach(btn => {
            btn.addEventListener("click", () => {
                const type = btn.dataset.type;
                const val = parseFloat(btn.dataset.val);

                if (type === "unit") {
                    this.applyPresetUnits(val);
                } else if (type === "rm") {
                    this.applyPresetAllocation(val);
                }
            });
        });

        // Quick Execution Buttons (Buy / Sell)
        const buyBtn = document.getElementById("btn-quick-buy");
        const sellBtn = document.getElementById("btn-quick-sell");

        if (buyBtn) {
            buyBtn.addEventListener("click", () => this.executeQuickOrder("BUY"));
        }

        if (sellBtn) {
            sellBtn.addEventListener("click", () => this.executeQuickOrder("SELL"));
        }

        // Initial preview sync
        this.syncCostPreview();
    }

    syncCostPreview() {
        const unitsInput = document.getElementById("sizer-units-input");
        const costPreview = document.getElementById("sizer-cost-preview");
        const cashPreview = document.getElementById("sizer-cash-preview");

        const units = unitsInput ? (parseFloat(unitsInput.value) || 0.0) : 1.0;
        const price = this.activePrice > 0 ? this.activePrice : 1.0;
        const totalCost = units * price;

        if (costPreview) {
            costPreview.textContent = `RM ${totalCost.toFixed(4)}`;
        }

        if (cashPreview) {
            const remaining = Math.max(0, this.availableCash - totalCost);
            cashPreview.textContent = `RM ${remaining.toFixed(2)}`;
            cashPreview.className = remaining >= 0 ? "val-up" : "val-down";
        }
    }

    async executeQuickOrder(action) {
        const unitsInput = document.getElementById("sizer-units-input");
        const amountInput = document.getElementById("sizer-amount-input");

        const units = unitsInput ? parseFloat(unitsInput.value) : 1.0;
        const amt = amountInput ? parseFloat(amountInput.value) : 5.0;

        if (isNaN(units) || units < 0.01) {
            if (this.vimCli) this.vimCli.printLine("Minimum order size is 0.01 fractional units.", "err");
            return;
        }

        if (this.vimCli) {
            this.vimCli.printLine(`Submitting ${action} order: ${units.toFixed(4)} units of ${this.activeTicker} (RM ${amt.toFixed(2)})...`, "normal");
        }

        try {
            const resp = await fetch("/api/order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: action.toUpperCase(),
                    ticker: this.activeTicker,
                    units: units,
                    amount_myr: amt,
                    notes: "Desk Quick Sizer"
                })
            });

            const res = await resp.json();
            if (res.success) {
                const t = res.trade;
                if (this.vimCli) {
                    this.vimCli.printLine(`✓ Executed: ${t.action} ${t.units} units of ${t.symbol} @ RM ${t.price.toFixed(3)} (RM ${t.total_myr.toFixed(2)})`, "ok");
                    this.vimCli.printLine(`  Compliance: i-ETF ${res.rubric.etf_badge} | Fractional ${res.rubric.fractional_badge} | Total ${res.rubric.total_badge}`, "gold");
                }
                this.updateRubricHUD(res.rubric);
            } else {
                if (this.vimCli) {
                    this.vimCli.printLine(`Order Rejected: ${res.error}`, "err");
                }
            }
        } catch (e) {
            if (this.vimCli) {
                this.vimCli.printLine(`Order failed: ${e.message}`, "err");
            }
        }
    }

    notifyScanComplete() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ event: "RUN_SCAN" }));
        }
    }

    async loadRubricHUD() {
        try {
            const resp = await fetch("/api/rubric");
            const data = await resp.json();
            this.updateRubricHUD(data);
        } catch (e) {
            console.error("Error loading rubric HUD:", e);
        }
    }

    updateRubricHUD(rubric) {
        if (!rubric) return;
        this.rubricData = rubric;
        this.availableCash = rubric.cash_balance !== undefined ? rubric.cash_balance : 50.00;
        this.totalEquity = rubric.total_equity !== undefined ? rubric.total_equity : 50.00;

        const etfBadge = document.getElementById("rubric-etf-badge");
        const fracBadge = document.getElementById("rubric-fractional-badge");
        const totalBadge = document.getElementById("rubric-total-badge");
        const cashDisplay = document.getElementById("rubric-cash-val");
        const equityDisplay = document.getElementById("rubric-equity-val");
        const pnlDisplay = document.getElementById("rubric-pnl-val");

        if (etfBadge) {
            etfBadge.textContent = `i-ETF Trades ${rubric.etf_badge}`;
            etfBadge.className = `badge ${rubric.etf_compliant ? 'badge-teal' : 'badge-gold'}`;
        }

        if (fracBadge) {
            fracBadge.textContent = `Fractional Trades ${rubric.fractional_badge}`;
            fracBadge.className = `badge ${rubric.fractional_compliant ? 'badge-teal' : 'badge-gold'}`;
        }

        if (totalBadge) {
            totalBadge.textContent = `Total Trades ${rubric.total_badge}`;
            totalBadge.className = `badge ${rubric.total_compliant ? 'badge-teal' : 'badge-blue'}`;
        }

        if (cashDisplay) cashDisplay.textContent = `RM ${this.availableCash.toFixed(2)}`;
        if (equityDisplay) equityDisplay.textContent = `RM ${this.totalEquity.toFixed(2)}`;
        if (pnlDisplay) {
            const pnl = rubric.total_pnl || 0.0;
            const pnlPct = rubric.total_pnl_pct || 0.0;
            const pnlSign = pnl >= 0 ? '+' : '';
            pnlDisplay.textContent = `${pnlSign}RM ${pnl.toFixed(2)} (${pnlSign}${pnlPct.toFixed(2)}%)`;
            pnlDisplay.className = pnl >= 0 ? 'val-up' : 'val-down';
        }

        this.syncCostPreview();
    }
}

// Instantiate Desk sync on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    window.deskClient = new DeskSyncClient();

    // Standard double-click reset behavior on chart canvas or price scale
    const chartWrapperEl = document.getElementById("tradingview-main-canvas");
    if (chartWrapperEl) {
        chartWrapperEl.addEventListener("dblclick", (e) => {
            e.preventDefault();
            if (typeof window.resetChartViewport === "function") {
                window.resetChartViewport();
            }
        });
    }
});
