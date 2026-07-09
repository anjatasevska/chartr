"""OHLCV helpers: DB first, then CoinGecko / CoinPaprika / CryptoCompare."""

from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.core.cache import cache

import pandas as pd

from .models import CoinHistory

API_BASE = "https://api.coingecko.com/api/v3"
PAPRIKA_BASE = "https://api.coinpaprika.com/v1"
CC_HISTODAY = "https://min-api.cryptocompare.com/data/v2/histoday"

DEFAULT_SYMBOLS = [
    "BTC", "ETH", "BNB", "SOL", "XRP",
    "ADA", "DOGE", "DOT", "LTC", "LINK",
    "AVAX", "MATIC", "TRX", "XLM", "ATOM",
]

SYMBOL_TO_COINGECKO = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "DOT": "polkadot",
    "LTC": "litecoin", "LINK": "chainlink", "AVAX": "avalanche-2",
    "MATIC": "matic-network", "TRX": "tron", "XLM": "stellar", "ATOM": "cosmos",
    "USDT": "tether", "USDC": "usd-coin", "SHIB": "shiba-inu", "UNI": "uniswap",
}


def _candles_to_dataframe(candles):
    if not candles:
        return None
    return pd.DataFrame(candles)


def fetch_ohlcv_coingecko(symbol, days=365):
    """OHLC candles from CoinGecko (works when CryptoCompare is rate-limited)."""
    symbol = symbol.upper()
    coin_id = SYMBOL_TO_COINGECKO.get(symbol)
    if not coin_id:
        return None

    allowed = [1, 7, 14, 30, 90, 180, 365]
    cg_days = 365
    for d in allowed:
        if days <= d:
            cg_days = d
            break

    cache_key = f"ohlcv_cg_{symbol}_{cg_days}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"{API_BASE}/coins/{coin_id}/ohlc",
            params={"vs_currency": "usd", "days": cg_days},
            timeout=20,
        )
        if r.status_code != 200:
            return None
        rows = []
        for ts_ms, o, h, l, c in r.json():
            rows.append({
                "timestamp": int(ts_ms / 1000),
                "open": o, "high": h, "low": l, "close": c,
                "volume": 0,
            })
        if rows:
            cache.set(cache_key, rows, 3600)
        return rows or None
    except requests.RequestException:
        return None


def fetch_ohlcv_cryptocompare(symbol, days=365):
    """Daily OHLCV from CryptoCompare."""
    symbol = symbol.upper()
    cache_key = f"ohlcv_cc_{symbol}_{days}"
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
        rows = [
            {
                "timestamp": c["time"],
                "open": c["open"], "high": c["high"],
                "low": c["low"], "close": c["close"],
                "volume": c.get("volumeto") or c.get("volume") or 0,
            }
            for c in data["Data"]["Data"] if c.get("close")
        ]
        if rows:
            cache.set(cache_key, rows, 3600)
        return rows or None
    except requests.RequestException:
        return None


def fetch_ohlcv_api(symbol, days=365):
    """Try CoinGecko first, then CryptoCompare."""
    return fetch_ohlcv_coingecko(symbol, days) or fetch_ohlcv_cryptocompare(symbol, days)


def get_ohlcv_dataframe(symbol, days=365, min_rows=30):
    symbol = symbol.upper()
    qs = CoinHistory.objects.filter(symbol=symbol).order_by("timestamp")
    if qs.count() >= min_rows:
        return pd.DataFrame(list(qs.values(
            "timestamp", "open", "high", "low", "close", "volume"
        )))

    candles = fetch_ohlcv_api(symbol, days)
    return _candles_to_dataframe(candles)


def fetch_chart_series(symbol, paprika_id=None, days=1, label_fmt="%d %b %H:%M"):
    """
    Return (labels, closes) for coin detail charts.
    Tries CoinPaprika historical, then CoinGecko, then CryptoCompare.
    """
    cache_key = f"chart_{paprika_id or symbol}_{days}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    labels, closes = [], []

    # 1) CoinPaprika historical (we already have paprika coin id on detail page)
    if paprika_id:
        if days <= 1:
            interval = "1h"
        elif days <= 7:
            interval = "6h"
        else:
            interval = "1d"
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            r = requests.get(
                f"{PAPRIKA_BASE}/tickers/{paprika_id}/historical",
                params={"start": start, "interval": interval},
                timeout=20,
            )
            if r.status_code == 200:
                for p in r.json():
                    ts = p.get("timestamp")
                    price = p.get("price")
                    if ts and price is not None:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        labels.append(dt.strftime(label_fmt))
                        closes.append(price)
        except requests.RequestException:
            pass

    # 2) CoinGecko OHLC
    if not labels:
        candles = fetch_ohlcv_coingecko(symbol, days)
        if candles:
            for c in candles[-min(len(candles), days * 24 if days <= 7 else days):]:
                dt = datetime.utcfromtimestamp(c["timestamp"])
                labels.append(dt.strftime(label_fmt))
                closes.append(c["close"])

    # 3) CryptoCompare
    if not labels:
        candles = fetch_ohlcv_cryptocompare(symbol, days)
        if candles:
            for c in candles:
                dt = datetime.utcfromtimestamp(c["timestamp"])
                labels.append(dt.strftime(label_fmt))
                closes.append(c["close"])

    if labels:
        cache.set(cache_key, (labels, closes), 1800)
    return labels, closes


def list_available_symbols():
    symbols = list(
        CoinHistory.objects.values_list("symbol", flat=True).distinct().order_by("symbol")
    )
    return symbols if symbols else DEFAULT_SYMBOLS
