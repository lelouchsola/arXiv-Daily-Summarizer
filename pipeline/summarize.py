from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Settings
from .models import PaperRecord


SUMMARY_TEMPLATE = """1. **研究背景和核心动机**：{background}\n\n2. **提出的数学模型、优化算法或主要创新点**：{innovation}\n\n3. **实验验证及核心结论**：{evaluation}\n\n4. **对现实电力/能源系统的潜在应用价值**：{application}\n\n5. **领域判定**：{label}。{reason}"""


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
你正在为“大湾区大学 IDEA Lab 每日论文精选”撰写中文科研快报。请阅读下面的论文信息，并只返回合法 JSON，不要输出 markdown 代码块。

请返回如下 JSON 结构：
{{
  "background": "1-2句，说明研究背景和核心动机",
  "innovation": "2-3句，说明数学模型、优化算法或主要创新点；如涉及 decision-focused、机器学习或优化框架，请明确写出",
  "evaluation": "1-2句，说明实验验证及核心结论",
  "application": "1句，说明对现实电力/能源系统的潜在应用价值",
  "relevance_label": "【强相关】 | 【较相关】 | 【一般相关】",
  "relevance_score": 0.0,
  "reason": "1句中文，解释为什么这样判定",
  "application_value": "1句中文，说明为什么值得今天优先读"
}}

要求：
1. 输出内容必须严谨、学术、简洁。
2. relevance_score 使用 0 到 10 的评分。
3. 若缺少摘要，请根据标题、期刊与关键词尽量保守判断。

论文标题：{record.title}
期刊来源：{record.journal}
作者：{", ".join(record.authors[:8])}
摘要：{record.abstract_raw or 'No abstract available. Score based on title and source metadata.'}
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

    record.ai_summary = SUMMARY_TEMPLATE.format(
        background=(payload.get("background") or "未提供足够信息，需要查看原文进一步确认。"),
        innovation=(payload.get("innovation") or "未能稳定提取方法细节，建议优先查看原文模型与算法部分。"),
        evaluation=(payload.get("evaluation") or "当前未提取到可靠的实验结论，建议直接查看实验部分。"),
        application=(payload.get("application") or "可作为后续是否值得精读的初步判断依据。"),
        label=(payload.get("relevance_label") or _fallback_label(record)),
        reason=(payload.get("reason") or "与当前研究方向存在一定关联，但仍建议结合原文判断。"),
    )
    record.application_value = payload.get("application_value") or "适合纳入今天的快速浏览清单。"
    record.relevance_label = _normalize_label(payload.get("relevance_label") or record.relevance_label)
    record.llm_score = _safe_float(payload.get("relevance_score"), default=record.rule_score)
    record.final_score = round((record.rule_score * 0.45) + (record.llm_score * 0.55), 2)
    record.score_reason = payload.get("reason") or record.score_reason


def _apply_fallback_summary(record: PaperRecord) -> None:
    record.ai_summary = _fallback_summary_text(record)
    record.application_value = _fallback_application_value(record)
    record.relevance_label = _fallback_label(record)
    record.llm_score = record.rule_score
    record.final_score = round(record.rule_score, 2)


def _fallback_summary_text(record: PaperRecord) -> str:
    text = re.sub(r"\s+", " ", record.abstract_raw).strip()
    short_text = text[:220].rstrip() + ("..." if len(text) > 220 else "")
    return SUMMARY_TEMPLATE.format(
        background="该工作处于电力系统、能源优化与数据驱动决策相关研究脉络中，适合作为近三天新增论文的快速筛查对象。",
        innovation=(short_text or "当前缺少公开摘要，暂时只能依据标题、期刊来源与关键词命中结果进行保守判断。"),
        evaluation="当前页面为自动快报，若需要确认实验设置、求解效率或泛化表现，建议进入原文进一步核对。",
        application=_fallback_application_value(record),
        label=_fallback_label(record),
        reason=(record.score_reason or "该论文与当前关注方向存在一定契合度，建议根据原文再做最终优先级判断。"),
    )


def _fallback_application_value(record: PaperRecord) -> str:
    journal_lower = record.journal.lower()
    if "smart grid" in journal_lower or "power systems" in journal_lower:
        return "该工作较可能直接服务于电力系统运行优化、调度或规划决策。"
    if "nature" in journal_lower or "joule" in journal_lower:
        return "该工作适合作为趋势扫描入口，帮助快速识别高关注度期刊中的新方向。"
    return "建议先快速浏览摘要和图表，再决定是否投入精读时间。"


def _fallback_label(record: PaperRecord) -> str:
    if record.final_score >= 7.8:
        return "【强相关】"
    if record.final_score >= 5.2:
        return "【较相关】"
    return "【一般相关】"


def _normalize_label(label: str) -> str:
    mapping = {
        "【强相关】": "Strong Match",
        "【较相关】": "Promising",
        "【一般相关】": "Background Read",
        "Strong Match": "Strong Match",
        "Promising": "Promising",
        "Background Read": "Background Read",
    }
    return mapping.get(label, label)


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
