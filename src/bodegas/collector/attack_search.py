"""Búsqueda de ataques coordinados via X API v2 (pay-per-use).

Estrategia: buscar replies a los blancos (cuentas críticas) y detectar
cuentas que aparecen atacando a múltiples blancos = comportamiento coordinado.

Costo estimado: ~$17.50 para 5 blancos × 500 tweets + perfiles.
"""

import logging
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

import tweepy
from sqlmodel import Session, select

from bodegas.config import settings
from bodegas.db.models import Account, Tweet, Relationship
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)

TWEET_FIELDS = [
    "created_at",
    "author_id",
    "in_reply_to_user_id",
    "public_metrics",
    "lang",
    "referenced_tweets",
]

USER_FIELDS = [
    "created_at",
    "description",
    "location",
    "profile_image_url",
    "public_metrics",
    "verified",
]

# Tracking de costos
cost_tracker = {"posts_read": 0, "users_read": 0}


def estimated_cost() -> float:
    return cost_tracker["posts_read"] * 0.005 + cost_tracker["users_read"] * 0.01


def get_client() -> tweepy.Client:
    if not settings.x_bearer_token:
        raise ValueError("X_BEARER_TOKEN no configurado")
    return tweepy.Client(bearer_token=settings.x_bearer_token, wait_on_rate_limit=True)


def search_replies_to_target(
    target_username: str,
    max_results: int = 500,
    keywords: Optional[list[str]] = None,
) -> list[dict]:
    """Buscar replies a un blanco específico.

    Retorna lista de dicts con info del tweet y autor.
    """
    client = get_client()

    # Construir query
    query = f"to:{target_username}"
    if keywords:
        kw_part = " OR ".join(keywords)
        query = f"to:{target_username} ({kw_part})"

    # Limitar a 512 chars (límite de API)
    if len(query) > 512:
        query = f"to:{target_username}"

    logger.info(f"🔍 Buscando: {query}")

    tweets_data = []
    fetched = 0
    next_token = None

    while fetched < max_results:
        batch_size = min(100, max_results - fetched)  # max 100 per request
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=max(10, batch_size),
                tweet_fields=TWEET_FIELDS,
                expansions=["author_id"],
                user_fields=USER_FIELDS,
                next_token=next_token,
            )

            cost_tracker["posts_read"] += len(response.data) if response.data else 0

            if not response.data:
                logger.info(f"  Sin más resultados para {target_username}")
                break

            # Map author_id -> user info from includes
            users_map = {}
            if response.includes and "users" in response.includes:
                for u in response.includes["users"]:
                    users_map[u.id] = u

            for tweet in response.data:
                author = users_map.get(tweet.author_id)
                tweets_data.append({
                    "tweet_id": str(tweet.id),
                    "text": tweet.text or "",
                    "author_id": str(tweet.author_id),
                    "author_username": author.username if author else "",
                    "author_name": author.name if author else "",
                    "author_avatar": (author.profile_image_url or "").replace("_normal", "_400x400") if author else "",
                    "author_bio": author.description if author else "",
                    "author_location": author.location if author else "",
                    "author_created_at": author.created_at if author else None,
                    "author_followers": (author.public_metrics or {}).get("followers_count", 0) if author else 0,
                    "author_following": (author.public_metrics or {}).get("following_count", 0) if author else 0,
                    "author_tweet_count": (author.public_metrics or {}).get("tweet_count", 0) if author else 0,
                    "tweet_created_at": tweet.created_at,
                    "in_reply_to": target_username,
                    "lang": getattr(tweet, "lang", ""),
                    "like_count": (tweet.public_metrics or {}).get("like_count", 0),
                    "reply_count": (tweet.public_metrics or {}).get("reply_count", 0),
                    "retweet_count": (tweet.public_metrics or {}).get("retweet_count", 0),
                })

            fetched += len(response.data)
            logger.info(f"  {target_username}: {fetched}/{max_results} tweets (costo: ${estimated_cost():.2f})")

            # Pagination
            if hasattr(response, "meta") and response.meta and "next_token" in response.meta:
                next_token = response.meta["next_token"]
            else:
                break

        except tweepy.TooManyRequests:
            logger.warning("⏳ Rate limit, esperando 15s...")
            time.sleep(15)
        except tweepy.TweepyException as e:
            logger.error(f"❌ Error API: {e}")
            break

    logger.info(f"✅ {target_username}: {len(tweets_data)} tweets recolectados")
    return tweets_data


