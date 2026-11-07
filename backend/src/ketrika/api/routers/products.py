"""Products router (SPECS §19, ADR-165)."""

from __future__ import annotations

import calendar
import json
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ketrika.api.auth import get_current_user
from ketrika.api.schemas import (
    ObservationBatchCreateRequest,
    ObservationBatchCreateResponse,
    ProductCreateRequest,
    ProductItem,
)
from ketrika.core.bronze import BronzeStore
from ketrika.core.db import get_db
from ketrika.core.models.db import (
    Location,
    PriceObservation,
    Product,
    ProductAlias,
    Source,
    SourceRecord,
    UserAccount,
)
from ketrika.core.taxonomy import (
    append_aliases_to_yaml,
    append_product_to_yaml,
    normalize_string,
)

logger = logging.getLogger("ketrika.api.products")

router = APIRouter(prefix="/v1/products", tags=["products"])


@router.get("", response_model=list[ProductItem])
def list_products(session: Session = Depends(get_db)) -> list[ProductItem]:
    """Retrieve all reference PPN products with their canonical names and primary aliases."""
    stmt = select(Product).order_by(Product.product_code)
    products = list(session.execute(stmt).scalars().all())

    # Fetch aliases
    alias_stmt = select(ProductAlias)
    aliases_rows = list(session.execute(alias_stmt).scalars().all())
    alias_map: dict[str, list[str]] = {}
    for a in aliases_rows:
        alias_map.setdefault(str(a.product_id), []).append(a.alias_display)

    items: list[ProductItem] = []
    for p in products:
        items.append(
            ProductItem(
                product_id=p.product_id,
                product_code=p.product_code,
                canonical_name_fr=p.canonical_name_fr,
                category=p.category,
                base_unit=p.base_unit,
                hs6_codes=p.hs6_codes or [],
                faostat_item_codes=p.faostat_item_codes or [],
                aliases=alias_map.get(str(p.product_id), []),
            )
        )
    return items


@router.get("/{product_code}", response_model=ProductItem)
def get_product_by_code(
    product_code: str,
    session: Session = Depends(get_db),
) -> ProductItem:
    """Retrieve a single reference product by code."""
    p_code = product_code.strip().upper()
    stmt = select(Product).where(Product.product_code == p_code)
    prod = session.execute(stmt).scalar_one_or_none()
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit '{product_code}' introuvable.",
        )

    # Fetch aliases
    alias_stmt = select(ProductAlias).where(ProductAlias.product_id == prod.product_id)
    aliases_rows = list(session.execute(alias_stmt).scalars().all())
    alias_names = [a.alias_display for a in aliases_rows]

    return ProductItem(
        product_id=prod.product_id,
        product_code=prod.product_code,
        canonical_name_fr=prod.canonical_name_fr,
        category=prod.category,
        base_unit=prod.base_unit,
        hs6_codes=prod.hs6_codes or [],
        faostat_item_codes=prod.faostat_item_codes or [],
        aliases=alias_names,
    )


