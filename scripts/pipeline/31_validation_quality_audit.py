#!/usr/bin/env python3
"""Build validation, extraction-recovery, and readiness audit tables.

This script does not run classification or create substantive findings. It
summarizes current evidence quality so the next human-coding and extraction
work can be prioritized transparently.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
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


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def present(value: Any) -> bool:
    return bool(str(value or "").strip())


def pct(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def text_for(row: Dict[str, str]) -> str:
    return " ".join(
        row.get(field, "")
        for field in (
            "citation_sentence",
            "sentence_before",
            "sentence_after",
            "context_window",
            "legacy_snippet",
            "snippet_clean",
            "evidence_text",
        )
    ).strip()


def context_len(row: Dict[str, str]) -> int:
    return len(text_for(row))


def has_generic_ltg(text: str) -> bool:
    lower = text.lower()
    return "limits to growth" in lower and not any(
        token in lower
        for token in ("meadows", "club of rome", "world3", "world 3", "1972")
    )


def has_generic_title_mention(text: str) -> bool:
    lower = text.lower()
    return bool(re.search(r"\b(the )?limits to growth\b", lower)) and context_len({"legacy_snippet": text}) < 220


def has_ocr_indicator(row: Dict[str, str]) -> bool:
    text = text_for(row).lower()
    flags = " ".join(row.get(field, "") for field in ("v2_uncertainty_flags", "ocr_or_bibliography_flags", "extraction_issue_flags")).lower()
    broken_tokens = len(re.findall(r"\b[a-zA-Z]{1,2}\b", text))
    return (
        "ocr" in flags
        or row.get("failure_mode_family") == "ocr_or_text_quality"
        or "r r" in text
        or "ev " in text
        or broken_tokens > 20
    )


def group_counts(rows: Iterable[Dict[str, str]], field: str) -> Counter:
    return Counter((row.get(field) or "unknown") for row in rows)


def router_safe_validation_plan() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates = read_csv(VALIDATION / "router_safe_scale_candidate_set.csv")
    spotcheck = read_csv(VALIDATION / "router_safe_spotcheck_sample.csv")
    definitions = {
        row["router_safe_category"]: row for row in read_csv(TABLES / "router_safe_category_definition.csv")
    }
    category_map = {
        "true_bibliography_only": "bibliography_only",
        "explicit_modeling_simulation_language": "modeling_simulation_reference",
        "explicit_foundational_resource_constraint_claim": "foundational_resource_constraint_claim",
        "clear_historical_publication_lineage": "historical_publication_lineage",
        "severe_ocr_incoherent_unclear_human_review": "severe_ocr_unclear",
    }
    importance = {
        "bibliography_only": ("medium", "medium", "medium", "high"),
        "modeling_simulation_reference": ("high", "high", "high", "high"),
        "foundational_resource_constraint_claim": ("high", "high", "very_high", "very_high"),
        "historical_publication_lineage": ("high", "high", "very_high", "very_high"),
        "severe_ocr_unclear": ("medium", "medium", "high", "medium"),
    }
    candidate_counts = group_counts(candidates, "stratum_category")
    spot_counts = group_counts(spotcheck, "stratum_category")
    rows: List[Dict[str, Any]] = []
    priorities: List[Dict[str, Any]] = []
    for raw_category, public_category in category_map.items():
        candidate_n = candidate_counts[raw_category]
        spot_n = spot_counts[raw_category]
        definition = definitions.get(raw_category, {})
        risk = risk_for(public_category, definition.get("risk_level", "unknown"))
        expected_precision = expected_precision_for(public_category)
        false_pos, false_neg = risk_notes(public_category)
        strategy = review_strategy(public_category, candidate_n, spot_n)
        rows.append({
            "category": public_category,
            "router_safe_category": raw_category,
            "candidate_count": candidate_n,
            "spot_check_count": spot_n,
            "validation_coverage": pct(spot_n, candidate_n),
            "estimated_risk_level": risk,
            "expected_precision": expected_precision,
            "expected_false_positive_risks": false_pos,
            "expected_false_negative_risks": false_neg,
            "recommended_human_review_strategy": strategy,
            "maturity_for_eventual_scaling": maturity_for(public_category),
        })
        method_importance, meadows_importance, urgency, payoff = importance[public_category]
        priorities.append({
            "category": public_category,
            "candidate_count": candidate_n,
            "spot_check_count": spot_n,
            "methodological_importance": method_importance,
            "meadows_study_importance": meadows_importance,
            "validation_urgency": urgency,
            "expected_payoff": payoff,
            "priority_rank": priority_score(method_importance, meadows_importance, urgency, payoff, candidate_n),
            "recommended_next_action": strategy,
        })
    priorities.sort(key=lambda row: int(row["priority_rank"]), reverse=True)
    for idx, row in enumerate(priorities, 1):
        row["priority_order"] = idx
    return rows, priorities


def risk_for(category: str, definition_risk: str) -> str:
    return {
        "bibliography_only": "low for function; high for topic/stance if misused",
        "modeling_simulation_reference": "medium",
        "foundational_resource_constraint_claim": "medium-high",
        "historical_publication_lineage": "medium",
        "severe_ocr_unclear": "high for interpretation; low for abstention",
    }.get(category, definition_risk)


def expected_precision_for(category: str) -> str:
    return {
        "bibliography_only": "high if bibliography flags are correct",
        "modeling_simulation_reference": "medium-high when modeling terms appear in the citation event",
        "foundational_resource_constraint_claim": "medium pending boundary validation",
        "historical_publication_lineage": "medium pending historical/foundational review",
        "severe_ocr_unclear": "high for abstention, not for substantive labeling",
    }[category]


def risk_notes(category: str) -> tuple[str, str]:
    notes = {
        "bibliography_only": (
            "Body-text publication-history snippets may be mistaken for references.",
            "Reference-list entries split across OCR lines may be missed.",
        ),
        "modeling_simulation_reference": (
            "Modeling terms elsewhere in the paragraph may override a historical citation event.",
            "Short model-comparison snippets without standard terms may be routed gray-zone.",
        ),
        "foundational_resource_constraint_claim": (
            "Chronology words may hide whether the Meadows claim is actually used as a premise.",
            "Substantive resource-limit premises may be missed when context is short.",
        ),
        "historical_publication_lineage": (
            "Historical words may absorb modeling or foundational uses.",
            "Publication-lineage language without obvious chronology terms may be missed.",
        ),
        "severe_ocr_unclear": (
            "Coherent short snippets could be over-abstained.",
            "Damaged OCR with chronology terms may still be overinterpreted.",
        ),
    }
    return notes[category]


def review_strategy(category: str, candidate_n: int, spot_n: int) -> str:
    if category == "bibliography_only":
        return "Code the 61-row spot check first; verify true reference-list status and do not evaluate topic/stance."
    if category == "modeling_simulation_reference":
        return "Human-code all 11 spot-check rows, prioritizing whether modeling language belongs to the citation event."
    if category == "foundational_resource_constraint_claim":
        return "Human-code all 10 spot-check rows and compare against historical-lineage boundary rules."
    if category == "historical_publication_lineage":
        return "Human-code all 12 spot-check rows and the six historical/foundational casebook rows before scaling."
    return "Review the single severe-OCR abstention and add more OCR cases before estimating precision."


def maturity_for(category: str) -> str:
    return {
        "bibliography_only": "promising pending spot check",
        "modeling_simulation_reference": "promising but requires boundary spot check",
        "foundational_resource_constraint_claim": "not mature until historical/foundational cases are reviewed",
        "historical_publication_lineage": "not mature until historical/foundational cases are reviewed",
        "severe_ocr_unclear": "abstention rule only; needs more examples",
    }[category]


def priority_score(*values: Any) -> int:
    weights = {"very_high": 5, "high": 4, "medium": 3, "low": 2, "unknown": 1}
    score = sum(weights.get(str(value), 1) for value in values[:4])
    try:
        n = int(values[4])
    except (TypeError, ValueError):
        n = 0
    return score + min(n // 100, 3)


def extraction_recovery_tables() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    gray = read_csv(TABLES / "gray_zone_analysis.csv")
    prior_candidates = {row["context_group_id"]: row for row in read_csv(TABLES / "extraction_improvement_candidate_set.csv")}
    rows_by_id: Dict[str, Dict[str, str]] = {}
    for row in gray:
        text = text_for(row)
        low_conf = safe_float(row.get("extraction_confidence"), 1.0) < 0.55 if row.get("extraction_confidence") else False
        include = (
            row.get("failure_mode_family") in {"short_context", "ocr_or_text_quality"}
            or row.get("context_group_id") in prior_candidates
            or not present(row.get("sentence_before"))
            or not present(row.get("sentence_after"))
            or low_conf
            or has_generic_title_mention(text)
            or has_generic_ltg(text)
        )
        if include:
            rows_by_id[row["context_group_id"]] = row
    for group_id, row in prior_candidates.items():
        if group_id not in rows_by_id:
            rows_by_id[group_id] = row

    out: List[Dict[str, Any]] = []
    for group_id, row in sorted(rows_by_id.items()):
        text = text_for(row)
        failure_mode = row.get("failure_mode_family") or row.get("failure_mode") or "extraction_candidate"
        citation_present = present(row.get("citation_sentence"))
        before_present = present(row.get("sentence_before"))
        after_present = present(row.get("sentence_after"))
        ocr = has_ocr_indicator(row)
        biblio = "biblio" in " ".join([row.get("citation_section", ""), row.get("rule_hits", ""), text]).lower()
        generic_title = has_generic_title_mention(text)
        generic_ltg = has_generic_ltg(text)
        recoverability = recoverability_for(row, citation_present, before_present, after_present, ocr, generic_title, generic_ltg)
        out.append({
            "context_group_id": group_id,
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "stratum": row.get("stratum", ""),
            "failure_mode": failure_mode,
            "extraction_confidence": row.get("extraction_confidence", ""),
            "context_length": len(text),
            "citation_sentence_present": str(citation_present).lower(),
            "sentence_before_present": str(before_present).lower(),
            "sentence_after_present": str(after_present).lower(),
            "ocr_indicators": str(ocr).lower(),
            "bibliography_indicators": str(biblio).lower(),
            "generic_title_mention": str(generic_title).lower(),
            "generic_limits_to_growth_mention": str(generic_ltg).lower(),
            "recoverability_estimate": recoverability,
            "recommended_extraction_intervention": extraction_intervention(citation_present, before_present, after_present, ocr, generic_title, generic_ltg),
            "expected_evidence_gain": evidence_gain(recoverability),
            "expected_reduction_in_uncertainty": uncertainty_gain(recoverability),
            "context_text": text,
        })
    summary = extraction_summary(out, gray)
    return out, summary


def recoverability_for(row: Dict[str, str], citation: bool, before: bool, after: bool, ocr: bool, generic_title: bool, generic_ltg: bool) -> str:
    if ocr and len(text_for(row)) < 120:
        return "low-medium"
    if not citation or not before or not after:
        return "high"
    if generic_title or generic_ltg:
        return "medium"
    if ocr:
        return "medium"
    return "medium-high"


def extraction_intervention(citation: bool, before: bool, after: bool, ocr: bool, generic_title: bool, generic_ltg: bool) -> str:
    interventions = []
    if not citation:
        interventions.append("reconstruct citation sentence")
    if not before or not after:
        interventions.append("recover adjacent sentences")
    if ocr:
        interventions.append("OCR cleanup or abstention flag")
    if generic_title or generic_ltg:
        interventions.append("seed-identification verification")
    return "; ".join(interventions) or "human review of evidence window"


def evidence_gain(recoverability: str) -> str:
    return {"high": "high", "medium-high": "medium-high", "medium": "medium", "low-medium": "low-medium"}.get(recoverability, "unknown")


def uncertainty_gain(recoverability: str) -> str:
    return {"high": "high", "medium-high": "medium", "medium": "medium", "low-medium": "low"}.get(recoverability, "unknown")


def extraction_summary(rows: List[Dict[str, Any]], gray: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    by_mode = Counter(row["failure_mode"] for row in rows)
    by_recoverability = Counter(row["recoverability_estimate"] for row in rows)
    summary: List[Dict[str, Any]] = []
    for mode, count in by_mode.most_common():
        mode_rows = [row for row in rows if row["failure_mode"] == mode]
        summary.append({
            "summary_type": "failure_mode_count",
            "category": mode,
            "count": count,
            "projected_recoverability": modal(row["recoverability_estimate"] for row in mode_rows),
            "likely_effect_on_gray_zone_rejection_rates": rejection_effect(mode),
            "likely_effect_on_human_review_rates": review_effect(mode),
        })
    for level, count in by_recoverability.most_common():
        summary.append({
            "summary_type": "recoverability_count",
            "category": level,
            "count": count,
            "projected_recoverability": level,
            "likely_effect_on_gray_zone_rejection_rates": "indirect; depends on reclassification after extraction repair",
            "likely_effect_on_human_review_rates": "likely lower only after human spot checks confirm evidence adequacy",
        })
    summary.append({
        "summary_type": "overall",
        "category": "all_extraction_recovery_candidates",
        "count": len(rows),
        "projected_recoverability": f"{sum(1 for row in rows if row['recoverability_estimate'] in {'high', 'medium-high'})}/{len(rows)} high_or_medium_high",
        "likely_effect_on_gray_zone_rejection_rates": "Could reduce avoidable rejection for evidence-quality failures; no classification rerun performed.",
        "likely_effect_on_human_review_rates": "Could reduce uncertainty for recoverable short/missing-window rows, but OCR and generic mentions remain review-heavy.",
    })
    summary.append({
        "summary_type": "context",
        "category": "gray_zone_base",
        "count": len(gray),
        "projected_recoverability": "not estimated as corpus count",
        "likely_effect_on_gray_zone_rejection_rates": "Do not estimate final corpus counts from this audit.",
        "likely_effect_on_human_review_rates": "Use as prioritization only.",
    })
    return summary


def modal(values: Iterable[str]) -> str:
    counts = Counter(values)
    return counts.most_common(1)[0][0] if counts else "unknown"


def rejection_effect(mode: str) -> str:
    if mode in {"evidence_quote_failure", "uncertainty_policy_failure"}:
        return "low until prompt/validator changes; extraction alone may not solve it"
    if mode in {"short_context", "ocr_or_text_quality"}:
        return "potentially meaningful if repaired windows contain exact evidence"
    return "uncertain"


def review_effect(mode: str) -> str:
    if mode in {"short_context", "ocr_or_text_quality"}:
        return "may lower review need after repair, but sample validation required"
    return "likely still requires targeted review"


def historical_foundational_tables() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    review = read_csv(TABLES / "historical_foundational_router_review.csv")
    casebook: List[Dict[str, Any]] = []
    for row in review:
        text = row.get("evidence_text", "")
        lower = text.lower()
        resource = any(term in lower for term in ("resource", "finite", "growth", "collapse", "overshoot", "population", "pollution", "scarcity"))
        lineage = any(term in lower for term in ("published", "publication", "report", "book", "landmark", "seminal", "founding", "history", "intellectual", "roots", "came", "age"))
        chronology = bool(re.search(r"\b(19|20)\d{2}\b|since|after|before|earlier|followed|history|historical", lower))
        premise = resource and any(term in lower for term in ("argue", "claim", "constraint", "limit", "limits", "growth", "sustainable", "development"))
        deterministic = row.get("could_deterministic_rule_safely_resolve") == "true" and row.get("recommend_new_router_rule") != "yes"
        casebook.append({
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "context_text": text,
            "human_recommendation": row.get("human_primary_role", ""),
            "router_recommendation": row.get("v2_citation_function", ""),
            "rationale": hf_rationale(resource, lineage, chronology, premise),
            "resource_constraint_language_present": str(resource).lower(),
            "publication_lineage_language_present": str(lineage).lower(),
            "chronology_language_present": str(chronology).lower(),
            "substantive_premise_present": str(premise).lower(),
            "could_a_deterministic_rule_solve_this": str(deterministic).lower(),
            "risk_of_overfitting": row.get("risk_of_overfitting_if_added", "medium"),
        })
    safe_count = sum(1 for row in casebook if row["could_a_deterministic_rule_solve_this"] == "true")
    assessment = [
        {
            "question": "Is a new router rule justified?",
            "answer": "not yet",
            "basis": "All six cases are marked review_first; the observed patterns are useful but too few for automatic rule expansion.",
            "affected_cases": len(casebook),
        },
        {
            "question": "Would the rule generalize?",
            "answer": "uncertain",
            "basis": "Resource, chronology, and lineage language overlap; a broad rule could collapse foundational premises into historical framing or the reverse.",
            "affected_cases": safe_count,
        },
        {
            "question": "What error risk would it introduce?",
            "answer": "medium",
            "basis": "Overfitting to a six-case boundary set and misrouting short contexts where resource terms appear in historical prose.",
            "affected_cases": len(casebook),
        },
        {
            "question": "Estimated benefit",
            "answer": "modest until more human labels exist",
            "basis": "A future narrow rule may reduce LLM gray-zone volume, but human spot checks should come first.",
            "affected_cases": safe_count,
        },
    ]
    return casebook, assessment


def hf_rationale(resource: bool, lineage: bool, chronology: bool, premise: bool) -> str:
    if premise and not lineage:
        return "Visible resource/growth-limit language appears to function as a substantive premise."
    if lineage and chronology and not premise:
        return "Chronology or publication-lineage language appears dominant."
    if premise and lineage:
        return "Both premise and lineage cues are present; keep as boundary review rather than deterministic rule."
    return "Insufficient lexical separation for a safe deterministic rule."


def validation_coverage_tables() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    validation = read_csv(VALIDATION / "citation_context_validation_sample.csv")
    spot = read_csv(VALIDATION / "router_safe_spotcheck_sample.csv")
    gray = read_csv(TABLES / "gray_zone_analysis.csv")
    boundary = read_csv(TABLES / "historical_foundational_router_review.csv")
    router_candidates = read_csv(VALIDATION / "router_safe_scale_candidate_set.csv")
    rows: List[Dict[str, Any]] = []

    def add(stratum: str, total: int, coded: int, note: str, priority: str) -> None:
        unresolved = max(total - coded, 0)
        rows.append({
            "stratum": stratum,
            "total_rows": total,
            "human_coded_rows": coded,
            "unresolved_rows": unresolved,
            "human_coded_coverage": pct(coded, total),
            "validation_status": status_for(coded, total),
            "representation_assessment": representation_for(stratum, total, coded),
            "recommended_next_human_coding_priority": priority,
            "notes": note,
        })

    human_coded = sum(1 for row in validation if present(row.get("human_primary_role")))
    add("total_validation_sample", len(validation), human_coded, "Main validation sample.", "Continue coding unresolved high-priority rows.")
    add("router_safe_spotcheck", len(spot), sum(1 for row in spot if present(row.get("human_primary_role"))), "Router-safe spot check has blank human fields pending review.", "Highest immediate priority.")
    add("gray_zone", len(gray), sum(1 for row in gray if row.get("has_human_label") == "yes"), "Rows sent to LLM in hybrid pilot.", "Review rejected and short-context rows after extraction audit.")
    add("historical_foundational_boundary", len(boundary), sum(1 for row in boundary if present(row.get("human_primary_role"))), "Six boundary cases need casebook review before rule expansion.", "High priority.")
    add("ocr_rows", count_ocr(validation, gray, spot), 0, "OCR-oriented validation is not systematically labeled as a separate stratum.", "Add targeted OCR sample.")
    add("bibliography_rows", count_role_like(validation, spot, router_candidates, "bibliographic"), count_human_role(validation, "bibliographic_only"), "Bibliography dominates router-safe candidates.", "Code router-safe bibliography spot check.")
    add("modeling_rows", count_role_like(validation, spot, router_candidates, "modeling"), count_human_role(validation, "modeling_simulation_reference"), "Modeling category is important and moderately represented.", "Code all modeling spot-check rows.")
    add("foundational_rows", count_role_like(validation, spot, router_candidates, "foundational"), count_human_role(validation, "foundational_citation"), "Foundational boundary is under-validated relative to importance.", "Code foundational and historical/foundational rows.")
    add("historical_rows", count_role_like(validation, spot, router_candidates, "historical"), count_human_role(validation, "historical_framing"), "Historical category is central to diffusion interpretation.", "Code historical-lineage spot check and decade-balanced rows.")

    plan = [
        sampling_plan("router_safe_spotcheck", 95, "Human-code all current router-safe spot-check rows before deterministic scaling."),
        sampling_plan("historical_foundational_boundary", 6, "Review all casebook rows; do not implement new rules until complete."),
        sampling_plan("extraction_recovery", 29, "Review repaired windows after extraction work, especially short/OCR rows."),
        sampling_plan("gray_zone_rejected", 25, "Human-code rejected gray-zone rows to distinguish model-contract failures from evidence insufficiency."),
        sampling_plan("ocr_targeted", 20, "Add a targeted OCR sample because current OCR coverage is thin and methodologically important."),
        sampling_plan("decade_balanced_contextual", 10, "After above, sample by decade before testing temporal contextual claims."),
    ]
    return rows, plan


def status_for(coded: int, total: int) -> str:
    coverage = pct(coded, total)
    if coverage >= 0.8:
        return "well_covered_for_internal_audit"
    if coverage >= 0.4:
        return "partially_covered"
    if coded == 0:
        return "not_yet_human_coded"
    return "under_validated"


def representation_for(stratum: str, total: int, coded: int) -> str:
    if stratum == "router_safe_spotcheck":
        return "under-validated because human coding has not started"
    if stratum in {"historical_foundational_boundary", "foundational_rows", "ocr_rows"}:
        return "under-validated relative to methodological importance"
    if stratum == "bibliography_rows":
        return "over-represented in router-safe candidates but still needs structural spot check"
    return "adequate for prioritization, not final inference"


def count_ocr(*tables: List[Dict[str, str]]) -> int:
    seen = set()
    for rows in tables:
        for row in rows:
            key = row.get("context_group_id") or row.get("context_id") or str(id(row))
            if has_ocr_indicator(row):
                seen.add(key)
    return len(seen)


def count_role_like(validation: List[Dict[str, str]], spot: List[Dict[str, str]], router: List[Dict[str, str]], token: str) -> int:
    seen = set()
    for rows in (validation, spot, router):
        for row in rows:
            fields = " ".join(str(row.get(field, "")) for field in (
                "human_primary_role",
                "llm_primary_role",
                "router_citation_function",
                "rule_hits",
                "stratum_category",
                "validation_stratum",
            )).lower()
            if token in fields:
                seen.add(row.get("context_group_id") or row.get("context_id") or row.get("source_context_id") or str(id(row)))
    return len(seen)


def count_human_role(rows: List[Dict[str, str]], role: str) -> int:
    return sum(1 for row in rows if row.get("human_primary_role") == role)


def sampling_plan(stratum: str, target_n: int, rationale: str) -> Dict[str, Any]:
    return {
        "sampling_stratum": stratum,
        "target_rows_to_code": target_n,
        "selection_logic": "Use existing candidate tables; prioritize human-coded comparability, decade balance, OCR/context quality variation, and boundary cases.",
        "rationale": rationale,
        "expected_output": "Human-coded rows suitable for validation/audit, not final corpus estimates.",
    }


def evidence_level_framework() -> List[Dict[str, Any]]:
    levels = {
        "Level 1": ("Traditional bibliometric evidence", "high for descriptive bibliometrics; coverage caveats apply"),
        "Level 2": ("Human-reviewed contextual evidence", "high within reviewed sample only"),
        "Level 3": ("Validated deterministic-router evidence", "pending spot-check validation"),
        "Level 4": ("Hybrid accepted but not human-reviewed", "exploratory only"),
        "Level 5": ("Gray-zone unresolved", "not usable as finding"),
    }
    findings = [
        ("Corpus construction and metadata diffusion", "Level 1", "yes", "Database coverage, DOI gaps, and external-enrichment limits remain."),
        ("Venue, field, and yearly diffusion tables", "Level 1", "yes", "Use source/enrichment caveats."),
        ("Reference network structure", "Level 1", "with caveat", "OpenAlex reference coverage and combinatorial expansion must be disclosed."),
        ("Contextual examples from human-coded rows", "Level 2", "yes, scoped", "Do not generalize prevalence."),
        ("Citation-function coding distinction", "Level 2", "yes, methods-only", "Use as validation framework, not Meadows impact finding."),
        ("Bibliography-only structural classification", "Level 3", "not yet", "Requires router-safe spot check."),
        ("Explicit modeling/foundational/historical router categories", "Level 3", "not yet", "Requires spot check and boundary review."),
        ("Hybrid contextual labels not human-reviewed", "Level 4", "no", "Use only to plan validation."),
        ("Stance, topic, policy/governance prevalence", "Level 5", "no", "Insufficient validation and gray-zone resolution."),
    ]
    rows = []
    for finding, level, usable, caveat in findings:
        label, confidence = levels[level]
        rows.append({
            "major_meadows_finding_or_component": finding,
            "evidence_level": level,
            "evidence_level_definition": label,
            "confidence": confidence,
            "usable_now": usable,
            "caveats": caveat,
        })
    return rows


def readiness_audit() -> List[Dict[str, Any]]:
    return [
        readiness("canonical corpus", "high", "structural checks exist", "duplicate/ambiguous cases still need review", "good with caveats"),
        readiness("metadata enrichment", "medium-high", "500-record enrichment tested; cache exists", "coverage and external-source bias", "promising but subset-dependent"),
        readiness("diffusion analyses", "medium-high", "tables generated", "field labels preliminary/OpenAlex-derived", "usable with methods caveats"),
        readiness("network analyses", "medium", "reference/cocitation/coupling outputs exist", "OpenAlex coverage and edge inflation", "exploratory to cautious"),
        readiness("contextual analyses", "low-medium", "human and hybrid scaffolds exist", "validation coverage and gray-zone failures", "not publication-ready for prevalence claims"),
        readiness("validation framework", "medium", "codebook, samples, comparison scripts exist", "router-safe spot check uncoded", "strong scaffold; needs human coding"),
        readiness("extraction workflow", "medium", "structured windows implemented", "short/OCR/generic mentions remain bottlenecks", "needs recovery work before scaling"),
        readiness("router workflow", "medium-high", "deterministic router works on reviewed/pilot sets", "needs spot-check validation before corpus counts", "promising, not final"),
        readiness("gray-zone workflow", "medium", "failure families and remediation plans exist", "LLM gray-zone rejection high; evidence quality unresolved", "audit-ready, not scale-ready"),
    ]


def readiness(component: str, completeness: str, validation_status: str, risks: str, publication: str) -> Dict[str, str]:
    return {
        "component": component,
        "completeness": completeness,
        "validation_status": validation_status,
        "remaining_risks": risks,
        "readiness_for_eventual_publication": publication,
    }


def main() -> None:
    validation_plan, priorities = router_safe_validation_plan()
    write_csv(TABLES / "router_safe_validation_plan.csv", validation_plan)
    write_csv(TABLES / "router_safe_validation_priorities.csv", priorities)

    recovery, recovery_summary = extraction_recovery_tables()
    write_csv(PROCESSED / "extraction_recovery_dataset.csv", recovery)
    write_csv(TABLES / "extraction_recovery_summary.csv", recovery_summary)

    casebook, rule_assessment = historical_foundational_tables()
    write_csv(TABLES / "historical_foundational_casebook.csv", casebook)
    write_csv(TABLES / "historical_foundational_rule_assessment.csv", rule_assessment)

    coverage, sampling = validation_coverage_tables()
    write_csv(TABLES / "validation_coverage_audit.csv", coverage)
    write_csv(TABLES / "validation_sampling_plan_v2.csv", sampling)

    write_csv(TABLES / "evidence_level_framework.csv", evidence_level_framework())
    write_csv(TABLES / "meadows_data_readiness_audit.csv", readiness_audit())

    print(f"Router-safe validation categories: {len(validation_plan)}")
    print(f"Extraction recovery rows: {len(recovery)}")
    print(f"Historical/foundational casebook rows: {len(casebook)}")
    print(f"Validation coverage strata: {len(coverage)}")


if __name__ == "__main__":
    main()
