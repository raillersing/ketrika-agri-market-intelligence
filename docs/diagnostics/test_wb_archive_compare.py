import csv
import hashlib
import io
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

from wb_archive_compare import GRAIN, compare, read_edition


class ArchiveComparisonTests(unittest.TestCase):
    def test_sub_storage_precision_change_is_not_a_stored_price_correction(self):
        key = tuple("synthetic" for _ in GRAIN)
        result = compare(
            {key: (Decimal("1.00000001"), "1.00000001", 1, 2)},
            {key: (Decimal("1.00000002"), "1.00000002", 1, 2)},
        )
        self.assertEqual(result["numeric_revision_candidates"], 1)
        self.assertEqual(result["storage_scale4_revision_candidates"], 0)
        self.assertEqual(result["changed_sample"], [])

    def write(self, root, name, prices, currency="MGA"):
        text = io.StringIO(newline="")
        writer = csv.DictWriter(text, fieldnames=[*GRAIN, "c_rice"])
        writer.writeheader()
        for month, value in prices:
            row = dict.fromkeys(GRAIN, "synthetic")
            row.update(ISO3="MDG", price_date=month, currency=currency, c_rice=value)
            writer.writerow(row)
        path = root / (name + ".zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name + ".csv", text.getvalue())
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), name + ".csv"

    def test_numeric_revision_is_not_new_period_or_lexical_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = read_edition(
                *self.write(root, "old", [("2026-01-01", "1"), ("2026-02-01", "2.0")])
            )
            new, _ = read_edition(
                *self.write(
                    root,
                    "new",
                    [
                        ("2026-01-01", "1.25"),
                        ("2026-02-01", "2.00"),
                        ("2026-03-01", "3"),
                    ],
                )
            )
            result = compare(old, new)
            self.assertEqual(result["common_valid_grains"], 2)
            self.assertEqual(result["numeric_revision_candidates"], 1)
            self.assertEqual(result["lexical_only_changes"], 1)
            self.assertEqual(result["new_only_valid_estimates"], 1)
            self.assertEqual(result["changed_sample"][0]["old_price_raw"], "1")

    def test_currency_change_does_not_create_same_grain_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, _ = read_edition(*self.write(root, "old", [("2026-01-01", "1")]))
            new, _ = read_edition(
                *self.write(root, "new", [("2026-01-01", "2")], currency="USD")
            )
            self.assertEqual(compare(old, new)["numeric_revision_candidates"], 0)

    def test_missing_is_not_zero_and_duplicate_grain_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values, stats = read_edition(
                *self.write(root, "zero", [("2026-01-01", "0"), ("2026-02-01", "")])
            )
            self.assertEqual(stats["missing_estimates"], 1)
            self.assertEqual(len(values), 1)
            self.assertEqual(next(iter(values.values()))[0], 0)
            with self.assertRaisesRegex(ValueError, "ambiguous_source_grain"):
                read_edition(
                    *self.write(
                        root, "duplicate", [("2026-01-01", "1"), ("2026-01-01", "2")]
                    )
                )

    def test_original_digest_and_decompression_bounds_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.write(Path(directory), "original", [("2026-01-01", "1")])
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                read_edition(args[0], "0" * 64, args[2])
            with self.assertRaisesRegex(ValueError, "member_outside_bounds"):
                read_edition(*args, max_uncompressed=1)


if __name__ == "__main__":
    unittest.main()
