#!/usr/bin/env python3
"""Build KPI Scope's disclosure radar from TDnet and EDINET metadata.

The output intentionally contains metadata and explainable title-based signals only.
It never presents an inferred numeric revision as a value extracted from a filing.
"""

from __future__ import annotations

import argparse
import html.parser
import json
import os
import re
import time
import urllib.error
import urllib.parse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from data_quality import normalize_security_code
from update_edinet_financials import API as EDINET_API
from update_edinet_financials import get as get_edinet
from update_tdnet_financials import BASE_URL as TDNET_BASE_URL
from update_tdnet_financials import get as get_tdnet

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public/data/disclosures.json"
SHARD_DIR = ROOT / "public/data/disclosures"
SHARD_MANIFEST = SHARD_DIR / "manifest.json"
DEFAULT_SHARD_SIZE = 400
MASTER = ROOT / "src/data/listedCompanies.json"
FINANCIALS = ROOT / "public/data/financials.json"
JST = timezone(timedelta(hours=9))

CATEGORY_LABELS = {
    "earnings": "決算",
    "guidance": "業績予想",
    "dividend": "配当",
    "buyback": "自己株式",
    "ma": "M&A・提携",
    "capital": "資本政策",
    "finance": "資金調達",
    "governance": "ガバナンス",
    "personnel": "人事",
    "large-holding": "大量保有",
    "annual-report": "法定開示",
    "correction": "訂正",
    "other": "その他",
}

SUMMARY_TEMPLATES = {
    "earnings": "決算実績と今後の見通しに関する開示です。",
    "guidance": "会社業績予想の変更に関する開示です。",
    "dividend": "株主還元・配当方針に関する開示です。",
    "buyback": "自己株式の取得・消却に関する開示です。",
    "ma": "買収、売却、提携など事業構造に関する開示です。",
    "capital": "株式数や資本構成に影響する開示です。",
    "finance": "資金調達や財務方針に関する開示です。",
    "governance": "統治体制、監査、上場管理に関する開示です。",
    "personnel": "経営体制や主要人事に関する開示です。",
    "large-holding": "株主構成の変化を確認するための法定開示です。",
    "annual-report": "有価証券報告書などの法定開示です。",
    "correction": "過去に提出した開示の訂正・差替えです。",
    "other": "企業が公表した適時・法定開示です。",
}


def compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_datetime(value: object, default_tz=JST) -> datetime | None:
    text = compact_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M"):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except ValueError:
                continue
        else:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(JST)


def iso_datetime(value: object, fallback_date: date | None = None) -> str:
    parsed = parse_datetime(value)
    if parsed is None and fallback_date is not None:
        parsed = datetime.combine(fallback_date, datetime.min.time(), tzinfo=JST)
    return (parsed or datetime.now(JST)).isoformat(timespec="seconds")


def load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_sharded_snapshot(manifest_path: Path = SHARD_MANIFEST) -> dict:
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise ValueError("disclosure shard manifest could not be read") from error
    if int(manifest.get("schemaVersion") or 0) != 1:
        raise ValueError("disclosure shard manifest schemaVersion must be 1")
    snapshot = dict(manifest.get("snapshot") or {})
    events: list[dict] = []
    for entry in manifest.get("shards") or []:
        filename = compact_text((entry or {}).get("file"))
        if not re.fullmatch(r"chunk-\d{3}\.json", filename):
            raise ValueError(f"invalid disclosure shard filename: {filename}")
        try:
            payload = json.loads(
                (manifest_path.parent / filename).read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError, OSError) as error:
            raise ValueError(f"disclosure shard could not be read: {filename}") from error
        if payload.get("generatedAt") != manifest.get("generatedAt"):
            raise ValueError(f"disclosure shard generation mismatch: {filename}")
        shard_events = payload.get("events")
        if not isinstance(shard_events, list):
            raise ValueError(f"disclosure shard events are invalid: {filename}")
        if len(shard_events) != int((entry or {}).get("eventCount") or 0):
            raise ValueError(f"disclosure shard count mismatch: {filename}")
        events.extend(shard_events)
    if len(events) != int(manifest.get("eventCount") or 0):
        raise ValueError("disclosure manifest event count mismatch")
    return {**snapshot, "events": events}


def load_existing_snapshot(output: Path) -> dict:
    snapshot = load_json(output, {})
    if isinstance(snapshot.get("events"), list):
        return snapshot
    if output.resolve() == OUTPUT.resolve():
        sharded = load_sharded_snapshot()
        if sharded:
            return sharded
    return {"events": []}


