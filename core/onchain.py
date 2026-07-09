import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import time

from textblob import TextBlob
import json
import os


class OnChainAnalysis:
    # On-Chain анализа

    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"

    def get_onchain_metrics(self, coin_id='bitcoin', days=30):

        # Собира on-chain метрики од CoinGecko

        try:
            coin_data = requests.get(
                f"{self.base_url}/coins/{coin_id}",
                params={'localization': 'false', 'tickers': 'false',
                        'community_data': 'true', 'developer_data': 'true'},
                timeout=15,
            ).json()

            time.sleep(0.5)

            # Историски податоци
            market_data = requests.get(
                f"{self.base_url}/coins/{coin_id}/market_chart",
                params={'vs_currency': 'usd', 'days': days},
                timeout=15,
            ).json()

            # Пресметка на метрики
            metrics = {
                'market_cap': coin_data['market_data']['market_cap']['usd'],
                'total_volume_24h': coin_data['market_data']['total_volume']['usd'],
                'circulating_supply': coin_data['market_data']['circulating_supply'],
                'total_supply': coin_data['market_data'].get('total_supply', 0),
                'price_change_24h': coin_data['market_data']['price_change_percentage_24h'],
                'price_change_7d': coin_data['market_data']['price_change_percentage_7d'],
                'price_change_30d': coin_data['market_data']['price_change_percentage_30d'],

                # Community
                'twitter_followers': coin_data.get('community_data', {}).get('twitter_followers', 0),
                'reddit_subscribers': coin_data.get('community_data', {}).get('reddit_subscribers', 0),

                # Developer
                'github_forks': coin_data.get('developer_data', {}).get('forks', 0),
                'github_stars': coin_data.get('developer_data', {}).get('stars', 0),


                'nvt_ratio': self._calculate_nvt_ratio(
                    coin_data['market_data']['market_cap']['usd'],
                    coin_data['market_data']['total_volume']['usd']
                ),
                'volume_to_market_cap': coin_data['market_data']['total_volume']['usd'] /
                                        coin_data['market_data']['market_cap']['usd'],
            }

            # волатилност
            prices = [p[1] for p in market_data['prices']]
            returns = np.diff(prices) / prices[:-1]
            metrics['volatility_30d'] = np.std(returns) * np.sqrt(365) * 100

            return metrics

        except Exception as e:
            print(f"Грешка при собирање на метрики: {e}")
            return None

    def get_tvl(self, coin_id):
        # Добива Total Value Locked од DefiLlama API
        try:
            # Мапирање на CoinGecko ID кон DefiLlama slug
            protocol_map = {
                'ethereum': 'ethereum',
                'bitcoin': 'wrapped-bitcoin',
                'binancecoin': 'bsc',
                'solana': 'solana',
                'cardano': 'cardano',
                'avalanche-2': 'avalanche',
                'polygon': 'polygon'
            }

            protocol = protocol_map.get(coin_id)
            if not protocol:
                return None

            response = requests.get(
                f"{self.defillama_url}/tvl/{protocol}",
                timeout=5
            )

            if response.status_code == 200:
                return response.json()
            return None

        except Exception as e:
            print(f"TVL недостапна за {coin_id}: {e}")
            return None
    def _calculate_nvt_ratio(self, market_cap, volume_24h):
        if volume_24h == 0:
            return 0
        return market_cap / (volume_24h * 30)  # Проценка за месечен волумен

    def analyze_exchange_flows(self, coin_id='bitcoin'):

        try:

            tickers = requests.get(
                f"{self.base_url}/coins/{coin_id}/tickers",
                params={'depth': 'true'},
                timeout=15,
            ).json()

            time.sleep(0.5)

            exchange_volumes = {}
            total_volume = 0

            for ticker in tickers.get('tickers', [])[:10]:  # Топ 10 берзи
                exchange = ticker['market']['name']
                volume = ticker.get('converted_volume', {}).get('usd', 0)
                exchange_volumes[exchange] = volume
                total_volume += volume

            # концентрација на волумен
            concentration = {}
            for exchange, volume in exchange_volumes.items():
                concentration[exchange] = (volume / total_volume * 100) if total_volume > 0 else 0 #% Учество по берза

            return {
                'exchange_volumes': exchange_volumes,
                'concentration': concentration,
                'total_volume': total_volume,
                'top_exchange': max(concentration, key=concentration.get) if concentration else None
            }

        except Exception as e:
            print(f"Грешка при анализа на exchange flows: {e}")
            return None

    def get_whale_alert_simulation(self, coin_symbol='BTC'):

        # Симулирани податоци за големи трансакции
        np.random.seed(42)

        whale_transactions = []
        base_amount = 100 if coin_symbol == 'BTC' else 1000

        for i in range(5):
            whale_transactions.append({
                'timestamp': (datetime.now() - timedelta(days=np.random.randint(0, 7))).isoformat(),
                'amount': base_amount * np.random.uniform(10, 100),
                'type': np.random.choice(['exchange_inflow', 'exchange_outflow', 'whale_transfer']),
                'impact': np.random.choice(['bullish', 'bearish', 'neutral'])
            })

        return whale_transactions


