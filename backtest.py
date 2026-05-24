"""
backtest.py – Walk-forward historical performance of the FVG+MACD signal.

How it works
------------
For each daily candle (after a warm-up period):
  1. Slice ALL timeframe data to only what was visible at that moment:
       1d / 4h / 1h  →  rows with index ≤ T
       1w            →  rows with index ≤ T − 7 days  (prevents including
                        a partially-open weekly candle)
     This gives zero look-ahead bias on divergence and IFVG state.
  2. Run grade_signal() on the sliced data.
  3. Record the signal when the grade *upgrades* (None→any, or lower→higher).
     Entry price = daily close at signal candle.
  4. Measure what price did over the next 1, 3, 5, 10, 20 daily candles
     (SHORT direction: positive return = price fell).

Output files
------------
  backtest_signals.csv   one row per signal event (full metadata + returns)
  backtest_stats.csv     win-rate / avg-return aggregated by grade × window

Usage
-----
  python backtest.py
  python backtest.py --symbols BTC/USDT,ETH/USDT --lookback-days 500
  python backtest.py --min-grade B+ --gap 0.003
  python backtest.py --verbose
"""
import argparse
import csv
import time
from typing import Dict, List, Optional, Any

import pandas as pd

import config
from data.fetcher import get_exchange
from grading.signal_grader import grade_signal, GRADE_RANK

# ── constants ─────────────────────────────────────────────────────────────────

_DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT",
    "LINK/USDT", "DOT/USDT", "MATIC/USDT", "ADA/USDT", "ATOM/USDT",
]

_WINDOWS = [1, 3, 5, 10, 20]          # forward return windows (daily candles)
_COOLDOWN = 10                         # candles to skip after each signal fires
_PAGE = 1000                           # max candles per paginated fetch

# For sub-daily timeframes (4h, 1h), limit the look-back window used per
# walk-forward step.  This caps detect_ifvg's O(n²) work without losing
# meaningful signal history (an IFVG from 6 months ago is rarely still active).
_MAX_INTRADAY_CANDLES = {"4h": 300, "1h": 300}   # ~50 days of 4h; ~12 days of 1h

# Minimum daily-candle warm-up required before grades become reliable.
# B+/Watchlist only need daily divergence (~46 + PIVOT_WINDOW buffer = 80).
# A/A+ also need weekly divergence: 46 weekly candles × 7 days ≈ 340 daily candles.
_WARMUP_BY_MIN_GRADE = {
    "Watchlist": 80,
    "B+":        80,
    "A":         350,
    "A+":        350,
}

# ── paginated data fetcher ────────────────────────────────────────────────────

def fetch_history(symbol: str, tf: str, lookback_days: int) -> Optional[pd.DataFrame]:
    """
    Fetch up to `lookback_days` of historical OHLCV for `symbol` on `tf`.

    Uses paginated requests (up to _PAGE candles each) so it works for
    high-frequency timeframes (4h → 2 190 candles/year, 1h → 8 760/year).

    Returns a DataFrame indexed by open-time (UTC), last incomplete candle
    dropped.  Returns None on failure.
    """
    tf_mins = {"1w": 10080, "1d": 1440, "4h": 240, "1h": 60}
    mins_per_candle = tf_mins.get(tf, 1440)
    needed_candles  = (lookback_days * 1440) // mins_per_candle + 5

    exchange = get_exchange()
    since_ms = (
        pd.Timestamp.utcnow() - pd.Timedelta(days=lookback_days)
    ).value // 1_000_000   # ccxt uses integer milliseconds

    all_rows = []
    try:
        while True:
            batch = exchange.fetch_ohlcv(symbol, tf, since=since_ms, limit=_PAGE)
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < _PAGE:
                break
            since_ms = batch[-1][0] + 1        # advance past last returned ts
            if len(all_rows) >= needed_candles:
                break
            time.sleep(exchange.rateLimit / 1000)
    except Exception as exc:
        print(f"      [{tf}] error: {exc}")
        return None

    if not all_rows:
        return None

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    df.drop_duplicates("timestamp", inplace=True)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    # Drop the last (potentially open/incomplete) candle
    return df.iloc[:-1] if len(df) > 1 else None


