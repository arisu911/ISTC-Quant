"""
Bursa Strategy Quantitative Trading Server & REST/WebSocket Gateway
FastAPI asynchronous architecture serving dual-display workstations (/tower & /desk).
Fully compatible with Microsoft Edge and Brave Browser. Zero paid APIs, 100% self-contained.
"""

import json
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config.settings import (
    BASE_DIR,
    TEMPLATES_DIR,
    STATIC_DIR,
    REPORTS_DIR,
    HOST,
    PORT,
    DATE_TOURNAMENT_OPEN,
    DATE_BUDGET_2027
)
from config.universe import UNIVERSE_DATA, ALL_SYMBOLS, get_ticker_meta
from config.catalysts import get_catalyst_telemetry
from data.loader import data_loader, MARKET_STATE
from data.realtime_feed import LIVE_MARKET_STATE, realtime_feed
from data.bursa_scraper import bursa_scraper
from factors.ichimoku import calculate_ichimoku, score_ichimoku_momentum, build_ichimoku_chart_series
from factors.volume_volatility import calculate_volume_volatility, get_latest_volume_metrics
from factors.relative_strength import calculate_mansfield_rs, get_latest_rs_metrics
from factors.institutional_flow import calculate_institutional_flows, get_latest_flow_metrics
from analyzer.pdf_extractor import pdf_extractor
from analyzer.fundamental_audit import fundamental_auditor
from analyzer.llm_agent import llm_agent
from analyzer.macro_audit import macro_auditor, MACRO_STATE
from simulation.rolling_sprint import rolling_sprint_simulator
from simulation.exit_engine import portfolio
from server.ws_hub import ws_hub

logger = logging.getLogger("bursa.server.app")

# Asynchronous Lifespan Management (Decoupled Background Polling)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: spawn real-time Bursa quote polling worker
    poll_task = asyncio.create_task(data_loader.start_realtime_polling(ws_hub.broadcast))
    logger.info("Direct Real-Time Bursa market data polling worker initialized.")
    yield
    # Shutdown: cancel worker, close HTTP client, and flush SSD Parquet caches
    poll_task.cancel()
    data_loader.stop_polling()
    await realtime_feed.close()
    logger.info("Server shutdown complete.")

