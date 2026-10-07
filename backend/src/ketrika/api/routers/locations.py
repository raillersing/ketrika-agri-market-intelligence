"""Locations router (SPECS §19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ketrika.api.schemas import LocationItem
from ketrika.core.db import get_db
from ketrika.core.models.db import Location, LocationAlias

router = APIRouter(prefix="/v1/locations", tags=["locations"])


def get_geojson_dir() -> Path:
    """Find geo directory containing processed GeoJSONs."""
    p1 = Path("/app/geo/processed")
    if p1.exists():
        return p1
    p2 = Path(__file__).resolve().parent.parent.parent.parent.parent / "geo" / "processed"
    if p2.exists():
        return p2
    return Path("geo/processed")


@router.get("")
def list_locations(
    level: int | None = Query(
        None, description="Filter by administrative level (1=Region, 2=District, 9=Market)"
    ),
    geometry: bool = Query(False, description="Return GeoJSON FeatureCollection if true"),
    session: Session = Depends(get_db),
) -> Any:
    """List reference locations or return simplified GeoJSON FeatureCollection."""
    if geometry:
        # Load GeoJSON from processed assets
        geo_dir = get_geojson_dir()
        lvl = level if level in (0, 1, 2, 3) else 1
        geojson_file = geo_dir / f"admin{lvl}.geojson"
        if geojson_file.exists():
            data = json.loads(geojson_file.read_text(encoding="utf-8"))
            return JSONResponse(content=data)
        # Fallback empty collection
        return JSONResponse(content={"type": "FeatureCollection", "features": []})

    # Query from database
    stmt = select(Location)
    if level is not None:
        stmt = stmt.where(Location.admin_level == level)
    stmt = stmt.order_by(Location.admin_level, Location.pcode)
    locations = list(session.execute(stmt).scalars().all())

    # Map aliases
    alias_stmt = select(LocationAlias)
    aliases_rows = list(session.execute(alias_stmt).scalars().all())
    alias_map: dict[str, list[str]] = {}
    for a in aliases_rows:
        alias_map.setdefault(str(a.location_id), []).append(a.alias_norm)

    # Parent PCode lookup
    loc_by_id = {loc.location_id: loc.pcode for loc in locations}

    items: list[LocationItem] = []
    for loc in locations:
        items.append(
            LocationItem(
                location_id=loc.location_id,
                admin_level=loc.admin_level,
                pcode=loc.pcode,
                name=loc.name,
                parent_pcode=loc_by_id.get(loc.parent_id) if loc.parent_id else None,
                boundary_version=loc.boundary_version,
                aliases=alias_map.get(str(loc.location_id), []),
            )
        )
    return items
