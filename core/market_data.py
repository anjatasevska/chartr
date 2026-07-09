"""OHLCV helpers: read from DB, fall back to CryptoCompare when empty."""

import requests
from django.conf import settings
from django.core.cache import cache

import pandas as pd

from .models import CoinHistory

DEFAULT_SYMBOLS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "DOT", "LTC", "LINK",
    "AVAX", "MATIC", "TRX", "XLM", "ATOM",
]

CC_HISTODAY = "https://min-api.cryptocompare.com/data/v2/histoday"


def fetch_ohlcv_api(symbol, days=365):
    """Daily OHLCV candles from CryptoCompare. Returns list of dicts or None."""
    symbol = symbol.upper()
    cache_key = f"ohlcv_api_{symbol}_{days}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {"fsym": symbol, "tsym": "USD", "limit": days}
    api_key = getattr(settings, "CRYPTOCOMPARE_API_KEY", "") or ""
    headers = {"authorization": f"Apikey {api_key}"} if api_key else {}

    try:
        r = requests.get(CC_HISTODAY, params=params, headers=headers, timeout=20)
        data = r.json()
        if data.get("Response") != "Success":
            return None
        rows = [d for d in data["Data"]["Data"] if d.get("close")]
        cache.set(cache_key, rows, 3600)
        return rows
    except requests.RequestException:
        return None


def get_ohlcv_dataframe(symbol, days=365, min_rows=30):
    """
    Return OHLCV as a DataFrame. Uses the local DB when populated,
    otherwise fetches live from CryptoCompare (for hosted deploys where
    seed_ohlcv may have failed during build).
    """
    symbol = symbol.upper()
    qs = CoinHistory.objects.filter(symbol=symbol).order_by("timestamp")
    if qs.count() >= min_rows:
        return pd.DataFrame(list(qs.values(
            "timestamp", "open", "high", "low", "close", "volume"
        )))

    candles = fetch_ohlcv_api(symbol, days)
    if not candles:
        return None

    return pd.DataFrame([
        {
            "timestamp": c["time"],
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": c.get("volumeto") or c.get("volume") or 0,
        }
        for c in candles
    ])


def list_available_symbols():
    """Symbols with DB data, or the default curated list."""
    symbols = list(
        CoinHistory.objects.values_list("symbol", flat=True).distinct().order_by("symbol")
    )
    return symbols if symbols else DEFAULT_SYMBOLS
