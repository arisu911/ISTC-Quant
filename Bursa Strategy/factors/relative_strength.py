"""
Bursa Strategy Quantitative Factor Engine - Mansfield Relative Strength (MRS) & Alpha
Vectorized MRS vs FBMS.KL / ^KLSE benchmark and rolling 10D/30D institutional alpha.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

def calculate_mansfield_rs(
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    mrs_period: int = 20
) -> pd.DataFrame:
    """
    Computes Mansfield Relative Strength (MRS) vs Benchmark (FBMS.KL / ^KLSE).
    Formula:
      Base RS = Close(Stock) / Close(Benchmark)
      MRS = ((Base RS / SMA_20(Base RS)) - 1.0) * 100
    Also computes:
      - Rolling 10-day Alpha: Return_10D(Stock) - Return_10D(Benchmark)
      - Rolling 30-day Alpha: Return_30D(Stock) - Return_30D(Benchmark)
    """
    res = stock_df.copy()
    
    # Align dates on common index
    common_idx = stock_df.index.intersection(benchmark_df.index)
    if len(common_idx) < 25:
        # Fallback if alignment is small: align forward-fill
        combined = pd.DataFrame({
            "stock_close": stock_df["Close"],
            "bench_close": benchmark_df["Close"]
        }).ffill().dropna()
    else:
        combined = pd.DataFrame({
            "stock_close": stock_df.loc[common_idx, "Close"],
            "bench_close": benchmark_df.loc[common_idx, "Close"]
        }, index=common_idx)

    # 1. Base RS
    base_rs = combined["stock_close"] / combined["bench_close"].replace(0, np.nan)
    base_rs_sma = base_rs.rolling(window=mrs_period).mean()
    
    # 2. Mansfield Relative Strength: ((Base RS / SMA_20(Base RS)) - 1.0) * 100
    mrs = ((base_rs / base_rs_sma.replace(0, np.nan)) - 1.0) * 100.0
    
    # 3. MRS Slope (dMRS/dt)
    mrs_slope = mrs - mrs.shift(1)

    # 4. Rolling 10D & 30D Returns and Alpha
    stock_ret10 = combined["stock_close"].pct_change(10) * 100.0
    bench_ret10 = combined["bench_close"].pct_change(10) * 100.0
    alpha_10d = stock_ret10 - bench_ret10

    stock_ret30 = combined["stock_close"].pct_change(30) * 100.0
    bench_ret30 = combined["bench_close"].pct_change(30) * 100.0
    alpha_30d = stock_ret30 - bench_ret30

    res["base_rs"] = base_rs
    res["mrs"] = mrs
    res["mrs_slope"] = mrs_slope
    res["alpha_10d"] = alpha_10d
    res["alpha_30d"] = alpha_30d
    res["outperforming"] = (res["mrs"] > 0) & (res["mrs_slope"] > 0)

    return res

def get_latest_rs_metrics(df_rs: pd.DataFrame) -> Dict[str, Any]:
    """Extract latest relative strength and alpha metrics."""
    if df_rs.empty:
        return {}

    last = df_rs.iloc[-1]
    mrs_val = float(last.get("mrs", 0.0))
    mrs_slope = float(last.get("mrs_slope", 0.0))
    alpha_10d = float(last.get("alpha_10d", 0.0))
    alpha_30d = float(last.get("alpha_30d", 0.0))
    outperf = bool(last.get("outperforming", False))

    return {
        "mrs": round(mrs_val, 2),
        "mrs_slope": round(mrs_slope, 2),
        "alpha_10d": round(alpha_10d, 2),
        "alpha_30d": round(alpha_30d, 2),
        "outperforming": outperf,
        "mrs_state": "Rising Outperformance (+)" if outperf else ("Underperforming (-)" if mrs_val < 0 else "Neutral")
    }
