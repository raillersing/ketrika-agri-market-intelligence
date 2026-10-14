"""Database seeding, batch normalization and Silver loading engine (SPECS §8, §13, §14)."""

from __future__ import annotations

import argparse
import functools
import sys
import uuid
from copy import deepcopy

from argon2 import PasswordHasher
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ketrika.connectors.records import PriceRecord
from ketrika.core.db import transaction
from ketrika.core.geo import load_geographic_entities, load_location_aliases
from ketrika.core.models.db import (
    Location,
    LocationAlias,
    PriceObservation,
    Product,
    ProductAlias,
    UnitConversion,
    UserAccount,
)
from ketrika.core.registry import sync_sources_to_db
from ketrika.core.taxonomy import (
    load_aliases,
    load_products,
    normalize_string,
)
from ketrika.core.units import load_units
from ketrika.normalize.locations import (
    LocationResolver,
    normalize_location_string,
    parse_admin_level,
)
from ketrika.normalize.price_bridge import identity_evidence, resolve_price_identity
from ketrika.normalize.products import ProductResolver
from ketrika.normalize.supersede import create_review_item, load_observation_with_supersession
from ketrika.normalize.units import UnitConverter, normalize_currency, parse_numeric_value


def seed_products(session: Session) -> dict[str, uuid.UUID]:
    """Seed ref.product and ref.product_alias from taxonomy."""
    products = load_products()
    aliases = load_aliases()

    product_map: dict[str, uuid.UUID] = {}

    for p in products:
        existing = session.execute(
            select(Product).where(Product.product_code == p.product_code)
        ).scalar_one_or_none()

        if existing is None:
            new_id = uuid.uuid4()
            prod = Product(
                product_id=new_id,
                product_code=p.product_code,
                canonical_name_fr=p.canonical_name_fr,
                category=p.category,
                base_unit=p.base_unit,
                hs6_codes=p.hs6_codes,
                faostat_item_codes=[str(c) for c in p.faostat_item_codes],
                verified=p.verified,
            )
            session.add(prod)
            product_map[p.product_code] = new_id
        else:
            product_map[p.product_code] = existing.product_id

    session.flush()

    for a in aliases:
        target_prod_id = product_map.get(a.product_code)
        if not target_prod_id:
            continue

        norm_alias = normalize_string(a.alias)
        stmt = select(ProductAlias).where(
            ProductAlias.alias_norm == norm_alias,
            ProductAlias.source_id.is_(None),
        )
        existing_alias = session.execute(stmt).scalar_one_or_none()

        if existing_alias is None:
            alias_row = ProductAlias(
                alias_id=uuid.uuid4(),
                alias_norm=norm_alias,
                alias_display=a.alias,
                lang=a.lang,
                product_id=target_prod_id,
                source_id=None,
                confidence=a.confidence,
                origin="seed",
                human_reviewed=False,
            )
            session.add(alias_row)

    session.flush()
    return product_map


def seed_units(session: Session, product_map: dict[str, uuid.UUID]) -> None:
    """Seed ref.unit_conversion from taxonomy/units.yaml."""
    units = load_units()

    for u in units:
        # 1. Base / generic conversion
        if u.factor is not None and u.target_unit is not None:
            stmt = select(UnitConversion).where(
                UnitConversion.unit_code == u.unit_code,
                UnitConversion.product_id.is_(None),
            )
            existing = session.execute(stmt).scalar_one_or_none()
            if existing is None:
                row = UnitConversion(
                    unit_code=u.unit_code,
                    product_id=None,
                    base_unit=u.target_unit,
                    factor=u.factor,
                    confidence=u.confidence,
                    evidence=u.evidence or u.name_fr,
                )
                session.add(row)

        # 2. Product-specific conversions
        if u.product_specific:
            for p_code, spec in u.product_specific.items():
                p_id = product_map.get(p_code)
                if not p_id:
                    continue
                stmt = select(UnitConversion).where(
                    UnitConversion.unit_code == u.unit_code,
                    UnitConversion.product_id == p_id,
                )
                existing = session.execute(stmt).scalar_one_or_none()
                if existing is None:
                    row = UnitConversion(
                        unit_code=u.unit_code,
                        product_id=p_id,
                        base_unit=spec.target_unit,
                        factor=spec.factor,
                        confidence=spec.confidence,
                        evidence=spec.evidence or u.evidence,
                    )
                    session.add(row)

    session.flush()


