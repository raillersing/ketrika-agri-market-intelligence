"""Historical as-of dataset builder, C2/C4 temporal integrity, and leak-free partitioning (SPECS §17, ADR-074, R3.2)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ketrika.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DatasetRecord:
    """Canonical observation record inside an as-of dataset."""

    observation_id: str
    source_id: str
    natural_key: str
    product_code: str
    location_pcode: str
    actor_level: str
    period_start: str
    period_end: str
    month: str
    price_mga_per_base: float
    base_unit: str
    observed_or_imputed: str
    published_at: str | None
    first_available_at: str | None
    ingested_at: str
    superseded_by: str | None
    bronze_object_key: str | None

    def to_canonical_dict(self) -> dict[str, Any]:
        """Return deterministic sorted representation for canonical hashing."""
        return {
            "actor_level": self.actor_level,
            "base_unit": self.base_unit,
            "bronze_object_key": self.bronze_object_key,
            "first_available_at": self.first_available_at,
            "ingested_at": self.ingested_at,
            "location_pcode": self.location_pcode,
            "month": self.month,
            "natural_key": self.natural_key,
            "observation_id": self.observation_id,
            "observed_or_imputed": self.observed_or_imputed,
            "period_end": self.period_end,
            "period_start": self.period_start,
            "price_mga_per_base": round(self.price_mga_per_base, 4),
            "product_code": self.product_code,
            "published_at": self.published_at,
            "source_id": self.source_id,
            "superseded_by": self.superseded_by,
        }


@dataclass
class DatasetSplit:
    """Chronologically isolated dataset partition (train, calibration, test)."""

    split_name: str
    period_start: str
    period_end: str
    observations_count: int
    canonical_fingerprint: str
    record_ids: list[str]


@dataclass
class AsOfDataset:
    """Complete frozen dataset artifact with C2 temporal integrity and C4 provenance."""

    dataset_id: str
    name: str
    version: str
    as_of: str
    origin_mode: str  # as_of_point_in_time | retrospective
    cohort: str  # observed | mixed
    canonical_fingerprint: str
    observations_count: int
    observation_ids: list[str]
    artefacts: list[str]
    source_ids: list[str]
    selection_rules: dict[str, Any]
    code_version: str
    taxonomy_version: str
    geography_version: str
    records: list[DatasetRecord] = field(default_factory=list)
    splits: dict[str, DatasetSplit] = field(default_factory=dict)
    exogenous_indicators: list[dict[str, Any]] = field(default_factory=list)

    def to_manifest(self) -> dict[str, Any]:
        """Export dataset manifest without embedding full record payloads."""
        return {
            "dataset_id": self.dataset_id,
            "name": self.name,
            "version": self.version,
            "as_of": self.as_of,
            "origin_mode": self.origin_mode,
            "cohort": self.cohort,
            "canonical_fingerprint": self.canonical_fingerprint,
            "observations_count": self.observations_count,
            "observation_ids": self.observation_ids,
            "artefacts": self.artefacts,
            "source_ids": self.source_ids,
            "selection_rules": self.selection_rules,
            "code_version": self.code_version,
            "taxonomy_version": self.taxonomy_version,
            "geography_version": self.geography_version,
            "splits": {k: asdict(v) for k, v in self.splits.items()},
            "exogenous_count": len(self.exogenous_indicators),
        }


def _to_utc_datetime(val: Any) -> datetime | None:
    """Normalize input value to timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=UTC)
        return val.astimezone(UTC)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, 0, 0, 0, tzinfo=UTC)
    if isinstance(val, str):
        # ISO format parser
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    return None


def compute_canonical_fingerprint(records: list[DatasetRecord]) -> str:
    """Compute strictly deterministic SHA-256 fingerprint over sorted canonical records."""
    # Deterministic sort order by (natural_key, observation_id, month)
    sorted_records = sorted(records, key=lambda r: (r.natural_key, r.observation_id, r.month))
    payload = [r.to_canonical_dict() for r in sorted_records]
    raw_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


