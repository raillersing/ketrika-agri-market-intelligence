"""Persisted unreviewed origin claims are downgraded without changing observations."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.core.db import get_engine
from ketrika.core.models.db import Product, ProductAlias, Source
from ketrika.core.qualification import require_synthetic_test_database


@pytest.mark.parametrize(
    "scenario,confidence,expected,invalidated",
    [
        ("global_unreviewed", 1.0, 0.8, True),
        ("already_lower", 0.6, 0.6, False),
        ("reviewed", 1.0, 1.0, False),
        ("source_specific", 1.0, 1.0, False),
        ("different_product", 1.0, 1.0, False),
    ],
)
def test_only_unsupported_global_origin_is_downgraded(
    scenario, confidence, expected, invalidated, monkeypatch
):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    path = Path(__file__).parents[2] / "alembic/versions/0028_ambiguous_milled_rice_alias.py"
    spec = importlib.util.spec_from_file_location("rice_alias_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            monkeypatch.setattr(
                migration, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
            )
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                tag = "synthetic_alias_" + uuid4().hex
                # Keep seeded aliases intact after rollback and avoid a shared key
                # making an unrelated scenario invalidate caches legitimately.
                session.execute(
                    text(
                        "UPDATE ref.product_alias SET alias_norm=:tag WHERE alias_norm='rice_milled'"
                    ),
                    {"tag": tag},
                )
                local = session.scalar(
                    select(Product).where(Product.product_code == "RICE_WHITE_LOCAL")
                )
                assert local is not None
                other = Product(
                    product_id=uuid4(),
                    product_code=tag,
                    canonical_name_fr=tag,
                    category="synthetic",
                    base_unit="kg",
                )
                source = Source(source_id=tag, spec={"synthetic": True}, status="active")
                session.add_all([other, source])
                session.flush()
                alias = ProductAlias(
                    alias_id=uuid4(),
                    alias_norm="rice_milled",
                    alias_display="rice_milled",
                    lang="fr",
                    product_id=other.product_id
                    if scenario == "different_product"
                    else local.product_id,
                    source_id=tag if scenario == "source_specific" else None,
                    confidence=confidence,
                    origin="synthetic migration fixture",
                    human_reviewed=scenario == "reviewed",
                )
                session.add(alias)
                session.flush()
                before = dict(
                    session.execute(
                        text(
                            "SELECT to_jsonb(a) AS row FROM ref.product_alias a WHERE alias_id=:id"
                        ),
                        {"id": alias.alias_id},
                    ).scalar_one()
                )
                for view in ("trade_monthly", "import_dependency"):
                    session.execute(text(f"REFRESH MATERIALIZED VIEW gold.{view}"))
                migration.upgrade()
                after = dict(
                    session.execute(
                        text(
                            "SELECT to_jsonb(a) AS row FROM ref.product_alias a WHERE alias_id=:id"
                        ),
                        {"id": alias.alias_id},
                    ).scalar_one()
                )
                assert after == dict(before, confidence=expected)
                populated = session.execute(
                    text(
                        "SELECT matviewname,ispopulated FROM pg_matviews WHERE schemaname='gold' AND matviewname IN ('trade_monthly','import_dependency') ORDER BY 1"
                    )
                ).all()
                assert len(populated) == 2
                assert all(value is not invalidated for _, value in populated)
                migration.upgrade()
                repeated = session.execute(
                    text("SELECT to_jsonb(a) FROM ref.product_alias a WHERE alias_id=:id"),
                    {"id": alias.alias_id},
                ).scalar_one()
                assert repeated == after
        finally:
            transaction.rollback()


def test_downgrade_cannot_restore_an_unsupported_origin_claim():
    path = Path(__file__).parents[2] / "alembic/versions/0028_ambiguous_milled_rice_alias.py"
    spec = importlib.util.spec_from_file_location("rice_alias_downgrade", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with pytest.raises(RuntimeError, match="unverified rice-origin"):
        migration.downgrade()
