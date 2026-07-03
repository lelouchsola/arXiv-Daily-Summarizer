from __future__ import annotations

from datetime import datetime
import re
from zoneinfo import ZoneInfo

from .config import Settings
from .models import PaperRecord

KEYWORD_GROUPS = {
    "电力系统优化": {
        "ac optimal power flow": 2.5,
        "ac opf": 2.1,
        "optimal power flow": 2.1,
        "opf": 1.2,
        "unit commitment": 1.9,
        "economic dispatch": 1.8,
        "security-constrained unit commitment": 2.0,
        "scuc": 1.8,
        "security-constrained economic dispatch": 1.8,
        "sced": 1.6,
        "distributed optimal power flow": 1.7,
        "stochastic optimization": 1.7,
        "robust optimization": 1.7,
        "power system": 1.3,
        "power systems": 1.3,
        "smart grid": 1.4,
        "microgrid": 1.3,
        "microgrids": 1.3,
        "demand response": 1.4,
        "energy storage": 1.3,
        "distributed energy resource": 1.2,
        "distributed energy resources": 1.2,
        "der": 1.0,
        "virtual power plant": 1.3,
        "flexibility": 0.8,
        "chance-constrained optimization": 1.6,
        "chance-constrained": 1.2,
        "frequency-constrained": 1.4,
        "frequency nadir": 1.4,
        "voltage security": 1.4,
        "market clearing": 1.4,
        "energy trading": 1.3,
        "peer-to-peer energy trading": 1.7,
        "p2p energy trading": 1.7,
        "peer-to-peer transaction": 1.1,
    },
    "AI+Optimization": {
        "learn to optimize": 2.0,
        "learning to optimize": 2.0,
        "decision-focused": 2.0,
        "decision-focused learning": 2.1,
        "predict-and-optimize": 1.9,
        "decision-aware": 1.7,
        "end-to-end optimization": 1.7,
        "differentiable optimization": 1.8,
        "optimization surrogate": 1.4,
        "surrogate model": 1.2,
        "reinforcement learning": 1.3,
        "imitation learning": 1.2,
        "graph neural network": 1.1,
    },
    "源荷预测": {
        "load forecasting": 1.8,
        "net load forecasting": 1.8,
        "renewable forecasting": 1.6,
        "renewable generation forecasting": 1.7,
        "wind power forecasting": 1.7,
        "solar forecasting": 1.7,
        "photovoltaic forecasting": 1.6,
        "pv forecasting": 1.5,
        "probabilistic forecasting": 1.6,
        "time series forecasting": 1.2,
        "spatio-temporal forecasting": 1.3,
    },
    "氢电互动": {
        "hydrogen": 0.6,
        "power-to-gas": 1.7,
        "p2g": 1.1,
        "electrolyzer": 0.8,
        "fuel cell": 0.8,
        "hydrogen energy storage": 1.6,
        "hydrogen production": 0.9,
        "integrated energy system": 1.5,
        "multi-energy system": 1.5,
        "sector coupling": 1.4,
    },
    "车网互动": {
        "vehicle-to-grid": 1.8,
        "v2g": 1.5,
        "electric vehicle": 1.4,
        "ev charging": 1.4,
        "charging station": 1.3,
        "charging scheduling": 1.4,
        "transportation electrification": 1.4,
        "vehicle-grid interaction": 1.7,
        "fleet charging": 1.3,
    },
    "电网韧性": {
        "resilience": 1.4,
        "resilient operation": 1.6,
        "grid resilience": 1.7,
        "outage management": 1.5,
        "service restoration": 1.7,
        "network reconfiguration": 1.5,
        "black start": 1.4,
        "fault recovery": 1.2,
        "disaster response": 1.2,
        "typhoon": 1.1,
        "extreme weather": 1.3,
    },
    "稳定性": {
        "transient stability": 1.0,
        "transient-stability": 1.0,
        "large signal stability": 0.9,
        "large-signal stability": 0.9,
    },
    "构网型": {
        "grid forming": 0.95,
        "grid-forming": 0.95,
        "grid following": 0.75,
        "grid-following": 0.75,
        "current limiting": 0.45,
        "current-limiting": 0.45,
    },
}

