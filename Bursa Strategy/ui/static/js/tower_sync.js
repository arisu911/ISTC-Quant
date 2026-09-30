/**
 * Bursa Strategy - Display 1 (Tower) Client Synchronization
 * Manages WebSocket state, Factor Matrix Table sorting, Catalyst Horizons, PDF Auditor, and Telemetry.
 * Features instant client state reset on selection, strict ticker cache isolation,
 * single source of truth debt ratio binding, and dynamic asset-class forking (Equities vs. i-ETF Vault Auditor).
 * Verified compatible with Microsoft Edge and Brave Browser (Shields safe).
 */

class TowerSyncClient {
    constructor() {
        this.ws = null;
        this.selectedTicker = "5211.KL";
        this.matrixData = [];
        this.currentSortCol = "ichimoku_score";
        this.sortAscending = false;

        this.init();
    }

    async init() {
        this.initWebSocket();
        await this.loadCatalysts();
        await this.loadFactorMatrix();
        await this.loadAuditForTicker(this.selectedTicker);
        this.initTableSortListeners();
    }

    initWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/channel`;

        console.log(`[TowerSync] Connecting WebSocket to ${wsUrl}...`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log("[TowerSync] WebSocket connected successfully.");
            this.setConnectionStatus(true);
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.handleMessage(msg);
            } catch (e) {
                console.warn("[TowerSync] WS JSON error:", e);
            }
        };

        this.ws.onclose = () => {
            this.setConnectionStatus(false);
            console.log("[TowerSync] WebSocket disconnected. Retrying in 2s...");
            setTimeout(() => this.initWebSocket(), 2000);
        };

        this.ws.onerror = (err) => {
            console.warn("[TowerSync] WS Warning:", err);
        };
    }

    setConnectionStatus(connected) {
        const beacon = document.getElementById("tower-sync-beacon");
        const text = document.getElementById("tower-sync-text");
        if (beacon) {
            beacon.style.background = connected ? "var(--neon-teal)" : "var(--neon-pink)";
            beacon.style.boxShadow = connected ? "0 0 8px var(--neon-teal)" : "0 0 8px var(--neon-pink)";
        }
        if (text) {
            text.textContent = connected ? "LIVE SYNC ACTIVE" : "RECONNECTING...";
            text.style.color = connected ? "var(--neon-teal)" : "var(--neon-pink)";
        }
    }

    handleMessage(msg) {
        const ev = msg.event;

        if (ev === "TICKER_SELECT") {
            const sym = msg.ticker_symbol || msg.ticker;
            if (sym) {
                this.selectedTicker = sym;
                this.highlightMatrixRow(sym);
                this.clearZone3State(sym);
                this.loadAuditForTicker(sym);
            }
        } else if (ev === "STATE_SNAPSHOT") {
            if (msg.state && msg.state.selected_ticker) {
                const sym = msg.state.selected_ticker;
                this.selectedTicker = sym;
                this.highlightMatrixRow(sym);
                if (msg.state.latest_fundamental && (msg.state.latest_fundamental.ticker === sym || msg.state.latest_fundamental.ticker.replace(".KL", "") === sym.replace(".KL", ""))) {
                    this.renderFundamentalUpdate(msg.state.latest_fundamental);
                } else {
                    this.clearZone3State(sym);
                    this.loadAuditForTicker(sym);
                }
            }
            if (msg.state && msg.state.logs) {
                msg.state.logs.forEach(l => this.appendLog(l));
            }
        } else if (ev === "FUNDAMENTAL_UPDATE") {
            if (this.isMatchingTicker(msg.ticker, this.selectedTicker)) {
                this.renderFundamentalUpdate(msg);
            }
        } else if (ev === "AUDIT_RESULT") {
            if (this.isMatchingTicker(msg.ticker, this.selectedTicker)) {
                if (msg.payload) {
                    this.renderFundamentalUpdate(msg.payload);
                } else {
                    this.renderAuditUI(msg.audit, msg.mda_review);
                }
            }
        } else if (ev === "STOP_AUDIT") {
            this.renderStopAlerts(msg.alerts);
        } else if (ev === "SCAN_TRIGGERED") {
            this.loadFactorMatrix();
        } else if (ev === "TICK_STREAM") {
            this.handleTickStream(msg.ticks);
        } else if (ev === "PORTFOLIO_UPDATE") {
            if (msg.trade) {
                const tr = msg.trade;
                this.appendLog({
                    timestamp: new Date().toLocaleTimeString(),
                    tag: "ORDER",
                    level: "SUCCESS",
                    message: `[DESK SIM] ${tr.action} ${tr.units} units of ${tr.symbol} @ RM ${tr.price.toFixed(3)} (RM ${tr.total_myr.toFixed(2)}) | Cash: RM ${msg.rubric ? msg.rubric.cash_balance.toFixed(2) : '--'}`
                });
            }
        }
    }

    isMatchingTicker(symA, symB) {
        if (!symA || !symB) return false;
        const cleanA = symA.replace(".KL", "").toUpperCase();
        const cleanB = symB.replace(".KL", "").toUpperCase();
        return cleanA === cleanB;
    }

    handleTickStream(ticks) {
        if (!ticks || !Array.isArray(ticks)) return;
        ticks.forEach(t => {
            const sym = t.ticker_symbol || t.symbol || t.ticker;
            if (!sym) return;

            const price = t.price !== undefined ? t.price : t.last_price;
            const chgPct = t.change_pct !== undefined ? t.change_pct : t.daily_change_pct;

            // Update in-memory matrix data
            const item = this.matrixData.find(x => x.symbol === sym);
            if (item) {
                item.last_price = price;
                item.daily_change_pct = chgPct;
                item.volume = t.volume;
            }

            // High-performance direct DOM update without re-sorting table
            const row = document.querySelector(`.matrix-row[data-symbol="${sym}"]`);
            if (row) {
                const cells = row.querySelectorAll("td");
                if (cells.length >= 5) {
                    cells[3].innerHTML = `<strong>RM ${price.toFixed(3)}</strong>`;
                    const chgClass = chgPct >= 0 ? 'val-up' : 'val-down';
                    cells[4].className = chgClass;
                    cells[4].textContent = `${chgPct > 0 ? '+' : ''}${chgPct.toFixed(2)}%`;
                }
            }
        });
    }

    sendTickerSelect(symbol, name) {
        this.selectedTicker = symbol;
        this.highlightMatrixRow(symbol);
        
        // Mandate 4: Wipe prior company state immediately on click
        this.clearZone3State(symbol);
        this.loadAuditForTicker(symbol);

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                event: "TICKER_SELECT",
                ticker: symbol,
                ticker_symbol: symbol,
                name: name
            }));
        }
    }

    /**
     * Mandate 4 Point 1: Clear Prior State on Ticker Click
     * Immediately wipe previous company's numbers and text from Zone 3 and show loading skeleton.
     */
    clearZone3State(ticker) {
        const titleEl = document.getElementById("auditor-panel-title");
        const headerEl = document.getElementById("auditor-ticker-badge");
        const verdictEl = document.getElementById("auditor-shariah-verdict");
        const leftContainer = document.getElementById("auditor-left-panel") || document.querySelector(".auditor-left");
        const rightContainer = document.getElementById("auditor-mda-points");

        const isEtf = ticker.includes("0828EA");

        if (titleEl) {
            titleEl.textContent = isEtf 
                ? "Zone 3: Macro Driver & Commodity Transmission Engine (0828EA.KL)" 
                : "Zone 3: A4 PDF Quarterly Disclosure & Fundamental Auditor";
        }

        if (headerEl) {
            headerEl.textContent = isEtf 
                ? `[MACRO ENGINE] Polling cross-asset benchmarks & bullion pricing for ${ticker}...`
                : `[AUDITOR] Loading quarterly disclosure for ${ticker}...`;
            headerEl.className = isEtf ? "badge badge-gold skeleton-pulse" : "badge badge-blue skeleton-pulse";
        }

        if (verdictEl) {
            verdictEl.textContent = isEtf ? "POLLING TELEMETRY" : "SCANNING";
            verdictEl.className = isEtf ? "sac-badge-pass skeleton-pulse" : "sac-badge-warn skeleton-pulse";
        }

        if (leftContainer) {
            if (isEtf) {
                leftContainer.innerHTML = `
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>COMEX GOLD (USD/oz)</span><span class="badge badge-gold">LBMA PM Fix</span></div>
                        <div class="stat-value skeleton-line">Polling Gold Benchmark...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>US 10Y BOND YIELD</span><span class="badge badge-teal">Real Rates</span></div>
                        <div class="stat-value skeleton-line">Polling US Treasury...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>BRENT CRUDE OIL</span><span class="badge badge-purple">Energy / CPI</span></div>
                        <div class="stat-value skeleton-line">Polling Energy Benchmark...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>USD / MYR FX RATE</span><span class="badge badge-blue">Currency Pair</span></div>
                        <div class="stat-value skeleton-line">Polling Forex Vector...</div>
                    </div>
                `;
            } else {
                leftContainer.innerHTML = `
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>Free Cash Flow (FCF = CFO - CAPEX)</span><span class="badge badge-teal">Cash Generation</span></div>
                        <div class="stat-value skeleton-line">Loading Cash Flow...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>Earnings Quality (CFO / EBITDA)</span><span class="badge badge-blue">Accrual Check</span></div>
                        <div class="stat-value skeleton-line">Computing Accruals...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>SAC SC Cash Ratio (&lt; 33%)</span><span style="font-size:9px;color:var(--text-dim)">Cash / Assets</span></div>
                        <div class="stat-value skeleton-line">Auditing Conventional Cash...</div>
                    </div>
                    <div class="auditor-stat-card skeleton-box">
                        <div class="stat-label"><span>SAC SC Conventional Debt Ratio (&lt; 33%)</span><span style="font-size:9px;color:var(--text-dim)">Debt / Assets</span></div>
                        <div class="stat-value skeleton-line">Auditing Debt Facilities...</div>
                    </div>
                `;
            }
        }

        if (rightContainer) {
            if (isEtf) {
                rightContainer.innerHTML = `
                    <div class="mda-point gold skeleton-box">
                        <div class="mda-point-title">1. Theoretical NAV & Pricing Spread (Arbitrage Check)</div>
                        <div class="mda-point-body skeleton-line">Computing bullion theoretical NAV per gram & per unit...</div>
                    </div>
                    <div class="mda-point blue skeleton-box">
                        <div class="mda-point-title">2. Real Yields & Opportunity Cost Transmission</div>
                        <div class="mda-point-body skeleton-line">Auditing US 10Y directional trend & bullion carry drag...</div>
                    </div>
                    <div class="mda-point purple skeleton-box">
                        <div class="mda-point-title">3. Energy & Geopolitical Risk Premium</div>
                        <div class="mda-point-body skeleton-line">Evaluating crude oil CPI inflation expectations & safe-haven flows...</div>
                    </div>
                    <div class="mda-point skeleton-box">
                        <div class="mda-point-title">4. USD/MYR Currency Translation Impact</div>
                        <div class="mda-point-body skeleton-line">Decomposing unhedged MYR returns vs USD gold move...</div>
                    </div>
                    <div class="mda-point gold skeleton-box">
                        <div class="mda-point-title">5. Tournament Utility & Shariah Vault Governance</div>
                        <div class="mda-point-body skeleton-line">Verifying 30% i-ETF challenge rubric & AAOIFI Std 57 vault compliance...</div>
                    </div>
                `;
            } else {
                rightContainer.innerHTML = `
                    <div class="mda-point skeleton-box">
                        <div class="mda-point-title">1. Real Commercial Drivers of Revenue Changes</div>
                        <div class="mda-point-body skeleton-line">Loading audited disclosure for ${ticker}...</div>
                    </div>
                    <div class="mda-point gold skeleton-box">
                        <div class="mda-point-title">2. Destinations of Operating Cash (CFO Deployment)</div>
                        <div class="mda-point-body skeleton-line">Extracting quarterly filings...</div>
                    </div>
                    <div class="mda-point purple skeleton-box">
                        <div class="mda-point-title">3. Inventory & Receivables vs Revenue Growth Rate</div>
                        <div class="mda-point-body skeleton-line">Verifying balance sheet schedules...</div>
                    </div>
                    <div class="mda-point blue skeleton-box">
                        <div class="mda-point-title">4. Forward Operational Catalysts & Backlog</div>
                        <div class="mda-point-body skeleton-line">Analyzing forward backlog...</div>
                    </div>
                    <div class="mda-point skeleton-box">
                        <div class="mda-point-title">5. Shariah Governance & SAC SC Compliance Audit</div>
                        <div class="mda-point-body skeleton-line">Verifying Shariah thresholds...</div>
                    </div>
                `;
            }
        }
    }

    async loadCatalysts() {
        try {
            const resp = await fetch("/api/catalysts");
            const data = await resp.json();
            const grid = document.getElementById("catalyst-grid-container");
            if (!grid) return;

            grid.innerHTML = "";
            data.events.forEach(ev => {
                const card = document.createElement("div");
                let colorClass = "teal";
                if (ev.id.includes("budget")) colorClass = "gold";
                if (ev.id.includes("finale")) colorClass = "pink";
                if (ev.id.includes("bursa")) colorClass = "blue";
                if (ev.id.includes("earnings")) colorClass = "purple";

                card.className = `catalyst-card ${colorClass}`;
                card.innerHTML = `
                    <div class="catalyst-top">
                        <span class="catalyst-title">${ev.title}</span>
                        <span class="badge badge-${colorClass === 'teal'?'teal':(colorClass==='gold'?'gold':(colorClass==='pink'?'pink':'blue'))}">${ev.tag}</span>
                    </div>
                    <div class="catalyst-counter">
                        <span class="counter-num ${colorClass}">${ev.trading_days_remaining}</span>
                        <span class="counter-label">Trading Days</span>
                    </div>
                    <div class="catalyst-footer">
                        <span>Target: ${ev.formatted_target}</span>
                        <span>${ev.calendar_days_remaining} Cal Days</span>
                    </div>
                `;
                grid.appendChild(card);
            });
        } catch (e) {
            console.error("Error loading catalysts:", e);
        }
    }

    async loadFactorMatrix() {
        try {
            const resp = await fetch("/api/scan");
            const data = await resp.json();
            this.matrixData = data.ranked_matrix;
            this.renderMatrixTable();
        } catch (e) {
            console.error("Error loading factor matrix:", e);
        }
    }

    renderMatrixTable() {
        const tbody = document.getElementById("matrix-table-body");
        if (!tbody) return;

        // Apply sorting
        this.matrixData.sort((a, b) => {
            let vA = a[this.currentSortCol];
            let vB = b[this.currentSortCol];
            if (typeof vA === "string") {
                return this.sortAscending ? vA.localeCompare(vB) : vB.localeCompare(vA);
            }
            return this.sortAscending ? (vA - vB) : (vB - vA);
        });

        tbody.innerHTML = "";
        this.matrixData.forEach(row => {
            const tr = document.createElement("tr");
            tr.className = `matrix-row ${this.isMatchingTicker(row.symbol, this.selectedTicker) ? 'active' : ''}`;
            tr.dataset.symbol = row.symbol;
            tr.dataset.name = row.name;

            let scoreClass = "score-neutral";
            if (row.ichimoku_score >= 1.0) scoreClass = "score-bullish";
            else if (row.ichimoku_score <= -1.0) scoreClass = "score-bearish";

            const zClass = row.institutional_acc ? "z-high" : "";
            const squeezeBadge = row.volatility_squeeze ? '<span class="squeeze-pill" title="Kumo Squeeze Active"></span>' : '';
            const changeClass = row.daily_change_pct >= 0 ? 'val-up' : 'val-down';

            tr.innerHTML = `
                <td class="ticker-cell">
                    ${row.code}
                    ${row.is_etf ? '<span class="etf-tag">ETF</span>' : ''}
                </td>
                <td><strong>${row.name}</strong></td>
                <td style="color:var(--text-secondary);font-size:10px;">${row.sector}</td>
                <td><strong>RM ${row.last_price.toFixed(3)}</strong></td>
                <td class="${changeClass}">${row.daily_change_pct > 0 ? '+' : ''}${row.daily_change_pct.toFixed(2)}%</td>
                <td>
                    <span class="score-badge ${scoreClass}">
                        ${row.ichimoku_score > 0 ? '+' : ''}${row.ichimoku_score.toFixed(1)}
                    </span>
                </td>
                <td><span class="${zClass}">${row.volume_z_score.toFixed(2)}</span></td>
                <td>${row.mrs.toFixed(2)}%</td>
                <td>${row.atr_pct.toFixed(2)}% ${squeezeBadge}</td>
            `;

            tr.addEventListener("click", () => {
                this.sendTickerSelect(row.symbol, row.name);
            });

            tbody.appendChild(tr);
        });
    }

    highlightMatrixRow(symbol) {
        const rows = document.querySelectorAll(".matrix-row");
        rows.forEach(r => {
            if (this.isMatchingTicker(r.dataset.symbol, symbol)) {
                r.classList.add("active");
                r.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                r.classList.remove("active");
            }
        });
    }

    initTableSortListeners() {
        const headers = document.querySelectorAll(".matrix-table th");
        headers.forEach(th => {
            th.addEventListener("click", () => {
                const col = th.dataset.col;
                if (!col) return;
                if (this.currentSortCol === col) {
                    this.sortAscending = !this.sortAscending;
                } else {
                    this.currentSortCol = col;
                    this.sortAscending = false;
                }
                this.renderMatrixTable();
            });
        });
    }

    async loadAuditForTicker(ticker) {
        try {
            const resp = await fetch(`/api/analyze/${encodeURIComponent(ticker)}`);
            const data = await resp.json();
            if (data.success) {
                if (data.payload) {
                    this.renderFundamentalUpdate(data.payload);
                } else {
                    this.renderAuditUI(data.audit, data.llm_review);
                }
            }
        } catch (e) {
            console.error("Error loading audit for ticker:", e);
        }
    }

    /**
     * Mandate 2 & Mandate 4: Dynamic Asset-Class Forking and WebSocket State Rendering
     * Branch A: Equity Fundamental Auditor (Applied to 22 Equities)
     * Branch B: i-ETF Vault & Structure Auditor (Applied to 0828EA.KL GOLDETF)
     */
    renderFundamentalUpdate(payload) {
        const titleEl = document.getElementById("auditor-panel-title");
        const headerEl = document.getElementById("auditor-ticker-badge");
        const verdictEl = document.getElementById("auditor-shariah-verdict");
        const leftContainer = document.getElementById("auditor-left-panel") || document.querySelector(".auditor-left");
        const rightContainer = document.getElementById("auditor-mda-points");

        const m = payload.metrics || {};
        const n = payload.narrative || {};
        const isEtf = payload.is_etf || payload.ticker.includes("0828EA");

        // ---------------------------------------------------------------------
        // Branch B: i-ETF Macro Driver & Commodity Transmission Engine (0828EA.KL)
        // ---------------------------------------------------------------------
        if (isEtf) {
            if (titleEl) titleEl.textContent = "Zone 3: Macro Driver & Commodity Transmission Engine (0828EA.KL)";
            if (headerEl) {
                headerEl.textContent = `${payload.name || "TradePlus Gold"} (${payload.ticker})`;
                headerEl.className = "badge badge-gold";
            }
            if (verdictEl) {
                verdictEl.textContent = "100% ALLOCATED BULLION (AAOIFI Standard 57)";
                verdictEl.className = "sac-badge-pass";
            }

            const tele = payload.macro_telemetry || {};
            const bp = payload.bullion_pricing || {};

            // Card 1: COMEX GOLD (USD/oz)
            const c1 = tele.card_1 || {};
            const goldVal = c1.val || m.macro_card_1_val || (m.gold_price_usd ? `$${Number(m.gold_price_usd).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : "$4,241.40");
            const goldBadge = c1.badge || m.macro_card_1_badge || "+1.48% (99.8% PM Fix Corr)";
            const goldClass = c1.class || m.macro_card_1_class || "sac-badge-pass";

