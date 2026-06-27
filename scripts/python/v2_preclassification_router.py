from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


CONTROLLED_ABSTENTION = "insufficient_evidence"


MODELING_TERMS = [
    "simulation", "simulations", "system dynamics", "world3", "world 3",
    "scenario", "scenarios", "projection", "projections", "forecast",
    "forecasting", "estimate", "estimating", "model", "modelling",
    "modeling", "assumption", "assumptions", "feedback", "sensitivity",
    "resembles the classic limits to growth simulations", "model performance",
]
FOUNDATIONAL_TERMS = [
    "exhaustible resources", "resource constraints", "resources probably",
    "finite planet", "limitless growth",
    "constrain economic growth", "constrains economic growth",
    "population overshoot", "overshoot and collapse", "collapse",
    "food", "pollution", "interlocking resources",
]
HISTORICAL_TERMS = [
    "first exercises", "one of the first", "publication", "published",
    "documented in", "sold over", "founding text", "landmark", "seminal",
    "classic", "famous", "influential", "influence", "adoption",
    "adopted", "readership", "50 years", "more than 50 years",
    "immediately followed", "released its report", "main challenge",
]
POLICY_TERMS = [
    "policy", "governance", "planning", "regulation", "management",
    "institutional decision", "decision-making", "public decision-making",
    "strategy", "strategic planning",
]
BIBLIOGRAPHY_PATTERN = re.compile(
    r"^[A-Z][A-Za-z'\-]+(?:\s+[A-Z]\.?|\s+[A-Z][a-z]+)?(?:,\s*|\s+and\s+).{0,180}\(\d{4}\)\s+[^.]{5,120}\.?$"
)


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def normalized_text(row: Dict[str, str]) -> str:
    fields = [
        row.get("citation_sentence", ""),
        row.get("sentence_before", ""),
        row.get("sentence_after", ""),
        row.get("context_window", ""),
        row.get("snippet_clean", ""),
    ]
    return " ".join(part.strip() for part in fields if part and part.strip())


def primary_context(row: Dict[str, str]) -> str:
    return (
        row.get("citation_sentence", "").strip()
        or row.get("context_window", "").strip()
        or row.get("snippet_clean", "").strip()
    )


def first_exact(context: str, terms: Iterable[str]) -> str:
    context_lower = context.lower()
    for term in terms:
        pos = context_lower.find(term.lower())
        if pos >= 0:
            return context[pos:pos + len(term)]
    return ""


def exact_seed_quote(context: str) -> str:
    patterns = [
        r"Limits to Growth[^.;,\)]*(?:\(Meadows[^)]*\))?",
        r"Meadows et al\.?,?\s*1972",
        r"Meadows[^.;,\)]*\(1972\)",
        r"Club of Rome[^.;]*(?:Limits to Growth|Meadows)",
    ]
    for pattern in patterns:
        match = re.search(pattern, context, flags=re.IGNORECASE)
        if match:
            return match.group(0)[:280]
    return context[:120].strip()


def topic_from_context(context: str, function: str) -> str:
    lower = context.lower()
    if any(term in lower for term in ["system dynamics", "simulation", "simulations", "model", "modelling", "modeling", "world3", "world 3"]):
        return "system_dynamics_modeling"
    if any(term in lower for term in ["economic growth", "economics"]):
        return "economics_growth"
    if any(term in lower for term in ["population", "resources", "food", "pollution", "overshoot", "collapse"]):
        return "population_resources"
    if any(term in lower for term in ["policy", "governance", "planning", "regulation", "management"]):
        return "environmental_policy"
    if function == "historical_framing" and any(term in lower for term in ["50 years", "published", "publication", "sold over", "founding text", "followed"]):
        return "historical_or_cultural_memory"
    if "sustainab" in lower or "environmentalism" in lower:
        return "sustainability"
    if "limits to growth" in lower or "ltg" in lower:
        return "limits_to_growth"
    return "unclear"


def is_seed_identified(context: str) -> bool:
    lower = context.lower()
    return (
        "meadows" in lower
        or "limits to growth" in lower
        or "club of rome" in lower
        or "ltg" in lower
        or "world3" in lower
    )


def true_bibliography(row: Dict[str, str], context: str) -> bool:
    if row.get("citation_section") == "BIBLIO":
        return True
    if boolish(row.get("bibliography_detected")) and len(context.split()) < 35:
        return True
    return bool(BIBLIOGRAPHY_PATTERN.search(context.strip()))