CORE_KEYWORDS = {
    keyword: weight
    for keywords in KEYWORD_GROUPS.values()
    for keyword, weight in keywords.items()
}

KEYWORD_TO_GROUP = {
    keyword: group_name
    for group_name, keywords in KEYWORD_GROUPS.items()
    for keyword in keywords
}

DOMAIN_GROUPS = {
    "电力系统优化",
    "源荷预测",
    "氢电互动",
    "车网互动",
    "电网韧性",
    "稳定性",
    "构网型",
}
METHOD_GROUPS = {"AI+Optimization"}
STABILITY_PRIORITY_GROUPS = {"稳定性", "构网型"}
OPTIMIZATION_PRIORITY_GROUPS = {
    "电力系统优化",
    "AI+Optimization",
    "源荷预测",
    "氢电互动",
    "车网互动",
}

BROAD_RELEVANCE_KEYWORDS = {
    "ac optimal power flow",
    "ac opf",
    "ac optimal power flow",
    "ac opf",
    "optimal power flow",
    "opf",
    "unit commitment",
    "economic dispatch",
    "security-constrained unit commitment",
    "scuc",
    "security-constrained economic dispatch",
    "sced",
    "distributed optimal power flow",
    "stochastic optimization",
    "robust optimization",
    "power system",
    "smart grid",
    "microgrid",
    "demand response",
    "energy storage",
    "distributed energy resource",
    "power systems",
    "microgrids",
    "distributed energy resources",
    "chance-constrained optimization",
    "chance-constrained",
    "frequency-constrained",
    "frequency nadir",
    "voltage security",
    "market clearing",
    "energy trading",
    "peer-to-peer energy trading",
    "p2p energy trading",
    "peer-to-peer transaction",
    "virtual power plant",
    "load forecasting",
    "net load forecasting",
    "renewable forecasting",
    "renewable generation forecasting",
    "wind power forecasting",
    "solar forecasting",
    "photovoltaic forecasting",
    "pv forecasting",
    "probabilistic forecasting",
    "time series forecasting",
    "spatio-temporal forecasting",
    "power-to-gas",
    "hydrogen energy storage",
    "integrated energy system",
    "multi-energy system",
    "sector coupling",
    "vehicle-to-grid",
    "v2g",
    "electric vehicle",
    "ev charging",
    "charging station",
    "charging scheduling",
    "transportation electrification",
    "vehicle-grid interaction",
    "fleet charging",
    "resilience",
    "resilient operation",
    "grid resilience",
    "outage management",
    "service restoration",
    "network reconfiguration",
    "black start",
    "fault recovery",
    "disaster response",
    "typhoon",
    "extreme weather",
    "transient stability",
    "transient-stability",
    "large signal stability",
    "large-signal stability",
    "grid forming",
    "grid-forming",
    "grid following",
    "grid-following",
    "learn to optimize",
    "learning to optimize",
    "decision-focused",
    "decision-focused learning",
    "predict-and-optimize",
    "decision-aware",
    "end-to-end optimization",
    "differentiable optimization",
    "optimization surrogate",
    "surrogate model",
    "reinforcement learning",
    "imitation learning",
    "graph neural network",
}

