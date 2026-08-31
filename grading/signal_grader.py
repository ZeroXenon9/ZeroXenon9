"""
Signal grading.

Grade definitions
-----------------
A+        Weekly MACD bearish divergence (3 pivots, closed)
        + Daily  MACD bearish divergence (3 pivots, closed)
        + Unmitigated IFVG on 4H or above

A         Weekly MACD divergence confirmed
        + Any IFVG (mitigated or not), any timeframe

B+        Daily MACD divergence confirmed
        + Unmitigated IFVG on 4H or above

Watchlist Daily MACD divergence confirmed, no IFVG required
"""
from typing import Dict, Any, Optional

import pandas as pd

from indicators.macd_divergence import detect_bearish_divergence
from indicators.fvg import get_unmitigated_ifvg, get_latest_ifvg

GRADE_A_PLUS = "A+"
GRADE_A = "A"
GRADE_B_PLUS = "B+"
GRADE_WATCHLIST = "Watchlist"

# Timeframes considered "4H or above" for IFVG checks
_TF_4H_PLUS = ["1w", "1d", "4h"]
_TF_ALL = ["1w", "1d", "4h", "1h"]

# Grade rank for sorting / filtering
GRADE_RANK: Dict[Optional[str], int] = {
    None: 0,
    GRADE_WATCHLIST: 1,
    GRADE_B_PLUS: 2,
    GRADE_A: 3,
    GRADE_A_PLUS: 4,
}


def _divergence(dfs: Dict[str, pd.DataFrame], tf: str) -> Dict[str, Any]:
    df = dfs.get(tf)
    if df is None or len(df) < 50:
        return {"confirmed": False, "pivots": []}
    return detect_bearish_divergence(df)


def _find_ifvg(dfs: Dict[str, pd.DataFrame], timeframes, unmitigated_only: bool):
    for tf in timeframes:
        df = dfs.get(tf)
        if df is None or len(df) < 10:
            continue
        ifvg = get_unmitigated_ifvg(df) if unmitigated_only else get_latest_ifvg(df)
        if ifvg:
            return ifvg, tf
    return None, None


def grade_signal(symbol: str, dfs: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    """
    Grade the signal for `symbol`.

    Parameters
    ----------
    symbol : str
        Trading pair, e.g. ``"BTC/USDT"``.
    dfs : dict
        Mapping of timeframe string → closed-candle OHLCV DataFrame.
        Expected keys: ``"1w"``, ``"1d"``, ``"4h"``, ``"1h"``
        (missing / None keys are treated as no data).

    Returns
    -------
    dict with keys:
        ``symbol``, ``grade``, ``weekly_div``, ``daily_div``,
        ``ifvg``, ``ifvg_timeframe``.
    """
    weekly_div = _divergence(dfs, "1w")
    daily_div = _divergence(dfs, "1d")

    # Unmitigated IFVG on 4H or above (needed for A+ and B+)
    unmitigated_4h, unmitigated_4h_tf = _find_ifvg(dfs, _TF_4H_PLUS, unmitigated_only=True)

    # Any IFVG on any timeframe (needed for A)
    any_ifvg, any_ifvg_tf = _find_ifvg(dfs, _TF_ALL, unmitigated_only=False)

    # Grading – checked in priority order
    if weekly_div["confirmed"] and daily_div["confirmed"] and unmitigated_4h:
        grade = GRADE_A_PLUS
        ifvg_for_report, ifvg_tf = unmitigated_4h, unmitigated_4h_tf
    elif weekly_div["confirmed"] and any_ifvg:
        grade = GRADE_A
        ifvg_for_report, ifvg_tf = any_ifvg, any_ifvg_tf
    elif daily_div["confirmed"] and unmitigated_4h:
        grade = GRADE_B_PLUS
        ifvg_for_report, ifvg_tf = unmitigated_4h, unmitigated_4h_tf
    elif daily_div["confirmed"]:
        grade = GRADE_WATCHLIST
        ifvg_for_report, ifvg_tf = None, None
    else:
        grade = None
        ifvg_for_report, ifvg_tf = None, None

    return {
        "symbol": symbol,
        "grade": grade,
        "weekly_div": weekly_div,
        "daily_div": daily_div,
        "ifvg": ifvg_for_report,
        "ifvg_timeframe": ifvg_tf,
    }