def severe_ocr_or_incoherent(row: Dict[str, str], context: str) -> bool:
    lower = context.lower()
    words = re.findall(r"[A-Za-z]{2,}", context)
    if len(words) < 9 and "meadows" in lower and "limits to growth" not in lower:
        return True
    if "conception of the past" in lower and "limits to growth" not in lower:
        return True
    if context.count("(") != context.count(")") and len(words) < 25:
        return True
    return False


def make_result(
    row: Dict[str, str],
    function: str,
    topic: str,
    stance: str,
    evidence_function: str,
    evidence_topic: str,
    evidence_stance: str,
    confidence: float,
    flags: List[str],
    needs_review: bool,
    reason: str,
) -> Dict[str, Any]:
    limited_context = not row.get("citation_sentence", "").strip() or not (
        row.get("sentence_before", "").strip() or row.get("sentence_after", "").strip()
    )
    final_needs_review = needs_review or (limited_context and function != "bibliographic_only")
    if flags and flags != ["none"] and flags != ["bibliography_only"]:
        final_needs_review = True
    return {
        "context_id": row.get("canonical_context_id") or row.get("mention_level_id", ""),
        "context_group_id": row.get("context_group_id", ""),
        "citation_function": function,
        "topic_or_discourse_area": topic,
        "stance_toward_seed": stance,
        "evidence_quote_function": evidence_function or CONTROLLED_ABSTENTION,
        "evidence_quote_topic": evidence_topic or CONTROLLED_ABSTENTION,
        "evidence_quote_stance": evidence_stance or CONTROLLED_ABSTENTION,
        "confidence_function": confidence,
        "confidence_topic": min(confidence, 0.82) if topic != "unclear" else 0.45,
        "confidence_stance": 0.84 if stance == "neutral_descriptive" else (0.78 if stance == "supportive" else 0.45),
        "uncertainty_flags": flags or ["none"],
        "needs_human_review": final_needs_review,
        "reasoning_summary": reason[:220],
    }


@dataclass
class Route:
    routing_decision: str
    routed_citation_function: str
    routed_topic_or_discourse_area: str
    routed_stance_toward_seed: str
    routing_confidence: float
    routing_reason: str
    send_to_llm: bool
    force_needs_human_review: bool
    rule_hits: List[str]
    result: Dict[str, Any] | None = None