# Initialize FastAPI app
app = FastAPI(
    title="Bursa Strategy - Institutional Trading Terminal",
    description="Quantitative Research Terminal & Shariah Factor Screener for Bursa Malaysia",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static files and templates
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Order Request Model supporting both Fractional Units and RM allocation
class OrderPayload(BaseModel):
    action: str  # BUY or SELL
    ticker: str
    units: Optional[float] = None
    amount_myr: Optional[float] = None
    notes: Optional[str] = ""

# --------------------------------------------------------------------------
# HTML UI Routes (Dual-Screen Display Workstation)
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def route_index(request: Request):
    """Launchpad hub providing direct entry to Tower (Portrait) and Desk (Widescreen)."""
    return templates.TemplateResponse(request=request, name="desk.html", context={"active_view": "desk"})

@app.get("/tower", response_class=HTMLResponse)
async def route_tower(request: Request):
    """Display 1: Vertical Portrait Monitor (1440 x 2560) - Factor Matrix, Catalysts, A4 PDF, Telemetry."""
    return templates.TemplateResponse(request=request, name="tower.html", context={"active_view": "tower"})

@app.get("/desk", response_class=HTMLResponse)
async def route_desk(request: Request):
    """Display 2: Horizontal Widescreen Laptop (1920 x 1080) - TradingView Canvas, Rubric HUD, Vim CLI."""
    return templates.TemplateResponse(request=request, name="desk.html", context={"active_view": "desk"})

# --------------------------------------------------------------------------
# WebSocket Endpoint
# --------------------------------------------------------------------------

@app.websocket("/ws/channel")
async def websocket_channel(websocket: WebSocket):
    """Bi-directional state sync between Display 1 and Display 2."""
    await ws_hub.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                ev = msg.get("event")
                
                if ev == "TICKER_SELECT":
                    ticker = msg.get("ticker_symbol") or msg.get("ticker", "5211.KL")
                    meta = get_ticker_meta(ticker)
                    await ws_hub.broadcast_ticker_select(meta["symbol"], meta["name"])
                    await ws_hub.broadcast_log(f"Display sync: Selected {meta['symbol']} ({meta['name']})", "INFO", "WS")
                    asyncio.create_task(analyze_quarterly_report(meta["symbol"]))

                elif ev == "PING":
                    await websocket.send_text(json.dumps({"event": "PONG"}))

                elif ev == "RUN_SCAN":
                    await ws_hub.broadcast_log("Initiating full universe factor rescan via WebSocket...", "INFO", "SCAN")
                    await ws_hub.broadcast({"event": "SCAN_TRIGGERED"})

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_hub.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_hub.disconnect(websocket)

# --------------------------------------------------------------------------
# Quantitative REST Endpoints
# --------------------------------------------------------------------------

@app.get("/api/universe")
async def get_universe():
    """Return the 23 permitted UP App instruments with sector metadata."""
    return {
        "count": len(UNIVERSE_DATA),
        "universe": UNIVERSE_DATA
    }

@app.get("/api/catalysts")
async def get_catalysts():
    """Return catalyst calendar dates with trading and calendar day countdowns."""
    events = get_catalyst_telemetry()
    return {
        "events": events,
        "as_of": datetime.now().strftime("%Y-%m-%d")
    }

@app.get("/api/macro")
async def get_macro_telemetry(bursa_price: Optional[float] = None):
    """
    Return live cross-asset macro telemetry (GC=F, ^TNX, BZ=F, MYR=X)
    and physical bullion theoretical NAV and arbitrage spread for 0828EA.KL.
    """
    if bursa_price is None:
        st = LIVE_MARKET_STATE.get("0828EA.KL") or MARKET_STATE.get("0828EA.KL")
        if st and (st.get("price") or st.get("last_price")):
            bursa_price = float(st.get("price") or st.get("last_price") or 5.28)
        else:
            bursa_price = 5.28

    telemetry = await macro_auditor.fetch_macro_telemetry_async()
    nav_data = macro_auditor.compute_gold_nav(bursa_price)
    narrative = macro_auditor.generate_macro_audit_narrative(nav_data, bursa_price)

    return {
        "status": "LIVE",
        "macro_state": telemetry,
        "nav_data": nav_data,
        "narrative": narrative
    }

@app.get("/api/market_state")
async def get_market_state_snapshot():
    """Return single source of truth in-memory LIVE_MARKET_STATE for all 23 tickers."""
    summary = []
    for sym in ALL_SYMBOLS:
        st = LIVE_MARKET_STATE.get(sym) or MARKET_STATE.get(sym)
        if not st:
            st = data_loader.fetch_live_quote_fast(sym)
        if st:
            p = st.get("price") if st.get("price") is not None else st.get("last_price", 1.0)
            chg = st.get("change", 0.0)
            chg_pct = st.get("change_pct") if st.get("change_pct") is not None else st.get("daily_change_pct", 0.0)
            high = st.get("high") if st.get("high") is not None else st.get("day_high", p)
            low = st.get("low") if st.get("low") is not None else st.get("day_low", p)
            vol = st.get("volume", 0)

            summary.append({
                "ticker_symbol": st.get("ticker_symbol", sym),
                "symbol": st.get("symbol", sym),
                "code": st.get("code", ""),
                "name": st.get("name", ""),
                "sector": st.get("sector", ""),
                "is_etf": st.get("is_etf", False),
                "price": round(float(p), 3),
                "last_price": round(float(p), 3),
                "change": round(float(chg), 3),
                "daily_change_pct": round(float(chg_pct), 2),
                "day_high": round(float(high), 3),
                "day_low": round(float(low), 3),
                "volume": int(vol),
                "updated_at": st.get("timestamp") or st.get("updated_at", "")
            })
    return {
        "count": len(summary),
        "symbols": [s["symbol"] for s in summary],
        "market_state": summary
    }

@app.get("/api/scan")
async def run_universe_scan():
    """
    Executes vectorized quantitative factor pipeline across the 23-instrument universe:
      - Composite Ichimoku Momentum Score (-5 to +5)
      - Institutional Volume Z-Score & Volatility Squeeze
      - Mansfield Relative Strength (MRS) & Alpha
      - Anchored VWAP & Chaikin Money Flow (CMF-21)
    """
    bench_df = data_loader.fetch_benchmark()
    results = []

    for item in UNIVERSE_DATA:
        sym = item["symbol"]
        try:
            df = data_loader.fetch_ohlcv(sym)
            if df.empty or len(df) < 30:
                continue

            # 1. Ichimoku
            ichi_df = calculate_ichimoku(df)
            ichi_score, ichi_meta = score_ichimoku_momentum(ichi_df)

            # 2. Volume & Volatility
            vol_df = calculate_volume_volatility(df)
            vol_meta = get_latest_volume_metrics(vol_df)

            # 3. Mansfield RS
            rs_df = calculate_mansfield_rs(df, bench_df)
            rs_meta = get_latest_rs_metrics(rs_df)

            # 4. Institutional Flows
            flow_df = calculate_institutional_flows(df)
            flow_meta = get_latest_flow_metrics(flow_df)

            # Retrieve price from in-memory market state if present
            st = MARKET_STATE.get(sym)
            if st and st.get("last_price"):
                last_price = st["last_price"]
                daily_change_pct = st["daily_change_pct"]
            else:
                last_bar = df.iloc[-1]
                last_price = float(last_bar["Close"])
                prev_price = float(df.iloc[-2]["Close"])
                daily_change_pct = round(((last_price - prev_price) / prev_price) * 100, 2)

            results.append({
                "symbol": sym,
                "code": item["code"],
                "name": item["name"],
                "category": item.get("category", "Equities"),
                "sector": item["sector"],
                "is_etf": item.get("is_etf", False),
                "last_price": round(last_price, 3),
                "daily_change_pct": daily_change_pct,
                "ichimoku_score": ichi_score,
                "cloud_state": ichi_meta.get("cloud_state", ""),
                "volume_z_score": vol_meta.get("volume_z_score", 0.0),
                "institutional_acc": vol_meta.get("institutional_accumulation", False),
                "volatility_squeeze": vol_meta.get("volatility_squeeze", False),
                "atr_pct": vol_meta.get("atr_pct", 0.0),
                "bb_bandwidth": vol_meta.get("bb_bandwidth", 0.0),
                "mrs": rs_meta.get("mrs", 0.0),
                "alpha_10d": rs_meta.get("alpha_10d", 0.0),
                "outperforming": rs_meta.get("outperforming", False),
                "cmf_21": flow_meta.get("cmf_21", 0.0),
                "flow_bias": flow_meta.get("flow_bias", "NEUTRAL"),
                "avwap_tourn": flow_meta.get("avwap_tournament", last_price),
                "bursa_page": item.get("bursa_page", "")
            })
        except Exception as e:
            logger.error(f"Error scanning {sym}: {e}")

    # Sort results by Ichimoku score descending, then by volume Z-score
    results.sort(key=lambda x: (x["ichimoku_score"], x["volume_z_score"]), reverse=True)
    
    await ws_hub.broadcast_log(f"Factor matrix updated: {len(results)} counters processed.", "INFO", "SCAN")

    return {
        "count": len(results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ranked_matrix": results
    }

async def _get_chart_data(identifier: str, timeframe: Optional[str] = None, interval: Optional[str] = None) -> Dict[str, Any]:
    """
    Format OHLCV and overlay indicators across 1h, 4h, and 1d timeframes for Lightweight Charts.
    Emits integer Unix epoch seconds for all candlestick and indicator timestamps.
    """
    tf = (timeframe or interval or "1d").lower()
    if tf not in ("1h", "4h", "1d"):
        tf = "1d"
    meta = get_ticker_meta(identifier)
    sym = meta["symbol"]
    
    df = data_loader.fetch_ohlcv(sym, timeframe=tf)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No market data for {sym} ({tf})")

    # Run technical indicators on sliding window
    ichi_df = calculate_ichimoku(df)
    ichi_series = build_ichimoku_chart_series(df, ichi_df, interval=tf)
    vol_df = calculate_volume_volatility(df)
    flow_df = calculate_institutional_flows(df)

    candles = []
    volume_bars = []
    avwap_series = []
    cmf_series = []

    for idx, row in df.iterrows():
        t_val = int(idx.timestamp())

        o = float(row["Open"])
        h = float(row["High"])
        l = float(row["Low"])
        c = float(row["Close"])
        v = float(row["Volume"])

        candles.append({"time": t_val, "open": o, "high": h, "low": l, "close": c, "volume": v})

        # Check volume Z-score
        z = float(vol_df.loc[idx, "volume_z_score"]) if idx in vol_df.index and pd.notna(vol_df.loc[idx, "volume_z_score"]) else 0.0
        
        # Color coding: Green for up, Red for down. Bright yellow for institutional accumulation Z >= 2.0
        if z >= 2.0:
            v_color = "#ffd700"  # Bright Gold / Institutional Accumulation
        elif c >= o:
            v_color = "rgba(0, 255, 170, 0.6)"  # Neon Green
        else:
            v_color = "rgba(255, 0, 85, 0.6)"   # Neon Pink/Red

        volume_bars.append({"time": t_val, "value": v, "color": v_color})

        if idx in flow_df.index:
            av = flow_df.loc[idx, "avwap_tournament"]
            if pd.notna(av):
                avwap_series.append({"time": t_val, "value": round(float(av), 3)})
            
            cm = flow_df.loc[idx, "cmf_21"]
            if pd.notna(cm):
                cmf_series.append({"time": t_val, "value": round(float(cm), 3)})

    # Current bar factor snapshot
    score, ichi_m = score_ichimoku_momentum(ichi_df)
    vol_m = get_latest_volume_metrics(vol_df)
    flow_m = get_latest_flow_metrics(flow_df)

    # Use live quote from LIVE_MARKET_STATE or MARKET_STATE if available
    st = LIVE_MARKET_STATE.get(sym) or MARKET_STATE.get(sym)
    candle_close = candles[-1]["close"] if candles else 0.0
    if st and st.get("price") and st["price"] > 1.0:
        last_price = st["price"]
    elif st and st.get("last_price") and st["last_price"] > 1.0:
        last_price = st["last_price"]
    else:
        last_price = candle_close

    return {
        "ticker": sym,
        "symbol": sym,
        "timeframe": tf,
        "interval": tf,
        "name": meta["name"],
        "full_name": meta["full_name"],
        "candles": candles,
        "volume": volume_bars,
        "tenkan": ichi_series["tenkan"],
        "kijun": ichi_series["kijun"],
        "chikou": ichi_series["chikou"],
        "span_a": ichi_series["span_a"],
        "span_b": ichi_series["span_b"],
        "avwap": avwap_series,
        "cmf": cmf_series,
        "current_score": score,
        "current_metrics": {
            "last_price": last_price,
            "tenkan": ichi_series["tenkan"][-1]["value"] if ichi_series["tenkan"] else 0.0,
            "kijun": ichi_series["kijun"][-1]["value"] if ichi_series["kijun"] else 0.0,
            "avwap": avwap_series[-1]["value"] if avwap_series else 0.0,
            "cmf_21": flow_m.get("cmf_21", 0.0),
            "volume_z_score": vol_m.get("volume_z_score", 0.0),
            "volatility_squeeze": vol_m.get("volatility_squeeze", False),
            "cloud_state": ichi_m.get("cloud_state", "")
        }
    }

@app.get("/api/chart/{ticker}")
async def get_chart_endpoint(
    ticker: str, 
    timeframe: Optional[str] = Query(None),
    interval: Optional[str] = Query(None)
):
    """
    Multi-Timeframe Chart Data Endpoint (1h, 4h, 1d) with forward-projected Ichimoku Kumo and indicators.
    """
    tf = timeframe or interval or "1d"
    return await _get_chart_data(ticker, tf)

@app.get("/api/ohlcv/{identifier}")
async def get_ohlcv_data(
    identifier: str, 
    timeframe: Optional[str] = Query(None),
    interval: Optional[str] = Query(None)
):
    """
    Legacy and direct OHLCV compatibility endpoint with timeframe support.
    """
    tf = timeframe or interval or "1d"
    return await _get_chart_data(identifier, tf)

@app.get("/api/analyze/{identifier}")
async def analyze_quarterly_report(identifier: str):
    """
    Downloads/loads latest Bursa quarterly report PDF for identifier.
    Runs Deterministic Financial Audit and Qualitative MD&A LLM Audit.
    Emits typed FUNDAMENTAL_UPDATE payload across WebSocket.
    """
    meta = get_ticker_meta(identifier)
    code = meta["code"]
    sym = meta["symbol"]
    is_etf = meta.get("is_etf", False) or sym == "0828EA.KL"

    await ws_hub.broadcast_log(f"Starting A4 PDF & Fundamental Audit for {meta['name']} ({code})...", "INFO", "AUDITOR")

    if is_etf:
        audit_results = fundamental_auditor.audit_report(None, sym)
        llm_results = llm_agent.audit_mda("", sym, audit_results)
        pdf_name = f"{meta['name']}_{code}_ETF_Vault.pdf"
        tables_count = 1
    else:
        pdf_path = bursa_scraper.get_or_generate_report_pdf(code)
        parsed = pdf_extractor.parse_pdf(pdf_path)
        audit_results = fundamental_auditor.audit_report(parsed, code)
        mda_text = parsed["sections"].get("mda_operational", "")
        llm_results = llm_agent.audit_mda(mda_text, code, audit_results)
        pdf_name = parsed["pdf_name"]
        tables_count = len(parsed["tables"])

    m = audit_results["metrics"]

    # Construct typed FUNDAMENTAL_UPDATE payload as per Mandates 1, 2, and 4
    if is_etf:
        gold_st = MACRO_STATE.get("GC=F", {})
        tnx_st = MACRO_STATE.get("^TNX", {})
        brent_st = MACRO_STATE.get("BZ=F", {})
        myr_st = MACRO_STATE.get("MYR=X", {})

        macro_telemetry = {
            "card_1": {
                "header": "COMEX GOLD (USD/oz)",
                "val": m.get("macro_card_1_val") or gold_st.get("formatted_price", "$4,241.40"),
                "badge": m.get("macro_card_1_badge") or gold_st.get("badge", "+1.48% (99.8% PM Fix Corr)"),
                "class": m.get("macro_card_1_class") or gold_st.get("badge_class", "sac-badge-pass")
            },
            "card_2": {
                "header": "US 10Y BOND YIELD",
                "val": m.get("macro_card_2_val") or tnx_st.get("formatted_price", "5.21%"),
                "badge": m.get("macro_card_2_badge") or tnx_st.get("badge", "Bullion Carry Cost (Restrictive)"),
                "class": m.get("macro_card_2_class") or tnx_st.get("badge_class", "sac-badge-pass")
            },
            "card_3": {
                "header": "BRENT CRUDE OIL",
                "val": m.get("macro_card_3_val") or brent_st.get("formatted_price", "$97.76/bbl"),
                "badge": m.get("macro_card_3_badge") or brent_st.get("badge", "Headline Inflation & Risk Premium"),
                "class": m.get("macro_card_3_class") or brent_st.get("badge_class", "sac-badge-warn")
            },
            "card_4": {
                "header": "USD / MYR FX RATE",
                "val": m.get("macro_card_4_val") or myr_st.get("formatted_price", "RM 4.0787"),
                "badge": m.get("macro_card_4_badge") or myr_st.get("badge", "Unhedged FX Drag / Tailwind"),
                "class": m.get("macro_card_4_class") or myr_st.get("badge_class", "sac-badge-pass")
            }
        }

        bullion_pricing = {
            "nav_per_gram": m.get("nav_per_gram", 555.78),
            "indicative_nav": m.get("indicative_nav", 5.629),
            "nav_formatted": m.get("nav_formatted", "RM 5.629"),
            "spread_pct": m.get("spread_pct", -6.20),
            "spread_formatted": m.get("spread_formatted", "-6.20%"),
            "arbitrage_status": m.get("arbitrage_status", "DISCOUNT (Arbitrage Entry)"),
            "arbitrage_recommendation": m.get("arbitrage_recommendation", "Bursa units trading below physical bullion NAV."),
            "bursa_price": m.get("bursa_price", 5.28)
        }

        fundamental_payload = {
            "event": "FUNDAMENTAL_UPDATE",
            "ticker": sym,
            "name": meta["name"],
            "sector": audit_results.get("sector", "Exchange Traded Funds"),
            "is_etf": True,
            "macro_mode": True,
            "etf_structure": audit_results.get("etf_structure", {}),
            "macro_telemetry": macro_telemetry,
            "bullion_pricing": bullion_pricing,
            "metrics": m,
            "narrative": {
                "point1_title": llm_results.get("point1_title", "1. Theoretical NAV & Pricing Spread (Arbitrage Check)"),
                "point1_body": llm_results.get("point1_body", llm_results.get("commercial_drivers", "")),
                "point2_title": llm_results.get("point2_title", "2. Real Yields & Opportunity Cost Transmission"),
                "point2_body": llm_results.get("point2_body", llm_results.get("cash_deployment", "")),
                "point3_title": llm_results.get("point3_title", "3. Energy & Geopolitical Risk Premium"),
                "point3_body": llm_results.get("point3_body", llm_results.get("working_capital", "")),
                "point4_title": llm_results.get("point4_title", "4. USD/MYR Currency Translation Impact"),
                "point4_body": llm_results.get("point4_body", llm_results.get("forward_catalysts", "")),
                "point5_title": llm_results.get("point5_title", "5. Tournament Utility & Shariah Vault Governance"),
                "point5_body": llm_results.get("point5_body", llm_results.get("shariah_governance", "")),
                "commercial_drivers": llm_results["commercial_drivers"],
                "cash_deployment": llm_results["cash_deployment"],
                "working_capital": llm_results["working_capital"],
                "forward_catalysts": llm_results["forward_catalysts"],
                "shariah_governance": llm_results["shariah_governance"]
            }
        }
    else:
        fundamental_payload = {
            "event": "FUNDAMENTAL_UPDATE",
            "ticker": sym,
            "name": meta["name"],
            "sector": audit_results.get("sector", meta.get("sector", "Equities")),
            "is_etf": False,
            "metrics": {
                "free_cash_flow": m.get("free_cash_flow") or m.get("fcf_formatted", "--"),
                "earnings_quality": m.get("earnings_quality") or m.get("cfo_ebitda_ratio", 0.0),
                "cash_ratio_pct": m.get("cash_ratio_pct", 0.0),
                "debt_ratio_pct": m.get("debt_ratio_pct", 0.0),
                "shariah_compliant": m.get("shariah_compliant", True)
            },
            "narrative": {
                "commercial_drivers": llm_results["commercial_drivers"],
                "cash_deployment": llm_results["cash_deployment"],
                "working_capital": llm_results["working_capital"],
                "forward_catalysts": llm_results["forward_catalysts"],
                "shariah_governance": llm_results["shariah_governance"]
            }
        }

    # Broadcast structured FUNDAMENTAL_UPDATE across WebSocket displays
    await ws_hub.broadcast_fundamental_update(fundamental_payload)

    # Legacy AUDIT_RESULT event broadcast for backwards compatibility
    await ws_hub.broadcast({
        "event": "AUDIT_RESULT",
        "ticker": sym,
        "audit": audit_results,
        "mda_review": llm_results,
        "payload": fundamental_payload
    })
    await ws_hub.broadcast_log(f"Audit completed: {meta['name']} Shariah Verdict: {audit_results['shariah_verdict']}", "INFO", "AUDITOR")

    return {
        "success": True,
        "meta": meta,
        "pdf_name": pdf_name,
        "audit": audit_results,
        "llm_review": llm_results,
        "payload": fundamental_payload,
        "tables_extracted": tables_count
    }

@app.post("/api/order")
async def execute_order(payload: OrderPayload):
    """Simulates fractional order execution (BUY or SELL) by units or RM amount."""
    meta = get_ticker_meta(payload.ticker)
    
    # Fetch live price from MARKET_STATE or latest bar
    st = MARKET_STATE.get(meta["symbol"])
    if st and st.get("last_price"):
        curr_price = st["last_price"]
    else:
        df = data_loader.fetch_ohlcv(meta["symbol"])
        curr_price = float(df.iloc[-1]["Close"]) if not df.empty else 4.39

    result = portfolio.execute_order(
        action=payload.action,
        identifier=meta["symbol"],
        units=payload.units,
        amount_myr=payload.amount_myr,
        price_override=curr_price,
        notes=payload.notes
    )

    if result.get("success"):
        # Broadcast PORTFOLIO_UPDATE and ORDER_EXECUTE across displays
        await ws_hub.broadcast({
            "event": "PORTFOLIO_UPDATE",
            "trade": result["trade"],
            "rubric": result["rubric"],
            "positions": list(portfolio.positions.values())
        })
        await ws_hub.broadcast({
            "event": "ORDER_EXECUTE",
            "trade": result["trade"],
            "rubric": result["rubric"],
            "positions": list(portfolio.positions.values())
        })
        await ws_hub.broadcast_log(
            f"ORDER {payload.action.upper()}: {result['trade']['units']} units of {meta['name']} at RM {result['trade']['price']:.3f} (RM {result['trade']['total_myr']:.2f})",
            "SUCCESS",
            "ORDER"
        )
    else:
        await ws_hub.broadcast_log(f"ORDER REJECTED: {result.get('error')}", "WARNING", "ORDER")

    return result

@app.get("/api/positions")
async def get_positions():
    """Returns current active positions, fractional holdings, and cash balance."""
    return {
        "positions": list(portfolio.positions.values()),
        "cash": round(portfolio.cash, 2),
        "trade_count": len(portfolio.trade_log)
    }

@app.get("/api/rubric")
async def get_rubric():
    """Returns competition rubric status (i-ETF Trades, Fractional Trades, Total Trades)."""
    return portfolio.get_rubric_metrics()

@app.get("/api/stop_audit")
async def run_stop_audit():
    """Audit open positions for daily Kijun-sen trailing stop and ATR chandelier breaches."""
    symbols = list(portfolio.positions.keys())
    data_map = {}
    for s in symbols:
        data_map[s] = data_loader.fetch_ohlcv(s)

    alerts = portfolio.run_stop_audit(data_map)

    await ws_hub.broadcast({
        "event": "STOP_AUDIT",
        "alerts": alerts,
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    
    if alerts:
        await ws_hub.broadcast_log(f"STOP AUDIT ALERT: {len(alerts)} positions breached Kijun-sen/ATR stop!", "WARNING", "STOP AUDIT")
    else:
        await ws_hub.broadcast_log("STOP AUDIT: All open positions holding comfortably above Kijun-sen.", "INFO", "STOP AUDIT")

    return {
        "status": "COMPLETED",
        "alert_count": len(alerts),
        "alerts": alerts
    }

@app.get("/api/backtest/{identifier}")
async def run_sprint_backtest(identifier: str):
    """Executes 25-trading-day tournament sprint backtest on historical OHLCV data."""
    meta = get_ticker_meta(identifier)
    df = data_loader.fetch_ohlcv(meta["symbol"])
    res = rolling_sprint_simulator.run_sprint_backtest(df, meta["symbol"])
    return res

@app.post("/api/select")
async def select_ticker_api(payload: Dict[str, str]):
    """REST endpoint to trigger synchronized ticker selection across screens."""
    ticker = payload.get("ticker", "5211.KL")
    meta = get_ticker_meta(ticker)
    await ws_hub.broadcast_ticker_select(meta["symbol"], meta["name"])
    asyncio.create_task(analyze_quarterly_report(meta["symbol"]))
    return {"success": True, "ticker": meta["symbol"], "name": meta["name"]}
