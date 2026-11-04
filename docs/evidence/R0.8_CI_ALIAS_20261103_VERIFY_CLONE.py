"""Verify an isolated alias-only correction from native raw snapshots."""

import gzip
import hashlib
import json
import sys
from pathlib import Path


def read(path):
    return json.loads(
        gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    )


def digest(rows):
    result = hashlib.sha256()
    for row in sorted(rows):
        encoded = row.encode()
        result.update(len(encoded).to_bytes(8, "big"))
        result.update(encoded)
    return result.hexdigest()


def verify(before, after, parent, child):
    assert before["revision"] == "0027_quarantined_normalization_copies"
    assert after["revision"] == "0028_ambiguous_milled_rice_alias"
    assert (
        before["database"]
        == after["database"]
        == child["database"]
        == "ketrika_restore_alias_20261103"
    )
    assert parent["database"] == "ketrika_restore_final_20261103"
    assert all(item["read_only"] for item in (before, after, parent, child))
    assert before["tables"].keys() == after["tables"].keys()
    assert len(before["tables"]) == 40
    for name, original in before["tables"].items():
        expected = dict(original)
        if name == "ref.product_alias":
            expected["raw_sha256"] = after["tables"][name]["raw_sha256"]
        assert after["tables"][name] == expected, name
    assert before["quarantines"] == after["quarantines"]
    assert len(after["quarantines"]) == 6229
    for snapshot, aliases in ((before, parent), (after, child)):
        assert digest(aliases["rows"]) == snapshot["tables"]["ref.product_alias"]["raw_sha256"]
    old_rows = {json.loads(row)["alias_id"]: row for row in parent["rows"]}
    new_rows = {json.loads(row)["alias_id"]: row for row in child["rows"]}
    assert old_rows.keys() == new_rows.keys()
    assert parent["local_product_id"] == child["local_product_id"]
    changed = 0
    for identity, raw in old_rows.items():
        original, current = json.loads(raw), json.loads(new_rows[identity])
        selected = (
            original["alias_norm"] == "rice_milled"
            and original["product_id"] == parent["local_product_id"]
            and original["source_id"] is None
            and original["human_reviewed"] is False
            and original["confidence"] > 0.8
        )
        if selected:
            assert current == dict(original, confidence=0.8)
            changed += 1
        else:
            assert new_rows[identity] == raw
    assert changed == 1
    return {
        "passed": True,
        "protected_tables": 40,
        "fully_unchanged_tables": 39,
        "alias_rows": len(old_rows),
        "downgraded_unreviewed_global_aliases": changed,
        "quarantines_unchanged": 6229,
        "owners_and_permissions_unchanged": True,
        "active_database_modified": False,
        "scope": "isolated SQL metadata correction, not deployment/source/model qualification",
    }


if __name__ == "__main__":
    print(json.dumps(verify(*(read(Path(path)) for path in sys.argv[1:])), sort_keys=True))