def seed_locations(session: Session) -> dict[str, uuid.UUID]:
    """Seed ref.location and ref.location_alias from geo/processed and taxonomy."""
    raw_entities = []
    for lvl in ["admin0", "admin1", "admin2", "admin3"]:
        try:
            raw_entities.extend(load_geographic_entities(lvl))
        except Exception:
            pass

    location_map: dict[str, uuid.UUID] = {}
    parent_pcode_map: dict[str, str] = {}

    # Pass 1: Insert locations without parent_id
    for ent in raw_entities:
        existing = session.execute(
            select(Location).where(Location.pcode == ent.pcode)
        ).scalar_one_or_none()

        if existing is None:
            loc_id = uuid.uuid4()
            lvl_num = parse_admin_level(ent.admin_level)
            loc = Location(
                location_id=loc_id,
                admin_level=lvl_num,
                pcode=ent.pcode,
                name=ent.name_fr,
                parent_id=None,
                boundary_version="2024.1",
            )
            session.add(loc)
            location_map[ent.pcode] = loc_id
        else:
            location_map[ent.pcode] = existing.location_id

        if ent.parent_pcode:
            parent_pcode_map[ent.pcode] = ent.parent_pcode

    session.flush()

    # Pass 2: Link parents
    for pcode, parent_pcode in parent_pcode_map.items():
        child_id = location_map.get(pcode)
        parent_id = location_map.get(parent_pcode)
        if child_id and parent_id:
            upd = (
                update(Location).where(Location.location_id == child_id).values(parent_id=parent_id)
            )
            session.execute(upd)

    session.flush()

    # Pass 3: Seed location aliases
    aliases = load_location_aliases()
    for a in aliases:
        target_loc_id = location_map.get(a.pcode)
        if not target_loc_id:
            continue

        norm_alias = normalize_location_string(a.alias)
        stmt = select(LocationAlias).where(
            LocationAlias.alias_norm == norm_alias,
            LocationAlias.source_id.is_(None),
        )
        existing_alias = session.execute(stmt).scalar_one_or_none()

        if existing_alias is None:
            alias_row = LocationAlias(
                alias_norm=norm_alias,
                location_id=target_loc_id,
                source_id=None,
                confidence=a.confidence,
                origin="seed",
            )
            session.add(alias_row)

    session.flush()
    return location_map


def seed_demo_users(session: Session) -> None:
    """Seed demo accounts admin@ketrika.mg and demo@ketrika.mg with Argon2."""
    ph = PasswordHasher()

    users_to_seed = [
        ("admin@ketrika.mg", "AdminKetrika2026!", "admin"),
        ("demo@ketrika.mg", "DemoKetrika2026!", "client"),
    ]

    for email, raw_password, role in users_to_seed:
        existing = session.execute(
            select(UserAccount).where(UserAccount.email == email)
        ).scalar_one_or_none()

        if existing is None:
            pwd_hash = ph.hash(raw_password)
            user = UserAccount(
                user_id=uuid.uuid4(),
                email=email,
                password_hash=pwd_hash,
                role=role,
                disabled=False,
            )
            session.add(user)

    session.flush()


def seed_database(session: Session) -> dict[str, int]:
    """Execute complete database seed process (registries, taxonomies, geo, demo users)."""
    # 1. Sources
    n_sources = sync_sources_to_db(session)

    # 2. Products
    prod_map = seed_products(session)

    # 3. Units
    seed_units(session, prod_map)

    # 4. Locations
    loc_map = seed_locations(session)

    # 5. Demo users
    seed_demo_users(session)

    return {
        "sources": n_sources,
        "products": len(prod_map),
        "locations": len(loc_map),
        "users": 2,
    }


def _build_price_obs(
    obs_id: uuid.UUID,
    rec: PriceRecord,
    source_id: str,
    source_record_id: uuid.UUID,
    nk: str,
    product_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    price_val: float | None,
    price_mga_per_base: float | None,
    base_unit: str | None,
    conversion_status: str,
    missing_code: str | None,
    overall_conf: float,
) -> PriceObservation:
    return PriceObservation(
        observation_id=obs_id,
        source_record_id=source_record_id,
        natural_key=nk,
        product_raw=rec.product_raw,
        product_id=product_id,
        variety=getattr(rec, "variety", None),
        quality_grade=getattr(rec, "quality_grade", None),
        location_raw=rec.location_raw,
        location_id=location_id,
        market_name=getattr(rec, "market_name", None),
        actor_level=rec.actor_level,
        period_start=rec.period_start,
        period_end=rec.period_end,
        published_at=getattr(rec, "published_at", None),
        price_raw=rec.price_raw,
        price_value=price_val,
        currency_raw=rec.currency_raw,
        unit_raw=rec.unit_raw,
        package_quantity=getattr(rec, "package_quantity", None),
        package_unit=getattr(rec, "package_unit", None),
        price_mga_per_base=price_mga_per_base,
        base_unit=base_unit,
        conversion_status=conversion_status,
        observed_or_imputed=rec.observed_or_imputed,
        missing_code=missing_code,
        extraction_method=rec.extraction_method,
        evidence=deepcopy(rec.evidence) | {"price_identity": identity_evidence(rec, source_id)},
        confidence=overall_conf,
        review_status="accepted",
        superseded_by=None,
    )


