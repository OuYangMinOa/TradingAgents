"""Technical indicator calculation using pandas-ta."""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta


def _safe(series: pd.Series, idx: int = -1) -> float | None:
    """Extract a float from a Series, returning None for NaN."""
    try:
        val = series.iloc[idx]
        return None if pd.isna(val) else float(val)
    except (IndexError, TypeError):
        return None


def calculate_indicators(ohlcv: list[dict]) -> dict:
    """Calculate all required technical indicators from OHLCV data.

    Args:
        ohlcv: list of dicts with keys: date, open, high, low, close, volume
               sorted oldest→newest.

    Returns:
        dict of latest indicator values (None where insufficient data).
    """
    df = pd.DataFrame(ohlcv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    volume = df["volume"].astype(float)

    # MACD (12, 26, 9)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)

    # RSI (14)
    rsi = ta.rsi(close, length=14)

    # Bollinger Bands (20, 2)
    bb = ta.bbands(close, length=20, std=2)

    # KD / Stochastic (9, 3, 3)
    stoch = ta.stoch(high, low, close, k=9, d=3, smooth_k=3)

    # Simple Moving Averages
    ma5  = ta.sma(close, length=5)
    ma10 = ta.sma(close, length=10)
    ma20 = ta.sma(close, length=20)
    ma60 = ta.sma(close, length=60)

    # Volume moving averages
    vol5  = ta.sma(volume, length=5)
    vol20 = ta.sma(volume, length=20)

    # ADX (14)
    adx_df = ta.adx(high, low, close, length=14)

    snapshot = {
        "close":      _safe(close),
        "macd":       _safe(macd_df["MACD_12_26_9"])       if macd_df  is not None else None,
        "macd_signal":_safe(macd_df["MACDs_12_26_9"])      if macd_df  is not None else None,
        "macd_hist":  _safe(macd_df["MACDh_12_26_9"])      if macd_df  is not None else None,
        "rsi":        _safe(rsi),
        "bb_upper":   _safe(bb["BBU_20_2.0"])              if bb       is not None else None,
        "bb_mid":     _safe(bb["BBM_20_2.0"])              if bb       is not None else None,
        "bb_lower":   _safe(bb["BBL_20_2.0"])              if bb       is not None else None,
        "k":          _safe(stoch["STOCHk_9_3_3"])         if stoch    is not None else None,
        "d":          _safe(stoch["STOCHd_9_3_3"])         if stoch    is not None else None,
        "ma5":        _safe(ma5),
        "ma10":       _safe(ma10),
        "ma20":       _safe(ma20),
        "ma60":       _safe(ma60),
        "vol5":       _safe(vol5),
        "vol20":      _safe(vol20),
        "adx":        _safe(adx_df["ADX_14"])              if adx_df   is not None else None,
    }

    # Price positions relative to key MAs (for prompt context)
    c = snapshot["close"] or 0
    snapshot["above_ma20"] = c > (snapshot["ma20"] or 0) if snapshot["ma20"] else None
    snapshot["above_ma60"] = c > (snapshot["ma60"] or 0) if snapshot["ma60"] else None

    return snapshot


def estimate_support_resistance(ohlcv: list[dict], window: int = 20) -> tuple[float, float]:
    """Simple support/resistance: low/high of recent window."""
    recent = ohlcv[-window:] if len(ohlcv) >= window else ohlcv
    lows   = [r["low"]  for r in recent]
    highs  = [r["high"] for r in recent]
    return min(lows), max(highs)
