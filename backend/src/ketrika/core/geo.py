import hashlib
import json
from pathlib import Path
from typing import Any, cast

import yaml

from ketrika.core.models.geo import (
    AdminLevel,
    CropCalendarEntry,
    GeographicEntity,
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


def load_geo_manifest(geo_dir: Path | str | None = None) -> dict[str, Any]:
    """Load and parse geographic dataset manifest tracing boundary versions, counts and divergences."""
    if geo_dir is not None:
        p = Path(geo_dir)
        base_geo = p if p.name == "geo" or (p / "manifest.json").exists() else p.parent
        manifest_path = base_geo / "manifest.json"
    else:
        root = find_repo_root()
        manifest_path = root / "geo" / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Geographic manifest not found: {manifest_path}")

    with open(manifest_path, encoding="utf-8") as f:
        data: Any = json.load(f)

    if not isinstance(data, dict) or "dataset_id" not in data:
        raise ValueError(f"Invalid geographic manifest in {manifest_path}")

    return data


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


def load_geographic_entities(
    level: str = "admin1",
    geo_dir: Path | str | None = None,
) -> list[GeographicEntity]:
    """Load administrative boundaries as validated GeographicEntity models."""
    fc = load_admin_geojson(level, geo_dir)
    features = fc.get("features", [])
    entities: list[GeographicEntity] = []

    level_num_str = level.replace("admin", "")
    pcode_prop = f"ADM{level_num_str}_PCODE"
    name_prop = f"ADM{level_num_str}_FR"
    parent_level = (
        int(level_num_str) - 1 if level_num_str.isdigit() and int(level_num_str) > 0 else None
    )
    parent_pcode_prop = f"ADM{parent_level}_PCODE" if parent_level is not None else None

    for feat in features:
        props = feat.get("properties", {})
        pcode = props.get(pcode_prop) or props.get("PCODE") or props.get("pcode", "")
        name_fr = props.get(name_prop) or props.get("name_fr") or props.get("NAME", "")
        name_mg = props.get(f"ADM{level_num_str}_MG") or props.get("name_mg")
        parent_pcode = props.get(parent_pcode_prop) if parent_pcode_prop else None

        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        lat: float | None = None
        lon: float | None = None
        if coords:
            if geom.get("type") == "Polygon" and len(coords[0]) > 0:
                poly = coords[0]
                lon = sum(c[0] for c in poly) / len(poly)
                lat = sum(c[1] for c in poly) / len(poly)
            elif geom.get("type") == "MultiPolygon" and len(coords[0][0]) > 0:
                poly = coords[0][0]
                lon = sum(c[0] for c in poly) / len(poly)
                lat = sum(c[1] for c in poly) / len(poly)

        admin_lvl = cast(
            AdminLevel, level if level in ("admin0", "admin1", "admin2", "admin3") else "admin1"
        )
        entities.append(
            GeographicEntity(
                pcode=pcode,
                name_fr=name_fr,
                name_mg=name_mg,
                admin_level=admin_lvl,
                parent_pcode=parent_pcode,
                latitude=round(lat, 4) if lat is not None else None,
                longitude=round(lon, 4) if lon is not None else None,
            )
        )

    return entities


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

    from ketrika.geo.contracts import CalendarType, CropCalendarRecord

    result: list[CropCalendarEntry] = []
    for item in data:
        if isinstance(item, dict) and "product_code" in item:
            rich = CropCalendarRecord.model_validate(item)
            if (
                rich.calendar_type != CalendarType.TRADITIONAL_BASELINE
                or not rich.verified
                or not rich.eligible_for_alerts
                or not rich.is_active
                or rich.superseded_by is not None
            ):
                continue
            projected = {key: getattr(rich, key) for key in CropCalendarEntry.model_fields}
            projected["source"] = rich.source or rich.source_reference
            result.append(CropCalendarEntry.model_validate(projected))
        else:
            result.append(CropCalendarEntry.model_validate(item))
    return result


def resolve_location(
    raw_name: str,
    aliases: list[LocationAlias] | None = None,
    min_confidence: float = 0.8,
) -> tuple[str, str, float] | None:
    """Resolve raw location denomination to (pcode, admin_level, confidence)."""
    if not raw_name or not raw_name.strip():
        return None

    if aliases is None:
        aliases = load_location_aliases()

    norm_upper = raw_name.strip().upper()

    # 1. Direct P-Code match
    for a in aliases:
        if a.pcode.upper() == norm_upper:
            if a.confidence >= min_confidence:
                return (a.pcode, a.admin_level, 1.0)

    # 2. Exact normalized alias match
    norm_query = normalize_string(raw_name)
    best_match: tuple[str, str, float] | None = None

    for a in aliases:
        if normalize_string(a.alias) == norm_query:
            if a.confidence >= min_confidence:
                if best_match is None or a.confidence > best_match[2]:
                    best_match = (a.pcode, a.admin_level, a.confidence)

    if best_match is not None:
        return best_match

    # 3. Fallback: hyphen/space equivalence
    norm_query_no_hyphen = " ".join(norm_query.replace("-", " ").split())
    for a in aliases:
        a_norm_no_hyphen = " ".join(normalize_string(a.alias).replace("-", " ").split())
        if a_norm_no_hyphen == norm_query_no_hyphen:
            if a.confidence >= min_confidence:
                if best_match is None or a.confidence > best_match[2]:
                    best_match = (a.pcode, a.admin_level, a.confidence)

    return best_match


def validate_geo(
    geo_dir: Path | str | None = None,
    taxonomy_dir: Path | str | None = None,
) -> list[str]:
    """Validate spatial datasets, region counts, manifest concordance and location aliases."""
    errors: list[str] = []
    g_dir = Path(geo_dir) if geo_dir else get_default_geo_dir()

    # 1. Validate Geographic Manifest concordance (R1.10)
    try:
        manifest = load_geo_manifest(g_dir)
        levels_declared = manifest.get("levels", {})
        for lvl_name, decl in levels_declared.items():
            expected_file = decl.get("file")
            expected_sha = decl.get("sha256")
            expected_count = decl.get("feature_count")

            target_path = (
                (g_dir.parent / expected_file) if expected_file else (g_dir / f"{lvl_name}.geojson")
            )
            if not target_path.exists():
                errors.append(f"Manifest level '{lvl_name}' file not found: {target_path}")
                continue

            content = target_path.read_bytes()
            actual_sha = hashlib.sha256(content).hexdigest()
            if expected_sha and actual_sha != expected_sha:
                errors.append(
                    f"Manifest sha256 mismatch for '{lvl_name}': expected {expected_sha}, got {actual_sha}"
                )

            geo_data = json.loads(content)
            actual_count = len(geo_data.get("features", []))
            if expected_count is not None and actual_count != expected_count:
                errors.append(
                    f"Manifest count mismatch for '{lvl_name}': expected {expected_count}, got {actual_count}"
                )
    except Exception as e:
        errors.append(f"Failed to validate geographic manifest: {e}")

    # 2. Validate GeoJSON boundaries and spatial coordinates
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

    try:
        admin2 = load_admin_geojson("admin2", geo_dir)
        if len(admin2.get("features", [])) < 3:
            errors.append("admin2.geojson should contain at least 3 sample districts")
    except Exception as e:
        errors.append(f"Failed to load admin2.geojson: {e}")

    try:
        admin3 = load_admin_geojson("admin3", geo_dir)
        if len(admin3.get("features", [])) < 1:
            errors.append("admin3.geojson should contain at least 1 sample commune")
    except Exception as e:
        errors.append(f"Failed to load admin3.geojson: {e}")

    # 3. Validate geographic entities loading and bounding box
    try:
        entities = load_geographic_entities("admin1", geo_dir)
        if len(entities) != 23:
            errors.append(
                f"load_geographic_entities('admin1') returned {len(entities)}, expected 23"
            )
        for ent in entities:
            if ent.latitude is not None and not (-26.0 <= ent.latitude <= -11.0):
                errors.append(
                    f"Entity '{ent.pcode}' latitude {ent.latitude} outside Madagascar bounds"
                )
            if ent.longitude is not None and not (43.0 <= ent.longitude <= 51.5):
                errors.append(
                    f"Entity '{ent.pcode}' longitude {ent.longitude} outside Madagascar bounds"
                )
    except Exception as e:
        errors.append(f"Failed to load geographic entities: {e}")

    # 4. Validate location aliases
    try:
        aliases = load_location_aliases(taxonomy_dir)
        seen: set[str] = set()
        admin1_pcodes_in_aliases: set[str] = set()
        for a in aliases:
            norm = normalize_string(a.alias)
            if norm in seen:
                errors.append(f"Duplicate location alias: '{a.alias}'")
            seen.add(norm)
            if a.admin_level == "admin1":
                admin1_pcodes_in_aliases.add(a.pcode)

        # Ensure all 23 official regions are covered in aliases
        expected_admin1_pcodes = {
            "MDG11",
            "MDG12",
            "MDG13",
            "MDG14",
            "MDG21",
            "MDG22",
            "MDG23",
            "MDG24",
            "MDG25",
            "MDG26",
            "MDG31",
            "MDG32",
            "MDG33",
            "MDG41",
            "MDG42",
            "MDG43",
            "MDG44",
            "MDG51",
            "MDG52",
            "MDG53",
            "MDG54",
            "MDG71",
            "MDG72",
        }
        missing_admin1 = expected_admin1_pcodes - admin1_pcodes_in_aliases
        if missing_admin1:
            errors.append(f"Missing location aliases for admin1 P-Codes: {sorted(missing_admin1)}")
    except Exception as e:
        errors.append(f"Failed to load location aliases: {e}")

    # 5. Non-arbitrary default check (R1.10): unknown location never falls back to MDG1101
    try:
        resolved_unknown = resolve_location("non_existent_location_query_xyz")
        if resolved_unknown is not None:
            errors.append(
                f"Unknown location resolved to {resolved_unknown} instead of None (arbitrary fallback violation)"
            )
    except Exception as e:
        errors.append(f"Failed to test unresolved location safety: {e}")

    # 6. Validate crop calendar
    try:
        cal = load_crop_calendar(taxonomy_dir)
        for c in cal:
            if not c.source.strip():
                errors.append(f"Crop calendar entry '{c.zone_code}:{c.crop}' missing source")
    except Exception as e:
        errors.append(f"Failed to load crop calendar: {e}")

    return errors
