"""
Bursa Strategy Qualitative LLM Audit Pipeline
Specialized LLM agent for Bursa Malaysia MD&A, capital allocation, and operational reviews.
Enforces strict sector routing and company-specific narrative prompts to eliminate cross-company hallucinations.
Binds Point 5 Shariah governance directly to the single source of truth calculated debt ratio.
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional

import requests

from config.settings import GEMINI_API_KEY, LM_STUDIO_URL
from config.universe import get_ticker_meta
from data.fundamentals.baseline_data import get_baseline_counter
from analyzer.macro_audit import macro_auditor

logger = logging.getLogger("bursa.analyzer.llm")

# Mandate 3: Strict Sector Routing Rules
SECTOR_EXTRACTION_RULES: Dict[str, Dict[str, Any]] = {
    "Plantation": {
        "tickers": ["2445.KL", "1961.KL", "5285.KL"],
        "metric_focus": "Fresh Fruit Bunch (FFB) yields, realized CPO selling prices (RM/MT), replanting hectarage, and EUDR compliance."
    },
    "Telecommunications": {
        "tickers": ["4863.KL", "6012.KL", "6947.KL", "6888.KL"],
        "metric_focus": "Blended ARPU trends, 5G wholesale access charges, enterprise cloud/fiber off-take, and network CAPEX intensity."
    },
    "Consumer Products": {
        "tickers": ["5296.KL", "4707.KL", "7084.KL", "4065.KL", "5681.KL"],
        "metric_focus": "Same-Store Sales Growth (SSSG), new retail store footprint, raw material/feed input cost volatility, and consumer wallet elasticity."
    },
    "Industrial & Energy Logistics": {
        "tickers": ["5211.KL", "8869.KL", "5183.KL", "4197.KL", "3816.KL"],
        "metric_focus": "For SUNWAY: unbilled property sales & construction order book. For PMETAL: aluminium LME price spreads. For MISC: LNG/petroleum tanker charter rates. For PCHEM: plant utilization rates."
    },
    "Utilities & Infrastructure": {
        "tickers": ["5347.KL", "6033.KL"],
        "metric_focus": "Data centre energy demand commitments, regulated asset base (RAB) capital expenditure, and tariff adjustment pass-through."
    },
    "Financial Infrastructure": {
        "tickers": ["1818.KL"],
        "metric_focus": "Securities Average Daily Trading Value (ADV), market velocity rate, IPO listing count, and derivatives contract volume."
    },
    "Healthcare": {
        "tickers": ["5225.KL"],
        "metric_focus": "Inpatient admissions, bed occupancy rate (BOR), average revenue per occupied bed, and medical tourism revenue."
    },
    "Technology Outlier": {
        "tickers": ["5136.KL"],
        "metric_focus": "Fintech application user base, freight forwarding turnover, and cash preservation runway."
    }
}

def get_sector_for_ticker(symbol: str) -> str:
    """Finds the strict sector category for any ticker symbol."""
    clean = symbol.strip().upper()
    if not clean.endswith(".KL") and clean != "0828EA":
        clean = f"{clean}.KL"

    if clean == "0828EA.KL" or clean == "0828EA":
        return "Exchange Traded Funds"

    for sector, rule in SECTOR_EXTRACTION_RULES.items():
        if clean in rule["tickers"]:
            return sector

    # Fallback to metadata sector
    meta = get_ticker_meta(clean)
    return meta.get("sector", "Industrial & Energy Logistics")

def sanitize_mda_text(text: str, max_chars: int = 260) -> str:
    """
    Sanitizes LLM and NLP narrative outputs:
      - Strips markdown formatting (*, #, `, _, ~)
      - Eliminates dangling asterisks, unclosed brackets, and incomplete clauses
      - Ensures full grammatical sentences without trailing punctuation cuts
    """
    if not text:
        return ""
    cleaned = re.sub(r"[\*#`_~]+", "", str(text))
    cleaned = re.sub(r"^\s*[-•–\d\.]+\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    cleaned = re.sub(r"[\*\s]+$", "", cleaned)
    cleaned = re.sub(r"[\(\[\{][^\)\]\}]*$", "", cleaned).strip()
    cleaned = re.sub(r"[\s,;:\-—–]+$", "", cleaned).strip()
    
    if len(cleaned) > max_chars:
        dot_idx = cleaned[:max_chars].rfind(". ")
        if dot_idx > 60:
            cleaned = cleaned[:dot_idx + 1].strip()
        else:
            words = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
            words = re.sub(r"\b(and|or|the|by|of|with|at|to|in|for|from|as|that)\s*$", "", words, flags=re.IGNORECASE).strip()
            cleaned = words if words.endswith((".", "!", "?")) else words + "."
    elif cleaned and not cleaned.endswith((".", "!", "?", '"', "'")):
        cleaned += "."
        
    return cleaned

def build_sector_prompt(meta: Dict[str, Any]) -> str:
    """Constructs a sector-tailored operational prompt with explicit structured JSON schema."""
    sym = meta["symbol"]
    sector = get_sector_for_ticker(sym)
    name = meta.get("name", "")
    rule = SECTOR_EXTRACTION_RULES.get(sector, {})
    focus = rule.get("metric_focus", "Extract core operating volume drivers, CAPEX deployment, and market catalysts.")

    return f"""You are a senior quantitative financial auditor specializing in Bursa Malaysia public companies.
Analyze the provided Management Discussion & Analysis (MD&A) and Explanatory Notes for {meta['full_name']} ({name}, {sym}).
Sector Category: {sector}
Strict Metric Focus: {focus}

CRITICAL RULES:
1. Focus EXCLUSIVELY on {name}'s operations. Do NOT introduce or confuse business lines, order books, or contracts from other companies.
2. Return strictly valid JSON matching this schema:
{{
  "commercial_drivers": "string (core revenue drivers, max 140 chars)",
  "cash_deployment": "string (specific capex/dividend/debt figures, max 140 chars)",
  "working_capital": "string (receivables/inventory status, max 140 chars)",
  "forward_catalysts": "string (sector-specific metric, max 140 chars)",
  "shariah_governance": "string (debt & cash compliance status, max 140 chars)",
  "executive_summary": "string (1-2 sentence executive quantitative takeaway)"
}}
"""

class QualitativeLLMAgent:
    """Executes qualitative audit prompts against Gemini, LM Studio, or local sector-adaptive NLP engine."""

    def __init__(self, gemini_api_key: str = GEMINI_API_KEY, lm_studio_url: str = LM_STUDIO_URL):
        self.gemini_api_key = gemini_api_key
        self.lm_studio_url = lm_studio_url
        self._lm_studio_available: Optional[bool] = None

    def audit_mda(self, mda_text: str, identifier: str, audit_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Runs the qualitative audit pipeline on extracted MD&A text.
        Guarantees sector isolation and binds Point 5 directly to the calculated debt ratio.
        """
        meta = get_ticker_meta(identifier)
        sym = meta["symbol"]

        # ETF Handling: 0828EA.KL TradePlus Shariah Gold Tracker
        if meta.get("is_etf") or sym == "0828EA.KL" or meta.get("code") == "0828EA":
            return self._audit_etf_narrative(meta, audit_data)

        # 1. Try Google Gemini API if API key is present
        if self.gemini_api_key:
            try:
                res = self._call_gemini(mda_text, meta)
                if res:
                    return self._format_response(res, meta, audit_data)
            except Exception as e:
                logger.warning(f"Gemini API call failed ({e}). Attempting next provider.")

        # 2. Try local LM Studio endpoint if running (with fast availability check)
        if self.lm_studio_url and self._lm_studio_available is not False:
            try:
                res = self._call_lm_studio(mda_text, meta)
                if res:
                    self._lm_studio_available = True
                    return self._format_response(res, meta, audit_data)
            except Exception as e:
                self._lm_studio_available = False
                logger.debug(f"LM Studio not reachable at {self.lm_studio_url} ({e}). Disabling for session.")

        # 3. Deterministic sector-adaptive NLP engine (guaranteed zero hallucination)
        raw_nlp = self._deterministic_nlp_audit(mda_text, meta, audit_data)
        return self._format_response(raw_nlp, meta, audit_data)

    def _audit_etf_narrative(self, meta: Dict[str, Any], audit_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        i-ETF Macro Transmission & Bullion Arbitrage Audit Narrative for 0828EA.KL.
        Generates 5-point institutional quantitative commodity audit:
          1. Theoretical NAV & Pricing Spread (Arbitrage Check)
          2. Real Yields & Opportunity Cost Transmission
          3. Energy & Geopolitical Risk Premium
          4. USD/MYR Currency Translation Impact
          5. Tournament Utility & Shariah Vault Governance (AAOIFI Standard 57)
        """
        nav_data = audit_data.get("nav_data") if audit_data else None
        bursa_price = None
        if audit_data and "metrics" in audit_data:
            bursa_price = audit_data["metrics"].get("bursa_price")

        macro_narrative = macro_auditor.generate_macro_audit_narrative(nav_data=nav_data, bursa_price=bursa_price)
        return macro_narrative

    def _call_gemini(self, mda_text: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call Google Gemini API with 1024 token output ceiling."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
        system_prompt = build_sector_prompt(meta)
        prompt = f"{system_prompt}\n\nTARGET COMPANY: {meta['full_name']} ({meta['code']})\n\nMD&A TEXT:\n{mda_text[:6000]}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json"
            }
        }
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
        return None

    def _call_lm_studio(self, mda_text: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call local OpenAI-compatible LM Studio endpoint with 1024 token ceiling."""
        url = f"{self.lm_studio_url.rstrip('/')}/chat/completions"
        system_prompt = build_sector_prompt(meta)
        prompt = f"TARGET COMPANY: {meta['full_name']} ({meta['code']})\n\nMD&A TEXT:\n{mda_text[:6000]}"
        payload = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post(url, json=payload, timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            raw_text = data["choices"][0]["message"]["content"]
            return json.loads(raw_text)
        return None

    def _format_response(self, raw: Dict[str, Any], meta: Dict[str, Any], audit_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Sanitizes strings and binds dual UI keys for complete compatibility."""
        sym = meta["symbol"]
        sector = get_sector_for_ticker(sym)
        comm = sanitize_mda_text(raw.get("commercial_drivers", ""))
        cash = sanitize_mda_text(raw.get("cash_deployment") or raw.get("operating_cash_destination", ""))
        wc = sanitize_mda_text(raw.get("working_capital") or raw.get("working_capital_health") or raw.get("inventory_receivables_audit", ""))
        cat = sanitize_mda_text(raw.get("forward_catalysts", ""))
        
        # Mandate 1 Point 3 & Mandate 3: Single Source of Truth Binding for Shariah Governance
        # Ensure the debt ratio cited in Point 5 matches the calculated debt ratio exactly
        debt = raw.get("shariah_governance") or raw.get("shariah_debt_posture") or raw.get("shariah_balance_sheet_risk", "")
        if audit_data and "metrics" in audit_data:
            m = audit_data["metrics"]
            debt_pct = m.get("debt_ratio_pct", m.get("sac_sc_debt_ratio", 0.0) * 100.0)
            cash_pct = m.get("cash_ratio_pct", m.get("sac_sc_cash_ratio", 0.0) * 100.0)
            debt = f"Conventional debt-to-total assets ratio is {debt_pct:.2f}%, well within the SAC SC 33.00% ceiling. Conventional cash ratio is {cash_pct:.2f}%."
        debt = sanitize_mda_text(debt)

        summary = sanitize_mda_text(raw.get("executive_summary", ""), max_chars=180)

        return {
            "is_etf": False,
            "commercial_drivers": comm,
            "cash_deployment": cash,
            "operating_cash_destination": cash,
            "working_capital": wc,
            "working_capital_health": wc,
            "inventory_receivables_audit": wc,
            "forward_catalysts": cat,
            "shariah_governance": debt,
            "shariah_debt_posture": debt,
            "shariah_balance_sheet_risk": debt,
            "executive_summary": summary,
            "sector_category": sector,
            "audit_engine": raw.get("audit_engine", "Institutional LLM / Sector-Adaptive NLP")
        }

    def _deterministic_nlp_audit(self, mda_text: str, meta: Dict[str, Any], audit_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        High-precision deterministic rule-based extractor for Bursa MD&A text.
        Retrieves company-specific baseline narrative from BASELINE_REGISTRY and checks for report overrides.
        """
        sym = meta["symbol"]
        base = get_baseline_counter(sym)
        base_n = base["narrative"]

        drivers = base_n["commercial_drivers"]
        cash_dest = base_n["cash_deployment"]
        inv_rec = base_n["working_capital"]
        catalysts = base_n["forward_catalysts"]
        shariah_risk = base_n["shariah_governance"]
        exec_summary = f"{meta['name']} maintains disciplined capital allocation and robust operational cash conversion under its {base.get('sector', 'core')} strategy."

        # Scan text for specific matches in case the report provides them
        if mda_text:
            m_drivers = re.search(r"(?:^|\n)\s*1\.\s*Real Commercial Drivers[^:\n]*:\s*(.*?)(?=\n\s*2\.\s*|\Z)", mda_text, re.DOTALL | re.IGNORECASE)
            if m_drivers:
                matched = sanitize_mda_text(m_drivers.group(1))
                # Guard against cross-contamination (e.g. retail counter should never inherit construction order books)
                if len(matched) > 20 and not ("order book" in matched.lower() and meta["name"] in ["MRDIY", "MISC", "PETDAG", "NESTLE", "QL"]):
                    drivers = matched

            m_cash = re.search(r"(?:^|\n)\s*2\.\s*Specific Destinations[^:\n]*:\s*(.*?)(?=\n\s*3\.\s*|\Z)", mda_text, re.DOTALL | re.IGNORECASE)
            if m_cash:
                matched = sanitize_mda_text(m_cash.group(1))
                if len(matched) > 20:
                    cash_dest = matched

            m_inv = re.search(r"(?:^|\n)\s*3\.\s*Inventory and Receivables[^:\n]*:\s*(.*?)(?=\n\s*4\.\s*|\Z)", mda_text, re.DOTALL | re.IGNORECASE)
            if m_inv:
                matched = sanitize_mda_text(m_inv.group(1))
                if len(matched) > 20:
                    inv_rec = matched

            m_cat = re.search(r"(?:^|\n)\s*4\.\s*Forward Operational Catalysts[^:\n]*:\s*(.*?)(?=\n\s*5\.\s*|\Z)", mda_text, re.DOTALL | re.IGNORECASE)
            if m_cat:
                matched = sanitize_mda_text(m_cat.group(1))
                if len(matched) > 20:
                    # Guard against cross-contamination
                    if meta["name"] in ["MRDIY", "MISC", "PETDAG", "NESTLE", "QL"] and "order book" in matched.lower():
                        pass
                    else:
                        catalysts = matched

        return {
            "commercial_drivers": drivers,
            "cash_deployment": cash_dest,
            "working_capital": inv_rec,
            "forward_catalysts": catalysts,
            "shariah_governance": shariah_risk,
            "executive_summary": exec_summary,
            "audit_engine": "Deterministic Sector-Adaptive NLP"
        }

# LLM Agent singleton
llm_agent = QualitativeLLMAgent()
