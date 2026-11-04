"""Offline comparison of two original WB editions; no ingestion or qualification."""

import csv
import hashlib
import io
import json
import sys
import zipfile
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

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
VARIABLE = "c_rice"
EDITIONS = (
    (
        "b7af62d6f8825582bcbaea73041fc1c3bbc5932abac5266b54fffdcd38f9a63d",
        "MDG_RTFP_mkt_2007_2026-09-28.csv",
    ),
    (
        "43a59a06bac8609e2f845b6ce8d210b4c66065f8a7d0aa990ba6f74be80dbc83",
        "MDG_RTFP_mkt_2007_2026-10-05.csv",
    ),
)


def read_edition(path, expected_sha, member_name, max_uncompressed=64 * 1024 * 1024):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("archive_size_outside_bounds")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("original_archive_digest_mismatch")
    values, seen, currencies = {}, set(), set()
    missing = invalid = total = 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != member_name:
            raise ValueError("archive_layout_not_accepted")
        member = members[0]
        if member.flag_bits & 1 or not 0 < member.file_size <= max_uncompressed:
            raise ValueError("archive_member_outside_bounds")
        inner_hash = hashlib.sha256()
        with archive.open(member) as stream:
            size = 0
            while chunk := stream.read(65536):
                size += len(chunk)
                if size > max_uncompressed:
                    raise ValueError("archive_member_outside_bounds")
                inner_hash.update(chunk)
        if size != member.file_size:
            raise ValueError("archive_member_size_mismatch")
        with archive.open(member) as stream:
            reader = csv.DictReader(
                io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            )
            if not {*GRAIN, VARIABLE}.issubset(reader.fieldnames or []):
                raise ValueError("archive_schema_drift")
            for row in reader:
                total += 1
                if total > 500000 or row["ISO3"] != "MDG":
                    raise ValueError("country_or_row_scope_not_accepted")
                if (
                    not row["geo_id"]
                    or not row["currency"]
                    or date.fromisoformat(row["price_date"]).day != 1
                ):
                    raise ValueError("source_identity_incomplete")
                key = tuple(row[field] for field in GRAIN)
                if key in seen:
                    raise ValueError("ambiguous_source_grain")
                seen.add(key)
                currencies.add(row["currency"])
                raw = row[VARIABLE]
                if raw == "":
                    missing += 1
                    continue
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    invalid += 1
                    continue
                if not value.is_finite():
                    invalid += 1
                    continue
                values[key] = (value, raw, total, reader.line_num)
    return values, {
        "archive_sha256": expected_sha,
        "member": member_name,
        "member_sha256": inner_hash.hexdigest(),
        "member_bytes": size,
        "rows": total,
        "valid_estimates": len(values),
        "missing_estimates": missing,
        "invalid_estimates": invalid,
        "currencies": sorted(currencies),
        "crc_verified": True,
    }


def compare(old, new):
    common = old.keys() & new.keys()
    changed = sorted(key for key in common if old[key][0] != new[key][0])
    # Current price_value SQL contract is NUMERIC(18,4); retain the raw lexemes.
    quantum = Decimal("0.0001")
    storage_changed = [
        key
        for key in changed
        if old[key][0].quantize(quantum, rounding=ROUND_HALF_UP)
        != new[key][0].quantize(quantum, rounding=ROUND_HALF_UP)
    ]
    lexical = sum(
        old[key][1] != new[key][1] and old[key][0] == new[key][0] for key in common
    )
    sample = [
        {
            "grain": dict(zip(GRAIN, key, strict=True)),
            "old_price_raw": old[key][1],
            "new_price_raw": new[key][1],
            "old_data_row": old[key][2],
            "new_data_row": new[key][2],
            "old_csv_line": old[key][3],
            "new_csv_line": new[key][3],
        }
        for key in storage_changed[:30]
    ]
    return {
        "common_valid_grains": len(common),
        "numeric_revision_candidates": len(changed),
        "storage_scale4_revision_candidates": len(storage_changed),
        "lexical_only_changes": lexical,
        "old_only_valid_estimates": len(old.keys() - new.keys()),
        "new_only_valid_estimates": len(new.keys() - old.keys()),
        "changed_sample": sample,
    }


def main():
    root = Path(sys.argv[1])
    pairs = [
        read_edition(root / (digest + ".zip"), digest, member)
        for digest, member in EDITIONS
    ]
    result = compare(pairs[0][0], pairs[1][0])
    result.update(
        editions=[item[1] for item in pairs],
        variable=VARIABLE,
        value_kind="imputed",
        statistic="publisher_modeled_close",
        source_unit_reference="KG / ticker rice / study MDG_2021_RTFP_v02_M metadata",
        unit_reference_sha256="4a9e254e14c65ca5d3c85d69362f94ca4ccaf46b8e68cfbf88f300df6c122860",
        authentic_revision_qualified=False,
        silver_imported=False,
        scope="Original bytes and numeric comparison only; rights, annotations and replay reception remain separate",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
