"""Query and ambiguity contracts; mocks do not qualify SQL deployment."""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from ketrika.core.models.db import Location, Product, UnitConversion
from ketrika.normalize.price_references import resolve_location, resolve_product, unit_factor


def product():
    return Product(product_id=uuid4(), product_code="SYNTHETIC", base_unit="kg")


def test_product_source_alias_precedes_global_and_does_not_mutate():
    entity = product()
    session = MagicMock()
    session.execute.return_value.all.return_value = [(entity, Decimal(1), uuid4())]
    match = resolve_product(session, "RIZ", "synthetic_source")
    assert match.entity is entity and match.method == "exact_source_alias"
    assert session.execute.call_count == 1
    statement = session.execute.call_args.args[0]
    assert "synthetic_source" in statement.compile().params.values()
    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_ambiguous_source_alias_is_not_overridden_by_global_or_fuzzy():
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        (product(), Decimal(1), uuid4()),
        (product(), Decimal(1), uuid4()),
    ]
    assert resolve_product(session, "rice", "source") is None
    assert session.execute.call_count == 1


def test_global_alias_and_unique_pgtrgm_candidate():
    entity = product()
    for responses, method in [
        ([[], [(entity, Decimal(1), uuid4())]], "exact_global_alias"),
        ([[], [], [(entity, Decimal("0.86"), uuid4())]], "fuzzy_trigram"),
    ]:
        session = MagicMock()
        session.execute.return_value.all.side_effect = responses
        match = resolve_product(session, "rice", "source")
        assert match.entity is entity and match.method == method
        if method == "fuzzy_trigram":
            query = session.execute.call_args.args[0]
            sql = str(query.compile(dialect=postgresql.dialect()))
            assert "similarity" in sql
            assert Decimal("0.85") in query.compile().params.values()


def test_low_confidence_exact_alias_requires_review_not_fallback():
    session = MagicMock()
    session.execute.return_value.all.return_value = [(product(), Decimal("0.5"), uuid4())]
    assert resolve_product(session, "rice", "source") is None
    assert session.execute.call_count == 1


def test_multiple_aliases_of_one_product_are_not_ambiguous():
    entity = product()
    session = MagicMock()
    session.execute.return_value.all.return_value = [
        (entity, Decimal(1), uuid4()),
        (entity, Decimal("0.9"), uuid4()),
    ]
    match = resolve_product(session, "rice", "source")
    assert match.confidence == Decimal("0.9") and len(match.reference_ids) == 2


def test_location_pcode_respects_explicit_admin_level():
    entity = Location(location_id=uuid4(), pcode="SYNTHETIC-ONLY", admin_level=2)
    session = MagicMock()
    session.scalars.return_value.all.return_value = [entity]
    match = resolve_location(session, "synthetic-only", "source", admin_level=2)
    assert match.entity is entity and match.method == "exact_pcode"
    sql = str(session.scalars.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "admin_level" in sql and "pcode" in sql
    session.execute.assert_not_called()


def test_unknown_admin_level_does_not_permit_fuzzy_location():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    session.execute.return_value.all.return_value = []
    assert resolve_location(session, "unknown", "source") is None
    assert session.execute.call_count == 2
    assert all("similarity" not in str(call.args[0]) for call in session.execute.call_args_list)


def test_location_fuzzy_filters_level_and_rejects_ambiguity():
    session = MagicMock()
    session.scalars.return_value.all.return_value = []
    session.execute.return_value.all.side_effect = [
        [],
        [],
        [
            (Location(location_id=uuid4()), Decimal("0.9"), "alias1"),
            (Location(location_id=uuid4()), Decimal("0.9"), "alias2"),
        ],
    ]
    assert resolve_location(session, "unknown", "source", admin_level=2) is None
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "similarity" in sql and "admin_level" in sql


def test_unit_factor_specific_precedence_and_no_sac_assumption():
    session = MagicMock()
    product_id = uuid4()
    unit = UnitConversion(unit_code="kg", product_id=product_id, factor=Decimal(1))
    session.scalars.return_value.all.return_value = [unit]
    assert unit_factor(session, "KILO", product_id) is unit
    params = session.scalars.call_args.args[0].compile().params
    assert "kg" in params.values() and product_id in params.values()
    session.scalars.return_value.all.return_value = []
    assert unit_factor(session, "sac", product_id) is None
    assert all(
        "sac_50kg" not in call.args[0].compile().params.values()
        for call in session.scalars.call_args_list
    )
