"""NASA POWER Agroclimatology Daily Point API connector (SPECS §5.4, R1.11).

Ingests daily agro-meteorological variables (PRECTOTCORR, T2M_MAX, T2M_MIN, RH2M)
for district centroids (admin_level = 2) in Madagascar under strict policy rules.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import WeatherRecord
from ketrika.core.geo import load_geographic_entities
from ketrika.core.policy import PolicyStop
from ketrika.core.registry import find_repo_root

logger = logging.getLogger(__name__)

NASA_POWER_POINT_API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Parameter mappings to standard weather variables
PARAM_MAP: dict[str, str] = {
    "PRECTOTCORR": "precip_mm",
    "T2M_MAX": "t2m_max_c",
    "T2M_MIN": "t2m_min_c",
    "RH2M": "rh2m_pct",
}

SENTINEL_THRESHOLD = -900.0

# Bounding box for Madagascar geographical validation
MDG_LON_MIN, MDG_LON_MAX = 43.0, 51.5
MDG_LAT_MIN, MDG_LAT_MAX = -26.0, -11.0


class NasaPowerConnector:
    """Connector for NASA POWER agro-meteorological daily point observations."""

    source_id: ClassVar[str] = "nasa_power"
    parser_version: ClassVar[str] = "1.1.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover query URLs for each district centroid (admin_level = 2)."""
        districts = load_geographic_entities("admin2")
        override_urls = ctx.metadata.get("urls")

        if override_urls:
            for item_info in override_urls:
                yield DiscoveredItem(
                    url=item_info["url"],
                    partition_key=item_info.get("partition_key", "sample"),
                    hints=item_info.get("hints", {}),
                )
            return

        endpoint = ctx.metadata.get("endpoint_url") or NASA_POWER_POINT_API_URL
        start = ctx.metadata.get("start", "20240101")
        end = ctx.metadata.get("end", "20240110")

        # Track native 0.5° x 0.5° grid cells to avoid redundant queries while linking zones
        seen_cells: dict[str, list[str]] = {}

        for district in districts:
            if district.longitude is None or district.latitude is None:
                continue

            cell_lon = round(district.longitude * 2.0) / 2.0
            cell_lat = round(district.latitude * 2.0) / 2.0
            cell_id = f"{cell_lon:.2f}_{cell_lat:.2f}"

            if cell_id not in seen_cells:
                seen_cells[cell_id] = []
            seen_cells[cell_id].append(district.pcode or district.name_fr)

            query_url = (
                f"{endpoint}?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M"
                f"&community=AG"
                f"&longitude={district.longitude}&latitude={district.latitude}"
                f"&start={start}&end={end}"
                f"&time-standard=UTC"
                f"&format=JSON"
            )

            yield DiscoveredItem(
                url=query_url,
                partition_key=f"{district.pcode}_{start}_{end}",
                hints={
                    "district_pcode": district.pcode,
                    "district_name": district.name_fr,
                    "longitude": str(district.longitude),
                    "latitude": str(district.latitude),
                    "grid_cell": cell_id,
                    "start": start,
                    "end": end,
                    "time_standard": "UTC",
                },
            )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch NASA POWER GeoJSON point data respecting policy engine and offline mode."""
        override_urls = ctx.metadata.get("urls")

        # 1. Strict policy check: refuse network access when source is disabled (B-R010)
        if not ctx.offline and not override_urls and self.source_id == "nasa_power":
            root = find_repo_root()
            sources_yaml = root / "registry" / "sources.yaml"
            if sources_yaml.exists():
                import yaml

                data = yaml.safe_load(sources_yaml.read_text(encoding="utf-8"))
                for s in data:
                    if s.get("source_id") == "nasa_power" and s.get("status") == "disabled":
                        raise PolicyStop(
                            f"Source '{self.source_id}' is marked disabled in sources.yaml (robots.txt Disallow: /api/)"
                        )

        # 2. Offline fixture fallback for reproducible validation
        if ctx.offline:
            root = find_repo_root()
            base_dir = root / "backend" if (root / "backend").exists() else root
            fixture_path = (
                base_dir / "tests" / "fixtures" / "nasa_power" / "nasa_power_point_sample.json"
            )
            if not fixture_path.exists():
                raise FileNotFoundError(f"Offline fixture not found at {fixture_path}")
            content_bytes = fixture_path.read_bytes()
            content_sha256 = hashlib.sha256(content_bytes).hexdigest()
            now = datetime.now(UTC)
            object_key = f"{self.source_id}/{now.year}/{now.month:02d}/{content_sha256}.json"
            is_new = True

            if ctx.bronze_store:
                art = ctx.bronze_store.put(
                    source_id=self.source_id,
                    content=content_bytes,
                    mime_type="application/json",
                    url=item.url,
                )
                object_key = art.object_key
                is_new = art.is_new

            return RawArtifact(
                source_record_id=str(uuid.uuid4()),
                object_key=object_key,
                content_sha256=content_sha256,
                mime_type="application/json",
                url=item.url,
                is_new=is_new,
            )

        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse NASA POWER GeoJSON payload into typed WeatherRecord objects with physical checks."""
        if ctx.bronze_store is None:
            raise ValueError("Bronze store is required in RunContext")

        raw_bytes = ctx.bronze_store.get(artifact.object_key)
        text_content = raw_bytes.decode("utf-8", errors="replace")

        records: list[WeatherRecord] = []
        issues: list[dict[str, Any]] = []

        try:
            payload = json.loads(text_content)
        except json.JSONDecodeError as exc:
            issues.append({"kind": "json_decode_error", "detail": str(exc)})
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        if not isinstance(payload, dict):
            issues.append({"kind": "unexpected_payload", "detail": f"Payload is {type(payload)}"})
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        props = payload.get("properties", {})
        geometry = payload.get("geometry", {})
        coords = geometry.get("coordinates", [])

        # Identify district resolution strictly: no blind MDG1101 fallback
        district_pcode = props.get("district_pcode")
        if not district_pcode and coords and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            # Bounding box check for Madagascar
            if MDG_LON_MIN <= lon <= MDG_LON_MAX and MDG_LAT_MIN <= lat <= MDG_LAT_MAX:
                districts = load_geographic_entities("admin2")
                best_dist = float("inf")
                best_pcode = None
                for d in districts:
                    if d.longitude is not None and d.latitude is not None:
                        sq_dist = (d.longitude - lon) ** 2 + (d.latitude - lat) ** 2
                        if sq_dist < best_dist:
                            best_dist = sq_dist
                            best_pcode = d.pcode
                # Threshold for proximity matching (~1.5 degrees squared)
                if best_pcode and best_dist <= 2.25:
                    district_pcode = best_pcode

        if not district_pcode:
            issues.append(
                {
                    "kind": "unresolved_location_needs_review",
                    "detail": f"Location could not be resolved from properties or coordinates {coords}",
                    "coordinates": coords,
                }
            )
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        if "parameter" not in props or not isinstance(props["parameter"], dict):
            issues.append(
                {
                    "kind": "missing_parameters",
                    "detail": "properties.parameter is missing or not a dict",
                }
            )
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        param_dict = props["parameter"]

        # Pre-index daily values by date for cross-variable physical consistency checks
        values_by_date: dict[str, dict[str, Any]] = {}
        for param_key in PARAM_MAP:
            daily_dict = param_dict.get(param_key, {})
            if isinstance(daily_dict, dict):
                for d_str, raw_val in daily_dict.items():
                    if d_str not in values_by_date:
                        values_by_date[d_str] = {}
                    values_by_date[d_str][param_key] = raw_val

        for date_str, daily_params in values_by_date.items():
            try:
                year = int(date_str[:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                obs_date = date(year, month, day)
            except Exception as exc:
                issues.append(
                    {
                        "kind": "invalid_date_format",
                        "date": date_str,
                        "detail": str(exc),
                    }
                )
                continue

            # Validate thermal consistency: t2m_min <= t2m_max
            raw_tmin = daily_params.get("T2M_MIN")
            raw_tmax = daily_params.get("T2M_MAX")
            tmin_val: float | None = None
            tmax_val: float | None = None

            if raw_tmin is not None and float(raw_tmin) > SENTINEL_THRESHOLD:
                tmin_val = float(raw_tmin)
            if raw_tmax is not None and float(raw_tmax) > SENTINEL_THRESHOLD:
                tmax_val = float(raw_tmax)

            # Check Tmin <= Tmax if both present and valid
            if tmin_val is not None and tmax_val is not None and tmin_val > tmax_val:
                issues.append(
                    {
                        "kind": "physical_coherence_error",
                        "variable": "temperature",
                        "date": date_str,
                        "tmin": tmin_val,
                        "tmax": tmax_val,
                        "detail": f"t2m_min ({tmin_val}) > t2m_max ({tmax_val})",
                    }
                )
                # Invalidate thermal variables for this date
                tmin_val = None
                tmax_val = None

            for param_key, var_name in PARAM_MAP.items():
                raw_val = daily_params.get(param_key)
                if raw_val is None:
                    continue

                try:
                    val = float(raw_val)
                    # Filter NASA missing value sentinel (-999.0) - NEVER convert to 0.0
                    if val <= SENTINEL_THRESHOLD:
                        continue

                    # If thermal variables were flagged with coherence error, skip
                    if (
                        param_key == "T2M_MIN"
                        and tmin_val is None
                        and raw_tmin is not None
                        and float(raw_tmin) > SENTINEL_THRESHOLD
                        and tmax_val is None
                    ):
                        continue
                    if (
                        param_key == "T2M_MAX"
                        and tmax_val is None
                        and raw_tmax is not None
                        and float(raw_tmax) > SENTINEL_THRESHOLD
                        and tmin_val is None
                    ):
                        continue

                    # Validate physical limits
                    if var_name == "precip_mm" and val < 0.0:
                        issues.append(
                            {
                                "kind": "physical_coherence_error",
                                "variable": var_name,
                                "date": date_str,
                                "value": val,
                                "detail": f"Negative precipitation ({val} mm)",
                            }
                        )
                        continue

                    if var_name == "rh2m_pct" and (val < 0.0 or val > 100.0):
                        issues.append(
                            {
                                "kind": "physical_coherence_error",
                                "variable": var_name,
                                "date": date_str,
                                "value": val,
                                "detail": f"Relative humidity ({val}%) out of bounds [0, 100]",
                            }
                        )
                        continue

                    if var_name in ("t2m_max_c", "t2m_min_c") and (val < -15.0 or val > 55.0):
                        issues.append(
                            {
                                "kind": "physical_coherence_error",
                                "variable": var_name,
                                "date": date_str,
                                "value": val,
                                "detail": f"Temperature ({val}°C) out of realistic bounds [-15, 55]",
                            }
                        )
                        continue

                    rec = WeatherRecord(
                        location_raw=district_pcode,
                        date=obs_date,
                        variable=var_name,
                        value=round(val, 3),
                        value_raw=str(raw_val),
                        method="point_centroid",
                        provider="nasa_power",
                        extraction_method="deterministic",
                        evidence={
                            "source": "nasa_power",
                            "source_family": "nasa",
                            "param_raw": param_key,
                            "date_raw": date_str,
                            "coordinates": coords,
                            "district_pcode": district_pcode,
                            "cell_to_zone_mapping": district_pcode,
                            "time_reference": "UTC",
                            "is_forecast_or_estimated": False,
                            "value_kind": "observed",
                        },
                        confidence=1.0,
                    )
                    records.append(rec)

                except Exception as exc:
                    issues.append(
                        {
                            "kind": "row_parse_error",
                            "param": param_key,
                            "date": date_str,
                            "detail": str(exc),
                        }
                    )

        return ParseResult(records=records, issues=issues, parser_version=self.parser_version)
