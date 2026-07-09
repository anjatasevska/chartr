"""
Seed the local `crypto_ohlcv` table with daily OHLCV data.

This makes the Technical Analysis and AI Prediction pages work out of the box
on a fresh SQLite database (no MySQL / scraper pipeline required).

Usage:
    python manage.py seed_ohlcv
    python manage.py seed_ohlcv --days 400 --symbols BTC ETH SOL
"""

import time

from django.core.management.base import BaseCommand
from django.db import connection

from core.market_data import DEFAULT_SYMBOLS, fetch_ohlcv_api

COIN_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "Binance Coin", "SOL": "Solana",
    "XRP": "XRP", "ADA": "Cardano", "DOGE": "Dogecoin", "DOT": "Polkadot",
    "LTC": "Litecoin", "LINK": "Chainlink", "AVAX": "Avalanche", "MATIC": "Polygon",
    "TRX": "TRON", "XLM": "Stellar", "ATOM": "Cosmos",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS crypto_ohlcv (
    timestamp  BIGINT  NOT NULL,
    exchange   TEXT,
    asset_id   TEXT,
    symbol     TEXT    NOT NULL,
    name       TEXT,
    pair       TEXT,
    date       TEXT,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     REAL,
    scraped_at TEXT,
    PRIMARY KEY (timestamp, symbol)
);
"""


class Command(BaseCommand):
    help = "Create and seed the crypto_ohlcv table with daily OHLCV data from CryptoCompare."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365,
                            help="Number of daily candles to fetch per coin (default: 365).")
        parser.add_argument("--symbols", nargs="+", default=None,
                            help="Symbols to seed (default: a curated top list).")

    def fetch_cryptocompare(self, symbol, days):
        return fetch_ohlcv_api(symbol, days)

    def handle(self, *args, **options):
        days = options["days"]
        symbols = options["symbols"] or DEFAULT_SYMBOLS

        with connection.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)

        self.stdout.write(self.style.NOTICE(f"Seeding {len(symbols)} coins ({days} days each)..."))

        total_rows = 0
        for i, symbol in enumerate(symbols, 1):
            symbol = symbol.upper()
            candles = self.fetch_cryptocompare(symbol, days)

            if not candles:
                self.stdout.write(self.style.WARNING(f"[{i}/{len(symbols)}] {symbol}: no data, skipped"))
                continue

            name = COIN_NAMES.get(symbol, symbol)
            rows = [
                (
                    c["time"], "cryptocompare", symbol.lower(), symbol, name,
                    f"{symbol}/USD", None,
                    c["open"], c["high"], c["low"], c["close"], c["volumeto"],
                    None,
                )
                for c in candles
            ]

            # Use the right "insert or update" syntax for the active DB backend.
            vendor = connection.vendor  # 'postgresql', 'sqlite', 'mysql'
            if vendor == "postgresql":
                insert_sql = """
                    INSERT INTO crypto_ohlcv
                    (timestamp, exchange, asset_id, symbol, name, pair, date,
                     open, high, low, close, volume, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high,
                        low = EXCLUDED.low, close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """
            else:
                insert_sql = """
                    INSERT OR REPLACE INTO crypto_ohlcv
                    (timestamp, exchange, asset_id, symbol, name, pair, date,
                     open, high, low, close, volume, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

            with connection.cursor() as cur:
                cur.executemany(insert_sql, rows)

            total_rows += len(rows)
            self.stdout.write(self.style.SUCCESS(f"[{i}/{len(symbols)}] {symbol}: {len(rows)} rows"))
            time.sleep(0.15)

        self.stdout.write(self.style.SUCCESS(f"Done. Inserted {total_rows} rows across {len(symbols)} coins."))
