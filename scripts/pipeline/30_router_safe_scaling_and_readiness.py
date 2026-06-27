#!/usr/bin/env python3
"""Prepare router-safe scaling and gray-zone remediation artifacts."""

from __future__ import annotations

import csv
import hashlib
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.python.v2_preclassification_router import route_context


TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
PROCESSED = ROOT / "analysis/data/processed"


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def safe_float(value: Any, default: float = 0.7) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def decade(year: str) -> str:
    try:
        y = int(float(year))
    except (TypeError, ValueError):
        return "unknown"
    return f"{(y // 10) * 10}s"


def group_id_for(row: Dict[str, str]) -> str:
    raw = row.get("context_id") or row.get("hit_id") or row.get("snippet_hash") or row.get("snippet", "")
    return "cg_scale_" + hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]


def enriched_to_v2(row: Dict[str, str]) -> Dict[str, str]:
    context_id = row.get("context_id") or row.get("hit_id") or group_id_for(row)
    return {
        "context_group_id": group_id_for(row),
        "mention_level_id": context_id,
        "canonical_context_id": context_id,
        "title": row.get("canonical_title", ""),
        "year": row.get("year", ""),
        "venue": row.get("venue", ""),
        "page": row.get("page", ""),
        "citation_section": row.get("citation_section") or ("BIBLIO" if boolish(row.get("is_biblio_any")) else "BODY"),
        "mention_type": row.get("mention_type", ""),
        "snippet_clean": row.get("snippet") or "",
        "context_window": row.get("surrounding_sentence_window") or row.get("snippet") or "",
        "citation_sentence": row.get("sentence") or row.get("snippet") or "",
        "sentence_before": "",
        "sentence_after": "",
        "bibliography_detected": str(boolish(row.get("is_biblio_any")) or boolish(row.get("bib_like"))).lower(),
        "bibliography_score": row.get("biblio_score") or "0",
        "extraction_confidence": row.get("extraction_confidence") or "0.6",
        "source_database": row.get("source_database", ""),
        "document_type": row.get("document_type", ""),
        "false_positive_risk": row.get("false_positive_risk", ""),
        "source_context_id": context_id,
        "work_id": row.get("work_id", ""),
    }


def category_from_route(decision: str) -> str:
    return {
        "deterministic_bibliography": "true_bibliography_only",
        "deterministic_modeling": "explicit_modeling_simulation_language",
        "deterministic_foundational": "explicit_foundational_resource_constraint_claim",
        "deterministic_historical": "clear_historical_publication_lineage",
        "deterministic_unclear": "severe_ocr_incoherent_unclear_human_review",
    }.get(decision, "not_router_safe")


