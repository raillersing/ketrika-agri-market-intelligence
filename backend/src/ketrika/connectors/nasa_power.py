"""NASA POWER Agroclimatology Daily Point API connector (SPECS §5.4, MVP_EXECUTION_PLAN T3.4).

Ingests daily agro-meteorological variables (PRECTOTCORR, T2M_MAX, T2M_MIN, RH2M)
for district centroids (admin_level = 2) in Madagascar.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import date
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import WeatherRecord
from ketrika.core.geo import load_geographic_entities

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


class NasaPowerConnector:
    """Connector for NASA POWER agro-meteorological daily point observations."""

    source_id: ClassVar[str] = "nasa_power"
    parser_version: ClassVar[str] = "1.0.0"

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

        for district in districts:
            if district.longitude is None or district.latitude is None:
                continue

            query_url = (
                f"{endpoint}?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M"
                f"&community=AG"
                f"&longitude={district.longitude}&latitude={district.latitude}"
                f"&format=JSON"
            )

            yield DiscoveredItem(
                url=query_url,
                partition_key=f"{district.pcode}_daily",
                hints={
                    "district_pcode": district.pcode,
                    "district_name": district.name_fr,
                    "longitude": str(district.longitude),
                    "latitude": str(district.latitude),
                },
            )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch NASA POWER GeoJSON point data and store into Bronze layer."""
        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse NASA POWER GeoJSON payload into typed WeatherRecord objects."""
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

        # Identify district
        district_pcode = props.get("district_pcode")
        if not district_pcode and coords and len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            # Find nearest district by centroid
            districts = load_geographic_entities("admin2")
            best_dist = float("inf")
            best_pcode = None
            for d in districts:
                if d.longitude is not None and d.latitude is not None:
                    sq_dist = (d.longitude - lon) ** 2 + (d.latitude - lat) ** 2
                    if sq_dist < best_dist:
                        best_dist = sq_dist
                        best_pcode = d.pcode
            district_pcode = best_pcode

        if not district_pcode:
            # Fallback to Antananarivo Renivohitra sample
            district_pcode = "MDG1101"

        param_dict = props.get("parameter", {})
        if not isinstance(param_dict, dict):
            issues.append(
                {
                    "kind": "missing_parameters",
                    "detail": "properties.parameter is missing",
                }
            )
            return ParseResult(records=[], issues=issues, parser_version=self.parser_version)

        for param_key, var_name in PARAM_MAP.items():
            daily_values = param_dict.get(param_key, {})
            if not isinstance(daily_values, dict):
                continue

            for date_str, raw_val in daily_values.items():
                if raw_val is None:
                    continue
                try:
                    val = float(raw_val)
                    # Filter sentinels
                    if val <= SENTINEL_THRESHOLD:
                        continue

                    # Filter invalid physical values
                    if var_name == "precip_mm" and val < 0.0:
                        continue
                    if var_name == "rh2m_pct" and (val < 0.0 or val > 100.0):
                        continue

                    # Parse date YYYYMMDD
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    obs_date = date(year, month, day)

                    rec = WeatherRecord(
                        location_raw=district_pcode,
                        date=obs_date,
                        variable=var_name,
                        value=round(val, 3),
                        method="point_centroid",
                        provider="nasa_power",
                        extraction_method="deterministic",
                        evidence={
                            "source": "nasa_power",
                            "param_raw": param_key,
                            "date_raw": date_str,
                            "coordinates": coords,
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
