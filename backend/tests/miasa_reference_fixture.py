"""Symbolic QA references, not official aliases, places or a geographic corpus."""

import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.core.models.db import Location, LocationAlias, Product, ProductAlias
from ketrika.core.qualification import require_synthetic_test_database
from ketrika.normalize.locations import normalize_location_string
from ketrika.normalize.products import normalize_product_string

SOURCE_ID = "miasa_odr"
ORIGIN = (
    "synthetic_miasa_fixture;verified=false;human_reviewed=false;"
    "proof=tests/golden/miasa_odr/odr_bulletin_850.expected.json"
)
PRODUCTS = {
    "Riz paddy": "RICE_PADDY",
    "Riz blanc local (Vary gasy)": "RICE_WHITE_LOCAL",
    "Riz blanc local (Makalioka)": "RICE_WHITE_LOCAL",
    "Riz blanc local (Tsipala)": "RICE_WHITE_LOCAL",
    "Riz importé (25% brisures)": "RICE_WHITE_IMPORTED",
}


def seed_miasa_normalization_references(session: Session) -> dict[str, int]:
    """Supply a test's declared lookup preconditions, never learn from its parser."""
    target = session.get_bind().engine.url
    require_synthetic_test_database(target.host, target.database)
    golden = Path(__file__).parent / "golden/miasa_odr/odr_bulletin_850.expected.json"
    fixture = json.loads(golden.read_text(encoding="utf-8"))
    assert fixture["metadata"]["human_reviewed"] is False
    records = fixture["records"]
    assert {row["product_raw"] for row in records} == set(PRODUCTS)
    counts = {"product_aliases": 0, "symbolic_locations": 0, "location_aliases": 0}
    for raw, code in PRODUCTS.items():
        product = session.scalar(select(Product).where(Product.product_code == code))
        assert product is not None
        normalized = normalize_product_string(raw)
        product_alias = session.scalar(
            select(ProductAlias).where(
                ProductAlias.alias_norm == normalized, ProductAlias.source_id == SOURCE_ID
            )
        )
        if product_alias is None:
            session.add(
                ProductAlias(
                    alias_id=uuid4(),
                    alias_norm=normalized,
                    alias_display=raw,
                    lang="fr",
                    product_id=product.product_id,
                    source_id=SOURCE_ID,
                    confidence=Decimal(1),
                    origin=ORIGIN,
                    human_reviewed=False,
                )
            )
            counts["product_aliases"] += 1
        else:
            assert product_alias.product_id == product.product_id and product_alias.origin == ORIGIN
    session.flush()
    places = {row["location_raw"] for row in records}
    for raw in sorted(places):
        normalized = normalize_location_string(raw)
        # Existing global aliases are already explicit fixtures' references.
        global_alias = session.scalar(
            select(LocationAlias).where(
                LocationAlias.alias_norm == normalized, LocationAlias.source_id.is_(None)
            )
        )
        if global_alias is not None:
            continue
        location_alias = session.scalar(
            select(LocationAlias).where(
                LocationAlias.alias_norm == normalized, LocationAlias.source_id == SOURCE_ID
            )
        )
        if location_alias is not None:
            location = session.get(Location, location_alias.location_id)
            assert location is not None and location.pcode is None
            assert location.boundary_version == "synthetic-fixture;verified=false"
            assert location_alias.origin == ORIGIN
            # Only this helper's earlier symbolic fixtures, never a P-coded
            # place or another origin. An actor does not define an admin level.
            location.admin_level = 9
            continue
        location = Location(
            location_id=uuid4(),
            pcode=None,
            name=raw,
            admin_level=9,
            boundary_version="synthetic-fixture;verified=false",
        )
        session.add(location)
        session.flush()
        session.add(
            LocationAlias(
                alias_norm=normalized,
                location_id=location.location_id,
                source_id=SOURCE_ID,
                confidence=Decimal(1),
                origin=ORIGIN,
            )
        )
        counts["symbolic_locations"] += 1
        counts["location_aliases"] += 1
    session.flush()
    return counts
