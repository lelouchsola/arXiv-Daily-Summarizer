from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta, timezone
import os
import random
import re
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import arxiv
from bs4 import BeautifulSoup
import requests

from pipeline.models import PaperRecord

ARXIV_EXTRA_BACKOFF_SECONDS = (60.0, 180.0, 420.0)
ARXIV_MAX_PAGE_SIZE = 25
ARXIV_MIN_DELAY_SECONDS = 12.0
ARXIV_MIN_NUM_RETRIES = 8
ARXIV_GITHUB_ACTIONS_JITTER_SECONDS = 45.0
ARXIV_CATEGORY_PAUSE_SECONDS = 12.0
ARXIV_USER_AGENT = "DailyPaperBot/1.0 (+https://github.com/lelouchsola/arXiv-Daily-Summarizer)"
ARXIV_RECENT_LIST_URL_FORMAT = "https://arxiv.org/list/{category}/recent?skip=0&show=2000"
ARXIV_FALLBACK_TIMEOUT_SECONDS = 30


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
    timezone_local = ZoneInfo(timezone_name)
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
        try:
            api_records = _collect_api_category(
                client=client,
                category=category,
                target_date=target_date,
                min_date=min_date,
                timezone_local=timezone_local,
                max_results_per_category=max_results_per_category,
            )
            _append_unique_records(papers, seen_ids, api_records)
        except Exception as exc:
            if _should_use_recent_page_fallback(exc):
                try:
                    fallback_records = _collect_recent_page_category(
                        category=category,
                        target_date=target_date,
                        min_date=min_date,
                        max_results_per_category=max_results_per_category,
                        contact_email=contact_email,
                    )
                    if fallback_records:
                        _append_unique_records(papers, seen_ids, fallback_records)
                        print(
                            f"Using arXiv recent-page fallback for {category}: "
                            f"collected {len(fallback_records)} papers."
                        )
                    else:
                        category_errors.append(
                            f"{category}: {exc} | recent-page fallback returned 0 records"
                        )
                except Exception as fallback_exc:
                    category_errors.append(f"{category}: {exc} | fallback failed: {fallback_exc}")
            else:
                category_errors.append(f"{category}: {exc}")

        if index < len(categories) - 1:
            time.sleep(ARXIV_CATEGORY_PAUSE_SECONDS)

    if category_errors and not papers:
        raise RuntimeError("all arXiv categories failed: " + " | ".join(category_errors))
    if category_errors:
        print("Partial arXiv category failures: " + " | ".join(category_errors))

    return papers


def _collect_api_category(
    client: arxiv.Client,
    category: str,
    target_date: date,
    min_date: date,
    timezone_local: ZoneInfo,
    max_results_per_category: int,
) -> list[PaperRecord]:
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results_per_category,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    records: list[PaperRecord] = []
    for result in _results_with_backoff(client, search):
        published_local = result.published.astimezone(timezone_local)
        published_date = published_local.date()
        if published_date < min_date:
            break
        if published_date > target_date:
            continue

        records.append(
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

    return records


def _collect_recent_page_category(
    category: str,
    target_date: date,
    min_date: date,
    max_results_per_category: int,
    contact_email: str | None = None,
) -> list[PaperRecord]:
    session = requests.Session()
    headers = {"User-Agent": ARXIV_USER_AGENT}
    if contact_email:
        headers["User-Agent"] = f"{ARXIV_USER_AGENT} mailto:{contact_email}"
        headers["From"] = contact_email
    session.headers.update(headers)

    response = session.get(
        ARXIV_RECENT_LIST_URL_FORMAT.format(category=category),
        timeout=ARXIV_FALLBACK_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    records: list[PaperRecord] = []

    for section_header, section_list in zip(soup.find_all("h3"), soup.find_all("dl")):
        section_date = _parse_recent_section_date(section_header.get_text(" ", strip=True))
        if section_date is None:
            continue
        if section_date < min_date:
            break
        if section_date > target_date:
            continue

        dt_nodes = section_list.find_all("dt", recursive=False)
        dd_nodes = section_list.find_all("dd", recursive=False)
        for dt_node, dd_node in zip(dt_nodes, dd_nodes):
            record = _recent_pair_to_record(dt_node, dd_node, category, section_date)
            if record is None:
                continue
            records.append(record)
            if len(records) >= max_results_per_category:
                return records

    return records


def _recent_pair_to_record(dt_node, dd_node, category: str, section_date: date) -> PaperRecord | None:
    abstract_link = dt_node.find("a", title="Abstract")
    if abstract_link is None or not abstract_link.get("href"):
        return None

    entry_id = (abstract_link.get("id") or abstract_link.get("href", "").split("/")[-1]).strip()
    if not entry_id:
        return None

    title = _extract_meta_text(dd_node, "list-title")
    if not title:
        return None

    authors = [author.get_text(" ", strip=True) for author in dd_node.select("div.list-authors a")]
    comments = _extract_meta_text(dd_node, "list-comments")
    subjects_text = _extract_meta_text(dd_node, "list-subjects")
    categories = [value.strip() for value in subjects_text.split(";") if value.strip()]

    pdf_link = dt_node.find("a", title="Download PDF")
    published_at = datetime.combine(section_date, datetime_time.min, tzinfo=timezone.utc)

    return PaperRecord(
        id=f"https://arxiv.org/abs/{entry_id}",
        source="arxiv",
        journal="arXiv",
        title=title,
        authors=authors,
        abstract_raw="",
        url=urljoin("https://arxiv.org", abstract_link["href"]),
        pdf_url=urljoin("https://arxiv.org", pdf_link["href"]) if pdf_link and pdf_link.get("href") else None,
        doi=None,
        published_at=published_at,
        categories=categories or [category],
        metadata={
            "primary_category": category,
            "fallback_source": "arxiv_recent_page",
            "comments": comments,
        },
    )


def _extract_meta_text(dd_node, class_name: str) -> str:
    container = dd_node.find("div", class_=class_name)
    if container is None:
        return ""

    descriptor = container.find("span", class_="descriptor")
    if descriptor is not None:
        descriptor.extract()

    return " ".join(container.get_text(" ", strip=True).split())


def _parse_recent_section_date(header_text: str) -> date | None:
    match = re.match(r"^[A-Za-z]{3},\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", header_text.strip())
    if not match:
        return None
    return datetime.strptime(match.group(0), "%a, %d %b %Y").date()


def _append_unique_records(
    destination: list[PaperRecord],
    seen_ids: set[str],
    new_records: list[PaperRecord],
) -> None:
    for record in new_records:
        if record.id in seen_ids:
            continue
        seen_ids.add(record.id)
        destination.append(record)


def _should_use_recent_page_fallback(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return any(token in error_text for token in ("429", "500", "502", "503", "504", "connection", "timeout"))


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
