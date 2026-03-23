from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .config import Settings
from .models import PaperRecord


def write_site_payload(
    site_dir: Path,
    settings: Settings,
    target_date: date,
    generated_at: datetime,
    records: list[PaperRecord],
    source_errors: list[str],
) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)

    core_power_journals = {
        config.journal_title for config in settings.source_configs if config.group_key == "core_ieee"
    }
    arxiv_records = [record for record in records if record.source == "arxiv"]
    discovery_records = [
        record for record in records if record.source != "arxiv" and record.journal not in core_power_journals
    ]
    core_power_records = [record for record in records if record.journal in core_power_journals]

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
            "arxiv": {
                "title": "arXiv 精选榜",
                "description": "单独汇总近三天 arXiv 论文，优先保留真正贴近电力系统、优化与 AI 方法的条目。",
                "count": len(arxiv_records),
                "papers": [record.to_dict(settings.timezone_name) for record in arxiv_records],
            },
            "discovery": {
                "title": "Nature / Joule 发现榜",
                "description": "汇总 Nature 系列与 Joule，宁缺勿滥，只保留方法或电力系统语境明确的论文。",
                "count": len(discovery_records),
                "papers": [record.to_dict(settings.timezone_name) for record in discovery_records],
            },
            "core_ieee": {
                "title": "核心电力期刊榜",
                "description": "汇总 IEEE Transactions 与 Applied Energy、Advances in Applied Energy、Energy Conversion and Management、Renewable Energy、Energy 等核心电力能源期刊。",
                "count": len(core_power_records),
                "papers": [record.to_dict(settings.timezone_name) for record in core_power_records],
            },
        },
        "papers": [record.to_dict(settings.timezone_name) for record in records],
    }

    latest_json = site_dir / "latest.json"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
