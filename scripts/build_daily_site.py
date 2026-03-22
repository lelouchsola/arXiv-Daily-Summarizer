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
from pipeline.score import passes_display_gate, passes_rule_gate


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
                latest_rows=settings.crossref_latest_rows,
                max_age_days=settings.crossref_max_age_days,
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
    records.sort(key=_sort_key, reverse=True)

    core_ieee_journals = {
        config.journal_title for config in settings.source_configs if config.group_key == "core_ieee"
    }
    discovery_candidates = [
        record for record in records if record.journal not in core_ieee_journals and passes_rule_gate(record)
    ]
    core_ieee_candidates = [
        record for record in records if record.journal in core_ieee_journals and passes_rule_gate(record)
    ]

    selected_candidates = (
        discovery_candidates[: settings.max_results_per_section]
        + core_ieee_candidates[: settings.max_results_per_section]
    )[: settings.max_results]
    enrich_records_with_summaries(selected_candidates, settings)

    llm_enabled = bool(settings.deepseek_api_key)
    discovery_selected = [
        record
        for record in selected_candidates
        if record.journal not in core_ieee_journals and passes_display_gate(record, llm_enabled)
    ]
    core_ieee_selected = [
        record
        for record in selected_candidates
        if record.journal in core_ieee_journals and passes_display_gate(record, llm_enabled)
    ]

    discovery_selected.sort(key=_sort_key, reverse=True)
    core_ieee_selected.sort(key=_sort_key, reverse=True)
    selected_records = (
        discovery_selected[: settings.max_results_per_section]
        + core_ieee_selected[: settings.max_results_per_section]
    )[: settings.max_results]

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


def _sort_key(record: PaperRecord) -> tuple[float, float]:
    return (record.final_score, record.published_at.timestamp())


if __name__ == "__main__":
    raise SystemExit(main())
