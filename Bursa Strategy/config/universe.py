"""
Bursa Malaysia Whitelist Universe: 23 Permitted UP App Instruments
Strictly compliant with Securities Commission Malaysia (SAC SC) Shariah screening.
Consists of 1 Compliance i-ETF, 10 High Beta & Momentum, and 12 Blue Chips & Defensives.
All counters support Bursa Malaysia Fractional Share Trading (min 0.01 units).
"""

from typing import Dict, List, Any

UNIVERSE_DATA: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # Compliance i-ETF (1 Counter)
    # -------------------------------------------------------------------------
    {
        "symbol": "0828EA.KL",
        "code": "0828EA",
        "name": "GOLDETF",
        "full_name": "TradePlus Shariah Gold Tracker ETF",
        "category": "Compliance i-ETF",
        "sector": "Exchange Traded Funds",
        "subsector": "Commodity ETF - Physical Gold",
        "shariah": True,
        "fractional": True,
        "is_etf": True,
        "description": "Bursa Malaysia's premier Shariah-compliant physical gold ETF backing each unit with 99.5% LBMA gold bars.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=0828EA"
    },

    # -------------------------------------------------------------------------
    # High Beta & Momentum (10 Counters)
    # -------------------------------------------------------------------------
    {
        "symbol": "5136.KL",
        "code": "5136",
        "name": "HEXTECH",
        "full_name": "Hexbase Technologies Berhad",
        "category": "High Beta & Momentum",
        "sector": "Technology",
        "subsector": "Software & Digital Logistics Platforms",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "High-beta technology company scaling fintech mobile applications and cross-border digital logistics ecosystems.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5136"
    },
    {
        "symbol": "5211.KL",
        "code": "5211",
        "name": "SUNWAY",
        "full_name": "Sunway Berhad",
        "category": "High Beta & Momentum",
        "sector": "Industrial & Conglomerate",
        "subsector": "Diversified Conglomerates",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Conglomerate with high-margin Healthcare (IPO pipeline), Property Development, and Construction (AI data centers & LRT).",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5211"
    },
    {
        "symbol": "8869.KL",
        "code": "8869",
        "name": "PMETAL",
        "full_name": "Press Metal Aluminium Holdings Berhad",
        "category": "High Beta & Momentum",
        "sector": "Industrial Products",
        "subsector": "Low-Carbon Aluminium Smelting",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Largest integrated aluminium producer in Southeast Asia powered by Sarawak hydro-power.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=8869"
    },
    {
        "symbol": "1818.KL",
        "code": "1818",
        "name": "BURSA",
        "full_name": "Bursa Malaysia Berhad",
        "category": "High Beta & Momentum",
        "sector": "Financial Exchange",
        "subsector": "Exchange Operator & Derivatives",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "National securities exchange monopoly benefiting directly from surging equity ADV, retail participation, and IPO listings.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=1818"
    },
    {
        "symbol": "5347.KL",
        "code": "5347",
        "name": "TENAGA",
        "full_name": "Tenaga Nasional Berhad",
        "category": "High Beta & Momentum",
        "sector": "Utilities",
        "subsector": "Conventional Electricity & Grid",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "National grid monopoly and prime beneficiary of the National Energy Transition Roadmap (NETR) and data center energy demand.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5347"
    },
    {
        "symbol": "4863.KL",
        "code": "4863",
        "name": "TM",
        "full_name": "Telekom Malaysia Berhad",
        "category": "High Beta & Momentum",
        "sector": "Telecommunications",
        "subsector": "Fixed Broadband & Data Centers",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "National fiber backbone operator with expanding hyperscaler submarine cable landings and cloud data centers in Cyberjaya/Kulai.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=4863"
    },
    {
        "symbol": "5296.KL",
        "code": "5296",
        "name": "MRDIY",
        "full_name": "MR D.I.Y. Group (M) Berhad",
        "category": "High Beta & Momentum",
        "sector": "Consumer Products",
        "subsector": "Home Improvement & Value Retail",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Malaysia's largest value home improvement retailer with aggressive store expansion and superior cash conversion cycle.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5296"
    },
    {
        "symbol": "3816.KL",
        "code": "3816",
        "name": "MISC",
        "full_name": "MISC Berhad",
        "category": "High Beta & Momentum",
        "sector": "Transportation & Logistics",
        "subsector": "LNG Carriers & Offshore Assets",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Global energy maritime solutions leader with long-term LNG carrier charters and expanding deepwater FPSO operations.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=3816"
    },
    {
        "symbol": "5183.KL",
        "code": "5183",
        "name": "PCHEM",
        "full_name": "Petronas Chemicals Group Berhad",
        "category": "High Beta & Momentum",
        "sector": "Industrial Products",
        "subsector": "Commodity & Specialty Chemicals",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Petrochemical leader benefiting from Pengerang Integrated Complex ramp-up and cyclical chemical spread recovery.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5183"
    },
    {
        "symbol": "5681.KL",
        "code": "5681",
        "name": "PETDAG",
        "full_name": "Petronas Dagangan Berhad",
        "category": "High Beta & Momentum",
        "sector": "Consumer Products",
        "subsector": "Retail Fuel & Convenience Stores",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Dominant retail fuel network and Mesra convenience retail benefiting from domestic mobility and targeted subsidy clarity.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5681"
    },

    # -------------------------------------------------------------------------
    # Blue Chips & Defensives (12 Counters)
    # -------------------------------------------------------------------------
    {
        "symbol": "6012.KL",
        "code": "6012",
        "name": "MAXIS",
        "full_name": "Maxis Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Telecommunications",
        "subsector": "Mobile & Enterprise ICT Solutions",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Premier Malaysian telecommunications and converged connectivity provider with stable postpaid cash flows.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=6012"
    },
    {
        "symbol": "6947.KL",
        "code": "6947",
        "name": "CDB",
        "full_name": "CelcomDigi Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Telecommunications",
        "subsector": "Mobile Telecommunications Network",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Largest mobile operator in Malaysia post-merger, capturing OPEX/CAPEX network synergies and enterprise 5G contracts.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=6947"
    },
    {
        "symbol": "6888.KL",
        "code": "6888",
        "name": "AXIATA",
        "full_name": "Axiata Group Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Telecommunications",
        "subsector": "Regional Telco & EDOTCO Towers",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Regional ASEAN telecom operator with balance sheet deleveraging catalyst via Edotco tower portfolio monetization.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=6888"
    },
    {
        "symbol": "4707.KL",
        "code": "4707",
        "name": "NESTLE",
        "full_name": "Nestle (Malaysia) Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Consumer Products",
        "subsector": "Food & Beverage Staples",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Blue-chip consumer staples powerhouse with formidable brand equity, pricing power, and defensive dividend yield.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=4707"
    },
    {
        "symbol": "6033.KL",
        "code": "6033",
        "name": "PETGAS",
        "full_name": "Petronas Gas Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Utilities",
        "subsector": "Gas Transmission & Regasification",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Stable regulated asset base under Incentive-Based Regulation (IBR) providing defensive high-dividend cash flows.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=6033"
    },
    {
        "symbol": "5225.KL",
        "code": "5225",
        "name": "IHH",
        "full_name": "IHH Healthcare Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Healthcare",
        "subsector": "Healthcare Providers & Hospitals",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Global premium healthcare provider with sustained inpatient volume growth across Malaysia, Singapore, and international hubs.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5225"
    },
    {
        "symbol": "4197.KL",
        "code": "4197",
        "name": "SIME",
        "full_name": "Sime Darby Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Consumer / Industrial",
        "subsector": "Automotive & Heavy Equipment",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Industrial Caterpillar distributor and luxury automotive dealer consolidating UMW Holdings for Malaysian market leadership.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=4197"
    },
    {
        "symbol": "7084.KL",
        "code": "7084",
        "name": "QL",
        "full_name": "QL Resources Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Consumer Products",
        "subsector": "Agro-Food Manufacturing & Marine Products",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Resilient agro-food manufacturer, surimi producer, and master franchisee of FamilyMart convenience stores in Malaysia.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=7084"
    },
    {
        "symbol": "4065.KL",
        "code": "4065",
        "name": "PPB",
        "full_name": "PPB Group Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Consumer Products",
        "subsector": "Grains, Agribusiness & Golden Screen Cinemas",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Diversified conglomerate holding an 18.8% equity stake in Wilmar International alongside premier flour milling assets.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=4065"
    },
    {
        "symbol": "1961.KL",
        "code": "1961",
        "name": "IOICORP",
        "full_name": "IOI Corporation Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Plantation",
        "subsector": "Integrated Agribusiness",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Integrated upstream plantation and downstream oleochemical manufacturer with robust FCF and low CPO production costs.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=1961"
    },
    {
        "symbol": "2445.KL",
        "code": "2445",
        "name": "KLK",
        "full_name": "Kuala Lumpur Kepong Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Plantation",
        "subsector": "Agribusiness & Oleochemicals",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Tier-1 plantation conglomerate with European downstream oleochemical operations and conservative leverage structure.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=2445"
    },
    {
        "symbol": "5285.KL",
        "code": "5285",
        "name": "SDG",
        "full_name": "SD Guthrie Berhad",
        "category": "Blue Chips & Defensives",
        "sector": "Plantation",
        "subsector": "Palm Oil & Renewable Energy Land",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "World's largest certified sustainable palm oil producer unlocking land bank value for solar parks and green industrial estates.",
        "bursa_page": "https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company=5285"
    }
]