def category_definitions() -> List[Dict[str, str]]:
    return [
        {
            "router_safe_category": "true_bibliography_only",
            "inclusion_criteria": "Reference-list syntax, bibliography page/section, or unambiguous citation record with no body-text interpretation.",
            "exclusion_criteria": "Body-text publication history, influence claims, editions, sales, or lineage prose.",
            "required_evidence_terms_patterns": "bibliography_detected=true; citation_section=BIBLIO; author-year-title reference syntax.",
            "risk_level": "low",
            "required_spot_check_rate": "10% or at least 10 if available",
            "report_topic_labels": "no",
            "report_stance_labels": "no",
        },
        {
            "router_safe_category": "explicit_modeling_simulation_language",
            "inclusion_criteria": "Citation event explicitly mentions simulation, model/modeling, system dynamics, World3, scenarios, forecasts, projections, assumptions, feedback, sensitivity, resemblance, or model performance.",
            "exclusion_criteria": "Paper is about modeling but the citation event only provides historical background.",
            "required_evidence_terms_patterns": "simulation; model; system dynamics; World3; scenario; forecast; projection; feedback; sensitivity; resembles.",
            "risk_level": "medium",
            "required_spot_check_rate": "15% or at least 10 if available",
            "report_topic_labels": "only with caveat",
            "report_stance_labels": "only if explicit evaluative evidence is present",
        },
        {
            "router_safe_category": "explicit_foundational_resource_constraint_claim",
            "inclusion_criteria": "Citation event uses a visible Meadows-related claim about finite resources, growth limits, population, overshoot, collapse, pollution, or resource constraints as a premise.",
            "exclusion_criteria": "Generic title mention, historical landmark sentence, or sustainability topic language without a substantive claim.",
            "required_evidence_terms_patterns": "finite planet; exhaustible resources; constrain economic growth; overshoot; collapse; population; pollution; interlocking resources.",
            "risk_level": "medium-high",
            "required_spot_check_rate": "20% or at least 10 if available",
            "report_topic_labels": "only exploratory",
            "report_stance_labels": "no, unless explicit evaluative evidence is present",
        },
        {
            "router_safe_category": "clear_historical_publication_lineage",
            "inclusion_criteria": "Citation event clearly concerns publication history, chronology, editions, influence, adoption, readership, landmark status, or intellectual lineage.",
            "exclusion_criteria": "Visible modeling behavior, substantive Meadows claim used as a premise, or policy/governance action.",
            "required_evidence_terms_patterns": "publication; published; documented in; sold; founding text; landmark; seminal; classic; 50 years; followed by; released report.",
            "risk_level": "medium",
            "required_spot_check_rate": "15% or at least 10 if available",
            "report_topic_labels": "only with caveat",
            "report_stance_labels": "neutral/descriptive only; no evaluative claims without evidence",
        },
        {
            "router_safe_category": "severe_ocr_incoherent_unclear_human_review",
            "inclusion_criteria": "Context is unreadable, syntactically incoherent, ambiguous seed identification, or too damaged for interpretation.",
            "exclusion_criteria": "Short but coherent context with explicit modeling, foundational, historical, or bibliography evidence.",
            "required_evidence_terms_patterns": "ocr_noise flag; incoherent syntax; ambiguous referent; missing usable context.",
            "risk_level": "high for interpretation, low for abstention",
            "required_spot_check_rate": "20% or at least 10 if available",
            "report_topic_labels": "no",
            "report_stance_labels": "no",
        },
    ]


def router_safe_candidates() -> List[Dict[str, Any]]:
    candidates = []
    seen = set()
    for raw in read_csv(PROCESSED / "citation_contexts_enriched.csv"):
        row = enriched_to_v2(raw)
        if row["context_group_id"] in seen:
            continue
        seen.add(row["context_group_id"])
        route = route_context(row)
        if route.send_to_llm:
            continue
        category = category_from_route(route.routing_decision)
        result = route.result or {}
        candidates.append({
            "context_group_id": row["context_group_id"],
            "source_context_id": row["source_context_id"],
            "work_id": row.get("work_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "decade": decade(row.get("year", "")),
            "venue": row.get("venue", ""),
            "field_or_venue": row.get("venue") or row.get("source_database") or "unknown",
            "citation_sentence": row.get("citation_sentence", ""),
            "context_window": row.get("context_window", ""),
            "legacy_snippet": row.get("snippet_clean", ""),
            "router_citation_function": route.routed_citation_function,
            "router_topic_or_discourse_area": route.routed_topic_or_discourse_area,
            "router_stance_toward_seed": route.routed_stance_toward_seed,
            "router_confidence": route.routing_confidence,
            "routing_reason": route.routing_reason,
            "rule_hits": " | ".join(route.rule_hits),
            "needs_human_review": result.get("needs_human_review", route.force_needs_human_review),
            "stratum_category": category,
            "extraction_confidence": row.get("extraction_confidence", ""),
            "ocr_or_bibliography_flags": " | ".join(flag for flag in [
                "bibliography_detected" if boolish(row.get("bibliography_detected")) else "",
                "low_extraction_confidence" if safe_float(row.get("extraction_confidence")) < 0.55 else "",
                "ocr_or_unclear" if route.routing_decision == "deterministic_unclear" else "",
            ] if flag),
            "bibliography_detected": row.get("bibliography_detected", ""),
            "citation_section": row.get("citation_section", ""),
        })
    return candidates


def spotcheck_sample(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected = []
    for category, rows in sorted(groupby(candidates, "stratum_category").items()):
        target = min(len(rows), max(10, math.ceil(len(rows) * 0.10)))
        rows = sorted(
            rows,
            key=lambda row: (
                str(row.get("needs_human_review")) != "True",
                row.get("decade", ""),
                row.get("field_or_venue", ""),
                row.get("context_group_id", ""),
            ),
        )
        selected.extend(rows[:target])
    out = []
    for row in selected:
        with_blanks = dict(row)
        with_blanks.update({
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "spotcheck_result": "",
            "spotcheck_issue_type": "",
        })
        out.append(with_blanks)
    return out


def groupby(rows: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key, "unknown") or "unknown")].append(row)
    return groups


