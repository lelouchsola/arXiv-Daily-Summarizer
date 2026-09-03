from __future__ import annotations

import html
import re
import time
from urllib.parse import quote

from bs4 import BeautifulSoup
import requests

from .models import PaperRecord


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
USER_AGENT = "DailyPaperBot/1.0 (+https://github.com/lelouchsola/arXiv-Daily-Summarizer)"
PAGE_REQUEST_INTERVAL_SECONDS = 3.0
REQUEST_TIMEOUT_SECONDS = 20
MIN_ABSTRACT_LENGTH = 120


def enrich_missing_abstracts(
    records: list[PaperRecord],
    contact_email: str | None = None,
    openalex_api_key: str | None = None,
) -> list[PaperRecord]:
    """Best-effort abstract enrichment for the small set selected for summarization."""
    if not records:
        return records

    session = requests.Session()
    user_agent = USER_AGENT
    if contact_email and contact_email.strip():
        user_agent = f"{USER_AGENT} mailto:{contact_email.strip()}"
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json, text/html, application/xhtml+xml;q=0.9, */*;q=0.8",
        }
    )

    page_request_started_at: float | None = None
    enriched_count = 0
    for record in records:
        if record.abstract_raw.strip():
            continue

        abstract = ""
        abstract_source = ""

        if record.source == "arxiv":
            page_request_started_at = _wait_for_page_request(page_request_started_at)
            abstract = _fetch_page_abstract(session, record.url)
            abstract_source = "arxiv_abstract_page"
        elif record.doi:
            abstract = _fetch_openalex_abstract(session, record.doi, openalex_api_key)
            abstract_source = "openalex"

            # Nature landing pages expose a reliable machine-readable description.
            if not abstract and record.source == "nature":
                page_request_started_at = _wait_for_page_request(page_request_started_at)
                abstract = _fetch_page_abstract(session, record.url)
                abstract_source = "publisher_landing_page"

        if not abstract:
            continue

        record.abstract_raw = abstract
        record.metadata["abstract_source"] = abstract_source
        enriched_count += 1

    missing_count = sum(1 for record in records if not record.abstract_raw.strip())
    print(
        f"Abstract enrichment recovered {enriched_count} abstracts; "
        f"{missing_count} selected papers remain without an abstract."
    )
    return records


def _fetch_openalex_abstract(
    session: requests.Session,
    doi: str,
    api_key: str | None,
) -> str:
    normalized_doi = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip()
    if not normalized_doi:
        return ""

    params = {"select": "id,abstract_inverted_index"}
    if api_key and api_key.strip():
        params["api_key"] = api_key.strip()

    try:
        response = session.get(
            f"{OPENALEX_WORKS_URL}/doi:{quote(normalized_doi, safe='/():._-')}",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code in {404, 429}:
            return ""
        response.raise_for_status()
        return _reconstruct_openalex_abstract(response.json().get("abstract_inverted_index"))
    except (requests.RequestException, ValueError, TypeError):
        return ""


def _reconstruct_openalex_abstract(inverted_index: object) -> str:
    if not isinstance(inverted_index, dict):
        return ""

    positioned_words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_words.append((position, word))

    positioned_words.sort(key=lambda item: item[0])
    return _clean_abstract(" ".join(word for _, word in positioned_words))


def _fetch_page_abstract(session: requests.Session, url: str) -> str:
    if not url:
        return ""

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code not in {200, 202}:
            return ""
        soup = BeautifulSoup(response.text, "lxml")

        for key in ("citation_abstract", "dc.description", "og:description", "description"):
            meta = soup.find("meta", attrs={"name": key}) or soup.find(
                "meta", attrs={"property": key}
            )
            value = _clean_abstract(meta.get("content", "") if meta else "")
            if len(value) >= MIN_ABSTRACT_LENGTH:
                return value

        abstract_node = soup.select_one("blockquote.abstract, section#abstract, div.abstract")
        if abstract_node is not None:
            value = _clean_abstract(abstract_node.get_text(" ", strip=True))
            if len(value) >= MIN_ABSTRACT_LENGTH:
                return value
    except requests.RequestException:
        return ""

    return ""


def _wait_for_page_request(previous_started_at: float | None) -> float:
    if previous_started_at is not None:
        elapsed = time.monotonic() - previous_started_at
        if elapsed < PAGE_REQUEST_INTERVAL_SECONDS:
            time.sleep(PAGE_REQUEST_INTERVAL_SECONDS - elapsed)
    return time.monotonic()


def _clean_abstract(value: str) -> str:
    normalized = html.unescape(value or "")
    normalized = re.sub(r"^\s*Abstract\s*:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