@router.post("", response_model=ProductItem, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ProductItem:
    """Dynamically register a new canonical commodity and aliases (ADR-165)."""
    p_code = payload.product_code.strip().upper()

    # 1. Check uniqueness
    existing = session.execute(
        select(Product).where(Product.product_code == p_code)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Le produit avec le code '{p_code}' existe déjà.",
        )

    # 2. Insert into ref.product
    new_prod_id = uuid.uuid4()
    prod = Product(
        product_id=new_prod_id,
        product_code=p_code,
        canonical_name_fr=payload.canonical_name_fr.strip(),
        category=payload.category.strip().lower(),
        base_unit=payload.base_unit.strip().lower(),
        hs6_codes=payload.hs6_codes,
        faostat_item_codes=payload.faostat_item_codes,
        verified=True,
    )
    session.add(prod)
    session.flush()

    # 3. Create aliases in ref.product_alias
    aliases_to_add = [payload.canonical_name_fr] + payload.aliases
    registered_aliases: list[str] = []
    yaml_aliases: list[dict[str, str | float]] = []

    # Get already normalized global aliases to prevent primary key collision
    all_alias_norms = set(
        session.scalars(
            select(ProductAlias.alias_norm).where(ProductAlias.source_id.is_(None))
        ).all()
    )

    for alias_text in aliases_to_add:
        cleaned = alias_text.strip()
        norm = normalize_string(cleaned)
        if not norm or norm in all_alias_norms:
            continue
        all_alias_norms.add(norm)

        alias_row = ProductAlias(
            alias_id=uuid.uuid4(),
            alias_norm=norm,
            alias_display=cleaned,
            lang="fr",
            product_id=new_prod_id,
            source_id=None,
            confidence=1.0 if cleaned == payload.canonical_name_fr else 0.95,
            origin="user_created",
            human_reviewed=True,
        )
        session.add(alias_row)
        registered_aliases.append(cleaned)
        yaml_aliases.append({
            "alias": cleaned,
            "lang": "fr",
            "product_code": p_code,
            "confidence": 0.95,
            "evidence": f"Créé par {current_user.email} (ADR-165)",
        })

    session.commit()

    # 4. Mirror sync into taxonomy YAML files for rebuild rejouabilité (AGENTS.md Principle 4)
    try:
        append_product_to_yaml(
            product_code=p_code,
            canonical_name_fr=payload.canonical_name_fr.strip(),
            category=payload.category.strip().lower(),
            base_unit=payload.base_unit.strip().lower(),
            hs6_codes=payload.hs6_codes,
            faostat_item_codes=[int(c) for c in payload.faostat_item_codes if c.isdigit()],
            notes=payload.notes,
        )
        append_aliases_to_yaml(yaml_aliases)
    except Exception as exc:
        logger.warning("Mirror YAML taxonomy sync warning: %s", exc)

    return ProductItem(
        product_id=prod.product_id,
        product_code=prod.product_code,
        canonical_name_fr=prod.canonical_name_fr,
        category=prod.category,
        base_unit=prod.base_unit,
        hs6_codes=prod.hs6_codes or [],
        faostat_item_codes=prod.faostat_item_codes or [],
        aliases=registered_aliases,
    )


@router.post(
    "/{product_code}/observations",
    response_model=ObservationBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_observations_batch(
    product_code: str,
    payload: ObservationBatchCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ObservationBatchCreateResponse:
    """Ingest price observations with 100% verified Bronze provenance (ADR-165)."""
    p_code = product_code.strip().upper()
    prod = session.execute(
        select(Product).where(Product.product_code == p_code)
    ).scalar_one_or_none()
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit '{product_code}' introuvable.",
        )

    # 1. Ensure 'user_upload' source exists in meta.source
    src = session.get(Source, "user_upload")
    if not src:
        src = Source(
            source_id="user_upload",
            spec={"name": "Relevés directs et imports utilisateurs", "type": "manual_entry"},
            status="active",
        )
        session.add(src)
        session.flush()

    # 2. Store raw JSON payload in MinIO Bronze store with SHA-256
    raw_dict = {
        "product_code": p_code,
        "submitted_by": current_user.email,
        "submitted_at": datetime.now(UTC).isoformat(),
        "notes": payload.notes,
        "observations": [obs.model_dump() for obs in payload.observations],
    }
    raw_bytes = json.dumps(raw_dict, ensure_ascii=False, indent=2).encode("utf-8")

    try:
        bronze = BronzeStore()
        artifact = bronze.put(
            source_id="user_upload",
            content=raw_bytes,
            mime_type="application/json",
            url=f"manual://products/{p_code}/batch/{uuid.uuid4()}",
            retrieved_via="direct",
        )
    except Exception as exc:
        logger.error("Bronze store write failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stockage Bronze immuable temporairement indisponible.",
        ) from exc

    # 3. Create SourceRecord
    source_record_id = uuid.uuid4()
    srec = SourceRecord(
        source_record_id=source_record_id,
        source_id="user_upload",
        source_url=f"manual://products/{p_code}/batch/{source_record_id}",
        retrieved_via="direct",
        object_key=artifact.object_key,
        content_sha256=artifact.content_sha256,
        mime_type="application/json",
        http_status=200,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        extraction_status="extracted",
    )
    session.add(srec)
    session.flush()

    # 4. Resolve national and regional locations lookup
    locations_by_pcode: dict[str, Location] = {}
    for loc in session.scalars(select(Location)).all():
        if loc.pcode:
            locations_by_pcode[loc.pcode.upper()] = loc
    national_loc = locations_by_pcode.get("MDG") or session.scalars(select(Location).where(Location.admin_level == 0)).first()

    # 5. Insert observations in Silver (obs.price_observation)
    count_created = 0
    now_utc = datetime.now(UTC)

    for item in payload.observations:
        # Parse date
        d_str = item.date.strip()
        try:
            if len(d_str) == 7:  # YYYY-MM
                parts = d_str.split("-")
                year, month = int(parts[0]), int(parts[1])
                day = 1
            else:  # YYYY-MM-DD
                parts = d_str.split("-")
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            start_date = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = date(year, month, last_day)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format de date invalide '{item.date}'. Utilisez YYYY-MM-DD ou YYYY-MM.",
            ) from exc

        # Resolve location
        loc = locations_by_pcode.get(item.location_pcode.strip().upper()) or national_loc
        loc_id = loc.location_id if loc else None
        loc_pcode = loc.pcode if loc else item.location_pcode

        nat_key = f"{p_code}:{loc_pcode}:{item.actor_level}:{start_date.isoformat()}"

        # Manage supersession (Principle 3: Append-only)
        existing_active = session.scalars(
            select(PriceObservation).where(
                PriceObservation.natural_key == nat_key,
                PriceObservation.superseded_by.is_(None),
            )
        ).first()

        new_obs_id = uuid.uuid4()
        if existing_active:
            existing_active.superseded_by = new_obs_id

        p_val = Decimal(str(round(item.price, 2)))

        obs = PriceObservation(
            observation_id=new_obs_id,
            source_record_id=source_record_id,
            natural_key=nat_key,
            product_raw=prod.canonical_name_fr,
            product_id=prod.product_id,
            location_raw=item.location_pcode,
            location_id=loc_id,
            actor_level=item.actor_level,
            period_start=start_date,
            period_end=end_date,
            published_at=now_utc,
            ingested_at=now_utc,
            price_raw=str(item.price),
            price_value=p_val,
            currency_raw=item.currency,
            unit_raw=item.unit,
            price_mga_per_base=p_val if item.currency == "MGA" else None,
            base_unit=prod.base_unit,
            conversion_status="direct",
            observed_or_imputed="observed",
            extraction_method="manual_import",
            confidence=Decimal("1.00"),
            review_status="accepted",
        )
        session.add(obs)
        count_created += 1

    session.commit()

    # 6. Refresh Gold materialized views so changes appear immediately
    recomputed_views = ["price_obs_current", "price_monthly", "price_monthly_best"]
    try:
        session.execute(text("REFRESH MATERIALIZED VIEW gold.price_obs_current;"))
        session.execute(text("REFRESH MATERIALIZED VIEW gold.price_monthly;"))
        session.execute(text("REFRESH MATERIALIZED VIEW gold.price_monthly_best;"))
        session.commit()
    except Exception as exc:
        logger.warning("Gold views refresh warning: %s", exc)

    return ObservationBatchCreateResponse(
        product_code=p_code,
        observations_created=count_created,
        bronze_content_hash=artifact.content_sha256,
        source_record_id=source_record_id,
        recomputed_gold_views=recomputed_views,
    )
