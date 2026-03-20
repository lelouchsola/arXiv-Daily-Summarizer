from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class JournalSourceConfig:
    source_key: str
    journal_title: str
    issns: tuple[str, ...]
    journal_weight: float


@dataclass(frozen=True)
class Settings:
    timezone_name: str = "Asia/Shanghai"
    site_title: str = "Daily Paper Briefing"
    site_subtitle: str = (
        "A once-a-day research brief for optimization, power systems, and sustainable energy."
    )
    max_results: int = 12
    arxiv_categories: tuple[str, ...] = ("math.OC", "eess.SY")
    max_results_per_arxiv_category: int = 80
    summary_count: int = 12
    enabled_sources: tuple[str, ...] = ("arxiv", "nature", "joule", "ieee")
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    crossref_mailto: str | None = None
    source_configs: tuple[JournalSourceConfig, ...] = field(default_factory=tuple)


def load_settings() -> Settings:
    timezone_name = os.environ.get("TARGET_TIMEZONE", "Asia/Shanghai")
    site_title = os.environ.get("SITE_TITLE", "Daily Paper Briefing")
    site_subtitle = os.environ.get(
        "SITE_SUBTITLE",
        "A once-a-day research brief for optimization, power systems, and sustainable energy.",
    )
    max_results = int(os.environ.get("MAX_RESULTS", "12"))
    summary_count = int(os.environ.get("SUMMARY_COUNT", str(max_results)))
    arxiv_categories = tuple(
        category.strip()
        for category in os.environ.get("ARXIV_CATEGORIES", "math.OC,eess.SY").split(",")
        if category.strip()
    )
    enabled_sources = tuple(
        source.strip()
        for source in os.environ.get("ENABLED_SOURCES", "arxiv,nature,joule,ieee").split(",")
        if source.strip()
    )

    source_configs = (
        JournalSourceConfig(
            source_key="nature",
            journal_title="Nature Energy",
            issns=("2058-7546",),
            journal_weight=1.5,
        ),
        JournalSourceConfig(
            source_key="nature",
            journal_title="Nature Communications",
            issns=("2041-1723",),
            journal_weight=1.35,
        ),
        JournalSourceConfig(
            source_key="joule",
            journal_title="Joule",
            issns=("2542-4351",),
            journal_weight=1.4,
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Smart Grid",
            issns=("1949-3053", "1949-3061"),
            journal_weight=1.3,
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Power Systems",
            issns=("0885-8950", "1558-0679"),
            journal_weight=1.3,
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Sustainable Energy",
            issns=("1949-3029", "1949-3037"),
            journal_weight=1.25,
        ),
    )

    return Settings(
        timezone_name=timezone_name,
        site_title=site_title,
        site_subtitle=site_subtitle,
        max_results=max_results,
        arxiv_categories=arxiv_categories,
        max_results_per_arxiv_category=max_results * 8,
        summary_count=summary_count,
        enabled_sources=enabled_sources,
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        crossref_mailto=os.environ.get("CROSSREF_MAILTO"),
        source_configs=source_configs,
    )
