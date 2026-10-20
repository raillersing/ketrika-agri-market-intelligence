"""Synthetic SQL/MinIO publication; never official data/model qualification."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event, select, text
from sqlalchemy.exc import SQLAlchemyError

from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session
from ketrika.core.models.db import DqResult, PriceObservation, SourceRecord
from ketrika.core.provenance_bronze import BronzeProofReader
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.gold.provenance_gate import GoldProvenanceRejected
from ketrika.gold.refresh import init_gold_views, refresh_gold_views
from ketrika.pipelines.rebuild import wipe_silver_gold_tables
from tests.e2e_data.synthetic_gold_dataset import seed_synthetic_gold_data


def signature(session):
    return session.execute(
        text(
            "SELECT count(*), md5(coalesce(string_agg(to_jsonb(p)::text, ',' ORDER BY observation_id), '')) FROM gold.price_obs_current p"
        )
    ).one()


class DamagedMemoryReader:
    def __init__(self, original: BronzeProofReader, key: str) -> None:
        self.original, self.key = original, key

    def get(self, object_key: str) -> bytes:
        content = self.original.get(object_key)
        return content + b"simulated damage" if object_key == self.key else content


@pytest.mark.integration
def test_real_publication_rejects_bad_provenance_and_rolls_back_partial_sql(
    request: pytest.FixtureRequest,
) -> None:
    with get_session() as session:
        target = session.get_bind().engine.url
        require_synthetic_test_database(target.host, target.database)
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[2] / "alembic")
        )
        expected_head = ScriptDirectory.from_config(config).get_current_head()
        assert expected_head is not None
        assert (
            session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == expected_head
        )
        store = BronzeStore()
        assert store.bucket == "ketrika-qa-bronze"
        before_references = session.execute(
            text("SELECT count(*) FROM meta.source_record")
        ).scalar_one()
        wipe_silver_gold_tables(session)
        assert (
            session.execute(text("SELECT count(*) FROM meta.source_record")).scalar_one()
            == before_references
        )
        counts = seed_synthetic_gold_data(session)
        assert init_gold_views(session) == {"views_initialized": 14, "views_populated": 0}
        assert (
            session.execute(
                text("SELECT count(*) FROM pg_matviews WHERE schemaname='gold' AND ispopulated")
            ).scalar_one()
            == 0
        )
        with pytest.raises(SQLAlchemyError):
            with session.begin_nested():
                session.execute(text("SELECT count(*) FROM gold.price_obs_current"))
        reader = BronzeProofReader(store)
        published = refresh_gold_views(session, reader=reader)
        expected = sum(
            counts[key] for key in ("price", "stock", "trade", "production", "weather", "cpi")
        )
        assert published["count"] == 13 and published["errors"] == {}
        assert published["withheld_views"] == {
            "economic_dashboard": "macro_publication_not_qualified"
        }
        assert (
            published["source_observations_valid"]
            == published["source_observations_total"]
            == expected
        )
        assert published["source_cell_rate"] == "100"
        assert published["provenance_scope"] == "source_cells_not_authenticity_conversions_or_model"
        baseline = signature(session)
        assert baseline[0] == counts["price"]
        template = session.scalars(
            select(PriceObservation).order_by(PriceObservation.observation_id)
        ).first()
        assert template is not None
        reference = session.get(SourceRecord, template.source_record_id)
        assert reference is not None
        original_hash = hashlib.sha256(reader.get(reference.object_key)).hexdigest()
        assert original_hash == reference.content_sha256
        with pytest.raises(GoldProvenanceRejected) as rejected:
            refresh_gold_views(session, reader=DamagedMemoryReader(reader, reference.object_key))
        failed = rejected.value.receipt
        assert not failed.report.passed and failed.report.valid < failed.report.total == expected
        assert signature(session) == baseline
        assert hashlib.sha256(reader.get(reference.object_key)).hexdigest() == original_hash
        failed_dq_id, positive_dq_id = failed.dq_id, published["source_cell_dq_id"]
        values = {
            column.key: deepcopy(getattr(template, column.key))
            for column in PriceObservation.__table__.columns
            if column.key not in {"observation_id", "natural_key", "ingested_at", "superseded_by"}
        }
        session.add(PriceObservation(observation_id=uuid4(), natural_key=uuid4().hex, **values))
        session.flush()
        connection = session.connection()

        def fail_second_refresh(conn, cursor, statement, parameters, context, executemany):
            if statement == "REFRESH MATERIALIZED VIEW gold.price_monthly;":
                return "SELECT 1/0", parameters
            return statement, parameters

        event.listen(connection, "before_cursor_execute", fail_second_refresh, retval=True)
        try:
            with pytest.raises(ValueError, match="gold_publication_failed"):
                refresh_gold_views(
                    session, views=["price_obs_current", "price_monthly"], reader=reader
                )
        finally:
            event.remove(connection, "before_cursor_execute", fail_second_refresh)
        assert signature(session) == baseline
        derived = refresh_gold_views(session, views=["price_changes"], reader=reader)
        assert derived["views_refreshed"] == [
            "price_obs_current",
            "price_monthly",
            "price_monthly_best",
            "price_changes",
        ]
        fresh_signature = signature(session)
        assert fresh_signature[0] == baseline[0] + 1
        request.node.user_properties.append(
            (
                "ketrika.gold.publication",
                json.dumps(
                    {
                        "dataset": "synthetic",
                        "published_source_cells": expected,
                        "validated_source_cells": expected,
                        "bad_provenance_rejected": True,
                        "partial_refresh_rolled_back": True,
                        "dependency_caches_refreshed": True,
                        "model_qualified": False,
                    }
                ),
            )
        )
    with get_session() as session:
        negative = session.get(DqResult, failed_dq_id)
        assert negative is not None and not negative.passed
        positive = session.get(DqResult, positive_dq_id)
        assert positive is not None and positive.passed
        assert signature(session) == fresh_signature
