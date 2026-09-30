"""
Bursa Strategy Quantitative Trading Terminal - Global Settings
Configured for dual-display workstation and Edge/Brave browser environment.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
REPORTS_DIR = DATA_DIR / "reports"
SIMULATION_DIR = BASE_DIR / "simulation"
SERVER_DIR = BASE_DIR / "server"
UI_DIR = BASE_DIR / "ui"
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"

# Ensure runtime directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Server Configuration
HOST = os.getenv("BURSA_HOST", "0.0.0.0")
PORT = int(os.getenv("BURSA_PORT", 8000))
WS_PATH = "/ws/channel"

# Benchmark Symbols
BENCHMARK_PRIMARY = "^KLSE"          # FTSE Bursa Malaysia KLCI (yfinance primary)
BENCHMARK_SHARIAH = "FBMS.KL"        # FTSE Bursa Malaysia EMAS Shariah
BENCHMARK_FALLBACK = "^KLSE"

# Dual-Display Profiles
DISPLAY_TOWER = {
    "name": "Tower Display (Portrait)",
    "width": 1440,
    "height": 2560,
    "route": "/tower",
    "target": "Vertical Monitor"
}

DISPLAY_DESK = {
    "name": "Desk Display (Widescreen)",
    "width": 1920,
    "height": 1080,
    "route": "/desk",
    "target": "Horizontal Laptop Workspace"
}

# Tournament & Capital Constants (RM 50.00 starting fund)
INITIAL_CAPITAL_MYR = 50.00          # RM 50.00 tournament allocation fund
MIN_FRACTIONAL_TRADE_MYR = 0.05      # Minimum fractional share purchase
MIN_FRACTIONAL_UNITS = 0.01          # Minimum 0.01 units
FRACTIONAL_UNIT_STEP = 0.01          # 0.01 units step
DEFAULT_TRADE_UNIT_MYR = 5.00        # Standard quick allocation
DECIMAL_PLACES_UNITS = 4             # Bursa fractional 4 decimal places (0.0001 units)

# Real-Time Data Pipeline Parameters
TICK_POLL_INTERVAL_SECONDS = 3       # Poll yfinance fast_info every 3-5 seconds
MAX_BARS_WINDOW = 250                # Fixed sliding window to prevent memory leaks

# Tournament Calendar Dates (2026 Season)
DATE_TOURNAMENT_OPEN = "2026-10-05"  # 5 Oct 2026 - AVWAP Anchor 1
DATE_BUDGET_2027 = "2026-10-09"      # 9 Oct 2026 - Federal Budget Day (AVWAP Anchor 2)
DATE_BURSA_3Q26_RESULTS = "2026-10-28" # 28 Oct 2026 - Bursa Earnings
DATE_CHALLENGE_END = "2026-11-13"    # 13 Nov 2026 - Challenge Finale

# Quantitative Factor Parameters
ICHIMOKU_TENKAN_PERIOD = 9
ICHIMOKU_KIJUN_PERIOD = 26
ICHIMOKU_SPAN_B_PERIOD = 52
ICHIMOKU_DISPLACEMENT = 26

VOLUME_SMA_PERIOD = 20
INSTITUTIONAL_Z_SCORE_THRESHOLD = 2.0
BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2.0
ATR_PERIOD = 14
CMF_PERIOD = 21

# SAC Securities Commission Malaysia Shariah Ratios (< 33% threshold)
SAC_SC_MAX_CASH_RATIO = 0.33
SAC_SC_MAX_DEBT_RATIO = 0.33

# Browser Target Configurations (Zero Chrome Dependency)
BROWSER_CANDIDATES = [
    # Microsoft Edge paths
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")),
    # Brave Browser paths
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
    Path(os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")),
    Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
]

# Hardware Acceleration & High-Performance Browser Flags
BROWSER_LAUNCH_FLAGS = [
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--new-window"
]

# AI Studio / LM Studio API configurations
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
