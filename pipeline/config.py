from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class JournalSourceConfig:
    source_key: str
    journal_title: str
    issns: tuple[str, ...]
    journal_weight: float
    group_key: str = "discovery"


@dataclass(frozen=True)
class Settings:
    timezone_name: str = "Asia/Shanghai"
    site_title: str = "每日论文精选推送"
    site_subtitle: str = "聚焦近三天 arXiv 与重点能源电力期刊的新论文，按相关性、质量与时效综合排序。"
    max_results: int = 20
    max_results_per_section: int = 10
    arxiv_categories: tuple[str, ...] = ("math.OC", "eess.SY")
    max_results_per_arxiv_category: int = 200
    summary_count: int = 20
    lookback_days: int = 3
    enabled_sources: tuple[str, ...] = ("arxiv", "nature", "joule", "ieee")
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    crossref_mailto: str | None = None
    source_configs: tuple[JournalSourceConfig, ...] = field(default_factory=tuple)


def load_settings() -> Settings:
    timezone_name = os.environ.get("TARGET_TIMEZONE", "Asia/Shanghai")
    site_title = os.environ.get("SITE_TITLE", "每日论文精选推送")
    site_subtitle = os.environ.get(
        "SITE_SUBTITLE",
        "聚焦近三天 arXiv 与重点能源电力期刊的新论文，按相关性、质量与时效综合排序。",
    )
    max_results = int(os.environ.get("MAX_RESULTS", "20"))
    max_results_per_section = int(os.environ.get("MAX_RESULTS_PER_SECTION", "10"))
    summary_count = int(os.environ.get("SUMMARY_COUNT", str(max_results)))
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", "3"))
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
            group_key="discovery",
        ),
        JournalSourceConfig(
            source_key="nature",
            journal_title="Nature Communications",
            issns=("2041-1723",),
            journal_weight=1.35,
            group_key="discovery",
        ),
        JournalSourceConfig(
            source_key="joule",
            journal_title="Joule",
            issns=("2542-4351",),
            journal_weight=1.4,
            group_key="discovery",
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Smart Grid",
            issns=("1949-3053", "1949-3061"),
            journal_weight=1.3,
            group_key="core_ieee",
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Power Systems",
            issns=("0885-8950", "1558-0679"),
            journal_weight=1.3,
            group_key="core_ieee",
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Sustainable Energy",
            issns=("1949-3029", "1949-3037"),
            journal_weight=1.25,
            group_key="core_ieee",
        ),
        JournalSourceConfig(
            source_key="ieee",
            journal_title="IEEE Transactions on Transportation Electrification",
            issns=("2332-7782", "2332-7790"),
            journal_weight=1.15,
            group_key="core_ieee",
        ),
    )

    return Settings(
        timezone_name=timezone_name,
        site_title=site_title,
        site_subtitle=site_subtitle,
        max_results=max_results,
        max_results_per_section=max_results_per_section,
        arxiv_categories=arxiv_categories,
        max_results_per_arxiv_category=max_results * 10,
        summary_count=summary_count,
        lookback_days=lookback_days,
        enabled_sources=enabled_sources,
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        crossref_mailto=os.environ.get("CROSSREF_MAILTO"),
        source_configs=source_configs,
    )
