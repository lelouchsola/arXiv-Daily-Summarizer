from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


@dataclass
class PaperRecord:
    id: str
    source: str
    journal: str
    title: str
    authors: list[str]
    abstract_raw: str
    url: str
    published_at: datetime
    pdf_url: str | None = None
    doi: str | None = None
    categories: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_score: float = 0.0
    llm_score: float = 0.0
    final_score: float = 0.0
    score_reason: str = ""
    ai_summary: str = ""
    application_value: str = ""
    relevance_label: str = "Pending"
    matched_keywords: list[str] = field(default_factory=list)

    def published_at_local(self, timezone_name: str) -> datetime:
        return self.published_at.astimezone(ZoneInfo(timezone_name))

    def to_dict(self, timezone_name: str) -> dict[str, Any]:
        published_local = self.published_at_local(timezone_name)
        return {
            "id": self.id,
            "source": self.source,
            "journal": self.journal,
            "title": self.title,
            "authors": self.authors,
            "abstract_raw": self.abstract_raw,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "doi": self.doi,
            "published_at": self.published_at.isoformat(),
            "published_at_local": published_local.isoformat(),
            "published_date_local": published_local.strftime("%Y-%m-%d"),
            "published_time_local": published_local.strftime("%H:%M"),
            "categories": self.categories,
            "metadata": self.metadata,
            "rule_score": round(self.rule_score, 2),
            "llm_score": round(self.llm_score, 2),
            "final_score": round(self.final_score, 2),
            "score_reason": self.score_reason,
            "ai_summary": self.ai_summary,
            "application_value": self.application_value,
            "relevance_label": self.relevance_label,
            "matched_keywords": self.matched_keywords,
        }