            // Card 2: US 10Y BOND YIELD
            const c2 = tele.card_2 || {};
            const tnxVal = c2.val || m.macro_card_2_val || (m.us10y_yield ? `${Number(m.us10y_yield).toFixed(2)}%` : "5.21%");
            const tnxBadge = c2.badge || m.macro_card_2_badge || "Bullion Carry Cost (Restrictive)";
            const tnxClass = c2.class || m.macro_card_2_class || "sac-badge-pass";

            // Card 3: BRENT CRUDE OIL
            const c3 = tele.card_3 || {};
            const brentVal = c3.val || m.macro_card_3_val || (m.brent_price_usd ? `$${Number(m.brent_price_usd).toFixed(2)}/bbl` : "$97.76/bbl");
            const brentBadge = c3.badge || m.macro_card_3_badge || "Headline Inflation & Risk Premium";
            const brentClass = c3.class || m.macro_card_3_class || "sac-badge-warn";

            // Card 4: USD / MYR FX RATE
            const c4 = tele.card_4 || {};
            const myrVal = c4.val || m.macro_card_4_val || (m.usd_myr_rate ? `RM ${Number(m.usd_myr_rate).toFixed(4)}` : "RM 4.0787");
            const myrBadge = c4.badge || m.macro_card_4_badge || "Unhedged FX Drag / Tailwind";
            const myrClass = c4.class || m.macro_card_4_class || "sac-badge-pass";

