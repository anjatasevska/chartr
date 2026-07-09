# core/views.py
import json
import requests
import numpy as np

from datetime import datetime

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import render

from .models import CoinHistory
from .market_data import get_ohlcv_dataframe, list_available_symbols, fetch_chart_series

API_BASE = "https://api.coingecko.com/api/v3"
CRYPTOCOMPARE_BASE = "https://min-api.cryptocompare.com/data/v2"
NEWS_API_URL = "https://min-api.cryptocompare.com/data/v2/news/"

# -------------------------------------------------
#  Helper функции
# -------------------------------------------------
def signal_from_value(indicator, value):
    if value is None:
        return "HOLD"

    try:
        value = float(value)
    except:
        return "HOLD"

    if indicator == "RSI":
        if value < 30:
            return "BUY"
        elif value > 70:
            return "SELL"

    if indicator == "CCI":
        if value < -100:
            return "BUY"
        elif value > 100:
            return "SELL"

    return "HOLD"

def safe_get(url, params=None):
    """
    Wrapper околу requests.get за да фатиме 429 и други грешки
    и да вратиме (data, error_code).
    """
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None, "rate_limit"
        if e.response is not None and e.response.status_code == 404:
            return None, "not_found"
        raise  # други грешки нека пукнат за да ги видиме во лог


def fetch_top_coins(limit=5):
    """
    Топ коини по market cap, со 24h промена.
    Реално од CoinGecko.
    """
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    r = requests.get(f"{API_BASE}/coins/markets", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def fetch_coin_list(limit=50):
    """
    Листа за 'View all coins'. CoinGecko со кеш; ако е rate-limited (429),
    fallback на CoinPaprika за да не падне страницата.
    """
    from django.core.cache import cache

    cache_key = f"coin_list_{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    try:
        r = requests.get(f"{API_BASE}/coins/markets", params=params, timeout=10)
        r.raise_for_status()
        coins = r.json()
        cache.set(cache_key, coins, 300)
        return coins
    except requests.RequestException:
        coins = _fetch_coin_list_paprika(limit)
        if coins:
            cache.set(cache_key, coins, 300)
        return coins


def _fetch_coin_list_paprika(limit=50):
    """Fallback листа од CoinPaprika, мапирана во CoinGecko-стил полиња."""
    try:
        res = requests.get(
            "https://api.coinpaprika.com/v1/tickers",
            params={"quotes": "USD"},
            timeout=10,
        )
        res.raise_for_status()
        tickers = res.json()
    except requests.RequestException:
        return []

    tickers = [t for t in tickers if t.get("rank")]
    tickers.sort(key=lambda t: t["rank"])

    coins = []
    for t in tickers[:limit]:
        usd = (t.get("quotes") or {}).get("USD") or {}
        coins.append({
            "id": t.get("id"),
            "name": t.get("name"),
            "symbol": (t.get("symbol") or "").lower(),
            "current_price": usd.get("price"),
            "price_change_percentage_24h": usd.get("percent_change_24h"),
        })
    return coins


def fetch_coin_detail(coin_id):
    """
    Детали за конкретен coin од CoinGecko.
    """
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
        "sparkline": "false",
    }
    return safe_get(f"{API_BASE}/coins/{coin_id}", params=params)


def fetch_coin_ohlc(coin_id, days=1):
    """
    OHLC од CoinGecko (ако ти треба некаде).
    """
    params = {"vs_currency": "usd", "days": days}
    return safe_get(f"{API_BASE}/coins/{coin_id}/ohlc", params=params)


def fetch_crypto_news(limit=18):
    from django.core.cache import cache

    cache_key = f"crypto_news_{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    articles = _fetch_news_cryptocompare(limit)
    if not articles:
        articles = _fetch_news_newsapi(limit)

    if not articles:
        stale = cache.get(f"{cache_key}_stale")
        return stale or []

    cache.set(cache_key, articles, 600)
    cache.set(f"{cache_key}_stale", articles, 86400)
    return articles