def normalize_and_load_price_records(
    session: Session,
    records: list[PriceRecord],
    source_id: str,
    source_record_id: uuid.UUID,
    product_resolver: ProductResolver | None = None,
    location_resolver: LocationResolver | None = None,
    unit_converter: UnitConverter | None = None,
) -> dict[str, int]:
    """Normalize raw PriceRecords and load into obs.price_observation with supersession."""
    p_res = product_resolver or ProductResolver()
    l_res = location_resolver or LocationResolver()
    u_conv = unit_converter or UnitConverter()

    stats = {"inserted": 0, "superseded": 0, "skipped": 0, "review_items": 0, "rejected": 0}

    # Fetch product_id map from database
    db_prods = session.execute(select(Product.product_code, Product.product_id)).all()
    prod_id_map = dict(db_prods)

    # Fetch location_id map from database
    db_locs = session.execute(select(Location.pcode, Location.location_id)).all()
    loc_id_map = {pcode: loc_id for pcode, loc_id in db_locs if pcode}

    for rec in records:
        resolution = resolve_price_identity(session, rec, source_id, source_record_id)
        if resolution.review_id is not None:
            stats["rejected"] += 1
            stats["review_items"] += resolution.reviews_created
            continue
        # 1. Parse numeric value and missing code
        price_val, missing_code = parse_numeric_value(rec.price_raw)

        # 2. Resolve product
        p_match = p_res.resolve(rec.product_raw, source_id=source_id)
        product_id: uuid.UUID | None = None
        resolved_pcode: str | None = None

        if p_match:
            resolved_pcode = p_match.product_code
            product_id = prod_id_map.get(p_match.product_code)
        else:
            # Create review_item for unknown product
            create_review_item(
                session=session,
                kind="unknown_product",
                source_record_id=source_record_id,
                payload={"raw_product": rec.product_raw, "source_id": source_id},
            )
            stats["review_items"] += 1

        # 3. Resolve location
        l_match = l_res.resolve(rec.location_raw)
        location_id: uuid.UUID | None = None

        if l_match:
            location_id = loc_id_map.get(l_match.pcode)
        elif rec.location_raw:
            # Create review_item for unknown location
            create_review_item(
                session=session,
                kind="unknown_location",
                source_record_id=source_record_id,
                payload={"raw_location": rec.location_raw, "source_id": source_id},
            )
            stats["review_items"] += 1

        # 4. Currency normalization (FMG -> MGA/5)
        price_mga, curr_status, curr_conf = normalize_currency(price_val, rec.currency_raw)

        # 5. Unit conversion
        price_mga_per_base, base_unit, unit_status, unit_conf = u_conv.convert_price_to_base(
            price_mga=price_mga,
            unit_raw=rec.unit_raw,
            product_code=resolved_pcode,
        )

        conversion_status = "exact"
        if curr_status == "uncertain" or unit_status == "uncertain":
            conversion_status = "uncertain"
        elif curr_status == "confident" or unit_status == "confident":
            conversion_status = "confident"

        # Overall confidence
        prod_conf = p_match.confidence if p_match else 0.5
        overall_conf = round(rec.confidence * curr_conf * unit_conf * prod_conf, 2)

        # Natural key calculation
        nk = rec.compute_natural_key(source_id)

        builder = functools.partial(
            _build_price_obs,
            rec=rec,
            source_id=source_id,
            source_record_id=source_record_id,
            nk=nk,
            product_id=product_id,
            location_id=location_id,
            price_val=price_val,
            price_mga_per_base=price_mga_per_base,
            base_unit=base_unit,
            conversion_status=conversion_status,
            missing_code=missing_code,
            overall_conf=overall_conf,
        )

        compare_attrs = {
            "price_raw": rec.price_raw,
            "price_value": price_val,
            "unit_raw": rec.unit_raw,
            "observed_or_imputed": rec.observed_or_imputed,
        }

        action, _ = load_observation_with_supersession(
            session=session,
            model_cls=PriceObservation,
            natural_key=nk,
            create_instance_fn=builder,
            compare_attrs=compare_attrs,
            lookup_key=resolution.lookup_key,
        )

        if action == "inserted":
            stats["inserted"] += 1
        elif action == "superseded":
            stats["superseded"] += 1
        else:
            stats["skipped"] += 1

    return stats


def main() -> None:
    """CLI entrypoint for seeding and normalization."""
    parser = argparse.ArgumentParser(description="Ketrika Normalization and Seeding CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("seed", help="Seed database with taxonomies, registries and demo users")

    args = parser.parse_args()

    if args.command == "seed":
        with transaction() as session:
            results = seed_database(session)
            print(f"Seed complete: {results}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
