"""
Bursa Strategy Quantitative Factor Engine - Volume Z-Score & Volatility Squeeze
Vectorized institutional volume accumulation, Bollinger Bandwidth (BBW), and ATR% contraction.
"""

from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

from config.settings import (
    VOLUME_SMA_PERIOD,
    INSTITUTIONAL_Z_SCORE_THRESHOLD,
    BOLLINGER_PERIOD,
    BOLLINGER_STD_DEV,
    ATR_PERIOD
)

def calculate_volume_volatility(
    df: pd.DataFrame,
    vol_period: int = VOLUME_SMA_PERIOD,
    bb_period: int = BOLLINGER_PERIOD,
    bb_std: float = BOLLINGER_STD_DEV,
    atr_period: int = ATR_PERIOD
) -> pd.DataFrame:
    """
    Computes vectorized Volume Z-Score, Bollinger Bandwidth, and ATR% metrics.
    Input df must contain 'High', 'Low', 'Close', 'Volume'.
    """
    res = df.copy()
    close = res["Close"]
    high = res["High"]
    low = res["Low"]
    volume = res["Volume"]

    # 1. Volume Z-Score: Z_vol = (Volume - SMA_20(Volume)) / StdDev_20(Volume)
    vol_sma = volume.rolling(window=vol_period).mean()
    vol_std = volume.rolling(window=vol_period).std(ddof=0)
    # Prevent division by zero
    vol_std_safe = vol_std.replace(0, np.nan).fillna(1.0)
    res["volume_sma20"] = vol_sma
    res["volume_z_score"] = (volume - vol_sma) / vol_std_safe
    res["institutional_acc"] = res["volume_z_score"] >= INSTITUTIONAL_Z_SCORE_THRESHOLD

    # 2. Bollinger Bands & Bandwidth (BBW)
    close_sma = close.rolling(window=bb_period).mean()
    close_std = close.rolling(window=bb_period).std(ddof=0)
    res["bb_upper"] = close_sma + (bb_std * close_std)
    res["bb_middle"] = close_sma
    res["bb_lower"] = close_sma - (bb_std * close_std)
    
    # BBW = (Upper - Lower) / SMA_20(Close)
    res["bb_bandwidth"] = (res["bb_upper"] - res["bb_lower"]) / close_sma.replace(0, np.nan)
    # 20-day rolling minimum of BBW
    res["bbw_min20"] = res["bb_bandwidth"].rolling(window=20).min()
    
    # 3. ATR & ATR% Contraction
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    res["true_range"] = true_range
    res["atr_14"] = true_range.rolling(window=atr_period).mean()
    res["atr_pct"] = (res["atr_14"] / close.replace(0, np.nan)) * 100.0

    # 4. Volatility Squeeze Detection: BBW near 20-day low and ATR% contracting
    # Check if current BBW <= rolling 20-day min * 1.05 (tight band compression)
    res["volatility_squeeze"] = (res["bb_bandwidth"] <= (res["bbw_min20"] * 1.05))

    return res

def get_latest_volume_metrics(df_calc: pd.DataFrame) -> Dict[str, Any]:
    """Extract summary metrics from the latest row."""
    if df_calc.empty:
        return {}

    last = df_calc.iloc[-1]
    z_vol = float(last.get("volume_z_score", 0.0))
    bbw = float(last.get("bb_bandwidth", 0.0))
    atr_pct = float(last.get("atr_pct", 0.0))
    squeeze = bool(last.get("volatility_squeeze", False))
    inst_acc = bool(last.get("institutional_acc", False))

    return {
        "volume_z_score": round(z_vol, 2),
        "institutional_accumulation": inst_acc,
        "bb_bandwidth": round(bbw * 100, 2), # In percentage points
        "atr_pct": round(atr_pct, 2),
        "volatility_squeeze": squeeze,
        "last_volume": int(last.get("Volume", 0)),
        "avg_volume_20": int(last.get("volume_sma20", 0) if pd.notna(last.get("volume_sma20")) else 0)
    }
