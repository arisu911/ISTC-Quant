# BURSA STRATEGY: Institutional Quantitative Terminal & Shariah Execution Desk
### Dual-Display Workstation, Real-Time Factor Screener & Automated Macro/Fundamental Auditor
**Engineered for the Invest Shariah Trading Challenge (ISTC) 2026**  
*Platform: UP by CGS International | Bourse: Bursa Malaysia*

---

## 1. Executive Summary & Pitch Thesis

**Bursa Strategy** is a custom-engineered quantitative trading terminal and automated factor screener designed to solve the structural disadvantages retail participants face in small-capital equity trading competitions.

### The Competition Context
* **Seed Capital:** RM 50.00 (Fixed tournament allocation).
* **Execution Environment:** UP App Fractional Share Engine (increments of 0.01 units).
* **The Strategic Problem:** In an ultra-low seed capital challenge, conventional retail trading behaviors—such as over-diversification, emotional chasing of penny stocks, and unhedged drawdowns—lead to immediate alpha decay. Splitting RM 50 across 5 different stocks introduces friction and dilutes percentage returns ($ROI\%$).
* **The Systematic Solution:** Bursa Strategy treats the competition as a high-conviction momentum sprint governed by strict risk management:
  1. **Algorithmic Signal Convergence:** Trades are triggered strictly when discrete mathematical factors align: Ichimoku Composite Score $\ge +3.0$, Institutional Accumulation Volume $Z$-Score $\ge 2.0$, and positive Mansfield Relative Strength ($\text{MRS}$).
  2. **Rubric Optimization:** Fulfills mandatory challenge quotas on Day 1 (2 fractional trades, 2 i-ETF trades using `0828EA`), ensuring full compliance with the 30% i-ETF and 20% Fractional scoring criteria.
  3. **Dual-Display Architecture:** Fully decouples execution mechanics (1080p horizontal workspace) from high-density data analytics (1440p vertical tower) via low-latency WebSockets.

---

## 2. Dual-Display Hardware Geometry & Layout

The terminal operates across two physical displays synchronized in real time via an asynchronous FastAPI WebSocket hub (`/ws/channel`):

```
┌──────────────────────────────────────────────┐  ┌─────────────────────────────────────────────────────────┐
│     DISPLAY 1: VERTICAL TOWER (1440 × 2560)  │  │         DISPLAY 2: DESK WORKSPACE (1920 × 1080)         │
│     Route: /tower                            │  │         Route: /desk                                  │
├──────────────────────────────────────────────┤  ├─────────────────────────────────────────────────────────┤
│ ZONE 1: Shariah Universe Factor Screener     │  │ ZONE A: Multi-Timeframe Lightweight Chart               │
│ • 23 Whitelisted Instruments (22 + 0828EA)   │  │ • 1H, 4H, and 1D Candlesticks (Up to 730D Depth)       │
│ • Ichimoku Score (-5 to +5)                  │  │ • TradingView-Native Palette (Tenkan Blue, Kijun Red)   │
│ • Vol Z-Score, Mansfield RS%, ATR% Squeeze   │  │ • Hardware-Accelerated Shaded Kumo Canvas Overlay       │
├──────────────────────────────────────────────┤  │ • Anchored VWAP (Tournament & Budget 2027 Anchors)      │
│ ZONE 2: Catalyst Countdown Horizon           │  ├─────────────────────────────────────────────────────────┤
│ • Kickoff (Oct 5), Budget 2027 (Oct 9)       │  │ ZONE B: Fractional Unit Sizer & Tournament HUD          │
│ • 3Q26 Disclosures, Finale Stop (Nov 13)     │  │ • Reactive 0.01 Fractional Share Math (Locked to RM50)  │
├──────────────────────────────────────────────┤  │ • Live Rubric Status: i-ETF [X/2], Fractional [X/2]     │
│ ZONE 3: Sector-Adaptive Auditor              │  │ • Active PnL, Portfolio Value, and Order Execution      │
│ • Equities: FCF, CFO/EBITDA, SAC SC Ratios   │  ├─────────────────────────────────────────────────────────┤
│ • 0828EA: Gold, 10Y Yield, Crude, USDMYR     │  │ ZONE C: Quantitative Vim Terminal Prompt                │
├──────────────────────────────────────────────┤  │ • CLI Keyboard Navigation (:SCAN, :CHART, :ORDER)       │
│ ZONE 4: Institutional Telemetry & Stops      │  └─────────────────────────────────────────────────────────┘
│ • WebSocket Logs & Kijun-sen Trailing Alerts │
└──────────────────────────────────────────────┘
```

---

## 3. Data Pipeline & Real-Time Integrity

The architecture eliminates standard retail feed delays and protects against data contamination:

1. **Zero-Delay Price Ingestion (`data/realtime_feed.py`):**
   - Eliminates Yahoo Finance's 15–20 minute delay on Malaysian `.KL` tickers.
   - Polls direct Bursa Malaysia equities endpoints and unadjusted real-time feeds every 3–5 seconds during market hours (`09:00 - 12:30`, `14:30 - 17:00` MYT).
   - Ingests into an in-memory dictionary `LIVE_MARKET_STATE` streamed over `/ws/channel`.
