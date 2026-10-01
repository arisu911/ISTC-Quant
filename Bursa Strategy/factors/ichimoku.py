"""
Bursa Strategy Quantitative Factor Engine - Ichimoku Kinko Hyo
Vectorized calculation of standard 9-26-52 periods + discrete composite momentum scoring (-5 to +5).
Pure NumPy and Pandas vectorized operations for high-speed institutional screening.
"""

from typing import Dict, Any, Tuple, List
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from config.settings import (
    ICHIMOKU_TENKAN_PERIOD,
    ICHIMOKU_KIJUN_PERIOD,
    ICHIMOKU_SPAN_B_PERIOD,
    ICHIMOKU_DISPLACEMENT
)

def calculate_ichimoku(
    df: pd.DataFrame,
    tenkan_period: int = ICHIMOKU_TENKAN_PERIOD,
    kijun_period: int = ICHIMOKU_KIJUN_PERIOD,
    span_b_period: int = ICHIMOKU_SPAN_B_PERIOD,
    displacement: int = ICHIMOKU_DISPLACEMENT
) -> pd.DataFrame:
    """
    Calculate vectorized Ichimoku Kinko Hyo components.
    Input df must contain 'High', 'Low', 'Close'.
    
    Returns DataFrame with:
      - 'tenkan_sen'
      - 'kijun_sen'
      - 'span_a_current' (Span A aligned to current bar t)
      - 'span_b_current' (Span B aligned to current bar t)
      - 'span_a_fwd' (Span A forward projection)
      - 'span_b_fwd' (Span B forward projection)
      - 'chikou_span' (Close shifted back 26 bars)
      - 'kumo_top'
      - 'kumo_bottom'
    """
    res = df.copy()
    
    # Assert Non-Zero Rolling Windows: enforce strictly positive prices
    valid_low = res["Low"].replace(0, np.nan).ffill().bfill()
    valid_high = res["High"].replace(0, np.nan).ffill().bfill()
    valid_close = res["Close"].replace(0, np.nan).ffill().bfill()

    # Fallback guard against any lingering non-positive prices
    if (valid_low <= 0).any() or valid_low.isna().any():
        valid_low = valid_low.mask(valid_low <= 0).fillna(1.0)
    if (valid_high <= 0).any() or valid_high.isna().any():
        valid_high = valid_high.mask(valid_high <= 0).fillna(1.0)

    # Tenkan-sen (Conversion Line): (9-period High + 9-period Low) / 2
    high_9 = valid_high.rolling(window=tenkan_period, min_periods=tenkan_period).max()
    low_9 = valid_low.rolling(window=tenkan_period, min_periods=tenkan_period).min()
    res["tenkan_sen"] = (high_9 + low_9) / 2.0

    # Kijun-sen (Base Line): (26-period High + 26-period Low) / 2
    high_26 = valid_high.rolling(window=kijun_period, min_periods=kijun_period).max()
    low_26 = valid_low.rolling(window=kijun_period, min_periods=kijun_period).min()
    res["kijun_sen"] = (high_26 + low_26) / 2.0

    # Raw Span A & B at bar t
    raw_span_a = (res["tenkan_sen"] + res["kijun_sen"]) / 2.0
    high_52 = valid_high.rolling(window=span_b_period, min_periods=span_b_period).max()
    low_52 = valid_low.rolling(window=span_b_period, min_periods=span_b_period).min()
    raw_span_b = (high_52 + low_52) / 2.0

    # In classic trading, the Cloud visible at bar t is Span A and Span B calculated 26 periods ago
    res["span_a_current"] = raw_span_a.shift(displacement)
    res["span_b_current"] = raw_span_b.shift(displacement)

    # Forward Kumo (Span A and B plotted 26 periods ahead)
    res["span_a_fwd"] = raw_span_a
    res["span_b_fwd"] = raw_span_b

    # Kumo boundaries for current price bar
    res["kumo_top"] = np.maximum(res["span_a_current"], res["span_b_current"])
    res["kumo_bottom"] = np.minimum(res["span_a_current"], res["span_b_current"])

    # Chikou Span: Current close compared against close 26 periods ago
    res["chikou_ref_price"] = valid_close.shift(displacement)

    return res

