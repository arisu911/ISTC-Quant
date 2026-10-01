"""
Bursa Strategy Quantitative Data Ingestion & Live Market State Engine
Vectorized offline historical OHLCV extraction with Snappy-compressed Parquet caching on SSD.
Enforces auto_adjust=False to prevent nominal price deflation from dividend adjustments.
Integrates directly with data.realtime_feed for live, nominal Bursa prices (Single Source of Truth).
"""

import os
import time
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
import yfinance as yf

from config.settings import (
    CACHE_DIR,
    BENCHMARK_PRIMARY,
    BENCHMARK_SHARIAH,
    MAX_BARS_WINDOW,
    TICK_POLL_INTERVAL_SECONDS
)
from config.universe import ALL_SYMBOLS, UNIVERSE_DATA, get_ticker_meta
from data.realtime_feed import LIVE_MARKET_STATE, realtime_feed
from analyzer.macro_audit import MACRO_STATE, macro_auditor

logger = logging.getLogger("bursa.data.loader")

# In-Memory Single Source of Truth
# Holds latest tick, daily metrics, and 250-bar sliding window DataFrame
MARKET_STATE: Dict[str, Dict[str, Any]] = {}

# Multi-timeframe historical cache keyed by f"{symbol}_{interval}"
MARKET_CACHE: Dict[str, pd.DataFrame] = {}

def build_4h_bars(df_1h: pd.DataFrame) -> pd.DataFrame:
    """
    Synthesize 4H bars directly from 1H DataFrame using Pandas resampling.
    Aligns to standard Bursa sessions with 4h offset.
    """
    if df_1h.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df_4h = df_1h.resample('4h', offset='1h').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna(subset=['Close'])
    return df_4h

