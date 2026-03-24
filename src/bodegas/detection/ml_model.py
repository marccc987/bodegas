"""Modelo de ML para detección de bots (Random Forest / XGBoost)."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from bodegas.db.models import Account
from bodegas.db.session import get_engine
from bodegas.detection.features import extract_all_features

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "account_age_days", "has_avatar", "has_bio", "bio_length",
    "username_entropy", "has_numeric_suffix", "username_looks_random",
    "followers_count", "following_count", "tweet_count",
    "tweets_per_day", "follower_following_ratio", "is_verified",
    "total_tweets_collected", "retweet_ratio", "reply_ratio", "avg_text_length",
    "posting_hour_entropy", "night_posting_ratio", "burst_count",
    "avg_interval_seconds", "interval_variance",
    "in_degree", "out_degree", "pagerank", "betweenness", "closeness", "clustering",
]


def build_feature_matrix(graph_metrics: dict[str, dict] | None = None) -> pd.DataFrame:
    """Construir matriz de features para todas las cuentas."""
    engine = get_engine()
    rows = []

    with Session(engine) as session:
        accounts = session.exec(select(Account)).all()
        for account in accounts:
            features = extract_all_features(account, graph_metrics)
            features["account_id"] = account.id
            features["username"] = account.username
            features["current_label"] = account.bot_label
            rows.append(features)

    df = pd.DataFrame(rows)
    logger.info(f"Matriz de features: {len(df)} cuentas, {len(df.columns)} columnas")
    return df


def train_model(
    df: pd.DataFrame,
    label_column: str = "current_label",
    model_type: str = "random_forest",
) -> dict:
    """Entrenar modelo de clasificación.

    Usa las etiquetas existentes (de heurísticas o manuales) como ground truth.
    Retorna dict con modelo, métricas y feature importance.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder

    # Filtrar cuentas con label
    labeled = df[df[label_column].notna()].copy()
    if len(labeled) < 20:
        raise ValueError(
            f"Se necesitan al menos 20 cuentas etiquetadas. "
            f"Actualmente hay {len(labeled)}. Ejecuta primero la detección heurística."
        )

    # Preparar features
    available_cols = [c for c in FEATURE_COLUMNS if c in labeled.columns]
    X = labeled[available_cols].fillna(0).values
    le = LabelEncoder()
    y = le.fit_transform(labeled[label_column])

    # Entrenar
    if model_type == "xgboost":
        try:
            from xgboost import XGBClassifier
            model = XGBClassifier(
                n_estimators=100, max_depth=5, random_state=42,
                use_label_encoder=False, eval_metric="mlogloss",
            )
        except ImportError:
            logger.warning("XGBoost no disponible, usando Random Forest")
            model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    else:
        model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)

    # Cross-validation
    scores = cross_val_score(model, X, y, cv=min(5, len(set(y))), scoring="accuracy")
    logger.info(f"Cross-val accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")

    # Entrenar modelo final con todos los datos
    model.fit(X, y)

    # Feature importance
    importances = dict(zip(available_cols, model.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "model": model,
        "label_encoder": le,
        "feature_columns": available_cols,
        "cv_accuracy": float(scores.mean()),
        "cv_std": float(scores.std()),
        "top_features": top_features,
        "classes": le.classes_.tolist(),
    }


def predict(
    df: pd.DataFrame,
    model_result: dict,
) -> pd.DataFrame:
    """Predecir labels para todas las cuentas usando el modelo entrenado."""
    model = model_result["model"]
    le = model_result["label_encoder"]
    cols = model_result["feature_columns"]

    X = df[cols].fillna(0).values
    predictions = model.predict(X)
    probas = model.predict_proba(X)

    df = df.copy()
    df["ml_label"] = le.inverse_transform(predictions)
    df["ml_confidence"] = np.max(probas, axis=1)

    return df


def save_ml_predictions(df: pd.DataFrame) -> int:
    """Guardar predicciones ML en la base de datos."""
    if "ml_label" not in df.columns:
        return 0

    engine = get_engine()
    updated = 0
    with Session(engine) as session:
        for _, row in df.iterrows():
            account = session.get(Account, row["account_id"])
            if account:
                account.bot_label = row["ml_label"]
                account.bot_score = float(row.get("ml_confidence", 0))
                updated += 1
        session.commit()

    logger.info(f"Predicciones ML guardadas para {updated} cuentas")
    return updated
