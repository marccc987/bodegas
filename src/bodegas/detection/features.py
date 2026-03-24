"""Extracción de features por cuenta para detección de bots."""

import math
import re
from collections import Counter
from datetime import datetime

import numpy as np
from sqlmodel import Session, select

from bodegas.db.models import Account, Tweet
from bodegas.db.session import get_engine


def _entropy(values: list) -> float:
    """Calcular entropía de Shannon de una distribución."""
    if not values:
        return 0.0
    counts = Counter(values)
    total = sum(counts.values())
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _username_entropy(username: str) -> float:
    """Entropía de caracteres del username. Alta = más aleatorio."""
    if not username:
        return 0.0
    return _entropy(list(username))


def _has_numeric_suffix(username: str) -> bool:
    """Detectar si el username termina en secuencia numérica larga."""
    return bool(re.search(r"\d{5,}$", username))


def _username_looks_random(username: str) -> bool:
    """Heurística: username parece generado aleatoriamente."""
    if not username:
        return False
    # Ratio de dígitos
    digits = sum(1 for c in username if c.isdigit())
    if len(username) > 0 and digits / len(username) > 0.5:
        return True
    # Patrón común de bots: letras + números largos
    if re.match(r"^[a-zA-Z]{2,8}\d{5,}$", username):
        return True
    return False


def extract_profile_features(account: Account) -> dict:
    """Features basadas en el perfil de la cuenta."""
    now = datetime.utcnow()
    account_age_days = 0
    if account.created_at:
        account_age_days = max((now - account.created_at).days, 1)

    tweets_per_day = account.tweet_count / max(account_age_days, 1)

    follower_following_ratio = 0.0
    if account.following_count > 0:
        follower_following_ratio = account.followers_count / account.following_count

    return {
        "account_age_days": account_age_days,
        "has_avatar": int(account.has_avatar),
        "has_bio": int(account.has_bio),
        "bio_length": len(account.bio),
        "username_entropy": _username_entropy(account.username),
        "has_numeric_suffix": int(_has_numeric_suffix(account.username)),
        "username_looks_random": int(_username_looks_random(account.username)),
        "followers_count": account.followers_count,
        "following_count": account.following_count,
        "tweet_count": account.tweet_count,
        "tweets_per_day": tweets_per_day,
        "follower_following_ratio": follower_following_ratio,
        "is_verified": int(account.is_verified),
    }


def extract_activity_features(account_id: str) -> dict:
    """Features basadas en la actividad (tweets almacenados)."""
    engine = get_engine()
    with Session(engine) as session:
        tweets = session.exec(
            select(Tweet).where(Tweet.author_id == account_id)
        ).all()

    if not tweets:
        return {
            "total_tweets_collected": 0,
            "retweet_ratio": 0.0,
            "reply_ratio": 0.0,
            "avg_text_length": 0.0,
        }

    total = len(tweets)
    retweets = sum(1 for t in tweets if t.is_retweet)
    replies = sum(1 for t in tweets if t.is_reply)
    avg_text_len = np.mean([len(t.text) for t in tweets]) if tweets else 0

    return {
        "total_tweets_collected": total,
        "retweet_ratio": retweets / total,
        "reply_ratio": replies / total,
        "avg_text_length": float(avg_text_len),
    }


def extract_temporal_features(account_id: str) -> dict:
    """Features basadas en patrones temporales de posting."""
    engine = get_engine()
    with Session(engine) as session:
        tweets = session.exec(
            select(Tweet)
            .where(Tweet.author_id == account_id)
            .where(Tweet.created_at.isnot(None))
        ).all()

    if len(tweets) < 3:
        return {
            "posting_hour_entropy": 0.0,
            "night_posting_ratio": 0.0,
            "burst_count": 0,
            "avg_interval_seconds": 0.0,
            "interval_variance": 0.0,
        }

    # Horas de posting
    hours = [t.created_at.hour for t in tweets if t.created_at]
    hour_entropy = _entropy(hours)

    # Ratio de tweets en madrugada (1am-6am Colombia = UTC-5)
    night_tweets = sum(1 for h in hours if 6 <= h <= 11)  # 1am-6am COT en UTC
    night_ratio = night_tweets / len(hours) if hours else 0

    # Intervalos entre tweets
    sorted_tweets = sorted(tweets, key=lambda t: t.created_at)
    intervals = []
    for i in range(1, len(sorted_tweets)):
        delta = (sorted_tweets[i].created_at - sorted_tweets[i - 1].created_at).total_seconds()
        intervals.append(delta)

    avg_interval = float(np.mean(intervals)) if intervals else 0
    interval_var = float(np.var(intervals)) if intervals else 0

    # Detección de ráfagas (tweets con < 10 segundos de diferencia)
    bursts = sum(1 for i in intervals if i < 10)

    return {
        "posting_hour_entropy": hour_entropy,
        "night_posting_ratio": night_ratio,
        "burst_count": bursts,
        "avg_interval_seconds": avg_interval,
        "interval_variance": interval_var,
    }


def extract_network_features(node_id: str, metrics: dict[str, dict]) -> dict:
    """Features basadas en métricas de red (pre-calculadas)."""
    node_metrics = metrics.get(node_id, {})
    return {
        "in_degree": node_metrics.get("in_degree", 0),
        "out_degree": node_metrics.get("out_degree", 0),
        "pagerank": node_metrics.get("pagerank", 0.0),
        "betweenness": node_metrics.get("betweenness", 0.0),
        "closeness": node_metrics.get("closeness", 0.0),
        "clustering": node_metrics.get("clustering", 0.0),
    }


def extract_all_features(
    account: Account,
    graph_metrics: dict[str, dict] | None = None,
) -> dict:
    """Extraer todas las features para una cuenta."""
    features = {}
    features.update(extract_profile_features(account))
    features.update(extract_activity_features(account.id))
    features.update(extract_temporal_features(account.id))
    if graph_metrics:
        features.update(extract_network_features(account.id, graph_metrics))
    return features
