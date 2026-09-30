"""
Unit & Integration Tests for Multi-Timeframe Engine (1H, 4H, 1D),
TradingView Ichimoku Palette, and Forward Kumo Projection.
"""

import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from data.loader import data_loader, build_4h_bars, MARKET_CACHE
from factors.ichimoku import (
    calculate_ichimoku, 
    score_ichimoku_momentum,
    generate_future_timestamps,
    build_ichimoku_chart_series
)
from server.app import _get_chart_data

class TestMultiTimeframeIchimoku(unittest.TestCase):

    def setUp(self):
        # Create a synthetic 1H DataFrame representing Bursa trading hours
        dates = []
        base = pd.Timestamp("2026-09-21 09:00:00", tz="Asia/Kuala_Lumpur")
        for day in range(10): # 10 business days
            day_dt = base + timedelta(days=day)
            if day_dt.weekday() >= 5:
                continue
            for hour in [9, 10, 11, 12, 14, 15, 16]:
                dates.append(day_dt.replace(hour=hour, minute=0, second=0))

        n = len(dates)
        np.random.seed(42)
        close_prices = 4.0 + np.cumsum(np.random.randn(n) * 0.02)
        high_prices = close_prices + np.random.uniform(0.01, 0.05, n)
        low_prices = close_prices - np.random.uniform(0.01, 0.05, n)
        open_prices = low_prices + np.random.uniform(0.0, 0.04, n)
        volumes = np.random.randint(10000, 500000, n)

        self.df_1h = pd.DataFrame({
            "Open": open_prices,
            "High": high_prices,
            "Low": low_prices,
            "Close": close_prices,
            "Volume": volumes
        }, index=pd.DatetimeIndex(dates, name="Datetime"))

    def test_01_build_4h_resampling(self):
        """Test synthesizing 4H bars directly from 1H bars using pandas resample."""
        df_4h = build_4h_bars(self.df_1h)
        self.assertFalse(df_4h.empty)
        # Each trading day has 2 bars (09:00 and 13:00)
        self.assertLess(len(df_4h), len(self.df_1h))
        self.assertIn("Open", df_4h.columns)
        self.assertIn("Close", df_4h.columns)
        self.assertIn("High", df_4h.columns)
        self.assertIn("Low", df_4h.columns)
        self.assertIn("Volume", df_4h.columns)

    def test_02_future_timestamp_generation(self):
        """Test future timestamp generation for 1d, 1h, and 4h intervals as integer Unix epoch seconds."""
        last_d = pd.Timestamp("2026-09-30")
        fwd_1d = generate_future_timestamps(last_d, interval="1d", count=26)
        self.assertEqual(len(fwd_1d), 26)
        self.assertIsInstance(fwd_1d[0], int)
        # Ensure strictly increasing by 86400s
        for i in range(len(fwd_1d) - 1):
            self.assertEqual(fwd_1d[i + 1] - fwd_1d[i], 86400)

        # Test 1h session bars (incremented by 3600s)
        last_h = pd.Timestamp("2026-09-30 16:00:00", tz="Asia/Kuala_Lumpur")
        fwd_1h = generate_future_timestamps(last_h, interval="1h", count=26)
        self.assertEqual(len(fwd_1h), 26)
        self.assertIsInstance(fwd_1h[0], int)
        for i in range(len(fwd_1h) - 1):
            self.assertEqual(fwd_1h[i + 1] - fwd_1h[i], 3600)

        # Test 4h session bars (incremented by 14400s)
        last_4h = pd.Timestamp("2026-09-30 13:00:00", tz="Asia/Kuala_Lumpur")
        fwd_4h = generate_future_timestamps(last_4h, interval="4h", count=26)
        self.assertEqual(len(fwd_4h), 26)
        self.assertIsInstance(fwd_4h[0], int)
        for i in range(len(fwd_4h) - 1):
            self.assertEqual(fwd_4h[i + 1] - fwd_4h[i], 14400)

    def test_03_ichimoku_forward_projection_series(self):
        """Test build_ichimoku_chart_series includes 26-bar future projection for Span A and Span B."""
        ichi_df = calculate_ichimoku(self.df_1h)
        series = build_ichimoku_chart_series(self.df_1h, ichi_df, interval="1h")

        self.assertIn("tenkan", series)
        self.assertIn("kijun", series)
        self.assertIn("chikou", series)
        self.assertIn("span_a", series)
        self.assertIn("span_b", series)

        # The last Span A/B timestamp should be greater than the last candle timestamp
        last_candle_time = int(self.df_1h.index[-1].timestamp())
        last_span_a_time = series["span_a"][-1]["time"]
        last_span_b_time = series["span_b"][-1]["time"]

        self.assertGreater(last_span_a_time, last_candle_time)
        self.assertGreater(last_span_b_time, last_candle_time)

    def test_04_market_data_loader_intervals(self):
        """Test data_loader.fetch_ohlcv across 1d, 1h, and 4h intervals."""
        # 1d
        df_1d = data_loader.fetch_ohlcv("5211.KL", interval="1d")
        self.assertFalse(df_1d.empty)
        self.assertIn("5211.KL_1d", MARKET_CACHE)

        # 1h
        df_1h = data_loader.fetch_ohlcv("5211.KL", interval="1h")
        self.assertFalse(df_1h.empty)
        self.assertIn("5211.KL_1h", MARKET_CACHE)

        # 4h
        df_4h = data_loader.fetch_ohlcv("5211.KL", interval="4h")
        self.assertFalse(df_4h.empty)
        self.assertIn("5211.KL_4h", MARKET_CACHE)

    async def _async_test_api(self):
        for tf in ["1d", "1h", "4h"]:
            data = await _get_chart_data("5211.KL", interval=tf)
            self.assertEqual(data["interval"], tf)
            self.assertGreater(len(data["candles"]), 0)
            self.assertGreater(len(data["tenkan"]), 0)
            self.assertGreater(len(data["kijun"]), 0)
            self.assertGreater(len(data["span_a"]), 0)
            self.assertGreater(len(data["span_b"]), 0)

    def test_05_api_chart_endpoint(self):
        """Verify _get_chart_data async handler across all 3 timeframes."""
        import asyncio
        asyncio.run(self._async_test_api())

if __name__ == "__main__":
    unittest.main()