POWER_SYSTEM_SIGNAL_KEYWORDS = {
    "optimal power flow",
    "opf",
    "unit commitment",
    "economic dispatch",
    "security-constrained unit commitment",
    "scuc",
    "security-constrained economic dispatch",
    "sced",
    "distributed optimal power flow",
    "power system",
    "smart grid",
    "microgrid",
    "demand response",
    "energy storage",
    "distributed energy resource",
    "der",
    "power systems",
    "microgrids",
    "distributed energy resources",
    "chance-constrained optimization",
    "chance-constrained",
    "frequency-constrained",
    "frequency nadir",
    "voltage security",
    "market clearing",
    "energy trading",
    "peer-to-peer energy trading",
    "p2p energy trading",
    "peer-to-peer transaction",
    "virtual power plant",
    "load forecasting",
    "net load forecasting",
    "renewable forecasting",
    "renewable generation forecasting",
    "wind power forecasting",
    "solar forecasting",
    "photovoltaic forecasting",
    "pv forecasting",
    "vehicle-to-grid",
    "v2g",
    "ev charging",
    "charging scheduling",
    "transportation electrification",
    "resilience",
    "resilient operation",
    "grid resilience",
    "outage management",
    "service restoration",
    "network reconfiguration",
    "black start",
    "transient stability",
    "transient-stability",
    "large signal stability",
    "large-signal stability",
    "grid forming",
    "grid-forming",
    "grid following",
    "grid-following",
}

POWER_CONTEXT_TERMS = {
    "power system",
    "power systems",
    "electric power",
    "grid",
    "electric grid",
    "electricity",
    "smart grid",
    "microgrid",
    "dispatch",
    "unit commitment",
    "load forecasting",
    "vehicle-to-grid",
    "electric vehicle",
    "charging",
    "integrated energy system",
    "multi-energy system",
    "energy system",
    "renewable generation",
    "renewable energy",
    "transient stability",
    "transient-stability",
    "large signal stability",
    "large-signal stability",
    "grid forming",
    "grid-forming",
    "grid following",
    "grid-following",
}

MATERIAL_RISK_TERMS = {
    "catalyst",
    "electrocatalyst",
    "photocatalyst",
    "nanoparticle",
    "nanomaterial",
    "membrane",
    "membranes",
    "anode",
    "cathode",
    "alloy",
    "surface chemistry",
    "electrode",
    "electrochemical synthesis",
    "material design",
    "materials chemistry",
    "perovskite",
    "semiconductor",
    "thin film",
    "thin-film",
    "surface engineering",
    "synthesis",
    "characterization",
    "crystal structure",
    "composite",
}

JOURNAL_PRIORITIES = {
    "arxiv": 0.55,
    "nature energy": 1.1,
    "nature communications": 1.1,
    "joule": 1.1,
    "ieee transactions on smart grid": 1.15,
    "ieee transactions on power systems": 1.15,
    "ieee transactions on sustainable energy": 1.1,
    "ieee transactions on transportation electrification": 1.0,
}

CORE_POWER_JOURNALS = {
    "ieee transactions on smart grid",
    "ieee transactions on power systems",
    "ieee transactions on sustainable energy",
    "ieee transactions on transportation electrification",
    "applied energy",
    "advances in applied energy",
    "energy conversion and management",
    "renewable energy",
    "energy",
}

DISCOVERY_REQUIRED_GROUPS = {
    "\u7535\u529b\u7cfb\u7edf\u4f18\u5316",
    "\u6e90\u8377\u9884\u6d4b",
    "\u8f66\u7f51\u4e92\u52a8",
    "\u7535\u7f51\u97e7\u6027",
    "\u7a33\u5b9a\u6027",
    "\u6784\u7f51\u578b",
}


def score_records(records: list[PaperRecord], settings: Settings) -> list[PaperRecord]:
    for record in records:
        matched_keywords = _extract_matched_keywords(record)
        record.matched_keywords = matched_keywords
        record.matched_keyword_groups = _extract_matched_keyword_groups(matched_keywords)
        record.rule_score = round(_calculate_rule_score(record, settings, matched_keywords), 2)
        record.llm_score = record.rule_score
        record.final_score = record.rule_score
        record.relevance_label = _label_for_score(record.rule_score)
        record.score_reason = _build_reason(record, settings)
    return records