def gray_zone_remediation() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    summary = read_csv(TABLES / "gray_zone_failure_mode_summary.csv")
    info = {
        "short_context": ("extraction", "high", "high", "medium", "no", "yes", "yes"),
        "evidence_quote_failure": ("prompt_validator", "high", "high", "low-medium", "yes for benchmark only", "yes for sample", "yes"),
        "uncertainty_policy_failure": ("validator_prompt", "high", "medium-high", "low", "yes for benchmark only", "yes for sample", "yes"),
        "historical_vs_foundational": ("router", "medium", "medium", "low", "no", "yes for spot check", "yes"),
        "ocr_or_text_quality": ("extraction", "medium-high", "medium", "high", "no", "yes", "yes"),
        "policy_governance_ambiguity": ("human_review", "medium", "low", "low", "maybe later", "yes", "limited"),
        "true_interpretive_gray_zone": ("human_review_or_benchmark", "medium", "low", "medium", "yes if context adequate", "yes", "limited"),
    }
    rows = []
    triage = []
    readiness = []
    for row in summary:
        mode = row["failure_mode_family"]
        fix_type, priority, impact, effort, api, human, readiness_effect = info.get(mode, ("human_review", "medium", "unknown", "medium", "no", "yes", "limited"))
        rows.append({
            "failure_mode": mode,
            "next_intervention": intervention_for(mode),
            "intervention_type": fix_type,
            "priority": priority,
            "expected_impact": impact,
            "estimated_implementation_effort": effort,
            "new_api_calls_needed": api,
            "human_coding_needed": human,
            "affects_meadows_impact_readiness": readiness_effect,
            "n_cases": row.get("n", ""),
            "accepted_n": row.get("accepted_n", ""),
            "rejected_n": row.get("rejected_n", ""),
        })
        triage.append({
            "failure_mode": mode,
            "count": row.get("n", ""),
            "percent_of_gray_zone_cases": row.get("pct", ""),
            "accepted_count": row.get("accepted_n", ""),
            "rejected_count": row.get("rejected_n", ""),
            "fix_type": fix_type,
            "expected_accuracy_gain": impact,
            "implementation_effort": effort,
            "estimated_cost": cost_for(fix_type),
            "requires_new_api_calls": api,
            "requires_human_review": human,
            "candidate_for_model_benchmark": "yes" if mode in {"evidence_quote_failure", "uncertainty_policy_failure", "policy_governance_ambiguity", "true_interpretive_gray_zone"} else "no",
            "recommended_priority": priority,
            "ranking_note": ranking_note(mode),
        })
        primary = primary_problem(mode)
        readiness.append({
            "failure_mode": mode,
            "primary_problem": primary,
            "benchmarking_stronger_model_likely_to_help": benchmark_help(mode),
            "expected_benchmark_benefit": benchmark_benefit(mode),
            "benchmark_readiness": benchmark_readiness(mode),
            "reason": benchmark_reason(mode),
        })
    return rows, triage, readiness


def intervention_for(mode: str) -> str:
    return {
        "short_context": "Recover adjacent sentences or reconstruct citation sentence before rerunning classifier.",
        "evidence_quote_failure": "Tighten exact-evidence prompting, add repair pass, and benchmark only after context is adequate.",
        "uncertainty_policy_failure": "Fix uncertainty flag contract and validator-facing prompt examples.",
        "historical_vs_foundational": "Review cases for narrowly generalizable resource-premise router rules.",
        "ocr_or_text_quality": "Improve OCR/text cleanup or mark as unclear with human review.",
        "policy_governance_ambiguity": "Human-code a targeted sample; avoid broad policy router rules.",
        "true_interpretive_gray_zone": "Human adjudication first; consider small model benchmark only with adequate context.",
    }.get(mode, "Targeted human review.")


