"""
Fair Value Gap (FVG) and Inverted Fair Value Gap (IFVG) detection.

Boundaries use wicks (high/low), not bodies.

Bearish FVG (3-candle pattern):
  - Candle 1 low  > Candle 3 high  →  gap exists
  - Zone top    = candle 1 low
  - Zone bottom = candle 3 high

IFVG (Bearish FVG flipped to support):
  - After the FVG forms, a subsequent candle closes above zone_top
  - The zone then acts as support
  - Mitigated when any later candle closes at or below zone_top
    (i.e. back inside or below the zone)
"""
from typing import List, Optional, Dict, Any

import pandas as pd

import config


def detect_bearish_fvg(df: pd.DataFrame, min_gap_pct: float = None) -> List[Dict[str, Any]]:
    """
    Return every bearish FVG in `df` that meets the minimum gap size.

    Each entry::

        {
            'index': int,               # row index of candle 3
            'timestamp': Timestamp,
            'zone_top':    float,       # candle 1 low
            'zone_bottom': float,       # candle 3 high
            'gap_size':    float,
            'gap_pct':     float,       # gap_size / zone_top
        }
    """
    min_gap_pct = min_gap_pct if min_gap_pct is not None else config.MIN_FVG_GAP_PCT
    fvgs = []

    for i in range(2, len(df)):
        c1_low = float(df["low"].iloc[i - 2])
        c3_high = float(df["high"].iloc[i])

        if c1_low <= c3_high:
            continue

        gap = c1_low - c3_high
        gap_pct = gap / c1_low

        if gap_pct < min_gap_pct:
            continue

        fvgs.append({
            "index": i,
            "timestamp": df.index[i],
            "zone_top": c1_low,
            "zone_bottom": c3_high,
            "gap_size": gap,
            "gap_pct": gap_pct,
        })

    return fvgs


def detect_ifvg(df: pd.DataFrame, min_gap_pct: float = None) -> List[Dict[str, Any]]:
    """
    Detect all IFVGs in `df`.

    For each bearish FVG, scan forward:
      1. Wait for a candle that closes above zone_top  → flipped to IFVG.
      2. From that point, watch for close ≤ zone_top   → mitigated.

    Additional fields in each returned entry::

        'flip_idx':       int
        'flip_timestamp': Timestamp
        'mitigated':      bool
    """
    fvgs = detect_bearish_fvg(df, min_gap_pct)
    ifvgs = []

    for fvg in fvgs:
        fvg_idx = fvg["index"]
        zone_top = fvg["zone_top"]

        flipped = False
        flip_idx = None
        mitigated = False

        for i in range(fvg_idx + 1, len(df)):
            close = float(df["close"].iloc[i])
            if not flipped:
                if close > zone_top:
                    flipped = True
                    flip_idx = i
            else:
                # Close back inside or below the zone → mitigated
                if close <= zone_top:
                    mitigated = True
                    break

        if flipped:
            ifvgs.append({
                **fvg,
                "flip_idx": flip_idx,
                "flip_timestamp": df.index[flip_idx],
                "mitigated": mitigated,
            })

    return ifvgs


def get_unmitigated_ifvg(df: pd.DataFrame, min_gap_pct: float = None) -> Optional[Dict[str, Any]]:
    """Return the most recent unmitigated IFVG, or None."""
    candidates = [z for z in detect_ifvg(df, min_gap_pct) if not z["mitigated"]]
    return candidates[-1] if candidates else None


def get_latest_ifvg(df: pd.DataFrame, min_gap_pct: float = None) -> Optional[Dict[str, Any]]:
    """Return the most recent IFVG (mitigated or not), or None."""
    candidates = detect_ifvg(df, min_gap_pct)
    return candidates[-1] if candidates else None
