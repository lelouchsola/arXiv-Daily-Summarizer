from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape

from .config import Settings
from .models import PaperRecord


def write_site_payload(
    site_dir: Path,
    settings: Settings,
    target_date: date,
    generated_at: datetime,
    records: list[PaperRecord],
    source_errors: list[str],
) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)

    site_base_url = _normalize_base_url(settings.site_base_url)
    homepage_url = site_base_url
    feed_url = urljoin(site_base_url, "feed.xml")

    core_power_journals = {
        config.journal_title for config in settings.source_configs if config.group_key == "core_ieee"
    }
    arxiv_records = [record for record in records if record.source == "arxiv"]
    discovery_records = [
        record for record in records if record.source != "arxiv" and record.journal not in core_power_journals
    ]
    core_power_records = [record for record in records if record.journal in core_power_journals]

    source_counts = Counter(record.source for record in records)
    journal_counts = Counter(record.journal for record in records)
    strong_match_count = sum(1 for record in records if record.relevance_label == "Strong Match")

    payload = {
        "meta": {
            "title": settings.site_title,
            "subtitle": settings.site_subtitle,
            "site_base_url": site_base_url,
            "homepage_url": homepage_url,
            "feed_url": feed_url,
            "subscribe_url": settings.subscribe_url,
            "target_date": target_date.isoformat(),
            "generated_at": generated_at.isoformat(),
            "timezone": settings.timezone_name,
            "lookback_days": settings.lookback_days,
            "paper_count": len(records),
            "source_count": len(source_counts),
            "strong_match_count": strong_match_count,
            "source_counts": dict(source_counts),
            "journal_counts": dict(journal_counts),
            "source_errors": source_errors,
        },
        "sections": {
            "arxiv": {
                "title": "arXiv 精选榜",
                "description": "单独汇总近三天 arXiv 论文，优先保留真正贴近电力系统、优化与 AI 方法的条目。",
                "count": len(arxiv_records),
                "papers": [record.to_dict(settings.timezone_name) for record in arxiv_records],
            },
            "discovery": {
                "title": "Nature / Joule 发现榜",
                "description": "汇总 Nature 系列与 Joule，宁缺勿滥，只保留方法或电力系统语境明确的论文。",
                "count": len(discovery_records),
                "papers": [record.to_dict(settings.timezone_name) for record in discovery_records],
            },
            "core_ieee": {
                "title": "核心电力期刊榜",
                "description": "汇总 IEEE Transactions 与 Applied Energy、Advances in Applied Energy、Energy Conversion and Management、Renewable Energy、Energy 等核心电力能源期刊。",
                "count": len(core_power_records),
                "papers": [record.to_dict(settings.timezone_name) for record in core_power_records],
            },
        },
        "papers": [record.to_dict(settings.timezone_name) for record in records],
    }

    latest_json = site_dir / "latest.json"
    latest_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_feed_xml(
        site_dir=site_dir,
        homepage_url=homepage_url,
        feed_url=feed_url,
        settings=settings,
        target_date=target_date,
        generated_at=generated_at,
        records=records,
    )


def _write_feed_xml(
    site_dir: Path,
    homepage_url: str,
    feed_url: str,
    settings: Settings,
    target_date: date,
    generated_at: datetime,
    records: list[PaperRecord],
) -> None:
    top_records = sorted(records, key=lambda record: record.final_score, reverse=True)[:5]
    summary_lines = []
    for index, record in enumerate(top_records, start=1):
        summary_lines.append(
            f"{index}. {record.title} [{record.journal}] - {record.final_score:.1f}/10"
        )
    if not summary_lines:
        summary_lines.append("今日没有达到展示门槛的新论文。")

    description = (
        f"{settings.site_title} · {target_date.isoformat()}\n"
        + "\n".join(summary_lines)
        + f"\n\n访问完整网页：{homepage_url}"
    )
    guid = f"{homepage_url}#digest-{target_date.isoformat()}"
    pub_date = generated_at.strftime("%a, %d %b %Y %H:%M:%S %z")

    feed_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape(settings.site_title)}</title>
    <link>{escape(homepage_url)}</link>
    <description>{escape(settings.site_subtitle)}</description>
    <language>zh-CN</language>
    <lastBuildDate>{escape(pub_date)}</lastBuildDate>
    <atom:link href="{escape(feed_url)}" rel="self" type="application/rss+xml" xmlns:atom="http://www.w3.org/2005/Atom" />
    <item>
      <title>{escape(f'{settings.site_title} · {target_date.isoformat()}')}</title>
      <link>{escape(homepage_url)}</link>
      <guid isPermaLink="false">{escape(guid)}</guid>
      <pubDate>{escape(pub_date)}</pubDate>
      <description>{escape(description)}</description>
    </item>
  </channel>
</rss>
'''
    (site_dir / "feed.xml").write_text(feed_xml, encoding="utf-8")


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip()
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized
