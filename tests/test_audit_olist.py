"""Focused tests for the reusable Olist audit helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.audit_olist import discover_csv_files, schema_statistics, sha256_file


class DiscoverCsvFilesTests(unittest.TestCase):
    def test_discovers_only_top_level_csv_files_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "b.csv").write_text("id\n2\n", encoding="utf-8")
            (root / "A.CSV").write_text("id\n1\n", encoding="utf-8")
            (root / "notes.txt").write_text("not data", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "hidden.csv").write_text("id\n3\n", encoding="utf-8")

            self.assertEqual(
                [path.name for path in discover_csv_files(root)],
                ["A.CSV", "b.csv"],
            )


class Sha256Tests(unittest.TestCase):
    def test_sha256_matches_known_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample.csv"
            path.write_bytes(b"abc")

            self.assertEqual(
                sha256_file(path),
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            )


class SchemaStatisticsTests(unittest.TestCase):
    def test_reports_rows_nulls_uniques_duplicates_and_id_uniqueness(self) -> None:
        frame = pd.DataFrame(
            {
                "order_id": ["a", "b", "b", None],
                "status": ["ok", "ok", "ok", None],
                "amount": [10.0, 20.0, 20.0, None],
            }
        )

        result = schema_statistics(frame)
        columns = {column["name"]: column for column in result["columns"]}

        self.assertEqual(result["row_count"], 4)
        self.assertEqual(result["column_count"], 3)
        self.assertEqual(result["duplicate_row_count"], 1)
        self.assertEqual(columns["order_id"]["null_count"], 1)
        self.assertEqual(columns["order_id"]["unique_count"], 2)
        self.assertFalse(columns["order_id"]["non_null_unique"])
        self.assertEqual(columns["order_id"]["duplicate_non_null_rows"], 2)
        self.assertAlmostEqual(columns["status"]["null_percentage"], 25.0)


if __name__ == "__main__":
    unittest.main()
