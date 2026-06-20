#!/usr/bin/env python3
"""Build a stricter TDnet-only full-year earnings KPI snapshot.

This updater intentionally favors correctness over coverage:
- only full-year TDnet earnings releases are accepted
- quarterly/interim releases are skipped
- EDINET records are never merged into the public snapshot
- broad/ambiguous revenue tags such as OrdinaryIncome are not used as sales
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from update_edinet_financials import (
    INVENTORY_COMPONENTS,
    add_metric,
    at,
    growth,
    percent,
    period_before,
    previous,
    roe_for_period,
)
from update_tdnet_financials import (
    BASE_URL,
    COMPANY_MASTER,
    JST,
    SNAPSHOT,
    TDNET_DEBT_COMPONENTS,
    TDNET_VALUATION_FACT_NAMES,
    filing_timestamp,
    get,
    is_actual_consolidated,
    parse_inline_xbrl,
    parse_list_page,
)
from data_quality import (
    context_rank as quality_context_rank,
    normalize_security_code,
    select_preferred_values,
)

STRICT_TDNET_FACT_NAMES = {
    "revenue": (
        "NetSales",
        "NetSalesSummaryOfBusinessResults",
        "Revenue",
        "RevenueIFRS",
        "RevenueFromContractsWithCustomers",
        "RevenueFromContractsWithCustomersIFRS",
        "OperatingRevenue1",
        "OperatingRevenue2",
        "GrossOperatingRevenue",
    ),
    "operatingIncome": (
        "OperatingIncome",
        "OperatingIncomeIFRS",
        "OperatingProfitLoss",
        "OperatingProfitLossIFRS",
    ),
    "disclosedRoe": (
        "RateOfReturnOnEquitySummaryOfBusinessResults",
    ),
    "profit": (
        "ProfitLossAttributableToOwnersOfParent",
        "ProfitLossAttributableToOwnersOfParentIFRS",
        "ProfitLoss",
        "ProfitLossIFRS",
        "NetIncomeLoss",
        "NetIncome",
        "ProfitLossSummaryOfBusinessResults",
    ),
    "operatingCf": (
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivitiesIFRS",
        "CashFlowsFromOperatingActivitiesIFRS",
        "NetCashProvidedByUsedInOperatingActivitiesIFRS",
    ),
    "equity": (
        "EquityAttributableToOwnersOfParent",
        "EquityAttributableToOwnersOfParentIFRS",
        "Equity",
        "EquityIFRS",
        "ShareholdersEquity",
        "NetAssets",
        "NetAssetsSummaryOfBusinessResults",
    ),
    "assets": (
        "Assets",
        "AssetsIFRS",
        "TotalAssets",
        "TotalAssetsSummaryOfBusinessResults",
    ),
    "cash": (
        "CashAndCashEquivalents",
        "CashAndCashEquivalentsIFRS",
        "CashAndDeposits",
    ),
    "inventory": (
        "Inventories",
        "InventoriesIFRS",
    ),
    "receivables": (
        "NotesAndAccountsReceivableTradeAndContractAssets",
        "NotesAndAccountsReceivableTrade",
        "AccountsReceivableTrade",
        "TradeAndOtherReceivablesCurrent",
        "TradeAndOtherReceivablesCurrentIFRS",
        "TradeAndOtherReceivablesCAIFRS",
    ),
    "debt": (
        "InterestBearingDebt",
        "InterestBearingLiabilities",
        "BondsAndBorrowings",
    ),
}

FULL_YEAR_EXCLUDED_TITLE_TOKENS = (
    "四半期",
    "中間",
    "第1四半期",
    "第１四半期",
    "第2四半期",
    "第２四半期",
    "第3四半期",
    "第３四半期",
    "Q1",
    "Q2",
    "Q3",
)

DURATION_KEYS = {
    "revenue",
    "operatingIncome",
    "profit",
    "operatingCf",
    "disclosedRoe",
}
FULL_YEAR_MIN_DAYS = 250
FULL_YEAR_MAX_DAYS = 460


def normalize_title(title: str) -> str:
    return title.translate(str.maketrans({"１": "1", "２": "2", "３": "3"})).upper()


def is_full_year_earnings_title(title: str) -> bool:
    normalized = normalize_title(title)
    if "決算短信" not in normalized:
        return False
    return not any(token.upper() in normalized for token in FULL_YEAR_EXCLUDED_TITLE_TOKENS)


def context_days(context: dict) -> int | None:
    try:
        if not context.get("start") or not context.get("end"):
            return None
        return (date.fromisoformat(context["end"]) - date.fromisoformat(context["start"])).days
    except (TypeError, ValueError):
        return None


def is_full_year_duration(context: dict) -> bool:
    days = context_days(context)
    return days is not None and FULL_YEAR_MIN_DAYS <= days <= FULL_YEAR_MAX_DAYS


def context_rank(context_id: str, context: dict, period_end: str, duration: bool) -> tuple[int, int, int, int, int]:
    return quality_context_rank(context_id, context, period_end, duration)


def values_for(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool,
) -> dict[str, float]:
    return select_preferred_values(
        contexts,
        facts,
        names,
        duration,
        duration_range=(FULL_YEAR_MIN_DAYS, FULL_YEAR_MAX_DAYS),
    )


def disclosed_or_calculated_tdnet_roe(
    disclosed_values: dict[str, float],
    profit_values: dict[str, float],
    equity_values: dict[str, float],
    period_end: str | None,
) -> float | None:
    if period_end is None:
        return None
    disclosed = at(disclosed_values, period_end)
    if disclosed is not None and math.isfinite(disclosed):
        # TDnet Inline XBRL exposes the displayed percentage (23.5 = 23.5%).
        return disclosed
    return roe_for_period(profit_values, equity_values, period_end)


def summed_values_for(
    contexts: dict,
    facts: dict,
    names: tuple[str, ...],
    duration: bool = False,
) -> dict[str, float]:
    result: dict[str, float] = defaultdict(float)
    for name in names:
        for period_end, value in values_for(contexts, facts, (name,), duration).items():
            result[period_end] += value
    return dict(result)


def infer_period_end(contexts: dict) -> str:
    candidates: list[str] = []
    for context_id, context in contexts.items():
        if not is_actual_consolidated(context_id, context):
            continue
        if "CurrentYear" not in context_id:
            continue
        if context.get("end") and is_full_year_duration(context):
            candidates.append(context["end"])
        elif context.get("instant"):
            candidates.append(context["instant"])
    if not candidates:
        raise ValueError("full-year TDnet reporting period was not found")
    return max(candidates)


def list_full_year_filings(days: int) -> tuple[dict[str, dict], dict[str, int]]:
    latest: dict[str, dict] = {}
    stats = {
        "tdnetRowsScanned": 0,
        "tdnetEarningsRows": 0,
        "tdnetQuarterlyRowsSkipped": 0,
        "tdnetFullYearFilings": 0,
    }
    today = datetime.now(JST).date()
    for offset in range(days):
        target = today - timedelta(days=offset)
        date_token = target.strftime("%Y%m%d")
        try:
            first_payload = get(f"{BASE_URL}/I_list_001_{date_token}.html")
        except Exception as error:
            if getattr(error, "code", None) == 404:
                continue
            raise
        rows, pages = parse_list_page(first_payload)
        all_rows = list(rows)
        for page in range(2, pages + 1):
            payload = get(f"{BASE_URL}/I_list_{page:03d}_{date_token}.html")
            page_rows, _ = parse_list_page(payload)
            all_rows.extend(page_rows)

        stats["tdnetRowsScanned"] += len(all_rows)
        for row in all_rows:
            title = row.get("title", "")
            if "決算短信" not in title:
                continue
            stats["tdnetEarningsRows"] += 1
            if not is_full_year_earnings_title(title):
                stats["tdnetQuarterlyRowsSkipped"] += 1
                continue
            code = normalize_security_code(row.get("code"))
            if not code:
                continue
            filed_at = filing_timestamp(target, row.get("time", ""))
            filing = {
                "code": code,
                "companyName": row.get("companyName", ""),
                "title": title,
                "filedAt": filed_at,
                "pdfUrl": f"{BASE_URL}/{row.get('titleHref', '')}",
                "xbrlUrl": f"{BASE_URL}/{row['xbrlHref']}",
                "documentId": Path(row["xbrlHref"]).stem,
            }
            current = latest.get(code)
            if current is None or (
                filed_at,
                filing["documentId"],
            ) > (
                current["filedAt"],
                current["documentId"],
            ):
                latest[code] = filing
        time.sleep(0.04)
    stats["tdnetFullYearFilings"] = len(latest)
    return latest, stats


def build_record(filing: dict, archive_data: bytes) -> dict:
    contexts, facts = parse_inline_xbrl(archive_data)
    period_end = infer_period_end(contexts)
    series = {
        key: values_for(contexts, facts, names, key in DURATION_KEYS)
        for key, names in STRICT_TDNET_FACT_NAMES.items()
    }
    if not series["debt"]:
        series["debt"] = summed_values_for(contexts, facts, TDNET_DEBT_COMPONENTS)
    if not series["inventory"]:
        series["inventory"] = summed_values_for(contexts, facts, INVENTORY_COMPONENTS)

    current = {key: at(values, period_end) for key, values in series.items()}
    prior = {key: previous(values, period_end) for key, values in series.items()}
    prior_profit_period_end = period_before(series["profit"], period_end)

    metrics: dict[str, dict] = {}
    add_metric(metrics, "revenueGrowth", growth(current["revenue"], prior["revenue"]))
    add_metric(
        metrics,
        "operatingMargin",
        percent(current["operatingIncome"], current["revenue"]),
        percent(prior["operatingIncome"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "netMargin",
        percent(current["profit"], current["revenue"]),
        percent(prior["profit"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "roe",
        disclosed_or_calculated_tdnet_roe(
            series["disclosedRoe"],
            series["profit"],
            series["equity"],
            period_end,
        ),
        disclosed_or_calculated_tdnet_roe(
            series["disclosedRoe"],
            series["profit"],
            series["equity"],
            prior_profit_period_end,
        ),
    )
    add_metric(
        metrics,
        "equityRatio",
        percent(current["equity"], current["assets"]),
        percent(prior["equity"], prior["assets"]),
    )
    add_metric(
        metrics,
        "operatingCfMargin",
        percent(current["operatingCf"], current["revenue"]),
        percent(prior["operatingCf"], prior["revenue"]),
    )
    add_metric(
        metrics,
        "debtRatio",
        None
        if current["debt"] is None
        or current["equity"] is None
        or current["equity"] <= 0
        else current["debt"] / current["equity"],
    )
    add_metric(
        metrics,
        "netCash",
        None
        if current["cash"] is None or current["debt"] is None
        else (current["cash"] - current["debt"]) / 100_000_000,
    )
    add_metric(metrics, "inventoryGrowth", growth(current["inventory"], prior["inventory"]))
    add_metric(metrics, "receivablesGrowth", growth(current["receivables"], prior["receivables"]))

    history = []
    for year_end in sorted(series["revenue"])[-3:]:
        revenue = series["revenue"].get(year_end)
        point = {
            "year": year_end[:7].replace("-", "/"),
            "revenue": round(revenue / 100_000_000) if revenue is not None else None,
            "operatingMargin": percent(series["operatingIncome"].get(year_end), revenue),
            "netMargin": percent(series["profit"].get(year_end), revenue),
            "roe": disclosed_or_calculated_tdnet_roe(
                series["disclosedRoe"],
                series["profit"],
                series["equity"],
                year_end,
            ),
            "operatingCfMargin": percent(series["operatingCf"].get(year_end), revenue),
        }
        if all(value is not None for value in point.values()):
            history.append(
                {
                    key: round(value, 2) if isinstance(value, float) else value
                    for key, value in point.items()
                }
            )
    for key in ("operatingMargin", "netMargin", "roe", "operatingCfMargin"):
        if key in metrics and history:
            metrics[key]["trend"] = [point[key] for point in history]

    valuation: dict[str, float] = {}
    eps = at(values_for(contexts, facts, TDNET_VALUATION_FACT_NAMES["eps"], True), period_end)
    forecast_eps = at(
        values_for(contexts, facts, TDNET_VALUATION_FACT_NAMES["forecastEps"], True),
        period_end,
    )
    bps = at(values_for(contexts, facts, TDNET_VALUATION_FACT_NAMES["bps"], False), period_end)
    if eps is not None and math.isfinite(eps):
        valuation["eps"] = round(eps, 4)
    if forecast_eps is not None and math.isfinite(forecast_eps):
        valuation["forecastEps"] = round(forecast_eps, 4)
    if bps is not None and math.isfinite(bps):
        valuation["bps"] = round(bps, 4)

    record = {
        "code": filing["code"],
        "companyName": filing["companyName"],
        "documentId": filing["documentId"],
        "documentType": "FullYearEarnings",
        "filedAt": filing["filedAt"],
        "periodEnd": period_end,
        "periodType": "annual",
        "source": "TDnet",
        "sourceDetail": "TDnet決算短信XBRL・通期のみ",
        "sourceUrl": filing["pdfUrl"],
        "title": filing["title"],
        "metrics": metrics,
        "history": history,
        "quality": {
            "policy": "strict-full-year-only",
            "roeModelVersion": 1,
            "quarterlySkipped": True,
            "edinetMerged": False,
            "ambiguousRevenueTagsExcluded": ["OrdinaryIncome"],
            "inventoryPolicy": "Inventoriesタグを優先し、無い場合は商品・製品、仕掛品、原材料等を合算",
        },
    }
    if valuation:
        record["valuation"] = valuation
    return record


def should_replace(existing: dict | None, record: dict) -> bool:
    if existing is None:
        return True
    old_key = (str(existing.get("periodEnd") or ""), str(existing.get("filedAt") or ""))
    return (record["periodEnd"], record["filedAt"]) >= old_key


def load_company_codes() -> set[str]:
    payload = json.loads(COMPANY_MASTER.read_text(encoding="utf-8"))
    return {str(company["code"]) for company in payload.get("companies", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-days", type=int, default=31)
    parser.add_argument("--max-documents", type=int, default=1500)
    args = parser.parse_args()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    current_codes = load_company_codes()
    old_records = snapshot.get("records", {}) or {}
    records = {
        code: record
        for code, record in old_records.items()
        if code in current_codes
        and isinstance(record, dict)
        and record.get("source") == "TDnet"
        and record.get("documentType") == "FullYearEarnings"
    }
    dropped_existing = len(old_records) - len(records)

    filings, scan_stats = list_full_year_filings(args.lookback_days)
    updated = 0
    failures: list[str] = []
    candidates = list(filings.values())[: args.max_documents]
    for index, filing in enumerate(candidates, 1):
        try:
            record = build_record(filing, get(filing["xbrlUrl"]))
            if (record.get("metrics") or record.get("valuation")) and should_replace(
                records.get(record["code"]),
                record,
            ):
                records[record["code"]] = record
                updated += 1
        except Exception as error:
            failures.append(f"{filing.get('code')}:{filing.get('documentId')}: {error}")
        if index % 50 == 0:
            print(f"Processed {index}/{len(candidates)}")
        time.sleep(0.06)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    snapshot.update(
        {
            "generatedAt": generated_at,
            "source": "TDnet",
            "status": "ready",
            "message": (
                "TDnet決算短信ベースで更新中。"
                "四半期・中間短信とEDINET有価証券報告書データは統合していません。"
            ),
            "dataPolicy": {
                "mode": "tdnet-only-full-year-strict",
                "primarySource": "TDnet決算短信XBRL",
                "acceptedDocumentType": "FullYearEarnings",
                "edinetMerged": False,
                "quarterlyMerged": False,
                "note": (
                    "年次KPIの齟齬を減らすため、TDnetの通期決算短信のみを公開します。"
                    "四半期・中間短信は対象期と年次KPIの混在を避けるため除外します。"
                ),
            },
            "records": records,
            "stats": {
                **snapshot.get("stats", {}),
                **scan_stats,
                "companies": len(records),
                "tdnetDocumentsUpdated": updated,
                "tdnetStrictFailures": len(failures),
                "nonStrictExistingRecordsDropped": dropped_existing,
            },
        }
    )
    SNAPSHOT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Saved {len(records)} strict full-year TDnet companies; "
        f"updated {updated}; skipped/failures {len(failures)}."
    )
    for failure in failures[:30]:
        print(f"warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
