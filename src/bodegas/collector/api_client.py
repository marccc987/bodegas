"""Wrapper para X API v2 Free tier usando tweepy."""

import logging
from datetime import datetime

import tweepy
from sqlmodel import Session

from bodegas.config import settings
from bodegas.db.models import Account, CollectionJob
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)

DEFAULT_USER_FIELDS = [
    "created_at",
    "description",
    "location",
    "profile_image_url",
    "public_metrics",
    "verified",
]


def get_client() -> tweepy.Client:
    if not settings.x_bearer_token:
        raise ValueError("X_BEARER_TOKEN no configurado. Revisa tu archivo .env")
    return tweepy.Client(bearer_token=settings.x_bearer_token, wait_on_rate_limit=True)


def _user_to_account(user: tweepy.User, is_seed: bool = False) -> Account:
    metrics = user.public_metrics or {}
    has_default_avatar = user.profile_image_url and "default_profile" in user.profile_image_url
    return Account(
        id=str(user.id),
        username=user.username,
        display_name=user.name or "",
        bio=user.description or "",
        location=user.location or "",
        followers_count=metrics.get("followers_count", 0),
        following_count=metrics.get("following_count", 0),
        tweet_count=metrics.get("tweet_count", 0),
        created_at=user.created_at,
        is_verified=getattr(user, "verified", False) or False,
        has_avatar=not has_default_avatar,
        has_bio=bool(user.description),
        profile_url=f"https://x.com/{user.username}",
        avatar_url=user.profile_image_url or "",
        collected_at=datetime.utcnow(),
        is_seed=is_seed,
    )


def lookup_users_by_usernames(
    usernames: list[str], is_seed: bool = False
) -> list[Account]:
    """Buscar perfiles de usuario por username. Máx 100 por request."""
    client = get_client()
    accounts = []

    # Procesar en lotes de 100 (límite de la API)
    for i in range(0, len(usernames), 100):
        batch = usernames[i : i + 100]
        logger.info(f"Buscando lote {i // 100 + 1}: {len(batch)} usuarios")

        try:
            response = client.get_users(
                usernames=batch, user_fields=DEFAULT_USER_FIELDS
            )
            if response.data:
                for user in response.data:
                    accounts.append(_user_to_account(user, is_seed=is_seed))
            if response.errors:
                for error in response.errors:
                    logger.warning(f"Error para usuario: {error}")
        except tweepy.TooManyRequests:
            logger.error("Rate limit alcanzado. Espera antes de reintentar.")
            raise
        except tweepy.TweepyException as e:
            logger.error(f"Error de API: {e}")
            raise

    return accounts


def lookup_users_by_ids(user_ids: list[str], is_seed: bool = False) -> list[Account]:
    """Buscar perfiles de usuario por ID. Máx 100 por request."""
    client = get_client()
    accounts = []

    for i in range(0, len(user_ids), 100):
        batch = user_ids[i : i + 100]
        logger.info(f"Buscando lote {i // 100 + 1}: {len(batch)} usuarios por ID")

        try:
            response = client.get_users(
                ids=batch, user_fields=DEFAULT_USER_FIELDS
            )
            if response.data:
                for user in response.data:
                    accounts.append(_user_to_account(user, is_seed=is_seed))
            if response.errors:
                for error in response.errors:
                    logger.warning(f"Error para ID: {error}")
        except tweepy.TweepyException as e:
            logger.error(f"Error de API: {e}")
            raise

    return accounts


def save_accounts(accounts: list[Account]) -> int:
    """Guardar cuentas en la base de datos. Retorna cantidad guardada."""
    engine = get_engine()
    saved = 0
    with Session(engine) as session:
        for account in accounts:
            existing = session.get(Account, account.id)
            if existing:
                # Actualizar campos
                for field in [
                    "display_name", "bio", "location", "followers_count",
                    "following_count", "tweet_count", "is_verified",
                    "has_avatar", "has_bio", "avatar_url", "collected_at",
                ]:
                    setattr(existing, field, getattr(account, field))
                if account.is_seed:
                    existing.is_seed = True
            else:
                session.add(account)
            saved += 1
        session.commit()
    return saved
