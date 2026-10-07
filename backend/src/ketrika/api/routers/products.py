"""Products router (SPECS §19)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.schemas import ProductItem
from ketrika.core.db import get_db
from ketrika.core.models.db import Product, ProductAlias

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
