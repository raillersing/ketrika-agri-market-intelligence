"""Database connection management."""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ketrika.core.settings import get_settings

_engine: Engine | None = None


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


def check_db_connection() -> bool:
    """Check connectivity to PostgreSQL."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
