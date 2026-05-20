from __future__ import annotations

from datetime import date, timedelta
import os
import random
import time
from zoneinfo import ZoneInfo

import arxiv

from pipeline.models import PaperRecord

ARXIV_EXTRA_BACKOFF_SECONDS = (60.0, 180.0, 420.0)
ARXIV_MAX_PAGE_SIZE = 25
ARXIV_MIN_DELAY_SECONDS = 12.0
ARXIV_MIN_NUM_RETRIES = 8
ARXIV_GITHUB_ACTIONS_JITTER_SECONDS = 45.0
ARXIV_CATEGORY_PAUSE_SECONDS = 12.0
ARXIV_USER_AGENT = "DailyPaperBot/1.0 (+https://github.com/lelouchsola/arXiv-Daily-Summarizer)"


def collect_arxiv_papers(
    categories: list[str],
    target_date: date,
    timezone_name: str,
    max_results_per_category: int,
    lookback_days: int,
    page_size: int = 50,
    delay_seconds: float = 8.0,
    num_retries: int = 6,
    contact_email: str | None = None,
) -> list[PaperRecord]:
    timezone = ZoneInfo(timezone_name)
    min_date = target_date - timedelta(days=max(lookback_days - 1, 0))
    effective_page_size = max(1, min(page_size, ARXIV_MAX_PAGE_SIZE))
    effective_delay_seconds = max(delay_seconds, ARXIV_MIN_DELAY_SECONDS)
    effective_num_retries = max(num_retries, ARXIV_MIN_NUM_RETRIES)
    client = arxiv.Client(
        page_size=effective_page_size,
        delay_seconds=effective_delay_seconds,
        num_retries=effective_num_retries,
    )
    _configure_client(client, contact_email)
    papers: list[PaperRecord] = []
    seen_ids: set[str] = set()
    category_errors: list[str] = []

    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        time.sleep(random.uniform(0.0, ARXIV_GITHUB_ACTIONS_JITTER_SECONDS))

    for index, category in enumerate(categories):
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

        if index < len(categories) - 1:
            time.sleep(ARXIV_CATEGORY_PAUSE_SECONDS)

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


def _configure_client(client: arxiv.Client, contact_email: str | None) -> None:
    user_agent = ARXIV_USER_AGENT
    if contact_email:
        user_agent = f"{user_agent} mailto:{contact_email}"

    client._session.headers.update({"user-agent": user_agent})
    if contact_email:
        client._session.headers.update({"from": contact_email})
