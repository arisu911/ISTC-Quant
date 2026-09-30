"""
Comprehensive Institutional Verification Script:
Validates all 23 Instruments against the Fundamental Auditor & LLM Pipeline Mandates.
"""

import sys
from config.universe import ALL_SYMBOLS, get_ticker_meta
from analyzer.fundamental_audit import fundamental_auditor
from analyzer.llm_agent import llm_agent

def verify_all_23_instruments():
    print(f"=================================================================")
    print(f"VERIFYING 23-INSTRUMENT FUNDAMENTAL AUDITOR PIPELINE")
    print(f"=================================================================")

    metrics_cache = {}
    narrative_cache = {}
    discrepancies = []

    for sym in ALL_SYMBOLS:
        meta = get_ticker_meta(sym)
        code = meta["code"]
        name = meta["name"]
        
        # 1. Audit counter
        audit = fundamental_auditor.get_or_load_audit(sym)
        metrics = audit["metrics"]
        is_etf = audit.get("is_etf", False)

        # 2. LLM / NLP Qualitative narrative
        mda = llm_agent.audit_mda("", sym, audit)

        metrics_cache[sym] = metrics
        narrative_cache[sym] = mda

        print(f"\n[{sym}] {name} ({meta['sector']}) | is_etf={is_etf}")
        
        if is_etf:
            print(f"  ETF Asset: {audit['etf_structure']['asset_class']}")
            print(f"  Purity: {audit['etf_structure']['gold_purity']}")
            print(f"  Vault Custody: {audit['etf_structure']['custody_vault']}")
            print(f"  NAV: {audit['etf_structure']['nav_per_unit']} | Prem: {audit['etf_structure']['premium_discount_pct']} | MER: {audit['etf_structure']['mer_pct']}")
            print(f"  Shariah: {audit['etf_structure']['shariah_standard']} ({audit['etf_structure']['shariah_advisor']})")
            
            # Assertions for 0828EA
            assert "Malca-Amit Singapore" in audit['etf_structure']['custody_vault'], "Missing Malca-Amit Singapore vault"
            assert "99.5%" in audit['etf_structure']['gold_purity'], "Missing 99.5% LBMA purity"
            assert "0.50%" in audit['etf_structure']['mer_pct'], "Missing 0.50% MER"
            assert "Amanie Advisors" in audit['etf_structure']['shariah_advisor'], "Missing Amanie Advisors"
            assert "AAOIFI" in audit['etf_structure']['shariah_standard'], "Missing AAOIFI standard"
            assert mda.get("is_etf") is True, "LLM agent must flag is_etf as True"
        else:
            fcf = metrics["free_cash_flow"]
            eq = metrics["earnings_quality"]
            cash_pct = metrics["cash_ratio_pct"]
            debt_pct = metrics["debt_ratio_pct"]
            
            print(f"  FCF: {fcf} | CFO/EBITDA: {eq} | Cash: {cash_pct:.2f}% | Debt: {debt_pct:.2f}%")
            print(f"  Driver: {mda['commercial_drivers']}")
            print(f"  Gov P5: {mda['shariah_governance']}")

            # Verify Single Source of Truth Binding:
            # Bullet 5 MUST cite the exact debt ratio
            expected_debt_str = f"{debt_pct:.2f}%"
            if expected_debt_str not in mda["shariah_governance"]:
                discrepancies.append(f"{sym}: Debt ratio {expected_debt_str} not cited in Bullet 5 narrative: {mda['shariah_governance']}")

            # Specific counter checks
            if sym == "5211.KL": # SUNWAY
                assert "order book" in mda["forward_catalysts"].lower() or "order book" in mda["commercial_drivers"].lower(), "SUNWAY missing order book"
                assert "4.8" in mda["forward_catalysts"], "SUNWAY missing RM 4.8B order book reference"
            elif sym == "3816.KL": # MISC
                assert "tanker" in mda["commercial_drivers"].lower() or "fleet" in mda["commercial_drivers"].lower() or "gas" in mda["commercial_drivers"].lower(), "MISC missing shipping/tanker driver"
                assert "order book" not in mda["commercial_drivers"].lower(), "MISC hallucinated construction order book!"
                assert fcf == "RM 420.5M", f"MISC expected FCF RM 420.5M, got {fcf}"
                assert eq == 0.912, f"MISC expected CFO/EBITDA 0.912, got {eq}"
                assert debt_pct == 18.50, f"MISC expected Debt Ratio 18.50%, got {debt_pct}"
                assert cash_pct == 14.20, f"MISC expected Cash Ratio 14.20%, got {cash_pct}"
            elif sym == "5296.KL": # MRDIY
                assert "store" in mda["commercial_drivers"].lower() or "retail" in mda["commercial_drivers"].lower(), "MRDIY missing retail driver"
                assert "order book" not in mda["commercial_drivers"].lower(), "MRDIY hallucinated construction order book!"
                assert fcf == "RM 188.1M", f"MRDIY expected FCF RM 188.1M, got {fcf}"
                assert debt_pct == 0.00, f"MRDIY expected Debt Ratio 0.00%, got {debt_pct}"
            elif sym == "8869.KL": # PMETAL
                assert "aluminium" in mda["commercial_drivers"].lower() or "lme" in mda["commercial_drivers"].lower(), "PMETAL missing aluminium driver"
            elif sym == "5347.KL": # TENAGA
                assert "data centre" in mda["forward_catalysts"].lower() or "grid" in mda["cash_deployment"].lower(), "TENAGA missing grid / DC metrics"

    print("\n-----------------------------------------------------------------")
    print("CHECKING FOR CLONED METRICS ACROSS EQUITIES...")
    equities = [s for s in ALL_SYMBOLS if s != "0828EA.KL"]
    
    # Check that not all equities share the same FCF or Debt
    fcfs = [metrics_cache[s]["free_cash_flow"] for s in equities]
    debts = [metrics_cache[s]["debt_ratio_pct"] for s in equities]
    
    unique_fcfs = set(fcfs)
    unique_debts = set(debts)
    print(f"Total Equities: {len(equities)}")
    print(f"Unique FCF Values: {len(unique_fcfs)}")
    print(f"Unique Debt Ratio Values: {len(unique_debts)}")
    
    assert len(unique_fcfs) >= 20, f"Too many duplicate FCFs: {len(unique_fcfs)}"
    assert len(unique_debts) >= 20, f"Too many duplicate Debt Ratios: {len(unique_debts)}"

    if discrepancies:
        print(f"\nFAILED DISCREPANCIES ({len(discrepancies)}):")
        for d in discrepancies:
            print(f"  - {d}")
        sys.exit(1)

    print("\n=================================================================")
    print("ALL 23 INSTRUMENTS VERIFIED WITH ZERO DEFECTS / 100% COMPLIANCE!")
    print("=================================================================")

if __name__ == "__main__":
    verify_all_23_instruments()
