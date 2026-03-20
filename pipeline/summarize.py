from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Settings
from .models import PaperRecord


def enrich_records_with_summaries(records: list[PaperRecord], settings: Settings) -> list[PaperRecord]:
    if not records:
        return records

    client = None
    if settings.deepseek_api_key:
        client = OpenAI(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
        )

    for index, record in enumerate(records):
        if index >= settings.summary_count:
            _apply_fallback_summary(record)
            continue

        if client is None:
            _apply_fallback_summary(record)
            continue

        try:
            _apply_model_summary(record, client, settings.deepseek_model)
        except Exception:
            _apply_fallback_summary(record)

    return records


def _apply_model_summary(record: PaperRecord, client: OpenAI, model: str) -> None:
    prompt = f"""
You are curating a daily research briefing for power systems, optimization, and sustainable energy.
Read the paper metadata below and respond with valid JSON only.

Return this schema:
{{
  "summary_zh": "120-180 Chinese characters summarizing the core contribution and evidence.",
  "application_value": "One Chinese sentence on why this matters in practice.",
  "relevance_label": "Strong Match | Promising | Background Read",
  "relevance_score": 0.0,
  "reason": "One short English sentence explaining the score."
}}

Title: {record.title}
Journal: {record.journal}
Authors: {", ".join(record.authors[:8])}
Abstract: {record.abstract_raw or "No abstract available. Score based on title and source metadata."}
""".strip()

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "Return strict JSON only. Do not wrap it in markdown.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    content = response.choices[0].message.content or ""
    payload = _parse_json_blob(content)

    record.ai_summary = payload.get("summary_zh") or _fallback_summary_text(record)
    record.application_value = payload.get("application_value") or "适合纳入今天的快速浏览清单。"
    record.relevance_label = payload.get("relevance_label") or record.relevance_label
    record.llm_score = _safe_float(payload.get("relevance_score"), default=record.rule_score)
    record.final_score = round((record.rule_score * 0.45) + (record.llm_score * 0.55), 2)
    record.score_reason = payload.get("reason") or record.score_reason


def _apply_fallback_summary(record: PaperRecord) -> None:
    record.ai_summary = _fallback_summary_text(record)
    record.application_value = _fallback_application_value(record)
    record.llm_score = record.rule_score
    record.final_score = round(record.rule_score, 2)


def _fallback_summary_text(record: PaperRecord) -> str:
    if not record.abstract_raw:
        return "该条目缺少公开摘要，当前以标题、期刊来源和关键词命中结果作为初步优先级参考。"

    text = re.sub(r"\s+", " ", record.abstract_raw).strip()
    if len(text) <= 180:
        return text
    return f"{text[:180].rstrip()}..."


def _fallback_application_value(record: PaperRecord) -> str:
    journal_lower = record.journal.lower()
    if "smart grid" in journal_lower or "power systems" in journal_lower:
        return "如果你今天只看少量文章，这篇更值得优先排进电力系统方向的阅读队列。"
    if "nature" in journal_lower or "joule" in journal_lower:
        return "这篇来自高关注度期刊，适合作为今天的趋势扫描入口。"
    return "建议先快速浏览摘要和图表，再决定是否投入精读时间。"


def _parse_json_blob(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate)
        candidate = candidate.rstrip("`").strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain JSON.")

    return json.loads(candidate[start : end + 1])


def _safe_float(value: object, default: float) -> float:
    try:
        return max(0.0, min(float(value), 10.0))
    except (TypeError, ValueError):
        return default
