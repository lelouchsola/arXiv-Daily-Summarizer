from __future__ import annotations

from .config import Settings
from .models import PaperRecord

CORE_KEYWORDS = {
    "decision-focused": 2.0,
    "learn to optimize": 2.0,
    "predict-and-optimize": 1.8,
    "optimization": 1.4,
    "optimal power flow": 2.0,
    "opf": 1.1,
    "unit commitment": 1.6,
    "economic dispatch": 1.4,
    "power system": 1.3,
    "smart grid": 1.5,
    "energy system": 1.2,
    "sustainable energy": 1.2,
    "renewable": 1.0,
    "electricity market": 1.0,
    "energy storage": 1.2,
    "hydrogen": 1.3,
    "electrolyzer": 1.3,
    "microgrid": 1.2,
    "stochastic optimization": 1.5,
    "robust optimization": 1.5,
    "reinforcement learning": 1.4,
    "machine learning": 1.0,
    "data-driven": 0.9,
    "flexibility": 0.9,
    "demand response": 1.2,
    "resilience": 1.0,
}

JOURNAL_PRIORITIES = {
    "nature energy": 1.5,
    "nature communications": 1.2,
    "joule": 1.3,
    "ieee transactions on smart grid": 1.1,
    "ieee transactions on power systems": 1.1,
    "ieee transactions on sustainable energy": 1.0,
    "arxiv": 0.6,
}


def score_records(records: list[PaperRecord], settings: Settings) -> list[PaperRecord]:
    for record in records:
        record.rule_score = round(_calculate_rule_score(record, settings), 2)
        record.llm_score = record.rule_score
        record.final_score = record.rule_score
        record.relevance_label = _label_for_score(record.rule_score)
        record.score_reason = _build_reason(record)
    return records


def _calculate_rule_score(record: PaperRecord, settings: Settings) -> float:
    score = 0.0
    title_lower = record.title.lower()
    abstract_lower = record.abstract_raw.lower()

    for keyword, weight in CORE_KEYWORDS.items():
        if keyword in title_lower:
            score += weight
        elif keyword in abstract_lower:
            score += weight * 0.5

    abstract_length = len(record.abstract_raw)
    if abstract_length > 1600:
        score += 1.2
    elif abstract_length > 800:
        score += 0.8
    elif abstract_length > 400:
        score += 0.4
    elif abstract_length < 120:
        score -= 0.8

    author_count = len(record.authors)
    if 2 <= author_count <= 8:
        score += 0.5
    elif author_count > 8:
        score += 0.2

    title_word_count = len(record.title.split())
    if 6 <= title_word_count <= 18:
        score += 0.5
    elif title_word_count > 28:
        score -= 0.3

    source_priority = JOURNAL_PRIORITIES.get(record.journal.lower(), JOURNAL_PRIORITIES.get(record.source, 0.4))
    score += source_priority

    if record.source == "arxiv":
        primary_category = (record.metadata.get("primary_category") or "").lower()
        if primary_category in {category.lower() for category in settings.arxiv_categories}:
            score += 0.3

    return max(0.0, min(score, 10.0))


def _label_for_score(score: float) -> str:
    if score >= 7.5:
        return "Strong Match"
    if score >= 5.0:
        return "Promising"
    return "Background Read"


def _build_reason(record: PaperRecord) -> str:
    title_lower = record.title.lower()
    abstract_lower = record.abstract_raw.lower()
    hits = [keyword for keyword in CORE_KEYWORDS if keyword in title_lower or keyword in abstract_lower]
    if hits:
        return f"Signals found in {', '.join(hits[:3])}."
    if not record.abstract_raw:
        return "Metadata-only match from a high-value source."
    return "Selected from today's releases based on title, abstract, and source quality."
