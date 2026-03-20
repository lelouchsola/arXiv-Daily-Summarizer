from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import arxiv

from pipeline.models import PaperRecord


def collect_arxiv_papers(
    categories: list[str],
    target_date: date,
    timezone_name: str,
    max_results_per_category: int,
    lookback_days: int,
) -> list[PaperRecord]:
    timezone = ZoneInfo(timezone_name)
    min_date = target_date - timedelta(days=max(lookback_days - 1, 0))
    client = arxiv.Client()
    papers: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for category in categories:
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results_per_category,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        for result in client.results(search):
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

    return papers
