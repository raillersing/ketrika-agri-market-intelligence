"""Unit tests for as-of historical datasets, temporal integrity C2, and C4 provenance (SPECS §17, ADR-074, R3.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

from ketrika.ml.dataset import build_as_of_dataset


def _make_raw_record(
    obs_id: str | None = None,
    product_code: str = "rice_milled",
    location_pcode: str = "MG11",
    actor_level: str = "retail",
    month: str = "2024-01-01",
    price: float = 3000.0,
    observed_or_imputed: str = "observed",
    published_at: datetime | str | None = None,
    ingested_at: datetime | str | None = None,
    superseded_by: str | None = None,
    bronze_key: str = "bronze/raw/odr/2024/doc.pdf",
) -> dict:
    return {
        "observation_id": obs_id or str(uuid.uuid4()),
        "source_id": "miasa_odr",
        "natural_key": f"nk_{product_code}_{location_pcode}_{month}_{price}",
        "product_code": product_code,
        "location_pcode": location_pcode,
        "actor_level": actor_level,
        "period_start": month,
        "period_end": month[:7] + "-28",
        "month": month,
        "price_mga_per_base": price,
        "base_unit": "kg",
        "observed_or_imputed": observed_or_imputed,
        "published_at": published_at,
        "first_available_at": published_at,
        "ingested_at": ingested_at or datetime(2024, 1, 15, tzinfo=UTC),
        "superseded_by": superseded_by,
        "bronze_object_key": bronze_key,
    }


def test_anti_leakage_future_publication_excluded():
    """Verify that a January price published in March is absent in February and present in March (criterion R3.2)."""
    # Observation for January 2024, but published on 2024-03-05
    jan_obs_id = str(uuid.uuid4())
    rec = _make_raw_record(
        obs_id=jan_obs_id,
        month="2024-01-01",
        price=2800.0,
        published_at=datetime(2024, 3, 5, 10, 0, tzinfo=UTC),
        ingested_at=datetime(2024, 3, 5, 12, 0, tzinfo=UTC),
    )

    # 1. Dataset as-of mid-February 2024
    as_of_feb = datetime(2024, 2, 15, 0, 0, tzinfo=UTC)
    ds_feb = build_as_of_dataset(as_of=as_of_feb, raw_records=[rec])
    assert ds_feb.observations_count == 0
    assert jan_obs_id not in ds_feb.observation_ids

    # 2. Dataset as-of mid-March 2024 (after publication)
    as_of_mar = datetime(2024, 3, 15, 0, 0, tzinfo=UTC)
    ds_mar = build_as_of_dataset(as_of=as_of_mar, raw_records=[rec])
    assert ds_mar.observations_count == 1
    assert jan_obs_id in ds_mar.observation_ids
    assert ds_mar.records[0].price_mga_per_base == 2800.0


def test_historical_revision_exclusion_and_point_in_time_preservation():
    """Verify that an April revision is excluded in March, preserving the initial active version (criterion R3.2)."""
    id_initial = str(uuid.uuid4())
    id_revision = str(uuid.uuid4())

    # Record A: Ingested on 2024-03-01 with price 2500, superseded later by B
    rec_initial = _make_raw_record(
        obs_id=id_initial,
        month="2024-02-01",
        price=2500.0,
        published_at=datetime(2024, 3, 1, 9, 0, tzinfo=UTC),
        ingested_at=datetime(2024, 3, 1, 10, 0, tzinfo=UTC),
        superseded_by=id_revision,
    )

    # Record B: Correction ingested on 2024-04-05 with revised price 2550
    rec_revision = _make_raw_record(
        obs_id=id_revision,
        month="2024-02-01",
        price=2550.0,
        published_at=datetime(2024, 4, 5, 9, 0, tzinfo=UTC),
        ingested_at=datetime(2024, 4, 5, 10, 0, tzinfo=UTC),
        superseded_by=None,
    )

    raw_pool = [rec_initial, rec_revision]

    # 1. As-of March 15, 2024:
    # B does not exist yet. Record A was active and must be retained!
    as_of_mar = datetime(2024, 3, 15, 0, 0, tzinfo=UTC)
    ds_mar = build_as_of_dataset(as_of=as_of_mar, raw_records=raw_pool)

    assert ds_mar.observations_count == 1
    assert ds_mar.observation_ids == [id_initial]
    assert ds_mar.records[0].price_mga_per_base == 2500.0

    # 2. As-of April 15, 2024:
    # B is ingested. Record A is now superseded and replaced by B!
    as_of_apr = datetime(2024, 4, 15, 0, 0, tzinfo=UTC)
    ds_apr = build_as_of_dataset(as_of=as_of_apr, raw_records=raw_pool)

    assert ds_apr.observations_count == 1
    assert ds_apr.observation_ids == [id_revision]
    assert ds_apr.records[0].price_mga_per_base == 2550.0


def test_deterministic_recomputation_identical_fingerprint():
    """Verify that rebuilding the dataset from different raw ordering yields identical canonical SHA-256."""
    as_of = datetime(2024, 3, 1, 0, 0, tzinfo=UTC)

    r1 = _make_raw_record(month="2023-11-01", price=2400.0, published_at=datetime(2023, 11, 15, tzinfo=UTC))
    r2 = _make_raw_record(month="2023-12-01", price=2450.0, published_at=datetime(2023, 12, 15, tzinfo=UTC))
    r3 = _make_raw_record(month="2024-01-01", price=2500.0, published_at=datetime(2024, 1, 15, tzinfo=UTC))

    ds1 = build_as_of_dataset(as_of=as_of, raw_records=[r1, r2, r3])
    # Shuffled input order
    ds2 = build_as_of_dataset(as_of=as_of, raw_records=[r3, r1, r2])

    assert ds1.canonical_fingerprint == ds2.canonical_fingerprint
    assert ds1.dataset_id == ds2.dataset_id
    assert ds1.observations_count == 3
    assert [r.month for r in ds1.records] == ["2023-11-01", "2023-12-01", "2024-01-01"]
    assert [r.month for r in ds2.records] == ["2023-11-01", "2023-12-01", "2024-01-01"]


def test_no_unknown_uuids_and_artefacts_lineage():
    """Verify dataset records reference exact observation IDs and Bronze artefacts."""
    as_of = datetime(2024, 3, 1, 0, 0, tzinfo=UTC)
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())

    r1 = _make_raw_record(obs_id=id1, bronze_key="bronze/source_a/f1.csv")
    r2 = _make_raw_record(obs_id=id2, bronze_key="bronze/source_b/f2.xlsx")

    ds = build_as_of_dataset(as_of=as_of, raw_records=[r1, r2])
    assert set(ds.observation_ids) == {id1, id2}
    assert ds.artefacts == ["bronze/source_a/f1.csv", "bronze/source_b/f2.xlsx"]
    assert ds.source_ids == ["miasa_odr"]

    manifest = ds.to_manifest()
    assert manifest["observations_count"] == 2
    assert manifest["canonical_fingerprint"] == ds.canonical_fingerprint


def test_exogenous_variables_aligned_as_of():
    """Verify that exogenous variables (macro, exchange rate) must be available at as-of date."""
    as_of = datetime(2024, 2, 1, 0, 0, tzinfo=UTC)
    price_rec = _make_raw_record(month="2024-01-01", price=3000.0)

    macro_valid = {
        "indicator_code": "FX_USD_MGA",
        "value": 4500.0,
        "first_available_at": datetime(2024, 1, 31, 23, 0, tzinfo=UTC),
        "ingested_at": datetime(2024, 1, 31, 23, 30, tzinfo=UTC),
    }
    macro_future = {
        "indicator_code": "CPI_INDEX",
        "value": 115.2,
        "first_available_at": datetime(2024, 2, 15, 0, 0, tzinfo=UTC),  # Future availability!
        "ingested_at": datetime(2024, 2, 15, 0, 0, tzinfo=UTC),
    }

    ds = build_as_of_dataset(
        as_of=as_of,
        raw_records=[price_rec],
        raw_macro_records=[macro_valid, macro_future],
    )
    assert len(ds.exogenous_indicators) == 1
    assert ds.exogenous_indicators[0]["indicator_code"] == "FX_USD_MGA"


def test_leak_free_partitioning_splits():
    """Verify chronologically disjoint train, calibration, and test splits."""
    as_of = datetime(2024, 4, 1, 0, 0, tzinfo=UTC)

    records = [
        _make_raw_record(month="2023-01-01", price=2000.0),
        _make_raw_record(month="2023-06-01", price=2100.0),
        _make_raw_record(month="2023-11-01", price=2200.0),
        _make_raw_record(month="2023-12-01", price=2250.0),
        _make_raw_record(month="2024-01-01", price=2300.0),
        _make_raw_record(month="2024-02-01", price=2350.0),
        _make_raw_record(month="2024-03-01", price=2400.0),
    ]

    ds = build_as_of_dataset(
        as_of=as_of,
        raw_records=records,
        train_cutoff=date(2023, 11, 30),
        calibration_cutoff=date(2024, 1, 31),
    )

    assert "train" in ds.splits
    assert "calibration" in ds.splits
    assert "test" in ds.splits

    train_ids = set(ds.splits["train"].record_ids)
    cal_ids = set(ds.splits["calibration"].record_ids)
    test_ids = set(ds.splits["test"].record_ids)

    # Absolutely zero overlap
    assert len(train_ids & cal_ids) == 0
    assert len(train_ids & test_ids) == 0
    assert len(cal_ids & test_ids) == 0
    assert len(train_ids | cal_ids | test_ids) == 7

    assert ds.splits["train"].observations_count == 3
    assert ds.splits["calibration"].observations_count == 2
    assert ds.splits["test"].observations_count == 2


def test_cohort_filtering_pure_observed_vs_mixed():
    """Verify cohort isolation: observed only vs mixed."""
    as_of = datetime(2024, 4, 1, 0, 0, tzinfo=UTC)
    r_obs = _make_raw_record(product_code="rice_milled", observed_or_imputed="observed")
    r_imp = _make_raw_record(product_code="maize", observed_or_imputed="imputed")

    ds_obs = build_as_of_dataset(as_of=as_of, raw_records=[r_obs, r_imp], cohort="observed")
    assert ds_obs.observations_count == 1
    assert ds_obs.records[0].product_code == "rice_milled"

    ds_mixed = build_as_of_dataset(as_of=as_of, raw_records=[r_obs, r_imp], cohort="mixed")
    assert ds_mixed.observations_count == 2


def test_as_of_dataset_with_mock_session_sql():
    """Verify build_as_of_dataset SQL query execution with mock session."""
    as_of = datetime(2024, 3, 1, 0, 0, tzinfo=UTC)

    class MockSQLRow:
        observation_id = uuid.uuid4()
        source_id = "miasa_odr"
        bronze_object_key = "bronze/raw/sample.pdf"
        natural_key = "nk_sql_1"
        product_code = "rice_milled"
        location_pcode = "MG11"
        actor_level = "retail"
        period_start = date(2024, 1, 1)
        period_end = date(2024, 1, 31)
        month = date(2024, 1, 1)
        price_mga_per_base = 3200.0
        base_unit = "kg"
        observed_or_imputed = "observed"
        published_at = datetime(2024, 2, 1, tzinfo=UTC)
        ingested_at = datetime(2024, 2, 1, 10, 0, tzinfo=UTC)
        superseded_by = None

    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [MockSQLRow()]

    ds = build_as_of_dataset(as_of=as_of, session=mock_session)
    assert ds.observations_count == 1
    assert ds.records[0].price_mga_per_base == 3200.0
    assert ds.records[0].product_code == "rice_milled"
