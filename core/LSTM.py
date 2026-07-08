# core/LSTM.py

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, r2_score
import warnings

warnings.filterwarnings('ignore')


LOOKBACK = 30
EPOCHS = 50


def create_sequences(data, lookback=LOOKBACK):
    """Креира секвенци за LSTM од нормализирани податоци"""
    X, y = [], []
    for i in range(len(data) - lookback):
        X.append(data[i:i + lookback])
        y.append(data[i + lookback, 0])  # само close цена
    return np.array(X), np.array(y)


def train_lstm(df):
    """
    Тренира LSTM модел за предвидување на цени

    Args:
        df: DataFrame со 'close' колона (и опционално open, high, low, volume)

    Returns:
        tuple: (predictions, real_values, rmse, r2)

    Raises:
        ValueError: Ако нема доволно податоци
    """
    # Проверka дали има доволно податоци
    min_required = LOOKBACK + 20
    if len(df) < min_required:
        raise ValueError(
            f"Need at least {min_required} data points for LSTM training. "
            f"Got only {len(df)}. Try collecting more historical data."
        )


    prices = df['close'].values.reshape(-1, 1)

    print(f"Training LSTM with {len(prices)} data points...")

    # Нормализација (0-1 range)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(prices)


    X, y = create_sequences(scaled_data, LOOKBACK)

    print(f"Created {len(X)} sequences (lookback={LOOKBACK})")

    # 70% train, 30% test
    split_index = int(len(X) * 0.7)
    X_train, X_test = X[:split_index], X[split_index:]
    y_train, y_test = y[:split_index], y[split_index:]

    print(f"📈 Training on {len(X_train)} samples, testing on {len(X_test)} samples")

    # LSTM модел
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(LOOKBACK, 1)),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1)
    ])


    model.compile(optimizer='adam', loss='mse', metrics=['mae'])

    # Тренирање
    print(f"Training for {EPOCHS} epochs...")
    history = model.fit(
        X_train, y_train,
        epochs=EPOCHS,
        batch_size=32,
        validation_split=0.15,
        verbose=0
    )


    predictions_scaled = model.predict(X_test, verbose=0)

    # Инверзна трансформација
    predictions = scaler.inverse_transform(predictions_scaled).flatten()
    y_test_real = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()

    #rmse, r2 i mpe
    rmse = np.sqrt(mean_squared_error(y_test_real, predictions))
    r2 = r2_score(y_test_real, predictions)
    mape = np.mean(np.abs((y_test_real - predictions) / y_test_real)) * 100

    print(f"\n📊 Results:")
    print(f"   RMSE: {rmse:.4f}")
    print(f"   R²:   {r2:.4f}")
    print(f"   MAPE: {mape:.2f}%")
    print(f"Training complete!\n")

    return predictions, y_test_real, rmse, r2


def calculate_mape(y_true, y_pred):
    # Пресметува Mean Absolute Percentage Error
    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