# Lookup Maps
SYMBOL_MAP: Dict[str, Dict[str, Any]] = {item["symbol"]: item for item in UNIVERSE_DATA}
CODE_MAP: Dict[str, Dict[str, Any]] = {item["code"]: item for item in UNIVERSE_DATA}
NAME_MAP: Dict[str, Dict[str, Any]] = {item["name"]: item for item in UNIVERSE_DATA}

ALL_SYMBOLS: List[str] = [item["symbol"] for item in UNIVERSE_DATA]
SHARIAH_FRACTIONAL_SYMBOLS: List[str] = [item["symbol"] for item in UNIVERSE_DATA if not item["is_etf"]]
ETF_SYMBOLS: List[str] = [item["symbol"] for item in UNIVERSE_DATA if item["is_etf"]]

def get_ticker_meta(identifier: str) -> Dict[str, Any]:
    """Resolve identifier (symbol with/without .KL, 4-digit code, or ticker name)."""
    clean_id = identifier.strip().upper()
    if clean_id in SYMBOL_MAP:
        return SYMBOL_MAP[clean_id]
    if f"{clean_id}.KL" in SYMBOL_MAP:
        return SYMBOL_MAP[f"{clean_id}.KL"]
    if clean_id in CODE_MAP:
        return CODE_MAP[clean_id]
    if clean_id in NAME_MAP:
        return NAME_MAP[clean_id]
    # Default fallback
    return {
        "symbol": clean_id if clean_id.endswith(".KL") else f"{clean_id}.KL",
        "code": clean_id.replace(".KL", ""),
        "name": clean_id.replace(".KL", ""),
        "full_name": clean_id,
        "category": "Equities",
        "sector": "Equities",
        "subsector": "General",
        "shariah": True,
        "fractional": True,
        "is_etf": False,
        "description": "Bursa Malaysia listed security",
        "bursa_page": f"https://www.bursamalaysia.com/market_information/announcements/company_announcement?keyword=&cat=FA&company={clean_id.replace('.KL', '')}"
    }
