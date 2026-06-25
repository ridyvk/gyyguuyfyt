#!/usr/bin/env python3
"""Classify companies that are present in the app universe but missing KPI records."""

from __future__ import annotations

import glob
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"

EXCLUDED_INDUSTRIES = {
    "銀行業",
    "保険業",
    "証券、商品先物取引業",
    "その他金融業",
}

EXCLUDED_NAME_PATTERNS = (
    "ETF",
    "ＥＴＦ",
    "ETN",
    "ＥＴＮ",
    "REIT",
    "リート",
    "投資法人",
    "インフラファンド",
    "種類株式",
    "優先株",
    "社債型",
)


def load_universe() -> list[dict[str, str]]:
    files = sorted(glob.glob(str(ASSETS_DIR / "companyUniverse-*.js")))
    if not files:
        raise FileNotFoundError("assets/companyUniverse-*.js was not found")

    text = Path(files[0]).read_text(encoding="utf-8")
    pattern = re.compile(
        r"\{code:`(?P<code>[^`]+)`,name:`(?P<name>[^`]+)`,market:`(?P<market>[^`]+)`,industry:`(?P<industry>[^`]+)`\}"
    )
    return [match.groupdict() for match in pattern.finditer(text)]


def load_financials() -> dict:
    path = DATA_DIR / "financials.json"
    if not path.exists():
        return {"records": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def is_security_like(company: dict[str, str]) -> bool:
    code = company["code"]
    name = company["name"]
    industry = company["industry"]

    if len(code) > 4 and not re.fullmatch(r"\d{3}[A-Z]", code):
        return True
    if industry in EXCLUDED_INDUSTRIES:
        return True
    return any(token in name for token in EXCLUDED_NAME_PATTERNS)


def classify(company: dict[str, str]) -> str:
    if is_security_like(company):
        return "separate-model"
    if re.fullmatch(r"\d{3}[A-Z]", company["code"]):
        return "new-listing-or-recent-ipo"
    return "ordinary-company"


def main() -> None:
    universe = load_universe()
    financials = load_financials()
    records = financials.get("records", {})

    missing = []
    by_reason: dict[str, list[dict[str, str]]] = {}
    for company in universe:
        if company["code"] in records:
            continue
        reason = classify(company)
        item = {**company, "reason": reason}
        missing.append(item)
        by_reason.setdefault(reason, []).append(item)

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "targetCompanies": len(universe),
        "implementedCompanies": len(records),
        "missingCompanies": len(missing),
        "ordinaryMissingCompanies": len(by_reason.get("ordinary-company", [])),
        "newListingOrRecentIpo": len(by_reason.get("new-listing-or-recent-ipo", [])),
        "separateModelCompanies": len(by_reason.get("separate-model", [])),
        "reasons": by_reason,
        "missing": missing,
        "policy": {
            "ordinary-company": "Run the EDINET annual-report fallback parser first.",
            "new-listing-or-recent-ipo": "Keep in the universe and pick up automatically once annual data appears.",
            "separate-model": "Do not force company KPI scoring; use a bank, REIT, fund, or special-security model.",
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "missing-companies.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "missing={missing} ordinary={ordinary} recent={recent} separate={separate}".format(
            missing=payload["missingCompanies"],
            ordinary=payload["ordinaryMissingCompanies"],
            recent=payload["newListingOrRecentIpo"],
            separate=payload["separateModelCompanies"],
        )
    )


if __name__ == "__main__":
    main()
