"""
Telegram alert delivery.

If TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not configured, alerts are
printed to stdout instead so the scanner still works without credentials.
"""
from typing import Dict, Any

import requests

import config


def send_alert(message: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print(f"[ALERT]\n{message}\n")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()


def format_signal_alert(result: Dict[str, Any]) -> str:
    grade = result["grade"]
    symbol = result["symbol"]

    grade_tag = {
        "A+": "A+ SIGNAL",
        "A": "A SIGNAL",
        "B+": "B+ SIGNAL",
        "Watchlist": "WATCHLIST",
    }.get(grade, grade)

    lines = [f"<b>{grade_tag}: {symbol}</b>", ""]

    weekly_div = result.get("weekly_div") or {}
    daily_div = result.get("daily_div") or {}

    if weekly_div.get("confirmed"):
        n = len(weekly_div.get("pivots", []))
        lines.append(f"Weekly MACD bearish divergence ({n} pivots)")

    if daily_div.get("confirmed"):
        n = len(daily_div.get("pivots", []))
        lines.append(f"Daily MACD bearish divergence ({n} pivots)")

    ifvg = result.get("ifvg")
    if ifvg:
        tf = (result.get("ifvg_timeframe") or "?").upper()
        status = "Unmitigated" if not ifvg.get("mitigated") else "Mitigated"
        lines.append(
            f"IFVG [{tf}] {status} | "
            f"Zone {ifvg['zone_bottom']:.6g} – {ifvg['zone_top']:.6g}"
        )

    return "\n".join(lines)