def build_symbol_data(symbol: str, lookback_days: int) -> Dict[str, Optional[pd.DataFrame]]:
    dfs: Dict[str, Optional[pd.DataFrame]] = {}
    for tf in config.TIMEFRAMES:
        dfs[tf] = fetch_history(symbol, tf, lookback_days)
        time.sleep(0.05)
    return dfs


# ── walk-forward slicing (zero look-ahead) ────────────────────────────────────

def _slice_at(
    all_dfs: Dict[str, Optional[pd.DataFrame]],
    up_to_ts: pd.Timestamp,
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Return each DataFrame trimmed to data that was actually closed at up_to_ts.

    1d / 4h / 1h  →  index ≤ up_to_ts
    1w            →  index ≤ up_to_ts − 7 days
                     (weekly candle opened at W closes at W+7; including
                      a partially-open weekly candle would be look-ahead bias)
    """
    out: Dict[str, Optional[pd.DataFrame]] = {}
    for tf, df in all_dfs.items():
        if df is None or df.empty:
            out[tf] = None
            continue
        if tf == "1w":
            cutoff = up_to_ts - pd.Timedelta(days=7)
        else:
            cutoff = up_to_ts
        sliced = df[df.index <= cutoff]
        # Cap intraday timeframes to a recent window so O(n²) IFVG scan
        # stays bounded regardless of total history length.
        cap = _MAX_INTRADAY_CANDLES.get(tf)
        if cap and len(sliced) > cap:
            sliced = sliced.iloc[-cap:]
        out[tf] = sliced if not sliced.empty else None
    return out


# ── forward metrics ───────────────────────────────────────────────────────────

def _forward_metrics(daily: pd.DataFrame, i: int, entry: float) -> Dict[str, Any]:
    """
    Compute forward return metrics for a SHORT entry at daily candle i.

    Positive ret_Nd_pct  = price fell  = short was profitable.
    mae_pct              = max upward  move against the short (loss territory).
    mfe_pct              = max downward move for the short (profit territory).
    """
    metrics: Dict[str, Any] = {}
    for w in _WINDOWS:
        if i + w < len(daily):
            fc = float(daily["close"].iloc[i + w])
            metrics[f"ret_{w}d_pct"] = round((entry - fc) / entry * 100, 4)
        else:
            metrics[f"ret_{w}d_pct"] = None

    future = daily.iloc[i + 1: i + max(_WINDOWS) + 1]
    if not future.empty:
        max_h = float(future["high"].max())
        min_l = float(future["low"].min())
        metrics["mae_pct"] = round((max_h - entry) / entry * 100, 4)
        metrics["mfe_pct"] = round((entry - min_l) / entry * 100, 4)
    else:
        metrics["mae_pct"] = None
        metrics["mfe_pct"] = None

    return metrics


# ── walk-forward engine ───────────────────────────────────────────────────────

def walk_forward(
    symbol: str,
    all_dfs: Dict[str, Optional[pd.DataFrame]],
    min_grade: str = "Watchlist",
    warmup: int = None,
    stride: int = 1,
) -> List[Dict[str, Any]]:
    """
    Walk through the daily series, detect upward grade transitions, and
    compute forward return metrics.  Returns a list of signal records.

    Parameters
    ----------
    stride : int
        Check every `stride` daily candles instead of every 1.
        stride=1 is fully accurate; stride=5 is ~5× faster with minor
        risk of missing a signal that appeared and vanished within a 5-day window.
    """
    daily = all_dfs.get("1d")
    if daily is None or len(daily) < (warmup or _WARMUP_BY_MIN_GRADE.get(min_grade, 80)) + max(_WINDOWS) + 1:
        return []

    min_rank = GRADE_RANK.get(min_grade, 1)
    effective_warmup = warmup or _WARMUP_BY_MIN_GRADE.get(min_grade, 80)
    stride = max(1, stride)
    signals: List[Dict[str, Any]] = []
    prev_grade: Optional[str] = None
    cooldown = 0
    scan_end = len(daily) - max(_WINDOWS) - 1

    for i in range(effective_warmup, scan_end, stride):
        if cooldown > 0:
            cooldown -= 1
            continue

        up_to_ts = daily.index[i]
        sliced = _slice_at(all_dfs, up_to_ts)

        try:
            result = grade_signal(symbol, sliced)
        except Exception:
            prev_grade = None
            continue

        grade      = result["grade"]
        grade_rank = GRADE_RANK.get(grade, 0)
        prev_rank  = GRADE_RANK.get(prev_grade, 0)

        # Fire on upward grade transition only
        new_signal = (
            grade is not None
            and grade_rank >= min_rank
            and grade_rank > prev_rank
        )

        old_prev_grade = prev_grade   # capture before updating
        prev_grade = grade

        if not new_signal:
            continue

        entry_price = float(daily["close"].iloc[i])
        fwd = _forward_metrics(daily, i, entry_price)

        # Enrich with signal detail
        weekly_div = result.get("weekly_div") or {}
        daily_div  = result.get("daily_div") or {}
        ifvg       = result.get("ifvg") or {}

        signals.append({
            "symbol":            symbol,
            "grade":             grade,
            "prev_grade":        old_prev_grade if old_prev_grade else "",
            "signal_date":       up_to_ts.date().isoformat(),
            "entry_price":       entry_price,
            "weekly_div":        weekly_div.get("confirmed", False),
            "daily_div":         daily_div.get("confirmed", False),
            "ifvg_tf":           result.get("ifvg_timeframe") or "",
            "ifvg_zone_top":     ifvg.get("zone_top", ""),
            "ifvg_zone_bottom":  ifvg.get("zone_bottom", ""),
            "ifvg_mitigated":    ifvg.get("mitigated", ""),
            **fwd,
        })

        cooldown = _COOLDOWN

    return signals


# ── aggregated statistics ─────────────────────────────────────────────────────

def _mean(vals: list) -> Optional[float]:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _fmt(v: Optional[float]) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def aggregate_stats(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns one row per (grade, window) pair, sorted by grade rank desc."""
    by_grade: Dict[str, List] = {}
    for sig in signals:
        by_grade.setdefault(sig["grade"], []).append(sig)

    rows = []
    for grade, sigs in sorted(
        by_grade.items(), key=lambda kv: GRADE_RANK.get(kv[0], 0), reverse=True
    ):
        for w in _WINDOWS:
            key = f"ret_{w}d_pct"
            rets = [s[key] for s in sigs if s.get(key) is not None]
            wins = [r for r in rets if r > 0]
            rows.append({
                "grade":       grade,
                "window_days": w,
                "n_signals":   len(sigs),
                "win_rate":    _fmt(len(wins) / len(rets) * 100 if rets else None),
                "mean_ret":    _fmt(_mean(rets)),
                "median_ret":  _fmt(sorted(rets)[len(rets) // 2] if rets else None),
                "mean_mfe":    _fmt(_mean([s.get("mfe_pct") for s in sigs])),
                "mean_mae":    _fmt(_mean([s.get("mae_pct") for s in sigs])),
            })
    return rows


# ── display helpers ───────────────────────────────────────────────────────────

def print_summary(signals: List[Dict[str, Any]]) -> None:
    rows = aggregate_stats(signals)
    if not rows:
        print("  No signals to summarise.")
        return

    headers = ["grade", "window_days", "n_signals", "win_rate",
               "mean_ret", "median_ret", "mean_mfe", "mean_mae"]
    col = 13
    sep = "─" * (col * len(headers))

    print(f"\n{sep}")
    print("".join(h[:col].ljust(col) for h in headers))
    print(sep)
    for row in rows:
        print("".join(str(row.get(h, ""))[:col].ljust(col) for h in headers))
    print(sep)


def print_signals_table(signals: List[Dict[str, Any]]) -> None:
    if not signals:
        return
    print(f"\n{'─'*70}")
    print("  All signals")
    print(f"{'─'*70}")
    for s in signals:
        rets = "  ".join(
            f"{w}d:{str(s.get(f'ret_{w}d_pct','?')):>7}"
            for w in _WINDOWS
        )
        print(f"  {s['grade']:<5}  {s['symbol']:<12}  {s['signal_date']}  "
              f"@{s['entry_price']:<10.4g}  {rets}")


def export_csv(rows: List[Dict], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Walk-forward backtest of the FVG+MACD signal grader"
    )
    parser.add_argument("--symbols", default="",
                        help="Comma-separated Binance pairs (default: 10 built-in)")
    parser.add_argument("--lookback-days", type=int, default=500,
                        help="Calendar days of history to fetch (default: 500)")
    parser.add_argument("--min-grade", default="Watchlist",
                        choices=["Watchlist", "B+", "A", "A+"],
                        help="Minimum grade to record (default: Watchlist)")
    parser.add_argument("--gap", type=float, default=None,
                        help="Override MIN_FVG_GAP_PCT, e.g. 0.003")
    parser.add_argument("--out-signals", default="backtest_signals.csv",
                        help="Output CSV: individual signal events")
    parser.add_argument("--out-stats", default="backtest_stats.csv",
                        help="Output CSV: aggregated stats by grade × window")
    parser.add_argument("--stride", type=int, default=1,
                        help="Check every N daily candles (default 1 = every candle). "
                             "Use 5 for a ~5× speed boost with minor accuracy trade-off.")
    parser.add_argument("--verbose", action="store_true",
                        help="Print every signal in addition to summary")
    args = parser.parse_args()

    symbols = ([s.strip() for s in args.symbols.split(",") if s.strip()]
               or _DEFAULT_SYMBOLS)

    if args.gap is not None:
        config.MIN_FVG_GAP_PCT = args.gap

    warmup = _WARMUP_BY_MIN_GRADE.get(args.min_grade, 80)

    print(f"\n{'='*65}")
    print(f"  FVG + MACD Signal Backtest  (walk-forward, no look-ahead)")
    print(f"{'='*65}")
    print(f"  Symbols      : {len(symbols)}")
    print(f"  Lookback     : {args.lookback_days} days")
    print(f"  Min grade    : {args.min_grade}")
    print(f"  Gap pct      : {config.MIN_FVG_GAP_PCT:.4f}")
    print(f"  Warmup       : {warmup} daily candles")
    print(f"  Stride       : every {args.stride} daily candle(s)")
    print(f"  Direction    : SHORT  (positive ret = price fell)")
    print(f"  Cooldown     : {_COOLDOWN} candles after each signal")
    print(f"{'='*65}\n")

    all_signals: List[Dict[str, Any]] = []

    for symbol in symbols:
        print(f"  {symbol}")
        all_dfs = build_symbol_data(symbol, args.lookback_days)

        daily = all_dfs.get("1d")
        if daily is None:
            print(f"    skipped – no daily data")
            continue
        print(f"    {len(daily)} daily candles")

        sigs = walk_forward(symbol, all_dfs,
                            min_grade=args.min_grade, warmup=warmup,
                            stride=args.stride)
        print(f"    {len(sigs)} signal(s)")
        all_signals.extend(sigs)

    print(f"\n{'='*65}")
    print(f"  RESULTS — {len(all_signals)} signal(s) across {len(symbols)} symbols")
    print(f"  win_rate : % of signals where price was LOWER at N days (short won)")
    print(f"  mean_ret : average (entry−close)/entry×100  (short P&L)")
    print(f"  mean_mfe : avg max favorable excursion  (best downward move)")
    print(f"  mean_mae : avg max adverse excursion    (worst upward move vs short)")
    print_summary(all_signals)

    if args.verbose:
        print_signals_table(all_signals)

    stats_rows = aggregate_stats(all_signals)
    print(f"\n  Exporting results:")
    export_csv(all_signals, args.out_signals)
    export_csv(stats_rows,  args.out_stats)


if __name__ == "__main__":
    main()