def _fetch_news_cryptocompare(limit):
    params = {
        "lang": "EN",
        "sortOrder": "latest",
        "extraParams": "chartr",
        "api_key": settings.CRYPTOCOMPARE_API_KEY,
    }
    try:
        r = requests.get(NEWS_API_URL, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()
    except requests.RequestException:
        return []

    data = raw.get("Data", [])
    if not isinstance(data, list):
        return []

    articles = data[:limit]
    for a in articles:
        img = a.get("imageurl") or ""
        if img.startswith("/"):
            a["image_full"] = "https://www.cryptocompare.com" + img
        else:
            a["image_full"] = img

        ts = a.get("published_on")
        if isinstance(ts, (int, float)):
            try:
                dt = datetime.utcfromtimestamp(ts)
                a["published_human"] = dt.strftime("%d %b %Y • %H:%M UTC")
            except Exception:
                a["published_human"] = ""
        else:
            a["published_human"] = ""

        source_info = a.get("source_info") or {}
        a["source_name"] = source_info.get("name") or a.get("source") or "Crypto News"

    return articles


def _fetch_news_newsapi(limit):
    """Fallback when CryptoCompare news is rate-limited."""
    import os
    key = os.getenv("NEWSAPI_KEY", "a16a798ad7394417a8c1636b26e2ddab")
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": "cryptocurrency OR bitcoin OR ethereum",
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": limit,
                "apiKey": key,
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []
        out = []
        for a in r.json().get("articles", [])[:limit]:
            pub = a.get("publishedAt") or ""
            out.append({
                "title": a.get("title") or "",
                "body": a.get("description") or "",
                "url": a.get("url") or "",
                "image_full": a.get("urlToImage") or "",
                "source_name": (a.get("source") or {}).get("name") or "News",
                "published_human": pub[:16].replace("T", " ") if pub else "",
                "categories": "",
            })
        return out
    except requests.RequestException:
        return []

# -------------------------------------------------
#  Views
# -------------------------------------------------

def home(request):
    news_preview = fetch_crypto_news(limit=2)  # десниот News бокс на home
    top_coins = fetch_coin_list(limit=6)  # server-side (кеш + fallback) за да не падне во browser
    return render(request, "home.html", {
        "news_preview": news_preview,
        "top_coins": top_coins,
    })


def coin_list(request):
    coins = fetch_coin_list(limit=50)
    return render(request, "coin_list.html", {"coins": coins})


# Complete coin_detail function for views.py
# Replace your existing coin_detail function with this




def coin_detail(request, coin_id):
    """
    Детален view за coin – CoinPaprika + CryptoCompare график.
    Се е реално од APIs.
    """
    paprika_base = "https://api.coinpaprika.com/v1"

    # --- избран временски период од query string ---
    # 1D / 1W / 1M / 1Y / 5Y / 10Y
    range_param = request.GET.get("range", "1D").upper()

    RANGE_DAYS = {
        "1D": 1,
        "1W": 7,
        "1M": 30,
        "1Y": 365,
        "5Y": 365 * 5,
        "10Y": 365 * 10,
    }

    if range_param not in RANGE_DAYS:
        range_param = "1D"

    days = RANGE_DAYS[range_param]

    # --- 1) CoinPaprika (цена, промени, market cap...) ---
    ticker_res = requests.get(
        f"{paprika_base}/tickers/{coin_id}",
        params={"quotes": "USD"},
        timeout=10
    )

    rate_limited = False
    if ticker_res.status_code == 429:
        rate_limited = True
        return render(
            request,
            "coin_detail.html",
            {
                "rate_limited": True,
                "coin": None,
                "labels_json": "[]",
                "closes_json": "[]",
                "active_range": range_param,
                "range_options": ["1D", "1W", "1M", "1Y", "5Y", "10Y"],
            },
        )

    if ticker_res.status_code != 200:
        raise Http404("Coin not found")

    coin = ticker_res.json()

    # --- 2) Chart data (Paprika → CoinGecko → CryptoCompare) ---
    symbol = (coin.get("symbol") or "").upper()
    if days <= 7:
        label_fmt = "%d %b %H:%M"
    else:
        label_fmt = "%d %b %Y"

    labels, closes = fetch_chart_series(
        symbol, paprika_id=coin_id, days=days, label_fmt=label_fmt
    )

    context = {
        "coin": coin,
        "rate_limited": rate_limited,
        "labels_json": json.dumps(labels),
        "closes_json": json.dumps(closes),
        "active_range": range_param,
        "range_options": ["1D", "1W", "1M", "1Y", "5Y"],
    }
    return render(request, "coin_detail.html", context)




def crypto_news(request):
    articles = fetch_crypto_news(limit=18)
    return render(request, "news.html", {"articles": articles})


from .technical_analysis import calculate_technical_indicators
import pandas as pd


def coin_analysis_view(request, symbol):
    df = get_ohlcv_dataframe(symbol, min_rows=30)
    if df is None or df.empty:
        return render(request, "core/no_data.html", {"symbol": symbol})

    df_analysis = calculate_technical_indicators(df)

    def tf_value(series, n):
        return round(series.tail(n).mean(), 2)

    indicators = [
        {
            "name": "RSI (14)",
            "timeframes": [
                {"value": tf_value(df_analysis["RSI"], 30), "signal": signal_from_value("RSI", tf_value(df_analysis["RSI"], 30))},
                {"value": tf_value(df_analysis["RSI"], 365), "signal": signal_from_value("RSI", tf_value(df_analysis["RSI"], 365))},
                {"value": tf_value(df_analysis["RSI"], 3650), "signal": signal_from_value("RSI", tf_value(df_analysis["RSI"], 3650))},
            ]
        },
        {
            "name": "MACD (12,26,9)",
            "timeframes": [
                {"value": round(df_analysis["MACD"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["MACD"].iloc[-1], 2), "signal": "BUY"},
                {"value": round(df_analysis["MACD"].iloc[-1], 2), "signal": "BUY"},
            ]
        },
        {
            "name": "SMA 20",
            "timeframes": [
                {"value": round(df_analysis["SMA"].iloc[-1], 2), "signal": "BUY"},
                {"value": round(df_analysis["SMA"].iloc[-1], 2), "signal": "BUY"},
                {"value": round(df_analysis["SMA"].iloc[-1], 2), "signal": "BUY"},
            ]
        },
        {
            "name": "EMA 20",
            "timeframes": [
                {"value": round(df_analysis["EMA"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["EMA"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["EMA"].iloc[-1], 2), "signal": "HOLD"},
            ]
        },
        {
            "name": "Stochastic %K",
            "timeframes": [
                {"value": round(df_analysis["Stochastic"].iloc[-1], 2), "signal": "SELL"},
                {"value": round(df_analysis["Stochastic"].iloc[-1], 2), "signal": "SELL"},
                {"value": round(df_analysis["Stochastic"].iloc[-1], 2), "signal": "SELL"},
            ]
        },
        {
            "name": "CCI (20)",
            "timeframes": [
                {"value": tf_value(df_analysis["CCI"], 30),
                 "signal": signal_from_value("CCI", tf_value(df_analysis["CCI"], 30))},
                {"value": tf_value(df_analysis["CCI"], 365),
                 "signal": signal_from_value("CCI", tf_value(df_analysis["CCI"], 365))},
                {"value": tf_value(df_analysis["CCI"], 3650),
                 "signal": signal_from_value("CCI", tf_value(df_analysis["CCI"], 3650))},
            ]
        },
        {
            "name": "ADX (14)",
            "timeframes": [
                {"value": tf_value(df_analysis["ADX"], 30), "signal": "HOLD"},
                {"value": tf_value(df_analysis["ADX"], 365), "signal": "HOLD"},
                {"value": tf_value(df_analysis["ADX"], 3650), "signal": "HOLD"},
            ]
        },
        {
            "name": "Bollinger Bands",
            "timeframes": [
                {"value": round(df_analysis["BB_HIGH"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["BB_HIGH"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["BB_HIGH"].iloc[-1], 2), "signal": "HOLD"},
            ]
        },
        {
            "name": "Volume MA 20",
            "timeframes": [
                {"value": round(df_analysis["VOL_MA"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["VOL_MA"].iloc[-1], 2), "signal": "HOLD"},
                {"value": round(df_analysis["VOL_MA"].iloc[-1], 2), "signal": "HOLD"},
            ]
        },
        {
            "name": "WMA 20",
            "timeframes": [
                {"value": round(df_analysis["WMA"].iloc[-1], 2), "signal": "BUY"},
                {"value": round(df_analysis["WMA"].iloc[-1], 2), "signal": "BUY"},
                {"value": round(df_analysis["WMA"].iloc[-1], 2), "signal": "BUY"},
            ]
        },
    ]

    context = {
        "symbol": symbol.upper(),
        "indicators": indicators,
    }

    return render(request, "technical_analysis.html", context)

from collections import Counter

def api_technical_analysis(request, coin):
    tf = request.GET.get("tf", "1d")

    symbol = coin.split("-")[0].upper()

    df = get_ohlcv_dataframe(symbol, min_rows=30)
    if df is None or df.empty:
        return JsonResponse({"error": "No data"}, status=404)

    df = calculate_technical_indicators(df)
    latest = df.iloc[-1]

    indicators = {
        "rsi": {
            "value": round(latest["RSI"], 4),
            "signal": "BUY" if latest["RSI"] < 30 else "SELL" if latest["RSI"] > 70 else "HOLD",
        },
        "macd": {
            "value": round(latest["MACD"], 4),
            "signal": "BUY" if latest["MACD"] > latest["MACD_SIGNAL"] else "SELL",
        },
        "stoch": {
            "value": round(latest["Stochastic"], 4),
            "signal": "BUY" if latest["Stochastic"] < 20 else "SELL" if latest["Stochastic"] > 80 else "HOLD",
        },
        "adx": {
            "value": round(latest["ADX"], 4),
            "signal": "BUY" if latest["ADX"] > 25 else "HOLD",
        },
        "cci": {
            "value": round(latest["CCI"], 4),
            "signal": "BUY" if latest["CCI"] < -100 else "SELL" if latest["CCI"] > 100 else "HOLD",
        },
        "sma": {
            "value": round(latest["SMA"], 4),
            "signal": "BUY" if latest["close"] > latest["SMA"] else "SELL",
        },
        "ema": {
            "value": round(latest["EMA"], 4),
            "signal": "BUY" if latest["close"] > latest["EMA"] else "SELL",
        },
        "wma": {
            "value": round(latest["WMA"], 4),
            "signal": "BUY" if latest["close"] > latest["WMA"] else "SELL",
        },
        "bb": {
            "value": round(latest["BB_HIGH"], 4),
            "signal": "HOLD",
        },
        "vma": {
            "value": round(latest["VOL_MA"], 4),
            "signal": "HOLD",
        },
    }

    counts = Counter(i["signal"] for i in indicators.values())
    final_signal = counts.most_common(1)[0][0]

    return JsonResponse({
        "coin": symbol,
        "timeframe": tf,
        "indicators": indicators,
        "final_signal": final_signal,
        "breakdown": dict(counts),
    })


def technical_analysis_page(request):
    coins = list_available_symbols()
    return render(request, "technical_analysis.html", {
        "coins": coins
    })


def coin_prediction_view(request, symbol):
    """
    LSTM предвидување за конкретен coin
    """
    # Нормализирај symbol
    symbol = symbol.upper()

    df = get_ohlcv_dataframe(symbol, min_rows=50)

    if df is None or df.empty:
        return render(request, "coin_prediction.html", {
            "error": f"No data available for {symbol}. Please try again in a moment.",
            "symbol": symbol,
        })

    if len(df) < 50:
        return render(request, "coin_prediction.html", {
            "error": f"Not enough data for {symbol}. Need at least 50 data points, got {len(df)}.",
            "symbol": symbol,
        })

    try:
        try:
            from .LSTM import train_lstm
            predictions, real, rmse, r2 = train_lstm(df)
            model_name = "LSTM"
        except ImportError:
            # TensorFlow not installed → use lightweight NumPy fallback model
            from .simple_model import simple_predict
            predictions, real, rmse, r2 = simple_predict(df)
            model_name = "Linear (NumPy)"

        context = {
            "symbol": symbol,
            "predictions": json.dumps(np.asarray(predictions).tolist()),
            "real": json.dumps(np.asarray(real).tolist()),
            "points": int(np.asarray(real).size),
            "rmse": float(rmse),
            "r2": float(r2),
            "model_name": model_name,
            "error": None,
        }
        return render(request, "coin_prediction.html", context)

    except ValueError as ve:
        return render(request, "coin_prediction.html", {
            "error": str(ve),
            "symbol": symbol,
        })

    except Exception as e:
        return render(request, "coin_prediction.html", {
            "error": f"Error training prediction model: {e}",
            "symbol": symbol,
        })
def prediction_select_view(request):
    symbols = list_available_symbols()
    return render(request, "prediction_select.html", {"symbols": symbols})


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .onchain import CombinedAnalysis, OnChainAnalysis, SentimentAnalysis

# Иницијализација на анализатори (можете да ги направите глобални за перформанси)
combined_analyzer = CombinedAnalysis()
onchain_analyzer = OnChainAnalysis()
sentiment_analyzer = SentimentAnalysis()


@require_http_methods(["GET"])
def get_onchain_metrics(request):
    """
    API endpoint за On-Chain метрики
    GET /api/onchain-metrics?coin=bitcoin&days=30

    Параметри:
        - coin: ID на монетата (bitcoin, ethereum, итн.)
        - days: Број на денови за историски податоци (default: 30)

    Пример:
        http://localhost:8000/api/onchain-metrics?coin=bitcoin&days=30
    """
    try:
        coin_id = request.GET.get('coin', 'bitcoin')
        days = int(request.GET.get('days', 30))

        metrics = onchain_analyzer.get_onchain_metrics(coin_id, days)

        if metrics:
            return JsonResponse({
                'success': True,
                'coin': coin_id,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch on-chain metrics'
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_sentiment_analysis(request):
    """
    API endpoint за сентимент анализа
    GET /api/sentiment?query=bitcoin&days=7

    Параметри:
        - query: Клучен збор за пребарување (bitcoin, ethereum, crypto)
        - days: Број на денови за вести (default: 7)

    Пример:
        http://localhost:8000/api/sentiment?query=bitcoin&days=7
    """
    try:
        query = request.GET.get('query', 'bitcoin')
        days = int(request.GET.get('days', 7))

        # Собери вести
        articles = sentiment_analyzer.get_crypto_news(query, days)

        # Анализирај сентимент
        sentiments = sentiment_analyzer.analyze_news_sentiment(articles)
        sentiment_score = sentiment_analyzer.calculate_sentiment_score(sentiments)

        return JsonResponse({
            'success': True,
            'query': query,
            'sentiment_score': sentiment_score,
            'news_count': len(articles),
            'recent_news': sentiments[:5],  # Топ 5 вести
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_exchange_flows(request):
    """
    API endpoint за exchange flow анализа
    GET /api/exchange-flows?coin=bitcoin

    Параметри:
        - coin: ID на монетата (bitcoin, ethereum, итн.)

    Пример:
        http://localhost:8000/api/exchange-flows?coin=bitcoin
    """
    try:
        coin_id = request.GET.get('coin', 'bitcoin')

        exchange_data = onchain_analyzer.analyze_exchange_flows(coin_id)

        if exchange_data:
            return JsonResponse({
                'success': True,
                'coin': coin_id,
                'exchange_data': exchange_data,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to analyze exchange flows'
            }, status=500)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_complete_analysis(request):
    """
    API endpoint за комплетна анализа (On-Chain + Sentiment)
    GET /api/complete-analysis?coin=bitcoin&symbol=BTC&query=bitcoin
    """
    try:
        coin_id = request.GET.get('coin', 'bitcoin')
        coin_symbol = request.GET.get('symbol', 'BTC')
        query = request.GET.get('query', coin_id)

        analyzer = CombinedAnalysis()
        results = analyzer.perform_full_analysis(
            coin_id=coin_id,
            coin_symbol=coin_symbol,
            query=query
        )

        def convert_numpy(obj):
            """Конвертира NumPy типови во Python типови"""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(i) for i in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        clean_results = convert_numpy(results)

        return JsonResponse({
            'success': True,
            'coin': coin_id,
            'analysis': {
                'onchain_metrics': clean_results.get('onchain_metrics'),
                'exchange_flows': clean_results.get('exchange_data'),
                'whale_activity': clean_results.get('whale_data'),
                'sentiment': clean_results.get('sentiment'),
                'trading_signal': clean_results.get('trading_signal')
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        }, status=500)

@require_http_methods(["GET"])
def get_trading_signal(request):
    """
    API endpoint за trading signal
    GET /api/trading-signal?coin=bitcoin&symbol=BTC

    Параметри:
        - coin: ID на монетата (bitcoin, ethereum, итн.)
        - symbol: Симбол на монетата (BTC, ETH, итн.)

    Пример:
        http://localhost:8000/api/trading-signal?coin=bitcoin&symbol=BTC
    """
    try:
        coin_id = request.GET.get('coin', 'bitcoin')
        coin_symbol = request.GET.get('symbol', 'BTC')

        # Брза анализа само за сигнал
        onchain_metrics = onchain_analyzer.get_onchain_metrics(coin_id)
        articles = sentiment_analyzer.get_crypto_news(coin_id)
        sentiments = sentiment_analyzer.analyze_news_sentiment(articles)
        sentiment_score = sentiment_analyzer.calculate_sentiment_score(sentiments)
        whale_data = onchain_analyzer.get_whale_alert_simulation(coin_symbol)

        signal = combined_analyzer._generate_trading_signal(
            onchain_metrics, sentiment_score, whale_data
        )

        return JsonResponse({
            'success': True,
            'coin': coin_id,
            'signal': signal,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def batch_analysis(request):
    """
    API endpoint за batch анализа на повеќе криптовалути
    POST /api/batch-analysis

    Body (JSON):
    {
        "coins": [
            {"id": "bitcoin", "symbol": "BTC"},
            {"id": "ethereum", "symbol": "ETH"}
        ]
    }

    Пример со curl:
        curl -X POST http://localhost:8000/api/batch-analysis \
        -H "Content-Type: application/json" \
        -d '{"coins": [{"id": "bitcoin", "symbol": "BTC"}, {"id": "ethereum", "symbol": "ETH"}]}'
    """
    try:
        data = json.loads(request.body)
        coins = data.get('coins', [])

        if not coins:
            return JsonResponse({
                'success': False,
                'error': 'No coins provided'
            }, status=400)

        results = []

        for coin in coins:
            coin_id = coin.get('id')
            coin_symbol = coin.get('symbol')

            if coin_id and coin_symbol:
                try:
                    analysis = combined_analyzer.perform_full_analysis(
                        coin_id=coin_id,
                        coin_symbol=coin_symbol,
                        query=coin_id
                    )

                    results.append({
                        'coin': coin_id,
                        'symbol': coin_symbol,
                        'success': True,
                        'trading_signal': analysis['trading_signal'],
                        'sentiment_score': analysis['sentiment']['score'],
                        'onchain_metrics': {
                            'market_cap': analysis['onchain_metrics']['market_cap'],
                            'volume_24h': analysis['onchain_metrics']['total_volume_24h'],
                            'price_change_24h': analysis['onchain_metrics']['price_change_24h']
                        }
                    })
                except Exception as coin_error:
                    results.append({
                        'coin': coin_id,
                        'symbol': coin_symbol,
                        'success': False,
                        'error': str(coin_error)
                    })

        return JsonResponse({
            'success': True,
            'results': results,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_whale_activity(request):
    """
    API endpoint за whale activity (големи трансакции)
    GET /api/whale-activity?symbol=BTC

    Параметри:
        - symbol: Симбол на монетата (BTC, ETH, итн.)

    Пример:
        http://localhost:8000/api/whale-activity?symbol=BTC
    """
    try:
        coin_symbol = request.GET.get('symbol', 'BTC')

        whale_data = onchain_analyzer.get_whale_alert_simulation(coin_symbol)

        return JsonResponse({
            'success': True,
            'symbol': coin_symbol,
            'whale_transactions': whale_data,
            'count': len(whale_data),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Опционален view за homepage/dashboard
@require_http_methods(["GET"])
def onchain_dashboard(request):
    """
    Render HTML dashboard (ако имаш frontend template)
    GET /onchain-dashboard/
    """
    from django.shortcuts import render

    # Можеш да го рендираш твојот HTML template
    return render(request, 'dashboard.html')
