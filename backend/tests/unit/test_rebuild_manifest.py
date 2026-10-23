"""Content comparison regressions; synthetic fixtures, not authentic rebuild proof."""

import copy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import uuid4

import pytest

from ketrika.core.rebuild_manifest import (
    OBS_COLUMNS,
    TABLES,
    ManifestError,
    canonical_manifest,
    capture_database,
    compare_manifests,
)
from ketrika.gold.refresh import ORDERED_GOLD_VIEWS, UNPUBLISHED_GOLD_VIEWS


@pytest.fixture
def snapshot():
    columns = {table: sorted(OBS_COLUMNS.get(table, {"metric"})) for table in TABLES}
    tables = {table: [] for table in TABLES}
    row = dict.fromkeys(columns["obs.price_observation"])
    row.update(
        observation_id=uuid4(),
        source_record_id=uuid4(),
        natural_key="synthetic-key",
        product_raw="synthetic-rice",
        product_id=uuid4(),
        location_id=uuid4(),
        price_raw="2800",
        price_value=Decimal("2800.0000"),
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        ingested_at=datetime(2026, 10, 15, tzinfo=UTC),
        unit_raw="kg",
        currency_raw="MGA",
        observed_or_imputed="observed",
        evidence={"row": [1, None, True, "2800"]},
    )
    tables["obs.price_observation"] = [row]
    columns["gold.price_obs_current"] = ["observation_id", "price_value", "ingested_at"]
    tables["gold.price_obs_current"] = [
        {key: row[key] for key in columns["gold.price_obs_current"]}
    ]
    return tables, columns


def test_ignores_only_generated_identity_and_ingestion_time(snapshot):
    tables, columns = snapshot
    before = canonical_manifest(tables, columns)
    changed = copy.deepcopy(tables)
    identifier = uuid4()
    for table in ("obs.price_observation", "gold.price_obs_current"):
        changed[table][0]["observation_id"] = identifier
        changed[table][0]["ingested_at"] += timedelta(days=1)
    after = canonical_manifest(changed, columns)
    assert before == after
    assert compare_manifests(before, after)["content_identical"] is True
    assert tables["obs.price_observation"][0]["observation_id"] != identifier


@pytest.mark.parametrize(
    "field,value",
    [
        ("price_value", Decimal("2801")),
        ("price_raw", "2 800"),
        ("unit_raw", "bag"),
        ("currency_raw", "USD"),
        ("period_start", date(2025, 1, 2)),
        ("period_end", date(2025, 1, 30)),
        ("observed_or_imputed", "imputed"),
        ("source_record_id", uuid4()),
        ("product_id", uuid4()),
        ("location_id", uuid4()),
        ("review_status", "rejected"),
        ("confidence", Decimal("0.1")),
        ("evidence", {"row": [2, None, True, "2800"]}),
    ],
)
def test_equal_counts_never_hide_changed_business_field(snapshot, field, value):
    tables, columns = snapshot
    before = canonical_manifest(tables, columns)
    tables["obs.price_observation"][0][field] = value
    result = compare_manifests(before, canonical_manifest(tables, columns))
    assert result["content_identical"] is False
    diff = result["changed_tables"]["obs.price_observation"]
    assert diff["before"]["count"] == diff["after"]["count"] == 1
    assert diff["before"]["sha256"] != diff["after"]["sha256"]


@pytest.mark.parametrize("length", [1, 2, 4])
def test_revision_cycles_cannot_be_certified_as_an_identical_replay(snapshot, length):
    tables, columns = snapshot
    first = tables["obs.price_observation"][0]
    rows = [first]
    for index in range(1, length):
        row = copy.deepcopy(first)
        row.update(observation_id=uuid4(), price_raw=str(2800 + index))
        rows.append(row)
    for index, row in enumerate(rows):
        row["superseded_by"] = rows[(index + 1) % length]["observation_id"]
    tables["obs.price_observation"] = rows
    with pytest.raises(ManifestError, match="manifest_revision_cycle"):
        canonical_manifest(tables, columns)


def test_revision_links_survive_regenerated_uuids(snapshot):
    tables, columns = snapshot
    old = tables["obs.price_observation"][0]
    new = copy.deepcopy(old)
    new.update(observation_id=uuid4(), source_record_id=uuid4(), price_value=Decimal("2900"))
    old["superseded_by"] = new["observation_id"]
    tables["obs.price_observation"].append(new)
    before = canonical_manifest(tables, columns)
    old["observation_id"], new["observation_id"] = uuid4(), uuid4()
    old["superseded_by"] = new["observation_id"]
    tables["gold.price_obs_current"][0]["observation_id"] = old["observation_id"]
    assert before == canonical_manifest(tables, columns)
    old["superseded_by"] = None
    result = compare_manifests(before, canonical_manifest(tables, columns))
    assert result["content_identical"] is False


@pytest.mark.parametrize("location", ["superseded_by", "gold"])
def test_missing_revision_or_gold_target_refused(snapshot, location):
    tables, columns = snapshot
    table, field = (
        ("gold.price_obs_current", "observation_id")
        if location == "gold"
        else ("obs.price_observation", "superseded_by")
    )
    tables[table][0][field] = uuid4()
    with pytest.raises(ManifestError, match="missing_observation_target"):
        canonical_manifest(tables, columns)