def resolve_point_in_time_records(
    raw_records: list[dict[str, Any]],
    as_of: datetime,
    require_observed_only: bool = False,
    allowed_product_codes: list[str] | None = None,
    allowed_location_pcodes: list[str] | None = None,
) -> list[DatasetRecord]:
    """Filter records strictly as-of availability and resolve historical revisions (Contract C2)."""
    as_of_utc = _to_utc_datetime(as_of)
    assert as_of_utc is not None

    # Step 1: Pre-filter by availability at as_of
    # An observation is available at as_of only if:
    # 1. ingested_at <= as_of
    # 2. published_at is None or published_at <= as_of
    # 3. first_available_at is None or first_available_at <= as_of
    available_records: list[dict[str, Any]] = []
    available_by_id: dict[str, dict[str, Any]] = {}

    for r in raw_records:
        ingested_at = _to_utc_datetime(r.get("ingested_at"))
        if ingested_at is None or ingested_at > as_of_utc:
            continue

        published_at = _to_utc_datetime(r.get("published_at"))
        if published_at is not None and published_at > as_of_utc:
            # Future publication -> strictly excluded (anti-leakage)
            continue

        first_avail = _to_utc_datetime(r.get("first_available_at"))
        if first_avail is not None and first_avail > as_of_utc:
            # Future availability -> strictly excluded
            continue

        obs_id_str = str(r["observation_id"])
        available_records.append(r)
        available_by_id[obs_id_str] = r

    # Step 2: Resolve historical revisions point-in-time
    # If record A has superseded_by = B:
    # If B is already available at as_of (ingested_at_B <= as_of), then A is superseded!
    # If B was ingested AFTER as_of (or not in available_by_id), then A was NOT superseded as of as_of!
    active_records: list[DatasetRecord] = []
    allowed_prods = set(allowed_product_codes) if allowed_product_codes else None
    allowed_locs = set(allowed_location_pcodes) if allowed_location_pcodes else None

    for r in available_records:
        obs_id_str = str(r["observation_id"])
        superseded_by_id = r.get("superseded_by")
        superseded_by_str = str(superseded_by_id) if superseded_by_id else None

        if superseded_by_str and superseded_by_str in available_by_id:
            # At as_of, the superseding record was already present -> current record is superseded
            continue

        # Cohort filtering
        obs_kind = str(r.get("observed_or_imputed", "observed"))
        if require_observed_only and obs_kind != "observed":
            continue

        p_code = str(r["product_code"])
        loc_pcode = str(r["location_pcode"])

        if allowed_prods and p_code not in allowed_prods:
            continue
        if allowed_locs and loc_pcode not in allowed_locs:
            continue

        price_val = float(r["price_mga_per_base"])

        period_start = str(r["period_start"])
        period_end = str(r["period_end"])
        month_val = str(r.get("month") or period_start[:7] + "-01")

        pub_iso = _to_utc_datetime(r.get("published_at"))
        first_iso = _to_utc_datetime(r.get("first_available_at"))
        ing_iso = _to_utc_datetime(r.get("ingested_at"))

        rec = DatasetRecord(
            observation_id=obs_id_str,
            source_id=str(r["source_id"]),
            natural_key=str(r["natural_key"]),
            product_code=p_code,
            location_pcode=loc_pcode,
            actor_level=str(r.get("actor_level", "retail")),
            period_start=period_start,
            period_end=period_end,
            month=month_val,
            price_mga_per_base=price_val,
            base_unit=str(r.get("base_unit", "kg")),
            observed_or_imputed=obs_kind,
            published_at=pub_iso.isoformat() if pub_iso else None,
            first_available_at=first_iso.isoformat() if first_iso else None,
            ingested_at=ing_iso.isoformat() if ing_iso else as_of_utc.isoformat(),
            superseded_by=superseded_by_str,
            bronze_object_key=r.get("bronze_object_key"),
        )
        active_records.append(rec)

    # Deterministic sort
    active_records.sort(key=lambda x: (x.product_code, x.location_pcode, x.actor_level, x.month))
    return active_records


def partition_dataset_splits(
    records: list[DatasetRecord],
    train_cutoff: date,
    calibration_cutoff: date | None = None,
) -> dict[str, DatasetSplit]:
    """Chronologically partition records into train, calibration, and test splits without leakage."""
    train_records: list[DatasetRecord] = []
    cal_records: list[DatasetRecord] = []
    test_records: list[DatasetRecord] = []

    for r in records:
        r_month = date.fromisoformat(r.month)
        if r_month <= train_cutoff:
            train_records.append(r)
        elif calibration_cutoff and r_month <= calibration_cutoff:
            cal_records.append(r)
        else:
            test_records.append(r)

    splits: dict[str, DatasetSplit] = {}

    def make_split(name: str, split_recs: list[DatasetRecord]) -> DatasetSplit:
        if not split_recs:
            return DatasetSplit(
                split_name=name,
                period_start="",
                period_end="",
                observations_count=0,
                canonical_fingerprint=hashlib.sha256(b"[]").hexdigest(),
                record_ids=[],
            )
        start_m = min(r.month for r in split_recs)
        end_m = max(r.month for r in split_recs)
        fp = compute_canonical_fingerprint(split_recs)
        return DatasetSplit(
            split_name=name,
            period_start=start_m,
            period_end=end_m,
            observations_count=len(split_recs),
            canonical_fingerprint=fp,
            record_ids=[r.observation_id for r in split_recs],
        )

    splits["train"] = make_split("train", train_records)
    if calibration_cutoff:
        splits["calibration"] = make_split("calibration", cal_records)
    splits["test"] = make_split("test", test_records)

    return splits


