"""
Bursa Strategy Quantitative Terminal - Unit & Integration Test Suite
Validates mathematical calculations, factor screening, fundamental audits, and Edge/Brave launcher.
"""

import sys
import os
import unittest
from pathlib import Path
import numpy as np
import pandas as pd

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import SAC_SC_MAX_CASH_RATIO, SAC_SC_MAX_DEBT_RATIO
from config.universe import UNIVERSE_DATA, ALL_SYMBOLS, get_ticker_meta
from config.catalysts import get_catalyst_telemetry, calculate_trading_days
from data.loader import data_loader
from data.bursa_scraper import bursa_scraper
from factors.ichimoku import calculate_ichimoku, score_ichimoku_momentum
from factors.volume_volatility import calculate_volume_volatility, get_latest_volume_metrics
from factors.relative_strength import calculate_mansfield_rs, get_latest_rs_metrics
from factors.institutional_flow import calculate_institutional_flows, get_latest_flow_metrics
from analyzer.pdf_extractor import pdf_extractor
from analyzer.fundamental_audit import fundamental_auditor
from analyzer.llm_agent import llm_agent
from simulation.rolling_sprint import rolling_sprint_simulator
from simulation.exit_engine import portfolio
from main import detect_browser

class TestBursaStrategy(unittest.TestCase):
    
    def test_01_universe_and_metadata(self):
        """Verify 22 Shariah fractional equities + 0828EA GOLDETF."""
        self.assertEqual(len(UNIVERSE_DATA), 23)
        self.assertIn("0828EA.KL", ALL_SYMBOLS)
        self.assertIn("5211.KL", ALL_SYMBOLS)
        
        # Test lookup resolution
        meta_code = get_ticker_meta("5211")
        self.assertEqual(meta_code["name"], "SUNWAY")
        self.assertTrue(meta_code["shariah"])
        self.assertTrue(meta_code["fractional"])
        
        meta_gold = get_ticker_meta("0828EA")
        self.assertTrue(meta_gold["is_etf"])

    def test_02_catalyst_countdown(self):
        """Verify catalyst calendar dates and trading day logic."""
        events = get_catalyst_telemetry()
        self.assertGreaterEqual(len(events), 4)
        
        # Ensure budget 2027 and challenge end exist
        event_ids = [e["id"] for e in events]
        self.assertIn("budget_2027", event_ids)
        self.assertIn("tourn_finale", event_ids)
        
        for e in events:
            self.assertIn("trading_days_remaining", e)
            self.assertIn("calendar_days_remaining", e)
            self.assertIsInstance(e["trading_days_remaining"], int)

    def test_03_data_loader_and_cache(self):
        """Verify OHLCV ingestion and caching."""
        df = data_loader.fetch_ohlcv("5211.KL", period="6mo")
        self.assertFalse(df.empty)
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            self.assertIn(col, df.columns)
        self.assertGreater(len(df), 50)

    def test_04_ichimoku_factors(self):
        """Verify vectorized 9-26-52 calculations and -5 to +5 scoring."""
        df = data_loader.fetch_ohlcv("5211.KL", period="6mo")
        ichi = calculate_ichimoku(df)
        self.assertIn("tenkan_sen", ichi.columns)
        self.assertIn("kijun_sen", ichi.columns)
        self.assertIn("span_a_current", ichi.columns)
        self.assertIn("span_b_current", ichi.columns)
        
        score, meta = score_ichimoku_momentum(ichi)
        self.assertGreaterEqual(score, -5.0)
        self.assertLessEqual(score, 5.0)
        self.assertIn("cloud_state", meta)

    def test_05_volume_volatility_factors(self):
        """Verify Volume Z-score, BBW, and ATR% squeeze."""
        df = data_loader.fetch_ohlcv("5211.KL", period="6mo")
        vol = calculate_volume_volatility(df)
        self.assertIn("volume_z_score", vol.columns)
        self.assertIn("bb_bandwidth", vol.columns)
        self.assertIn("atr_pct", vol.columns)
        
        meta = get_latest_volume_metrics(vol)
        self.assertIn("volume_z_score", meta)
        self.assertIn("volatility_squeeze", meta)

    def test_06_mansfield_rs_and_alpha(self):
        """Verify Mansfield Relative Strength and 10D/30D alpha."""
        stock_df = data_loader.fetch_ohlcv("5211.KL", period="6mo")
        bench_df = data_loader.fetch_benchmark(period="6mo")
        rs = calculate_mansfield_rs(stock_df, bench_df)
        self.assertIn("mrs", rs.columns)
        self.assertIn("alpha_10d", rs.columns)
        
        meta = get_latest_rs_metrics(rs)
        self.assertIn("mrs", meta)
        self.assertIn("alpha_10d", meta)

    def test_07_anchored_vwap_and_cmf(self):
        """Verify Anchored VWAP and Chaikin Money Flow (CMF-21)."""
        df = data_loader.fetch_ohlcv("5211.KL", period="6mo")
        flow = calculate_institutional_flows(df)
        self.assertIn("avwap_tournament", flow.columns)
        self.assertIn("cmf_21", flow.columns)
        
        meta = get_latest_flow_metrics(flow)
        self.assertIn("cmf_21", meta)
        self.assertIn("avwap_tournament", meta)

    def test_08_pdf_extractor_and_fundamental_audit(self):
        """Verify A4 PDF generation, table extraction, and SAC SC 33% ratios."""
        pdf_path = bursa_scraper.get_or_generate_report_pdf("5211")
        self.assertTrue(pdf_path.exists())
        
        parsed = pdf_extractor.parse_pdf(pdf_path)
        self.assertGreater(parsed["text_length"], 100)
        self.assertIn("mda_operational", parsed["sections"])
        
        audit = fundamental_auditor.audit_report(parsed, "5211")
        m = audit["metrics"]
        self.assertIn("fcf_myr_k", m)
        self.assertIn("cfo_ebitda_ratio", m)
        self.assertTrue(m["sac_cash_compliant"])
        self.assertTrue(m["sac_debt_compliant"])
        self.assertLess(m["sac_sc_cash_ratio"], SAC_SC_MAX_CASH_RATIO)
        self.assertLess(m["sac_sc_debt_ratio"], SAC_SC_MAX_DEBT_RATIO)

    def test_09_llm_mda_audit(self):
        """Verify qualitative LLM audit 5-point extraction."""
        pdf_path = bursa_scraper.get_or_generate_report_pdf("5211")
        parsed = pdf_extractor.parse_pdf(pdf_path)
        mda = llm_agent.audit_mda(parsed["sections"]["mda_operational"], "5211")
        self.assertIn("commercial_drivers", mda)
        self.assertIn("operating_cash_destination", mda)
        self.assertIn("inventory_receivables_audit", mda)
        self.assertIn("forward_catalysts", mda)
        self.assertIn("shariah_balance_sheet_risk", mda)

    def test_10_rolling_sprint_simulator(self):
        """Verify 25-day rolling sprint tournament simulation."""
        df = data_loader.fetch_ohlcv("5211.KL", period="1y")
        res = rolling_sprint_simulator.run_sprint_backtest(df, "5211.KL")
        self.assertIn("prob_return_gte_20", res)
        self.assertIn("win_rate_pct", res)
        self.assertIn("tournament_rating", res)

    def test_11_exit_engine_and_fractional_sizer(self):
        """Verify RM50 fractional calculation and rubric criteria."""
        units = portfolio.calculate_fractional_units(25.0, 4.65)
        self.assertAlmostEqual(units, round(25.0 / 4.65, 4), places=4)
        
        # Test trade execution using fractional units (1.00 unit)
        trade_res = portfolio.execute_order("BUY", "5211.KL", units=1.0, price_override=4.65)
        self.assertTrue(trade_res["success"])
        self.assertEqual(trade_res["trade"]["units"], 1.0)
        
        # Test trade execution using amount_myr (RM 5.00) for i-ETF compliance
        trade_res2 = portfolio.execute_order("BUY", "0828EA.KL", amount_myr=5.00, price_override=3.20)
        self.assertTrue(trade_res2["success"])
        self.assertAlmostEqual(trade_res2["trade"]["units"], round(5.00 / 3.20, 4), places=4)
        
        rubric = portfolio.get_rubric_metrics()
        self.assertIn("etf_badge", rubric)
        self.assertIn("fractional_badge", rubric)
        self.assertIn("total_badge", rubric)
        self.assertLessEqual(rubric["cash_balance"], 50.00)

    def test_12_browser_detector_edge_brave(self):
        """Verify Edge or Brave browser detection (zero Chrome dependency)."""
        b_name, exe = detect_browser()
        # Must detect Edge or Brave on Windows
        self.assertIn(b_name, ["edge", "brave"])
        self.assertIsNotNone(exe)
        self.assertTrue(exe.exists())
        self.assertNotIn("chrome", str(exe).lower())

if __name__ == "__main__":
    unittest.main()
