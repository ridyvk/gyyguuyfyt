from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.split_financials import (
    UNKNOWN_INDUSTRY,
    build_split_payloads,
    check_split,
    company_industries,
    write_split,
)


class FinancialShardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = {
            "schemaVersion": 3,
            "generatedAt": "2026-06-21T00:00:00Z",
            "source": "EDINET+TDnet",
            "status": "ready",
            "message": "fixture",
            "records": {
                "1001": {"code": "1001", "metrics": {"roe": {"value": 8.0}}},
                "2001": {"code": "2001", "metrics": {"roe": {"value": 9.0}}},
                "9999": {"code": "9999", "metrics": {"roe": {"value": 7.0}}},
            },
            "stats": {"companies": 3},
        }
        self.master = {
            "companies": [
                {"code": "1001", "industry": "水産・農林業"},
                {"code": "2001", "industry": "建設業"},
            ]
        }

    def test_split_reconstructs_every_record_exactly_once(self) -> None:
        manifest, shards = build_split_payloads(
            self.snapshot,
            company_industries(self.master),
        )

        self.assertEqual(manifest["recordCount"], 3)
        self.assertEqual(len(shards), 3)
        self.assertNotIn("records", manifest["snapshot"])
        self.assertEqual(manifest["snapshot"]["stats"], {"companies": 3})

        reconstructed = {}
        for shard in shards.values():
            for code, record in shard["records"].items():
                self.assertNotIn(code, reconstructed)
                reconstructed[code] = record
        self.assertEqual(reconstructed, self.snapshot["records"])
        self.assertIn(
            UNKNOWN_INDUSTRY,
            {entry["industry"] for entry in manifest["shards"]},
        )

    def test_write_and_check_remove_stale_shards(self) -> None:
        manifest, shards = build_split_payloads(
            self.snapshot,
            company_industries(self.master),
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "industry-99.json").write_text("{}", encoding="utf-8")

            write_split(output, manifest, shards)
            check_split(output, manifest, shards)

            self.assertFalse((output / "industry-99.json").exists())
            self.assertTrue((output / "manifest.json").exists())
            self.assertEqual(
                {path.name for path in output.glob("industry-*.json")},
                set(shards),
            )

    def test_check_rejects_duplicate_or_modified_output(self) -> None:
        manifest, shards = build_split_payloads(
            self.snapshot,
            company_industries(self.master),
        )

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_split(output, manifest, shards)
            shard_path = output / next(iter(shards))
            payload = json.loads(shard_path.read_text(encoding="utf-8"))
            payload["records"]["1001"] = {"code": "1001", "metrics": {}}
            shard_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "stale"):
                check_split(output, manifest, shards)


if __name__ == "__main__":
    unittest.main()
