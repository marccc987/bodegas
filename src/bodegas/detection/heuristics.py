"""Detección de bots basada en reglas heurísticas.

Incluye reglas para:
1. Bots clásicos (cuentas nuevas, sin perfil, usernames aleatorios)
2. Cuentas de campaña coordinada (nombre de candidato, solo RT de una persona)
3. Comportamiento sospechoso (ráfagas, actividad concentrada)
"""

import logging
import re

from sqlmodel import Session, select

from bodegas.db.models import Account, Relationship
from bodegas.db.session import get_engine
from bodegas.detection.features import extract_all_features

logger = logging.getLogger(__name__)


def _is_campaign_account_name(username: str, bio: str) -> bool:
    """Detectar si el nombre/bio sugiere cuenta de campaña dedicada."""
    combined = (username + " " + bio).lower()
    campaign_keywords = [
        "presidente", "pte", "sincensura", "sin censura",
        "defensores", "cuenta de apoyo", "firme por",
    ]
    return any(kw in combined for kw in campaign_keywords)


def _get_retweet_concentration(account_id: str) -> float:
    """Qué % de las interacciones salientes van a un solo target."""
    engine = get_engine()
    with Session(engine) as session:
        rels = session.exec(
            select(Relationship).where(Relationship.source_id == account_id)
        ).all()
    if not rels:
        return 0.0
    weights_by_target = {}
    for r in rels:
        weights_by_target[r.target_id] = weights_by_target.get(r.target_id, 0) + r.weight
    total = sum(weights_by_target.values())
    max_single = max(weights_by_target.values())
    return max_single / total if total > 0 else 0.0


RULES = [
    # === REGLAS CLÁSICAS DE BOT ===
    {
        "name": "cuenta_nueva_muchos_seguidos",
        "description": "Cuenta < 90 días con > 500 seguidos",
        "weight": 0.25,
        "check": lambda f: f["account_age_days"] < 90 and f["following_count"] > 500,
    },
    {
        "name": "sin_avatar_sin_bio",
        "description": "Sin avatar y sin bio",
        "weight": 0.20,
        "check": lambda f: not f["has_avatar"] and not f["has_bio"],
    },
    {
        "name": "actividad_extrema",
        "description": "> 50 tweets/día promedio",
        "weight": 0.25,
        "check": lambda f: f["tweets_per_day"] > 50,
    },
    {
        "name": "ratio_seguidores_bajo",
        "description": "Ratio seguidores/seguidos < 0.01 con muchos seguidos",
        "weight": 0.15,
        "check": lambda f: (
            f["following_count"] > 100 and f["follower_following_ratio"] < 0.01
        ),
    },
    {
        "name": "username_sospechoso",
        "description": "Username parece generado automáticamente",
        "weight": 0.15,
        "check": lambda f: f["username_looks_random"] or f["has_numeric_suffix"],
    },
    {
        "name": "cuenta_muy_nueva",
        "description": "Cuenta creada hace menos de 60 días",
        "weight": 0.15,
        "check": lambda f: 0 < f["account_age_days"] < 60,
    },

    # === REGLAS DE CAMPAÑA COORDINADA ===
    {
        "name": "nombre_campana",
        "description": "Username o bio contiene nombre del candidato / keywords de campaña",
        "weight": 0.30,
        "check": lambda f: _is_campaign_account_name(
            f.get("_username", ""), f.get("_bio", "")
        ),
    },
    {
        "name": "cuenta_reciente_campana",
        "description": "Cuenta creada < 2 años con actividad de campaña",
        "weight": 0.20,
        "check": lambda f: (
            f["account_age_days"] < 730  # < 2 años
            and _is_campaign_account_name(f.get("_username", ""), f.get("_bio", ""))
        ),
    },
    {
        "name": "pocos_seguidos_mucha_actividad",
        "description": "Sigue a < 20 personas pero tiene alta actividad (cuenta operativa)",
        "weight": 0.25,
        "check": lambda f: (
            f["following_count"] < 20 and f["tweet_count"] > 100
        ),
    },
    {
        "name": "alta_concentracion_interacciones",
        "description": "> 70% de interacciones dirigidas a un solo target",
        "weight": 0.20,
        "check": lambda f: f.get("_retweet_concentration", 0) > 0.70,
    },
    {
        "name": "mayoria_retweets",
        "description": "> 80% de tweets recolectados son retweets",
        "weight": 0.15,
        "check": lambda f: (
            f["total_tweets_collected"] >= 3 and f["retweet_ratio"] > 0.80
        ),
    },

    # === REGLAS TEMPORALES ===
    {
        "name": "rafagas_tweets",
        "description": "Ráfagas de tweets (< 10s entre ellos)",
        "weight": 0.15,
        "check": lambda f: f.get("burst_count", 0) >= 3,
    },
    {
        "name": "posting_uniforme",
        "description": "Entropía horaria muy baja (posting mecánico)",
        "weight": 0.10,
        "check": lambda f: (
            f.get("posting_hour_entropy", 0) > 0
            and f["posting_hour_entropy"] < 1.5
            and f.get("total_tweets_collected", 0) >= 5
        ),
    },
]


def score_account(features: dict) -> tuple[float, list[dict]]:
    """Calcular bot score heurístico para una cuenta.

    Retorna (score, triggered_rules) donde score está entre 0.0 y 1.0.
    """
    triggered = []
    total_score = 0.0

    for rule in RULES:
        try:
            if rule["check"](features):
                triggered.append({
                    "name": rule["name"],
                    "description": rule["description"],
                    "weight": rule["weight"],
                })
                total_score += rule["weight"]
        except (KeyError, TypeError, ZeroDivisionError):
            continue

    # Normalizar a [0, 1]
    max_possible = sum(r["weight"] for r in RULES)
    normalized_score = min(total_score / max_possible, 1.0) if max_possible > 0 else 0.0

    return normalized_score, triggered


def classify(score: float) -> str:
    """Clasificar cuenta basado en score."""
    if score >= 0.40:
        return "bot"
    elif score >= 0.20:
        return "suspicious"
    return "human"


def run_heuristic_detection(graph_metrics: dict[str, dict] | None = None) -> dict:
    """Ejecutar detección heurística en todas las cuentas."""
    engine = get_engine()
    results = {"bot": 0, "suspicious": 0, "human": 0, "total": 0}

    with Session(engine) as session:
        accounts = session.exec(select(Account)).all()

        for account in accounts:
            features = extract_all_features(account, graph_metrics)
            # Inject extra context for campaign-specific rules
            features["_username"] = account.username
            features["_bio"] = account.bio
            features["_retweet_concentration"] = _get_retweet_concentration(account.id)

            score, triggered = score_account(features)
            label = classify(score)

            account.bot_score = round(score, 4)
            account.bot_label = label
            results[label] += 1
            results["total"] += 1

            if triggered:
                logger.info(
                    f"@{account.username}: score={score:.3f} label={label} "
                    f"rules={[r['name'] for r in triggered]}"
                )

        session.commit()

    logger.info(
        f"Detección completada: {results['total']} cuentas - "
        f"{results['bot']} bots, {results['suspicious']} sospechosas, "
        f"{results['human']} humanas"
    )
    return results