@pytest.mark.parametrize("same_id", [True, False])
def test_ambiguous_observation_refused(snapshot, same_id):
    tables, columns = snapshot
    duplicate = copy.deepcopy(tables["obs.price_observation"][0])
    if not same_id:
        duplicate["observation_id"] = uuid4()
    tables["obs.price_observation"].append(duplicate)
    with pytest.raises(ManifestError, match="ambiguous_observation"):
        canonical_manifest(tables, columns)


@pytest.mark.parametrize("mutation", ["table", "column", "row", "duplicate_column"])
def test_incomplete_projection_refused(snapshot, mutation):
    tables, columns = snapshot
    if mutation == "table":
        del tables["obs.event"]
    elif mutation == "column":
        columns["obs.price_observation"].remove("price_raw")
    elif mutation == "row":
        del tables["obs.price_observation"][0]["price_raw"]
    else:
        columns["obs.price_observation"].append("price_raw")
    with pytest.raises(ManifestError):
        canonical_manifest(tables, columns)


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), Decimal("NaN"), object(), datetime(2025, 1, 1)]
)
def test_unsafe_scalar_refused(snapshot, value):
    tables, columns = snapshot
    tables["obs.price_observation"][0]["price_value"] = value
    with pytest.raises(ManifestError):
        canonical_manifest(tables, columns)


def test_decimal_precision_not_rounded_by_context(snapshot):
    tables, columns = snapshot
    tables["obs.price_observation"][0]["price_value"] = Decimal("123456789012345678.123456789")
    with localcontext() as context:
        context.prec = 3
        first = canonical_manifest(tables, columns)
        tables["obs.price_observation"][0]["price_value"] += Decimal(0)  # actual context rounding
        second = canonical_manifest(tables, columns)
    assert not compare_manifests(first, second)["content_identical"]


def test_decimal_trailing_zero_normalization(snapshot):
    tables, columns = snapshot
    before = canonical_manifest(tables, columns)
    tables["obs.price_observation"][0]["price_value"] = Decimal("2800")
    assert before == canonical_manifest(tables, columns)


def test_typed_values_do_not_collide(snapshot):
    tables, columns = snapshot
    before = canonical_manifest(tables, columns)
    tables["obs.price_observation"][0]["price_value"] = "2800"
    assert not compare_manifests(before, canonical_manifest(tables, columns))["content_identical"]


def test_gold_difference_and_schema_difference_visible(snapshot):
    tables, columns = snapshot
    before = canonical_manifest(tables, columns)
    tables["gold.price_obs_current"][0]["price_value"] = Decimal("2801")
    assert (
        "gold.price_obs_current"
        in compare_manifests(before, canonical_manifest(tables, columns))["changed_tables"]
    )
    columns["gold.stock_latest"].append("new_column")
    assert (
        "gold.stock_latest"
        in compare_manifests(before, canonical_manifest(tables, columns))["changed_tables"]
    )


def test_receipt_tampering_refused(snapshot):
    document = canonical_manifest(*snapshot)
    after = copy.deepcopy(document)
    after["tables"]["obs.event"]["count"] = 1
    with pytest.raises(ManifestError, match="hash_mismatch"):
        compare_manifests(document, after)


def test_empty_tables_are_present_not_successful_rebuild():
    tables = {table: [] for table in TABLES}
    columns = {table: sorted(OBS_COLUMNS.get(table, {"metric"})) for table in TABLES}
    manifest = canonical_manifest(tables, columns)
    assert len(manifest["tables"]) == len(TABLES)
    assert len(TABLES) == (len(OBS_COLUMNS) + len(ORDERED_GOLD_VIEWS) - len(UNPUBLISHED_GOLD_VIEWS))
    assert "gold.economic_dashboard" not in TABLES
    assert set(manifest["tables"]) == set(TABLES)
    assert all(item["count"] == 0 for item in manifest["tables"].values())
    assert "passed" not in manifest  # identity is not a replay/authenticity claim


def test_database_inventory_tolerates_publication_reserved_views():
    class InventoryResult:
        def scalars(self):
            return sorted(TABLES | {"gold.economic_dashboard"})

    class Session:
        statements = []

        def execute(self, statement):
            self.statements.append(str(statement))
            if len(self.statements) == 1:
                return InventoryResult()
            raise ManifestError("reached_capture_reads")

    session = Session()
    with pytest.raises(ManifestError, match="reached_capture_reads"):
        capture_database(session)
    assert session.statements[0].startswith("SELECT schemaname || '.' || tablename")


def test_database_inventory_checked_before_reading_rows():
    class Result:
        def scalars(self):
            return ["obs.price_observation"]

    class Session:
        statements = []

        def execute(self, statement):
            self.statements.append(str(statement))
            return Result()

    session = Session()
    with pytest.raises(ManifestError, match="database_inventory_mismatch"):
        capture_database(session)
    assert len(session.statements) == 1
    assert session.statements[0].startswith("SELECT ")
