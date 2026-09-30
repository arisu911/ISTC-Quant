/**
 * Bursa Strategy - Vim-Style Command Line Interface (CLI) Parser
 * Accepts: :SCAN, :CHART <TICKER>, :ANALYZE <TICKER>, :FUND <TICKER>, :ORDER BUY/SELL <TICKER> <RM>, :STOP AUDIT
 * Compatible with Edge and Brave browsers.
 */

class VimCLI {
    constructor(inputFieldId, outputBoxId, deskSyncClient) {
        this.input = document.getElementById(inputFieldId);
        this.output = document.getElementById(outputBoxId);
        this.deskSync = deskSyncClient;
        this.history = [];
        this.historyIndex = -1;

        this.init();
    }

    init() {
        if (!this.input) return;

        this.printLine("BURSA STRATEGY QUANTITATIVE TERMINAL (VIM CLI v2.0)", "gold");
        this.printLine("Type ':HELP' for command syntax. All commands begin with ':'.", "dim");

        this.input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const val = this.input.value.trim();
                if (val) {
                    this.history.push(val);
                    this.historyIndex = this.history.length;
                    this.execute(val);
                    this.input.value = ":";
                }
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                if (this.historyIndex > 0) {
                    this.historyIndex--;
                    this.input.value = this.history[this.historyIndex];
                }
            } else if (e.key === "ArrowDown") {
                e.preventDefault();
                if (this.historyIndex < this.history.length - 1) {
                    this.historyIndex++;
                    this.input.value = this.history[this.historyIndex];
                } else {
                    this.historyIndex = this.history.length;
                    this.input.value = ":";
                }
            }
        });

        // Ensure ':' is always present as prompt prefix
        this.input.addEventListener("input", () => {
            if (!this.input.value.startsWith(":")) {
                this.input.value = ":" + this.input.value.replace(/^:+/, "");
            }
        });
    }

    printLine(text, type = "normal") {
        if (!this.output) return;
        const line = document.createElement("div");
        line.className = "vim-line";
        
        if (type === "cmd") line.className += " vim-line-cmd";
        else if (type === "err") line.className += " vim-line-err";
        else if (type === "gold" || type === "ok") line.className += " vim-line-ok";
        else if (type === "dim") line.style.color = "var(--text-dim)";
        
        line.textContent = text;
        this.output.appendChild(line);
        this.output.scrollTop = this.output.scrollHeight;
    }

    async execute(rawCmd) {
        this.printLine(`> ${rawCmd}`, "cmd");
        const clean = rawCmd.replace(/^:+/, "").trim();
        const parts = clean.split(/\s+/);
        const command = parts[0].toUpperCase();
        const args = parts.slice(1);

        switch (command) {
            case "SCAN":
                await this.handleScan();
                break;

            case "CHART":
                if (args.length < 1) {
                    this.printLine("Usage: :CHART <TICKER> (e.g. :CHART 5211 or :CHART 0828EA)", "err");
                } else {
                    await this.handleChart(args[0]);
                }
                break;

            case "ANALYZE":
                if (args.length < 1) {
                    this.printLine("Usage: :ANALYZE <TICKER> (e.g. :ANALYZE 5211)", "err");
                } else {
                    await this.handleAnalyze(args[0]);
                }
                break;

            case "FUND":
                if (args.length < 1) {
                    this.printLine("Usage: :FUND <TICKER> (e.g. :FUND 5211)", "err");
                } else {
                    this.handleFund(args[0]);
                }
                break;

            case "ORDER":
                if (args.length < 3) {
                    this.printLine("Usage: :ORDER <BUY|SELL> <TICKER> <RM_AMOUNT> (e.g. :ORDER BUY 5211 500)", "err");
                } else {
                    await this.handleOrder(args[0], args[1], args[2]);
                }
                break;

            case "STOP":
                if (args[0] && args[0].toUpperCase() === "AUDIT") {
                    await this.handleStopAudit();
                } else {
                    this.printLine("Unknown subcommand. Did you mean ':STOP AUDIT'?", "err");
                }
                break;

            case "HELP":
                this.printHelp();
                break;

            case "CLEAR":
                this.output.innerHTML = "";
                break;

            default:
                this.printLine(`Unknown command ':${clean}'. Type ':HELP' for list of commands.`, "err");
        }
    }

    async handleScan() {
        this.printLine("Running vectorized quantitative factor scan across universe...", "normal");
        try {
            const resp = await fetch("/api/scan");
            const data = await resp.json();
            this.printLine(`✓ Factor scan complete! Evaluated ${data.count} tickers. Matrix updated.`, "ok");
            if (this.deskSync) {
                this.deskSync.notifyScanComplete();
            }
        } catch (e) {
            this.printLine(`Scan error: ${e.message}`, "err");
        }
    }

    async handleChart(ticker) {
        this.printLine(`Loading technical overlays and canvas for ${ticker}...`, "normal");
        if (this.deskSync) {
            await this.deskSync.selectTicker(ticker);
            this.printLine(`✓ Chart canvas updated to ${ticker}.`, "ok");
        }
    }

    async handleAnalyze(ticker) {
        this.printLine(`Fetching Bursa Category FA quarterly report for ${ticker}...`, "normal");
        try {
            const resp = await fetch(`/api/analyze/${encodeURIComponent(ticker)}`);
            const data = await resp.json();
            if (data.success) {
                const a = data.audit.metrics;
                this.printLine(`✓ Audit Completed: ${data.meta.name} (${data.meta.code})`, "ok");
                this.printLine(`  • Shariah Verdict: ${data.audit.shariah_verdict}`, "gold");
                this.printLine(`  • FCF: ${a.fcf_formatted || ('RM ' + a.fcf_myr_k.toLocaleString() + 'k')} | CFO/EBITDA: ${a.cfo_ebitda_ratio} (${a.quality_grade})`, "normal");
                this.printLine(`  • Conventional Cash Ratio: ${a.sac_cash_badge}`, "normal");
                this.printLine(`  • Conventional Debt Ratio: ${a.sac_debt_badge}`, "normal");
                this.printLine(`  • MD&A Summary: ${data.llm_review.executive_summary}`, "dim");
            } else {
                this.printLine(`Audit failed: ${data.error || "Unknown error"}`, "err");
            }
        } catch (e) {
            this.printLine(`Analyze error: ${e.message}`, "err");
        }
    }

    handleFund(ticker) {
        const clean = ticker.replace(".KL", "");
        const url = `https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=${clean}`;
        this.printLine(`Opening official Bursa Malaysia announcement page for ${ticker}...`, "normal");
        window.open(url, "_blank");
        this.printLine(`✓ Launched browser tab: ${url}`, "ok");
    }

    async handleOrder(action, ticker, amount) {
        const amt = parseFloat(amount);
        if (isNaN(amt) || amt <= 0) {
            this.printLine(`Invalid amount: ${amount}`, "err");
            return;
        }
        this.printLine(`Submitting simulated ${action.toUpperCase()} order for ${ticker} (RM ${amt.toFixed(2)})...`, "normal");
        try {
            const resp = await fetch("/api/order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: action.toUpperCase(),
                    ticker: ticker,
                    amount_myr: amt,
                    notes: "Vim CLI order"
                })
            });
            const res = await resp.json();
            if (res.success) {
                const t = res.trade;
                this.printLine(`✓ Order Executed: ${t.action} ${t.units} units of ${t.symbol} @ RM ${t.price.toFixed(3)} (RM ${t.total_myr.toFixed(2)})`, "ok");
                this.printLine(`  Rubric Status: i-ETF ${res.rubric.etf_badge} | Fractional ${res.rubric.fractional_badge} | Total ${res.rubric.total_badge}`, "gold");
                if (this.deskSync) {
                    this.deskSync.updateRubricHUD(res.rubric);
                }
            } else {
                this.printLine(`Order Rejected: ${res.error}`, "err");
            }
        } catch (e) {
            this.printLine(`Order execution failed: ${e.message}`, "err");
        }
    }

    async handleStopAudit() {
        this.printLine("Executing trailing stop audit on active positions against Daily Kijun-sen...", "normal");
        try {
            const resp = await fetch("/api/stop_audit");
            const data = await resp.json();
            if (data.alert_count === 0) {
                this.printLine("✓ Stop Audit Pass: All open positions holding above Daily Kijun-sen trailing stop.", "ok");
            } else {
                this.printLine(`⚠️ CRITICAL STOP AUDIT: ${data.alert_count} positions triggered trailing stops!`, "err");
                for (const al of data.alerts) {
                    this.printLine(`  [EXIT ALERT] ${al.symbol} (${al.name}): Price RM ${al.current_price.toFixed(3)} breached Kijun-sen! PnL: ${al.unrealized_pnl_pct}%`, "err");
                }
            }
        } catch (e) {
            this.printLine(`Stop audit error: ${e.message}`, "err");
        }
    }

    printHelp() {
        this.printLine("BURSA STRATEGY VIM COMMAND REFERENCE:", "gold");
        this.printLine("  :SCAN                           -> Re-runs factor pipeline across universe & updates table", "normal");
        this.printLine("  :CHART <TICKER>                 -> Loads ticker chart, Ichimoku cloud & AVWAP", "normal");
        this.printLine("  :ANALYZE <TICKER>               -> Downloads latest Bursa QR and runs fundamental audit", "normal");
        this.printLine("  :FUND <TICKER>                  -> Opens official Bursa Malaysia announcement page", "normal");
        this.printLine("  :ORDER BUY/SELL <TICKER> <RM>   -> Simulates fractional execution and logs entry", "normal");
        this.printLine("  :STOP AUDIT                     -> Scans open positions for daily closes below Kijun-sen", "normal");
        this.printLine("  :CLEAR                          -> Clears output window", "normal");
    }
}
