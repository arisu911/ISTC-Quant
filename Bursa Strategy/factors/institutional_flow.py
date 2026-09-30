"""
Bursa Strategy Quantitative Factor Engine - Anchored VWAP (AVWAP) & Chaikin Money Flow (CMF-21)
Vectorized AVWAP from tournament anchors (5 Oct / 9 Oct 2026) and institutional accumulation CMF.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from config.settings import DATE_TOURNAMENT_OPEN, DATE_BUDGET_2027, CMF_PERIOD

def calculate_anchored_vwap(
    df: pd.DataFrame,
    anchor_date: str = DATE_TOURNAMENT_OPEN,
    column_name: str = "avwap"
) -> pd.DataFrame:
    """
    Computes Anchored VWAP (AVWAP) starting strictly from the specified anchor date.
    Formula:
      Typical_Price = (High + Low + Close) / 3.0
      AVWAP = cumsum(Typical_Price * Volume) / cumsum(Volume)  [starting from anchor_date]
    If anchor_date is in the future relative to the dataset, anchor to the earliest bar or a recent pivot.
    """
    res = df.copy()
    typical_price = (res["High"] + res["Low"] + res["Close"]) / 3.0
    vol = res["Volume"]
    pv = typical_price * vol

    # Convert anchor date to timestamp, aligning timezone with DataFrame index
    anchor_ts = pd.to_datetime(anchor_date)
    if res.index.tz is not None:
        if anchor_ts.tz is None:
            anchor_ts = anchor_ts.tz_localize(res.index.tz)
        else:
            anchor_ts = anchor_ts.tz_convert(res.index.tz)
    elif anchor_ts.tz is not None:
        anchor_ts = anchor_ts.tz_localize(None)

    # Filter dates on or after anchor
    mask = res.index >= anchor_ts
    
    # If anchor is after the last date in the dataset, anchor to a 60-day lookback pivot
    if not mask.any():
        lookback_idx = max(0, len(res) - 60)
        mask = np.zeros(len(res), dtype=bool)
        mask[lookback_idx:] = True

    res[column_name] = np.nan
    cum_pv = pv[mask].cumsum()
    cum_vol = vol[mask].cumsum()
    
    # Avoid zero division
    cum_vol_safe = cum_vol.replace(0, np.nan)
    res.loc[mask, column_name] = cum_pv / cum_vol_safe
    
    # Forward-fill any minor gaps
    res[column_name] = res[column_name].ffill()

    return res

def calculate_chaikin_money_flow(
    df: pd.DataFrame,
    period: int = CMF_PERIOD
) -> pd.DataFrame:
    """
    Computes Chaikin Money Flow (CMF-21):
      MFM = ((Close - Low) - (High - Close)) / (High - Low)
      MFV = MFM * Volume
      CMF_21 = rolling_sum_21(MFV) / rolling_sum_21(Volume)
    Institutional buying pressure confirmed when CMF > +0.10.
    """
    res = df.copy()
    close = res["Close"]
    high = res["High"]
    low = res["Low"]
    volume = res["Volume"]

    hl_diff = high - low
    # Safe division for flat candle (High == Low)
    hl_diff_safe = hl_diff.replace(0, np.nan)

    mf_multiplier = ((close - low) - (high - close)) / hl_diff_safe
    mf_multiplier = mf_multiplier.fillna(0.0)

    mf_volume = mf_multiplier * volume
    
    sum_mfv = mf_volume.rolling(window=period).sum()
    sum_vol = volume.rolling(window=period).sum()
    
    sum_vol_safe = sum_vol.replace(0, np.nan)
    res["cmf_21"] = sum_mfv / sum_vol_safe
    res["institutional_buying"] = res["cmf_21"] > 0.10

    return res

def calculate_institutional_flows(
    df: pd.DataFrame,
    anchor_tourn: str = DATE_TOURNAMENT_OPEN,
    anchor_budget: str = DATE_BUDGET_2027
) -> pd.DataFrame:
    """Convenience pipeline calculating both Tournament AVWAP, Budget AVWAP, and CMF-21."""
    res = calculate_anchored_vwap(df, anchor_date=anchor_tourn, column_name="avwap_tournament")
    res = calculate_anchored_vwap(res, anchor_date=anchor_budget, column_name="avwap_budget")
    res = calculate_chaikin_money_flow(res, period=CMF_PERIOD)
    return res

def get_latest_flow_metrics(df_flow: pd.DataFrame) -> Dict[str, Any]:
    """Extract latest institutional flow metrics."""
    if df_flow.empty:
        return {}

    last = df_flow.iloc[-1]
    close = float(last["Close"])
    cmf = float(last.get("cmf_21", 0.0))
    avwap_tourn = float(last.get("avwap_tournament", 0.0)) if pd.notna(last.get("avwap_tournament")) else close
    avwap_budg = float(last.get("avwap_budget", 0.0)) if pd.notna(last.get("avwap_budget")) else close

    return {
        "cmf_21": round(cmf, 3),
        "institutional_buying": cmf > 0.10,
        "avwap_tournament": round(avwap_tourn, 3),
        "avwap_budget": round(avwap_budg, 3),
        "price_vs_avwap_tourn_pct": round(((close - avwap_tourn) / avwap_tourn) * 100, 2),
        "flow_bias": "STRONG ACCUMULATION" if cmf > 0.15 else ("ACCUMULATION" if cmf > 0.05 else ("DISTRIBUTION" if cmf < -0.05 else "NEUTRAL"))
    }
