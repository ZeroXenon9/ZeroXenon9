"""
Main scanner entry point.

Usage
-----
  python scanner.py                  # scan default symbols (or CMC top-N)
  python scanner.py --min-grade B+   # only report B+ and above
  python scanner.py --watch 3600     # re-scan every 3600 seconds
"""
import argparse
import sys
import time
from typing import List

import config
from data.fetcher import fetch_ohlcv, fetch_symbols_from_cmc, get_binance_symbols
from grading.signal_grader import grade_signal, GRADE_RANK
from alerts.telegram import send_alert, format_signal_alert

_DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT",
    "LINK/USDT", "DOT/USDT", "MATIC/USDT", "ADA/USDT", "ATOM/USDT",
]


def resolve_symbols() -> List[str]:
    if config.CMC_API_KEY:
        print("Fetching symbols from CoinMarketCap...")
        base = fetch_symbols_from_cmc(
            sectors=config.CMC_SECTORS or None,
            limit=config.TOP_COINS_LIMIT,
        )
        symbols = get_binance_symbols(base)
        print(f"  {len(symbols)} tradeable pairs found on Binance")
        return symbols

    print(f"No CMC_API_KEY set – using {len(_DEFAULT_SYMBOLS)} default symbols")
    return _DEFAULT_SYMBOLS


def scan_once(symbols: List[str], min_grade: str = None) -> List[dict]:
    min_rank = GRADE_RANK.get(min_grade, 0)
    results = []

    for symbol in symbols:
        print(f"  {symbol} ...", end=" ", flush=True)
        try:
            dfs = {}
            for tf in config.TIMEFRAMES:
                dfs[tf] = fetch_ohlcv(symbol, tf)
                time.sleep(0.05)

            result = grade_signal(symbol, dfs)
            grade = result["grade"]

            if grade and GRADE_RANK.get(grade, 0) >= min_rank:
                results.append(result)
                print(grade)
            else:
                print("–")

        except Exception as exc:
            print(f"ERROR: {exc}")

        time.sleep(0.1)

    return results


def report(results: List[dict]) -> None:
    if not results:
        print("\nNo signals found.")
        return

    # Sort highest grade first
    results.sort(key=lambda r: GRADE_RANK.get(r["grade"], 0), reverse=True)
    print(f"\n{'='*40}")
    print(f"  {len(results)} signal(s) found")
    print(f"{'='*40}")
    for r in results:
        print(f"  {r['grade']:<10}  {r['symbol']}")
    print(f"{'='*40}\n")

    if config.TELEGRAM_BOT_TOKEN:
        for r in results:
            try:
                send_alert(format_signal_alert(r))
            except Exception as exc:
                print(f"  Telegram error for {r['symbol']}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto signal scanner")
    parser.add_argument("--min-grade", default="Watchlist",
                        choices=["Watchlist", "B+", "A", "A+"],
                        help="Minimum grade to report (default: Watchlist)")
    parser.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                        help="Re-run every N seconds (0 = run once)")
    args = parser.parse_args()

    symbols = resolve_symbols()

    while True:
        print(f"\nScanning {len(symbols)} symbols  (min grade: {args.min_grade})")
        results = scan_once(symbols, min_grade=args.min_grade)
        report(results)

        if args.watch <= 0:
            break

        print(f"Next scan in {args.watch}s – Ctrl-C to stop.")
        try:
            time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
