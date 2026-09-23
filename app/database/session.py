from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings, get_settings
from app.database.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if raw.startswith("/") and not raw.startswith("///"):
        return Path(raw)
    return Path(raw)


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    settings = settings or get_settings()
    db_path = _sqlite_path(settings.database_url)
    if db_path is not None:
        if not db_path.is_absolute():
            db_path = settings.data_dir.parent / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{db_path.as_posix()}"
    else:
        url = settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, future=True, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def init_db(settings: Settings | None = None) -> None:
    engine = get_engine(settings)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