def save_tweets_and_accounts(tweets_data: list[dict], target_username: str) -> dict:
    """Guardar tweets, cuentas y relaciones en la DB."""
    engine = get_engine()
    stats = {"accounts_new": 0, "accounts_updated": 0, "tweets_new": 0, "relationships": 0}

    with Session(engine) as session:
        for td in tweets_data:
            # Upsert account
            acc = session.get(Account, td["author_id"])
            if acc:
                # Update with richer API data
                acc.display_name = td["author_name"] or acc.display_name
                acc.bio = td["author_bio"] or acc.bio
                acc.location = td["author_location"] or acc.location
                acc.followers_count = td["author_followers"] or acc.followers_count
                acc.following_count = td["author_following"] or acc.following_count
                acc.tweet_count = td["author_tweet_count"] or acc.tweet_count
                acc.avatar_url = td["author_avatar"] or acc.avatar_url
                acc.has_avatar = bool(td["author_avatar"]) and "default_profile" not in (td["author_avatar"] or "")
                acc.has_bio = bool(td["author_bio"])
                if td["author_created_at"]:
                    acc.created_at = td["author_created_at"]
                stats["accounts_updated"] += 1
            else:
                has_default = "default_profile" in (td["author_avatar"] or "")
                acc = Account(
                    id=td["author_id"],
                    username=td["author_username"],
                    display_name=td["author_name"],
                    bio=td["author_bio"] or "",
                    location=td["author_location"] or "",
                    followers_count=td["author_followers"],
                    following_count=td["author_following"],
                    tweet_count=td["author_tweet_count"],
                    created_at=td["author_created_at"],
                    has_avatar=not has_default and bool(td["author_avatar"]),
                    has_bio=bool(td["author_bio"]),
                    profile_url=f"https://x.com/{td['author_username']}",
                    avatar_url=td["author_avatar"] or "",
                    collected_at=datetime.utcnow(),
                )
                session.add(acc)
                stats["accounts_new"] += 1

            # Save tweet
            existing_tweet = session.get(Tweet, td["tweet_id"])
            if not existing_tweet:
                tweet = Tweet(
                    id=td["tweet_id"],
                    author_id=td["author_id"],
                    text=td["text"],
                    created_at=td["tweet_created_at"],
                    language=td.get("lang", ""),
                    like_count=td["like_count"],
                    reply_count=td["reply_count"],
                    retweet_count=td["retweet_count"],
                    is_reply=True,
                    in_reply_to_user_id=None,  # Will set via relationship
                    collected_at=datetime.utcnow(),
                )
                session.add(tweet)
                stats["tweets_new"] += 1

            # Create reply relationship
            # Find or create target account
            target_acc = session.exec(
                select(Account).where(Account.username == target_username)
            ).first()
            if target_acc:
                rel_key = (td["author_id"], target_acc.id, "reply")
                existing_rel = session.get(Relationship, rel_key)
                if existing_rel:
                    existing_rel.weight += 1
                    existing_rel.last_seen_at = datetime.utcnow()
                else:
                    session.add(Relationship(
                        source_id=td["author_id"],
                        target_id=target_acc.id,
                        relationship_type="reply",
                        weight=1,
                    ))
                    stats["relationships"] += 1

        session.commit()

    return stats


def run_attack_search(
    targets: list[str],
    max_per_target: int = 500,
    budget: float = 20.0,
) -> dict:
    """Ejecutar búsqueda completa de ataques coordinados.

    Args:
        targets: Lista de usernames blanco
        max_per_target: Máximo de tweets a buscar por blanco
        budget: Presupuesto en USD
    """
    logger.info(f"🎯 Iniciando búsqueda de ataques a {len(targets)} blancos")
    logger.info(f"💰 Presupuesto: ${budget:.2f}")

    all_tweets = {}  # target -> tweets_data
    attackers_by_target = defaultdict(set)  # target -> set of author_ids

    for target in targets:
        if estimated_cost() >= budget * 0.85:
            logger.warning(f"⚠️ Cerca del presupuesto (${estimated_cost():.2f}/${budget:.2f}), deteniendo")
            break

        tweets = search_replies_to_target(target, max_results=max_per_target)
        all_tweets[target] = tweets

        # Save to DB
        stats = save_tweets_and_accounts(tweets, target)
        logger.info(f"  💾 {target}: {stats}")

        for t in tweets:
            attackers_by_target[target].add(t["author_id"])

    # ANÁLISIS: encontrar cuentas que atacan múltiples blancos
    all_attacker_ids = set()
    for ids in attackers_by_target.values():
        all_attacker_ids.update(ids)

    multi_target = {}  # author_id -> list of targets attacked
    for author_id in all_attacker_ids:
        targets_hit = [t for t, ids in attackers_by_target.items() if author_id in ids]
        if len(targets_hit) > 1:
            multi_target[author_id] = targets_hit

    # Resumen
    logger.info("\n" + "="*60)
    logger.info("📊 RESUMEN DE BÚSQUEDA")
    logger.info("="*60)
    logger.info(f"Blancos analizados: {len(all_tweets)}")
    for target, tweets in all_tweets.items():
        unique = len(set(t["author_id"] for t in tweets))
        logger.info(f"  @{target}: {len(tweets)} tweets, {unique} cuentas únicas")
    logger.info(f"Total cuentas únicas: {len(all_attacker_ids)}")
    logger.info(f"Cuentas multi-blanco (COORDINADAS): {len(multi_target)}")

    if multi_target:
        logger.info("\n🚨 CUENTAS QUE ATACAN MÚLTIPLES BLANCOS:")
        for author_id, targets_hit in sorted(multi_target.items(), key=lambda x: -len(x[1])):
            # Get username from tweets
            username = "?"
            for tweets in all_tweets.values():
                for t in tweets:
                    if t["author_id"] == author_id:
                        username = t["author_username"]
                        break
                if username != "?":
                    break
            logger.info(f"  @{username} ({author_id}) → atacó a: {', '.join('@'+t for t in targets_hit)}")

    logger.info(f"\n💰 Costo total: ${estimated_cost():.2f}")

    return {
        "targets_searched": list(all_tweets.keys()),
        "total_tweets": sum(len(t) for t in all_tweets.values()),
        "total_unique_attackers": len(all_attacker_ids),
        "multi_target_count": len(multi_target),
        "multi_target": multi_target,
        "cost": estimated_cost(),
    }