2. **Unadjusted Historical Bar Integrity (`data/loader.py`):**
   - Enforces `auto_adjust=False` on all historical OHLCV queries to prevent dividend deductions from deflating nominal chart candles (preserving true nominal trading levels).
   - Intraday `1h` data is ingested with a `730d` lookback window (the maximum limit on Yahoo Finance = 2 full years of hourly candles) and cleanly resampled into native `4h` bars using Pandas.
3. **State Isolation & Anti-Collision:**
   - All state, caching, and fundamental data are strictly keyed by ticker string (`FUNDAMENTAL_REGISTRY[ticker]`), eliminating off-by-one array indexing errors and preventing cross-instrument leakage.

---

## 4. The 23-Instrument Shariah Universe

The screener tracks only the 23 Shariah-compliant counters tradeable under the UP App Fractional framework:

| Role / Tier | Counters | Focus Metrics |
| :--- | :--- | :--- |
| **Mandatory Compliance** | `0828EA.KL` (TradePlus Shariah Gold Tracker) | Physical gold backing, US 10Y Yield, USD/MYR beta, 30% challenge rubric fulfillment. |
| **Tier 1: High Beta & Momentum Outliers** | `5136.KL` (HEXTECH), `5211.KL` (SUNWAY), `8869.KL` (PMETAL), `1818.KL` (BURSA) | Maximum daily ATR%, institutional liquidity, relative strength breakouts. Primary capital targets. |
| **Tier 2: Liquid Cyclicals & Structural Swings** | `5347.KL` (TENAGA), `4863.KL` (TM), `5296.KL` (MRDIY), `3816.KL` (MISC), `5183.KL` (PCHEM), `5681.KL` (PETDAG) | High-volume trend-following plays tied to national policy (NETR, data centre grid buildouts). |
| **Tier 3: Core Defensives (Monitored Only)** | `6012.KL` (MAXIS), `6947.KL` (CDB), `6888.KL` (AXIATA), `4707.KL` (NESTLE), `6033.KL` (PETGAS), `5225.KL` (IHH), `4197.KL` (SIME), `7084.KL` (QL), `4065.KL` (PPB), `1961.KL` (IOICORP), `2445.KL` (KLK), `5285.KL` (SDG) | Low beta, low volatility. Tracked for market breadth; excluded from tournament capital deployment. |

---

## 5. Quantitative Methodology & Mathematical Models

### A. Discrete Ichimoku Momentum Scoring Engine ($-5.0$ to $+5.0$)
Calculated across standard 9, 26, and 52-period windows:
* **Tenkan-sen (Conversion Line):** $\frac{\max(H_9) + \min(L_9)}{2}$ (TradingView Royal Blue: `#2962FF`)
* **Kijun-sen (Base Line / Trailing Stop):** $\frac{\max(H_{26}) + \min(L_{26})}{2}$ (TradingView Solid Red: `#D32F2F`)
* **Senkou Span A:** $\frac{\text{Tenkan} + \text{Kijun}}{2}$ shifted $+26$ periods ahead (Border: `#81C784`)
* **Senkou Span B:** $\frac{\max(H_{52}) + \min(L_{52})}{2}$ shifted $+26$ periods ahead (Border: `#E57373`)
* **Chikou Span (Lagging Line):** Close shifted $-26$ periods back (Forest Green: `#4CAF50`)
* **Shaded Kumo Cloud Fill:** Rendered on an HTML5 canvas overlay via `requestAnimationFrame`:
  * Bullish Kumo ($\text{Span A} \ge \text{Span B}$): `rgba(76, 175, 80, 0.18)`
  * Bearish Kumo ($\text{Span A} < \text{Span B}$): `rgba(239, 83, 80, 0.18)`
* **Scoring Rules:** $+1.0$ for Price $>$ Cloud, $+1.0$ for Tenkan $>$ Kijun, $+1.0$ for Chikou $>$ Price, $+1.0$ for Bullish Forward Cloud, $+1.0$ for Positive Kijun Slope.

### B. Institutional Volume $Z$-Score
Identifies accumulation by institutional order desks versus retail turnover:
$$Z_{\text{vol}} = \frac{V_t - \mu_{20}(V)}{\sigma_{20}(V)}$$
* Threshold: $Z_{\text{vol}} \ge 2.0$ flags high-conviction institutional accumulation (highlighted gold on the volume histogram).

### C. Mansfield Relative Strength ($\text{MRS}$)
Quantifies continuous outperformance against the benchmark FBM Emas Shariah Index ($FBMS.KL$):
$$\text{Base RS}_t = \frac{P_{\text{stock}, t} / P_{\text{FBMS}, t}}{\text{SMA}_{20}(P_{\text{stock}} / P_{\text{FBMS}})}$$
$$\text{MRS}_t = (\text{Base RS}_t - 1.0) \times 100$$

