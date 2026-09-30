"""
Bursa Strategy WebSocket Hub - Multi-Display State Synchronization
Manages real-time bi-directional synchronization between Display 1 (Tower) and Display 2 (Desk).
Engineered for Microsoft Edge and Brave Browser (Shields compatible, zero dropped frames).
"""

import json
import logging
from typing import Set, Dict, Any, List
from fastapi import WebSocket

logger = logging.getLogger("bursa.server.wshub")

class WebSocketHub:
    """Manages active WebSocket connections across displays and broadcasts events."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.current_state: Dict[str, Any] = {
            "selected_ticker": "5211.KL",
            "selected_name": "SUNWAY",
            "last_scan_time": None,
            "logs": []
        }

    async def connect(self, websocket: WebSocket):
        """Register a new display connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Active displays: {len(self.active_connections)}")
        
        # Send initial state snapshot on connection
        await websocket.send_text(json.dumps({
            "event": "STATE_SNAPSHOT",
            "state": self.current_state
        }))

    def disconnect(self, websocket: WebSocket):
        """Deregister disconnected display."""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Remaining displays: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast event to all connected screens (Tower and Desk)."""
        payload = json.dumps(message)
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client ({e}), marking for cleanup.")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_ticker_select(self, ticker: str, name: str):
        """Broadcast synchronized ticker selection across all screens."""
        self.current_state["selected_ticker"] = ticker
        self.current_state["selected_name"] = name
        await self.broadcast({
            "event": "TICKER_SELECT",
            "ticker": ticker,
            "ticker_symbol": ticker,
            "name": name
        })

    async def broadcast_fundamental_update(self, payload: Dict[str, Any]):
        """Broadcast structured FUNDAMENTAL_UPDATE event across all screens."""
        self.current_state["latest_fundamental"] = payload
        await self.broadcast(payload)

    async def broadcast_log(self, message: str, level: str = "INFO", tag: str = "SYSTEM"):
        """Broadcast live system telemetry log event."""
        log_entry = {
            "timestamp": logger.handlers[0].formatter.formatTime(logging.LogRecord("", 0, "", 0, "", (), None)) if logger.handlers else "",
            "level": level,
            "tag": tag,
            "message": message
        }
        # Keep ring buffer of last 50 logs
        self.current_state["logs"].append(log_entry)
        if len(self.current_state["logs"]) > 50:
            self.current_state["logs"].pop(0)

        await self.broadcast({
            "event": "LOG_EVENT",
            "log": log_entry
        })

# Global WebSocket Hub instance
ws_hub = WebSocketHub()
