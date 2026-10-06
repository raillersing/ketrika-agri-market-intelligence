"""Geographic boundary loader, location resolver and crop calendar manager."""

import json
from pathlib import Path
from typing import Any

import yaml

from ketrika.core.models.geo import (
    CropCalendarEntry,
    LocationAlias,
)
from ketrika.core.registry import find_repo_root
from ketrika.core.taxonomy import normalize_string


def get_default_geo_dir() -> Path:
    """Return default path to geo/processed directory."""
    root = find_repo_root()
    return root / "geo" / "processed"


def get_default_taxonomy_dir() -> Path:
    """Return default path to taxonomy directory."""
    root = find_repo_root()
    return root / "taxonomy"


def load_admin_geojson(level: str = "admin1", geo_dir: Path | str | None = None) -> dict[str, Any]:
    """Load GeoJSON FeatureCollection for a given administrative level."""
    g_dir = Path(geo_dir) if geo_dir else get_default_geo_dir()
    path = g_dir / f"{level}.geojson"
    if not path.exists():
        raise FileNotFoundError(f"GeoJSON file not found for level '{level}': {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = json.load(f)

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise ValueError(f"File {path} is not a valid GeoJSON FeatureCollection")

    return data


def load_location_aliases(
    taxonomy_dir: Path | str | None = None,
) -> list[LocationAlias]:
    """Load and validate all location aliases from taxonomy/location_aliases.yaml."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "location_aliases.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Location aliases file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [LocationAlias.model_validate(item) for item in data]


def load_crop_calendar(
    taxonomy_dir: Path | str | None = None,
) -> list[CropCalendarEntry]:
    """Load and validate seasonal crop calendar from taxonomy/crop_calendar.yaml."""
    t_dir = Path(taxonomy_dir) if taxonomy_dir else get_default_taxonomy_dir()
    path = t_dir / "crop_calendar.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Crop calendar file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected YAML list in {path}, got {type(data).__name__}")

    return [CropCalendarEntry.model_validate(item) for item in data]


def resolve_location(
    raw_name: str,
    aliases: list[LocationAlias] | None = None,
    min_confidence: float = 0.8,
) -> tuple[str, str, float] | None:
    """Resolve raw location denomination to (pcode, admin_level, confidence)."""
    if aliases is None:
        aliases = load_location_aliases()

    norm_query = normalize_string(raw_name)
    best_match: tuple[str, str, float] | None = None

    for a in aliases:
        if normalize_string(a.alias) == norm_query:
            if a.confidence >= min_confidence:
                if best_match is None or a.confidence > best_match[2]:
                    best_match = (a.pcode, a.admin_level, a.confidence)

    return best_match


def validate_geo(
    geo_dir: Path | str | None = None,
    taxonomy_dir: Path | str | None = None,
) -> list[str]:
    """Validate spatial datasets, region counts and location aliases."""
    errors: list[str] = []

    # 1. Validate GeoJSON boundaries
    try:
        admin0 = load_admin_geojson("admin0", geo_dir)
        if len(admin0.get("features", [])) < 1:
            errors.append("admin0.geojson has no features")
    except Exception as e:
        errors.append(f"Failed to load admin0.geojson: {e}")

    try:
        admin1 = load_admin_geojson("admin1", geo_dir)
        features = admin1.get("features", [])
        if len(features) != 23:
            errors.append(
                f"admin1.geojson must contain exactly 23 official regions, got {len(features)}"
            )
        pcodes = {f.get("properties", {}).get("ADM1_PCODE") for f in features}
        if None in pcodes:
            errors.append("admin1.geojson has features with missing ADM1_PCODE")
    except Exception as e:
        errors.append(f"Failed to load admin1.geojson: {e}")

    # 2. Validate location aliases
    try:
        aliases = load_location_aliases(taxonomy_dir)
        seen: set[str] = set()
        for a in aliases:
            norm = normalize_string(a.alias)
            if norm in seen:
                errors.append(f"Duplicate location alias: '{a.alias}'")
            seen.add(norm)
    except Exception as e:
        errors.append(f"Failed to load location aliases: {e}")

    # 3. Validate crop calendar
    try:
        cal = load_crop_calendar(taxonomy_dir)
        for c in cal:
            if not c.source.strip():
                errors.append(f"Crop calendar entry '{c.zone_code}:{c.crop}' missing source")
    except Exception as e:
        errors.append(f"Failed to load crop calendar: {e}")

    return errors