class SentimentAnalysis:
    # Сентимент анализа од вести и социјални медиуми

    def __init__(self):
        self.newsapi_url = "https://newsapi.org/v2/everything"
        self.newsapi_key = os.getenv('NEWSAPI_KEY', 'a16a798ad7394417a8c1636b26e2ddab')

        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.vader = SentimentIntensityAnalyzer()
        except Exception as e:
            print(f"VADER not available, using TextBlob only: {e}")
            self.vader = None
    def get_crypto_news(self, query='bitcoin OR ethereum OR crypto', days=7):
        """Собира вести за криптовалути"""
        try:
            from_date = (datetime.now() - timedelta(days=days)).isoformat()

            params = {
                'q': query,
                'from': from_date,
                'sortBy': 'publishedAt',
                'language': 'en',
                'apiKey': self.newsapi_key
            }

            response = requests.get(self.newsapi_url, params=params, timeout=15)

            if response.status_code == 200:
                articles = response.json().get('articles', [])
                return articles[:20]  # Топ 20 вести
            else:
                return self._generate_sample_news(query)

        except Exception as e:
            print(f"Грешка при собирање на вести: {e}")
            return self._generate_sample_news(query)

    def _generate_sample_news(self, query):
        """Генерира примерни вести за тестирање"""
        sample_headlines = [
            "Bitcoin reaches new all-time high amid institutional adoption",
            "Ethereum upgrade shows promising results for scalability",
            "Regulatory concerns impact cryptocurrency markets",
            "Major exchange announces support for new DeFi tokens",
            "Crypto market shows bullish momentum as traders anticipate rate cuts",
            "Security breach raises concerns about decentralized platforms",
            "Institutional investors increase crypto portfolio allocations",
            "New blockchain technology promises faster transaction speeds"
        ]

        articles = []
        for i, headline in enumerate(sample_headlines):
            articles.append({
                'title': headline,
                'description': f"Analysis and insights about {query}",
                'publishedAt': (datetime.now() - timedelta(days=i)).isoformat(),
                'source': {'name': f'Crypto News {i + 1}'}
            })

        return articles

    def analyze_sentiment(self, text):
        blob = TextBlob(text)

        if self.vader is not None:
            vader_scores = self.vader.polarity_scores(text)
        else:
            # Fallback when VADER isn't installed: derive VADER-like scores
            # from TextBlob polarity so sentiment analysis still works.
            polarity = blob.sentiment.polarity  # range -1..1
            vader_scores = {
                'compound': polarity,
                'pos': max(polarity, 0.0),
                'neg': max(-polarity, 0.0),
                'neu': 1.0 - abs(polarity),
            }

        return {
            'vader_compound': vader_scores['compound'],  # -1 до 1
            'vader_positive': vader_scores['pos'],
            'vader_negative': vader_scores['neg'],
            'vader_neutral': vader_scores['neu'],
            'textblob_polarity': blob.sentiment.polarity,
            'sentiment': 'positive' if vader_scores['compound'] > 0.05
            else 'negative' if vader_scores['compound'] < -0.05
            else 'neutral'
        }

    def analyze_news_sentiment(self, articles):
        sentiments = []

        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}"
            sentiment = self.analyze_sentiment(text)

            sentiments.append({
                'title': article.get('title', ''),
                'date': article.get('publishedAt', ''),
                'source': article.get('source', {}).get('name', 'Unknown'),
                'vader_compound': sentiment['vader_compound'],  # 🔥 ПРОМЕНЕТО
                'sentiment': sentiment['sentiment']
            })

        return sentiments

    def calculate_sentiment_score(self, sentiments):
        """Пресметува агрегиран сентимент скор со VADER"""
        if not sentiments:
            return {'score': 0, 'classification': 'neutral'}

        # Користи VADER compound наместо polarity
        avg_compound = np.mean([s['vader_compound'] for s in sentiments])
        positive_ratio = len([s for s in sentiments if s['sentiment'] == 'positive']) / len(sentiments)
        negative_ratio = len([s for s in sentiments if s['sentiment'] == 'negative']) / len(sentiments)

        # Композитен скор (0-100)
        composite_score = ((avg_compound + 1) / 2) * 100

        return {
            'score': composite_score,
            'avg_compound': avg_compound,
            'positive_ratio': positive_ratio,
            'negative_ratio': negative_ratio,
            'classification': 'bullish' if composite_score > 60
                            else 'bearish' if composite_score < 40
                            else 'neutral'
        }


