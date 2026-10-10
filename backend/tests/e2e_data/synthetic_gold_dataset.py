"""Deterministic synthetic dataset for testing Gold analytical views (SPECS §15, §16, T5.1)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Numeric, inspect
from sqlalchemy.orm import Session

from ketrika.core.bronze import BronzeStore
from ketrika.core.models.db import (
    CpiObservation,
    Forecast,
    IngestionRun,
    Location,
    ModelRun,
    PriceObservation,
    Product,
    ProductionObservation,
    ReviewItem,
    Source,
    SourceRecord,
    StockObservation,
    TradeFlow,
    WeatherObservation,
)
from ketrika.core.qualification import require_synthetic_test_database
from tests.e2e_data.source_backed_synthetic import attach_new_synthetic_proof

# Deterministic UUIDs
PRODUCT_RICE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PRODUCT_MAIZE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
LOCATION_ANALAMANGA_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SOURCE_RECORD_ID_BASE = uuid.UUID("44444444-4444-4444-4444-444444444444")


def seed_synthetic_gold_data(session: Session) -> dict[str, int]:
    """Seed a clean, deterministic dataset for end-to-end SQL validation of all Gold views."""
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    reader = BronzeStore()
    if reader.bucket != "ketrika-qa-bronze":
        raise ValueError("synthetic_bronze_destination_refused")

    def add_observation(observation) -> None:
        # Explicit synthetic-generator inputs, never recovered real source values.
        for column in inspect(type(observation)).columns:
            value = getattr(observation, column.key)
            if isinstance(column.type, Numeric) and type(value) is float:
                setattr(observation, column.key, Decimal(str(value)))
        attach_new_synthetic_proof(session, observation, reader)
        session.add(observation)

    # 1. Products
    p_rice = session.get(Product, PRODUCT_RICE_ID)
    if not p_rice:
        p_rice = Product(
            product_id=PRODUCT_RICE_ID,
            product_code="rice_milled",
            canonical_name_fr="Riz blanc",
            category="cereal",
            base_unit="kg",
            hs6_codes=["100630"],
            faostat_item_codes=["2805"],
            verified=True,
        )
        session.add(p_rice)

    p_maize = session.get(Product, PRODUCT_MAIZE_ID)
    if not p_maize:
        p_maize = Product(
            product_id=PRODUCT_MAIZE_ID,
            product_code="maize",
            canonical_name_fr="Maïs grain",
            category="cereal",
            base_unit="kg",
            hs6_codes=["100590"],
            faostat_item_codes=["56"],
            verified=True,
        )
        session.add(p_maize)

    extra_products_spec = [
        (
            "cassava_fresh",
            "Manioc frais",
            "tuber",
            "kg",
            ["071410"],
            ["125"],
            uuid.UUID("55555555-5555-5555-5555-555555555555"),
        ),
        (
            "oil_edible",
            "Huile alimentaire",
            "oil",
            "l",
            ["151219"],
            ["257"],
            uuid.UUID("66666666-6666-6666-6666-666666666666"),
        ),
        (
            "sugar",
            "Sucre roux",
            "sugar",
            "kg",
            ["170114"],
            ["158"],
            uuid.UUID("77777777-7777-7777-7777-777777777777"),
        ),
        (
            "dry_beans",
            "Haricots secs",
            "pulse_oilseed",
            "kg",
            ["071333"],
            ["176"],
            uuid.UUID("88888888-8888-8888-8888-888888888888"),
        ),
        (
            "rice_imported",
            "Riz importé",
            "cereal",
            "kg",
            ["100630"],
            ["2805"],
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
        ),
        (
            "flour_wheat",
            "Farine de blé",
            "cereal",
            "kg",
            ["110100"],
            ["16"],
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        ),
        (
            "cassava_dry",
            "Manioc sec (Cossettes)",
            "tuber",
            "kg",
            ["071410"],
            ["125"],
            uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        ),
    ]
    for p_code, p_name, p_cat, p_unit, hs6, fao, p_uuid in extra_products_spec:
        p_obj = session.get(Product, p_uuid)
        if not p_obj:
            p_obj = Product(
                product_id=p_uuid,
                product_code=p_code,
                canonical_name_fr=p_name,
                category=p_cat,
                base_unit=p_unit,
                hs6_codes=hs6,
                faostat_item_codes=fao,
                verified=True,
            )
            session.add(p_obj)

    # 2. Location
    loc = session.get(Location, LOCATION_ANALAMANGA_ID)
    if not loc:
        loc = Location(
            location_id=LOCATION_ANALAMANGA_ID,
            admin_level=1,
            pcode="MG11",
            name="Analamanga",
            boundary_version="2024.1",
        )
        session.add(loc)

    extra_locs_spec = [
        ("MG12", "Vakinankaratra", uuid.UUID("33333333-3333-3333-3333-333333333312")),
        ("MG31", "Atsinanana", uuid.UUID("33333333-3333-3333-3333-333333333331")),
        ("MG41", "Boeny", uuid.UUID("33333333-3333-3333-3333-333333333341")),
        ("MG51", "Atsimo-Andrefana", uuid.UUID("33333333-3333-3333-3333-333333333351")),
    ]
    for l_pcode, l_name, l_uuid in extra_locs_spec:
        l_obj = session.get(Location, l_uuid)
        if not l_obj:
            l_obj = Location(
                location_id=l_uuid,
                admin_level=1,
                pcode=l_pcode,
                name=l_name,
                boundary_version="2024.1",
            )
            session.add(l_obj)

    # 3. Sources
    sources_spec = [
        ("miasa_odr", "ODR", "P0", 28),
        ("wfp_hdx_mdg", "WFP", "P1", 45),
        ("wb_rtfp_mdg", "WB RTFP", "P1", 30),
        ("mincc_ppn", "MinCC", "P1", 28),
        ("douanes_stats", "Douanes", "P1", 62),
        ("faostat", "FAOSTAT", "P2", 365),
        ("nasa_power", "NASA POWER", "P1", 60),
        ("instat_nipc", "INSTAT NIPC", "P1", 62),
    ]
    for s_id, s_name, prio, sla in sources_spec:
        s = session.get(Source, s_id)
        if not s:
            s = Source(
                source_id=s_id,
                spec={
                    "name": s_name,
                    "priority": prio,
                    "freshness_sla_days": sla,
                    "authenticity": "synthetic",
                    "verified": False,
                },
                status="active",
            )
            session.add(s)
        else:
            s.spec = {
                "name": s_name,
                "priority": prio,
                "freshness_sla_days": sla,
                "authenticity": "synthetic",
                "verified": False,
            }

    session.flush()

    # 4. Source Records
    def make_src_rec(s_id: str, offset: int = 0) -> SourceRecord:
        rec_id = uuid.uuid5(SOURCE_RECORD_ID_BASE, f"synthetic-generator-v2:{s_id}_{offset}")
        rec = session.get(SourceRecord, rec_id)
        if not rec:
            artifact = reader.put(
                source_id=s_id,
                content=json.dumps(
                    {
                        "generator_source": s_id,
                        "offset": offset,
                        "authenticity": "synthetic",
                        "verified": False,
                    },
                    sort_keys=True,
                ).encode(),
                mime_type="application/json",
                url="https://example.invalid/synthetic-gold-generator",
                retrieved_via="manual_upload",
                fetched_at=datetime(2024, 3, 1, 10, 0, tzinfo=UTC),
                http_status=0,
                http_headers={"x-ketrika-dataset": "synthetic; verified=false"},
            )
            rec = SourceRecord(
                source_record_id=rec_id,
                source_id=s_id,
                source_url="https://example.invalid/synthetic-gold-generator",
                retrieved_via="manual_upload",
                object_key=artifact.object_key,
                content_sha256=artifact.content_sha256,
                mime_type="application/json",
                fetched_at=datetime(2024, 3, 1, 10, 0, tzinfo=UTC),
                parser_version="1.0.0",
                extraction_status="parsed",
            )
            session.add(rec)
            session.flush()
        return rec

    src_rec_odr = make_src_rec("miasa_odr")
    src_rec_wfp = make_src_rec("wfp_hdx_mdg")
    src_rec_wb = make_src_rec("wb_rtfp_mdg")
    src_rec_mincc = make_src_rec("mincc_ppn")
    src_rec_douanes = make_src_rec("douanes_stats")
    src_rec_fao = make_src_rec("faostat")
    src_rec_nasa = make_src_rec("nasa_power")
    src_rec_cpi = make_src_rec("instat_nipc")

    counts = {
        "price": 0,
        "stock": 0,
        "trade": 0,
        "production": 0,
        "weather": 0,
        "cpi": 0,
        "forecast": 0,
    }

    # 5. Price observations:
    # A) Monthly historical series (13 consecutive months: 2023-01 to 2024-01) for rice in Analamanga (retail)
    # Price values: 2500 in 2023-01, increasing to 3000 in 2024-01
    prices_history = [
        (2023, 1, 2500.0),
        (2023, 2, 2550.0),
        (2023, 3, 2600.0),
        (2023, 4, 2650.0),
        (2023, 5, 2700.0),
        (2023, 6, 2750.0),
        (2023, 7, 2800.0),
        (2023, 8, 2820.0),
        (2023, 9, 2850.0),
        (2023, 10, 2900.0),
        (2023, 11, 2920.0),
        (2023, 12, 2950.0),
        (2024, 1, 3000.0),
    ]
    for y, m, pval in prices_history:
        p_date_start = date(y, m, 1)
        p_date_end = date(y, m, 28)
        p_obs = PriceObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"hist_{y}_{m}"),
            source_record_id=src_rec_odr.source_record_id,
            natural_key=f"nk_hist_{y}_{m}",
            product_raw="Riz blanc",
            product_id=PRODUCT_RICE_ID,
            location_raw="Analamanga",
            location_id=LOCATION_ANALAMANGA_ID,
            actor_level="retail",
            period_start=p_date_start,
            period_end=p_date_end,
            price_raw=str(pval),
            price_value=pval,
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=pval,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed="observed",
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        add_observation(p_obs)
        counts["price"] += 1

    # B) Priority arbitration test records for Month 2024-02:
    # 3 concurrent sources for (rice, Analamanga, retail, 2024-02):
    # - ODR: Priority P0, observed, price = 3100.0
    # - WFP: Priority P1, observed, price = 3200.0
    # - WB RTFP: Priority P1, imputed, price = 3150.0
    for s_name, rec, _prio_kind, obs_kind, price in [
        ("odr", src_rec_odr, "P0", "observed", 3100.0),
        ("wfp", src_rec_wfp, "P1", "observed", 3200.0),
        ("wb", src_rec_wb, "P1", "imputed", 3150.0),
    ]:
        p_arb = PriceObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"arb_2024_02_{s_name}"),
            source_record_id=rec.source_record_id,
            natural_key=f"nk_arb_2024_02_{s_name}",
            product_raw="Riz blanc",
            product_id=PRODUCT_RICE_ID,
            location_raw="Analamanga",
            location_id=LOCATION_ANALAMANGA_ID,
            actor_level="retail",
            period_start=date(2024, 2, 1),
            period_end=date(2024, 2, 29),
            price_raw=str(price),
            price_value=price,
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=price,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed=obs_kind,
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        add_observation(p_arb)
        counts["price"] += 1

    # C) Priority test for Month 2024-03:
    # Only P1 observed (WFP=3300.0) and P1 imputed (WB=3250.0) -> P1 observed MUST win!
    for s_name, rec, obs_kind, price in [
        ("wfp", src_rec_wfp, "observed", 3300.0),
        ("wb", src_rec_wb, "imputed", 3250.0),
    ]:
        p_arb = PriceObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"arb_2024_03_{s_name}"),
            source_record_id=rec.source_record_id,
            natural_key=f"nk_arb_2024_03_{s_name}",
            product_raw="Riz blanc",
            product_id=PRODUCT_RICE_ID,
            location_raw="Analamanga",
            location_id=LOCATION_ANALAMANGA_ID,
            actor_level="retail",
            period_start=date(2024, 3, 1),
            period_end=date(2024, 3, 31),
            price_raw=str(price),
            price_value=price,
            currency_raw="MGA",
            unit_raw="kg",
            price_mga_per_base=price,
            base_unit="kg",
            conversion_status="exact",
            observed_or_imputed=obs_kind,
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        add_observation(p_arb)
        counts["price"] += 1

    # D) Additional 12 distinct commodity and regional series for ML forecasting (SPECS §17)
    # Each series covers 18 consecutive months (2022-10 to 2024-03)
    extra_series_configs = [
        (
            "maize",
            PRODUCT_MAIZE_ID,
            "Maïs grain",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            1600.0,
            15.0,
        ),
        (
            "maize",
            PRODUCT_MAIZE_ID,
            "Maïs grain",
            "Vakinankaratra",
            uuid.UUID("33333333-3333-3333-3333-333333333312"),
            "wholesale",
            1450.0,
            12.0,
        ),
        (
            "cassava_fresh",
            uuid.UUID("55555555-5555-5555-5555-555555555555"),
            "Manioc frais",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            900.0,
            8.0,
        ),
        (
            "cassava_fresh",
            uuid.UUID("55555555-5555-5555-5555-555555555555"),
            "Manioc frais",
            "Atsimo-Andrefana",
            uuid.UUID("33333333-3333-3333-3333-333333333351"),
            "retail",
            850.0,
            7.0,
        ),
        (
            "oil_edible",
            uuid.UUID("66666666-6666-6666-6666-666666666666"),
            "Huile alimentaire",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            7500.0,
            40.0,
        ),
        (
            "oil_edible",
            uuid.UUID("66666666-6666-6666-6666-666666666666"),
            "Huile alimentaire",
            "Atsinanana",
            uuid.UUID("33333333-3333-3333-3333-333333333331"),
            "retail",
            7200.0,
            35.0,
        ),
        (
            "sugar",
            uuid.UUID("77777777-7777-7777-7777-777777777777"),
            "Sucre roux",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            4200.0,
            25.0,
        ),
        (
            "dry_beans",
            uuid.UUID("88888888-8888-8888-8888-888888888888"),
            "Haricots secs",
            "Vakinankaratra",
            uuid.UUID("33333333-3333-3333-3333-333333333312"),
            "retail",
            4800.0,
            30.0,
        ),
        (
            "rice_imported",
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
            "Riz importé",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            3200.0,
            20.0,
        ),
        (
            "rice_imported",
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
            "Riz importé",
            "Atsinanana",
            uuid.UUID("33333333-3333-3333-3333-333333333331"),
            "retail",
            3100.0,
            18.0,
        ),
        (
            "flour_wheat",
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            "Farine de blé",
            "Analamanga",
            LOCATION_ANALAMANGA_ID,
            "retail",
            3800.0,
            20.0,
        ),
        (
            "cassava_dry",
            uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            "Manioc sec (Cossettes)",
            "Atsimo-Andrefana",
            uuid.UUID("33333333-3333-3333-3333-333333333351"),
            "retail",
            1200.0,
            10.0,
        ),
    ]

    months_18 = [
        (2022, 10),
        (2022, 11),
        (2022, 12),
        (2023, 1),
        (2023, 2),
        (2023, 3),
        (2023, 4),
        (2023, 5),
        (2023, 6),
        (2023, 7),
        (2023, 8),
        (2023, 9),
        (2023, 10),
        (2023, 11),
        (2023, 12),
        (2024, 1),
        (2024, 2),
        (2024, 3),
    ]

    import math

    for p_code, p_uuid, p_raw, loc_raw, loc_uuid, act_lvl, base_p, slope in extra_series_configs:
        unit_str = "l" if p_code == "oil_edible" else "kg"
        for idx_m, (y, m) in enumerate(months_18):
            # Calculate price with trend + seasonal oscillation
            seasonal = math.sin(m * math.pi / 6.0) * (base_p * 0.03)
            pval = round(base_p + (idx_m * slope) + seasonal, 2)
            p_start = date(y, m, 1)
            p_end = date(y, m, 28)
            p_extra = PriceObservation(
                observation_id=uuid.uuid5(
                    SOURCE_RECORD_ID_BASE, f"extra_{p_code}_{loc_raw}_{act_lvl}_{y}_{m}"
                ),
                source_record_id=src_rec_mincc.source_record_id,
                natural_key=f"nk_extra_{p_code}_{loc_raw}_{act_lvl}_{y}_{m}",
                product_raw=p_raw,
                product_id=p_uuid,
                location_raw=loc_raw,
                location_id=loc_uuid,
                actor_level=act_lvl,
                period_start=p_start,
                period_end=p_end,
                price_raw=str(pval),
                price_value=pval,
                currency_raw="MGA",
                unit_raw=unit_str,
                price_mga_per_base=pval,
                base_unit=unit_str,
                conversion_status="exact",
                observed_or_imputed="observed",
                extraction_method="deterministic",
                confidence=1.0,
                review_status="accepted",
                superseded_by=None,
            )
            add_observation(p_extra)
            counts["price"] += 1

    # 6. Stock observations (3 sequential observations showing improving trend)
    stocks_seq = [
        (date(2024, 1, 1), date(2024, 1, 15), 10.0, "tight"),
        (date(2024, 1, 16), date(2024, 1, 31), 15.0, "tight"),
        (date(2024, 2, 1), date(2024, 2, 15), 25.0, "sufficient"),
    ]
    for idx, (p_start, p_end, cov, status) in enumerate(stocks_seq, start=1):
        s_obs = StockObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"stock_{idx}"),
            source_record_id=src_rec_mincc.source_record_id,
            natural_key=f"nk_stock_{idx}",
            product_raw="Riz blanc",
            product_id=PRODUCT_RICE_ID,
            location_raw="Analamanga",
            location_id=LOCATION_ANALAMANGA_ID,
            period_start=p_start,
            period_end=p_end,
            published_at=datetime(2024, 2, 16, 8, 0, tzinfo=UTC),
            quantity_raw=str(cov * 100.0),
            quantity_value=cov * 100.0,
            unit_raw="tonne",
            quantity_base=cov * 100.0,
            base_unit="tonne",
            stock_status=status,
            coverage_days=cov,
            extraction_method="deterministic",
            confidence=1.0,
            review_status="accepted",
            superseded_by=None,
        )
        add_observation(s_obs)
        counts["stock"] += 1

    # 7. Trade flows for 2024-01:
    # - Rice import: 10,000 tonnes (10,000,000 kg), 30,000,000,000 MGA, 6,666,666 USD
    # - Rice export: 1,000 tonnes (1,000,000 kg), 3,500,000,000 MGA, 777,777 USD
    tf_import = TradeFlow(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "tf_import_rice"),
        source_record_id=src_rec_douanes.source_record_id,
        natural_key="nk_tf_import_rice",
        flow="import",
        hs_code="10063000",
        product_raw="Riz semi-blanchi ou blanchi",
        product_id=PRODUCT_RICE_ID,
        partner_raw="Inde",
        partner_iso3="IND",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        value_mga=30000000000.0,
        value_usd=6666666.0,
        weight_kg=10000000.0,
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    add_observation(tf_import)
    counts["trade"] += 1

    tf_export = TradeFlow(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "tf_export_rice"),
        source_record_id=src_rec_douanes.source_record_id,
        natural_key="nk_tf_export_rice",
        flow="export",
        hs_code="10063000",
        product_raw="Riz semi-blanchi ou blanchi",
        product_id=PRODUCT_RICE_ID,
        partner_raw="Maurice",
        partner_iso3="MUS",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
        value_mga=3500000000.0,
        value_usd=777777.0,
        weight_kg=1000000.0,
        extraction_method="deterministic",
        confidence=1.0,
        review_status="accepted",
        superseded_by=None,
    )
    add_observation(tf_export)
    counts["trade"] += 1

    # 8. Production observation:
    # 50,000 tonnes rice production for 2024 in Madagascar
    prod_obs = ProductionObservation(
        observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, "prod_rice_2024"),
        source_record_id=src_rec_fao.source_record_id,
        natural_key="nk_prod_rice_2024",
        product_raw="Riz, paddy",
        product_id=PRODUCT_RICE_ID,
        location_id=LOCATION_ANALAMANGA_ID,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),
        element="production_t",
        value=50000.0,
        unit_raw="tonnes",
        observed_or_imputed="observed",
        extraction_method="deterministic",
        confidence=1.0,
        superseded_by=None,
    )
    add_observation(prod_obs)
    counts["production"] += 1

    # 9. Weather observations:
    # 2 months of weather (2024-01 and 2024-02) for Analamanga
    weather_data = [
        (date(2024, 1, 15), "precip_mm", 120.0),
        (date(2024, 1, 15), "t2m_max_c", 28.5),
        (date(2024, 1, 15), "t2m_min_c", 18.0),
        (date(2024, 1, 15), "rh2m_pct", 75.0),
        (date(2024, 2, 15), "precip_mm", 150.0),
        (date(2024, 2, 15), "t2m_max_c", 27.8),
        (date(2024, 2, 15), "t2m_min_c", 17.5),
        (date(2024, 2, 15), "rh2m_pct", 80.0),
    ]
    for wdate, var, val in weather_data:
        w_obs = WeatherObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"w_{wdate}_{var}"),
            source_record_id=src_rec_nasa.source_record_id,
            location_id=LOCATION_ANALAMANGA_ID,
            date=wdate,
            location_raw="Analamanga",
            variable=var,
            value=val,
            method="point_centroid",
            provider="nasa_power",
        )
        add_observation(w_obs)
        counts["weather"] += 1

    # 10. CPI observations:
    # 2 months of CPI (2024-01=100.0, 2024-02=105.0 -> +5.0% m/m)
    cpi_data = [
        (date(2024, 1, 1), date(2024, 1, 31), 100.0),
        (date(2024, 2, 1), date(2024, 2, 29), 105.0),
    ]
    for p_start, p_end, idx_val in cpi_data:
        c_obs = CpiObservation(
            observation_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"cpi_{p_start}"),
            source_record_id=src_rec_cpi.source_record_id,
            natural_key=f"nk_cpi_{p_start}",
            series_code="cpi_food",
            series_label="Indice des prix alimentaires",
            geo_scope="national",
            period_start=p_start,
            period_end=p_end,
            index_value=idx_val,
            base_period="2016=100",
            extraction_method="deterministic",
            confidence=1.0,
            superseded_by=None,
        )
        add_observation(c_obs)
        counts["cpi"] += 1

    # 11. ML Model Run and Forecast
    run_id = uuid.uuid5(SOURCE_RECORD_ID_BASE, "ml_run_1")
    m_run = session.get(ModelRun, run_id)
    if not m_run:
        m_run = ModelRun(
            model_run_id=run_id,
            task="price_forecast",
            model_name="AutoARIMA",
            model_version="1.0.0",
            data_cutoff=date(2024, 3, 1),
            trained_at=datetime(2024, 3, 15, 12, 0, tzinfo=UTC),
            params={"seasonal": True},
            metrics={"wape": 0.045},
        )
        session.add(m_run)
        session.flush()

    for h, tgt, p10, p50, p90 in [
        (1, date(2024, 4, 1), 3200.0, 3350.0, 3500.0),
        (2, date(2024, 5, 1), 3250.0, 3400.0, 3600.0),
    ]:
        fc = Forecast(
            forecast_id=uuid.uuid5(SOURCE_RECORD_ID_BASE, f"fc_{h}"),
            model_run_id=run_id,
            series_key="rice_milled|MG11|retail",
            product_id=PRODUCT_RICE_ID,
            location_id=LOCATION_ANALAMANGA_ID,
            actor_level="retail",
            target_period=tgt,
            horizon=h,
            p10=p10,
            p50=p50,
            p90=p90,
            generated_at=datetime(2024, 3, 15, 12, 30, tzinfo=UTC),
        )
        session.add(fc)
        counts["forecast"] += 1

    # 12. IngestionRun & ReviewItems for source_health testing
    ir_id = uuid.uuid5(SOURCE_RECORD_ID_BASE, "ir_odr")
    ir_odr = session.get(IngestionRun, ir_id)
    if not ir_odr:
        ir_odr = IngestionRun(
            run_id=ir_id,
            source_id="miasa_odr",
            started_at=datetime(2024, 3, 1, 9, 0, tzinfo=UTC),
            finished_at=datetime(2024, 3, 1, 9, 5, tzinfo=UTC),
            status="success",
            n_fetched=1,
            n_new_artifacts=1,
            n_records=20,
            n_rejected=0,
            n_review=0,
        )
        session.add(ir_odr)

    rev_id = uuid.uuid5(SOURCE_RECORD_ID_BASE, "rev_1")
    rev_item = session.get(ReviewItem, rev_id)
    if not rev_item:
        rev_item = ReviewItem(
            review_id=rev_id,
            kind="extraction_conflict",
            source_record_id=src_rec_odr.source_record_id,
            payload={"reason": "test"},
            status="open",
        )
        session.add(rev_item)

    session.flush()
    return counts
