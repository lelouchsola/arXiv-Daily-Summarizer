from __future__ import annotations

from datetime import date, timedelta
import time
from zoneinfo import ZoneInfo

import arxiv

from pipeline.models import PaperRecord

ARXIV_EXTRA_BACKOFF_SECONDS = (30.0, 90.0, 180.0)


def collect_arxiv_papers(
    categories: list[str],
    target_date: date,
    timezone_name: str,
    max_results_per_category: int,
    lookback_days: int,
    page_size: int = 50,
    delay_seconds: float = 8.0,
    num_retries: int = 6,
) -> list[PaperRecord]:
    timezone = ZoneInfo(timezone_name)
    min_date = target_date - timedelta(days=max(lookback_days - 1, 0))
    client = arxiv.Client(
        page_size=page_size,
        delay_seconds=delay_seconds,
        num_retries=num_retries,
    )
    papers: list[PaperRecord] = []
    seen_ids: set[str] = set()
    category_errors: list[str] = []

    for category in categories:
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results_per_category,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            for result in _results_with_backoff(client, search):
                published_local = result.published.astimezone(timezone)
                published_date = published_local.date()
                if published_date < min_date:
                    break
                if published_date > target_date:
                    continue
                if result.entry_id in seen_ids:
                    continue

                seen_ids.add(result.entry_id)
                papers.append(
                    PaperRecord(
                        id=result.entry_id,
                        source="arxiv",
                        journal="arXiv",
                        title=result.title.strip(),
                        authors=[author.name for author in result.authors],
                        abstract_raw=(result.summary or "").strip(),
                        url=result.entry_id,
                        pdf_url=result.pdf_url,
                        doi=None,
                        published_at=result.published,
                        categories=result.categories or [category],
                        metadata={
                            "primary_category": category,
                        },
                    )
                )
        except Exception as exc:
            category_errors.append(f"{category}: {exc}")

    if category_errors and not papers:
        raise RuntimeError("all arXiv categories failed: " + " | ".join(category_errors))
    if category_errors:
        print("Partial arXiv category failures: " + " | ".join(category_errors))

    return papers


def _results_with_backoff(client: arxiv.Client, search: arxiv.Search):
    for attempt in range(len(ARXIV_EXTRA_BACKOFF_SECONDS) + 1):
        try:
            yield from client.results(search)
            return
        except Exception:
            if attempt >= len(ARXIV_EXTRA_BACKOFF_SECONDS):
                raise
            time.sleep(ARXIV_EXTRA_BACKOFF_SECONDS[attempt])
