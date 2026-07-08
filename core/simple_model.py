"""
Lightweight, dependency-free price predictor.

Used as a fallback when TensorFlow/Keras (LSTM) is not available
(e.g. on Python versions TensorFlow doesn't ship wheels for). It trains
a linear model on lagged closing prices using NumPy least squares, so the
Prediction page works everywhere without heavy ML dependencies.
"""

import numpy as np


def simple_predict(df, lookback=10, test_frac=0.2):
    """Return (predictions, real, rmse, r2) as NumPy arrays / floats.

    Mirrors the return contract of ``core.LSTM.train_lstm`` so the view
    can use it interchangeably.
    """
    closes = np.asarray(df["close"], dtype=float)

    if len(closes) < (lookback + 20):
        raise ValueError(
            f"Not enough data to train (need at least {lookback + 20} points, "
            f"got {len(closes)})."
        )

    # Build lagged-feature matrix: predict close[i] from the previous `lookback` closes.
    X, y = [], []
    for i in range(lookback, len(closes)):
        X.append(closes[i - lookback:i])
        y.append(closes[i])
    X = np.asarray(X)
    y = np.asarray(y)

    split = int(len(X) * (1 - test_frac))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    # Solve least squares with a bias term.
    A_train = np.hstack([X_train, np.ones((len(X_train), 1))])
    coef, *_ = np.linalg.lstsq(A_train, y_train, rcond=None)

    A_test = np.hstack([X_test, np.ones((len(X_test), 1))])
    predictions = A_test @ coef

    rmse = float(np.sqrt(np.mean((predictions - y_test) ** 2)))
    ss_res = float(np.sum((y_test - predictions) ** 2))
    ss_tot = float(np.sum((y_test - np.mean(y_test)) ** 2))
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return predictions, y_test, rmse, r2
