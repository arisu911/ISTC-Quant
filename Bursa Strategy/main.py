"""
Bursa Strategy Quantitative Trading Terminal - System Entrypoint
Auto-launches Uvicorn server and intelligently detects Microsoft Edge or Brave Browser.
Zero dependencies on Google Chrome. Dual-display workstation launcher (/tower & /desk).
"""

import os
import sys
import time
import argparse
import logging
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Optional, List, Tuple

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("bursa.main")

# Known Browser Installation Candidates in Windows
BROWSER_PATHS = {
    "edge": [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe")),
    ],
    "brave": [
        Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")),
        Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
}

def detect_browser(preferred: Optional[str] = None) -> Tuple[Optional[str], Optional[Path]]:
    """
    Intelligently detects Microsoft Edge or Brave Browser on the system.
    Returns (browser_name, executable_path).
    Ensures zero dependency on Google Chrome.
    """
    if preferred:
        pref = preferred.lower()
        if pref in BROWSER_PATHS:
            for p in BROWSER_PATHS[pref]:
                if p.exists():
                    return pref, p

    # Default detection order: Edge first, then Brave
    for b_name in ["edge", "brave"]:
        for p in BROWSER_PATHS[b_name]:
            if p.exists():
                return b_name, p

    return None, None

def launch_browser_tabs(
    host: str, 
    port: int, 
    launch_tower: bool = True, 
    launch_desk: bool = True,
    preferred_browser: Optional[str] = None
):
    """
    Wait for server to boot, then open Display 1 (/tower) and Display 2 (/desk) in Edge or Brave.
    """
    # Wait for server to bind port
    time.sleep(1.8)

    base_url = f"http://localhost:{port}" if host in ["0.0.0.0", "127.0.0.1"] else f"http://{host}:{port}"
    urls = []
    if launch_tower:
        urls.append(f"{base_url}/tower")
    if launch_desk:
        urls.append(f"{base_url}/desk")

    browser_name, exe_path = detect_browser(preferred_browser)

    if exe_path and exe_path.exists():
        logger.info(f"Targeting {browser_name.upper()} executable at: {exe_path}")
        from config.settings import BROWSER_LAUNCH_FLAGS
        for url in urls:
            try:
                cmd = [str(exe_path)] + BROWSER_LAUNCH_FLAGS + [url]
                subprocess.Popen(cmd)
                logger.info(f"Launched {browser_name.upper()} tab with GPU acceleration: {url}")
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Error launching {exe_path} ({e}). Falling back to URL protocol.")
                os.system(f"start microsoft-edge:{url}")
    else:
        # Fallback to microsoft-edge: protocol or default non-Chrome browser
        logger.info("Browser executable path not found directly. Using system protocol launcher.")
        for url in urls:
            try:
                os.system(f"start microsoft-edge:{url}")
            except Exception:
                webbrowser.open(url)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Bursa Strategy Quantitative Trading Terminal")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Start server without auto-opening browser tabs")
    parser.add_argument("--tower-only", action="store_true", help="Launch only Display 1 (Tower portrait)")
    parser.add_argument("--desk-only", action="store_true", help="Launch only Display 2 (Desk landscape)")
    parser.add_argument("--browser", choices=["edge", "brave"], default=None, help="Target specific browser (edge or brave)")
    return parser.parse_args()

def main():
    args = parse_arguments()

    logger.info("======================================================================")
    logger.info("  BURSA STRATEGY QUANTITATIVE TRADING TERMINAL & FACTOR SCREENER")
    logger.info("  Universe: 22 UP Shariah Fractional Equities + 0828EA GOLDETF")
    logger.info(f"  Display 1: Tower Monitor -> http://localhost:{args.port}/tower (1440x2560)")
    logger.info(f"  Display 2: Desk Workspace -> http://localhost:{args.port}/desk (1920x1080)")
    logger.info("  Browser Environment: Microsoft Edge / Brave Browser (Zero Chrome)")
    logger.info("======================================================================")

    # Launch browser thread if enabled
    if not args.no_browser:
        launch_tower = not args.desk_only
        launch_desk = not args.tower_only
        t = threading.Thread(
            target=launch_browser_tabs,
            args=(args.host, args.port, launch_tower, launch_desk, args.browser),
            daemon=True
        )
        t.start()

    # Start FastAPI with Uvicorn
    # Add project root to sys.path
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    uvicorn.run(
        "server.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()