def score_ichimoku_momentum(df_ichimoku: pd.DataFrame) -> Tuple[float, Dict[str, Any]]:
    """
    Computes discrete composite momentum score (-5.0 to +5.0 scale) for the latest available bar:
      1. Cloud Position: +1.0 if Close > max(Span A, Span B), -1.0 if Close < min(Span A, Span B)
      2. Tenkan/Kijun Cross & Position: 
         - +1.0 if Tenkan > Kijun above Cloud (+0.5 if inside Cloud)
         - -1.0 if Tenkan < Kijun below Cloud (-0.5 if inside Cloud)
      3. Chikou Clearance: +1.0 if Chikou has unobstructed clearance above price 26 periods ago (-1.0 if below)
      4. Forward Kumo Trend: +1.0 if Forward Kumo is green (Span A > Span B) and expanding in thickness (-1.0 if red & expanding)
      5. Slopes: +1.0 if both Tenkan and Kijun have positive daily slopes (dTenkan/dt > 0 and dKijun/dt > 0) (-1.0 if both negative)
    """
    if len(df_ichimoku) < 55:
        return 0.0, {"error": "Insufficient history for Ichimoku scoring"}

    # Use the most recent valid bar
    last = df_ichimoku.iloc[-1]
    prev = df_ichimoku.iloc[-2]
    
    close = float(last["Close"])
    tenkan = float(last["tenkan_sen"])
    kijun = float(last["kijun_sen"])
    kumo_top = float(last["kumo_top"]) if pd.notna(last["kumo_top"]) else float(tenkan)
    kumo_bot = float(last["kumo_bottom"]) if pd.notna(last["kumo_bottom"]) else float(kijun)

    # 1. Cloud Position (-1.0 to +1.0)
    score_cloud = 0.0
    cloud_state = "Inside Cloud"
    if close > kumo_top:
        score_cloud = 1.0
        cloud_state = "Above Cloud (Bullish)"
    elif close < kumo_bot:
        score_cloud = -1.0
        cloud_state = "Below Cloud (Bearish)"

    # 2. Tenkan / Kijun Cross & Location (-1.0 to +1.0)
    score_tk = 0.0
    tk_state = "Neutral"
    if tenkan > kijun:
        if close > kumo_top:
            score_tk = 1.0
            tk_state = "TK Bullish Cross Above Cloud"
        else:
            score_tk = 0.5
            tk_state = "TK Bullish Cross Inside/Below Cloud"
    elif tenkan < kijun:
        if close < kumo_bot:
            score_tk = -1.0
            tk_state = "TK Bearish Cross Below Cloud"
        else:
            score_tk = -0.5
            tk_state = "TK Bearish Cross Inside/Above Cloud"

    # 3. Chikou Clearance (-1.0 to +1.0)
    score_chikou = 0.0
    chikou_state = "Neutral"
    chikou_ref = last.get("chikou_ref_price", np.nan)
    if pd.notna(chikou_ref):
        if close > float(chikou_ref) * 1.005:
            score_chikou = 1.0
            chikou_state = "Clear Unobstructed Above Price"
        elif close < float(chikou_ref) * 0.995:
            score_chikou = -1.0
            chikou_state = "Obstructed Below Price"
        else:
            score_chikou = 0.0
            chikou_state = "Testing Historical Price"

    # 4. Forward Kumo Thickness & Color (-1.0 to +1.0)
    score_fwd = 0.0
    fwd_state = "Neutral"
    fwd_span_a = float(last["span_a_fwd"])
    fwd_span_b = float(last["span_b_fwd"])
    prev_fwd_a = float(prev["span_a_fwd"])
    prev_fwd_b = float(prev["span_b_fwd"])
    
    current_diff = fwd_span_a - fwd_span_b
    prev_diff = prev_fwd_a - prev_fwd_b

    if current_diff > 0: # Green forward cloud
        if current_diff >= prev_diff:
            score_fwd = 1.0
            fwd_state = "Green Kumo Expanding (+1.0)"
        else:
            score_fwd = 0.5
            fwd_state = "Green Kumo Contracting (+0.5)"
    else: # Red forward cloud
        if current_diff <= prev_diff:
            score_fwd = -1.0
            fwd_state = "Red Kumo Expanding (-1.0)"
        else:
            score_fwd = -0.5
            fwd_state = "Red Kumo Contracting (-0.5)"

    # 5. Dual Slopes dTenkan/dt and dKijun/dt (-1.0 to +1.0)
    score_slope = 0.0
    slope_state = "Flat"
    d_tenkan = tenkan - float(prev["tenkan_sen"])
    d_kijun = kijun - float(prev["kijun_sen"])
    
    if d_tenkan > 0 and d_kijun > 0:
        score_slope = 1.0
        slope_state = "Both Slopes Positive (+1.0)"
    elif d_tenkan >= 0 and d_kijun >= 0 and (d_tenkan > 0 or d_kijun > 0):
        score_slope = 0.5
        slope_state = "Tenkan or Kijun Rising (+0.5)"
    elif d_tenkan < 0 and d_kijun < 0:
        score_slope = -1.0
        slope_state = "Both Slopes Negative (-1.0)"
    elif d_tenkan <= 0 and d_kijun <= 0 and (d_tenkan < 0 or d_kijun < 0):
        score_slope = -0.5
        slope_state = "Tenkan or Kijun Falling (-0.5)"

    # Total Composite Score bounded between -5.0 and +5.0
    total_score = float(np.clip(
        score_cloud + score_tk + score_chikou + score_fwd + score_slope,
        -5.0,
        5.0
    ))

    breakdown = {
        "total_score": round(total_score, 1),
        "score_cloud": score_cloud,
        "cloud_state": cloud_state,
        "score_tk": score_tk,
        "tk_state": tk_state,
        "score_chikou": score_chikou,
        "chikou_state": chikou_state,
        "score_fwd": score_fwd,
        "fwd_state": fwd_state,
        "score_slope": score_slope,
        "slope_state": slope_state,
        "tenkan": round(tenkan, 3),
        "kijun": round(kijun, 3),
        "span_a": round(kumo_top, 3),
        "span_b": round(kumo_bot, 3),
    }

    return total_score, breakdown

