"""Closed header of the two received official WB market-price archives."""

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field

from ketrika.core.schema_drift import SchemaInspection
from ketrika.core.wb_archive import MAX_ARCHIVE_BYTES, ArchiveError, _member_name, rows

COLUMNS = (
    "ISO3",
    "country",
    "adm1_name",
    "adm2_name",
    "mkt_name",
    "lat",
    "lon",
    "geo_id",
    "price_date",
    "year",
    "month",
    "currency",
    "components",
    "start_dense_data",
    "last_survey_point",
    "data_coverage",
    "data_coverage_recent",
    "index_confidence_score",
    "spatially_interpolated",
    "rice",
    "sugar",
    "wheat_flour",
    "o_rice",
    "h_rice",
    "l_rice",
    "c_rice",
    "inflation_rice",
    "trust_rice",
    "o_sugar",
    "h_sugar",
    "l_sugar",
    "c_sugar",
    "inflation_sugar",
    "trust_sugar",
    "o_wheat_flour",
    "h_wheat_flour",
    "l_wheat_flour",
    "c_wheat_flour",
    "inflation_wheat_flour",
    "trust_wheat_flour",
    "o_food_price_index",
    "h_food_price_index",
    "l_food_price_index",
    "c_food_price_index",
    "inflation_food_price_index",
    "trust_food_price_index",
)


@dataclass(frozen=True)
class WBArchiveSchemaContract:
    version: str = field(default="wb-rtfp-zip-csv-3.0.0", init=False)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(
            json.dumps([self.version, COLUMNS, 8, 64, 250000], separators=(",", ":")).encode()
        ).hexdigest()


def archive_member(content: bytes) -> str:
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_ARCHIVE_BYTES:
        raise ArchiveError("wb_archive_size_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != 1:
                raise ArchiveError("wb_archive_layout_invalid")
            return _member_name(names[0])
    except (zipfile.BadZipFile, OSError, ValueError):
        raise ArchiveError("wb_archive_layout_invalid") from None


def inspect_archive_schema(content: bytes, contract: WBArchiveSchemaContract) -> SchemaInspection:
    count = 0
    reason = None
    header: tuple[str, ...] = ()
    try:
        member = archive_member(content)
        for _, row in rows(content, member):
            header = tuple(row)
            if header != COLUMNS:
                raise ArchiveError("wb_archive_schema_drift")
            count += 1
    except ArchiveError as exc:
        reason = str(exc)
    return SchemaInspection(
        state="schema_drift" if reason else "verified",
        content_sha256=hashlib.sha256(content).hexdigest(),
        contract_sha256=contract.sha256,
        header_sha256=hashlib.sha256(json.dumps(header, separators=(",", ":")).encode()).hexdigest()
        if header
        else None,
        columns=len(header),
        rows=count,
        missing_columns=len(set(COLUMNS) - set(header)),
        unexpected_columns=len(set(header) - set(COLUMNS)),
        duplicate_columns=0,
        invalid_rows=int(reason is not None),
        reasons=(reason,) if reason else (),
    )
