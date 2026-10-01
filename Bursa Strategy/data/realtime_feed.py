"""
Bursa Strategy - Direct Real-Time Bursa Data Pipeline
Scrapes and streams live, unadjusted nominal market quotes directly from local Malaysian bourse sources.
Includes Primary Pipe (Bursa Malaysia API) with robust Secondary Fallbacks (KLSE Screener & Google Finance).
Decoupled async worker running on a 3 to 5 second interval maintaining centralized LIVE_MARKET_STATE.
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import httpx

from config.settings import TICK_POLL_INTERVAL_SECONDS
from config.universe import ALL_SYMBOLS, UNIVERSE_DATA, get_ticker_meta

logger = logging.getLogger("bursa.data.realtime")

# Centralized In-Memory Single Source of Truth
# {symbol: {"price": float, "change": float, "change_pct": float, "volume": int, "high": float, "low": float, "timestamp": str}}
LIVE_MARKET_STATE: Dict[str, Dict[str, Any]] = {}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BURSA_API_HEADERS = {
    **DEFAULT_HEADERS,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.bursamalaysia.com/market_information/equities_prices",
    "Accept": "application/json, text/javascript, */*; q=0.01"
}


class BursaRealtimeFeed:
    """Direct real-time market data ingestion pipeline for Bursa Malaysia."""

    def __init__(self, poll_interval: int = TICK_POLL_INTERVAL_SECONDS):
        self.poll_interval = poll_interval
        self._is_polling = False
        self._polling_task: Optional[asyncio.Task] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Pre-seed initial state for all 23 whitelisted counters
        self._initialize_state()

    def _initialize_state(self):
        """Seed initial state for all 23 whitelisted counters."""
        now_str = datetime.now().strftime("%H:%M:%S")
        for sym in ALL_SYMBOLS:
            meta = get_ticker_meta(sym)
            if sym not in LIVE_MARKET_STATE:
                LIVE_MARKET_STATE[sym] = {
                    "ticker_symbol": sym,
                    "symbol": sym,
                    "code": meta["code"],
                    "name": meta["name"],
                    "sector": meta["sector"],
                    "is_etf": meta.get("is_etf", False),
                    "price": 0.0,
                    "last_price": 0.0,
                    "change": 0.0,
                    "change_pct": 0.0,
                    "volume": 0,
                    "high": 0.0,
                    "low": 0.0,
                    "timestamp": now_str,
                    "source": "INIT"
                }

    async def get_client(self) -> httpx.AsyncClient:
        """Reuse or initialize async HTTP client with connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
                timeout=httpx.Timeout(connect=4.0, read=4.0, write=4.0, pool=5.0),
                limits=httpx.Limits(max_connections=30, max_keepalive_connections=25)
            )
        return self._http_client

    async def close(self):
        """Close HTTP client session."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def fetch_primary_bursa_api(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Primary Pipe: Query official Bursa Malaysia Equities API endpoint.
        https://www.bursamalaysia.com/api/v1/market_information/equities_prices?sort_by=short_name&sort_dir=asc&per_page=50&page=1
        Extract last_done_price, change, change_percentage, buy_volume, sell_volume, and high/low.
        """
        url = "https://www.bursamalaysia.com/api/v1/market_information/equities_prices?sort_by=short_name&sort_dir=asc&per_page=50&page=1"
        try:
            client = await self.get_client()
            resp = await client.get(url, headers=BURSA_API_HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                results = {}
                for item in items:
                    stock_code = str(item.get("stock_code", "")).strip()
                    # Match to our 23 tickers
                    sym = f"{stock_code}.KL"
                    if sym in ALL_SYMBOLS:
                        price = float(item.get("last_done_price") or item.get("last_price") or 0.0)
                        if price <= 0:
                            continue
                        chg = float(item.get("change") or 0.0)
                        chg_pct = float(item.get("change_percentage") or 0.0)
                        vol = int(item.get("volume") or item.get("buy_volume", 0) + item.get("sell_volume", 0))
                        high = float(item.get("high") or price)
                        low = float(item.get("low") or price)
                        if high <= 0:
                            high = price
                        if low <= 0:
                            low = price
                        
                        results[sym] = {
                            "ticker_symbol": sym,
                            "symbol": sym,
                            "code": stock_code,
                            "name": get_ticker_meta(sym)["name"],
                            "price": round(price, 3),
                            "last_price": round(price, 3),
                            "change": round(chg, 3),
                            "change_pct": round(chg_pct, 2),
                            "volume": vol,
                            "high": round(high, 3),
                            "low": round(low, 3),
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "source": "BURSA_API"
                        }
                if len(results) > 0:
                    return results
        except Exception as e:
            logger.debug(f"Primary Bursa API query bypassed: {e}")
        return None

    async def fetch_ticker_quote_secondary(self, symbol: str) -> Dict[str, Any]:
        """
        Secondary Pipe (Fallback):
        Scrapes real-time, unadjusted nominal market prices directly from KLSE Screener / Google Finance.
        Returns live price, change, change_pct, volume, high, and low.
        """
        meta = get_ticker_meta(symbol)
        code = meta["code"]
        name = meta["name"]
        now_str = datetime.now().strftime("%H:%M:%S")

        # 1. KLSE Screener Direct Parser
        url = f"https://www.klsescreener.com/v2/stocks/view/{code}"
        try:
            client = await self.get_client()
            r = await client.get(url)
            if r.status_code == 200:
                # Nominal unadjusted price
                m_p = re.search(r'id="price"[^>]*data-value="([0-9.,]+)"', r.text)
                if not m_p:
                    m_p = re.search(r'id="price"[^>]*>([0-9.,]+)<', r.text)
                
                if m_p:
                    price = float(m_p.group(1).replace(",", ""))

                    # Change and Change % from <span id="priceDiff">-0.150 (-3.3%)</span>
                    m_diff = re.search(r'id="priceDiff"[^>]*>([+-]?[0-9.,]+)\s*\(([+-]?[0-9.,]+)%?\)<', r.text)
                    if m_diff:
                        chg = float(m_diff.group(1).replace(",", ""))
                        chg_pct = float(m_diff.group(2).replace(",", ""))
                    else:
                        chg = 0.0
                        chg_pct = 0.0

                    # High, Low, Volume from table
                    m_h = re.search(r'High</td>\s*<td[^>]*>([0-9.,]+)</td>', r.text)
                    m_l = re.search(r'Low</td>\s*<td[^>]*>([0-9.,]+)</td>', r.text)
                    m_v = re.search(r'Volume</td>\s*<td[^>]*>([0-9.,]+)</td>', r.text)

                    high = float(m_h.group(1).replace(",", "")) if m_h else price
                    low = float(m_l.group(1).replace(",", "")) if m_l else price
                    vol = int(m_v.group(1).replace(",", "")) if m_v else 0
                    if high <= 0:
                        high = price
                    if low <= 0:
                        low = price

                    if price > 0:
                        return {
                            "ticker_symbol": symbol,
                            "symbol": symbol,
                            "code": code,
                            "name": name,
                            "price": round(price, 3),
                            "last_price": round(price, 3),
                            "change": round(chg, 3),
                            "change_pct": round(chg_pct, 2),
                            "volume": vol,
                            "high": round(high, 3),
                            "low": round(low, 3),
                            "timestamp": now_str,
                            "source": "KLSE_SCREENER"
                        }
        except Exception as e:
            logger.debug(f"Secondary quote lookup for {symbol} ({code}) fell back: {e}")

        # Retain last known state or initialized state
        current = LIVE_MARKET_STATE.get(symbol, {})
        if current and current.get("price", 0) > 0:
            return current

        return {
            "ticker_symbol": symbol,
            "symbol": symbol,
            "code": code,
            "name": name,
            "price": 1.0,
            "last_price": 1.0,
            "change": 0.0,
            "change_pct": 0.0,
            "volume": 0,
            "high": 1.0,
            "low": 1.0,
            "timestamp": now_str,
            "source": "FALLBACK"
        }

    async def fetch_universe_quotes(self) -> List[Dict[str, Any]]:
        """
        Poll all 23 whitelisted counters concurrently.
        Attempts Primary Pipe (Bursa API) first, falling back to Secondary Pipe.
        """
        # Try Primary Pipe
        primary_results = await self.fetch_primary_bursa_api()
        if primary_results and len(primary_results) >= len(ALL_SYMBOLS):
            for sym, quote in primary_results.items():
                if quote.get("price", 0) > 0:
                    LIVE_MARKET_STATE[sym] = quote
            return [q for q in LIVE_MARKET_STATE.values() if q.get("price", 0) > 0]

        # Fallback to Secondary Pipe concurrent fetching
        tasks = [self.fetch_ticker_quote_secondary(sym) for sym in ALL_SYMBOLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ticks = []
        for r in results:
            if isinstance(r, dict) and "symbol" in r and r.get("price", 0) > 0:
                sym = r["symbol"]
                LIVE_MARKET_STATE[sym] = r
                ticks.append(r)

        return ticks

    async def start_realtime_polling(
        self, 
        ws_broadcast_callback: Optional[Callable] = None, 
        on_tick_update: Optional[Callable] = None,
        interval_seconds: int = TICK_POLL_INTERVAL_SECONDS
    ):
        """
        Asynchronous background task polling live nominal quotes on a 3 to 5 second interval.
        Decoupled from WebSocket event loop so network delays never block UI rendering.
        """
        if self._is_polling:
            return
        self._is_polling = True
        logger.info(f"Direct Real-Time Bursa Data Pipeline active (interval: {interval_seconds}s)...")

        # Initial fetch immediately
        try:
            ticks = await self.fetch_universe_quotes()
            if on_tick_update:
                on_tick_update(LIVE_MARKET_STATE)
            if ws_broadcast_callback and ticks:
                await ws_broadcast_callback({
                    "event": "TICK_STREAM",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "ticks": ticks
                })
        except Exception as e:
            logger.warning(f"Error on initial live quote fetch: {e}")

        # Continuous polling loop
        while self._is_polling:
            try:
                ticks = await self.fetch_universe_quotes()

                # Sync with data_loader / external consumer
                if on_tick_update:
                    on_tick_update(LIVE_MARKET_STATE)

                # Broadcast live tick stream over WebSocket with explicit ticker strings
                if ws_broadcast_callback and ticks:
                    await ws_broadcast_callback({
                        "event": "TICK_STREAM",
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "ticks": ticks
                    })

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in realtime feed loop: {e}")

            await asyncio.sleep(interval_seconds)

    def stop_polling(self):
        """Stop background poller gracefully."""
        self._is_polling = False
        logger.info("Real-time Bursa feed stopped.")


# Global singleton
realtime_feed = BursaRealtimeFeed()