def generate_future_timestamps(last_ts: Any, interval: str = "1d", count: int = 26) -> List[int]:
    """
    Project forward Span A & B timestamps using Unix epoch seconds:
      - '1h': incremented by 3600s
      - '4h': incremented by 14400s
      - '1d': incremented by 86400s
    """
    interval = (interval or "1d").lower()
    last_dt = pd.to_datetime(last_ts)
    last_epoch = int(last_dt.timestamp())

    if interval == "1h":
        step = 3600
    elif interval == "4h":
        step = 14400
    else:
        step = 86400

    return [last_epoch + (i + 1) * step for i in range(count)]

def build_ichimoku_chart_series(
    df: pd.DataFrame, 
    ichi_df: pd.DataFrame, 
    interval: str = "1d"
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Format Tenkan-sen, Kijun-sen, Chikou Span, Span A, and Span B for TradingView Lightweight Charts.
    Projects Span A and Span B forward by +26 bars into the blank future chart space using Unix epoch seconds.
    Shifts Chikou Span backward by -26 bars.
    """
    interval = (interval or "1d").lower()
    
    def _format_time(ts: Any) -> int:
        if isinstance(ts, (int, float)):
            return int(ts)
        p_ts = pd.to_datetime(ts)
        return int(p_ts.timestamp())

    tenkan_series = []
    kijun_series = []
    chikou_series = []
    span_a_series = []
    span_b_series = []

    if df.empty or ichi_df.empty:
        return {
            "tenkan": tenkan_series,
            "kijun": kijun_series,
            "chikou": chikou_series,
            "span_a": span_a_series,
            "span_b": span_b_series,
        }

    idx_list = list(df.index)
    n_bars = len(idx_list)

    # 1. Tenkan & Kijun + Historical Span A & Span B
    for idx in idx_list:
        t_val = _format_time(idx)
        if idx in ichi_df.index:
            t_tenkan = ichi_df.loc[idx, "tenkan_sen"]
            if pd.notna(t_tenkan) and float(t_tenkan) > 0:
                tenkan_series.append({"time": t_val, "value": round(float(t_tenkan), 3)})
            
            t_kijun = ichi_df.loc[idx, "kijun_sen"]
            if pd.notna(t_kijun) and float(t_kijun) > 0:
                kijun_series.append({"time": t_val, "value": round(float(t_kijun), 3)})

            # Historical Span A & Span B (shifted from 26 bars ago)
            sa = ichi_df.loc[idx, "span_a_current"]
            if pd.notna(sa) and float(sa) > 0:
                span_a_series.append({"time": t_val, "value": round(float(sa), 3)})
            sb = ichi_df.loc[idx, "span_b_current"]
            if pd.notna(sb) and float(sb) > 0:
                span_b_series.append({"time": t_val, "value": round(float(sb), 3)})

    # 2. Chikou Span: Close shifted backward 26 bars (plotted at bar i - 26 with Close of bar i)
    displacement = 26
    for i in range(displacement, n_bars):
        past_idx = idx_list[i - displacement]
        curr_close = df.iloc[i]["Close"]
        if pd.notna(curr_close) and float(curr_close) > 0:
            chikou_series.append({
                "time": _format_time(past_idx),
                "value": round(float(curr_close), 3)
            })

    # 3. Future 26-bar projection for Span A and Span B
    raw_span_a = (ichi_df["tenkan_sen"] + ichi_df["kijun_sen"]) / 2.0
    raw_span_b = ichi_df["span_b_fwd"] if "span_b_fwd" in ichi_df else (df["High"].rolling(52).max() + df["Low"].rolling(52).min()) / 2.0

    last_ts = idx_list[-1]
    fwd_timestamps = generate_future_timestamps(last_ts, interval=interval, count=26)

    span_slice_a = raw_span_a.iloc[-26:].dropna()
    span_slice_b = raw_span_b.iloc[-26:].dropna()

    for j, f_ts in enumerate(fwd_timestamps):
        f_time_val = _format_time(f_ts)
        if j < len(span_slice_a):
            val_a = span_slice_a.iloc[j]
            if pd.notna(val_a) and float(val_a) > 0:
                span_a_series.append({"time": f_time_val, "value": round(float(val_a), 3)})
        if j < len(span_slice_b):
            val_b = span_slice_b.iloc[j]
            if pd.notna(val_b) and float(val_b) > 0:
                span_b_series.append({"time": f_time_val, "value": round(float(val_b), 3)})

    return {
        "tenkan": tenkan_series,
        "kijun": kijun_series,
        "chikou": chikou_series,
        "span_a": span_a_series,
        "span_b": span_b_series,
    }