def passes_rule_gate(record: PaperRecord) -> bool:
    return _has_minimum_relevance(record)


def passes_display_gate(record: PaperRecord, llm_enabled: bool) -> bool:
    if not _has_minimum_relevance(record):
        return False

    if llm_enabled:
        return record.final_score >= 6.0

    return record.rule_score >= 6.0


def _calculate_rule_score(record: PaperRecord, settings: Settings, matched_keywords: list[str]) -> float:
    title_lower = record.title.lower()

    domain_score = 0.0
    method_score = 0.0
    broad_keyword_hits = 0

    for keyword in matched_keywords:
        weight = CORE_KEYWORDS[keyword]
        occurrence_weight = 1.0 if _keyword_in_text(keyword, title_lower) else 0.55
        contribution = weight * occurrence_weight
        group_name = KEYWORD_TO_GROUP[keyword]

        if group_name in DOMAIN_GROUPS:
            domain_score += contribution
        elif group_name in METHOD_GROUPS:
            method_score += contribution

        if keyword in BROAD_RELEVANCE_KEYWORDS:
            broad_keyword_hits += 1

    score = 0.0
    score += min(domain_score, 5.35)
    score += min(method_score, 1.55)
    score += _power_system_signal_bonus(record)
    score += min(len(record.matched_keyword_groups) * 0.2, 0.65)
    score += _journal_priority(record)
    score += _recency_bonus(record, settings)
    score += _metadata_quality_bonus(record)

    if broad_keyword_hits >= 4:
        score += 0.45
    elif broad_keyword_hits >= 2:
        score += 0.22

    score -= _material_risk_penalty(record)
    score -= _stability_priority_penalty(record)

    if record.source == "arxiv":
        primary_category = (record.metadata.get("primary_category") or "").lower()
        if primary_category in {category.lower() for category in settings.arxiv_categories}:
            score += 0.25

    return max(0.0, min(score, 10.0))


def _extract_matched_keywords(record: PaperRecord) -> list[str]:
    title_lower = record.title.lower()
    abstract_lower = record.abstract_raw.lower()
    matches = [keyword for keyword in CORE_KEYWORDS if _keyword_in_text(keyword, title_lower) or _keyword_in_text(keyword, abstract_lower)]
    matches.sort(key=lambda keyword: CORE_KEYWORDS[keyword], reverse=True)
    return matches[:6]


