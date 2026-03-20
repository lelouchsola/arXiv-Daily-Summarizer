from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import collect_arxiv_papers, collect_crossref_journal_papers
from pipeline import (
    dedupe_records,
    enrich_records_with_summaries,
    load_settings,
    score_records,
    write_site_payload,
)
from pipeline.models import PaperRecord


def main() -> int:
    settings = load_settings()
    timezone = ZoneInfo(settings.timezone_name)
    generated_at = datetime.now(timezone)
    target_date = generated_at.date()

    print("=" * 72)
    print(f"Building daily site for {target_date.isoformat()} ({settings.timezone_name})")
    print("=" * 72)

    records: list[PaperRecord] = []
    source_errors: list[str] = []

    if "arxiv" in settings.enabled_sources:
        try:
            arxiv_records = collect_arxiv_papers(
                categories=list(settings.arxiv_categories),
                target_date=target_date,
                timezone_name=settings.timezone_name,
                max_results_per_category=settings.max_results_per_arxiv_category,
                lookback_days=settings.lookback_days,
            )
            print(f"Collected {len(arxiv_records)} arXiv papers.")
            records.extend(arxiv_records)
        except Exception as exc:
            message = f"arXiv collection failed: {exc}"
            source_errors.append(message)
            print(message)

    for source_config in settings.source_configs:
        if source_config.source_key not in settings.enabled_sources:
            continue

        try:
            journal_records = collect_crossref_journal_papers(
                config=source_config,
                target_date=target_date,
                timezone_name=settings.timezone_name,
                lookback_days=settings.lookback_days,
                contact_email=settings.crossref_mailto,
            )
            print(f"Collected {len(journal_records)} records from {source_config.journal_title}.")
            records.extend(journal_records)
        except Exception as exc:
            message = f"{source_config.journal_title} collection failed: {exc}"
            source_errors.append(message)
            print(message)

    score_records(records, settings)
    records = dedupe_records(records)
    records.sort(key=lambda record: (record.final_score, record.published_at.timestamp()), reverse=True)
    selected_records = records[: settings.max_results]
    enrich_records_with_summaries(selected_records, settings)
    selected_records.sort(
        key=lambda record: (record.final_score, record.published_at.timestamp()),
        reverse=True,
    )

    site_dir = Path(__file__).resolve().parents[1] / "site"
    write_site_payload(
        site_dir=site_dir,
        settings=settings,
        target_date=target_date,
        generated_at=generated_at,
        records=selected_records,
        source_errors=source_errors,
    )

    print(f"Wrote {len(selected_records)} papers to {site_dir / 'latest.json'}")
    if source_errors:
        print("Completed with partial source failures:")
        for error in source_errors:
            print(f"  - {error}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