def write_sharded_snapshot(
    snapshot: dict,
    shard_dir: Path = SHARD_DIR,
    shard_size: int = DEFAULT_SHARD_SIZE,
) -> dict:
    shard_dir.mkdir(parents=True, exist_ok=True)
    events = snapshot.get("events") or []
    shards: list[dict] = []
    expected_files: set[str] = set()
    for index, start in enumerate(range(0, len(events), max(1, shard_size)), 1):
        filename = f"chunk-{index:03d}.json"
        expected_files.add(filename)
        shard_events = events[start : start + max(1, shard_size)]
        payload = {
            "schemaVersion": 1,
            "generatedAt": snapshot.get("generatedAt"),
            "events": shard_events,
        }
        (shard_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        shards.append(
            {
                "file": filename,
                "eventCount": len(shard_events),
                "firstFiledAt": shard_events[0].get("filedAt") if shard_events else None,
                "lastFiledAt": shard_events[-1].get("filedAt") if shard_events else None,
            }
        )
    for stale_path in shard_dir.glob("chunk-*.json"):
        if stale_path.name not in expected_files:
            stale_path.unlink()
    snapshot_metadata = {
        key: value for key, value in snapshot.items() if key != "events"
    }
    manifest = {
        "schemaVersion": 1,
        "generatedAt": snapshot.get("generatedAt"),
        "eventCount": len(events),
        "snapshot": snapshot_metadata,
        "shards": shards,
    }
    (shard_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return manifest


def persist_snapshot(snapshot: dict, output: Path) -> None:
    if output.resolve() == OUTPUT.resolve():
        write_sharded_snapshot(snapshot)
        output.unlink(missing_ok=True)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def company_master() -> dict[str, str]:
    payload = load_json(MASTER, {"companies": []})
    return {
        str(company.get("code")): compact_text(company.get("name"))
        for company in payload.get("companies", [])
        if normalize_security_code(company.get("code"))
    }


class TDnetDisclosureParser(html.parser.HTMLParser):
    """Parse all TDnet rows, including PDF-only disclosures."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self.row: dict[str, str] | None = None
        self.field: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self.row = {}
            return
        if self.row is None:
            return
        if tag == "td":
            classes = set((attributes.get("class") or "").split())
            for field, class_name in (
                ("time", "kjTime"),
                ("code", "kjCode"),
                ("companyName", "kjName"),
                ("title", "kjTitle"),
                ("xbrl", "kjXbrl"),
            ):
                if class_name in classes:
                    self.field = field
                    self.row.setdefault(field, "")
                    break
        elif tag == "a" and self.field in {"title", "xbrl"}:
            href = attributes.get("href")
            if href:
                self.row[f"{self.field}Href"] = href

    def handle_data(self, data: str) -> None:
        if self.row is not None and self.field:
            self.row[self.field] = self.row.get(self.field, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td":
            self.field = None
        elif tag == "tr" and self.row is not None:
            row = {key: compact_text(value) for key, value in self.row.items()}
            if row.get("code") and row.get("title") and row.get("titleHref"):
                self.rows.append(row)
            self.row = None
            self.field = None


def parse_tdnet_page(payload: bytes) -> tuple[list[dict[str, str]], int]:
    text = payload.decode("utf-8", errors="replace")
    parser = TDnetDisclosureParser()
    parser.feed(text)
    pages = [
        int(match)
        for match in re.findall(r"I_list_(\d{3})_\d{8}\.html", text)
    ]
    return parser.rows, max(pages, default=1)


def classify_title(title: str, source: str = "TDnet") -> dict:
    normalized = compact_text(title)
    lower = normalized.lower()

    category = "other"
    base_score = 28
    category_rules: list[tuple[str, int, tuple[str, ...]]] = [
        ("guidance", 86, ("業績予想", "通期予想", "利益予想", "forecast")),
        ("dividend", 74, ("配当", "剰余金の配当", "dividend")),
        (
            "buyback",
            82,
            (
                "自己株式の取得",
                "自己株式取得",
                "自己株式の消却",
                "自社株買い",
                "share repurchase",
            ),
        ),
        (
            "ma",
            84,
            (
                "公開買付",
                "tob",
                "株式交換",
                "株式移転",
                "会社分割",
                "事業譲渡",
                "子会社化",
                "子会社の異動",
                "資本業務提携",
                "業務提携",
                "合併",
                "買収",
            ),
        ),
        (
            "capital",
            80,
            (
                "株式分割",
                "株式併合",
                "第三者割当",
                "新株予約権",
                "新株式発行",
                "公募増資",
                "売出し",
                "資本金の額",
                "自己株式の処分",
            ),
        ),
        (
            "finance",
            62,
            ("資金の借入", "社債", "資金調達", "コミットメントライン", "債務保証"),
        ),
        (
            "governance",
            62,
            (
                "監査法人",
                "内部統制",
                "コーポレート・ガバナンス",
                "上場廃止",
                "監理銘柄",
                "改善報告書",
                "特設注意市場",
            ),
        ),
        (
            "personnel",
            50,
            ("代表取締役", "代表執行役", "役員人事", "取締役の異動", "社長交代"),
        ),
        ("large-holding", 66, ("大量保有報告書", "変更報告書", "短期大量譲渡")),
        (
            "earnings",
            70,
            ("決算短信", "四半期決算", "決算説明", "決算補足", "決算発表"),
        ),
        (
            "annual-report",
            38,
            (
                "有価証券報告書",
                "半期報告書",
                "四半期報告書",
                "臨時報告書",
                "確認書",
                "報告書",
            ),
        ),
    ]
    for candidate, score, keywords in category_rules:
        if any(keyword.lower() in lower for keyword in keywords):
            category, base_score = candidate, score
            break

    is_equity_compensation = any(
        word in normalized
        for word in (
            "譲渡制限付株式報酬",
            "株式報酬制度",
            "従業員持株会",
            "インセンティブ報酬制度",
            "ストック・オプション",
            "ストックオプション",
        )
    )
    if is_equity_compensation and category in {"buyback", "capital"}:
        category, base_score = "capital", 52
    if (
        category == "earnings"
        and "決算短信" not in normalized
        and any(word in normalized for word in ("決算説明", "決算補足", "質疑応答"))
    ):
        base_score = 55

    signals: list[dict[str, str]] = []

    def add_signal(label: str, direction: str = "neutral", kind: str = "title") -> None:
        if label not in {signal["label"] for signal in signals}:
            signals.append({"label": label, "direction": direction, "basis": kind})

    score = base_score
    if is_equity_compensation:
        add_signal("株式報酬・インセンティブ制度", "neutral")
    if "上方修正" in normalized or "上方に修正" in normalized:
        score = max(score, 94)
        add_signal("業績見通しを上方修正", "positive")
    if "下方修正" in normalized or "下方に修正" in normalized:
        score = max(score, 97)
        add_signal("業績見通しを下方修正", "negative")
    if "増配" in normalized or "配当予想の修正（増配" in normalized:
        score = max(score, 88)
        add_signal("配当予想を増額", "positive")
    if "減配" in normalized:
        score = max(score, 94)
        add_signal("配当予想を減額", "negative")
    if "無配" in normalized:
        score = max(score, 96)
        add_signal("無配を公表", "negative")
    if "自己株式の取得" in normalized or "自己株式取得" in normalized:
        add_signal("自己株式の取得を公表", "positive")
    if "自己株式の消却" in normalized:
        score = max(score, 84)
        add_signal("自己株式の消却を公表", "positive")
    if "株式分割" in normalized:
        score = max(score, 78)
        add_signal("株式分割を公表", "positive")
    if any(word in normalized for word in ("第三者割当", "公募増資", "新株式発行")):
        if is_equity_compensation:
            score = max(score, 58)
            add_signal("株式数への影響を確認", "review")
        elif any(
            word in normalized
            for word in ("払込完了", "月間行使状況", "大量行使", "行使完了", "増資の結果")
        ):
            score = max(score, 78)
            add_signal("新株・新株予約権の行使状況", "negative")
        else:
            score = max(score, 91)
            add_signal("新株発行による希薄化可能性", "negative")
    if "公開買付" in normalized or re.search(r"\bTOB\b", normalized, re.I):
        score = max(score, 95)
        add_signal("公開買付けに関する重要開示", "neutral")
    if "資本業務提携" in normalized:
        score = max(score, 86)
        add_signal("資本業務提携を公表", "positive")
    elif "業務提携" in normalized:
        score = max(score, 72)
        add_signal("業務提携を公表", "positive")
    if "特別利益" in normalized:
        score = max(score, 78)
        add_signal("特別利益の計上", "positive")
    if "特別損失" in normalized or "減損損失" in normalized:
        score = max(score, 85)
        add_signal("特別損失・減損の計上", "negative")
    if "債務超過" in normalized:
        score = 100
        add_signal("債務超過に関する開示", "negative")
    if "上場廃止" in normalized or "監理銘柄" in normalized:
        score = max(score, 98)
        add_signal("上場維持に関する重要事項", "negative")
    if "代表取締役" in normalized and any(word in normalized for word in ("異動", "変更", "辞任")):
        score = max(score, 60)
        add_signal("代表者の異動", "neutral")

    is_correction = any(
        word in normalized
        for word in ("訂正", "差替", "修正データ", "訂正報告書", "訂正届出書")
    )
    if is_correction:
        score = min(100, max(score, 58) + 8)
        add_signal("過去開示を訂正・差替え", "review")
        if category in {"other", "annual-report"}:
            category = "correction"

    if source == "EDINET" and category == "other":
        category, score = "annual-report", max(score, 34)

    importance = (
        "critical" if score >= 90 else "high" if score >= 70 else "medium" if score >= 45 else "low"
    )
    lead = signals[0]["label"] + "。" if signals else ""
    return {
        "category": category,
        "categoryLabel": CATEGORY_LABELS[category],
        "importance": importance,
        "importanceScore": score,
        "summary": lead + SUMMARY_TEMPLATES[category],
        "signals": signals[:4],
        "isCorrection": is_correction,
    }


def make_event(
    *,
    source: str,
    document_id: str,
    code: str,
    company_name: str,
    filed_at: object,
    title: str,
    url: str,
    xbrl_url: str | None = None,
) -> dict:
    classification = classify_title(title, source)
    event = {
        "id": f"{source.lower()}:{document_id}",
        "source": source,
        "documentId": document_id,
        "code": code,
        "companyName": company_name,
        "filedAt": iso_datetime(filed_at),
        "title": compact_text(title),
        "url": url,
        **classification,
    }
    if xbrl_url:
        event["xbrlUrl"] = xbrl_url
    return event


def list_tdnet_events(days: int, companies: dict[str, str]) -> tuple[list[dict], int]:
    events: list[dict] = []
    scanned = 0
    today = datetime.now(JST).date()
    for offset in range(max(0, days)):
        target = today - timedelta(days=offset)
        token = target.strftime("%Y%m%d")
        try:
            first_payload = get_tdnet(f"{TDNET_BASE_URL}/I_list_001_{token}.html")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                continue
            raise
        rows, pages = parse_tdnet_page(first_payload)
        all_rows = list(rows)
        for page in range(2, pages + 1):
            payload = get_tdnet(
                f"{TDNET_BASE_URL}/I_list_{page:03d}_{token}.html"
            )
            page_rows, _ = parse_tdnet_page(payload)
            all_rows.extend(page_rows)
        scanned += len(all_rows)
        for row in all_rows:
            code = normalize_security_code(row.get("code"))
            if not code or code not in companies:
                continue
            href = row.get("titleHref", "")
            document_id = Path(urllib.parse.urlparse(href).path).stem
            if not document_id:
                continue
            filed_at = datetime.combine(target, datetime.min.time(), tzinfo=JST)
            try:
                hour, minute = [int(part) for part in row.get("time", "").split(":", 1)]
                filed_at = filed_at.replace(hour=hour, minute=minute)
            except (TypeError, ValueError):
                pass
            xbrl_href = row.get("xbrlHref")
            events.append(
                make_event(
                    source="TDnet",
                    document_id=document_id,
                    code=code,
                    company_name=companies[code],
                    filed_at=filed_at,
                    title=row.get("title", ""),
                    url=urllib.parse.urljoin(f"{TDNET_BASE_URL}/", href),
                    xbrl_url=(
                        urllib.parse.urljoin(f"{TDNET_BASE_URL}/", xbrl_href)
                        if xbrl_href
                        else None
                    ),
                )
            )
        time.sleep(0.04)
    return events, scanned


def list_edinet_events(
    api_key: str,
    days: int,
    companies: dict[str, str],
) -> tuple[list[dict], int]:
    events: list[dict] = []
    scanned = 0
    today = datetime.now(JST).date()
    for offset in range(max(0, days)):
        target = today - timedelta(days=offset)
        query = urllib.parse.urlencode({"date": target.isoformat(), "type": 2})
        payload = json.loads(
            get_edinet(f"{EDINET_API}/documents.json?{query}", api_key)
        )
        metadata = payload.get("metadata") or {}
        if str(metadata.get("status", "200")) != "200":
            raise RuntimeError(metadata.get("message") or metadata.get("status"))
        rows = payload.get("results") or []
        scanned += len(rows)
        for row in rows:
            code = normalize_security_code(row.get("secCode"))
            document_id = compact_text(row.get("docID"))
            title = compact_text(row.get("docDescription"))
            if not code or code not in companies or not document_id or not title:
                continue
            events.append(
                make_event(
                    source="EDINET",
                    document_id=document_id,
                    code=code,
                    company_name=companies[code],
                    filed_at=row.get("submitDateTime") or target.isoformat(),
                    title=title,
                    url=(
                        "https://disclosure2.edinet-fsa.go.jp/WZEK0040.aspx?"
                        f"{document_id}"
                    ),
                )
            )
        time.sleep(0.03)
    return events, scanned


def bootstrap_financial_events(companies: dict[str, str]) -> list[dict]:
    payload = load_json(FINANCIALS, {"records": {}})
    events: list[dict] = []
    for code, record in (payload.get("records") or {}).items():
        normalized_code = normalize_security_code(code)
        document_id = compact_text(record.get("documentId"))
        if not normalized_code or normalized_code not in companies or not document_id:
            continue
        source = "TDnet" if record.get("source") == "TDnet" else "EDINET"
        period_end = compact_text(record.get("periodEnd"))
        title = compact_text(record.get("title"))
        if not title:
            title = (
                f"有価証券報告書（{period_end}期）"
                if source == "EDINET"
                else f"決算短信（{period_end}期）"
            )
        events.append(
            make_event(
                source=source,
                document_id=document_id,
                code=normalized_code,
                company_name=companies[normalized_code],
                filed_at=record.get("filedAt") or period_end,
                title=title,
                url=compact_text(record.get("sourceUrl")),
            )
        )
    return events


def deduplicate_events(events: Iterable[dict]) -> list[dict]:
    deduplicated: dict[str, dict] = {}
    for event in events:
        event_id = compact_text(event.get("id"))
        if not event_id:
            continue
        existing = deduplicated.get(event_id)
        if existing is None or compact_text(event.get("filedAt")) > compact_text(existing.get("filedAt")):
            deduplicated[event_id] = event
    return list(deduplicated.values())


def reclassify_event(event: dict) -> dict:
    refreshed = dict(event)
    refreshed.update(
        classify_title(
            compact_text(refreshed.get("title")),
            compact_text(refreshed.get("source")) or "TDnet",
        )
    )
    for key in (
        "previousComparableId",
        "previousComparableFiledAt",
        "daysSincePrevious",
    ):
        refreshed.pop(key, None)
    return refreshed


def enrich_comparisons(events: list[dict]) -> list[dict]:
    ordered = sorted(events, key=lambda event: (event.get("filedAt", ""), event.get("id", "")))
    previous_by_group: dict[tuple[str, str], dict] = {}
    previous_by_company: dict[str, dict] = {}
    for event in ordered:
        key = (str(event.get("code")), str(event.get("category")))
        previous = previous_by_group.get(key)
        if event.get("isCorrection") and previous is None:
            previous = previous_by_company.get(str(event.get("code")))
        if previous:
            event["previousComparableId"] = previous.get("id")
            event["previousComparableFiledAt"] = previous.get("filedAt")
            current_date = parse_datetime(event.get("filedAt"))
            previous_date = parse_datetime(previous.get("filedAt"))
            if current_date and previous_date:
                event["daysSincePrevious"] = max(0, (current_date.date() - previous_date.date()).days)
        previous_by_group[key] = event
        previous_by_company[str(event.get("code"))] = event
    return sorted(ordered, key=lambda event: (event.get("filedAt", ""), event.get("id", "")), reverse=True)


def build_snapshot(
    events: Iterable[dict],
    *,
    retention_days: int,
    source_status: dict,
    scanned: dict[str, int],
    bootstrap_only: bool = False,
) -> dict:
    now = datetime.now(JST)
    cutoff = now - timedelta(days=max(1, retention_days))
    retained = []
    for event in deduplicate_events(reclassify_event(event) for event in events):
        filed_at = parse_datetime(event.get("filedAt"))
        if filed_at and filed_at >= cutoff:
            retained.append(event)
    enriched = enrich_comparisons(retained)
    importance_counts = Counter(event["importance"] for event in enriched)
    category_counts = Counter(event["category"] for event in enriched)
    source_counts = Counter(event["source"] for event in enriched)
    failed_sources = [name for name, state in source_status.items() if state.get("status") == "error"]
    succeeded_sources = [name for name, state in source_status.items() if state.get("status") == "ready"]
    if bootstrap_only:
        status = "partial"
        message = "既存の財務開示から初期タイムラインを構築済み。次回自動更新でTDnet・EDINET新着を追加します。"
    elif failed_sources and succeeded_sources:
        status = "partial"
        message = f"{', '.join(succeeded_sources)}を更新済み。{', '.join(failed_sources)}は取得失敗のため前回データを維持しています。"
    elif failed_sources:
        status = "error"
        message = "新着取得に失敗したため、前回の開示データを表示しています。"
    else:
        status = "ready"
        message = "TDnet・EDINETの新着開示を分類し、重要度と変更シグナルを更新しました。"
    return {
        "schemaVersion": 1,
        "generatedAt": now.isoformat(timespec="seconds"),
        "latestFiledAt": enriched[0]["filedAt"] if enriched else None,
        "status": status,
        "message": message,
        "retentionDays": retention_days,
        "sourceStatus": source_status,
        "events": enriched,
        "stats": {
            "events": len(enriched),
            "companies": len({event["code"] for event in enriched}),
            "critical": importance_counts["critical"],
            "high": importance_counts["high"],
            "corrections": sum(1 for event in enriched if event.get("isCorrection")),
            "byImportance": dict(sorted(importance_counts.items())),
            "byCategory": dict(sorted(category_counts.items())),
            "bySource": dict(sorted(source_counts.items())),
            "rowsScanned": scanned,
        },
    }


def refresh_disclosures(
    *,
    tdnet_days: int,
    edinet_days: int,
    retention_days: int,
    bootstrap_only: bool = False,
    output: Path = OUTPUT,
) -> dict:
    companies = company_master()
    previous = load_existing_snapshot(output)
    existing_events = previous.get("events") or []
    bootstrap_events = bootstrap_financial_events(companies)
    events = [*existing_events, *bootstrap_events]
    source_status: dict[str, dict] = {
        "TDnet": {"status": "bootstrap" if bootstrap_only else "pending"},
        "EDINET": {"status": "bootstrap" if bootstrap_only else "pending"},
    }
    scanned = {"TDnet": 0, "EDINET": 0}

    if not bootstrap_only:
        try:
            tdnet_events, tdnet_scanned = list_tdnet_events(tdnet_days, companies)
            events.extend(tdnet_events)
            scanned["TDnet"] = tdnet_scanned
            source_status["TDnet"] = {
                "status": "ready",
                "checkedAt": datetime.now(JST).isoformat(timespec="seconds"),
                "eventsFetched": len(tdnet_events),
            }
        except Exception as error:  # Preserve prior data when a public endpoint is transiently down.
            source_status["TDnet"] = {
                "status": "error",
                "checkedAt": datetime.now(JST).isoformat(timespec="seconds"),
                "message": compact_text(error),
            }

        api_key = os.environ.get("EDINET_API_KEY", "").strip()
        if not api_key:
            source_status["EDINET"] = {
                "status": "error",
                "checkedAt": datetime.now(JST).isoformat(timespec="seconds"),
                "message": "EDINET_API_KEY is not configured",
            }
        else:
            try:
                edinet_events, edinet_scanned = list_edinet_events(
                    api_key,
                    edinet_days,
                    companies,
                )
                events.extend(edinet_events)
                scanned["EDINET"] = edinet_scanned
                source_status["EDINET"] = {
                    "status": "ready",
                    "checkedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "eventsFetched": len(edinet_events),
                }
            except Exception as error:
                source_status["EDINET"] = {
                    "status": "error",
                    "checkedAt": datetime.now(JST).isoformat(timespec="seconds"),
                    "message": compact_text(error),
                }

    snapshot = build_snapshot(
        events,
        retention_days=retention_days,
        source_status=source_status,
        scanned=scanned,
        bootstrap_only=bootstrap_only,
    )
    persist_snapshot(snapshot, output)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tdnet-days", type=int, default=3)
    parser.add_argument("--edinet-days", type=int, default=3)
    parser.add_argument("--retention-days", type=int, default=120)
    parser.add_argument("--bootstrap-only", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    snapshot = refresh_disclosures(
        tdnet_days=args.tdnet_days,
        edinet_days=args.edinet_days,
        retention_days=args.retention_days,
        bootstrap_only=args.bootstrap_only,
        output=args.output,
    )
    print(
        "Disclosure radar updated: "
        f"{snapshot['stats']['events']} events, "
        f"{snapshot['stats']['critical']} critical, "
        f"{snapshot['stats']['high']} high."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