class CombinedAnalysis:
    # Комбинирана On-Chain и Сентимент анализа

    def __init__(self):
        self.onchain = OnChainAnalysis()
        self.sentiment = SentimentAnalysis()

    def perform_full_analysis(self, coin_id='bitcoin', coin_symbol='BTC', query='bitcoin'):

        # 1. On-Chain метрики
        onchain_metrics = self.onchain.get_onchain_metrics(coin_id)

        time.sleep(2)

        # 2. Exchange Flows
        exchange_data = self.onchain.analyze_exchange_flows(coin_id)

        time.sleep(1)

        # 3. Whale Activity
        whale_data = self.onchain.get_whale_alert_simulation(coin_symbol)

        time.sleep(1)

        # 4. News Sentiment
        articles = self.sentiment.get_crypto_news(query)

        # 5. Sentiment Analysis
        sentiments = self.sentiment.analyze_news_sentiment(articles)
        sentiment_score = self.sentiment.calculate_sentiment_score(sentiments)

        # 6. Комбинирана Препорака
        signal = self._generate_trading_signal(onchain_metrics, sentiment_score, whale_data)

        return {
            'onchain_metrics': onchain_metrics,
            'exchange_data': exchange_data,
            'whale_data': whale_data,
            'sentiment': sentiment_score,
            'sentiments_detail': sentiments,
            'trading_signal': signal
        }

    def _generate_trading_signal(self, onchain, sentiment, whale_data):
        """Генерира препорака за тргување со реалистичен confidence"""
        bullish_signals = 0
        bearish_signals = 0


        if onchain:

            # 24h Price Momentum
            if onchain['price_change_24h'] > 5:
                bullish_signals += 2
            elif onchain['price_change_24h'] > 2:
                bullish_signals += 1
            elif onchain['price_change_24h'] < -5:
                bearish_signals += 2
            elif onchain['price_change_24h'] < -2:
                bearish_signals += 1

            # 7 Day Trend
            if onchain['price_change_7d'] > 5:
                bullish_signals += 1
            elif onchain['price_change_7d'] < -5:
                bearish_signals += 1

            # Volume Strength
            if onchain['volume_to_market_cap'] > 0.1:
                bullish_signals += 1
            elif onchain['volume_to_market_cap'] < 0.02:
                bearish_signals += 1

            # NVT Ratio
            if onchain['nvt_ratio'] < 30:
                bullish_signals += 1
            elif onchain['nvt_ratio'] > 120:
                bearish_signals += 1


        if sentiment['score'] > 75:
            bullish_signals += 3
        elif sentiment['score'] > 60:
            bullish_signals += 2
        elif sentiment['score'] < 30:
            bearish_signals += 3
        elif sentiment['score'] < 40:
            bearish_signals += 2


        outflows = len([w for w in whale_data if w['type'] == 'exchange_outflow'])
        inflows = len([w for w in whale_data if w['type'] == 'exchange_inflow'])

        if outflows > inflows + 2:
            bullish_signals += 2
        elif outflows > inflows:
            bullish_signals += 1
        elif inflows > outflows + 2:
            bearish_signals += 2
        elif inflows > outflows:
            bearish_signals += 1


        total = bullish_signals + bearish_signals
        diff = abs(bullish_signals - bearish_signals)

        # BUY / SELL
        buy_score = max(0, bullish_signals - bearish_signals)
        sell_score = max(0, bearish_signals - bullish_signals)

        # HOLD
        hold_score = max(0, total - diff)

        epsilon = 0.2
        buy_score += epsilon
        sell_score += epsilon
        hold_score += epsilon

        scores = [buy_score, sell_score, hold_score]
        score_sum = sum(scores)

        buy_prob = (buy_score / score_sum) * 100
        sell_prob = (sell_score / score_sum) * 100
        hold_prob = (hold_score / score_sum) * 100


        max_prob = max(buy_prob, sell_prob, hold_prob)

        if max_prob == buy_prob:
            action = "BUY"
            confidence = buy_prob
            reasoning = f"Detected {bullish_signals} bullish vs {bearish_signals} bearish signals"

        elif max_prob == sell_prob:
            action = "SELL"
            confidence = sell_prob
            reasoning = f"Detected {bearish_signals} bearish vs {bullish_signals} bullish signals"

        else:
            action = "HOLD"
            confidence = hold_prob
            reasoning = "Market signals are balanced — best action is to wait"


        # confidence = min(confidence, 90)
        # confidence = round(confidence, 1)

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals
        }

    def save_results_to_csv(self, results, filename='onchain_sentiment_results.csv'):

        data = []

        row = {
            'timestamp': datetime.now().isoformat(),
            'market_cap': results['onchain_metrics']['market_cap'],
            'volume_24h': results['onchain_metrics']['total_volume_24h'],
            'nvt_ratio': results['onchain_metrics']['nvt_ratio'],
            'volatility': results['onchain_metrics']['volatility_30d'],
            'sentiment_score': results['sentiment']['score'],
            'sentiment_class': results['sentiment']['classification'],
            'positive_ratio': results['sentiment']['positive_ratio'],
            'trading_signal': results['trading_signal']['action'],
            'confidence': results['trading_signal']['confidence']
        }

        df = pd.DataFrame([row])

        # Додај на постоечки или креирај нов
        if os.path.exists(filename):
            df.to_csv(filename, mode='a', header=False, index=False)
        else:
            df.to_csv(filename, index=False)

        print(f" Резултати зачувани во {filename}")



if __name__ == "__main__":
    analyzer = CombinedAnalysis()

    print(" Стартувам анализа на Bitcoin...")
    btc_results = analyzer.perform_full_analysis(
        coin_id='bitcoin',
        coin_symbol='BTC',
        query='bitcoin'
    )

    analyzer.save_results_to_csv(btc_results, 'bitcoin_analysis.csv')

    print("\n" + "=" * 60)

    print("\n Стартувам анализа на Ethereum...")
    eth_results = analyzer.perform_full_analysis(
        coin_id='ethereum',
        coin_symbol='ETH',
        query='ethereum'
    )

    analyzer.save_results_to_csv(eth_results, 'ethereum_analysis.csv')