from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from dateutil import parser as date_parser

from pipeline.config import JournalSourceConfig
from pipeline.models import PaperRecord

CROSSREF_WORKS_API_URL = "https://api.crossref.org/works"
USER_AGENT = "DailyPaperBot/1.0 (+https://github.com/lelouchsola/arXiv-Daily-Summarizer)"


def collect_crossref_journal_papers(
    config: JournalSourceConfig,
    target_date: date,
    timezone_name: str,
    latest_rows: int,
    max_age_days: int,
    contact_email: str | None = None,
    timeout_seconds: int = 30,
) -> list[PaperRecord]:
    session = requests.Session()
    headers = {"User-Agent": USER_AGENT}
    if contact_email:
        headers["User-Agent"] = f"{USER_AGENT} mailto:{contact_email}"
    session.headers.update(headers)

    timezone_local = ZoneInfo(timezone_name)
    earliest_allowed_date = target_date - timedelta(days=max(max_age_days - 1, 0))
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()

    for issn in config.issns:
        items = _fetch_crossref_items(session, issn, latest_rows, timeout_seconds)
        for item in items:
            record = _item_to_record(item, config)
            if not record or record.id in seen_ids:
                continue
            published_local_date = record.published_at.astimezone(timezone_local).date()
            if published_local_date > target_date or published_local_date < earliest_allowed_date:
                continue
            seen_ids.add(record.id)
            records.append(record)

    records.sort(key=lambda record: record.published_at.timestamp(), reverse=True)
    return records


def _fetch_crossref_items(
    session: requests.Session,
    issn: str,
    latest_rows: int,
    timeout_seconds: int,
) -> list[dict]:
    select_fields = ",".join(
        [
            "DOI",
            "URL",
            "title",
            "author",
            "abstract",
            "container-title",
            "link",
            "subject",
            "published-online",
            "published-print",
            "issued",
            "created",
            "publisher",
        ]
    )

    query_variants = [
        {"filter": f"issn:{issn}", "sort": "published", "order": "desc"},
        {"filter": f"issn:{issn}", "sort": "created", "order": "desc"},
    ]

    for variant in query_variants:
        response = session.get(
            CROSSREF_WORKS_API_URL,
            params={
                **variant,
                "rows": latest_rows,
                "select": select_fields,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
        if items:
            return items

    return []


def _item_to_record(item: dict, config: JournalSourceConfig) -> PaperRecord | None:
    title_values = item.get("title") or []
    title = title_values[0].strip() if title_values else ""
    if not title:
        return None

    published_at = _extract_best_date(item)
    if published_at is None:
        return None

    doi = item.get("DOI")
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
    pdf_url = _extract_pdf_url(item.get("link") or [])
    abstract_raw = _clean_abstract(item.get("abstract") or "")
    authors = []
    for author in item.get("author") or []:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        full_name = " ".join(part for part in [given, family] if part).strip()
        if full_name:
            authors.append(full_name)

    container_titles = item.get("container-title") or []
    journal_title = container_titles[0].strip() if container_titles else config.journal_title
    identifier = doi or url or title
    return PaperRecord(
        id=identifier,
        source=config.source_key,
        journal=journal_title,
        title=title,
        authors=authors,
        abstract_raw=abstract_raw,
        url=url,
        pdf_url=pdf_url,
        doi=doi,
        published_at=published_at,
        categories=item.get("subject") or [],
        metadata={
            "publisher": item.get("publisher"),
            "issns": list(config.issns),
            "journal_weight": config.journal_weight,
        },
    )


def _extract_best_date(item: dict) -> datetime | None:
    for field in ("published-online", "published-print", "issued", "created"):
        value = item.get(field)
        parsed = _parse_crossref_date(value)
        if parsed is not None:
            return parsed
    return None


def _parse_crossref_date(value: dict | None) -> datetime | None:
    if not value:
        return None
    date_parts = value.get("date-parts") or []
    if not date_parts or not date_parts[0]:
        return None

    parts = date_parts[0]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1

    fallback = datetime(year, month, day, tzinfo=timezone.utc)
    text_value = value.get("date-time")
    if text_value:
        try:
            parsed = date_parser.isoparse(text_value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (TypeError, ValueError):
            return fallback
    return fallback


def _extract_pdf_url(links: list[dict]) -> str | None:
    for link in links:
        if "pdf" in (link.get("content-type") or "").lower():
            return link.get("URL")
    return None


def _clean_abstract(raw_abstract: str) -> str:
    if not raw_abstract:
        return ""
    normalized = html.unescape(raw_abstract)
    normalized = re.sub(r"</?(jats:)?[^>]+>", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
