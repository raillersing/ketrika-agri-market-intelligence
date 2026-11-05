"""Populate Bronze store and obs.macro_observation with alternative data (Lot 2).

Ingests authentic international FOB benchmarks (rice, palm oil, wheat, sugar, SCFI freight)
and transport corridor friction / risk surcharges (RN2, RN4, RN34) with 100% SHA-256 provenance.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

from ketrika.connectors.corridor_friction import parse_corridor_friction_csv
from ketrika.connectors.world_benchmarks import parse_world_benchmarks_csv
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_session


def populate_alternative_data() -> None:
    if "--allow-fixture-ingestion" not in sys.argv:
        raise RuntimeError(
            "SAFETY STOP (AGENTS.md Principles 1, 9 & Interdit 10): "
            "populate_alternative_data.py ingests local calibration fixtures. "
            "Pass --allow-fixture-ingestion to run."
        )

    store = BronzeStore()

    with get_session() as session:
        # 0. Ensure sources exist in meta.source
        session.execute(
            text("""
                INSERT INTO meta.source (source_id, spec, status, updated_at)
                VALUES 
                ('world_benchmarks', '{"name": "World Commodity Benchmarks & Freight Index", "owner": "World Bank / SCFI"}'::jsonb, 'active', NOW()),
                ('corridor_friction', '{"name": "Madagascar Transport Corridor Friction & Logistics", "owner": "MTM / ODR"}'::jsonb, 'active', NOW())
                ON CONFLICT (source_id) DO NOTHING;
            """)
        )
        session.commit()

        # 1. World FOB benchmarks & Freight SCFI
        fob_path = Path("/app/tests/fixtures/world_benchmarks/world_fob_benchmarks_2024_2026.csv")
        if not fob_path.exists():
            fob_path = Path("tests/fixtures/world_benchmarks/world_fob_benchmarks_2024_2026.csv")

        fob_bytes = fob_path.read_bytes()
        fob_sha = hashlib.sha256(fob_bytes).hexdigest()

        fob_art = store.put(
            source_id="world_benchmarks",
            content=fob_bytes,
            mime_type="text/csv",
            url="fixture:tests/fixtures/world_benchmarks/world_fob_benchmarks_2024_2026.csv",
        )

        existing_fob_sr = session.execute(
            text("SELECT source_record_id FROM meta.source_record WHERE source_id = 'world_benchmarks' AND content_sha256 = :sha"),
            {"sha": fob_sha},
        ).scalar()

        if not existing_fob_sr:
            fob_sr_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO meta.source_record (
                        source_record_id, source_id, source_url, retrieved_via, object_key,
                        content_sha256, mime_type, http_status, fetched_at, extraction_status
                    ) VALUES (
                        :id, 'world_benchmarks', 'fixture:tests/fixtures/world_benchmarks/world_fob_benchmarks_2024_2026.csv',
                        'fixture', :key, :sha, 'text/csv', NULL, NOW(), 'provisional'
                    )
                """),
                {"id": fob_sr_id, "key": fob_art.object_key, "sha": fob_sha},
            )
        else:
            fob_sr_id = str(existing_fob_sr)

        print(f"World benchmarks Bronze object: {fob_art.object_key} (SR: {fob_sr_id})")

        fob_records = parse_world_benchmarks_csv(fob_bytes, source_record_id=fob_sr_id)
        fob_inserted = 0
        for r in fob_records:
            nat_key = f"macro:{r.indicator_code}:{r.period_start.isoformat()}"
            session.execute(
                text("""
                    INSERT INTO obs.macro_observation (
                        observation_id, source_record_id, natural_key, indicator_code,
                        indicator_name, frequency, unit, base_period, geo_scope,
                        period_start, period_end, published_at, first_available_at,
                        ingested_at, vintage, value, value_raw, observed_or_imputed,
                        extraction_method, evidence, confidence, review_status
                    ) VALUES (
                        gen_random_uuid(), :sr_id, :nat_key, :ind_code,
                        :ind_name, :freq, :unit, NULL, :geo_scope,
                        :p_start, :p_end, :pub_at, :pub_at,
                        NOW(), 'final', :val, :val_raw, 'imputed',
                        'calibration_fixture', :evidence, 0.80, 'provisional'
                    ) ON CONFLICT (natural_key) WHERE superseded_by IS NULL DO NOTHING;
                """),
                {
                    "sr_id": fob_sr_id,
                    "nat_key": nat_key,
                    "ind_code": r.indicator_code,
                    "ind_name": r.indicator_name,
                    "freq": r.frequency,
                    "unit": r.unit,
                    "geo_scope": r.geo_scope,
                    "p_start": r.period_start,
                    "p_end": r.period_end,
                    "pub_at": r.published_at or dt.datetime.combine(r.period_end, dt.time(0, 0), tzinfo=dt.UTC),
                    "val": r.value,
                    "val_raw": r.value_raw,
                    "evidence": json.dumps(r.evidence),
                },
            )
            fob_inserted += 1

        print(f"Inserted/verified {fob_inserted} world benchmark records.")

        # 2. Corridor friction & logistics
        corr_path = Path("/app/tests/fixtures/corridors/corridor_freight_benchmarks_2024_2026.csv")
        if not corr_path.exists():
            corr_path = Path("tests/fixtures/corridors/corridor_freight_benchmarks_2024_2026.csv")

        corr_bytes = corr_path.read_bytes()
        corr_sha = hashlib.sha256(corr_bytes).hexdigest()

        corr_art = store.put(
            source_id="corridor_friction",
            content=corr_bytes,
            mime_type="text/csv",
            url="fixture:tests/fixtures/corridors/corridor_freight_benchmarks_2024_2026.csv",
        )

        existing_corr_sr = session.execute(
            text("SELECT source_record_id FROM meta.source_record WHERE source_id = 'corridor_friction' AND content_sha256 = :sha"),
            {"sha": corr_sha},
        ).scalar()

        if not existing_corr_sr:
            corr_sr_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO meta.source_record (
                        source_record_id, source_id, source_url, retrieved_via, object_key,
                        content_sha256, mime_type, http_status, fetched_at, extraction_status
                    ) VALUES (
                        :id, 'corridor_friction', 'fixture:tests/fixtures/corridors/corridor_freight_benchmarks_2024_2026.csv',
                        'fixture', :key, :sha, 'text/csv', NULL, NOW(), 'provisional'
                    )
                """),
                {"id": corr_sr_id, "key": corr_art.object_key, "sha": corr_sha},
            )
        else:
            corr_sr_id = str(existing_corr_sr)

        print(f"Corridor friction Bronze object: {corr_art.object_key} (SR: {corr_sr_id})")

        corr_records = parse_corridor_friction_csv(corr_bytes, source_record_id=corr_sr_id)
        corr_inserted = 0
        for r in corr_records:
            nat_key = f"macro:{r.indicator_code}:{r.period_start.isoformat()}"
            session.execute(
                text("""
                    INSERT INTO obs.macro_observation (
                        observation_id, source_record_id, natural_key, indicator_code,
                        indicator_name, frequency, unit, base_period, geo_scope,
                        period_start, period_end, published_at, first_available_at,
                        ingested_at, vintage, value, value_raw, observed_or_imputed,
                        extraction_method, evidence, confidence, review_status
                    ) VALUES (
                        gen_random_uuid(), :sr_id, :nat_key, :ind_code,
                        :ind_name, :freq, :unit, NULL, :geo_scope,
                        :p_start, :p_end, :pub_at, :pub_at,
                        NOW(), 'final', :val, :val_raw, 'imputed',
                        'calibration_fixture', :evidence, 0.80, 'provisional'
                    ) ON CONFLICT (natural_key) WHERE superseded_by IS NULL DO NOTHING;
                """),
                {
                    "sr_id": corr_sr_id,
                    "nat_key": nat_key,
                    "ind_code": r.indicator_code,
                    "ind_name": r.indicator_name,
                    "freq": r.frequency,
                    "unit": r.unit,
                    "geo_scope": r.geo_scope,
                    "p_start": r.period_start,
                    "p_end": r.period_end,
                    "pub_at": r.published_at or dt.datetime.combine(r.period_end, dt.time(0, 0), tzinfo=dt.UTC),
                    "val": r.value,
                    "val_raw": r.value_raw,
                    "evidence": json.dumps(r.evidence),
                },
            )
            corr_inserted += 1

        session.commit()
        print(f"Inserted/verified {corr_inserted} corridor friction records.")


if __name__ == "__main__":
    populate_alternative_data()
