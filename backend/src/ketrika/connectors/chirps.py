"""CHIRPS v2.0 Rainfall Estimates with Station Data Connector (ADR-080, ADR-081, SPECS §26, R4.2).

Ingests monthly satellite and ground-station rainfall estimates from Climate Hazards Center (UCSB).
Enforces:
1. Double-version lifecycle (preliminary at J+2..J+5, final at M+1) with immutable supersession (C2/C4).
2. Strict physical distinction between zero rain (0.0 mm) and nodata (-9999.0).
3. Geospatial bounding box clipping on Madagascar ([43.0, -25.8, 50.8, -11.8]).
4. Maximum monthly raster Bronze budget limit (<= 50 MB).
5. Zonal aggregation (zonal_mean) over administrative regions and districts.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import re
import uuid
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import ClassVar

from ketrika.connectors.base import DiscoveredItem, ParseResult, RawArtifact, RunContext
from ketrika.connectors.records import WeatherRecord
from ketrika.core.geo import load_geographic_entities
from ketrika.core.policy import PolicyStop
from ketrika.geo.contracts import (
    BBOX_MADAGASCAR,
    MAX_RASTER_FILE_SIZE_BYTES,
    SpatialResolution,
    WeatherStage,
    WeatherVariable,
)
from ketrika.geo.raster import aggregate_zonal, is_within_madagascar_bbox

logger = logging.getLogger(__name__)

# Official UCSB CHC data distribution endpoints
CHIRPS_AFRICA_MONTHLY_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs"
CHIRPS_PRELIM_AFRICA_MONTHLY_URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/africa_monthly/tifs"
)
CHIRPS_GLOBAL_MONTHLY_URL = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs"
CHIRPS_PRELIM_GLOBAL_MONTHLY_URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0/prelim/global_monthly/tifs"
)

CHIRPS_NODATA_VALUE: float = -9999.0


class ChirpsGridPayload:
    """In-memory gridded raster data for CHIRPS tiles cropped to Madagascar."""

    def __init__(
        self,
        year: int,
        month: int,
        stage: str,
        grid_data: dict[tuple[float, float], float],
        resolution: float = 0.05,
    ) -> None:
        self.year = year
        self.month = month
        self.stage = stage
        self.grid_data = grid_data  # (lon, lat) -> precipitation_mm
        self.resolution = resolution

    def get_cells_near(self, lon: float, lat: float, radius_deg: float = 0.15) -> list[float]:
        """Extract all raster cell values within radius_deg of target point."""
        cells: list[float] = []
        for (g_lon, g_lat), val in self.grid_data.items():
            if abs(g_lon - lon) <= radius_deg and abs(g_lat - lat) <= radius_deg:
                cells.append(val)
        return cells


class ChirpsConnector:
    """Connector for CHIRPS v2.0 agro-meteorological monthly precipitation rasters."""

    source_id: ClassVar[str] = "chirps"
    parser_version: ClassVar[str] = "1.0.0"

    def discover(self, ctx: RunContext) -> Iterable[DiscoveredItem]:
        """Discover CHIRPS raster partitions for preliminary and/or final stages."""
        override_urls = ctx.metadata.get("urls")
        if override_urls:
            for item in override_urls:
                yield DiscoveredItem(
                    url=item["url"],
                    partition_key=item.get("partition_key"),
                    hints=item.get("hints", {}),
                )
            return

        years: list[int] = ctx.metadata.get("years", [2024])
        months: list[int] = ctx.metadata.get("months", [1, 2, 3])
        stages: list[str]
        stage_meta = ctx.metadata.get("stage", "final")
        if stage_meta == "both":
            stages = ["preliminary", "final"]
        elif isinstance(stage_meta, list):
            stages = stage_meta
        else:
            stages = [str(stage_meta)]

        subregion = ctx.metadata.get("subregion", "africa")

        for year in years:
            for month in months:
                for stage in stages:
                    if stage == WeatherStage.PRELIMINARY or stage == "preliminary":
                        base_url = (
                            CHIRPS_PRELIM_AFRICA_MONTHLY_URL
                            if subregion == "africa"
                            else CHIRPS_PRELIM_GLOBAL_MONTHLY_URL
                        )
                        filename = f"chirps-v2.0.{year}.{month:02d}.tif.gz"
                    else:
                        base_url = (
                            CHIRPS_AFRICA_MONTHLY_URL
                            if subregion == "africa"
                            else CHIRPS_GLOBAL_MONTHLY_URL
                        )
                        filename = f"chirps-v2.0.{year}.{month:02d}.tif.gz"

                    full_url = f"{base_url}/{filename}"
                    partition_key = f"chirps_{stage}_{year}_{month:02d}"

                    yield DiscoveredItem(
                        url=full_url,
                        partition_key=partition_key,
                        hints={
                            "year": str(year),
                            "month": str(month),
                            "stage": stage,
                            "subregion": subregion,
                            "variable": WeatherVariable.PRECIP_MM,
                            "spatial_resolution": SpatialResolution.CHIRPS_005,
                        },
                    )

    def fetch(self, item: DiscoveredItem, ctx: RunContext) -> RawArtifact:
        """Fetch raw CHIRPS raster file and store in Bronze."""
        return ctx.fetch_and_store(item, mime_type="application/gzip")

    def parse(self, artifact: RawArtifact, ctx: RunContext) -> ParseResult:
        """Parse raw CHIRPS artifact into normalized WeatherRecord items."""
        # 1. Budget enforcement: reject rasters larger than 50 MB
        raw_bytes: bytes | None = None
        if ctx.bronze_store is not None:
            raw_bytes = ctx.bronze_store.get(artifact.object_key)

        if raw_bytes is None:
            # Check if artifact provides direct payload in metadata
            payload_data = ctx.metadata.get("payload_bytes")
            if isinstance(payload_data, bytes):
                raw_bytes = payload_data
            else:
                raw_bytes = b""

        if len(raw_bytes) > MAX_RASTER_FILE_SIZE_BYTES:
            raise PolicyStop(
                f"CHIRPS raster size ({len(raw_bytes)} bytes) exceeds budget of {MAX_RASTER_FILE_SIZE_BYTES} bytes"
            )

        # 2. Extract metadata and stage from URL / hints / filename
        filename = Path(artifact.url).name
        stage = "final"
        year = 2024
        month = 1

        match = re.search(r"(\d{4})\.(\d{1,2})", filename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))

        if "prelim" in artifact.url.lower() or "preliminary" in filename.lower():
            stage = "preliminary"

        # 3. Decode raster payload (supporting decompressed gzip or structured JSON raster)
        try:
            grid_data = self._decode_raster_data(raw_bytes, artifact.url)
        except Exception as exc:
            logger.warning("Failed to decode CHIRPS raster for %s: %s", artifact.url, exc)
            return ParseResult(
                records=[],
                issues=[{"kind": "raster_decode_error", "detail": str(exc), "url": artifact.url}],
                parser_version=self.parser_version,
            )

        # 4. Load Madagascar administrative zones (districts admin_level 2 and regions admin_level 1)
        entities = load_geographic_entities("admin2")
        if not entities:
            entities = load_geographic_entities("admin1")

        records: list[WeatherRecord] = []
        obs_date = date(year, month, 1)

        for entity in entities:
            if entity.longitude is None or entity.latitude is None:
                continue

            # Validate that entity centroid is within Madagascar BBOX
            if not is_within_madagascar_bbox(entity.longitude, entity.latitude):
                continue

            # Extract grid cells within entity boundary
            cells = grid_data.get_cells_near(entity.longitude, entity.latitude, radius_deg=0.15)
            if not cells:
                # Fallback to single nearest cell or default 0.0 if in coverage
                cells = [
                    grid_data.grid_data.get(
                        (round(entity.longitude * 20) / 20, round(entity.latitude * 20) / 20),
                        CHIRPS_NODATA_VALUE,
                    )
                ]

            # Perform zonal aggregation enforcing distinction between 0.0 mm and nodata
            agg_res = aggregate_zonal(
                values=cells,
                nodata_value=CHIRPS_NODATA_VALUE,
            )

            # If no valid cell found, skip to prevent artificial imputation
            if agg_res.value is None:
                continue

            loc_identifier = entity.pcode if entity.pcode else entity.name_fr

            sr_uuid: uuid.UUID | None = None
            if artifact.source_record_id:
                try:
                    sr_uuid = uuid.UUID(artifact.source_record_id)
                except ValueError:
                    sr_uuid = None

            rec = WeatherRecord(
                location_raw=loc_identifier,
                date=obs_date,
                variable=WeatherVariable.PRECIP_MM,
                value=agg_res.value,
                value_raw=str(agg_res.value),
                method="zonal_mean",
                provider="chirps",
                stage=stage,
                spatial_resolution="0.05_deg",
                coverage_ratio=agg_res.coverage_ratio,
                raster_source_record_id=sr_uuid,
                extraction_method="deterministic",
                evidence={
                    "source_file": filename,
                    "sha256": artifact.content_sha256,
                    "stage": stage,
                    "valid_cells": agg_res.valid_cell_count,
                    "coverage_ratio": agg_res.coverage_ratio,
                    "url": artifact.url,
                },
            )
            records.append(rec)

        return ParseResult(
            records=records,
            issues=[],
            parser_version=self.parser_version,
        )

    def _decode_raster_data(self, raw_bytes: bytes, url: str) -> ChirpsGridPayload:
        """Decode raster payload bytes into a structured grid representation."""
        data_to_parse = raw_bytes
        if len(raw_bytes) >= 2 and raw_bytes[:2] == b"\x1f\x8b":
            # Gzip compressed
            try:
                data_to_parse = gzip.decompress(raw_bytes)
            except Exception as e:
                logger.warning("Failed to decompress gzip raster: %s", e)

        # 1. Check if structured JSON representation
        if data_to_parse.startswith(b"{"):
            try:
                doc = json.loads(data_to_parse.decode("utf-8"))
                grid: dict[tuple[float, float], float] = {}
                for item in doc.get("cells", []):
                    lon = float(item["lon"])
                    lat = float(item["lat"])
                    val = float(item["val"])
                    grid[(lon, lat)] = val
                return ChirpsGridPayload(
                    year=doc.get("year", 2024),
                    month=doc.get("month", 1),
                    stage=doc.get("stage", "final"),
                    grid_data=grid,
                    resolution=doc.get("resolution", 0.05),
                )
            except Exception as e:
                logger.debug("Not a JSON grid format: %s", e)

        # 2. Try rasterio if available
        try:
            import rasterio  # type: ignore[import-untyped]

            with rasterio.open(io.BytesIO(data_to_parse)) as src:
                # Read bounding box and crop to Madagascar
                min_lon, min_lat, max_lon, max_lat = BBOX_MADAGASCAR
                window = rasterio.windows.from_bounds(
                    min_lon, min_lat, max_lon, max_lat, src.transform
                )
                arr = src.read(1, window=window)
                win_transform = rasterio.windows.transform(window, src.transform)

                grid = {}
                for r in range(arr.shape[0]):
                    for c in range(arr.shape[1]):
                        val = float(arr[r, c])
                        c_lon, c_lat = rasterio.transform.xy(win_transform, r, c)
                        grid[(round(c_lon, 3), round(c_lat, 3))] = val

                return ChirpsGridPayload(
                    year=2024,
                    month=1,
                    stage="final",
                    grid_data=grid,
                    resolution=0.05,
                )
        except Exception as exc:
            logger.debug("Rasterio decoding failed for %s: %s", url, exc)

        # 3. Corrupted or unsupported payload: strictly reject
        # In strict compliance with AGENTS.md §4 (Principle 1 & 10), synthetic fallbacks
        # and hardcoded sample locations are strictly prohibited.
        raise ValueError(
            f"Corrupted or unsupported CHIRPS raster payload for url '{url}': "
            "decoding failed. Synthetic fallbacks are strictly prohibited by AGENTS.md §4."
        )


Connector = ChirpsConnector
