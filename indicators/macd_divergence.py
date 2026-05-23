"""
MACD divergence detection.

Bearish divergence: price making higher pivot highs while MACD histogram
makes lower highs at the same pivots.  Requires at least `min_pivots`
consecutive confirming pivot points, all on closed candles.
"""
from typing import Dict, Any

import pandas as pd

import config


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_macd(
    close: pd.Series,
    fast: int = None,
    slow: int = None,
    signal: int = None,
):
    fast = fast or config.MACD_FAST
    slow = slow or config.MACD_SLOW
    signal = signal or config.MACD_SIGNAL_PERIOD
    macd_line = _ema(close, fast) - _ema(close, slow)
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def find_pivot_highs(series: pd.Series, window: int = None) -> pd.Series:
    """
    Boolean series marking pivot highs.
    A candle is a pivot high when its value is the maximum within
    [i-window, i+window] (inclusive).
    """
    window = window or config.PIVOT_WINDOW
    pivot_mask = pd.Series(False, index=series.index)
    arr = series.values
    for i in range(window, len(arr) - window):
        if arr[i] == max(arr[i - window: i + window + 1]):
            pivot_mask.iloc[i] = True
    return pivot_mask


def detect_bearish_divergence(df: pd.DataFrame, min_pivots: int = 3) -> Dict[str, Any]:
    """
    Detect bearish MACD divergence on a closed-candle OHLCV DataFrame.

    Returns::

        {
            'confirmed': bool,
            'pivots': [
                {'candle_idx': int, 'timestamp': Timestamp,
                 'price_high': float, 'macd_histogram': float},
                ...
            ]
        }

    'confirmed' is True only when the last `min_pivots` pivot highs all show
    price making a higher high while the MACD histogram makes a lower high.
    """
    empty = {"confirmed": False, "pivots": []}

    if len(df) < config.MACD_SLOW + config.MACD_SIGNAL_PERIOD + config.PIVOT_WINDOW * 2 + 1:
        return empty

    _, _, histogram = compute_macd(df["close"])
    pivot_mask = find_pivot_highs(df["high"])
    pivot_indices = [i for i, v in enumerate(pivot_mask) if v]

    if len(pivot_indices) < min_pivots:
        return empty

    # Examine the most recent `min_pivots` pivots
    recent = pivot_indices[-min_pivots:]

    for i in range(1, len(recent)):
        prev, curr = recent[i - 1], recent[i]
        price_higher = float(df["high"].iloc[curr]) > float(df["high"].iloc[prev])
        macd_lower = float(histogram.iloc[curr]) < float(histogram.iloc[prev])
        if not (price_higher and macd_lower):
            return empty

    pivots = [
        {
            "candle_idx": idx,
            "timestamp": df.index[idx],
            "price_high": float(df["high"].iloc[idx]),
            "macd_histogram": float(histogram.iloc[idx]),
        }
        for idx in recent
    ]
    return {"confirmed": True, "pivots": pivots}
