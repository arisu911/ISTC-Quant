"""
Bursa Strategy - API and WebSocket Hub Integration Tests
Validates real-time endpoints, order execution, fractional units, and single source of truth.
"""

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from server.app import app
from config.universe import ALL_SYMBOLS

class TestServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_universe_and_market_state(self):
        """Verify /api/market_state returns all 23 whitelisted tickers with no extra tickers."""
        resp = self.client.get("/api/market_state")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 23)
        self.assertEqual(len(data["symbols"]), 23)
        self.assertIn("0828EA.KL", data["symbols"])
        self.assertIn("5211.KL", data["symbols"])
        # Non-whitelisted tickers must NOT be present
        for banned in ["5141.KL", "7277.KL", "5162.KL", "7113.KL", "5819.KL"]:
            self.assertNotIn(banned, data["symbols"])

    def test_02_rubric_initial_state(self):
        """Verify starting portfolio equity is RM 50.00 (not RM 50,000)."""
        resp = self.client.get("/api/rubric")
        self.assertEqual(resp.status_code, 200)
        rubric = resp.json()
        self.assertLessEqual(rubric["cash_balance"], 50.00)
        self.assertLessEqual(rubric["total_equity"], 50.00)
        self.assertIn("[0/2]", rubric["etf_badge"])
        self.assertIn("[0/2]", rubric["fractional_badge"])
        self.assertIn("[0/5]", rubric["total_badge"])

    def test_03_fractional_order_execution(self):
        """Verify fractional unit order execution via /api/order."""
        # Test buying 0.05 fractional units of 5211.KL
        payload = {
            "action": "BUY",
            "ticker": "5211.KL",
            "units": 0.05,
            "notes": "API test fractional unit"
        }
        resp = self.client.post("/api/order", json=payload)
        self.assertEqual(resp.status_code, 200)
        res = resp.json()
        self.assertTrue(res["success"])
        trade = res["trade"]
        self.assertEqual(trade["units"], 0.05)
        self.assertEqual(trade["symbol"], "5211.KL")
        self.assertGreater(trade["price"], 0)
        self.assertAlmostEqual(trade["total_myr"], round(0.05 * trade["price"], 4))

    def test_04_html_views_render(self):
        """Verify /tower and /desk load without syntax errors."""
        resp_tower = self.client.get("/tower")
        self.assertEqual(resp_tower.status_code, 200)
        self.assertIn("Tower Portrait", resp_tower.text)

        resp_desk = self.client.get("/desk")
        self.assertEqual(resp_desk.status_code, 200)
        self.assertIn("DESK WORKSPACE", resp_desk.text)
        self.assertIn("sizer-units-input", resp_desk.text)

    def test_05_direct_realtime_feed(self):
        """Verify realtime_feed returns unadjusted nominal market prices for Bursa."""
        import asyncio
        from data.realtime_feed import realtime_feed
        quote = asyncio.run(realtime_feed.fetch_ticker_quote_secondary("5211.KL"))
        self.assertEqual(quote["symbol"], "5211.KL")
        self.assertGreater(quote["price"], 0.0)
        self.assertIn("ticker_symbol", quote)
        self.assertEqual(quote["ticker_symbol"], "5211.KL")

    def test_06_ohlcv_unadjusted_nominal_price(self):
        """Verify Tenaga (5347) and Sunway (5211) return valid candles with nominal pricing."""
        resp = self.client.get("/api/ohlcv/5347.KL")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["symbol"], "5347.KL")
        self.assertGreater(len(data["candles"]), 20)
        last_price = data["current_metrics"]["last_price"]
        self.assertGreater(last_price, 10.0)  # Tenaga nominal price ~RM 12-14

    def test_07_fundamental_multiplier_and_mrdiy_fcf(self):
        """Verify Hotfix 1: MRDIY Free Cash Flow displays accurately as RM 188.1M (not RM 188.1k)."""
        resp = self.client.get("/api/analyze/5296.KL")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        metrics = data["audit"]["metrics"]
        self.assertEqual(metrics["fcf_formatted"], "RM 188.1M")
        self.assertEqual(metrics["fcf_nominal"], 188100000.0)
        self.assertEqual(metrics["cfo_formatted"], "RM 712.1M")

    def test_08_sector_adaptive_mda_retail(self):
        """Verify Hotfix 3: MRDIY forward commentary reflects retail footprint rather than construction backlog."""
        resp = self.client.get("/api/analyze/5296.KL")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        llm_rev = data["llm_review"]
        catalysts = llm_rev["forward_catalysts"].lower()
        self.assertTrue("store" in catalysts or "retail" in catalysts or "footprint" in catalysts)
        self.assertNotIn("order book", catalysts)
        self.assertNotIn("backlog", catalysts)
        self.assertIn(llm_rev["sector_category"], ["CONSUMER_RETAIL", "Consumer Products"])

    def test_09_mda_sanitization_and_json_schema(self):
        """Verify Hotfix 2: MD&A points adhere to schema, have no trailing asterisks, and end with complete sentences."""
        resp = self.client.get("/api/analyze/5296.KL")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        llm_rev = data["llm_review"]

        required_keys = [
            "commercial_drivers",
            "cash_deployment",
            "working_capital_health",
            "forward_catalysts",
            "shariah_debt_posture"
        ]
        for k in required_keys:
            self.assertIn(k, llm_rev)
            val = llm_rev[k]
            self.assertFalse(val.endswith("*"), f"Field {k} ends with dangling asterisk: {val}")
            self.assertTrue(val.endswith((".", "!", "?")), f"Field {k} does not end with terminal punctuation: {val}")

if __name__ == "__main__":
    unittest.main()

