import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CMC_API_KEY = os.getenv("CMC_API_KEY", "")

# MACD parameters
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL_PERIOD = 9

# Pivot detection: number of candles required on each side of a swing high
PIVOT_WINDOW = 5

# Minimum FVG gap as fraction of price; primary backtest optimisation knob
MIN_FVG_GAP_PCT = float(os.getenv("MIN_FVG_GAP_PCT", "0.002"))

# Timeframes fetched per symbol (order matters: highest → lowest)
TIMEFRAMES = ["1w", "1d", "4h", "1h"]

# Candles fetched per timeframe per symbol
CANDLES_LIMIT = 500

# CMC sector slugs to scan (empty list = scan top coins by market cap)
CMC_SECTORS = [s for s in os.getenv("CMC_SECTORS", "").split(",") if s.strip()]

TOP_COINS_LIMIT = int(os.getenv("TOP_COINS_LIMIT", "100"))
QUOTE_CURRENCY = os.getenv("QUOTE_CURRENCY", "USDT")
