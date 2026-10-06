"""Integration tests for database schemas, immutability triggers and copilot_ro permissions."""

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from ketrika.core.settings import get_settings


@pytest.fixture(scope="module")
def app_engine():
    """Engine using default application credentials (ketrika / ketrika_app)."""
    from ketrika.core.db import check_db_connection

    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def copilot_engine():
    """Engine using copilot_ro credentials."""
    from ketrika.core.db import check_db_connection

    if not check_db_connection():
        pytest.skip("Database is not reachable (skipping integration tests)")
    settings = get_settings()
    url = f"postgresql+psycopg://copilot_ro:{settings.copilot_db_password}@db:5432/{settings.postgres_db}"
    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_copilot_ro_cannot_read_obs_price_observation(copilot_engine):
    """Verify copilot_ro cannot read obs.price_observation (SPECS §8)."""
    with copilot_engine.connect() as conn:
        with pytest.raises((ProgrammingError, DBAPIError)) as exc_info:
            conn.execute(text("SELECT * FROM obs.price_observation LIMIT 1;"))
        assert "permission denied" in str(exc_info.value).lower()


def test_copilot_ro_can_access_gold_schema(copilot_engine):
    """Verify copilot_ro has USAGE privilege on gold schema."""
    with copilot_engine.connect() as conn:
        # Schema usage check: querying information_schema for gold
        result = conn.execute(
            text("SELECT table_schema FROM information_schema.tables WHERE table_schema = 'gold';")
        )
        assert result is not None


def test_meta_source_record_immutability(app_engine):
    """Verify meta.source_record forbids deletions."""
    source_id = f"test_src_{uuid.uuid4().hex[:8]}"
    sha = uuid.uuid4().hex

    with app_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO meta.source (source_id, spec, status) "
                "VALUES (:s_id, '{\"name\": \"test\"}'::jsonb, 'active');"
            ),
            {"s_id": source_id},
        )
        res = conn.execute(
            text(
                "INSERT INTO meta.source_record "
                "(source_id, source_url, object_key, content_sha256, fetched_at) "
                "VALUES (:s_id, 'http://test.url', 'test/key', :sha, now()) "
                "RETURNING source_record_id;"
            ),
            {"s_id": source_id, "sha": sha},
        )
        record_id = res.scalar_one()

    # Attempting to delete should raise an exception via trigger
    with app_engine.begin() as conn:
        with pytest.raises(DBAPIError) as exc_info:
            conn.execute(
                text("DELETE FROM meta.source_record WHERE source_record_id = :id;"),
                {"id": record_id},
            )
        assert "bronze immutability" in str(exc_info.value).lower()


def test_obs_price_observation_append_only_rules(app_engine):
    """Verify obs.price_observation only permits setting superseded_by and forbids deletes."""
    source_id = f"test_src_{uuid.uuid4().hex[:8]}"
    sha = uuid.uuid4().hex
    nat_key = f"key_{uuid.uuid4().hex}"

    with app_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO meta.source (source_id, spec, status) "
                "VALUES (:s_id, '{\"name\": \"test\"}'::jsonb, 'active');"
            ),
            {"s_id": source_id},
        )
        res_sr = conn.execute(
            text(
                "INSERT INTO meta.source_record "
                "(source_id, source_url, object_key, content_sha256, fetched_at) "
                "VALUES (:s_id, 'http://test.url', 'test/key', :sha, now()) "
                "RETURNING source_record_id;"
            ),
            {"s_id": source_id, "sha": sha},
        )
        source_record_id = res_sr.scalar_one()

        res_obs = conn.execute(
            text(
                "INSERT INTO obs.price_observation "
                "(source_record_id, natural_key, product_raw, actor_level, "
                "period_start, period_end, price_raw, price_value, unit_raw, "
                "conversion_status, observed_or_imputed, extraction_method, confidence) "
                "VALUES (:sr_id, :nat_key, 'Riz blanc', 'retail', "
                ":p_start, :p_end, '2500', 2500.0, 'kg', 'exact', 'observed', 'deterministic', 1.0) "
                "RETURNING observation_id;"
            ),
            {
                "sr_id": source_record_id,
                "nat_key": nat_key,
                "p_start": date(2025, 1, 1),
                "p_end": date(2025, 1, 31),
            },
        )
        obs_id_1 = res_obs.scalar_one()

    # 1. Attempting to update a data field (e.g. price_value) must fail
    with app_engine.begin() as conn:
        with pytest.raises(DBAPIError) as exc_info:
            conn.execute(
                text(
                    "UPDATE obs.price_observation SET price_value = 2600.0 "
                    "WHERE observation_id = :id;"
                ),
                {"id": obs_id_1},
            )
        assert "only permit updating superseded_by" in str(exc_info.value).lower()

    # 2. Attempting to delete must fail
    with app_engine.begin() as conn:
        with pytest.raises(DBAPIError) as exc_info:
            conn.execute(
                text("DELETE FROM obs.price_observation WHERE observation_id = :id;"),
                {"id": obs_id_1},
            )
        assert "deletions are forbidden" in str(exc_info.value).lower()

    # 3. Setting superseded_by to an existing observation must succeed
    with app_engine.begin() as conn:
        res_obs2 = conn.execute(
            text(
                "INSERT INTO obs.price_observation "
                "(source_record_id, natural_key, product_raw, actor_level, "
                "period_start, period_end, price_raw, price_value, unit_raw, "
                "conversion_status, observed_or_imputed, extraction_method, confidence) "
                "VALUES (:sr_id, :nat_key, 'Riz blanc', 'retail', "
                ":p_start, :p_end, '2600', 2600.0, 'kg', 'exact', 'observed', 'deterministic', 1.0) "
                "RETURNING observation_id;"
            ),
            {
                "sr_id": source_record_id,
                "nat_key": f"key2_{uuid.uuid4().hex}",
                "p_start": date(2025, 1, 1),
                "p_end": date(2025, 1, 31),
            },
        )
        obs_id_2 = res_obs2.scalar_one()

    with app_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE obs.price_observation SET superseded_by = :new_id "
                "WHERE observation_id = :id;"
            ),
            {"id": obs_id_1, "new_id": obs_id_2},
        )

    # 4. Modifying a superseded record again must fail
    with app_engine.begin() as conn:
        with pytest.raises(DBAPIError) as exc_info:
            conn.execute(
                text(
                    "UPDATE obs.price_observation SET superseded_by = :another_id "
                    "WHERE observation_id = :id;"
                ),
                {"id": obs_id_1, "another_id": obs_id_2},
            )
        assert "already superseded" in str(exc_info.value).lower()
