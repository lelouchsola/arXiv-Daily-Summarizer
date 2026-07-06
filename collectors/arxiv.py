from __future__ import annotations

from datetime import date, datetime, time as datetime_time, timedelta, timezone
import os
import random
import re
import time
from urllib.parse import urlencode, urljoin
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests

from pipeline.models import PaperRecord

ARXIV_MAX_PAGE_SIZE = 25
ARXIV_MIN_DELAY_SECONDS = 6.0
ARXIV_MAX_NUM_RETRIES = 1
ARXIV_GITHUB_ACTIONS_JITTER_SECONDS = 8.0
ARXIV_CATEGORY_PAUSE_SECONDS = 3.0
ARXIV_REQUEST_RETRY_BACKOFF_SECONDS = 2.0
ARXIV_USER_AGENT = "DailyPaperBot/1.0 (+https://github.com/lelouchsola/arXiv-Daily-Summarizer)"
ARXIV_ACCEPT_HEADER = "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_API_TIMEOUT_SECONDS = 30
ARXIV_RECENT_LIST_URL_FORMAT = "https://arxiv.org/list/{category}/recent?skip=0&show=2000"
ARXIV_FALLBACK_TIMEOUT_SECONDS = 30

ATOM_NAMESPACE = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


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
    effective_num_retries = max(0, min(num_retries, ARXIV_MAX_NUM_RETRIES))
    api_client = _ArxivApiClient(
        session=_build_session(contact_email),
        page_size=effective_page_size,
        delay_seconds=effective_delay_seconds,
        num_retries=effective_num_retries,
    )

    papers: list[PaperRecord] = []
    seen_ids: set[str] = set()
    category_errors: list[str] = []

    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        time.sleep(random.uniform(0.0, ARXIV_GITHUB_ACTIONS_JITTER_SECONDS))

    for index, category in enumerate(categories):
        try:
            api_records = _collect_api_category(
                api_client=api_client,
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
                        session=api_client.session,
                        category=category,
                        target_date=target_date,
                        min_date=min_date,
                        max_results_per_category=max_results_per_category,
                    )
                    if fallback_records:
                        _append_unique_records(papers, seen_ids, fallback_records)
                        print(
                            f"arXiv API unavailable for {category} ({exc}); "
                            f"using recent-page fallback collected {len(fallback_records)} papers."
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


class _ArxivApiClient:
    def __init__(
        self,
        session: requests.Session,
        page_size: int,
        delay_seconds: float,
        num_retries: int,
    ) -> None:
        self.session = session
        self.page_size = page_size
        self.delay_seconds = delay_seconds
        self.num_retries = num_retries
        self._last_request_monotonic: float | None = None

    def query(self, category: str, start: int, max_results: int) -> ET.Element:
        params = {
            "search_query": f"cat:{category}",
            "id_list": "",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": start,
            "max_results": max_results,
        }
        url = f"{ARXIV_API_URL}?{urlencode(params)}"

        for attempt in range(self.num_retries + 1):
            self._sleep_if_needed()
            try:
                response = self.session.get(url, timeout=ARXIV_API_TIMEOUT_SECONDS)
                response.raise_for_status()
                if not response.content.strip():
                    raise RuntimeError(f"empty arXiv API response for {category}")
                return ET.fromstring(response.content)
            except Exception as exc:
                if _should_use_recent_page_fallback(exc) or attempt >= self.num_retries:
                    raise
                time.sleep(ARXIV_REQUEST_RETRY_BACKOFF_SECONDS)
            finally:
                self._last_request_monotonic = time.monotonic()

        raise RuntimeError(f"failed to query arXiv API for {category}")

    def _sleep_if_needed(self) -> None:
        if self._last_request_monotonic is None:
            return

        elapsed = time.monotonic() - self._last_request_monotonic
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)