def cost_for(fix_type: str) -> str:
    if "extraction" in fix_type:
        return "engineering time; no API required"
    if "router" in fix_type:
        return "low engineering plus spot checks"
    if "prompt" in fix_type or "validator" in fix_type:
        return "moderate; small API benchmark after changes"
    if "benchmark" in fix_type:
        return "API cost plus human adjudication"
    return "human review time"


def ranking_note(mode: str) -> str:
    return {
        "evidence_quote_failure": "highest-impact methodology fix",
        "uncertainty_policy_failure": "low-cost contract fix",
        "short_context": "largest extraction-readiness gain",
        "historical_vs_foundational": "lowest-cost router improvement",
        "ocr_or_text_quality": "important for abstention reliability",
        "policy_governance_ambiguity": "human interpretation bottleneck",
        "true_interpretive_gray_zone": "benchmark only after human coding",
    }.get(mode, "")


def primary_problem(mode: str) -> str:
    return {
        "short_context": "extraction",
        "evidence_quote_failure": "prompting/validation",
        "uncertainty_policy_failure": "validation",
        "historical_vs_foundational": "routing",
        "ocr_or_text_quality": "extraction",
        "policy_governance_ambiguity": "human interpretation",
        "true_interpretive_gray_zone": "human interpretation",
    }.get(mode, "human interpretation")


def benchmark_help(mode: str) -> str:
    return "yes" if mode in {"policy_governance_ambiguity", "true_interpretive_gray_zone"} else ("possibly after fixes" if mode in {"evidence_quote_failure", "uncertainty_policy_failure"} else "no")


def benchmark_benefit(mode: str) -> str:
    return {
        "short_context": "none",
        "ocr_or_text_quality": "none",
        "historical_vs_foundational": "low",
        "evidence_quote_failure": "low until prompt/validator fixed",
        "uncertainty_policy_failure": "low until validator contract fixed",
        "policy_governance_ambiguity": "moderate",
        "true_interpretive_gray_zone": "moderate",
    }.get(mode, "low")


def benchmark_readiness(mode: str) -> str:
    return "ready_later" if mode in {"policy_governance_ambiguity", "true_interpretive_gray_zone"} else "not_ready"


def benchmark_reason(mode: str) -> str:
    return {
        "short_context": "Context quality is the bottleneck.",
        "ocr_or_text_quality": "OCR/text quality is the bottleneck.",
        "historical_vs_foundational": "A targeted router/codebook rule is cheaper and more transparent.",
        "evidence_quote_failure": "The model failed the evidence contract, not necessarily reasoning.",
        "uncertainty_policy_failure": "The output contract failed before model reasoning can be assessed.",
        "policy_governance_ambiguity": "Adequate context may benefit from comparing model reasoning after human labels exist.",
        "true_interpretive_gray_zone": "A small benchmark may help after human adjudication defines the target.",
    }.get(mode, "")


