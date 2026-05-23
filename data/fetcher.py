import time
from typing import List, Optional

import ccxt
import pandas as pd
import requests

import config

_exchange: Optional[ccxt.Exchange] = None


def get_exchange() -> ccxt.Exchange:
    global _exchange
    if _exchange is None:
        _exchange = ccxt.binance({
            "apiKey": config.BINANCE_API_KEY,
            "secret": config.BINANCE_SECRET,
            "enableRateLimit": True,
        })
    return _exchange


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = None) -> pd.DataFrame:
    """Fetch OHLCV candles from Binance. Drops the last (potentially incomplete) candle."""
    exchange = get_exchange()
    limit = limit or config.CANDLES_LIMIT
    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    # Drop last candle – it may still be open / incomplete
    return df.iloc[:-1]


def fetch_symbols_from_cmc(sectors: List[str] = None, limit: int = 100) -> List[str]:
    """
    Return base currency symbols from CoinMarketCap.
    If sectors is provided, union of coins in those CMC category slugs is returned.
    Otherwise, returns the top `limit` coins by market cap.
    """
    headers = {"X-CMC_PRO_API_KEY": config.CMC_API_KEY}

    if sectors:
        symbols: set = set()
        for sector in sectors:
            sector = sector.strip()
            if not sector:
                continue
            url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/category"
            resp = requests.get(url, headers=headers, params={"slug": sector, "limit": 200}, timeout=15)
            resp.raise_for_status()
            for coin in resp.json().get("data", {}).get("coins", []):
                symbols.add(coin["symbol"])
        return list(symbols)

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    resp = requests.get(url, headers=headers, params={"limit": limit, "sort": "market_cap"}, timeout=15)
    resp.raise_for_status()
    return [coin["symbol"] for coin in resp.json().get("data", [])]


def get_binance_symbols(base_symbols: List[str], quote: str = None) -> List[str]:
    """Filter base symbols to those tradeable on Binance with the given quote currency."""
    exchange = get_exchange()
    exchange.load_markets()
    quote = quote or config.QUOTE_CURRENCY
    return [f"{sym}/{quote}" for sym in base_symbols if f"{sym}/{quote}" in exchange.markets]
