"""
Bursa Strategy Simulation & Risk Management Engine - Trailing Stops & Portfolio Sizer
Implements Daily Kijun-sen, ATR trailing stops, Time-decay rules, and Fractional Unit execution.
Starting fund strictly RM 50.00 (Competition Rubric: i-ETF [0/2], Fractional [0/2], Total [0/5]).
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd

from config.settings import (
    INITIAL_CAPITAL_MYR,
    MIN_FRACTIONAL_UNITS,
    DECIMAL_PLACES_UNITS
)
from config.universe import get_ticker_meta
from factors.ichimoku import calculate_ichimoku
from factors.volume_volatility import calculate_volume_volatility

logger = logging.getLogger("bursa.simulation.exit")

class PortfolioManager:
    """Manages tournament positions, fractional share execution, and trailing stop audits."""

    def __init__(self, initial_cash: float = INITIAL_CAPITAL_MYR):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        # positions map: symbol -> dict
        self.positions: Dict[str, Dict[str, Any]] = {}
        # trade history log
        self.trade_log: List[Dict[str, Any]] = []

    def calculate_fractional_units(self, amount_myr: float, current_price: float) -> float:
        """Calculate fractional units to exact 4 decimal places."""
        if current_price <= 0:
            return 0.0
        raw_units = amount_myr / current_price
        return round(raw_units, DECIMAL_PLACES_UNITS)

    def calculate_allocation_value(self, units: float, current_price: float) -> float:
        """Calculate MYR allocation value from units and price."""
        return round(units * current_price, 4)

    def execute_order(
        self, 
        action: str, 
        identifier: str, 
        units: Optional[float] = None,
        amount_myr: Optional[float] = None, 
        price_override: Optional[float] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Executes a simulated fractional order (BUY or SELL).
        Supports fractional share allocation with minimum 0.01 units.
        """
        meta = get_ticker_meta(identifier)
        sym = meta["symbol"]
        action = action.upper()

        price = price_override
        if price is None or price <= 0:
            price = 4.39

        # Determine exact units to trade
        if units is not None and units > 0:
            trade_units = round(units, DECIMAL_PLACES_UNITS)
        elif amount_myr is not None and amount_myr > 0:
            trade_units = self.calculate_fractional_units(amount_myr, price)
        else:
            return {"success": False, "error": "Must specify either units (> 0.01) or amount_myr."}

        if trade_units < MIN_FRACTIONAL_UNITS:
            return {
                "success": False,
                "error": f"Minimum fractional trade size is {MIN_FRACTIONAL_UNITS} units."
            }

        total_value = round(trade_units * price, 4)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "BUY":
            if self.cash < total_value:
                return {
                    "success": False,
                    "error": f"Insufficient cash buffer (Available: RM {self.cash:.2f}, Required: RM {total_value:.2f})"
                }
            self.cash = round(self.cash - total_value, 4)

            if sym in self.positions:
                pos = self.positions[sym]
                old_units = pos["units"]
                old_cost = pos["cost_basis"] * old_units
                new_units = round(old_units + trade_units, DECIMAL_PLACES_UNITS)
                new_cost_basis = (old_cost + total_value) / new_units if new_units > 0 else price
                pos["units"] = new_units
                pos["cost_basis"] = round(new_cost_basis, 3)
                pos["current_price"] = price
                pos["market_value"] = round(pos["units"] * price, 4)
                pos["unrealized_pnl"] = round(pos["market_value"] - (pos["cost_basis"] * pos["units"]), 2)
                pos["unrealized_pnl_pct"] = round((price - pos["cost_basis"]) / pos["cost_basis"] * 100, 2)
            else:
                self.positions[sym] = {
                    "symbol": sym,
                    "code": meta["code"],
                    "name": meta["name"],
                    "sector": meta["sector"],
                    "is_etf": meta.get("is_etf", False),
                    "units": trade_units,
                    "cost_basis": round(price, 3),
                    "current_price": round(price, 3),
                    "market_value": total_value,
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_pct": 0.0,
                    "entry_date": now_str,
                    "days_held": 1,
                    "kijun_stop": round(price * 0.96, 3),
                    "atr_stop": round(price * 0.94, 3)
                }

        elif action == "SELL":
            if sym not in self.positions or self.positions[sym]["units"] < trade_units:
                curr_units = self.positions[sym]["units"] if sym in self.positions else 0
                return {
                    "success": False,
                    "error": f"Cannot sell {trade_units} units. Position has {curr_units} units."
                }
            
            pos = self.positions[sym]
            pos["units"] = round(pos["units"] - trade_units, DECIMAL_PLACES_UNITS)
            pos["market_value"] = round(pos["units"] * price, 4)
            self.cash = round(self.cash + total_value, 4)

            if pos["units"] <= 0.0001:
                del self.positions[sym]

        else:
            return {"success": False, "error": f"Invalid action: {action}"}

        trade_record = {
            "timestamp": now_str,
            "action": action,
            "symbol": sym,
            "name": meta["name"],
            "is_etf": meta.get("is_etf", False),
            "units": trade_units,
            "price": round(price, 3),
            "total_myr": total_value,
            "remaining_cash": round(self.cash, 2),
            "notes": notes
        }
        self.trade_log.append(trade_record)
        logger.info(f"Executed {action} {trade_units} units of {sym} at RM {price:.3f} (Total: RM {total_value:.2f})")

        return {
            "success": True,
            "trade": trade_record,
            "rubric": self.get_rubric_metrics()
        }

    def update_position_prices(self, price_map: Dict[str, float], ichi_map: Optional[Dict[str, float]] = None):
        """Update market values and trailing stop levels for all open positions."""
        for sym, pos in self.positions.items():
            if sym in price_map:
                curr_p = price_map[sym]
                pos["current_price"] = round(curr_p, 3)
                pos["market_value"] = round(pos["units"] * curr_p, 4)
                pnl = (curr_p - pos["cost_basis"]) * pos["units"]
                pos["unrealized_pnl"] = round(pnl, 2)
                pos["unrealized_pnl_pct"] = round(((curr_p - pos["cost_basis"]) / pos["cost_basis"]) * 100, 2)

            if ichi_map and sym in ichi_map:
                kijun_val = ichi_map[sym]
                pos["kijun_stop"] = round(kijun_val, 3)

    def run_stop_audit(self, current_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Audit open positions for exit triggers:
          1. Daily Kijun-sen breach: Close < Kijun-sen
          2. ATR Chandelier Exit: Close < Highest_High_22 - 2.5*ATR
          3. Time decay: Days held >= 25 trading days
        """
        alerts: List[Dict[str, Any]] = []

        for sym, pos in self.positions.items():
            df = current_data.get(sym)
            if df is None or len(df) < 30:
                continue

            ichi = calculate_ichimoku(df)
            vol = calculate_volume_volatility(df)

            last_bar = ichi.iloc[-1]
            last_vol = vol.iloc[-1]
            
            close = float(last_bar["Close"])
            kijun = float(last_bar["kijun_sen"])
            atr = float(last_vol.get("atr_14", 0.0))
            recent_high = float(df["High"].iloc[-22:].max())
            atr_stop = recent_high - (2.5 * atr)

            pos["kijun_stop"] = round(kijun, 3)
            pos["atr_stop"] = round(atr_stop, 3)

            triggers = []
            if close < kijun:
                triggers.append({
                    "rule": "KIJUN-SEN TRAILING STOP",
                    "severity": "CRITICAL",
                    "detail": f"Close RM {close:.3f} < Daily Kijun RM {kijun:.3f} (Breach)"
                })
            
            if close < atr_stop:
                triggers.append({
                    "rule": "ATR CHANDELIER STOP",
                    "severity": "HIGH",
                    "detail": f"Close RM {close:.3f} < Chandelier Stop RM {atr_stop:.3f}"
                })

            if pos.get("days_held", 0) >= 25:
                triggers.append({
                    "rule": "TIME DECAY EXIT",
                    "severity": "MEDIUM",
                    "detail": f"Position held {pos.get('days_held')} days (Tournament Sprint Limit Reached)"
                })

            if triggers:
                alerts.append({
                    "symbol": sym,
                    "name": pos["name"],
                    "units": pos["units"],
                    "cost_basis": pos["cost_basis"],
                    "current_price": close,
                    "unrealized_pnl_pct": pos["unrealized_pnl_pct"],
                    "triggers": triggers,
                    "action_recommended": "EXIT / LIQUIDATE POSITION",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                })

        return alerts

    def get_rubric_metrics(self) -> Dict[str, Any]:
        """
        Evaluate tournament rubric criteria:
          - i-ETF Trades [target: >= 2]
          - Fractional Trades [target: >= 2]
          - Total Trades [target: >= 5]
        """
        etf_trades = sum(1 for t in self.trade_log if t.get("is_etf", False))
        fractional_trades = sum(1 for t in self.trade_log if not t.get("is_etf", False))
        total_trades = len(self.trade_log)

        market_val_sum = sum(p["market_value"] for p in self.positions.values())
        total_equity = round(self.cash + market_val_sum, 2)
        total_pnl = round(total_equity - self.initial_cash, 2)
        total_pnl_pct = round((total_pnl / self.initial_cash) * 100.0, 2) if self.initial_cash > 0 else 0.0

        return {
            "etf_trades_count": etf_trades,
            "etf_trades_target": 2,
            "etf_compliant": etf_trades >= 2,
            "etf_badge": f"[{min(etf_trades, 2)}/2]",
            "fractional_trades_count": fractional_trades,
            "fractional_trades_target": 2,
            "fractional_compliant": fractional_trades >= 2,
            "fractional_badge": f"[{min(fractional_trades, 2)}/2]",
            "total_trades_count": total_trades,
            "total_trades_target": 5,
            "total_compliant": total_trades >= 5,
            "total_badge": f"[{total_trades}/5]",
            "all_rubrics_satisfied": (etf_trades >= 2 and fractional_trades >= 2 and total_trades >= 5),
            "cash_balance": round(self.cash, 2),
            "total_equity": total_equity,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "open_positions_count": len(self.positions)
        }

# Portfolio singleton initialized with RM 50.00
portfolio = PortfolioManager(initial_cash=INITIAL_CAPITAL_MYR)
