"""Database engine, sessions, transactional helpers and provenance validation."""

import uuid
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ketrika.core.models.db import SourceRecord
from ketrika.core.settings import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return singleton database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Return configured SQLAlchemy session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def transaction() -> Generator[Session, None, None]:
    """Explicit alias for transactional database session."""
    with get_session() as session:
        yield session


def check_db_connection() -> bool:
    """Check connectivity to PostgreSQL."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def verify_observation_provenance(session: Session, source_record_id: uuid.UUID) -> bool:
    """Verify that an observation references a valid Bronze source record (SPECS §4.1)."""
    stmt = select(SourceRecord.source_record_id).where(
        SourceRecord.source_record_id == source_record_id
    )
    result = session.execute(stmt).scalar_one_or_none()
    return result is not None