def build_as_of_dataset(
    as_of: datetime,
    session: Session | None = None,
    raw_records: list[dict[str, Any]] | None = None,
    name: str = "ketrika_price_as_of",
    version: str = "1.0.0",
    origin_mode: str = "as_of_point_in_time",
    cohort: str = "observed",
    allowed_product_codes: list[str] | None = None,
    allowed_location_pcodes: list[str] | None = None,
    train_cutoff: date | None = None,
    calibration_cutoff: date | None = None,
    raw_macro_records: list[dict[str, Any]] | None = None,
) -> AsOfDataset:
    """Build a mathematically frozen, point-in-time as-of training dataset."""
    as_of_utc = _to_utc_datetime(as_of)
    assert as_of_utc is not None

    records_to_process: list[dict[str, Any]] = []

    if raw_records is not None:
        records_to_process = raw_records
    elif session is not None:
        # Query database with historical point-in-time constraints
        query = text(
            """
            SELECT
                po.observation_id,
                sr.source_id,
                sr.storage_key AS bronze_object_key,
                po.natural_key,
                p.product_code,
                loc.pcode AS location_pcode,
                po.actor_level,
                po.period_start,
                po.period_end,
                date_trunc('month', po.period_start)::date AS month,
                po.price_mga_per_base,
                po.base_unit,
                po.observed_or_imputed,
                po.published_at,
                po.ingested_at,
                po.superseded_by,
                po.superseded_by IS NOT NULL AS is_superseded
            FROM obs.price_observation po
            JOIN meta.source_record sr ON po.source_record_id = sr.source_record_id
            JOIN ref.product p ON po.product_id = p.product_id
            JOIN ref.location loc ON po.location_id = loc.location_id
            WHERE po.ingested_at <= :as_of
              AND po.price_mga_per_base IS NOT NULL
              AND po.price_mga_per_base > 0
              AND po.review_status = 'accepted'
            ORDER BY po.period_start ASC;
            """
        )
        rows = session.execute(query, {"as_of": as_of_utc}).fetchall()
        for r in rows:
            records_to_process.append(
                {
                    "observation_id": str(r.observation_id),
                    "source_id": r.source_id,
                    "bronze_object_key": r.bronze_object_key,
                    "natural_key": r.natural_key,
                    "product_code": r.product_code,
                    "location_pcode": r.location_pcode,
                    "actor_level": r.actor_level,
                    "period_start": str(r.period_start),
                    "period_end": str(r.period_end),
                    "month": str(r.month),
                    "price_mga_per_base": float(r.price_mga_per_base),
                    "base_unit": r.base_unit,
                    "observed_or_imputed": r.observed_or_imputed,
                    "published_at": r.published_at,
                    "first_available_at": r.published_at,  # In price_obs, published_at is availability
                    "ingested_at": r.ingested_at,
                    "superseded_by": str(r.superseded_by) if r.superseded_by else None,
                }
            )

    require_obs_only = cohort == "observed"
    active_records = resolve_point_in_time_records(
        raw_records=records_to_process,
        as_of=as_of_utc,
        require_observed_only=require_obs_only,
        allowed_product_codes=allowed_product_codes,
        allowed_location_pcodes=allowed_location_pcodes,
    )

    fingerprint = compute_canonical_fingerprint(active_records)

    obs_ids = [r.observation_id for r in active_records]
    artefacts = sorted({r.bronze_object_key for r in active_records if r.bronze_object_key})
    source_ids = sorted({r.source_id for r in active_records})

    selection_rules = {
        "as_of": as_of_utc.isoformat(),
        "origin_mode": origin_mode,
        "cohort": cohort,
        "allowed_products": allowed_product_codes,
        "allowed_locations": allowed_location_pcodes,
        "train_cutoff": train_cutoff.isoformat() if train_cutoff else None,
        "calibration_cutoff": calibration_cutoff.isoformat() if calibration_cutoff else None,
    }

    # Partition splits if train_cutoff specified
    splits: dict[str, DatasetSplit] = {}
    if train_cutoff:
        splits = partition_dataset_splits(
            records=active_records,
            train_cutoff=train_cutoff,
            calibration_cutoff=calibration_cutoff,
        )

    # Exogenous indicators filtered as-of
    exog_filtered: list[dict[str, Any]] = []
    if raw_macro_records:
        for m in raw_macro_records:
            m_avail = _to_utc_datetime(m.get("first_available_at") or m.get("published_at"))
            m_ing = _to_utc_datetime(m.get("ingested_at"))
            if m_avail and m_avail <= as_of_utc and (m_ing is None or m_ing <= as_of_utc):
                exog_filtered.append(m)

    dataset_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ketrika.ml.dataset:{fingerprint}"))

    dataset = AsOfDataset(
        dataset_id=dataset_id,
        name=name,
        version=version,
        as_of=as_of_utc.isoformat(),
        origin_mode=origin_mode,
        cohort=cohort,
        canonical_fingerprint=fingerprint,
        observations_count=len(active_records),
        observation_ids=obs_ids,
        artefacts=artefacts,
        source_ids=source_ids,
        selection_rules=selection_rules,
        code_version="1.0.0",
        taxonomy_version="1.0.0",
        geography_version="1.0.0",
        records=active_records,
        splits=splits,
        exogenous_indicators=exog_filtered,
    )

    logger.info(
        "as_of_dataset_built",
        dataset_id=dataset.dataset_id,
        as_of=dataset.as_of,
        observations_count=dataset.observations_count,
        fingerprint=dataset.canonical_fingerprint,
        splits=list(dataset.splits.keys()),
    )
    return dataset
