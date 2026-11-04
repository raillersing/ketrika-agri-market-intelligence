"""Read-only revalidation of full authentic replay/counterproof originals."""

import gzip
import hashlib
import json
import sys
from pathlib import Path

from ketrika.core.rebuild_manifest import compare_manifests

root = Path(sys.argv[1])


def read(name):
    with gzip.open(root / name, "rt") as stream:
        return json.load(stream)


positive = read("R0.8_WB_ARCHIVE_20261104_REAL_REPLAY.json.gz")
negative = read("R0.8_WB_ARCHIVE_20261104_FALSE_PARSER.json.gz")
manual = json.loads((root / "R0.8_WB_ARCHIVE_20261104_ANNOTATIONS.json").read_text())
assert positive["replay_passed"] is True and positive["uid"] == 1000
assert compare_manifests(positive["before"], positive["after"])["content_identical"]
assert positive["diff"]["changed_tables"] == {}
assert positive["protected_before"] == positive["protected_after"]
assert positive["bronze_inventory_before"] == positive["bronze_inventory_after"]
assert positive["bronze_inventory_verified"] and positive["bronze_inventory_before"]["count"] == 4
for receipt in (positive, negative):
    assert (
        receipt["network_before"]
        == receipt["network_after"]
        == {
            "interfaces": ["lo"],
            "external_ipv4_routes": 0,
        }
    )
    stats = receipt["replay_stats"]
    assert stats["source_records_total"] == stats["source_records_replayed"] == 3
    assert stats["source_records_skipped"] == stats["records_rejected"] == 0
    assert receipt["model_qualified"] is False and receipt["human_reviewed"] is False

rows = positive["before"]["tables"]["obs.price_observation"]["rows"]
assert len(rows) == 163
assert sum(row["superseded_by"] != ["null"] for row in rows) == 81
assert all(
    row["observed_or_imputed"] == ["text", "imputed"] and row["actor_level"] == ["text", "unknown"]
    for row in rows
)
assert positive["before"]["tables"]["gold.price_obs_current"]["count"] == 82
references = {
    row["source_record_id"]: row["content_sha256"]
    for row in map(json.loads, positive["protected_before"]["tables"]["meta.source_record"]["rows"])
}
values = {
    (references[row["source_record_id"][1]], row["period_start"][1]): row["price_raw"][1]
    for row in rows
}
checked = 0
for edition in manual["editions"]:
    for index, expected in enumerate(edition["values"]):
        period = f"{2024 + index // 12:04}-{index % 12 + 1:02}-01"
        assert values[(edition["sha256"], period)] == expected
        checked += 1
assert checked == 60
recompute = positive["versioned_recompute"]
assert recompute["min_points_required"] == 36
assert recompute["recompute_equal"] and recompute["forecasts_recomputed"]
assert recompute["eligible_series"] == 1 and recompute["forecasts_generated"] == [3, 3]
assert negative["counterproof_passed"] and negative["deliberately_changed_values"] == 1
assert negative["replay_passed"] is False
counter_diff = compare_manifests(negative["before"], negative["after"])
assert counter_diff["content_identical"] is False
assert set(counter_diff["changed_tables"]) == {"obs.price_observation"}
assert (
    negative["before"]["tables"]["obs.price_observation"]["count"]
    == negative["after"]["tables"]["obs.price_observation"]["count"]
    == 163
)
assert negative["protected_before"] == negative["protected_after"]
assert negative["bronze_inventory_verified"]
report = {
    "verified": True,
    "price_rows": 163,
    "revision_links": 81,
    "current_gold_rows": 82,
    "independent_numeric_annotations_in_sql": checked,
    "positive_manifests_identical": True,
    "bronze_objects_unchanged": 4,
    "negative_changed_values": 1,
    "negative_counts_identical": 163,
    "negative_changed_tables": sorted(counter_diff["changed_tables"]),
    "versioned_recompute_equal": True,
    "separate_forecasts_each_run": 3,
    "min_points_required": 36,
    "model_qualified": False,
    "human_reviewed": False,
    "source_freshness_qualified": False,
    "original_s3_versions_verified": False,
    "originals_sha256": {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in (
            "R0.8_WB_ARCHIVE_20261104_REAL_REPLAY.json.gz",
            "R0.8_WB_ARCHIVE_20261104_FALSE_PARSER.json.gz",
        )
    },
}
print(json.dumps(report, indent=2))
