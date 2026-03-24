"""Análisis de contenido de tweets para detección de bots."""

import logging
import re
from collections import Counter

from sqlmodel import Session, select

from bodegas.db.models import Tweet
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)


def _extract_hashtags(text: str) -> list[str]:
    return re.findall(r"#(\w+)", text)


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text)


def _extract_mentions(text: str) -> list[str]:
    return re.findall(r"@(\w+)", text)


def analyze_content(account_id: str) -> dict | None:
    """Analizar contenido de tweets de una cuenta.

    Retorna None si no hay suficientes tweets.
    """
    engine = get_engine()
    with Session(engine) as session:
        tweets = session.exec(
            select(Tweet).where(Tweet.author_id == account_id)
        ).all()

    if len(tweets) < 3:
        return None

    texts = [t.text for t in tweets if t.text]
    if not texts:
        return None

    # Métricas básicas
    avg_length = sum(len(t) for t in texts) / len(texts)
    all_hashtags = []
    all_urls = []
    all_mentions = []
    for text in texts:
        all_hashtags.extend(_extract_hashtags(text))
        all_urls.extend(_extract_urls(text))
        all_mentions.extend(_extract_mentions(text))

    hashtag_density = len(all_hashtags) / len(texts)
    url_density = len(all_urls) / len(texts)
    mention_density = len(all_mentions) / len(texts)

    # Duplicados: cuántos tweets son idénticos
    text_counts = Counter(texts)
    duplicate_ratio = sum(c - 1 for c in text_counts.values() if c > 1) / len(texts)

    # Similitud de contenido usando TF-IDF
    content_similarity = 0.0
    if len(texts) >= 5:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            vectorizer = TfidfVectorizer(max_features=500, stop_words=None)
            tfidf_matrix = vectorizer.fit_transform(texts)
            sim_matrix = cosine_similarity(tfidf_matrix)
            # Promedio de similitud entre pares (excluyendo diagonal)
            n = sim_matrix.shape[0]
            if n > 1:
                upper_tri = sim_matrix[np.triu_indices(n, k=1)]
                content_similarity = float(np.mean(upper_tri))
        except Exception:
            pass

    # Top hashtags usados
    top_hashtags = Counter(all_hashtags).most_common(10)

    return {
        "total_texts": len(texts),
        "avg_text_length": round(avg_length, 1),
        "hashtag_density": round(hashtag_density, 2),
        "url_density": round(url_density, 2),
        "mention_density": round(mention_density, 2),
        "duplicate_ratio": round(duplicate_ratio, 3),
        "content_similarity": round(content_similarity, 4),
        "unique_hashtags": len(set(all_hashtags)),
        "top_hashtags": top_hashtags,
    }
