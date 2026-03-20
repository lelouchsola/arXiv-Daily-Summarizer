from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Settings
from .models import PaperRecord

CORE_KEYWORDS = {
    "learn to optimize": 2.0,
    "decision-focused": 2.0,
    "predict-and-optimize": 1.9,
    "end-to-end": 1.2,
    "reinforcement learning": 1.4,
    "machine learning": 1.0,
    "data-driven": 1.0,
    "power system": 1.4,
    "energy system": 1.2,
    "smart grid": 1.6,
    "microgrid": 1.4,
    "hydrogen": 1.4,
    "power-to-gas": 1.4,
    "p2g": 1.0,
    "electrolyzer": 1.4,
    "fuel cell": 1.2,
    "unit commitment": 1.8,
    "economic dispatch": 1.7,
    "optimal power flow": 2.0,
    "opf": 1.1,
    "flexibility": 1.0,
    "flexible resource": 1.1,
    "demand response": 1.3,
    "energy storage": 1.3,
    "renewable": 1.1,
    "stochastic optimization": 1.7,
    "robust optimization": 1.7,
    "resilience": 1.0,
    "typhoon": 0.9,
    "der": 0.8,
    "novel": 0.6,
    "efficient": 0.6,
    "framework": 0.5,
    "state-of-the-art": 0.6,
}

JOURNAL_PRIORITIES = {
    "nature energy": 1.6,
    "nature communications": 1.25,
    "joule": 1.45,
    "ieee transactions on smart grid": 1.0,
    "ieee transactions on power systems": 1.0,
    "ieee transactions on sustainable energy": 0.95,
    "ieee transactions on transportation electrification": 0.9,
    "arxiv": 0.65,
}


def score_records(records: list[PaperRecord], settings: Settings) -> list[PaperRecord]:
    for record in records:
        matched_keywords = _extract_matched_keywords(record)
        record.matched_keywords = matched_keywords
        record.rule_score = round(_calculate_rule_score(record, settings, matched_keywords), 2)
        record.llm_score = record.rule_score
        record.final_score = record.rule_score
        record.relevance_label = _label_for_score(record.rule_score)
        record.score_reason = _build_reason(record, settings)
    return records


def _calculate_rule_score(record: PaperRecord, settings: Settings, matched_keywords: list[str]) -> float:
    score = 0.0
    title_lower = record.title.lower()
    abstract_lower = record.abstract_raw.lower()

    for keyword in matched_keywords:
        weight = CORE_KEYWORDS[keyword]
        if keyword in title_lower:
            score += weight
        elif keyword in abstract_lower:
            score += weight * 0.5

    abstract_length = len(record.abstract_raw)
    if abstract_length > 1600:
        score += 1.1
    elif abstract_length > 800:
        score += 0.8
    elif abstract_length > 400:
        score += 0.45
    elif abstract_length < 120:
        score -= 1.0

    author_count = len(record.authors)
    if 3 <= author_count <= 8:
        score += 0.8
    elif author_count > 8:
        score += 0.4

    title_word_count = len(record.title.split())
    if title_word_count < 5:
        score -= 0.5
    elif 6 <= title_word_count <= 18:
        score += 0.5
    elif title_word_count > 28:
        score -= 0.3

    score += _journal_priority(record)
    score += _recency_bonus(record, settings)

    if record.source == "arxiv":
        primary_category = (record.metadata.get("primary_category") or "").lower()
        if primary_category in {category.lower() for category in settings.arxiv_categories}:
            score += 0.3

    return max(0.0, min(score, 10.0))


def _extract_matched_keywords(record: PaperRecord) -> list[str]:
    title_lower = record.title.lower()
    abstract_lower = record.abstract_raw.lower()
    matches = [keyword for keyword in CORE_KEYWORDS if keyword in title_lower or keyword in abstract_lower]
    matches.sort(key=lambda keyword: CORE_KEYWORDS[keyword], reverse=True)
    return matches[:6]


def _journal_priority(record: PaperRecord) -> float:
    return JOURNAL_PRIORITIES.get(record.journal.lower(), JOURNAL_PRIORITIES.get(record.source, 0.45))


def _current_local_date(settings: Settings):
    return datetime.now(ZoneInfo(settings.timezone_name)).date()


def _recency_bonus(record: PaperRecord, settings: Settings) -> float:
    published_local = record.published_at_local(settings.timezone_name).date()
    days_old = max((_current_local_date(settings) - published_local).days, 0)
    bonus_map = {0: 1.2, 1: 0.75, 2: 0.35}
    return bonus_map.get(days_old, 0.0)


def _label_for_score(score: float) -> str:
    if score >= 7.8:
        return "Strong Match"
    if score >= 5.2:
        return "Promising"
    return "Background Read"


def _build_reason(record: PaperRecord, settings: Settings) -> str:
    published_local = record.published_at_local(settings.timezone_name).date()
    days_old = max((_current_local_date(settings) - published_local).days, 0)
    recency_text = {0: "today", 1: "yesterday"}.get(days_old, f"{days_old} days ago")
    if record.matched_keywords:
        return f"Published {recency_text}; strongest keyword signals: {', '.join(record.matched_keywords[:3])}."
    if not record.abstract_raw:
        return f"Published {recency_text}; metadata-only match from a high-value source."
    return f"Published {recency_text}; selected from the recent three-day window based on source quality and abstract coverage."