class MarketDataLoader:
    """Manages downloading, caching, and serving multi-timeframe (1h, 4h, 1d) OHLCV datasets and live quotes."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, pd.DataFrame] = {}
        self.market_cache = MARKET_CACHE
        self._is_polling = False
        self._polling_task: Optional[asyncio.Task] = None

    def _get_cache_path(self, symbol: str, interval: str = "1d") -> Path:
        """Sanitize symbol for filesystem filename with timeframe suffix."""
        safe_sym = symbol.replace("^", "_").replace(".", "_").replace("/", "_")
        if interval == "1d":
            p_old = self.cache_dir / f"{safe_sym}.parquet"
            p_new = self.cache_dir / f"{safe_sym}_1d.parquet"
            if p_old.exists() and not p_new.exists():
                return p_old
            return p_new
        return self.cache_dir / f"{safe_sym}_{interval}.parquet"

    def save_to_cache(self, symbol: str, df: pd.DataFrame, interval: str = "1d") -> None:
        """Write to SSD with Snappy-compressed Parquet (on shutdown or bar close)."""
        df = self._sanitize_ohlcv(df)
        if df.empty:
            return
        p_path = self._get_cache_path(symbol, interval)
        max_w = 5500 if interval in ("1h", "4h") else MAX_BARS_WINDOW
        try:
            trimmed_df = df.tail(max_w)
            trimmed_df.to_parquet(p_path, compression="snappy")
        except Exception as e:
            logger.warning(f"Parquet save failed for {symbol} {interval} ({e}), falling back to CSV.")
            csv_path = self.cache_dir / f"{symbol.replace('.', '_')}_{interval}.csv"
            df.tail(max_w).to_csv(csv_path)

    def _sanitize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Strict OHLCV Sanitization:
        1. Purge any row with zero, negative, or NaN prices in Open, High, Low, Close.
        2. Drop incomplete / empty current-day pre-market bar if volume is 0 or trading has not commenced.
        3. Enforce monotonic ascending index with deduplication.
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        df = df.copy()

        # Coerce numeric columns
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

        # 1. Purge any row with zero, negative, or NaN prices
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        df = df[(df["Open"] > 0) & (df["High"] > 0) & (df["Low"] > 0) & (df["Close"] > 0)]

        if df.empty:
            return df

        # 2. Drop current incomplete bar if volume is 0 or trading has not commenced (market closed / pre-market)
        try:
            last_dt = df.index[-1]
            last_date = last_dt.date() if hasattr(last_dt, "date") else pd.to_datetime(last_dt).date()
            now_date = datetime.now().date()
            if last_date == now_date:
                last_vol = df["Volume"].iloc[-1]
                last_close = df["Close"].iloc[-1]
                if last_vol <= 0 or last_close <= 0:
                    df = df.iloc[:-1]
        except Exception as e:
            logger.debug(f"Pre-market bar inspection skipped: {e}")

        if df.empty:
            return df

        # 3. Enforce monotonic Unix timestamps and deduplicate
        df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()

        return df

    def load_from_cache(self, symbol: str, interval: str = "1d") -> Optional[pd.DataFrame]:
        """Load DataFrame from Snappy-compressed Parquet cache and apply sanitization."""
        p_path = self._get_cache_path(symbol, interval)
        if p_path.exists():
            try:
                df = pd.read_parquet(p_path)
                df = self._sanitize_ohlcv(df)
                if df.empty:
                    return None
                max_w = 5500 if interval in ("1h", "4h") else MAX_BARS_WINDOW
                return df.tail(max_w)
            except Exception as e:
                logger.warning(f"Error reading Parquet cache for {symbol} ({interval}): {e}")
        return None

    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: Optional[str] = None,
        period: Optional[str] = None, 
        interval: Optional[str] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol using yfinance with disk and memory caching.
        Supports multi-timeframe architecture: '1d', '1h', '4h'.
        - 1d: yf.download(symbol, period="1y", interval="1d", auto_adjust=False)
        - 1h: yf.download(symbol, period="730d", interval="1h", auto_adjust=False) cleaned to Bursa sessions
        - 4h: Resamples 730d 1h DataFrame to 4-hour bars (hundreds of bars spanning multiple quarters)
        Enforces auto_adjust=False on all historical downloads.
        Retains all historical data in an in-memory cache keyed by symbol and timeframe:
        MARKET_CACHE[f"{symbol}_{interval}"].
        Appends the live tick from LIVE_MARKET_STATE as the active evolving candle.
        """
        resolved_tf = (timeframe or interval or "1d").lower()
        if resolved_tf not in ("1d", "1h", "4h"):
            resolved_tf = "1d"
        interval = resolved_tf
        cache_key = f"{symbol}_{interval}"
        min_expected_bars = 500 if interval == "1h" else (200 if interval == "4h" else 30)

        # -------------------------------------------------------------
        # 1. Check in-memory MARKET_CACHE
        # -------------------------------------------------------------
        if not force_refresh and cache_key in MARKET_CACHE:
            cached_df = MARKET_CACHE[cache_key]
            if cached_df is not None and not cached_df.empty and len(cached_df) >= min_expected_bars:
                return self._append_live_candle(symbol, cached_df.copy(), interval)

        # -------------------------------------------------------------
        # 2. Check Daily Market State legacy cache if 1d
        # -------------------------------------------------------------
        if not force_refresh and interval == "1d" and symbol in MARKET_STATE:
            state_df = MARKET_STATE[symbol].get("ohlcv_df")
            if state_df is not None and not state_df.empty:
                MARKET_CACHE[cache_key] = state_df
                return self._append_live_candle(symbol, state_df.copy(), interval)

        # -------------------------------------------------------------
        # 3. Check SSD Parquet Disk Cache
        # -------------------------------------------------------------
        if not force_refresh:
            disk_df = self.load_from_cache(symbol, interval)
            if disk_df is not None and not disk_df.empty and len(disk_df) >= min_expected_bars:
                MARKET_CACHE[cache_key] = disk_df
                if interval == "1d":
                    self._memory_cache[symbol] = disk_df
                    self._update_market_state_from_df(symbol, disk_df)
                return self._append_live_candle(symbol, disk_df.copy(), interval)

        # -------------------------------------------------------------
        # 4. Synthesize 4H bars from 1H bars via Pandas resampling
        # -------------------------------------------------------------
        if interval == "4h":
            logger.info(f"Synthesizing 4H bars for {symbol} from 1H data pipeline (730d)...")
            df_1h = self.fetch_ohlcv(symbol, timeframe="1h", period="730d", force_refresh=force_refresh)
            if not df_1h.empty:
                df_4h = build_4h_bars(df_1h)
                df_4h = self._sanitize_ohlcv(df_4h)
                if not df_4h.empty:
                    df_4h = df_4h.tail(2500)
                    self.save_to_cache(symbol, df_4h, "4h")
                    MARKET_CACHE[cache_key] = df_4h
                    return self._append_live_candle(symbol, df_4h.copy(), "4h")
            # Fallback to empty if 1H unavailable
            return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

        # -------------------------------------------------------------
        # 5. Fetch offline historical from yfinance (1h or 1d)
        # -------------------------------------------------------------
        fetch_period = period if period is not None else ("730d" if interval == "1h" else "1y")
        logger.info(f"Ingesting offline historical {interval} bars for {symbol} ({fetch_period})...")

        try:
            if interval == "1h":
                # Maximize 1H historical depth to 730 days (maximum limit on Yahoo Finance = 2 full years)
                df = yf.download(
                    symbol,
                    period=fetch_period,
                    interval="1h",
                    auto_adjust=False,
                    progress=False
                )
                if df.empty:
                    ticker = yf.Ticker(symbol)
                    df = ticker.history(period=fetch_period, interval="1h", auto_adjust=False)
            else:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=fetch_period, interval=interval, auto_adjust=False)
                if df.empty:
                    df = yf.download(symbol, period=fetch_period, interval=interval, progress=False, auto_adjust=False)

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            if not df.empty:
                required_cols = ["Open", "High", "Low", "Close", "Volume"]
                present_cols = [c for c in required_cols if c in df.columns]
                df = df[present_cols].copy()

                df.index = pd.to_datetime(df.index)

                # Filter and normalize based on timeframe
                if interval == "1h":
                    # Normalize timezone to Asia/Kuala_Lumpur
                    if df.index.tz is not None:
                        df.index = df.index.tz_convert("Asia/Kuala_Lumpur")
                    else:
                        df.index = df.index.tz_localize("Asia/Kuala_Lumpur")

                    # Filter to standard Bursa Malaysia trading sessions (09:00–12:30, 14:30–17:00 MYT)
                    # Hours 9, 10, 11, 12, 14, 15, 16 on Monday-Friday (weekday < 5)
                    session_hours = {9, 10, 11, 12, 14, 15, 16}
                    df = df[(df.index.weekday < 5) & (df.index.hour.isin(session_hours))].copy()
                else:
                    # 1d timeframe: strip timezone for clean calendar day indexing
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)

                df["Volume"] = df["Volume"].fillna(0)
                # Strict OHLCV Sanitization: drop NaN, zero/negative prices, empty pre-market bars, enforce monotonic
                df = self._sanitize_ohlcv(df)
                if df.empty:
                    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
                max_w = 5500 if interval in ("1h", "4h") else MAX_BARS_WINDOW
                df = df.tail(max_w)

                self.save_to_cache(symbol, df, interval)
                MARKET_CACHE[cache_key] = df
                if interval == "1d":
                    self._memory_cache[symbol] = df
                    self._update_market_state_from_df(symbol, df)
                return self._append_live_candle(symbol, df.copy(), interval)

        except Exception as e:
            logger.error(f"Historical market data fetch failed for {symbol} ({interval}): {e}")

        # -------------------------------------------------------------
        # 6. Stale cache fallback
        # -------------------------------------------------------------
        stale_df = self.load_from_cache(symbol, interval)
        if stale_df is not None and not stale_df.empty:
            logger.info(f"Serving cached historical {interval} data for {symbol}.")
            MARKET_CACHE[cache_key] = stale_df
            if interval == "1d":
                self._memory_cache[symbol] = stale_df
                self._update_market_state_from_df(symbol, stale_df)
            return self._append_live_candle(symbol, stale_df.copy(), interval)

        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    def _append_live_candle(self, symbol: str, df: pd.DataFrame, interval: str = "1d") -> pd.DataFrame:
        """
        Appends or updates the live tick from LIVE_MARKET_STATE as the active evolving candle.
        Ensures the latest price on chart reflects the verified Bursa live feed.
        """
        if df.empty:
            return df
        
        live = LIVE_MARKET_STATE.get(symbol)
        if live and live.get("price", 0) > 0 and live.get("source") != "INIT":
            price = float(live["price"])
            if price <= 0:
                return df
            high = float(live.get("high") or price)
            low = float(live.get("low") or price)
            if high <= 0:
                high = price
            if low <= 0:
                low = price
            vol = int(live.get("volume", 0) or 0)

            # Ensure current candle prices are positive
            curr_low = float(df.iloc[-1]["Low"])
            if curr_low <= 0:
                curr_low = price
            curr_high = float(df.iloc[-1]["High"])
            if curr_high <= 0:
                curr_high = price

            new_high = max(curr_high, high, price)
            new_low = min(curr_low, low, price)

            if new_low > 0 and new_high > 0:
                df.iloc[-1, df.columns.get_loc("Close")] = price
                df.iloc[-1, df.columns.get_loc("High")] = new_high
                df.iloc[-1, df.columns.get_loc("Low")] = new_low
                if vol > 0:
                    df.iloc[-1, df.columns.get_loc("Volume")] = vol

        return df

    def _update_market_state_from_df(self, symbol: str, df: pd.DataFrame):
        """Update in-memory MARKET_STATE entry from OHLCV DataFrame."""
        if df.empty:
            return
        last_bar = df.iloc[-1]
        prev_bar = df.iloc[-2] if len(df) > 1 else last_bar
        
        last_p = float(last_bar["Close"])
        prev_p = float(prev_bar["Close"])
        chg_pct = round(((last_p - prev_p) / prev_p) * 100, 2) if prev_p > 0 else 0.0

        meta = get_ticker_meta(symbol)
        bar_high = float(last_bar["High"]) if float(last_bar["High"]) > 0 else last_p
        bar_low = float(last_bar["Low"]) if float(last_bar["Low"]) > 0 else last_p
        
        # Preserve live price if already present in LIVE_MARKET_STATE
        live = LIVE_MARKET_STATE.get(symbol)
        if live and live.get("price", 0) > 0 and live.get("source") != "INIT":
            last_p = live["price"]
            chg_pct = live.get("change_pct", chg_pct)
        elif live:
            live["price"] = round(last_p, 3)
            live["last_price"] = round(last_p, 3)
            live["high"] = round(bar_high, 3)
            live["low"] = round(bar_low, 3)
            live["change_pct"] = chg_pct

        MARKET_STATE[symbol] = {
            "ticker_symbol": symbol,
            "symbol": symbol,
            "code": meta["code"],
            "name": meta["name"],
            "sector": meta["sector"],
            "is_etf": meta.get("is_etf", False),
            "price": round(last_p, 3),
            "last_price": round(last_p, 3),
            "previous_close": round(prev_p, 3),
            "daily_change_pct": chg_pct,
            "day_high": round(bar_high, 3),
            "day_low": round(bar_low, 3),
            "volume": int(last_bar["Volume"]),
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "ohlcv_df": df.tail(MAX_BARS_WINDOW)
        }

    def sync_live_market_state(self, live_state: Dict[str, Dict[str, Any]]):
        """
        Synchronize in-memory MARKET_STATE with real-time bourse feed.
        Updates nominal prices and mutates the evolving candle on ohlcv_df.
        """
        for sym, live in live_state.items():
            if sym not in ALL_SYMBOLS:
                continue
            meta = get_ticker_meta(sym)
            price = float(live.get("price", 0.0) or 0.0)
            if price <= 0:
                continue
            chg = float(live.get("change", 0.0) or 0.0)
            chg_pct = float(live.get("change_pct", 0.0) or 0.0)
            vol = int(live.get("volume", 0) or 0)
            high = float(live.get("high") or price)
            low = float(live.get("low") or price)
            if high <= 0:
                high = price
            if low <= 0:
                low = price
            timestamp = live.get("timestamp", datetime.now().strftime("%H:%M:%S"))

            if sym in MARKET_STATE:
                entry = MARKET_STATE[sym]
                entry["price"] = price
                entry["last_price"] = price
                entry["daily_change_pct"] = chg_pct
                entry["volume"] = vol if vol > 0 else entry["volume"]
                entry["day_high"] = high
                entry["day_low"] = low
                entry["updated_at"] = timestamp

                # Mutate active evolving candle
                df = entry.get("ohlcv_df")
                if df is not None and not df.empty:
                    curr_low = float(df.iloc[-1]["Low"])
                    if curr_low <= 0:
                        curr_low = price
                    curr_high = float(df.iloc[-1]["High"])
                    if curr_high <= 0:
                        curr_high = price

                    new_high = max(curr_high, high, price)
                    new_low = min(curr_low, low, price)

                    if new_low > 0 and new_high > 0:
                        df.iloc[-1, df.columns.get_loc("Close")] = price
                        df.iloc[-1, df.columns.get_loc("High")] = new_high
                        df.iloc[-1, df.columns.get_loc("Low")] = new_low
                        if vol > 0:
                            df.iloc[-1, df.columns.get_loc("Volume")] = vol
            else:
                MARKET_STATE[sym] = {
                    "ticker_symbol": sym,
                    "symbol": sym,
                    "code": meta["code"],
                    "name": meta["name"],
                    "sector": meta["sector"],
                    "is_etf": meta.get("is_etf", False),
                    "price": price,
                    "last_price": price,
                    "previous_close": price,
                    "daily_change_pct": chg_pct,
                    "day_high": high,
                    "day_low": low,
                    "volume": vol,
                    "updated_at": timestamp,
                    "ohlcv_df": self.load_from_cache(sym) or pd.DataFrame()
                }

    def fetch_live_quote_fast(self, symbol: str) -> Dict[str, Any]:
        """
        Query real-time nominal price from LIVE_MARKET_STATE or direct feed.
        Eliminates yfinance 15-minute lag completely.
        """
        # 1. Check in-memory MARKET_STATE for valid price
        if symbol in MARKET_STATE and MARKET_STATE[symbol].get("last_price", 0) > 1.0:
            return MARKET_STATE[symbol]

        # 2. Check LIVE_MARKET_STATE for verified live quote
        if symbol in LIVE_MARKET_STATE and LIVE_MARKET_STATE[symbol].get("price", 0) > 1.0:
            live = LIVE_MARKET_STATE[symbol]
            self.sync_live_market_state({symbol: live})
            return MARKET_STATE.get(symbol, {})

        # 3. Check cached DataFrame on SSD
        cached_df = self.load_from_cache(symbol)
        if cached_df is not None and not cached_df.empty:
            self._update_market_state_from_df(symbol, cached_df)
            return MARKET_STATE.get(symbol, {})

        # 4. Ingest real historical data
        try:
            real_df = self.fetch_ohlcv(symbol)
            if not real_df.empty:
                return MARKET_STATE.get(symbol, {})
        except Exception:
            pass

        # 5. Fallback to initialized metadata
        meta = get_ticker_meta(symbol)
        MARKET_STATE[symbol] = {
            "ticker_symbol": symbol,
            "symbol": symbol,
            "code": meta["code"],
            "name": meta["name"],
            "sector": meta["sector"],
            "is_etf": meta.get("is_etf", False),
            "price": 1.0,
            "last_price": 1.0,
            "previous_close": 1.0,
            "daily_change_pct": 0.0,
            "day_high": 1.0,
            "day_low": 1.0,
            "volume": 0,
            "updated_at": datetime.now().strftime("%H:%M:%S"),
            "ohlcv_df": pd.DataFrame()
        }
        return MARKET_STATE[symbol]

    def fetch_benchmark(self, period: str = "1y", force_refresh: bool = False) -> pd.DataFrame:
        """Fetch primary benchmark (^KLSE)."""
        df = self.fetch_ohlcv(BENCHMARK_PRIMARY, period=period, force_refresh=force_refresh)
        if df is not None and not df.empty and len(df) > 10:
            return df
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    def fetch_universe_batch(self, symbols: Optional[List[str]] = None, period: str = "1y") -> Dict[str, pd.DataFrame]:
        """Ingests full universe batch sequentially or from cache."""
        if symbols is None:
            symbols = ALL_SYMBOLS
        dataset = {}
        for sym in symbols:
            try:
                df = self.fetch_ohlcv(sym, period=period)
                if not df.empty:
                    dataset[sym] = df
            except Exception as e:
                logger.error(f"Error ingesting {sym}: {e}")
        return dataset

    async def start_realtime_polling(self, ws_broadcast_callback, interval_seconds: int = TICK_POLL_INTERVAL_SECONDS):
        """
        Background worker task decoupled from the WebSocket event loop.
        Polls live nominal prices via realtime_feed and broadcasts tick updates.
        """
        if self._is_polling:
            return
        self._is_polling = True
        logger.info(f"Starting real-time market data polling loop (interval: {interval_seconds}s)...")

        # Initial full batch preload
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.fetch_universe_batch, ALL_SYMBOLS, "6mo")

        # Spawn background macro telemetry loop (15s interval)
        async def _macro_poll_worker():
            while self._is_polling:
                try:
                    await macro_auditor.fetch_macro_telemetry_async()
                except Exception as e:
                    logger.warning(f"Macro background polling error: {e}")
                await asyncio.sleep(15)

        self._macro_poll_task = asyncio.create_task(_macro_poll_worker())

        # Start real-time feed background loop
        await realtime_feed.start_realtime_polling(
            ws_broadcast_callback=ws_broadcast_callback,
            on_tick_update=self.sync_live_market_state,
            interval_seconds=interval_seconds
        )

    def fetch_macro_telemetry(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Synchronously retrieves cached or fresh macro telemetry (GC=F, ^TNX, BZ=F, MYR=X)."""
        return macro_auditor.fetch_macro_telemetry_sync(force_refresh=force_refresh)

    async def fetch_macro_telemetry_async(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Asynchronously retrieves cached or fresh macro telemetry."""
        return await macro_auditor.fetch_macro_telemetry_async(force_refresh=force_refresh)

    def stop_polling(self):
        """Gracefully stop background polling and flush caches to SSD."""
        self._is_polling = False
        if hasattr(self, "_macro_poll_task") and self._macro_poll_task:
            self._macro_poll_task.cancel()
        realtime_feed.stop_polling()
        logger.info("Flushing market data cache to SSD on shutdown...")
        for sym, state in MARKET_STATE.items():
            df = state.get("ohlcv_df")
            if df is not None and not df.empty:
                self.save_to_cache(sym, df)

# Global singleton
data_loader = MarketDataLoader()