def _collect_api_category(
    api_client: _ArxivApiClient,
    category: str,
    target_date: date,
    min_date: date,
    timezone_local: ZoneInfo,
    max_results_per_category: int,
) -> list[PaperRecord]:
    records: list[PaperRecord] = []
    start = 0

    while len(records) < max_results_per_category:
        batch_size = min(api_client.page_size, max_results_per_category - len(records))
        feed_root = api_client.query(category=category, start=start, max_results=batch_size)
        entries = feed_root.findall("atom:entry", ATOM_NAMESPACE)
        if not entries:
            break

        stop_paging = False
        for entry in entries:
            record = _api_entry_to_record(entry, category)
            if record is None:
                continue

            published_local = record.published_at.astimezone(timezone_local)
            published_date = published_local.date()
            if published_date < min_date:
                stop_paging = True
                break
            if published_date > target_date:
                continue

            records.append(record)
            if len(records) >= max_results_per_category:
                return records

        if stop_paging or len(entries) < batch_size:
            break
        start += batch_size

    return records


def _collect_recent_page_category(
    session: requests.Session,
    category: str,
    target_date: date,
    min_date: date,
    max_results_per_category: int,
) -> list[PaperRecord]:
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


def _api_entry_to_record(entry: ET.Element, category: str) -> PaperRecord | None:
    entry_id = _normalize_space(_find_entry_text(entry, "atom:id"))
    title = _normalize_space(_find_entry_text(entry, "atom:title"))
    published_text = _normalize_space(_find_entry_text(entry, "atom:published"))
    if not entry_id or not title or not published_text:
        return None

    authors = [
        author_name
        for author_name in (
            _normalize_space(author_node.text)
            for author_node in entry.findall("atom:author/atom:name", ATOM_NAMESPACE)
        )
        if author_name
    ]
    abstract_raw = _normalize_space(_find_entry_text(entry, "atom:summary"))
    categories = _extract_api_categories(entry)
    pdf_url = _extract_pdf_url(entry)
    primary_category_node = entry.find("arxiv:primary_category", ATOM_NAMESPACE)
    primary_category = category
    if primary_category_node is not None and primary_category_node.get("term"):
        primary_category = primary_category_node.get("term", "").strip() or category

    return PaperRecord(
        id=entry_id,
        source="arxiv",
        journal="arXiv",
        title=title,
        authors=authors,
        abstract_raw=abstract_raw,
        url=entry_id,
        pdf_url=pdf_url,
        doi=_normalize_space(_find_entry_text(entry, "arxiv:doi")) or None,
        published_at=_parse_api_datetime(published_text),
        categories=categories or [primary_category],
        metadata={
            "primary_category": primary_category,
        },
    )


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


def _build_session(contact_email: str | None) -> requests.Session:
    session = requests.Session()
    user_agent = ARXIV_USER_AGENT
    headers = {
        "User-Agent": user_agent,
        "Accept": ARXIV_ACCEPT_HEADER,
    }
    if contact_email:
        headers["User-Agent"] = f"{user_agent} mailto:{contact_email}"
        headers["From"] = contact_email
    session.headers.update(headers)
    return session


def _find_entry_text(entry: ET.Element, path: str) -> str:
    node = entry.find(path, ATOM_NAMESPACE)
    if node is None or node.text is None:
        return ""
    return node.text


def _extract_api_categories(entry: ET.Element) -> list[str]:
    categories: list[str] = []
    seen: set[str] = set()
    for category_node in entry.findall("atom:category", ATOM_NAMESPACE):
        term = (category_node.get("term") or "").strip()
        if not term or term in seen:
            continue
        seen.add(term)
        categories.append(term)
    return categories


def _extract_pdf_url(entry: ET.Element) -> str | None:
    for link_node in entry.findall("atom:link", ATOM_NAMESPACE):
        href = (link_node.get("href") or "").strip()
        if not href:
            continue
        link_title = (link_node.get("title") or "").strip().lower()
        link_type = (link_node.get("type") or "").strip().lower()
        if link_title == "pdf" or link_type == "application/pdf" or "/pdf/" in href:
            return href
    return None


def _parse_api_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def _normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _should_use_recent_page_fallback(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return any(
        token in error_text
        for token in (
            "403",
            "406",
            "429",
            "500",
            "502",
            "503",
            "504",
            "connection",
            "timeout",
            "timed out",
            "forbidden",
            "not acceptable",
            "empty arxiv api response",
        )
    )
