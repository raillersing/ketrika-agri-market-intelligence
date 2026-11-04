"""Bounded original World Bank ZIP/CSV cell reader (ADR-162).

Never extracts files, performs network access, or infers observed prices.
Coordinates are logical data rows, starting at zero after the CSV header.
"""

from __future__ import annotations

import csv
import io
import re
import stat
import zipfile
import zlib
from collections.abc import Iterator, Mapping, Sequence
from datetime import date
from typing import Any

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ROWS = 250000
GRAIN = (
    "ISO3",
    "country",
    "adm1_name",
    "adm2_name",
    "mkt_name",
    "lat",
    "lon",
    "geo_id",
    "price_date",
    "currency",
)


class ArchiveError(ValueError):
    """Stable errors without collected text or local filesystem details."""


def _member_name(name: Any) -> str:
    if not isinstance(name, str):
        raise ArchiveError("wb_archive_member_invalid")
    match = re.fullmatch(r"MDG_RTFP_mkt_2007_(\d{4}-\d{2}-\d{2})\.csv", name)
    if not match:
        raise ArchiveError("wb_archive_member_invalid")
    try:
        date.fromisoformat(match[1])
    except ValueError:
        raise ArchiveError("wb_archive_member_invalid") from None
    return name


def rows(content: bytes, member: str) -> Iterator[tuple[int, Mapping[str, str]]]:
    """Validate the entire original when exhausted; yield source lexemes only."""
    _member_name(member)
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_ARCHIVE_BYTES:
        raise ArchiveError("wb_archive_size_invalid")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != member:
                raise ArchiveError("wb_archive_layout_invalid")
            item = members[0]
            mode = item.external_attr >> 16
            if (
                item.flag_bits & 1
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or not 0 < item.file_size <= MAX_MEMBER_BYTES
            ):
                raise ArchiveError("wb_archive_member_unsafe")
            # Reading to EOF verifies CRC. Bound actual output independently of metadata.
            with archive.open(item) as stream:
                body = stream.read(MAX_MEMBER_BYTES + 1)
                if len(body) > MAX_MEMBER_BYTES or len(body) != item.file_size:
                    raise ArchiveError("wb_archive_decompression_limit")
            reader = csv.reader(io.StringIO(body.decode("utf-8-sig"), newline=""), strict=True)
            headers = next(reader, [])
            if (
                not headers
                or len(headers) > 128
                or len(set(headers)) != len(headers)
                or any(not key or len(key) > 128 for key in headers)
                or not {*GRAIN, "c_rice"}.issubset(headers)
            ):
                raise ArchiveError("wb_archive_header_invalid")
            seen = set()
            count = 0
            for index, values in enumerate(reader):
                count += 1
                if count > MAX_ROWS:
                    raise ArchiveError("wb_archive_row_limit")
                if len(values) != len(headers) or any(len(value) > 4096 for value in values):
                    raise ArchiveError("wb_archive_row_invalid")
                row = dict(zip(headers, values, strict=True))
                if row["ISO3"] != "MDG" or not row["geo_id"] or not row["currency"]:
                    raise ArchiveError("wb_archive_identity_invalid")
                period = date.fromisoformat(row["price_date"])
                if period.day != 1:
                    raise ArchiveError("wb_archive_period_invalid")
                grain = tuple(row[key] for key in GRAIN)
                if grain in seen:
                    raise ArchiveError("wb_archive_duplicate_grain")
                seen.add(grain)
                yield index, row
            if not count:
                raise ArchiveError("wb_archive_empty")
    except ArchiveError:
        raise
    except (
        zipfile.BadZipFile,
        zlib.error,
        OSError,
        UnicodeError,
        csv.Error,
        ValueError,
        RuntimeError,
        NotImplementedError,
        OverflowError,
    ):
        raise ArchiveError("wb_archive_invalid") from None


def cells(content: bytes, coordinates: Sequence[Sequence[Any]]) -> dict[tuple[Any, ...], str]:
    """Resolve cells only after validating every row, including the unseen tail."""
    if not coordinates or len(coordinates) > 10000:
        raise ArchiveError("wb_archive_coordinates_invalid")
    requested: set[tuple[str, int, str]] = set()
    for coordinate in coordinates:
        if (
            len(coordinate) != 3
            or type(coordinate[1]) is not int
            or not 0 <= coordinate[1] < MAX_ROWS
            or not isinstance(coordinate[2], str)
            or not coordinate[2]
        ):
            raise ArchiveError("wb_archive_coordinates_invalid")
        key = (_member_name(coordinate[0]), coordinate[1], coordinate[2])
        if key in requested:
            raise ArchiveError("wb_archive_duplicate_cell")
        requested.add(key)
    members = {key[0] for key in requested}
    if len(members) != 1:
        raise ArchiveError("wb_archive_coordinates_invalid")
    member = next(iter(members))
    by_row: dict[int, list[str]] = {}
    for _, index, column in requested:
        by_row.setdefault(index, []).append(column)
    result: dict[tuple[Any, ...], str] = {}
    for index, row in rows(content, member):
        for column in by_row.get(index, []):
            if column not in row:
                raise ArchiveError("wb_archive_cell_missing")
            result[(member, index, column)] = row[column]
    if set(result) != requested:
        raise ArchiveError("wb_archive_cell_missing")
    return result