### D. Multi-Anchor VWAP ($\text{AVWAP}$)
$$\text{AVWAP}_{t_0 \to t} = \frac{\sum_{i=t_0}^t (P_{\text{typical}, i} \times V_i)}{\sum_{i=t_0}^t V_i}$$
* **Primary Anchor:** 5 October 2026 (Tournament Kickoff).
* **Macro Event Anchor:** 9 October 2026 (Malaysia Federal Budget 2027 Announcement).

---

## 6. Fundamental & Cross-Asset Macro Auditor (Zone 3)

Zone 3 dynamically switches analytical frameworks based on asset class:

### Mode 1: Corporate Equity Fundamental Auditor (The 22 Stocks)
Parses quarterly disclosures (`cat=FA`) with dynamic unit normalization (`RM'000` to `RM'M`):
* **Free Cash Flow:** $\text{FCF} = \text{Operating Cash Flow (CFO)} - \text{CAPEX}$
* **Earnings Quality (Accrual Metric):** $\text{Ratio} = \frac{\text{CFO}}{\text{EBITDA}}$ (Values $> 0.80$ verify cash generation over accounting accruals).
* **SAC Securities Commission Shariah Compliance Checks:**
  $$\text{Cash Ratio} = \frac{\text{Conventional Cash \& Placements}}{\text{Total Assets}} < 33.0\% \quad [\text{PASS}]$$
  $$\text{Debt Ratio} = \frac{\text{Interest-Bearing Conventional Debt}}{\text{Total Assets}} < 33.0\% \quad [\text{PASS}]$$
* **Sector-Adaptive MD&A Narrative:** Dynamically adapts operational extraction:
  * Consumer/Retail: Same-Store Sales Growth (SSSG), store count expansion.
  * Conglomerate/Construction: Unbilled order book, contracted backlog.
  * Utilities/Telco: Grid CAPEX, data centre power off-take commitments.
  * Plantation: Fresh Fruit Bunch (FFB) yields, realized CPO prices.

### Mode 2: Macro Driver & Bullion Arbitrage Auditor (`0828EA.KL`)
When `0828EA` is active, Zone 3 swaps corporate cards for live cross-asset macro telemetry:
* **COMEX Gold Futures (`GC=F`):** Spot gold momentum ($USD/oz$).
* **US 10-Year Treasury Yield (`^TNX`):** Real-rate opportunity cost for non-yielding bullion.
* **Brent Crude Oil (`BZ=F`):** Headline inflation barometer and geopolitical risk beta.
* **USD / MYR FX Rate (`MYR=X`):** Currency translation impact on Bursa quotation.
* **Theoretical NAV & Pricing Spread (Arbitrage Gauge):**
  $$\text{NAV}_{\text{per gram}} = \frac{P_{\text{Gold (USD)}} \times \text{USDMYR}}{31.1034768}$$
  $$\text{Spread \%} = \left( \frac{P_{\text{0828EA}}}{\text{Indicative Fund NAV}} - 1.0 \right) \times 100$$
* **Shariah Vault Certification:** Audits physical 1kg gold bar allocation (LBMA 99.5% minimum purity) in Singapore custody under AAOIFI Standard No. 57.

---

## 7. Tournament Sizing Engine & Rubric Tracker (Zone B)

* **Starting Capital:** Exactly **RM 50.00**.
* **0.01 Fractional Share Math:**
  * Bidirectional synchronization: adjusting fractional units updates RM allocation; adjusting RM allocation updates fractional units to 4 decimal places:
    $$\text{Units} = \frac{\text{Target RM Allocation}}{P_{\text{current}}}$$
* **Quick Presets:** `0.01 Unit` (Min trade), `1.00 Unit`, `RM 5.00` (10%), `RM 25.00` (50%), `RM 50.00` (100% all-in).
* **Rubric Badges:** Real-time completion counters for `i-ETF Trades [0/2]`, `Fractional Trades [0/2]`, and `Total Trades [0/5]`.
* **Viewport Zero-Clip Lock:** Optimized for 1080p laptop displays at 100% zoom using CSS Grid (`100vh`), ensuring `EXECUTE BUY`, `EXECUTE SELL`, and cash balances remain fully visible without scrolling.

---

## 8. Installation & Quickstart

### Prerequisites
* Python 3.11+
* Microsoft Edge or Brave Browser (Google Chrome not required)

### Setup & Launch
```bash
# 1. Clone repository and navigate to workspace
cd "Bursa Strategy"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch terminal application
python main.py
```

The system will initialize the FastAPI server on `http://localhost:8000` and launch both displays:
* **Display 1 (Vertical 1440x2560):** `http://localhost:8000/tower`
* **Display 2 (Horizontal 1920x1080):** `http://localhost:8000/desk`

### Vim CLI Commands (Zone C)
* `:SCAN` — Force recalculation of quantitative factor rankings across all 23 tickers.
* `:CHART <TICKER>` — Switch active chart on Desk (e.g., `:CHART 5211.KL`).
* `:TF <1h|4h|1d>` — Switch active candlestick interval.
* `:ORDER BUY <TICKER> <UNITS>` — Simulate fractional execution and log ledger state.
* `:STOP AUDIT` — Run daily Kijun-sen trailing stop breach audit across open positions.