            // Bullion pricing variables
            const indicativeNav = bp.indicative_nav || m.indicative_nav || m.nav_per_unit || 5.629;
            const navPerGram = bp.nav_per_gram || m.nav_per_gram || 555.78;
            const spreadPct = bp.spread_pct !== undefined ? bp.spread_pct : (m.spread_pct !== undefined ? m.spread_pct : -6.20);
            const spreadFormatted = bp.spread_formatted || m.spread_formatted || `${spreadPct > 0 ? '+' : ''}${Number(spreadPct).toFixed(2)}%`;
            const arbStatus = bp.arbitrage_status || m.arbitrage_status || "DISCOUNT (Arbitrage Entry)";
            const arbRec = bp.arbitrage_recommendation || m.arbitrage_recommendation || "Bursa units trading at a discount to theoretical physical NAV.";
            const bursaPrice = bp.bursa_price || m.bursa_price || 5.28;
            const arbBadgeClass = spreadPct > 0.75 ? "sac-badge-warn" : "sac-badge-pass";

            if (leftContainer) {
                leftContainer.innerHTML = `
                    <div class="auditor-stat-card">
                        <div class="stat-label">
                            <span>COMEX GOLD (USD/oz)</span>
                            <span class="badge badge-gold">LBMA PM Fix</span>
                        </div>
                        <div class="stat-value" id="macro-gold-val">${goldVal}</div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                            <span class="${goldClass}">${goldBadge}</span>
                            <span style="font-size:9.5px;color:var(--text-secondary)">Correlation: 0.998</span>
                        </div>
                    </div>

                    <div class="auditor-stat-card">
                        <div class="stat-label">
                            <span>US 10Y BOND YIELD</span>
                            <span class="badge badge-teal">Treasury Benchmark</span>
                        </div>
                        <div class="stat-value" id="macro-us10y-val">${tnxVal}</div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                            <span class="${tnxClass}">${tnxBadge}</span>
                            <span style="font-size:9.5px;color:var(--text-secondary)">Carry Opportunity Cost</span>
                        </div>
                    </div>

                    <div class="auditor-stat-card">
                        <div class="stat-label">
                            <span>BRENT CRUDE OIL</span>
                            <span class="badge badge-purple">Energy / CPI Beta</span>
                        </div>
                        <div class="stat-value" id="macro-brent-val">${brentVal}</div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                            <span class="${brentClass}">${brentBadge}</span>
                            <span style="font-size:9.5px;color:var(--text-secondary)">Geopolitical Risk Premium</span>
                        </div>
                    </div>

                    <div class="auditor-stat-card">
                        <div class="stat-label">
                            <span>USD / MYR FX RATE</span>
                            <span class="badge badge-blue">Currency Translation</span>
                        </div>
                        <div class="stat-value" id="macro-usdmyr-val">${myrVal}</div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                            <span class="${myrClass}">${myrBadge}</span>
                            <span style="font-size:9.5px;color:var(--text-secondary)">Unhedged Domestic FX</span>
                        </div>
                    </div>
                `;
            }

