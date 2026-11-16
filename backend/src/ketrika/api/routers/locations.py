"""Locations router (SPECS §19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ketrika.api.schemas import (
    LocationItem,
    LocationResolutionResult,
    UnresolvedLocationItem,
)
from ketrika.core.db import get_db
from ketrika.core.models.db import Location, LocationAlias, PriceObservation, SourceRecord
from ketrika.normalize.locations import LocationResolver

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


@router.get("/resolve", response_model=LocationResolutionResult)
def resolve_location_endpoint(
    query: str = Query(..., min_length=1, description="Raw location name or alias to resolve"),
    level: int | None = Query(
        None, description="Target admin level (1=Region, 2=District, 9=Market)"
    ),
    geo_id: str | None = Query(
        None, description="Provider geo identifier (e.g. mkt_mdg_analakely)"
    ),
) -> Any:
    """Resolve raw location or provider geo_id adhering to no_arbitrary_default."""
    resolver = LocationResolver()
    match = resolver.resolve(query, target_admin_level=level, geo_id=geo_id)
    if match is None:
        return LocationResolutionResult(
            raw_query=query,
            resolved=False,
            note="Unresolved location (no arbitrary default applied, routed to review queue)",
        )
    return LocationResolutionResult(
        raw_query=query,
        resolved=True,
        pcode=match.pcode,
        name=match.name,
        admin_level=match.admin_level,
        confidence=match.confidence,
        match_type=match.match_type,
        note=match.note,
    )


@router.get("/unresolved", response_model=list[UnresolvedLocationItem])
def list_unresolved_locations(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> Any:
    """List unresolved or pending location items awaiting human review (Gate H5)."""
    stmt = (
        select(
            PriceObservation.location_raw,
            SourceRecord.source_id,
            func.count(PriceObservation.observation_id).label("cnt"),
        )
        .join(
            SourceRecord,
            PriceObservation.source_record_id == SourceRecord.source_record_id,
            isouter=True,
        )
        .where(
            (PriceObservation.location_id.is_(None)) | (PriceObservation.review_status == "pending")
        )
        .group_by(PriceObservation.location_raw, SourceRecord.source_id)
        .order_by(func.count(PriceObservation.observation_id).desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    resolver = LocationResolver()
    results: list[UnresolvedLocationItem] = []
    for loc_raw, src_id, count in rows:
        if not loc_raw:
            continue
        candidates = resolver.propose_alias_candidates(loc_raw, min_fuzzy_score=70.0, limit=1)
        top_cand = candidates[0] if candidates else None
        results.append(
            UnresolvedLocationItem(
                location_raw=loc_raw,
                observation_count=count,
                source_id=src_id,
                suggested_pcode=top_cand.pcode if top_cand else None,
                suggested_name=top_cand.name if top_cand else None,
                suggested_confidence=top_cand.confidence if top_cand else 0.0,
                review_status="pending",
                human_reviewed=False,
            )
        )
    return results
