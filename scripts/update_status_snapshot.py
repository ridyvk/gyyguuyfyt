#!/usr/bin/env python3
"""Refresh update-status.json from the generated company universe and missing report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    missing = load_json(DATA_DIR / "missing-companies.json", {})
    financials = load_json(DATA_DIR / "financials.json", {"records": {}})
    previous = load_json(DATA_DIR / "update-status.json", {})

    target = int(missing.get("targetCompanies") or 0)
    implemented = int(missing.get("implementedCompanies") or len(financials.get("records", {})))
    missing_count = int(missing.get("missingCompanies") or max(target - implemented, 0))
    coverage = round(implemented / target * 100, 2) if target else 0

    payload = {
        **previous,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "jpx-universe-edinet-ordinary-autofill",
        "status": "ready",
        "source": "JPX+EDINET+TDnet",
        "edinetMerged": True,
        "tdnetOverlay": previous.get("tdnetOverlay", True),
        "companies": implemented,
        "targetCompanies": target,
        "missingCompanies": missing_count,
        "ordinaryMissingCompanies": int(missing.get("ordinaryMissingCompanies") or 0),
        "newListingOrRecentIpo": int(missing.get("newListingOrRecentIpo") or 0),
        "separateModelCompanies": int(missing.get("separateModelCompanies") or 0),
        "coverageRatio": coverage,
        "message": (
            f"JPX上場企業ユニバースを更新し、対象{target:,}社中"
            f"{implemented:,}社を取得済み、未取得{missing_count:,}社。"
            f"普通企業の未取得は{int(missing.get('ordinaryMissingCompanies') or 0):,}社。"
        ),
    }

    (DATA_DIR / "update-status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "status companies={companies} target={target} missing={missing} coverage={coverage}".format(
            companies=implemented,
            target=target,
            missing=missing_count,
            coverage=coverage,
        )
    )


if __name__ == "__main__":
    main()
