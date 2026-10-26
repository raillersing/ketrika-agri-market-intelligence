"""A real private SQLite session ledger for unit tests, not a PostgreSQL qualification."""

from pathlib import Path
from typing import Any, cast

from sqlalchemy import Table, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from ketrika.core.models.db import TokenRevocation


def session_store_engine(path: Path) -> Engine:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def attach(connection: Any, record: Any) -> None:
        connection.execute("ATTACH DATABASE ? AS auth", (str(path),))

    cast(Table, TokenRevocation.__table__).create(engine)
    return engine