def _keyword_in_text(keyword: str, text: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _extract_matched_keyword_groups(matched_keywords: list[str]) -> list[str]:
    groups: list[str] = []
    for keyword in matched_keywords:
        group_name = KEYWORD_TO_GROUP.get(keyword)
        if group_name and group_name not in groups:
            groups.append(group_name)
    return groups


def _has_minimum_relevance(record: PaperRecord) -> bool:
    journal_lower = record.journal.lower()
    broad_hits = sum(1 for keyword in record.matched_keywords if keyword in BROAD_RELEVANCE_KEYWORDS)
    text = f"{record.title} {record.abstract_raw}".lower()
    power_context = any(term in text for term in POWER_CONTEXT_TERMS)
    material_dominated = _material_risk_penalty(record) >= 1.6

    if material_dominated:
        return False

    if journal_lower in CORE_POWER_JOURNALS:
        return broad_hits >= 1 or power_context

    has_required_group = any(group in DISCOVERY_REQUIRED_GROUPS for group in record.matched_keyword_groups)
    has_method_group = "AI+Optimization" in record.matched_keyword_groups
    power_signal_hits = sum(1 for keyword in record.matched_keywords if keyword in POWER_SYSTEM_SIGNAL_KEYWORDS)

    if power_signal_hits >= 1 and (has_required_group or has_method_group):
        return True

    if has_method_group and power_context and broad_hits >= 1:
        return True

    return False


def _power_system_signal_bonus(record: PaperRecord) -> float:
    signal_hits = sum(1 for keyword in record.matched_keywords if keyword in POWER_SYSTEM_SIGNAL_KEYWORDS)
    return min(signal_hits * 0.55, 1.65)


def _material_risk_penalty(record: PaperRecord) -> float:
    text = f"{record.title} {record.abstract_raw}".lower()
    risk_hits = sum(1 for term in MATERIAL_RISK_TERMS if term in text)
    if risk_hits == 0:
        return 0.0

    broad_hits = sum(1 for keyword in record.matched_keywords if keyword in BROAD_RELEVANCE_KEYWORDS)
    if broad_hits == 0:
        return 3.0
    if broad_hits == 1:
        return 1.7
    return 0.6


def _stability_priority_penalty(record: PaperRecord) -> float:
    matched_groups = set(record.matched_keyword_groups)
    if not matched_groups or not (matched_groups & STABILITY_PRIORITY_GROUPS):
        return 0.0

    if matched_groups & OPTIMIZATION_PRIORITY_GROUPS:
        return 0.0

    if matched_groups <= STABILITY_PRIORITY_GROUPS:
        return 1.15

    return 0.45


def _journal_priority(record: PaperRecord) -> float:
    configured_weight = record.metadata.get("journal_weight")
    if isinstance(configured_weight, (int, float)):
        return float(configured_weight)
    return JOURNAL_PRIORITIES.get(record.journal.lower(), JOURNAL_PRIORITIES.get(record.source, 0.4))


def _metadata_quality_bonus(record: PaperRecord) -> float:
    score = 0.0
    journal_lower = record.journal.lower()
    fallback_source = record.metadata.get("fallback_source")
    abstract_length = len(record.abstract_raw)
    if abstract_length > 1400:
        score += 0.85
    elif abstract_length > 800:
        score += 0.6
    elif abstract_length > 350:
        score += 0.3
    elif (
        abstract_length < 120
        and journal_lower not in CORE_POWER_JOURNALS
        and fallback_source != "arxiv_recent_page"
    ):
        score -= 0.7

    author_count = len(record.authors)
    if 3 <= author_count <= 8:
        score += 0.45
    elif author_count > 8:
        score += 0.2

    title_word_count = len(record.title.split())
    if title_word_count < 5:
        score -= 0.35
    elif 6 <= title_word_count <= 18:
        score += 0.35
    elif title_word_count > 28:
        score -= 0.2

    return score


def _current_local_date(settings: Settings):
    return datetime.now(ZoneInfo(settings.timezone_name)).date()


def _recency_bonus(record: PaperRecord, settings: Settings) -> float:
    published_local = record.published_at_local(settings.timezone_name).date()
    days_old = max((_current_local_date(settings) - published_local).days, 0)
    if days_old <= 0:
        return 2.35
    if days_old == 1:
        return 1.9
    if days_old <= 3:
        return 1.45
    if days_old <= 7:
        return 1.05
    if days_old <= 14:
        return 0.55
    if days_old <= 21:
        return 0.15
    if days_old <= 30:
        return -0.55
    if days_old <= 45:
        return -1.55
    return -2.6


def _label_for_score(score: float) -> str:
    if score >= 7.0:
        return "Strong Match"
    if score >= 5.4:
        return "Promising"
    return "Background Read"


def _build_reason(record: PaperRecord, settings: Settings) -> str:
    published_local = record.published_at_local(settings.timezone_name).date()
    days_old = max((_current_local_date(settings) - published_local).days, 0)
    recency_text = {0: "today", 1: "yesterday"}.get(days_old, f"{days_old} days ago")
    if record.matched_keywords:
        return f"Published {recency_text}; strongest signals: {', '.join(record.matched_keywords[:3])}."
    if not record.abstract_raw:
        return f"Published {recency_text}; metadata-only match from a high-value source."
    return f"Published {recency_text}; selected by combined relevance, recency, and source quality."
