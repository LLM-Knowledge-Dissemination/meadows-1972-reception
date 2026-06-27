#!/usr/bin/env python3
"""Analyze gray-zone cases from the hybrid 100-context pilot without new LLM calls."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
OUTPUTS = ROOT / "analysis/data/llm_output/v2"
LOGS = ROOT / "analysis/logs"

QUEUE = TABLES / "v2_hybrid_pilot100_llm_queue.csv"
CLASSIFICATIONS = OUTPUTS / "v2_hybrid_pilot100_classifications.csv"
DIAGNOSTIC = LOGS / "v2_hybrid_pilot100_diagnostic.csv"
ERRORS = TABLES / "v2_hybrid_pilot100_validation_errors.csv"
HUMAN_AGREEMENT = TABLES / "v2_hybrid_pilot100_human_agreement.csv"

ACCEPTED = {"router_valid", "initial_valid", "repaired_valid"}


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


def yes(value: str) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def pct(n: int, d: int) -> float | str:
    return n / d if d else ""


def text(row: Dict[str, str]) -> str:
    return " ".join([
        row.get("citation_sentence", ""),
        row.get("sentence_before", ""),
        row.get("sentence_after", ""),
        row.get("context_window", ""),
        row.get("snippet_clean", ""),
        row.get("v2_reasoning_summary", ""),
    ]).lower()


def family_and_mode(row: Dict[str, str], errors: List[str]) -> tuple[str, str]:
    body = text(row)
    human = row.get("human_primary_role", "")
    v2 = row.get("v2_citation_function", "")
    v1 = row.get("v1_llm_primary_role", "")
    if errors:
        if "non_exact_evidence" in errors:
            return "evidence_quote_failure", "llm_used_non_exact_or_paraphrased_evidence"
        if "invalid_uncertainty_flags" in errors:
            return "uncertainty_policy_failure", "llm_returned_invalid_or_contradictory_uncertainty_flags"
        if "unsupported_label_without_evidence" in errors:
            return "evidence_quote_failure", "llm_label_not_supported_by_exact_evidence"
        if "stance_evidence_failure" in errors:
            return "stance_ambiguity", "evaluative_stance_without_valid_stance_evidence"
        if "review_policy_failure" in errors:
            return "uncertainty_policy_failure", "llm_failed_required_human_review_policy"
    if row.get("stratum") == "generic_limits_phrase" or ("limits of growth" in body and "meadows" not in body):
        return "generic_title_or_generic_limits", "generic_limits_phrase_or_title_mention"
    if any(term in body for term in ["ocr", "�", "not yet on the", "rübenach"]) or row.get("stratum") == "ocr_or_low_confidence":
        return "ocr_or_text_quality", "text_quality_or_ocr_noise_limits_interpretation"
    if any(term in body for term in ["policy", "governance", "planning", "regulation", "management", "decision-making"]):
        return "policy_governance_ambiguity", "policy_terms_present_but_rhetorical_function_uncertain"
    if any(term in body for term in ["simulation", "system dynamics", "model", "modelling", "modeling", "scenario", "forecast", "projection"]):
        if v2 == "historical_framing" or human == "modeling_simulation_reference" or v1 == "modeling_simulation_reference":
            return "historical_vs_modeling", "modeling_language_overlaps_with_historical_or_scenario_framing"
    if any(term in body for term in ["finite planet", "exhaustible resources", "resource", "growth", "collapse", "overshoot", "population"]):
        if v2 == "historical_framing" or human == "foundational_citation" or v1 == "foundational_citation":
            return "historical_vs_foundational", "substantive_resource_claim_overlaps_with_historical_framing"
    if row.get("bibliography_detected", "").lower() == "true" or row.get("citation_section") == "BIBLIO" or "publication" in body:
        return "bibliography_or_publication_history", "publication_history_or_bibliography_boundary"
    if len(body.split()) < 45 or row.get("limited_context") == "True":
        return "short_context", "context_too_short_or_missing_adjacent_sentences"
    if row.get("v2_stance_toward_seed") in {"supportive", "critical", "mixed"} or human in {"supportive", "critical", "mixed"}:
        return "stance_ambiguity", "stance_requires_explicit_evaluative_evidence"
    if row.get("v2_topic_or_discourse_area") == "unclear":
        return "topic_label_weakness", "topic_label_unclear_or_too_broad"
    return "true_interpretive_gray_zone", "coherent_context_requires_interpretive_judgment"


def recommendations(row: Dict[str, str], family: str, accepted: bool) -> Dict[str, str]:
    router = family in {
        "bibliography_or_publication_history",
        "historical_vs_modeling",
        "historical_vs_foundational",
        "generic_title_or_generic_limits",
        "ocr_or_text_quality",
        "short_context",
    }
    extraction = family in {"ocr_or_text_quality", "short_context", "seed_identification_ambiguity"}
    prompt = family in {"evidence_quote_failure", "uncertainty_policy_failure", "stance_ambiguity", "policy_governance_ambiguity"}
    human = (
        not accepted
        or family in {"true_interpretive_gray_zone", "policy_governance_ambiguity", "generic_title_or_generic_limits", "ocr_or_text_quality"}
        or row.get("has_human_label") != "yes"
    )
    benchmark = family in {"true_interpretive_gray_zone", "policy_governance_ambiguity", "evidence_quote_failure", "uncertainty_policy_failure", "stance_ambiguity"}
    if not accepted and family in {"evidence_quote_failure", "uncertainty_policy_failure"}:
        action = "tighten_prompt_validator_or_repair_then_benchmark"
    elif extraction:
        action = "improve_extraction_or_context_window_before_reclassification"
    elif router:
        action = "add_or_tighten_deterministic_router_rule"
    elif human:
        action = "targeted_human_review"
    elif benchmark:
        action = "model_benchmark_on_gray_zone"
    else:
        action = "retain_as_gray_zone_with_spot_check"
    return {
        "recommended_next_action": action,
        "can_router_handle_future_cases": str(router).lower(),
        "needs_extraction_improvement": str(extraction).lower(),
        "needs_prompt_improvement": str(prompt).lower(),
        "needs_human_review": str(human).lower(),
        "candidate_for_model_benchmark": str(benchmark).lower(),
    }


def mode_summary(rows: List[Dict[str, str]], key: str) -> List[Dict[str, Any]]:
    total = len(rows)
    out = []
    for value, group in groupby(rows, key).items():
        accepted = [row for row in group if row["accepted_or_rejected"] == "accepted"]
        human = [row for row in group if row.get("human_agreement_function")]
        out.append({
            key: value,
            "n": len(group),
            "pct": pct(len(group), total),
            "accepted_n": len(accepted),
            "rejected_n": len(group) - len(accepted),
            "accepted_rate": pct(len(accepted), len(group)),
            "human_labeled_n": len(human),
            "human_function_agreement_rate": pct(sum(yes(row["human_agreement_function"]) for row in human), len(human)),
            "router_can_handle_n": sum(yes(row["can_router_handle_future_cases"]) for row in group),
            "needs_extraction_n": sum(yes(row["needs_extraction_improvement"]) for row in group),
            "needs_prompt_n": sum(yes(row["needs_prompt_improvement"]) for row in group),
            "needs_human_review_n": sum(yes(row["needs_human_review"]) for row in group),
            "model_benchmark_n": sum(yes(row["candidate_for_model_benchmark"]) for row in group),
            "validation_errors": " | ".join(f"{k}:{v}" for k, v in Counter(err for row in group for err in row["validation_error_type"].split(" | ") if err).most_common(6)),
        })
    return sorted(out, key=lambda row: (-row["n"], str(row[key])))


def groupby(rows: List[Dict[str, str]], key: str) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get(key, "unknown") or "unknown"].append(row)
    return groups


def review_question(row: Dict[str, str]) -> str:
    family = row["failure_mode_family"]
    if family == "historical_vs_foundational":
        return "Is Meadows used as a substantive premise, or only placed historically?"
    if family == "historical_vs_modeling":
        return "Does the citation event discuss modeling/simulation behavior, or merely historical lineage?"
    if family == "policy_governance_ambiguity":
        return "Does the visible citation event itself perform policy/governance work?"
    if family == "generic_title_or_generic_limits":
        return "Is this a direct Meadows 1972 citation or generic limits-to-growth discourse?"
    if family == "ocr_or_text_quality":
        return "Is the text readable enough to classify, or should it remain unclear?"
    if family == "evidence_quote_failure":
        return "Can an exact evidence quote support the proposed label?"
    if family == "uncertainty_policy_failure":
        return "Which uncertainty flags and human-review status are appropriate?"
    return "What rhetorical job does this citation event visibly perform?"


def main() -> None:
    queue = {row["context_group_id"]: row for row in read_csv(QUEUE)}
    outputs = {row["context_group_id"]: row for row in read_csv(CLASSIFICATIONS)}
    diagnostics = {row["context_group_id"]: row for row in read_csv(DIAGNOSTIC)}
    agreement = {row["context_group_id"]: row for row in read_csv(HUMAN_AGREEMENT)}
    errors: Dict[str, List[str]] = defaultdict(list)
    for row in read_csv(ERRORS):
        errors[row["context_group_id"]].append(row["validation_error"])

    rows: List[Dict[str, str]] = []
    for gid, source in queue.items():
        out = outputs.get(gid, {})
        diag = diagnostics.get(gid, {})
        agree = agreement.get(gid, {})
        errs = list(dict.fromkeys(errors.get(gid, [])))
        accepted = out.get("classification_status") in ACCEPTED
        base = {
            "context_group_id": gid,
            "representative_context_id": source.get("canonical_context_id") or source.get("mention_level_id") or out.get("context_id", ""),
            "title": source.get("title", ""),
            "year": source.get("year", ""),
            "decade": source.get("decade", ""),
            "venue": source.get("venue", ""),
            "field_or_venue": source.get("field_or_venue", ""),
            "stratum": source.get("stratum", ""),
            "sampling_reason": source.get("sampling_reason", ""),
            "router_reason": source.get("routing_reason", ""),
            "rule_hits": source.get("rule_hits", ""),
            "citation_sentence": source.get("citation_sentence", ""),
            "sentence_before": source.get("sentence_before", ""),
            "sentence_after": source.get("sentence_after", ""),
            "context_window": source.get("context_window", ""),
            "legacy_snippet": source.get("snippet_clean", ""),
            "sent_to_llm": source.get("send_to_llm", ""),
            "llm_status": out.get("classification_status", ""),
            "accepted_or_rejected": "accepted" if accepted else "rejected",
            "rejection_reason": out.get("validation_errors", "") if not accepted else "",
            "validation_error_type": " | ".join(errs),
            "v2_citation_function": out.get("citation_function", ""),
            "v2_topic_or_discourse_area": out.get("topic_or_discourse_area", ""),
            "v2_stance_toward_seed": out.get("stance_toward_seed", ""),
            "v2_needs_human_review": out.get("needs_human_review", ""),
            "v2_uncertainty_flags": out.get("uncertainty_flags", ""),
            "v2_confidence_function": out.get("confidence_function", ""),
            "v2_confidence_topic": out.get("confidence_topic", ""),
            "v2_confidence_stance": out.get("confidence_stance", ""),
            "v2_evidence_quote_function": out.get("evidence_quote_function", ""),
            "v2_reasoning_summary": out.get("reasoning_summary", ""),
            "human_primary_role": source.get("human_primary_role", ""),
            "human_discourse_category": source.get("human_discourse_category", ""),
            "human_stance_toward_seed": source.get("human_stance_toward_seed", ""),
            "v1_llm_primary_role": source.get("v1_llm_primary_role", ""),
            "v1_llm_topic": source.get("v1_llm_topic", ""),
            "v1_llm_stance": source.get("v1_llm_stance", ""),
            "fallback_primary_role": source.get("fallback_primary_role", ""),
            "has_human_label": source.get("has_human_label", ""),
            "human_agreement_function": agree.get("human_function_agreement", ""),
            "human_agreement_stance": agree.get("human_stance_agreement", ""),
            "human_agreement_topic": agree.get("human_topic_agreement", ""),
            "initial_total_tokens": diag.get("initial_total_tokens", ""),
            "latency_seconds": diag.get("latency_seconds", ""),
        }
        family, mode = family_and_mode(base, errs)
        base["gray_zone_failure_mode"] = mode
        base["failure_mode_family"] = family
        base.update(recommendations(base, family, accepted))
        rows.append(base)

    write_csv(TABLES / "gray_zone_analysis.csv", rows)
    write_csv(TABLES / "gray_zone_failure_mode_summary.csv", mode_summary(rows, "failure_mode_family"))
    write_csv(TABLES / "gray_zone_by_stratum.csv", mode_summary(rows, "stratum"))
    write_csv(TABLES / "gray_zone_by_decade.csv", mode_summary(rows, "decade"))
    write_csv(TABLES / "gray_zone_by_field_or_venue.csv", mode_summary(rows, "field_or_venue"))

    recs = []
    for action, group in groupby(rows, "recommended_next_action").items():
        recs.append({
            "recommended_next_action": action,
            "n": len(group),
            "pct": pct(len(group), len(rows)),
            "accepted_n": sum(row["accepted_or_rejected"] == "accepted" for row in group),
            "rejected_n": sum(row["accepted_or_rejected"] == "rejected" for row in group),
            "dominant_failure_families": " | ".join(f"{k}:{v}" for k, v in Counter(row["failure_mode_family"] for row in group).most_common(5)),
            "rationale": recommendation_rationale(action),
        })
    write_csv(TABLES / "gray_zone_recommendations.csv", sorted(recs, key=lambda row: -row["n"]))

    def priority(row: Dict[str, str]) -> tuple[int, str]:
        score = 0
        if row["accepted_or_rejected"] == "rejected":
            score -= 100
        if row.get("human_agreement_function") == "false" or row.get("human_agreement_stance") == "false":
            score -= 80
        if yes(row.get("v2_needs_human_review")):
            score -= 30
        if row["failure_mode_family"] in {"policy_governance_ambiguity", "generic_title_or_generic_limits", "ocr_or_text_quality", "historical_vs_foundational", "historical_vs_modeling"}:
            score -= 20
        return (score, row["context_group_id"])

    packet = []
    for row in sorted(rows, key=priority):
        packet.append({
            "context_group_id": row["context_group_id"],
            "priority_reason": row["accepted_or_rejected"] + "; " + row["failure_mode_family"],
            "title": row["title"],
            "year": row["year"],
            "stratum": row["stratum"],
            "citation_sentence": row["citation_sentence"],
            "context_window": row["context_window"],
            "v2_output": row["v2_citation_function"],
            "v2_topic": row["v2_topic_or_discourse_area"],
            "v2_stance": row["v2_stance_toward_seed"],
            "v2_evidence_quote_function": row["v2_evidence_quote_function"],
            "human_label": row["human_primary_role"],
            "v1_label": row["v1_llm_primary_role"],
            "fallback_label": row["fallback_primary_role"],
            "failure_mode_family": row["failure_mode_family"],
            "gray_zone_failure_mode": row["gray_zone_failure_mode"],
            "validation_error_type": row["validation_error_type"],
            "recommended_next_action": row["recommended_next_action"],
            "recommended_human_review_question": review_question(row),
        })
    write_csv(TABLES / "gray_zone_case_review_packet.csv", packet)
    write_csv(TABLES / "contextual_findings_ready_for_meadows_report.csv", meadows_bridge(rows))
    print(f"Analyzed {len(rows)} gray-zone cases.")


def recommendation_rationale(action: str) -> str:
    return {
        "tighten_prompt_validator_or_repair_then_benchmark": "Most rows failed mechanical evidence or uncertainty requirements; solve output contract before scale.",
        "add_or_tighten_deterministic_router_rule": "Visible lexical or structural patterns may be safer as deterministic pre-classification.",
        "improve_extraction_or_context_window_before_reclassification": "The text supplied to the classifier is too short, noisy, or ambiguous.",
        "targeted_human_review": "Interpretive judgment or missing labels are the limiting factor.",
        "model_benchmark_on_gray_zone": "A model comparison may help only after prompt/schema constraints are stable.",
        "retain_as_gray_zone_with_spot_check": "No dominant failure mode; keep as gray-zone with audit sampling.",
    }.get(action, "Review before further classification.")


def meadows_bridge(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    accepted = [row for row in rows if row["accepted_or_rejected"] == "accepted"]
    rejected = [row for row in rows if row["accepted_or_rejected"] == "rejected"]
    return [
        {
            "finding_category": "ready for conservative report",
            "finding_area": "methods validation",
            "finding": "The hybrid workflow can safely separate deterministic-router outputs from LLM gray-zone outputs and reject mechanically invalid LLM labels.",
            "evidence": f"Gray-zone analysis covered {len(rows)} LLM-routed cases: {len(accepted)} accepted and {len(rejected)} rejected.",
            "reporting_status": "ready with scope limits",
            "caution": "This is methods evidence, not a corpus-wide substantive result.",
        },
        {
            "finding_category": "human-reviewed only",
            "finding_area": "human labels",
            "finding": "Manual labels remain the adjudication standard for rhetorical citation function.",
            "evidence": "Accepted gray-zone rows with human labels still included disagreements, especially short-context and OCR/text-quality cases.",
            "reporting_status": "ready as validation caveat",
            "caution": "Do not replace human labels with hybrid labels in the validation subset without adjudication.",
        },
        {
            "finding_category": "hybrid-pilot supported but not corpus-wide",
            "finding_area": "modeling/simulation references",
            "finding": "Explicit modeling and simulation language is a promising deterministic-router target.",
            "evidence": "The 100-context pilot routed many explicit modeling cases deterministically; gray-zone modeling/historical overlap still needs review.",
            "reporting_status": "safe as pipeline finding",
            "caution": "Do not estimate prevalence from the stratified pilot.",
        },
        {
            "finding_category": "hybrid-pilot supported but not corpus-wide",
            "finding_area": "bibliography-only citations",
            "finding": "Clearly bibliographic contexts are safe to classify structurally as bibliography-only.",
            "evidence": "Bibliography-like cases were handled by deterministic routing in the pilot.",
            "reporting_status": "safe as structural classification rule",
            "caution": "Body-text publication history is not bibliography-only and still needs separate handling.",
        },
        {
            "finding_category": "exploratory hypotheses",
            "finding_area": "historical framing prevalence",
            "finding": "Historical framing is common among accepted pilot and gray-zone classifications.",
            "evidence": f"{sum(row['v2_citation_function'] == 'historical_framing' for row in accepted)}/{len(accepted)} accepted gray-zone cases were labeled historical framing.",
            "reporting_status": "exploratory",
            "caution": "The sample is stratified and boundary-heavy; do not infer corpus prevalence.",
        },
        {
            "finding_category": "exploratory hypotheses",
            "finding_area": "foundational-to-historical transition",
            "finding": "The foundational-to-historical-framing transition remains a plausible hypothesis.",
            "evidence": "Gray-zone analysis clarifies historical/foundational boundary failures but does not supply decade-balanced validated prevalence.",
            "reporting_status": "plausible hypothesis",
            "caution": "Needs decade-stratified human validation or a validated deterministic/hybrid classifier before formal testing.",
        },
        {
            "finding_category": "not ready",
            "finding_area": "topic/discourse labels",
            "finding": "Topic/discourse labels are not reliable enough for strong Meadows impact claims.",
            "evidence": "Topic weakness appeared in prior pilot audit and gray-zone rows often used broad or unclear topic labels.",
            "reporting_status": "not ready",
            "caution": "Treat topic labels as exploratory until separately validated.",
        },
        {
            "finding_category": "not ready",
            "finding_area": "stance labels",
            "finding": "Stance labels are conservative but still require human checking for evaluative cases.",
            "evidence": "Most gray-zone accepted cases were neutral or unclear; stance errors cluster around explicit evidence requirements.",
            "reporting_status": "not ready for corpus-wide claims",
            "caution": "Do not make corpus-wide supportive/critical claims from current hybrid labels.",
        },
        {
            "finding_category": "not ready",
            "finding_area": "scaling",
            "finding": "A full 500-context hybrid run remains premature.",
            "evidence": f"{len(rejected)}/{len(rows)} gray-zone LLM outputs were rejected; dominant rejected families were evidence-quote and uncertainty-policy failures.",
            "reporting_status": "not ready",
            "caution": "Prioritize prompt/validator repair, extraction improvement, targeted human review, and small model benchmarks first.",
        },
    ]


if __name__ == "__main__":
    main()
