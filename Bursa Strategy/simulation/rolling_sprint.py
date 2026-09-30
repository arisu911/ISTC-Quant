"""
Bursa Strategy Simulation Engine - 25-Trading-Day Rolling Sprint Tournament Backtester
Evaluates probability of achieving +20% sprint return (P(Return >= 20%)) over rolling 25-day horizons.
Vectorized matrix calculations for high-velocity quantitative simulation.
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd

from config.settings import ICHIMOKU_KIJUN_PERIOD
from factors.ichimoku import calculate_ichimoku

class RollingSprintSimulator:
    """Simulates 25-trading-day sprint windows to evaluate tournament success probabilities."""

    def __init__(self, sprint_length_days: int = 25, target_return_pct: float = 20.0):
        self.sprint_length = sprint_length_days
        self.target_return_pct = target_return_pct

    def run_sprint_backtest(
        self, 
        df: pd.DataFrame, 
        ticker_symbol: str = "5211.KL"
    ) -> Dict[str, Any]:
        """
        Runs rolling 25-day windows across available historical data.
        Computes win rate, P(Return >= 20%), max drawdown, and risk-adjusted metrics.
        """
        if len(df) < self.sprint_length + 20:
            return {"error": "Insufficient historical data for 25-day rolling sprint"}

        close = df["Close"].values
        high = df["High"].values
        low = df["Low"].values
        n_bars = len(close)

        num_windows = n_bars - self.sprint_length
        window_returns = []
        window_max_returns = []
        window_drawdowns = []
        hit_target_count = 0
        positive_return_count = 0

        for i in range(num_windows):
            start_price = close[i]
            if start_price <= 0:
                continue

            window_close = close[i + 1 : i + 1 + self.sprint_length]
            window_high = high[i + 1 : i + 1 + self.sprint_length]
            window_low = low[i + 1 : i + 1 + self.sprint_length]

            # Final 25-day terminal return
            end_price = window_close[-1]
            term_ret = ((end_price - start_price) / start_price) * 100.0
            window_returns.append(term_ret)

            if term_ret > 0:
                positive_return_count += 1

            # Maximum Favorable Excursion (peak return inside the 25-day sprint)
            max_price = np.max(window_high)
            peak_ret = ((max_price - start_price) / start_price) * 100.0
            window_max_returns.append(peak_ret)

            if peak_ret >= self.target_return_pct:
                hit_target_count += 1

            # Max Adverse Excursion (max drawdown inside the 25-day sprint)
            min_price = np.min(window_low)
            dd = ((min_price - start_price) / start_price) * 100.0
            window_drawdowns.append(min(0.0, dd))

        window_returns = np.array(window_returns)
        window_max_returns = np.array(window_max_returns)
        window_drawdowns = np.array(window_drawdowns)

        total_tested = len(window_returns)
        if total_tested == 0:
            return {"error": "No valid windows generated"}

        prob_hit_target = (hit_target_count / total_tested) * 100.0
        win_rate = (positive_return_count / total_tested) * 100.0
        mean_return = float(np.mean(window_returns))
        median_return = float(np.median(window_returns))
        p90_return = float(np.percentile(window_returns, 90))
        max_return = float(np.max(window_max_returns))
        avg_drawdown = float(np.mean(window_drawdowns))
        max_drawdown = float(np.min(window_drawdowns))

        # Sharpe ratio approximation over sprint windows (annualized from 25-day blocks)
        std_return = float(np.std(window_returns))
        sharpe = (mean_return / std_return) * np.sqrt(250 / self.sprint_length) if std_return > 0 else 0.0

        # Sortino ratio (downside deviation only)
        downside = window_returns[window_returns < 0]
        downside_std = float(np.std(downside)) if len(downside) > 0 else 1.0
        sortino = (mean_return / downside_std) * np.sqrt(250 / self.sprint_length) if downside_std > 0 else 0.0

        # Profit factor
        gross_profit = float(np.sum(window_returns[window_returns > 0])) if np.any(window_returns > 0) else 0.0
        gross_loss = float(abs(np.sum(window_returns[window_returns < 0]))) if np.any(window_returns < 0) else 1.0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

        return {
            "ticker": ticker_symbol,
            "sprint_length_days": self.sprint_length,
            "target_return_pct": self.target_return_pct,
            "total_windows_tested": total_tested,
            "prob_return_gte_20": round(prob_hit_target, 2), # P(Return >= 20%)
            "win_rate_pct": round(win_rate, 2),
            "mean_terminal_return_pct": round(mean_return, 2),
            "median_terminal_return_pct": round(median_return, 2),
            "p90_terminal_return_pct": round(p90_return, 2),
            "max_sprint_return_pct": round(max_return, 2),
            "avg_sprint_drawdown_pct": round(avg_drawdown, 2),
            "max_sprint_drawdown_pct": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "profit_factor": profit_factor,
            "tournament_rating": "ELITE SPRINT RUNNER" if prob_hit_target >= 25 else ("SOLID CONTENDER" if prob_hit_target >= 12 else "DEFENSIVE COMPOUNDER")
        }

# Simulator singleton
rolling_sprint_simulator = RollingSprintSimulator()