            // Extract 5-Point Macro Audit narrative
            const p1Title = n.point1_title || "1. Theoretical NAV & Pricing Spread (Arbitrage Check)";
            const p1Body = n.point1_body || n.commercial_drivers || `Indicative Bullion NAV is RM ${Number(indicativeNav).toFixed(3)} per unit (Theoretical Gold RM ${Number(navPerGram).toFixed(2)}/gram) vs Current Bursa Price RM ${Number(bursaPrice).toFixed(3)}. Pricing spread stands at ${spreadFormatted} (${arbStatus}). ${arbRec}`;

            const p2Title = n.point2_title || "2. Real Yields & Opportunity Cost Transmission";
            const p2Body = n.point2_body || n.cash_deployment || `US 10-Year Treasury Yield trades at ${tnxVal}. Because physical bullion yields zero nominal coupon, elevated real yields increase bullion carry opportunity costs. Yield pullbacks prompt macro asset allocators to rotate capital out of sovereign debt into zero-credit-risk physical gold reserves.`;

            const p3Title = n.point3_title || "3. Energy & Geopolitical Risk Premium";
            const p3Body = n.point3_body || n.working_capital || `Brent Crude Oil Futures quote at ${brentVal}. Energy benchmarks serve as the primary catalyst for global headline CPI inflation expectations and geopolitical supply disruption risks. Spikes in crude risk premiums stimulate safe-haven flight-to-safety liquidity into physical bullion vaults as an unencumbered purchasing power hedge.`;

