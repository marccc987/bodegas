from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from bodegas.config import settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(settings.db_url, echo=False)
        # Asegurar que las tablas existen siempre
        from bodegas.db.models import Account, Tweet, Relationship, CollectionJob  # noqa
        SQLModel.metadata.create_all(_engine)
    return _engine


def create_tables():
    return get_engine()


def get_session():
    return Session(get_engine())
