"""Análisis de patrones temporales para detección de bots."""

import logging
from collections import Counter
from datetime import datetime

import numpy as np
from sqlmodel import Session, select

from bodegas.db.models import Tweet
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)


def analyze_posting_patterns(account_id: str) -> dict | None:
    """Analizar patrones temporales detallados de una cuenta.

    Retorna None si no hay suficientes tweets.
    """
    engine = get_engine()
    with Session(engine) as session:
        tweets = session.exec(
            select(Tweet)
            .where(Tweet.author_id == account_id)
            .where(Tweet.created_at.isnot(None))
            .order_by(Tweet.created_at)
        ).all()

    if len(tweets) < 5:
        return None

    timestamps = [t.created_at for t in tweets]
    hours = [ts.hour for ts in timestamps]
    days = [ts.weekday() for ts in timestamps]  # 0=lunes, 6=domingo

    # Distribución por hora
    hour_dist = Counter(hours)
    hour_counts = [hour_dist.get(h, 0) for h in range(24)]

    # Distribución por día de semana
    day_dist = Counter(days)
    day_counts = [day_dist.get(d, 0) for d in range(7)]

    # Intervalos entre tweets consecutivos
    intervals = []
    for i in range(1, len(timestamps)):
        delta = (timestamps[i] - timestamps[i - 1]).total_seconds()
        intervals.append(delta)

    # Detectar coordinación: muchos tweets en ventanas de 1 minuto
    minute_buckets = Counter()
    for ts in timestamps:
        bucket = ts.replace(second=0, microsecond=0)
        minute_buckets[bucket] += 1

    coordinated_minutes = sum(1 for count in minute_buckets.values() if count >= 3)

    return {
        "total_tweets": len(tweets),
        "hour_distribution": hour_counts,
        "day_distribution": day_counts,
        "peak_hour": max(range(24), key=lambda h: hour_counts[h]),
        "peak_day": max(range(7), key=lambda d: day_counts[d]),
        "avg_interval_seconds": float(np.mean(intervals)),
        "min_interval_seconds": float(np.min(intervals)),
        "max_interval_seconds": float(np.max(intervals)),
        "interval_std": float(np.std(intervals)),
        "burst_count": sum(1 for i in intervals if i < 10),
        "rapid_fire_count": sum(1 for i in intervals if i < 2),
        "coordinated_minutes": coordinated_minutes,
    }
