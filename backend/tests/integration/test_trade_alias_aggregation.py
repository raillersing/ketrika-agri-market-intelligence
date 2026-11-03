"""Unambiguous source-aware trade aliases never multiply measured quantities."""

import importlib.util
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.db import get_engine
from ketrika.core.models.db import Product, ProductAlias, SourceRecord, TradeFlow
from ketrika.core.qualification import require_synthetic_test_database


@pytest.mark.parametrize(
    "scenario,expected_resolved",
    [
        ("duplicate_same_product", True),
        ("ambiguous_products", False),
        ("low_confidence", False),
        ("human_reviewed", True),
        ("foreign_source", False),
        ("generic", True),
    ],
)
def test_trade_alias_does_not_duplicate_or_guess_product(scenario, expected_resolved, monkeypatch):
    engine = get_engine()
    require_synthetic_test_database(engine.url.host, engine.url.database)
    path = Path(__file__).parents[2] / "alembic/versions/0026_trade_alias_resolution.py"
    spec = importlib.util.spec_from_file_location("trade_alias_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        monkeypatch.setattr(
            migration, "op", SimpleNamespace(execute=lambda sql: connection.execute(text(sql)))
        )
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            try:
                tag = "synthetic_trade_alias_" + uuid4().hex
                source = tag
                session.execute(
                    text(
                        "INSERT INTO meta.source(source_id,spec,status) VALUES (:s,'{}','active')"
                    ),
                    {"s": source},
                )
                other_source = tag + "_other"
                session.execute(
                    text(
                        "INSERT INTO meta.source(source_id,spec,status) VALUES (:s,'{}','active')"
                    ),
                    {"s": other_source},
                )
                product = Product(
                    product_id=uuid4(),
                    product_code=tag,
                    canonical_name_fr=tag,
                    category="synthetic",
                    base_unit="kg",
                )
                other = Product(
                    product_id=uuid4(),
                    product_code=tag + "_other",
                    canonical_name_fr=tag + "_other",
                    category="synthetic",
                    base_unit="kg",
                )
                reference = SourceRecord(
                    source_record_id=uuid4(),
                    source_id=source,
                    source_url="https://example.invalid/synthetic-only",
                    fetched_at=datetime.now(UTC),
                    object_key="synthetic/" + tag,
                    content_sha256="a" * 64,
                    mime_type="application/json",
                    parser_version="synthetic-only",
                )
                session.add_all([product, other, reference])
                session.flush()
                session.add(
                    ProductAlias(
                        alias_id=uuid4(),
                        alias_norm=tag,
                        alias_display=tag,
                        lang="fr",
                        product_id=product.product_id,
                        source_id=other_source
                        if scenario == "foreign_source"
                        else source
                        if scenario in ("duplicate_same_product", "ambiguous_products")
                        else None,
                        confidence=0.2 if scenario in ("low_confidence", "human_reviewed") else 1.0,
                        origin="synthetic SQL regression",
                        human_reviewed=scenario == "human_reviewed",
                    )
                )
                if scenario in ("duplicate_same_product", "ambiguous_products"):
                    session.add(
                        ProductAlias(
                            alias_id=uuid4(),
                            alias_norm=tag,
                            alias_display=tag,
                            lang="fr",
                            product_id=other.product_id
                            if scenario == "ambiguous_products"
                            else product.product_id,
                            source_id=None,
                            confidence=1.0,
                            origin="synthetic SQL regression",
                            human_reviewed=False,
                        )
                    )
                flow = TradeFlow(
                    observation_id=uuid4(),
                    source_record_id=reference.source_record_id,
                    natural_key=tag,
                    product_raw=tag,
                    product_id=None,
                    flow="import",
                    period_start=date(2099, 10, 1),
                    period_end=date(2099, 10, 31),
                    weight_raw="1000",
                    extraction_method="deterministic",
                    confidence=0.5,
                    weight_kg=1000,
                    value_mga=10,
                    evidence={"synthetic": True},
                )
                session.add(flow)
                session.flush()
                before = connection.scalar(
                    text("SELECT to_jsonb(t)::text FROM obs.trade_flow t WHERE observation_id=:id"),
                    {"id": flow.observation_id},
                )
                migration.upgrade()
                connection.execute(text("REFRESH MATERIALIZED VIEW gold.trade_monthly"))
                row = connection.execute(
                    text(
                        "SELECT product_id,weight_tonnes,n_records FROM gold.trade_monthly WHERE month='2099-10-01' AND flow='import' AND (product_id=:id OR product_id IS NULL)"
                    ),
                    {"id": product.product_id},
                ).all()
                selected = (
                    [r for r in row if r[0] == product.product_id]
                    if expected_resolved
                    else [r for r in row if r[0] is None]
                )
                assert len(selected) == 1
                assert selected[0][1] == 1 and selected[0][2] == 1
                assert (selected[0][0] is not None) == expected_resolved
                assert (
                    connection.scalar(
                        text(
                            "SELECT to_jsonb(t)::text FROM obs.trade_flow t WHERE observation_id=:id"
                        ),
                        {"id": flow.observation_id},
                    )
                    == before
                )
            finally:
                session.close()
                transaction.rollback()
