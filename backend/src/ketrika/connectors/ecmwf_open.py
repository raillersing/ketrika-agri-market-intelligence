"""ECMWF Open Data Numerical Weather Prediction Connector (ADR-084, SPECS §26, R4.5).

Connector for European Centre for Medium-Range Weather Forecasts (ECMWF) Open Data.
Enforces:
1. Strict separation of predicted weather (WeatherForecastRecord -> obs.weather_forecast) vs observed facts.
2. Archiving immutable NWP runs in Bronze prior to rolling buffer expiration.
3. Quantiles of uncertainty (p10, p50/median, p90) and horizons (24h to 168h).
4. Physical consistency checks (non-negative rainfall, realistic tropical temperatures).
5. Absolute refusal to generate pseudo-hindcasts from actual observed weather.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import WeatherForecastRecord
from ketrika.geo.contracts import WeatherVariable

logger = logging.getLogger(__name__)

ECMWF_OPEN_DATA_BASE_URL = "https://data.ecmwf.int/forecasts"


class EcmwfOpenConnector:
    """Connector for ECMWF Open Data IFS operational numerical weather predictions."""

    source_id: ClassVar[str] = "ecmwf_open"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover available forecast runs (00Z and 12Z cycles) for Madagascar."""
        override_urls = ctx.metadata.get("urls")
        if override_urls:
            for item in override_urls:
                yield DiscoveredItem(
                    url=item["url"],
                    partition_key=item.get("partition_key"),
                    hints=item.get("hints", {}),
                )
            return

        date_str = ctx.metadata.get("target_date", "2024-03-01")
        base_date = datetime.fromisoformat(date_str).replace(tzinfo=UTC)

        # ECMWF Open Data publishes 00z and 12z runs
        cycles = ctx.metadata.get("cycles", ["00z", "12z"])
        for cycle in cycles:
            url = f"{ECMWF_OPEN_DATA_BASE_URL}/{base_date.strftime('%Y%m%d')}/{cycle}/ifs_madagascar_0p4.json"
            partition_key = f"ecmwf_open_{base_date.strftime('%Y%m%d')}_{cycle}"
            yield DiscoveredItem(
                url=url,
                partition_key=partition_key,
                hints={
                    "issued_at": f"{base_date.strftime('%Y-%m-%d')}T{cycle[:2]}:00:00Z",
                    "cycle": cycle,
                    "model": "ecmwf_ifs_open",
                },
            )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch forecast run artifact and archive in Bronze."""
        return ctx.fetch_and_store(item, mime_type="application/json")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse ECMWF Open Data forecast into WeatherForecastRecord items."""
        raw_bytes: bytes | None = None
        if ctx.bronze_store is not None:
            raw_bytes = ctx.bronze_store.get(artifact.object_key)

        if raw_bytes is None:
            payload_data = ctx.metadata.get("payload_bytes")
            if isinstance(payload_data, bytes):
                raw_bytes = payload_data
            else:
                raw_bytes = b""

        # 1. Check for missing or unavailable run
        if not raw_bytes or raw_bytes.strip() == b"":
            return ParseResult(
                records=[],
                issues=[
                    {
                        "kind": "document_unavailable",
                        "detail": f"Official ECMWF forecast run unavailable for url '{artifact.url}'",
                        "url": artifact.url,
                    }
                ],
                parser_version=self.parser_version,
            )

        filename = Path(artifact.url).name
        records: list[WeatherForecastRecord] = []
        issues: list[dict[str, Any]] = []

        try:
            doc = json.loads(raw_bytes.decode("utf-8"))

            if doc.get("status") == "unavailable":
                return ParseResult(
                    records=[],
                    issues=[
                        {
                            "kind": "document_unavailable",
                            "detail": doc.get("reason", "Forecast run unavailable at provider"),
                            "url": artifact.url,
                        }
                    ],
                    parser_version=self.parser_version,
                )

            issued_at_str = doc.get("issued_at", "2024-03-01T00:00:00Z")
            issued_at = datetime.fromisoformat(issued_at_str.replace("Z", "+00:00"))
            model_name = doc.get("model_name", "ecmwf_ifs_open")

            for item in doc.get("forecasts", []):
                location_raw = item["location_raw"]
                horizon_hours = int(item["horizon_hours"])
                variable = item.get("variable", WeatherVariable.PRECIP_MM.value)
                unit = item.get("unit", "mm")

                valid_from_str = item.get("valid_from")
                if valid_from_str:
                    valid_from = datetime.fromisoformat(valid_from_str.replace("Z", "+00:00"))
                else:
                    valid_from = issued_at + timedelta(hours=horizon_hours)

                valid_to_str = item.get("valid_to")
                if valid_to_str:
                    valid_to = datetime.fromisoformat(valid_to_str.replace("Z", "+00:00"))
                else:
                    valid_to = valid_from + timedelta(hours=24)

                val = float(item["predicted_value"])
                p10 = float(item["predicted_p10"]) if "predicted_p10" in item else None
                p90 = float(item["predicted_p90"]) if "predicted_p90" in item else None

                # Physical consistency controls (ADR-084)
                if variable == WeatherVariable.PRECIP_MM.value:
                    if val < 0:
                        issues.append(
                            {
                                "kind": "invalid_physical_value",
                                "detail": f"Negative rainfall forecast {val} mm rejected for {location_raw}",
                                "location_raw": location_raw,
                            }
                        )
                        continue
                    if p10 is not None and p10 < 0:
                        p10 = 0.0

                if "t2m" in variable:
                    if val > 60.0 or val < -15.0:
                        issues.append(
                            {
                                "kind": "unrealistic_temperature",
                                "detail": f"Unrealistic temperature {val} C for Madagascar location {location_raw}",
                                "location_raw": location_raw,
                            }
                        )
                        continue

                rec = WeatherForecastRecord(
                    location_raw=location_raw,
                    issued_at=issued_at,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    horizon_hours=horizon_hours,
                    variable=variable,
                    model_name=model_name,
                    predicted_value=val,
                    predicted_p10=p10,
                    predicted_p90=p90,
                    unit=unit,
                    method=item.get("method", "point_centroid"),
                    spatial_resolution=item.get("spatial_resolution", "0.4_deg"),
                    evidence={
                        "source_file": filename,
                        "sha256": artifact.content_sha256,
                        "issued_at": issued_at_str,
                        "horizon_hours": horizon_hours,
                        "model_name": model_name,
                    },
                )
                records.append(rec)

        except Exception as e:
            logger.warning("Error parsing ECMWF forecast run: %s", e)
            issues.append({"kind": "parse_error", "detail": str(e)})

        return ParseResult(
            records=records,
            issues=issues,
            parser_version=self.parser_version,
        )


Connector = EcmwfOpenConnector
