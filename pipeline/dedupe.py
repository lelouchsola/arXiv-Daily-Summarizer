from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import PaperRecord


def dedupe_records(records: list[PaperRecord], similarity_threshold: float = 0.9) -> list[PaperRecord]:
    by_identifier: dict[str, PaperRecord] = {}
    for record in records:
        for key in _exact_keys(record):
            if not key:
                continue
            existing = by_identifier.get(key)
            if existing is None or _record_rank(record) > _record_rank(existing):
                by_identifier[key] = record

    exact_deduped = list({id(record): record for record in by_identifier.values()}.values())
    fuzzy_deduped: list[PaperRecord] = []

    for record in exact_deduped:
        duplicate_index = None
        for index, existing in enumerate(fuzzy_deduped):
            if title_similarity(record.title, existing.title) >= similarity_threshold:
                duplicate_index = index
                break

        if duplicate_index is None:
            fuzzy_deduped.append(record)
            continue

        if _record_rank(record) > _record_rank(fuzzy_deduped[duplicate_index]):
            fuzzy_deduped[duplicate_index] = record

    return fuzzy_deduped


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def normalize_title(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _exact_keys(record: PaperRecord) -> list[str]:
    return [
        f"doi:{record.doi.lower()}" if record.doi else "",
        f"url:{record.url.lower()}" if record.url else "",
        f"title:{normalize_title(record.title)}",
    ]


def _record_rank(record: PaperRecord) -> tuple[float, float]:
    return (record.final_score or record.rule_score, record.published_at.timestamp())