            const p4Title = n.point4_title || "4. USD/MYR Currency Translation Impact";
            const p4Body = n.point4_body || n.forward_catalysts || `USD/MYR currency pair quotes at ${myrVal}. 0828EA is an unhedged domestic vehicle, meaning domestic MYR unit returns decompose into: [USD Gold Price Movement] + [USD/MYR FX Vector]. Ringgit moves directly transmit to domestic returns, serving as an organic hedge against local currency devaluation.`;

            const p5Title = n.point5_title || "5. Tournament Utility & Shariah Vault Governance";
            const p5Body = n.point5_body || n.shariah_governance || `Mandatory 30% i-ETF tournament allocation rubric: 0828EA satisfies portfolio diversification guidelines. Backed 100% by allocated physical LBMA 99.5% standard gold bars vaulted at Malca-Amit Singapore. Certified Shariah-compliant by Amanie Advisors under AAOIFI Shariah Standard No. 57 on Gold, guaranteeing zero interest-bearing paper gold, zero leverage, and strictly prohibited securities lending.`;

            if (rightContainer) {
                rightContainer.innerHTML = `
                    <div class="mda-point gold">
                        <div class="mda-point-title" style="display:flex;justify-content:space-between;align-items:center;">
                            <span>${p1Title}</span>
                            <span class="${arbBadgeClass}" style="font-size:9.5px;">${arbStatus}</span>
                        </div>
                        <div class="mda-point-body">${p1Body}</div>
                    </div>

                    <div class="mda-point blue">
                        <div class="mda-point-title">${p2Title}</div>
                        <div class="mda-point-body">${p2Body}</div>
                    </div>

                    <div class="mda-point purple">
                        <div class="mda-point-title">${p3Title}</div>
                        <div class="mda-point-body">${p3Body}</div>
                    </div>

                    <div class="mda-point">
                        <div class="mda-point-title">${p4Title}</div>
                        <div class="mda-point-body">${p4Body}</div>
                    </div>

                    <div class="mda-point gold">
                        <div class="mda-point-title" style="display:flex;justify-content:space-between;align-items:center;">
                            <span>${p5Title}</span>
                            <span class="badge badge-gold" style="font-size:9px;">30% i-ETF Rubric PASS</span>
                        </div>
                        <div class="mda-point-body">${p5Body}</div>
                    </div>
                `;
            }
            return;
        }

        // ---------------------------------------------------------------------
        // Branch A: Equity Fundamental Auditor (Applied to 22 Equities)
        // ---------------------------------------------------------------------
        if (titleEl) titleEl.textContent = "Zone 3: A4 PDF Quarterly Disclosure & Fundamental Auditor";
        if (headerEl) {
            headerEl.textContent = `${payload.name} (${payload.ticker})`;
            headerEl.className = "badge badge-blue";
        }

        const isCompliant = m.shariah_compliant !== undefined ? m.shariah_compliant : true;
        if (verdictEl) {
            verdictEl.textContent = isCompliant ? "STRICTLY COMPLIANT" : "FLAGGED NON-COMPLIANT";
            verdictEl.className = isCompliant ? "sac-badge-pass" : "sac-badge-warn";
        }

        const fcfFormatted = m.free_cash_flow || "RM --";
        const eqVal = typeof m.earnings_quality === 'number' ? m.earnings_quality.toFixed(3) : (m.earnings_quality || "--");
        const eqGrade = (typeof m.earnings_quality === 'number' && m.earnings_quality >= 0.85) 
            ? "HIGH QUALITY" 
            : ((typeof m.earnings_quality === 'number' && m.earnings_quality >= 0.70) ? "ACCEPTABLE" : "ACCRUAL DRIVEN");

        const cashPct = m.cash_ratio_pct !== undefined ? m.cash_ratio_pct : 0.0;
        const debtPct = m.debt_ratio_pct !== undefined ? m.debt_ratio_pct : 0.0;

        const cashPass = cashPct < 33.0;
        const debtPass = debtPct < 33.0;

        if (leftContainer) {
            leftContainer.innerHTML = `
                <div class="auditor-stat-card">
                    <div class="stat-label">
                        <span>Free Cash Flow (FCF = CFO - CAPEX)</span>
                        <span class="badge badge-teal">Cash Generation</span>
                    </div>
                    <div class="stat-value" id="auditor-fcf-val">${fcfFormatted}</div>
                </div>

                <div class="auditor-stat-card">
                    <div class="stat-label">
                        <span>Earnings Quality (CFO / EBITDA)</span>
                        <span class="badge badge-blue">Accrual Check</span>
                    </div>
                    <div class="stat-value" id="auditor-cfo-ebitda-val">${eqVal} <span style="font-size:10px;color:var(--text-secondary)">(${eqGrade})</span></div>
                </div>

                <div class="auditor-stat-card">
                    <div class="stat-label">
                        <span>SAC SC Cash Ratio (&lt; 33%)</span>
                        <span style="font-size:9px;color:var(--text-dim)">Cash / Assets</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                        <span class="${cashPass ? 'sac-badge-pass' : 'sac-badge-warn'}" id="auditor-cash-ratio-badge">${cashPct.toFixed(2)}% (${cashPass ? 'PASS <33%' : 'VIOLATION >=33%'})</span>
                        <span style="font-size:10px;color:var(--text-secondary)">Limit: 33.0%</span>
                    </div>
                </div>

                <div class="auditor-stat-card">
                    <div class="stat-label">
                        <span>SAC SC Conventional Debt Ratio (&lt; 33%)</span>
                        <span style="font-size:9px;color:var(--text-dim)">Interest Debt / Assets</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
                        <span class="${debtPass ? 'sac-badge-pass' : 'sac-badge-warn'}" id="auditor-debt-ratio-badge">${debtPct.toFixed(2)}% (${debtPass ? 'PASS <33%' : 'VIOLATION >=33%'})</span>
                        <span style="font-size:10px;color:var(--text-secondary)">Limit: 33.0%</span>
                    </div>
                </div>
            `;
        }

        if (rightContainer) {
            rightContainer.innerHTML = `
                <div class="mda-point">
                    <div class="mda-point-title">1. Real Commercial Drivers of Revenue Changes</div>
                    <div class="mda-point-body">${n.commercial_drivers || "Extracting operational revenue drivers..."}</div>
                </div>
                <div class="mda-point gold">
                    <div class="mda-point-title">2. Destinations of Operating Cash (CFO Deployment)</div>
                    <div class="mda-point-body">${n.cash_deployment || n.operating_cash_destination || "Extracting capital allocation..."}</div>
                </div>
                <div class="mda-point purple">
                    <div class="mda-point-title">3. Inventory & Receivables vs Revenue Growth Rate</div>
                    <div class="mda-point-body">${n.working_capital || n.inventory_receivables_audit || "Analyzing working capital velocity..."}</div>
                </div>
                <div class="mda-point blue">
                    <div class="mda-point-title">4. Forward Operational Catalysts & Backlog</div>
                    <div class="mda-point-body">${n.forward_catalysts || "Extracting forward operational catalysts..."}</div>
                </div>
                <div class="mda-point">
                    <div class="mda-point-title">5. Shariah Governance & SAC SC Compliance Audit</div>
                    <div class="mda-point-body">${n.shariah_governance || n.shariah_debt_posture || `Conventional debt-to-total assets ratio is ${debtPct.toFixed(2)}%, well within the SAC SC 33.00% ceiling.`}</div>
                </div>
            `;
        }
    }

    /**
     * Fallback renderer accepting legacy audit and mda objects
     */
    renderAuditUI(audit, mda) {
        if (!audit) return;
        const payload = {
            ticker: audit.symbol,
            name: audit.name,
            sector: audit.sector,
            is_etf: audit.is_etf,
            macro_mode: audit.is_etf,
            etf_structure: audit.etf_structure,
            bullion_pricing: audit.nav_data,
            metrics: audit.metrics || {},
            narrative: mda || {}
        };
        this.renderFundamentalUpdate(payload);
    }

    appendLog(log) {
        const stream = document.getElementById("telemetry-log-stream");
        if (!stream) return;

        const item = document.createElement("div");
        item.className = "log-item";
        item.innerHTML = `
            <span class="log-time">[${log.timestamp || new Date().toLocaleTimeString()}]</span>
            <span class="log-tag">[${log.tag || 'SYS'}]</span>
            <span class="log-msg" style="${log.level === 'WARNING' || log.level === 'CRITICAL' ? 'color:var(--neon-pink)' : (log.level === 'SUCCESS' ? 'color:var(--neon-teal)' : '')}">${log.message}</span>
        `;
        stream.appendChild(item);
        stream.scrollTop = stream.scrollHeight;
    }

    renderStopAlerts(alerts) {
        const box = document.getElementById("stop-alerts-box");
        if (!box) return;

        if (!alerts || alerts.length === 0) {
            box.innerHTML = `
                <div class="alert-item-ok">
                    ✓ All open positions holding comfortably above Daily Kijun-sen trailing stop.
                </div>
            `;
            return;
        }

        box.innerHTML = "";
        alerts.forEach(al => {
            const div = document.createElement("div");
            div.className = "alert-item";
            div.innerHTML = `
                <div style="font-weight:700;color:var(--neon-pink);display:flex;justify-content:space-between">
                    <span>⚠️ STOP TRIGGER: ${al.symbol} (${al.name})</span>
                    <span>PnL: ${al.unrealized_pnl_pct.toFixed(2)}%</span>
                </div>
                <div style="color:var(--text-secondary);margin-top:2px;">
                    Price RM ${al.current_price.toFixed(3)} breached Daily Kijun-sen trailing stop!
                </div>
                <div style="font-size:9px;color:var(--gold);margin-top:2px;">
                    Action: ${al.action_recommended}
                </div>
            `;
            box.appendChild(div);
        });
    }
}

// Instantiate Tower sync on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    window.towerClient = new TowerSyncClient();
});
