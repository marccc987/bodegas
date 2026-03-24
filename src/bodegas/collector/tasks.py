"""Tareas de orquestación para recolección de datos."""

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from bodegas.collector.api_client import lookup_users_by_usernames, save_accounts
from bodegas.collector.csv_importer import import_all
from bodegas.db.models import Account, CollectionJob
from bodegas.db.session import create_tables, get_engine

logger = logging.getLogger(__name__)


def _parse_seeds(seeds_path: str) -> list[str]:
    """Parsear seeds.json y retornar lista de usernames deduplicados."""
    path = Path(seeds_path)
    if not path.exists():
        raise FileNotFoundError(f"Seeds no encontrado: {path}")

    with open(path) as f:
        seeds = json.load(f)

    raw_accounts = seeds.get("accounts", [])
    usernames = []
    for item in raw_accounts:
        if isinstance(item, str):
            usernames.append(item)
        elif isinstance(item, dict) and "username" in item:
            usernames.append(item["username"])
    return list(dict.fromkeys(usernames))


def collect_profiles(seeds_path: str = "data/seeds.json") -> dict:
    """Recolectar perfiles desde seeds.json via X API."""
    usernames = _parse_seeds(seeds_path)
    if not usernames:
        logger.warning("No hay cuentas en seeds.json")
        return {"total": 0, "saved": 0}

    engine = get_engine()
    with Session(engine) as session:
        job = CollectionJob(
            job_type="profile_lookup",
            target=f"{len(usernames)} cuentas semilla",
            status="running",
            started_at=datetime.now(),
        )
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        accounts = lookup_users_by_usernames(usernames, is_seed=True)
        saved = save_accounts(accounts)

        with Session(engine) as session:
            job = session.get(CollectionJob, job_id)
            job.status = "completed"
            job.items_collected = saved
            job.completed_at = datetime.now()
            session.commit()

        return {"total": len(usernames), "found": len(accounts), "saved": saved}

    except Exception as e:
        with Session(engine) as session:
            job = session.get(CollectionJob, job_id)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now()
            session.commit()
        raise


def seed_accounts(seeds_path: str = "data/seeds.json") -> dict:
    """Crear cuentas semilla en la DB sin usar la API.

    Útil cuando la API no está disponible o no tiene créditos.
    """
    usernames = _parse_seeds(seeds_path)
    if not usernames:
        return {"total": 0, "saved": 0}

    engine = get_engine()
    saved = 0
    with Session(engine) as session:
        for username in usernames:
            existing = session.exec(
                select(Account).where(Account.username == username)
            ).first()
            if existing:
                existing.is_seed = True
            else:
                session.add(Account(
                    id=f"seed_{username.lower()}",
                    username=username,
                    display_name=username,
                    profile_url=f"https://x.com/{username}",
                    is_seed=True,
                    collected_at=datetime.now(),
                ))
            saved += 1
        session.commit()

    logger.info(f"Creadas {saved} cuentas semilla desde seeds.json")
    return {"total": len(usernames), "saved": saved}


def resolve_placeholders() -> int:
    """Buscar cuentas placeholder (de CSV import) y enriquecerlas via API."""
    engine = get_engine()
    with Session(engine) as session:
        stmt = select(Account).where(Account.id.startswith("placeholder_"))
        placeholders = session.exec(stmt).all()

    if not placeholders:
        logger.info("No hay cuentas placeholder por resolver")
        return 0

    usernames = [a.username for a in placeholders]
    logger.info(f"Resolviendo {len(usernames)} cuentas placeholder via API")

    enriched = lookup_users_by_usernames(usernames)

    # Map username -> enriched account
    enriched_map = {a.username.lower(): a for a in enriched}

    with Session(engine) as session:
        resolved = 0
        for placeholder in placeholders:
            real = enriched_map.get(placeholder.username.lower())
            if real:
                # Update placeholder with real data
                stmt = select(Account).where(Account.id == placeholder.id)
                db_account = session.exec(stmt).first()
                if db_account:
                    for field in [
                        "display_name", "bio", "location", "followers_count",
                        "following_count", "tweet_count", "created_at",
                        "is_verified", "has_avatar", "has_bio", "avatar_url",
                        "profile_url",
                    ]:
                        setattr(db_account, field, getattr(real, field))
                    # Replace placeholder ID with real ID
                    db_account.id = real.id
                    db_account.collected_at = datetime.utcnow()
                    resolved += 1
        session.commit()

    logger.info(f"Resueltas {resolved} de {len(usernames)} cuentas")
    return resolved


def import_manual_data(import_dir: str = "data/imports") -> dict:
    """Importar datos manuales desde CSVs."""
    engine = get_engine()
    with Session(engine) as session:
        job = CollectionJob(
            job_type="csv_import",
            target=import_dir,
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        results = import_all(import_dir)

        total = sum(
            r.get("imported", 0)
            for group in results.values()
            for r in group.values()
        )

        with Session(engine) as session:
            job = session.get(CollectionJob, job_id)
            job.status = "completed"
            job.items_collected = total
            job.completed_at = datetime.utcnow()
            session.commit()

        return results

    except Exception as e:
        with Session(engine) as session:
            job = session.get(CollectionJob, job_id)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            session.commit()
        raise
