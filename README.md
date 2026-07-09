# Chartr

Chartr is a crypto research dashboard built with Django. Open the app, pick a coin, and move between price charts, indicator breakdowns, short-term forecasts, chain activity, and headline sentiment without switching tools.

The interface is a single-page shell with a sidebar: Dashboard, All Coins, News, Technical Analysis, AI Prediction, and On-Chain. Search in the header jumps straight to a coin detail page via CoinPaprika.

## What you get

**Market view.** The home screen shows live top coins and a news preview. The coin list pulls from CoinGecko with a CoinPaprika fallback when rate limits hit. Each coin page renders an interactive chart (1D through 5Y) using CoinGecko and CryptoCompare data.

**Technical Analysis.** Pick a symbol and Chartr runs RSI, MACD, moving averages, Stochastic, CCI, ADX, and Bollinger Bands over stored OHLCV history. Results roll up into buy, sell, or hold signals per indicator and an overall read.

**AI Prediction.** With TensorFlow installed locally, predictions use an LSTM. On Render (or any environment without TensorFlow), the same page falls back to a small NumPy linear model. Both need historical rows in the database — see seeding below.

**On-Chain & Sentiment.** A dedicated dashboard combines CoinGecko on-chain stats, exchange flow estimates, whale-movement heuristics, and news sentiment (TextBlob; VADER is optional). JSON endpoints under `/api/` expose the same analysis for programmatic use.

## Run it locally

You need Python 3.12 or newer.

```bash
git clone <repo-url>
cd chartr
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_ohlcv
python manage.py runserver
```

Visit `http://127.0.0.1:8000`.

`seed_ohlcv` is the important step on a fresh clone. It creates the `crypto_ohlcv` table and pulls roughly a year of daily candles for fifteen major assets from CryptoCompare. Without it, Technical Analysis and Prediction will have nothing to work with.

### Environment variables

All are optional for local SQLite development. Create a `.env` in the project root if you need overrides:

```
SECRET_KEY=change-me
DEBUG=1
CRYPTOCOMPARE_API_KEY=your-key-here
```

For MySQL instead of SQLite, set `DB_ENGINE=mysql` plus `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, and `DB_PORT`. Production on Render uses `DATABASE_URL` (PostgreSQL) automatically.

## Code layout

The Django project package is `chartr/` (settings, WSGI/ASGI). Application logic lives in `core/` — views, `technical_analysis.py`, `onchain.py`, `LSTM.py`, and `simple_model.py`. Templates are in `templates/` and front-end assets in `static/`. `manage.py` sits at the repo root.

## Hosting on Render

`render.yaml` defines a web service and a free Postgres instance. Push to GitHub, import the blueprint in Render, and deploy. The build script installs `requirements-render.txt` (no TensorFlow), collects static files, migrates, and re-runs `seed_ohlcv` on each deploy.

Gunicorn starts with:

```
gunicorn chartr.wsgi:application --bind 0.0.0.0:$PORT
```

## Notes

- External APIs: CoinGecko, CoinPaprika, CryptoCompare. Responses are cached where practical.
