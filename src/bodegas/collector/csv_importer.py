"""Importador de datos manuales desde CSV."""

import csv
import logging
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from bodegas.db.models import Account, Relationship, Tweet
from bodegas.db.session import get_engine

logger = logging.getLogger(__name__)

VALID_RELATIONSHIP_TYPES = {"follows", "retweet", "mention", "reply", "quote"}


def _resolve_username_to_id(session: Session, username: str) -> str | None:
    """Buscar ID de cuenta por username. Retorna None si no existe."""
    username = username.strip().lstrip("@").lower()
    stmt = select(Account).where(Account.username == username)
    account = session.exec(stmt).first()
    return account.id if account else None


def _ensure_account_exists(session: Session, username: str) -> str:
    """Crear cuenta placeholder si no existe. Retorna el ID."""
    username = username.strip().lstrip("@").lower()
    stmt = select(Account).where(Account.username == username)
    account = session.exec(stmt).first()
    if account:
        return account.id

    # Crear placeholder - se enriquecerá cuando se haga lookup via API
    account_id = f"placeholder_{uuid4().hex[:12]}"
    placeholder = Account(
        id=account_id,
        username=username,
        display_name=username,
        collected_at=datetime.utcnow(),
    )
    session.add(placeholder)
    session.flush()
    return account_id


def import_relationships(filepath: str | Path) -> dict:
    """Importar relaciones desde CSV.

    Formato esperado: source_username,target_username,type
    Types válidos: follows, retweet, mention, reply, quote
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    engine = get_engine()
    stats = {"imported": 0, "skipped": 0, "errors": []}

    with Session(engine) as session:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            required = {"source_username", "target_username", "type"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    f"CSV debe tener columnas: {required}. "
                    f"Encontradas: {reader.fieldnames}"
                )

            for i, row in enumerate(reader, start=2):  # start=2 porque fila 1 es header
                try:
                    rel_type = row["type"].strip().lower()
                    if rel_type not in VALID_RELATIONSHIP_TYPES:
                        stats["errors"].append(
                            f"Fila {i}: tipo '{rel_type}' no válido"
                        )
                        stats["skipped"] += 1
                        continue

                    source_id = _ensure_account_exists(session, row["source_username"])
                    target_id = _ensure_account_exists(session, row["target_username"])

                    # Check if relationship exists
                    existing = session.get(
                        Relationship, (source_id, target_id, rel_type)
                    )
                    if existing:
                        existing.weight += 1
                        existing.last_seen_at = datetime.utcnow()
                    else:
                        rel = Relationship(
                            source_id=source_id,
                            target_id=target_id,
                            relationship_type=rel_type,
                        )
                        session.add(rel)

                    stats["imported"] += 1
                except Exception as e:
                    stats["errors"].append(f"Fila {i}: {e}")
                    stats["skipped"] += 1

        session.commit()

    return stats


def import_tweets(filepath: str | Path) -> dict:
    """Importar tweets desde CSV.

    Formato esperado: username,text,date,retweets,likes,is_retweet,is_reply
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

    engine = get_engine()
    stats = {"imported": 0, "skipped": 0, "errors": []}

    with Session(engine) as session:
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            required = {"username", "text", "date"}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError(
                    f"CSV debe tener columnas: {required}. "
                    f"Encontradas: {reader.fieldnames}"
                )

            for i, row in enumerate(reader, start=2):
                try:
                    author_id = _ensure_account_exists(session, row["username"])

                    # Parse date
                    created_at = None
                    if row.get("date"):
                        try:
                            created_at = datetime.fromisoformat(row["date"])
                        except ValueError:
                            created_at = datetime.strptime(
                                row["date"], "%Y-%m-%d %H:%M:%S"
                            )

                    tweet_id = f"manual_{uuid4().hex[:16]}"
                    is_rt = row.get("is_retweet", "false").lower() in ("true", "1", "yes")
                    is_reply = row.get("is_reply", "false").lower() in ("true", "1", "yes")

                    tweet = Tweet(
                        id=tweet_id,
                        author_id=author_id,
                        text=row.get("text", ""),
                        created_at=created_at,
                        retweet_count=int(row.get("retweets", 0)),
                        like_count=int(row.get("likes", 0)),
                        is_retweet=is_rt,
                        is_reply=is_reply,
                    )
                    session.add(tweet)
                    stats["imported"] += 1

                except Exception as e:
                    stats["errors"].append(f"Fila {i}: {e}")
                    stats["skipped"] += 1

        session.commit()

    return stats


def import_all(import_dir: str | Path = "data/imports") -> dict:
    """Importar todos los CSVs de un directorio."""
    import_dir = Path(import_dir)
    if not import_dir.exists():
        logger.warning(f"Directorio no encontrado: {import_dir}")
        return {"relationships": {}, "tweets": {}}

    results = {"relationships": {}, "tweets": {}}

    for csv_file in sorted(import_dir.glob("*.csv")):
        name = csv_file.stem.lower()
        try:
            if "relationship" in name or "relation" in name or "rel" in name:
                logger.info(f"Importando relaciones: {csv_file.name}")
                results["relationships"][csv_file.name] = import_relationships(csv_file)
            elif "tweet" in name:
                logger.info(f"Importando tweets: {csv_file.name}")
                results["tweets"][csv_file.name] = import_tweets(csv_file)
            else:
                logger.info(
                    f"Archivo '{csv_file.name}' no reconocido. "
                    "Usa 'relationship' o 'tweet' en el nombre."
                )
        except Exception as e:
            logger.error(f"Error importando {csv_file.name}: {e}")

    return results