def extraction_tables() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    gray = read_csv(TABLES / "gray_zone_analysis.csv")
    cases = []
    for row in gray:
        if row["failure_mode_family"] not in {"short_context", "ocr_or_text_quality"} and "missing_surrounding_context" not in row.get("v2_uncertainty_flags", "") and safe_float(row.get("extraction_confidence")) >= 0.55:
            continue
        body = " ".join([row.get("citation_sentence", ""), row.get("context_window", ""), row.get("legacy_snippet", "")])
        has_window = bool(row.get("citation_sentence") or row.get("context_window"))
        ocr = row["failure_mode_family"] == "ocr_or_text_quality" or "ocr" in body.lower()
        cases.append({
            "context_group_id": row["context_group_id"],
            "failure_mode_family": row["failure_mode_family"],
            "stratum": row["stratum"],
            "title": row["title"],
            "year": row["year"],
            "legacy_snippet": row["legacy_snippet"],
            "likely_recoverable_with_adjacent_sentence_expansion": str(not has_window).lower(),
            "likely_recoverable_with_improved_ocr": str(ocr).lower(),
            "likely_recoverable_with_citation_sentence_reconstruction": str(not row.get("citation_sentence")).lower(),
            "fundamentally_insufficient_evidence": str((not body.strip()) or (ocr and len(body.split()) < 20)).lower(),
            "expected_confidence_gain": "high" if not has_window else ("medium" if ocr else "low"),
            "expected_reduction_in_human_review": "high" if not has_window and not ocr else "medium",
        })
    recoverable = [row for row in cases if row["fundamentally_insufficient_evidence"] != "true"]
    summary = [
        {"metric": "extraction_candidate_cases", "value": len(cases)},
        {"metric": "potentially_recoverable_cases", "value": len(recoverable)},
        {"metric": "pct_gray_zone_potentially_recoverable", "value": len(recoverable) / max(len(gray), 1)},
        {"metric": "projected_acceptance_rate_effect", "value": "Could improve gray-zone acceptance most by recovering context for short/OCR cases before LLM use."},
        {"metric": "projected_meadows_readiness_effect", "value": "Improves evidence quality for contextual claims, but does not validate corpus-wide prevalence."},
    ]
    return cases, summary


def historical_foundational_review() -> List[Dict[str, Any]]:
    rows = [row for row in read_csv(TABLES / "gray_zone_analysis.csv") if row["failure_mode_family"] == "historical_vs_foundational"]
    out = []
    for row in rows:
        text = " ".join([row.get("citation_sentence", ""), row.get("context_window", ""), row.get("legacy_snippet", "")]).lower()
        resource_pattern = any(term in text for term in ["resource", "finite", "growth", "scarcity", "collapse", "overshoot", "population"])
        out.append({
            "context_group_id": row["context_group_id"],
            "title": row["title"],
            "year": row["year"],
            "v2_citation_function": row["v2_citation_function"],
            "human_primary_role": row["human_primary_role"],
            "v1_llm_primary_role": row["v1_llm_primary_role"],
            "could_deterministic_rule_safely_resolve": str(resource_pattern and bool(row.get("citation_sentence") or row.get("context_window"))).lower(),
            "lexical_trigger_available": str(resource_pattern).lower(),
            "resource_constraint_premise_pattern_available": str(resource_pattern).lower(),
            "human_review_still_required": str(row.get("has_human_label") != "yes").lower(),
            "risk_of_overfitting_if_added": "medium" if resource_pattern else "high",
            "recommend_new_router_rule": "review_first",
            "evidence_text": row.get("citation_sentence") or row.get("context_window") or row.get("legacy_snippet"),
        })
    return out


