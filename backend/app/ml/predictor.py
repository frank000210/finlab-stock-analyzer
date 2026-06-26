"""ML Stock Predictor - Random Forest based price direction prediction."""

import pandas as pd
import numpy as np
from typing import Optional

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ..analysis.technical import TechnicalAnalyzer


class StockPredictor:
    """Predicts stock price direction using Random Forest."""

    def __init__(self):
        self.analyzer = TechnicalAnalyzer()
        self.model = None
        self.scaler = None

    def predict(
        self, df: pd.DataFrame, horizon: int = 5, threshold: float = 0.02
    ) -> dict:
        """
        Predict price direction for the given horizon.
        
        Args:
            df: OHLCV DataFrame
            horizon: Prediction horizon in days
            threshold: Min return to classify as 'up'
            
        Returns:
            Prediction result with direction, confidence, feature importance
        """
        if not HAS_SKLEARN:
            return {"error": "scikit-learn not installed"}

        if len(df) < 100:
            return {"error": "Insufficient data for prediction (need 100+ rows)"}

        # Prepare features
        features_df = self._prepare_features(df)
        if features_df.empty:
            return {"error": "Feature preparation failed"}

        # Create labels
        features_df["target"] = (
            features_df["close"].shift(-horizon) / features_df["close"] - 1
        ).apply(lambda x: 1 if x > threshold else 0)

        # Drop NaN rows
        features_df = features_df.dropna()
        if len(features_df) < 60:
            return {"error": "Not enough clean data after feature engineering"}

        # Split features and target
        feature_cols = [c for c in features_df.columns if c not in [
            "date", "target", "open", "high", "low", "close", "volume"
        ]]
        X = features_df[feature_cols].values
        y = features_df["target"].values

        # Train on all but last row, predict last
        X_train, y_train = X[:-1], y[:-1]
        X_pred = X[-1:].reshape(1, -1)

        # Scale
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_pred_scaled = self.scaler.transform(X_pred)

        # Train model
        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=10, random_state=42, n_jobs=-1
        )
        self.model.fit(X_train_scaled, y_train)

        # Predict
        proba = self.model.predict_proba(X_pred_scaled)[0]
        prediction = int(self.model.predict(X_pred_scaled)[0])

        # Feature importance
        importances = sorted(
            zip(feature_cols, self.model.feature_importances_),
            key=lambda x: x[1], reverse=True
        )[:10]

        # Model accuracy (simple train accuracy as reference)
        train_acc = self.model.score(X_train_scaled, y_train)

        direction = "up" if prediction == 1 else "down"
        confidence = float(max(proba))

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "horizon_days": horizon,
            "probabilities": {
                "up": round(float(proba[1]) if len(proba) > 1 else 0, 4),
                "down": round(float(proba[0]), 4),
            },
            "feature_importance": [
                {"feature": name, "importance": round(float(imp), 4)}
                for name, imp in importances
            ],
            "model_accuracy": round(float(train_acc), 4),
        }

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare features for ML model."""
        indicators = ["ma", "ema", "bollinger", "macd", "kd", "rsi", "atr", "volume"]
        result = self.analyzer.compute(df.copy(), indicators)

        # Add lagged features (1, 3, 5, 10 days)
        for lag in [1, 3, 5, 10]:
            result[f"return_{lag}d"] = result["close"].pct_change(lag)
            result[f"vol_change_{lag}d"] = result["volume"].pct_change(lag)

        # Price position relative to MA
        if "ma20" in result.columns:
            result["price_vs_ma20"] = result["close"] / result["ma20"] - 1
        if "ma60" in result.columns:
            result["price_vs_ma60"] = result["close"] / result["ma60"] - 1

        # Volatility
        result["volatility_20"] = result["close"].pct_change().rolling(20).std()

        return result
