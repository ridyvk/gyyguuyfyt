#!/usr/bin/env python3
"""Split the financial snapshot into deterministic JPX industry shards."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "public" / "data" / "financials.json"
DEFAULT_COMPANY_MASTER = ROOT / "src" / "data" / "listedCompanies.json"
DEFAULT_OUTPUT = ROOT / "public" / "data" / "financials"

SCHEMA_VERSION = 1
UNKNOWN_INDUSTRY = "業種不明"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def company_industries(company_master: dict[str, Any]) -> dict[str, str]:
    companies = company_master.get("companies")
    if not isinstance(companies, list):
        raise ValueError("Company master must contain a companies array")

    mapping: dict[str, str] = {}
    for company in companies:
        if not isinstance(company, dict):
            continue
        code = str(company.get("code") or "")
        industry = str(company.get("industry") or "")
        if code and industry:
            mapping[code] = industry
    if not mapping:
        raise ValueError("Company master does not contain usable company industries")
    return mapping


def build_split_payloads(
    snapshot: dict[str, Any],
    industry_by_code: dict[str, str],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    records = snapshot.get("records")
    if not isinstance(records, dict):
        raise ValueError("Financial snapshot must contain a records object")

    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    for raw_code, record in records.items():
        code = str(raw_code)
        grouped[industry_by_code.get(code, UNKNOWN_INDUSTRY)][code] = record

    industries = sorted(grouped, key=lambda value: (value == UNKNOWN_INDUSTRY, value))
    generated_at = snapshot.get("generatedAt")
    metadata = {key: value for key, value in snapshot.items() if key != "records"}
    shards: dict[str, dict[str, Any]] = {}
    shard_entries: list[dict[str, Any]] = []

    for index, industry in enumerate(industries, start=1):
        filename = f"industry-{index:02d}.json"
        industry_records = dict(sorted(grouped[industry].items()))
        shards[filename] = {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "industry": industry,
            "records": industry_records,
        }
        shard_entries.append(
            {
                "industry": industry,
                "file": filename,
                "recordCount": len(industry_records),
            }
        )

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": generated_at,
        "recordCount": len(records),
        "snapshot": metadata,
        "shards": shard_entries,
    }
    return manifest, shards


def encoded_json(payload: dict[str, Any], *, compact: bool) -> str:
    if compact:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        ) + "\n"
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_split(
    output_dir: Path,
    manifest: dict[str, Any],
    shards: dict[str, dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    expected_files = set(shards)
    for stale_path in output_dir.glob("industry-*.json"):
        if stale_path.name not in expected_files:
            stale_path.unlink()

    for filename, payload in shards.items():
        write_atomic(output_dir / filename, encoded_json(payload, compact=True))
    write_atomic(
        output_dir / "manifest.json",
        encoded_json(manifest, compact=False),
    )


def check_split(
    output_dir: Path,
    manifest: dict[str, Any],
    shards: dict[str, dict[str, Any]],
) -> None:
    actual_manifest = load_json(output_dir / "manifest.json")
    if actual_manifest != manifest:
        raise ValueError("Financial shard manifest is stale")

    reconstructed: dict[str, Any] = {}
    expected_files = set(shards)
    actual_files = {path.name for path in output_dir.glob("industry-*.json")}
    if actual_files != expected_files:
        raise ValueError("Financial shard file set does not match the manifest")

    for filename, expected_payload in shards.items():
        actual_payload = load_json(output_dir / filename)
        if actual_payload != expected_payload:
            raise ValueError(f"Financial shard is stale: {filename}")
        for code, record in actual_payload["records"].items():
            if code in reconstructed:
                raise ValueError(f"Duplicate company across shards: {code}")
            reconstructed[code] = record

    if len(reconstructed) != manifest["recordCount"]:
        raise ValueError("Financial shard record count does not match the source")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--company-master", type=Path, default=DEFAULT_COMPANY_MASTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify existing shards instead of writing them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_json(args.snapshot)
    industry_by_code = company_industries(load_json(args.company_master))
    manifest, shards = build_split_payloads(snapshot, industry_by_code)

    if args.check:
        check_split(args.output, manifest, shards)
        action = "Verified"
    else:
        write_split(args.output, manifest, shards)
        check_split(args.output, manifest, shards)
        action = "Wrote"

    print(
        f"{action} {len(shards)} financial industry shards "
        f"covering {manifest['recordCount']} records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
