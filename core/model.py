"""Train / predict stubs. RandomForest wiring lands with Model page (H step 5)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def train_model(features: pd.DataFrame, labels: pd.Series) -> Any:
    """Fit RandomForestClassifier. Skeleton returns None until step 5."""
    _ = (features, labels)
    return None


def predict_proba(model: Any, features: pd.DataFrame) -> pd.DataFrame:
    """Return buy/hold/sell probabilities. Skeleton returns empty frame."""
    _ = (model, features)
    return pd.DataFrame(columns=["buy", "hold", "sell"])
