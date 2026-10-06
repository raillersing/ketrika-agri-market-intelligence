"""Unit and integration tests for normalization, supersession, and seeding (SPECS §7, §8.1, §13)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from ketrika.connectors.records import PriceRecord
from ketrika.core.db import transaction
from ketrika.core.models.db import (
    PriceObservation,
    ReviewItem,
    UserAccount,
)
from ketrika.normalize.loader import (
    normalize_and_load_price_records,
    seed_database,
)
from ketrika.normalize.locations import LocationResolver
from ketrika.normalize.products import ProductResolver
from ketrika.normalize.units import (
    UnitConverter,
    normalize_currency,
    parse_numeric_value,
)


class TestNumericAndCurrencyParsing:
    """Tests for SPECS §13 numeric and currency parsing rules."""

    @pytest.mark.parametrize(
        "missing_input", ["ND", "nd", "NA", "na", "-", "None", "null", "", " ", None]
    )
    def test_missing_values_return_none_and_never_zero(self, missing_input: str | None) -> None:
        """Acceptance: ND -> NULL + missing_code (jamais 0)."""
        val, missing_code = parse_numeric_value(missing_input)
        assert val is None, f"Expected None for {missing_input}, got {val}"
        assert val != 0, "Missing value must never be parsed as 0!"
        assert missing_code == "ND"

    def test_european_format_with_comma_decimal(self) -> None:
        """Acceptance: 2 850,50 -> 2850.50."""
        val, missing_code = parse_numeric_value("2 850,50")
        assert val == 2850.50
        assert missing_code is None

        # Format with dot thousand and comma decimal
        val2, _ = parse_numeric_value("2.850,50")
        assert val2 == 2850.50

    def test_standard_thousands_separator(self) -> None:
        """Parse integers with various thousands separators."""
        val, _ = parse_numeric_value("2 850")
        assert val == 2850.0

        val_attached, _ = parse_numeric_value("2850 Ar")
        assert val_attached == 2850.0

    def test_fmg_currency_division_by_five(self) -> None:
        """Acceptance: FMG divisé par 5 avec conversion_status = confident."""
        # 14 000 FMG = 2 800 MGA
        price_mga, status, conf = normalize_currency(14000.0, "FMG")
        assert price_mga == 2800.0
        assert status == "confident"
        assert conf == 0.95

        price_mga2, status2, conf2 = normalize_currency(15000.0, "Francs")
        assert price_mga2 == 3000.0
        assert status2 == "confident"

    def test_mga_currency_kept_as_is(self) -> None:
        """MGA / Ariary currency kept exact."""
        price_mga, status, conf = normalize_currency(3200.0, "MGA")
        assert price_mga == 3200.0
        assert status == "exact"
        assert conf == 1.0

    def test_unknown_currency_returns_uncertain(self) -> None:
        """Unknown or unconvertible currency returns uncertain."""
        price_mga, status, conf = normalize_currency(100.0, "EUR")
        assert price_mga is None
        assert status == "uncertain"
        assert conf == 0.5


class TestUnitConverter:
    """Tests for SPECS §7 unit conversions and confidence thresholds."""

    def test_standard_base_units(self) -> None:
        conv = UnitConverter()
        price, base_u, status, conf = conv.convert_price_to_base(3000.0, "kg")
        assert price == 3000.0
        assert base_u == "kg"
        assert status == "exact"
        assert conf == 1.0

    def test_kapoaka_conversion_high_confidence(self) -> None:
        """Kapoaka for RICE_WHITE_LOCAL has confidence 0.85 >= 0.8 -> price_mga_per_base computed."""
        conv = UnitConverter()
        # 1 kapoaka = 0.285 kg
        # Price per kg for 855 MGA / kapoaka = 855 / 0.285 = 3000.0
        price, base_u, status, conf = conv.convert_price_to_base(
            855.0, "kapoaka", product_code="RICE_WHITE_LOCAL"
        )
        assert price == 3000.0
        assert base_u == "kg"
        assert conf == 0.85
        assert status == "confident"

    def test_low_confidence_conversion_results_in_null_price_per_base(self) -> None:
        """Acceptance: conversion de confiance 0,5 -> price_mga_per_base IS NULL."""
        conv = UnitConverter()
        # Mock a low-confidence conversion
        mock_unit = conv.units.get("sac_50kg")
        assert mock_unit is not None
        # Manually test low confidence
        low_conf_unit = mock_unit.model_copy(update={"confidence": 0.5})
        conv.units["custom_low_conf"] = low_conf_unit

        price, base_u, status, conf = conv.convert_price_to_base(150000.0, "custom_low_conf")
        assert price is None, "When confidence < 0.8, price_mga_per_base MUST be NULL"
        assert status == "uncertain"
        assert conf == 0.5


class TestTaxonomyResolvers:
    """Tests for product and location entity resolution."""

    def test_product_resolver_exact_and_fuzzy(self) -> None:
        resolver = ProductResolver()
        # Canonical
        m1 = resolver.resolve("RICE_WHITE_LOCAL")
        assert m1 is not None
        assert m1.product_code == "RICE_WHITE_LOCAL"

        # French canonical
        m2 = resolver.resolve("Riz blanc local")
        assert m2 is not None
        assert m2.product_code == "RICE_WHITE_LOCAL"

        # Known alias
        m3 = resolver.resolve("vary gasy")
        assert m3 is not None
        assert m3.product_code == "RICE_WHITE_LOCAL"

        # Unknown product
        m_unknown = resolver.resolve("produit_totalement_inconnu_xyz_999")
        assert m_unknown is None

    def test_location_resolver_pcode_and_aliases(self) -> None:
        resolver = LocationResolver()
        # P-code
        m1 = resolver.resolve("MDG11")
        assert m1 is not None
        assert m1.pcode == "MDG11"
        assert m1.admin_level == 1

        # Region name
        m2 = resolver.resolve("Analamanga")
        assert m2 is not None
        assert m2.pcode == "MDG11"

        # Known alias
        m3 = resolver.resolve("Matsiatra Ambony")
        assert m3 is not None
        assert m3.pcode == "MDG21"

        # Unknown location
        m_unknown = resolver.resolve("lieu_imaginaire_narnia_999")
        assert m_unknown is None


@pytest.mark.integration
class TestLoaderIntegration:
    """Integration test verifying DB seeding, normalization, supersession, and review items."""

    def test_seed_database_is_complete_and_idempotent(self) -> None:
        with transaction() as session:
            stats = seed_database(session)
            assert stats["sources"] >= 10
            assert stats["products"] >= 15
            assert stats["locations"] >= 30
            assert stats["users"] == 2

            # Verify admin user
            admin = session.execute(
                select(UserAccount).where(UserAccount.email == "admin@ketrika.mg")
            ).scalar_one_or_none()
            assert admin is not None
            assert admin.role == "admin"
            assert admin.password_hash.startswith("$argon2")

            # Verify second run is idempotent
            stats2 = seed_database(session)
            assert stats2["products"] == stats["products"]

    def test_unknown_alias_creates_review_item(self) -> None:
        """Acceptance: alias inconnu -> review_item."""
        from ketrika.core.models.db import SourceRecord

        with transaction() as session:
            seed_database(session)

            dummy_src_rec_id = uuid.uuid4()
            src_rec = SourceRecord(
                source_record_id=dummy_src_rec_id,
                source_id="wfp_hdx_mdg",
                source_url="http://localhost:8000/wfp.csv",
                retrieved_via="direct",
                object_key=f"bronze/wfp_hdx_mdg/{dummy_src_rec_id}.csv",
                content_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                fetched_at=datetime.now(UTC),
                extraction_status="pending",
            )
            session.add(src_rec)
            session.flush()

            unique_suffix = uuid.uuid4().hex[:6]
            records = [
                PriceRecord(
                    product_raw=f"Farine de manioc mystère {unique_suffix}",
                    location_raw=f"Village Inconnu {unique_suffix}",
                    actor_level="retail",
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 1, 1),
                    price_raw="2 850,50",
                    unit_raw="kg",
                    currency_raw="MGA",
                    observed_or_imputed="observed",
                    extraction_method="deterministic",
                    confidence=0.9,
                )
            ]

            load_stats = normalize_and_load_price_records(
                session=session,
                records=records,
                source_id="wfp_hdx_mdg",
                source_record_id=dummy_src_rec_id,
            )

            assert load_stats["inserted"] == 1
            # 2 review items: 1 unknown_product, 1 unknown_location
            assert load_stats["review_items"] == 2

            # Verify review_item in ops.review_item
            review_items = (
                session.execute(
                    select(ReviewItem).where(ReviewItem.source_record_id == dummy_src_rec_id)
                )
                .scalars()
                .all()
            )
            assert len(review_items) == 2
            kinds = {r.kind for r in review_items}
            assert "unknown_product" in kinds
            assert "unknown_location" in kinds

            # Verify observation was inserted with NULL product_id and location_id
            obs = session.execute(
                select(PriceObservation).where(
                    PriceObservation.source_record_id == dummy_src_rec_id
                )
            ).scalar_one_or_none()
            assert obs is not None
            assert obs.product_id is None
            assert obs.location_id is None
            assert obs.price_value == 2850.50
            assert obs.price_mga_per_base == 2850.50
            assert obs.conversion_status == "exact"

            # 2. Idempotence test (run 2)
            load_stats_run2 = normalize_and_load_price_records(
                session=session,
                records=records,
                source_id="wfp_hdx_mdg",
                source_record_id=dummy_src_rec_id,
            )
            assert load_stats_run2["skipped"] == 1
            assert load_stats_run2["inserted"] == 0

            # 3. Supersession test (run 3 with modified price)
            records_modified = [
                PriceRecord(
                    product_raw=f"Farine de manioc mystère {unique_suffix}",
                    location_raw=f"Village Inconnu {unique_suffix}",
                    actor_level="retail",
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 1, 1),
                    price_raw="3 200,00",
                    unit_raw="kg",
                    currency_raw="MGA",
                    observed_or_imputed="observed",
                    extraction_method="deterministic",
                    confidence=0.9,
                )
            ]
            load_stats_run3 = normalize_and_load_price_records(
                session=session,
                records=records_modified,
                source_id="wfp_hdx_mdg",
                source_record_id=dummy_src_rec_id,
            )
            assert load_stats_run3["superseded"] == 1

            # Check that old observation now has superseded_by set
            session.refresh(obs)
            assert obs.superseded_by is not None

    def test_loader_main_seed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test loader CLI entrypoint."""
        from ketrika.normalize.loader import main

        monkeypatch.setattr("sys.argv", ["loader", "seed"])
        main()
        captured = capsys.readouterr()
        assert "Seed complete:" in captured.out
