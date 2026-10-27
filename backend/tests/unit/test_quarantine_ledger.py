"""Unit tests for quarantine ledger and anti-self-link models and guards (ADR-131, AU-08)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ketrika.core.models.db import QuarantineLedger
from ketrika.core.rebuild_manifest import ManifestError, canonical_manifest


def test_quarantine_ledger_model_attributes():
    qid = uuid4()
    obs_id = uuid4()
    srid = uuid4()
    now = datetime.now(UTC)
    entry = QuarantineLedger(
        quarantine_id=qid,
        table_name="obs.price_observation",
        observation_id=obs_id,
        source_record_id=srid,
        reason_code="HISTORICAL_SELF_LINK",
        details={"sample": "data"},
        operator="test_runner",
        quarantined_at=now,
    )
    assert entry.quarantine_id == qid
    assert entry.table_name == "obs.price_observation"
    assert entry.observation_id == obs_id
    assert entry.source_record_id == srid
    assert entry.reason_code == "HISTORICAL_SELF_LINK"
    assert entry.details == {"sample": "data"}
    assert entry.operator == "test_runner"
    assert entry.quarantined_at == now
    assert entry.revoked_at is None
    assert entry.revocation_reason is None


def test_rebuild_manifest_quarantine_projection():
    obs_id = uuid4()
    qid = uuid4()
    sr_id = uuid4()
    now = datetime.now(UTC)

    # Simulated tables matching Base metadata schema
    from ketrika.core.rebuild_manifest import OBS_COLUMNS, TABLES

    tables = {table: [] for table in TABLES}
    columns = {
        table: sorted(OBS_COLUMNS[table]) if table in OBS_COLUMNS else [] for table in TABLES
    }

    # Populate obs.quarantine_ledger
    columns["obs.quarantine_ledger"] = sorted(
        [
            "quarantine_id",
            "table_name",
            "observation_id",
            "source_record_id",
            "reason_code",
            "details",
            "operator",
            "quarantined_at",
            "revoked_at",
            "revocation_reason",
        ]
    )
    tables["obs.quarantine_ledger"] = [
        {
            "quarantine_id": qid,
            "table_name": "obs.price_observation",
            "observation_id": obs_id,
            "source_record_id": sr_id,
            "reason_code": "HISTORICAL_SELF_LINK",
            "details": {"key": "val"},
            "operator": "test",
            "quarantined_at": now,
            "revoked_at": None,
            "revocation_reason": None,
        }
    ]

    # Populate dummy observation in obs.price_observation without cycle
    obs_cols = list(OBS_COLUMNS["obs.price_observation"])
    columns["obs.price_observation"] = sorted(obs_cols)
    price_row = dict.fromkeys(obs_cols)
    price_row["observation_id"] = obs_id
    price_row["source_record_id"] = sr_id
    price_row["natural_key"] = "test_nk"
    price_row["product_raw"] = "riz"
    price_row["actor_level"] = "retail"
    price_row["period_start"] = now.date()
    price_row["period_end"] = now.date()
    price_row["observed_or_imputed"] = "observed"
    price_row["extraction_method"] = "deterministic"
    price_row["confidence"] = 1.0
    price_row["review_status"] = "accepted"
    price_row["superseded_by"] = None  # Cleaned, no self-link!
    price_row["ingested_at"] = now
    tables["obs.price_observation"] = [price_row]

    # Fill gold views with empty schemas
    from ketrika.gold.refresh import ORDERED_GOLD_VIEWS, UNPUBLISHED_GOLD_VIEWS

    reserved = frozenset("gold." + v for v in UNPUBLISHED_GOLD_VIEWS)
    for gv in ORDERED_GOLD_VIEWS:
        table_name = "gold." + gv
        if table_name not in reserved and not columns[table_name]:
            columns[table_name] = ["dummy_col"]

    manifest = canonical_manifest(tables, columns)
    assert manifest["version"] == 1
    assert "obs.quarantine_ledger" in manifest["tables"]
    assert manifest["tables"]["obs.quarantine_ledger"]["count"] == 1


def test_rebuild_manifest_rejects_self_links_as_cycles():
    from ketrika.core.rebuild_manifest import OBS_COLUMNS, TABLES

    obs_id = uuid4()
    now = datetime.now(UTC)

    tables = {table: [] for table in TABLES}
    columns = {
        table: sorted(OBS_COLUMNS[table]) if table in OBS_COLUMNS else [] for table in TABLES
    }

    # Price observation with self-link: superseded_by = observation_id
    obs_cols = list(OBS_COLUMNS["obs.price_observation"])
    columns["obs.price_observation"] = sorted(obs_cols)
    price_row = dict.fromkeys(obs_cols)
    price_row["observation_id"] = obs_id
    price_row["source_record_id"] = uuid4()
    price_row["natural_key"] = "test_nk"
    price_row["product_raw"] = "riz"
    price_row["actor_level"] = "retail"
    price_row["period_start"] = now.date()
    price_row["period_end"] = now.date()
    price_row["observed_or_imputed"] = "observed"
    price_row["extraction_method"] = "deterministic"
    price_row["confidence"] = 1.0
    price_row["review_status"] = "accepted"
    price_row["superseded_by"] = obs_id  # DEFECTIVE SELF-LINK
    price_row["ingested_at"] = now
    tables["obs.price_observation"] = [price_row]

    from ketrika.gold.refresh import ORDERED_GOLD_VIEWS, UNPUBLISHED_GOLD_VIEWS

    reserved = frozenset("gold." + v for v in UNPUBLISHED_GOLD_VIEWS)
    for gv in ORDERED_GOLD_VIEWS:
        table_name = "gold." + gv
        if table_name not in reserved and not columns[table_name]:
            columns[table_name] = ["dummy_col"]

    columns["obs.quarantine_ledger"] = sorted(
        [
            "quarantine_id",
            "table_name",
            "observation_id",
            "source_record_id",
            "reason_code",
            "details",
            "operator",
            "quarantined_at",
            "revoked_at",
            "revocation_reason",
        ]
    )

    with pytest.raises(ManifestError, match="manifest_revision_cycle"):
        canonical_manifest(tables, columns)
