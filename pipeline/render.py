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
            "paper_count": len(records),
            "source_count": len(source_counts),
            "strong_match_count": strong_match_count,
            "source_counts": dict(source_counts),
            "journal_counts": dict(journal_counts),
            "source_errors": source_errors,
        },
        "papers": [record.to_dict(settings.timezone_name) for record in records],
    }

    latest_json = site_dir / "latest.json"
    latest_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
