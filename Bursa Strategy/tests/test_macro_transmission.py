"""
Comprehensive Verification Suite:
Dynamic Macro Transmission & Commodity Arbitrage Engine for 0828EA.KL (GOLDETF).
"""

import unittest
from analyzer.macro_audit import (
    macro_auditor, 
    MACRO_STATE, 
    TROY_OUNCE_TO_GRAMS, 
    BULLION_UNIT_GRAMS, 
    FUND_CASH_DRAG_FACTOR
)
from analyzer.fundamental_audit import fundamental_auditor
from analyzer.llm_agent import llm_agent
from fastapi.testclient import TestClient
from server.app import app

class TestMacroTransmissionEngine(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_01_macro_state_ingestion(self):
        """Mandate 1: Verify macro state dictionary has all 4 benchmarks with valid quotes."""
        telemetry = macro_auditor.fetch_macro_telemetry_sync()
        for ticker in ["GC=F", "^TNX", "BZ=F", "MYR=X"]:
            self.assertIn(ticker, telemetry, f"Missing macro ticker {ticker}")
            st = telemetry[ticker]
            self.assertGreater(st["price"], 0.0, f"Ticker {ticker} price must be > 0")
            self.assertTrue(len(st["formatted_price"]) > 0, f"Formatted price missing for {ticker}")
            self.assertTrue(len(st["badge"]) > 0, f"Badge missing for {ticker}")

    def test_02_theoretical_nav_math(self):
        """Mandate 1: Mathematically verify theoretical bullion NAV and spread formulas."""
        gold_price = 2658.40
        usd_myr = 4.1250
        bursa_price = 3.600

        # Run exact formula
        expected_nav_per_gram = (gold_price * usd_myr) / 31.1034768
        expected_indicative_nav = expected_nav_per_gram * 0.01 * 1.0128
        expected_spread_pct = ((bursa_price / expected_indicative_nav) - 1.0) * 100.0

        # Test compute_gold_nav with mocked state
        original_gold = MACRO_STATE["GC=F"]["price"]
        original_myr = MACRO_STATE["MYR=X"]["price"]
        try:
            MACRO_STATE["GC=F"]["price"] = gold_price
            MACRO_STATE["MYR=X"]["price"] = usd_myr

            res = macro_auditor.compute_gold_nav(bursa_price)
            self.assertAlmostEqual(res["nav_per_gram"], round(expected_nav_per_gram, 2), places=1)
            self.assertAlmostEqual(res["indicative_nav"], round(expected_indicative_nav, 3), places=2)
            self.assertAlmostEqual(res["spread_pct"], round(expected_spread_pct, 2), places=1)

            # Check spread status
            if expected_spread_pct > 0.75:
                self.assertIn("PREMIUM", res["arbitrage_status"])
            elif expected_spread_pct < -0.75:
                self.assertIn("DISCOUNT", res["arbitrage_status"])
            else:
                self.assertIn("FAIR VALUE", res["arbitrage_status"])
        finally:
            MACRO_STATE["GC=F"]["price"] = original_gold
            MACRO_STATE["MYR=X"]["price"] = original_myr

    def test_03_purged_na_placeholders(self):
        """Mandate 1 & 2: Verify zero 'N/A (Vault Asset)' placeholders in 0828EA metrics."""
        audit = fundamental_auditor.get_or_load_audit("0828EA.KL")
        metrics = audit["metrics"]

        # Ensure N/A (Vault Asset) is purged
        self.assertNotEqual(metrics.get("free_cash_flow"), "N/A (Vault Asset)")
        self.assertNotEqual(metrics.get("fcf_formatted"), "N/A (Vault Asset)")
        self.assertIn("NAV", str(metrics.get("free_cash_flow")))

        # Check macro card keys
        self.assertIn("macro_card_1_header", metrics)
        self.assertEqual(metrics["macro_card_1_header"], "COMEX GOLD (USD/oz)")
        self.assertIn("macro_card_2_header", metrics)
        self.assertEqual(metrics["macro_card_2_header"], "US 10Y BOND YIELD")
        self.assertIn("macro_card_3_header", metrics)
        self.assertEqual(metrics["macro_card_3_header"], "BRENT CRUDE OIL")
        self.assertIn("macro_card_4_header", metrics)
        self.assertEqual(metrics["macro_card_4_header"], "USD / MYR FX RATE")

    def test_04_macro_audit_narrative_points(self):
        """Mandate 2: Verify the 5-point macro transmission narrative for 0828EA."""
        audit = fundamental_auditor.get_or_load_audit("0828EA.KL")
        mda = llm_agent.audit_mda("", "0828EA.KL", audit)

        self.assertTrue(mda.get("is_etf"), "0828EA must be flagged as is_etf")
        self.assertTrue(mda.get("macro_mode"), "0828EA must be flagged as macro_mode")

        # 5 distinct points
        p1 = mda["point1_body"]
        p2 = mda["point2_body"]
        p3 = mda["point3_body"]
        p4 = mda["point4_body"]
        p5 = mda["point5_body"]

        self.assertIn("NAV", p1)
        self.assertIn("Spread", p1)
        self.assertIn("10-Year", p2)
        self.assertIn("Brent Crude", p3)
        self.assertIn("USD/MYR", p4)
        self.assertIn("30%", p5)
        self.assertIn("Malca-Amit Singapore", p5)
        self.assertIn("AAOIFI", p5)

    def test_05_switching_reversion_to_equity(self):
        """Mandate 3: Seamless reversion between 0828EA and corporate equities."""
        # 1. Select 0828EA.KL (Commodity ETF Mode)
        etf_resp = self.client.get("/api/analyze/0828EA.KL")
        self.assertEqual(etf_resp.status_code, 200)
        etf_data = etf_resp.json()
        self.assertTrue(etf_data["payload"]["is_etf"])
        self.assertTrue(etf_data["payload"].get("macro_mode"))
        self.assertIn("macro_telemetry", etf_data["payload"])
        self.assertEqual(etf_data["payload"]["macro_telemetry"]["card_1"]["header"], "COMEX GOLD (USD/oz)")

        # 2. Switch back to SUNWAY (5211.KL) (Corporate Equity Mode)
        eq_resp = self.client.get("/api/analyze/5211.KL")
        self.assertEqual(eq_resp.status_code, 200)
        eq_data = eq_resp.json()
        self.assertFalse(eq_data["payload"]["is_etf"])
        self.assertNotIn("macro_telemetry", eq_data["payload"])

        # Check corporate metrics restored
        m = eq_data["payload"]["metrics"]
        self.assertIn("RM", m["free_cash_flow"])
        self.assertGreater(m["earnings_quality"], 0.0)
        self.assertGreaterEqual(m["cash_ratio_pct"], 0.0)
        self.assertGreaterEqual(m["debt_ratio_pct"], 0.0)

        # Check corporate MD&A restored with no macro bleed
        narrative = eq_data["payload"]["narrative"]
        self.assertNotIn("COMEX GOLD", narrative["commercial_drivers"])
        self.assertNotIn("Brent Crude", narrative["working_capital"])

    def test_06_rest_api_macro_endpoint(self):
        """Mandate 1: Verify /api/macro endpoint returns valid telemetry and pricing."""
        resp = self.client.get("/api/macro")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "LIVE")
        self.assertIn("macro_state", data)
        self.assertIn("nav_data", data)
        self.assertIn("narrative", data)
        self.assertGreater(data["nav_data"]["indicative_nav"], 0.0)

if __name__ == "__main__":
    unittest.main()
