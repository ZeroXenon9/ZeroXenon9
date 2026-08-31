"""
Backtest runner – optimise MIN_FVG_GAP_PCT.

For a range of gap-size values the runner pre-fetches market data once,
then runs the full signal grader for each value and reports how grade
counts change.  Results are printed as a table and written to a CSV.

Usage
-----
  python runner.py                              # default symbols & gap sizes
  python runner.py --symbols BTC/USDT,ETH/USDT
  python runner.py --gap-sizes 0.001,0.003,0.005,0.010
  python runner.py --out results.csv
"""
import argparse
import csv
import time
from typing import List, Dict, Any

import config
from data.fetcher import fetch_ohlcv
from grading.signal_grader import grade_signal, GRADE_WATCHLIST, GRADE_B_PLUS, GRADE_A, GRADE_A_PLUS

_DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT",
    "LINK/USDT", "DOT/USDT", "MATIC/USDT", "ADA/USDT", "ATOM/USDT",
]

_DEFAULT_GAP_SIZES = [0.001, 0.002, 0.003, 0.005, 0.007, 0.010, 0.015, 0.020]


def prefetch(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch all timeframe data for every symbol once; returns {symbol: {tf: df}}."""
    print(f"Pre-fetching data for {len(symbols)} symbols …")
    symbol_data: Dict[str, Dict] = {}

    for symbol in symbols:
        dfs: Dict[str, Any] = {}
        for tf in config.TIMEFRAMES:
            try:
                dfs[tf] = fetch_ohlcv(symbol, tf)
                time.sleep(0.05)
            except Exception as exc:
                print(f"  Warning: {symbol} {tf} – {exc}")
                dfs[tf] = None
        symbol_data[symbol] = dfs
        print(f"  {symbol} OK")

    return symbol_data


def run_backtest(
    symbols: List[str],
    gap_sizes: List[float] = None,
) -> List[Dict[str, Any]]:
    """
    For each gap size, grade every symbol and accumulate counts.

    Returns a list of rows, one per gap size::

        {gap_pct, A+, A, B+, Watchlist, None, total_signals, signal_symbols}
    """
    gap_sizes = gap_sizes or _DEFAULT_GAP_SIZES
    symbol_data = prefetch(symbols)

    rows = []
    for gap_pct in gap_sizes:
        config.MIN_FVG_GAP_PCT = gap_pct
        counts: Dict[str, int] = {GRADE_A_PLUS: 0, GRADE_A: 0, GRADE_B_PLUS: 0,
                                   GRADE_WATCHLIST: 0, "None": 0}
        hit_symbols: List[str] = []

        for symbol in symbols:
            try:
                result = grade_signal(symbol, symbol_data[symbol])
                grade = result["grade"] or "None"
                counts[grade] = counts.get(grade, 0) + 1
                if result["grade"]:
                    hit_symbols.append(symbol)
            except Exception as exc:
                counts["None"] += 1
                print(f"  Error grading {symbol}: {exc}")

        total = sum(v for k, v in counts.items() if k != "None")
        row = {
            "gap_pct": gap_pct,
            GRADE_A_PLUS: counts[GRADE_A_PLUS],
            GRADE_A: counts[GRADE_A],
            GRADE_B_PLUS: counts[GRADE_B_PLUS],
            GRADE_WATCHLIST: counts[GRADE_WATCHLIST],
            "None": counts["None"],
            "total_signals": total,
            "signal_symbols": "|".join(hit_symbols),
        }
        rows.append(row)
        print(
            f"gap={gap_pct:.4f}  A+={row[GRADE_A_PLUS]}  A={row[GRADE_A]}  "
            f"B+={row[GRADE_B_PLUS]}  WL={row[GRADE_WATCHLIST]}  "
            f"total={total}"
        )

    return rows


def print_table(rows: List[Dict[str, Any]]) -> None:
    headers = ["gap_pct", "A+", "A", "B+", "Watchlist", "total_signals"]
    col = 13
    sep = "-" * (col * len(headers))
    print(f"\n{sep}")
    print("".join(h.ljust(col) for h in headers))
    print(sep)
    for row in rows:
        print("".join(str(row.get(h, "")).ljust(col) for h in headers))
    print(sep)


def export_csv(rows: List[Dict[str, Any]], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="FVG gap-size backtest runner")
    parser.add_argument("--symbols", default="",
                        help="Comma-separated Binance pairs (default: built-in list)")
    parser.add_argument("--gap-sizes", default="",
                        help="Comma-separated gap fractions to test (default: built-in range)")
    parser.add_argument("--out", default="backtest_results.csv",
                        help="Output CSV path (default: backtest_results.csv)")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()] or _DEFAULT_SYMBOLS
    gap_sizes = ([float(g.strip()) for g in args.gap_sizes.split(",") if g.strip()]
                 or _DEFAULT_GAP_SIZES)

    print(f"Symbols  : {len(symbols)}")
    print(f"Gap sizes: {gap_sizes}")

    rows = run_backtest(symbols, gap_sizes)
    print_table(rows)
    export_csv(rows, args.out)


if __name__ == "__main__":
    main()