def route_context(row: Dict[str, str]) -> Route:
    context = primary_context(row)
    all_context = normalized_text(row)
    lower = all_context.lower()
    if not context:
        result = make_result(
            row, "unclear", "unclear", "unclear", CONTROLLED_ABSTENTION,
            CONTROLLED_ABSTENTION, CONTROLLED_ABSTENTION, 0.35,
            ["missing_surrounding_context"], True, "No usable context was available."
        )
        return Route("deterministic_unclear", "unclear", "unclear", "unclear", 0.35, result["reasoning_summary"], False, True, ["missing_context"], result)

    if true_bibliography(row, context):
        quote = exact_seed_quote(context)
        result = make_result(
            row, "bibliographic_only", "unclear", "unclear", quote,
            CONTROLLED_ABSTENTION, CONTROLLED_ABSTENTION, 0.92,
            ["bibliography_only"], False, "Reference-list syntax indicates bibliography-only use."
        )
        return Route("deterministic_bibliography", "bibliographic_only", "unclear", "unclear", 0.92, result["reasoning_summary"], False, False, ["bibliographic_only"], result)

    if not is_seed_identified(all_context) or severe_ocr_or_incoherent(row, all_context):
        flags = ["ocr_noise"] if severe_ocr_or_incoherent(row, all_context) else ["ambiguous_referent"]
        result = make_result(
            row, "unclear", "unclear", "unclear", CONTROLLED_ABSTENTION,
            CONTROLLED_ABSTENTION, CONTROLLED_ABSTENTION, 0.42,
            flags, True, "Context is too incoherent or ambiguous for deterministic interpretation."
        )
        return Route("deterministic_unclear", "unclear", "unclear", "unclear", 0.42, result["reasoning_summary"], False, True, flags, result)

    function_context = row.get("citation_sentence", "").strip() or context
    function_lower = function_context.lower()
    modeling_hit = first_exact(function_context, MODELING_TERMS)
    foundational_hit = first_exact(function_context, FOUNDATIONAL_TERMS)
    historical_hit = first_exact(function_context, HISTORICAL_TERMS)
    policy_hit = first_exact(function_context, POLICY_TERMS)

    rule_hits = []
    weak_modeling_only = (
        modeling_hit.lower() in {"scenario", "scenarios", "projection", "projections", "forecast", "forecasting"}
        and historical_hit
        and not any(term in function_lower for term in ["simulation", "simulations", "system dynamics", "world3", "world 3", "model", "modelling", "modeling", "resembles"])
    )
    if modeling_hit and weak_modeling_only:
        return Route("llm_gray_zone", "modeling_simulation_reference", topic_from_context(all_context, "modeling_simulation_reference"), "neutral_descriptive", 0.58, "Scenario language overlaps with historical framing and needs contextual judgment.", True, True, rule_hits)

    if modeling_hit:
        rule_hits.append("modeling")
    if foundational_hit:
        rule_hits.append("foundational")
    if historical_hit:
        rule_hits.append("historical")
    if policy_hit:
        rule_hits.append("policy")

    # Modeling evidence is intentionally prioritized over historical words such
    # as "classic" because prior regressions overused historical framing.
    if modeling_hit:
        stance = "supportive" if re.search(r"\bremarkable success\b|\bsuccess\b|\bsuccessful\b", all_context, re.I) else "neutral_descriptive"
        stance_quote = first_exact(all_context, ["remarkable success", "success", "successful"]) if stance == "supportive" else CONTROLLED_ABSTENTION
        topic = topic_from_context(all_context, "modeling_simulation_reference")
        result = make_result(
            row, "modeling_simulation_reference", topic, stance, modeling_hit,
            first_exact(function_context, ["system dynamics", "simulations", "model", "modelling", "modeling"]) or modeling_hit,
            stance_quote, 0.88, ["none"] if len(all_context.split()) >= 16 else ["snippet_too_short"],
            len(all_context.split()) < 16, "Explicit modeling/simulation language determines the citation function."
        )
        return Route("deterministic_modeling", "modeling_simulation_reference", topic, stance, 0.88, result["reasoning_summary"], False, result["needs_human_review"], rule_hits, result)

    if foundational_hit and not policy_hit:
        topic = topic_from_context(all_context, "foundational_citation")
        result = make_result(
            row, "foundational_citation", topic, "neutral_descriptive", foundational_hit,
            foundational_hit, CONTROLLED_ABSTENTION, 0.86,
            ["none"] if len(all_context.split()) >= 14 else ["snippet_too_short"],
            len(all_context.split()) < 14, "A visible Meadows claim is used as a substantive premise."
        )
        return Route("deterministic_foundational", "foundational_citation", topic, "neutral_descriptive", 0.86, result["reasoning_summary"], False, result["needs_human_review"], rule_hits, result)

    if policy_hit and not (modeling_hit or foundational_hit):
        # Clear policy/governance language is still sent to the LLM unless it
        # directly performs policy work around the citation event.
        return Route("llm_gray_zone", "policy_governance_framing", topic_from_context(all_context, "policy_governance_framing"), "neutral_descriptive", 0.62, "Policy language is present but function needs contextual judgment.", True, True, rule_hits)

    if historical_hit:
        topic = topic_from_context(all_context, "historical_framing")
        result = make_result(
            row, "historical_framing", topic, "neutral_descriptive", historical_hit,
            exact_seed_quote(all_context), CONTROLLED_ABSTENTION, 0.84,
            ["none"] if len(all_context.split()) >= 14 else ["snippet_too_short"],
            len(all_context.split()) < 14, "The citation event primarily places Meadows in historical or publication context."
        )
        return Route("deterministic_historical", "historical_framing", topic, "neutral_descriptive", 0.84, result["reasoning_summary"], False, result["needs_human_review"], rule_hits, result)

    return Route("llm_gray_zone", "unclear", topic_from_context(all_context, "unclear"), "unclear", 0.5, "Coherent context remains ambiguous after deterministic routing.", True, True, rule_hits or ["gray_zone"])


def route_to_record(row: Dict[str, str], route: Route) -> Dict[str, Any]:
    return {
        "context_group_id": row.get("context_group_id", ""),
        "context_id": row.get("canonical_context_id") or row.get("mention_level_id", ""),
        "routing_decision": route.routing_decision,
        "routed_citation_function": route.routed_citation_function,
        "routed_topic_or_discourse_area": route.routed_topic_or_discourse_area,
        "routed_stance_toward_seed": route.routed_stance_toward_seed,
        "routing_confidence": route.routing_confidence,
        "routing_reason": route.routing_reason,
        "send_to_llm": route.send_to_llm,
        "force_needs_human_review": route.force_needs_human_review,
        "rule_hits": " | ".join(route.rule_hits),
    }