def meadows_tables() -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    summary = [
        {
            "potential_finding": "Traditional bibliometric diffusion, venues, fields, and network coverage can be reported independently of contextual classifier scaling.",
            "evidence_level": "traditional bibliometric evidence",
            "safe_to_report_now": "yes",
            "report_with_caveat": "yes",
            "exploratory_only": "no",
            "not_ready": "no",
            "caveat": "Respect OpenAlex/database coverage and reference-network limitations.",
        },
        {
            "potential_finding": "Human-reviewed contextual labels can support scoped examples and validation claims.",
            "evidence_level": "human-reviewed contextual evidence",
            "safe_to_report_now": "yes",
            "report_with_caveat": "yes",
            "exploratory_only": "no",
            "not_ready": "no",
            "caveat": "Do not generalize beyond reviewed sample.",
        },
        {
            "potential_finding": "Router-safe contextual classifications can be prepared for scale pending spot checks.",
            "evidence_level": "router-safe contextual evidence pending spot check",
            "safe_to_report_now": "no",
            "report_with_caveat": "yes",
            "exploratory_only": "yes",
            "not_ready": "no",
            "caveat": "Must complete spot-check sample before using as evidence.",
        },
        {
            "potential_finding": "Hybrid accepted but not human-reviewed labels can guide exploration.",
            "evidence_level": "hybrid accepted but not human-reviewed",
            "safe_to_report_now": "no",
            "report_with_caveat": "no",
            "exploratory_only": "yes",
            "not_ready": "no",
            "caveat": "Use for hypothesis generation only.",
        },
        {
            "potential_finding": "Gray-zone unresolved rows are not reportable as contextual findings.",
            "evidence_level": "gray-zone unresolved / not reportable",
            "safe_to_report_now": "no",
            "report_with_caveat": "no",
            "exploratory_only": "no",
            "not_ready": "yes",
            "caveat": "Require remediation or human review.",
        },
    ]
    matrix = [
        claim("Historical framing is common", "hybrid accepted + human-reviewed subset", "hybrid accepted", "Exploratory support in accepted pilot rows, but sample is not corpus-representative.", "no", "yes", "yes", "no"),
        claim("Foundational citations are distinct from historical framing", "human-reviewed boundary work + router review", "human-reviewed contextual", "Supported as a coding distinction; prevalence not established.", "yes", "yes", "no", "no"),
        claim("Modeling/simulation references form a distinct citation function", "router-safe regression and pilot", "router-safe contextual", "Supported as a separable function when explicit modeling language is visible.", "no", "yes", "yes", "no"),
        claim("Bibliography-only citations can be identified structurally", "deterministic router + bibliography-like pilot rows", "router-safe contextual", "Structurally safe pending spot checks.", "no", "yes", "yes", "no"),
        claim("Citation function differs from topic/discourse", "validation failures and codebook redesign", "human-reviewed contextual", "Strong methodological lesson from boundary review.", "yes", "yes", "no", "no"),
        claim("Foundational-to-historical-framing transition", "pilot and boundary hypotheses", "gray-zone unresolved", "Plausible but not decade-validated.", "no", "no", "yes", "no"),
        claim("Topic/discourse distributions", "hybrid output labels", "hybrid accepted", "Topic labels remain weak.", "no", "no", "yes", "yes"),
        claim("Stance distributions", "hybrid output labels", "hybrid accepted", "Mostly neutral/unclear; evaluative stance requires more validation.", "no", "no", "yes", "yes"),
        claim("Policy/governance citation prevalence", "few policy ambiguity cases", "gray-zone unresolved", "Under-sampled and interpretively ambiguous.", "no", "no", "yes", "yes"),
    ]
    return summary, matrix


def claim(claim_text: str, source: str, level: str, support: str, safe: str, caveat: str, exploratory: str, not_ready: str) -> Dict[str, str]:
    return {
        "claim": claim_text,
        "evidence_source": source,
        "evidence_level": level,
        "current_support": support,
        "safe_to_report_now": safe,
        "report_with_caveat": caveat,
        "exploratory_only": exploratory,
        "not_ready": not_ready,
    }


def main() -> None:
    write_csv(TABLES / "router_safe_category_definition.csv", category_definitions())
    candidates = router_safe_candidates()
    write_csv(VALIDATION / "router_safe_scale_candidate_set.csv", candidates)
    write_csv(VALIDATION / "router_safe_spotcheck_sample.csv", spotcheck_sample(candidates))
    remediation, triage, benchmark = gray_zone_remediation()
    write_csv(TABLES / "gray_zone_remediation_plan.csv", remediation)
    write_csv(TABLES / "gray_zone_triage_matrix.csv", triage)
    write_csv(TABLES / "model_benchmark_readiness.csv", benchmark)
    extraction_cases, extraction_summary = extraction_tables()
    write_csv(TABLES / "extraction_improvement_candidate_set.csv", extraction_cases)
    write_csv(TABLES / "extraction_improvement_summary.csv", extraction_summary)
    write_csv(TABLES / "historical_foundational_router_review.csv", historical_foundational_review())
    contextual_summary, claim_matrix = meadows_tables()
    write_csv(TABLES / "meadows_diffusion_ready_contextual_summary.csv", contextual_summary)
    write_csv(TABLES / "meadows_contextual_evidence_levels.csv", contextual_summary)
    write_csv(TABLES / "meadows_claim_readiness_matrix.csv", claim_matrix)
    print(f"Router-safe candidates: {len(candidates)}")
    print(f"Spot-check sample: {len(spotcheck_sample(candidates))}")


if __name__ == "__main__":
    main()
