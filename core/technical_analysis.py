import pandas as pd
import ta


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:


    df = df.copy()


    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    # Осцилатори

    df["RSI"] = ta.momentum.rsi(df["close"], window=14)
    df["Stochastic"] = ta.momentum.stoch(
        df["high"], df["low"], df["close"], window=14
    )
    df["ADX"] = ta.trend.adx(
        df["high"], df["low"], df["close"], window=14
    )
    df["CCI"] = ta.trend.cci(
        df["high"], df["low"], df["close"], window=20
    )

    # MACD
    df["MACD"] = ta.trend.macd(df["close"])
    df["MACD_SIGNAL"] = ta.trend.macd_signal(df["close"])


    # Moving avg
    df["SMA"] = ta.trend.sma_indicator(df["close"], window=20)
    df["EMA"] = ta.trend.ema_indicator(df["close"], window=20)
    df["WMA"] = ta.trend.wma_indicator(df["close"], window=20)

    # bb
    bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
    df["BB_HIGH"] = bb.bollinger_hband()
    df["BB_LOW"] = bb.bollinger_lband()

    # Volume MA
    df["VOL_MA"] = df["volume"].rolling(window=20).mean()

    return df
