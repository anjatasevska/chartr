#!/usr/bin/env bash
# Render build script for Chartr.
# Runs on every deploy: install deps, collect static, migrate, seed market data.
set -o errexit

pip install --upgrade pip
pip install -r requirements-render.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

# Create + fill the crypto_ohlcv table so Technical Analysis and AI Prediction
# work out of the box. Idempotent (ON CONFLICT), safe to run every deploy.
python manage.py seed_ohlcv || echo "seed_ohlcv failed (continuing) — data may be rate-limited"
