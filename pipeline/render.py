from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .config import Settings
from .models import PaperRecord

CORE_IEEE_JOURNALS = {
    "IEEE Transactions on Smart Grid",
    "IEEE Transactions on Power Systems",
    "IEEE Transactions on Sustainable Energy",
    "IEEE Transactions on Transportation Electrification",
}


def write_site_payload(
    site_dir: Path,
    settings: Settings,
    target_date: date,
    generated_at: datetime,
    records: list[PaperRecord],
    source_errors: list[str],
) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)

    discovery_records = [record for record in records if record.journal not in CORE_IEEE_JOURNALS]
    core_ieee_records = [record for record in records if record.journal in CORE_IEEE_JOURNALS]

    source_counts = Counter(record.source for record in records)
    journal_counts = Counter(record.journal for record in records)
    strong_match_count = sum(1 for record in records if record.relevance_label == "Strong Match")

    payload = {
        "meta": {
            "title": settings.site_title,
            "subtitle": settings.site_subtitle,
            "target_date": target_date.isoformat(),
            "generated_at": generated_at.isoformat(),
            "timezone": settings.timezone_name,
            "lookback_days": settings.lookback_days,
            "paper_count": len(records),
            "source_count": len(source_counts),
            "strong_match_count": strong_match_count,
            "source_counts": dict(source_counts),
            "journal_counts": dict(journal_counts),
            "source_errors": source_errors,
        },
        "sections": {
            "discovery": {
                "title": "跨来源发现榜",
                "description": "汇总 arXiv、Nature、Joule 等来源，帮助你发现近三天最值得先扫一眼的新方向。",
                "count": len(discovery_records),
                "papers": [record.to_dict(settings.timezone_name) for record in discovery_records],
            },
            "core_ieee": {
                "title": "核心电力期刊榜",
                "description": "TSG、TPWRS、TSTE、TTE 单独成池排序，避免核心电力期刊因领域天然契合而长期挤占主榜。",
                "count": len(core_ieee_records),
                "papers": [record.to_dict(settings.timezone_name) for record in core_ieee_records],
            },
        },
        "papers": [record.to_dict(settings.timezone_name) for record in records],
    }

    latest_json = site_dir / "latest.json"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
