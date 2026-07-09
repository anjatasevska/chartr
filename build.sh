#!/usr/bin/env bash
# Render build script for Chartr.
# Runs on every deploy: install deps, collect static, migrate, seed market data.
set -o errexit

pip install --upgrade pip
pip install -r requirements-render.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Seed OHLCV — retry a few times (CryptoCompare may rate-limit on first deploy).
for attempt in 1 2 3; do
  python manage.py seed_ohlcv --days 200 --symbols BTC ETH SOL BNB XRP ADA DOGE && break
  echo "seed_ohlcv attempt $attempt failed, retrying in 15s..."
  sleep 15
done
