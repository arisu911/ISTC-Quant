"""
Bursa Strategy Catalyst Horizon & Trading Tournament Schedule
Calendar calculations for key macro catalysts, policy milestones, and tournament deadlines.
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Any

# Malaysian Market Holidays (Q3/Q4 2026 reference)
BURSA_HOLIDAYS_2026 = {
    date(2026, 8, 31),  # National Day
    date(2026, 9, 16),  # Malaysia Day
    date(2026, 9, 24),  # Maulidur Rasul
    date(2026, 11, 8),  # Deepavali
    date(2026, 11, 9),  # Deepavali replacement
    date(2026, 12, 25), # Christmas Day
}

CATALYST_EVENTS: List[Dict[str, Any]] = [
    {
        "id": "tourn_open",
        "title": "Tournament Kickoff",
        "date_str": "2026-10-05",
        "tag": "TOURNAMENT",
        "badge_color": "var(--neon-teal)",
        "description": "First day of fractional sprint competition. AVWAP Base Anchor set.",
        "sectors_impacted": ["All Universe", "i-ETF"],
        "avwap_anchor": True
    },
    {
        "id": "budget_2027",
        "title": "Federal Budget 2027",
        "date_str": "2026-10-09",
        "tag": "FISCAL MACRO",
        "badge_color": "var(--gold)",
        "description": "Tabling of Malaysia Budget 2027 by Ministry of Finance. Infrastructure, NETR, and semi funding catalysts.",
        "sectors_impacted": ["Utilities (TENAGA)", "Conglomerates (SUNWAY)", "Tech (INARI, PENTA)", "Plantations"],
        "avwap_anchor": True
    },
    {
        "id": "bursa_3q26",
        "title": "Bursa 3Q26 Results",
        "date_str": "2026-10-28",
        "tag": "EARNINGS DISCLOSURE",
        "badge_color": "var(--cyber-blue)",
        "description": "Bursa Malaysia 3Q26 financial results release. Signals retail/institutional trading velocity and ADV.",
        "sectors_impacted": ["Financial Markets", "High-beta Equities"],
        "avwap_anchor": False
    },
    {
        "id": "earnings_rush_3q",
        "title": "Peak 3Q26 QR Season",
        "date_str": "2026-11-06",
        "tag": "QUARTERLY AUDIT",
        "badge_color": "var(--neon-purple)",
        "description": "Mandatory filing deadline for June/Sept quarter reports. Fundamental auditor triggers active.",
        "sectors_impacted": ["Industrial", "Plantations (IOICORP, KLK)", "Healthcare (IHH)"],
        "avwap_anchor": False
    },
    {
        "id": "tourn_finale",
        "title": "Challenge Finale & Stop Audit",
        "date_str": "2026-11-13",
        "tag": "TOURNAMENT CLOSE",
        "badge_color": "var(--neon-pink)",
        "description": "Competition terminal close. Portfolio liquidation and rubric verification deadline.",
        "sectors_impacted": ["All Universe", "Cash Settlement"],
        "avwap_anchor": False
    }
]

def calculate_trading_days(from_date: date, to_date: date) -> int:
    """Calculate number of Bursa trading days between two dates (excluding weekends and Bursa holidays)."""
    if from_date >= to_date:
        return 0
    
    current = from_date + timedelta(days=1)
    trading_days = 0
    while current <= to_date:
        if current.weekday() < 5 and current not in BURSA_HOLIDAYS_2026: # Monday - Friday
            trading_days += 1
        current += timedelta(days=1)
    return trading_days

def get_catalyst_telemetry(as_of: date = None) -> List[Dict[str, Any]]:
    """Return enriched catalyst list with trading and calendar day countdowns."""
    if as_of is None:
        # Default to current date (or fixed test baseline 2026-09-29)
        as_of = date.today()
    
    results = []
    for ev in CATALYST_EVENTS:
        target_d = datetime.strptime(ev["date_str"], "%Y-%m-%d").date()
        cal_days = (target_d - as_of).days
        trad_days = calculate_trading_days(as_of, target_d)
        
        status = "UPCOMING"
        if cal_days < 0:
            status = "PASSED"
        elif cal_days == 0:
            status = "TODAY"
            
        results.append({
            **ev,
            "calendar_days_remaining": cal_days,
            "trading_days_remaining": trad_days,
            "status": status,
            "formatted_target": target_d.strftime("%d %b %Y")
        })
    return results
