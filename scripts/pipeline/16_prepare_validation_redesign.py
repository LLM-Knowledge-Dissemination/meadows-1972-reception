#!/usr/bin/env python3
"""Add context grouping and prepare the next validation review batch."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "analysis/validation/citation_context_validation_sample.csv"
TABLES = ROOT / "analysis/tables"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_flags(value):
    return [part.strip() for part in (value or "").split("|") if part.strip() and part.strip() != "none"]


def fallback_role(row):
    return {
        "sustainability_limits_to_growth_discourse": "sustainability_discourse",
        "methodological_comparison": "methods_comparison",
        "background_or_ambiguous": "unclear",
    }.get(row.get("rule_citation_function", ""), row.get("rule_citation_function", ""))


def group_key(row):
    return f"{row.get('source_document_id', '')}|{row.get('page', '')}"


def group_id(key):
    return "cg_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def priority_score(row):
    flags = set(split_flags(row.get("review_reason", "")))
    score = 0
    reasons = []

    def add(points, reason):
        nonlocal score
        score += points
        reasons.append(reason)

    if row.get("llm_primary_role") == "critique":
        add(120, "critique label requires explicit negative assessment")
    if row.get("llm_stance_toward_meadows") == "supportive":
        add(115, "supportive stance requires explicit positive endorsement")
    if "bibliography_only" in flags or row.get("llm_primary_role") == "bibliographic_only":
        add(95, "bibliography-only status may invalidate interpretive coding")
    if "historical_foundational_ambiguity" in flags:
        add(90, "historical framing versus foundational citation ambiguity")
    if "historical_modeling_ambiguity" in flags:
        add(90, "historical framing versus modeling reference ambiguity")
    if "fallback_llm_primary_role_disagreement" in flags and float(row.get("llm_confidence") or 0) >= 0.8:
        add(85, "high-confidence LLM/fallback disagreement")
    elif "fallback_llm_primary_role_disagreement" in flags:
        add(60, "LLM/fallback disagreement")
    if "snippet_too_short" in flags or "missing_surrounding_context" in flags:
        add(80, "short or incomplete context")
    if "substantive_role_with_bibliography_only_uncertainty" in flags:
        add(75, "substantive role conflicts with bibliography-only uncertainty")
    if "generic_limits_false_positive_risk" in flags:
        add(75, "generic limits-to-growth false-positive risk")
    if "low_extraction_confidence" in flags:
        add(50, "low extraction confidence")
    if "ocr_noise" in flags:
        add(40, "OCR noise")
    if "repeated_context_different_mentions" in flags:
        add(35, "same context extracted through multiple mention strings")
    if row.get("llm_primary_role") == "modeling_simulation_reference":
        add(65, "modeling-reference boundary case for historical-versus-modeling review")
    if row.get("llm_primary_role") in {"historical_framing", "foundational_citation", "modeling_simulation_reference"}:
        add(10, "boundary category central to redesign")
    return score, list(dict.fromkeys(reasons))


def coding_questions(row):
    flags = set(split_flags(row.get("review_reason", "")))
    questions = [
        "What rhetorical job does the citation perform, independent of the surrounding topic?",
        "Is the stance explicitly evaluative, or merely neutral/descriptive?",
    ]
    if row.get("llm_primary_role") == "critique":
        questions.append("Does the context explicitly reject, dispute, correct, or negatively evaluate Meadows?")
    if row.get("llm_stance_toward_meadows") == "supportive":
        questions.append("What exact words explicitly endorse or positively evaluate Meadows' claim/model?")
    if "bibliography_only" in flags or row.get("llm_primary_role") == "bibliographic_only":
        questions.append("Is this reference-list material rather than body-text interpretation?")
    if "historical_foundational_ambiguity" in flags or row.get("llm_primary_role") in {"historical_framing", "foundational_citation"}:
        questions.append("Is Meadows used only to mark history/influence, or is a substantive claim used as an anchor?")
    if "historical_modeling_ambiguity" in flags or row.get("llm_primary_role") == "modeling_simulation_reference":
        questions.append("Does the context discuss a model, simulation, scenario, projection, or assumption, rather than only historical lineage?")
    if "snippet_too_short" in flags or "missing_surrounding_context" in flags:
        questions.append("Is the visible context sufficient, or should citation function be coded unclear pending a wider window?")
    if "repeated_context_different_mentions" in flags:
        questions.append("Does this mention variant represent the same rhetorical citation event as its context-group peers?")
    return " | ".join(dict.fromkeys(questions))


def redesign_rows():
    dimensions = {
        "citation_function": [
            ("historical_framing", "Locates a debate, event, adoption, influence, or lineage historically."),
            ("modeling_simulation_reference", "Discusses World3, system dynamics, simulations, scenarios, projections, or model assumptions."),
            ("foundational_citation", "Uses a substantive Meadows claim as an anchoring source; importance alone is insufficient."),
            ("critique", "Explicitly rejects, disputes, corrects, or negatively evaluates the seed."),
            ("policy_governance_framing", "Directly connects the seed to policy, governance, planning, regulation, or institutional strategy."),
            ("bibliographic_only", "Reference-list material without body-text interpretation."),
            ("unclear", "Insufficient context to determine function."),
        ],
        "topic_or_discourse_area": [
            ("limits_to_growth", "General limits-to-growth debate or concept."),
            ("sustainability", "Sustainability, ecological limits, overshoot, or planetary boundaries."),
            ("system_dynamics_modeling", "System dynamics, World3, modeling, simulations, or scenarios."),
            ("environmental_policy", "Environmental policy, planning, governance, or regulation."),
            ("economics_growth", "Economic growth, development, degrowth, or postgrowth."),
            ("population_resources", "Population, demographic change, resources, scarcity, or carrying capacity."),
            ("climate_energy", "Climate change, emissions, energy systems, or transition."),
            ("historical_or_cultural_memory", "Historical influence, public awareness, cultural memory, or intellectual lineage."),
            ("unclear", "Topic cannot be determined."),
        ],
        "stance_toward_seed": [
            ("supportive", "Explicit endorsement, adoption, positive evaluation, confirmation, or claimed success."),
            ("neutral_descriptive", "Description, attribution, comparison, or historical placement without evaluation."),
            ("critical", "Explicit negative assessment, rejection, correction, failed-prediction framing, or methodological objection."),
            ("mixed", "Both explicit positive and explicit negative assessment."),
            ("unclear", "Stance cannot be determined."),
        ],
    }
    confusion_reduced = {
        "citation_function": "Separates rhetorical use from sustainability/economic/modeling topics; clarifies historical vs foundational vs modeling boundaries.",
        "topic_or_discourse_area": "Preserves topic information without forcing it into the citation-function label.",
        "stance_toward_seed": "Prevents historical importance, topic alignment, or controversy from being treated as endorsement or criticism.",
    }
    rows = []
    for dimension, categories in dimensions.items():
        for category, definition in categories:
            rows.append(
                {
                    "dimension": dimension,
                    "category": category,
                    "definition": definition,
                    "decision_rule": "Code independently from the other two dimensions.",
                    "observed_confusion_reduced": confusion_reduced[dimension],
                    "recommendation": "recommended",
                }
            )
    return rows


def workflow_rows():
    return [
        {"area": "classification_design", "priority": "high", "recommendation": "Adopt the three-dimension coding model.", "rationale": "Current role labels mix rhetorical function with topic, contributing to low fallback agreement and historical/foundational/modeling confusion.", "implementation": "Use the proposed v2 prompt/schema and update human fields before the next LLM test.", "status": "proposed"},
        {"area": "prompt_schema", "priority": "high", "recommendation": "Require separate function and stance evidence quotes.", "rationale": "Supportive and critique labels need explicit evaluative evidence.", "implementation": "Reject or escalate supportive/critical outputs whose stance quote lacks an evaluative cue.", "status": "proposed_v2_artifacts_created"},
        {"area": "prompt_schema", "priority": "high", "recommendation": "Make bibliography-only a terminal citation-function decision.", "rationale": "Bibliography-only uncertainty currently coexists with substantive roles.", "implementation": "When bibliography is detected, prohibit substantive function inference and require human review.", "status": "proposed_v2_artifacts_created"},
        {"area": "repeated_contexts", "priority": "high", "recommendation": "Retain mention variants for traceability but evaluate and sample at context_group_id level.", "rationale": "The 34 repeated rows are 17 same-page context groups and can double-weight one rhetorical event.", "implementation": "Use context_group_id, is_repeated_context, and mention_variant_count; select one canonical variant unless variants differ materially.", "status": "implemented_in_validation_sample"},
        {"area": "extraction", "priority": "high", "recommendation": "Extract sentence_before, citation_sentence, sentence_after, wider context_window, and section heading.", "rationale": "Short and incomplete snippets undermine function and stance decisions.", "implementation": "Structured fields added to future extraction and validation-sampling code.", "status": "implemented_for_future_runs"},
        {"area": "extraction", "priority": "high", "recommendation": "Strengthen bibliography detection and recalibrate extraction confidence.", "rationale": "Current bibliography uncertainty and score-only confidence create misleading high-confidence classifications.", "implementation": "Use page/snippet bibliography signals and citation-sentence completeness in confidence.", "status": "implemented_for_future_runs"},
        {"area": "human_review", "priority": "high", "recommendation": "Review the ranked next 25 before another LLM run.", "rationale": "They concentrate critique, bibliography, ambiguity, extraction, and repeated-context failure modes.", "implementation": "Use next_25_validation_rows_review_guide.csv.", "status": "ready"},
        {"area": "evaluation", "priority": "high", "recommendation": "Deduplicate by context_group_id for model metrics.", "rationale": "Mention variants should not count as independent validation observations.", "implementation": "Report both row-level traceability and group-level agreement.", "status": "proposed"},
        {"area": "scaling", "priority": "high", "recommendation": "Do not scale to 500 yet.", "rationale": "Only 24 rows are human-coded and the category/extraction redesign has not been tested.", "implementation": "Revise prompt/schema, adjudicate next 25, then run a new 100-context pilot.", "status": "recommended"},
    ]


def main():
    rows = read_csv(SAMPLE)
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)

    for row in rows:
        key = group_key(row)
        variants = {member["context_id"].split("|")[-1] for member in groups[key]}
        row["context_group_id"] = group_id(key)
        row["is_repeated_context"] = "TRUE" if len(variants) > 1 else "FALSE"
        row["mention_variant_count"] = str(len(variants))

    fields = list(rows[0])
    for field in ("context_group_id", "is_repeated_context", "mention_variant_count"):
        if field not in fields:
            fields.append(field)
    write_csv(SAMPLE, rows, fields)

    candidates = []
    for row in rows:
        if row.get("human_primary_role", "").strip():
            continue
        score, reasons = priority_score(row)
        candidate = dict(row)
        candidate["selection_score"] = score
        candidate["selection_reason"] = " | ".join(reasons)
        candidate["fallback_primary_role_normalized"] = fallback_role(row)
        candidate["suggested_coding_questions"] = coding_questions(row)
        candidates.append(candidate)

    candidates.sort(key=lambda row: (-int(row["selection_score"]), row["context_group_id"], row["context_id"]))
    selected = []
    group_counts = Counter()
    for row in candidates:
        cap = 2 if row["llm_primary_role"] == "critique" else 1
        if group_counts[row["context_group_id"]] >= cap:
            continue
        selected.append(row)
        group_counts[row["context_group_id"]] += 1
        if len(selected) == 25:
            break
    if len(selected) < 25:
        selected_ids = {row["context_id"] for row in selected}
        selected.extend(row for row in candidates if row["context_id"] not in selected_ids)[: 25 - len(selected)]

    next_fields = [
        "context_id", "context_group_id", "is_repeated_context", "mention_variant_count",
        "title", "year", "venue", "page", "selection_score", "selection_reason",
        "review_priority", "review_reason", "extraction_confidence", "llm_primary_role",
        "llm_discourse_category", "llm_stance_toward_meadows", "llm_confidence",
        "llm_uncertainty_flags", "fallback_primary_role_normalized", "snippet_clean",
    ]
    write_csv(TABLES / "next_25_validation_rows_to_review.csv", selected, next_fields)

    guide_fields = [
        "context_id", "context_group_id", "title", "year", "snippet_clean",
        "llm_primary_role", "llm_stance_toward_meadows", "fallback_primary_role_normalized",
        "selection_reason", "suggested_coding_questions",
    ]
    write_csv(TABLES / "next_25_validation_rows_review_guide.csv", selected, guide_fields)
    write_csv(TABLES / "validation_category_redesign_proposal.csv", redesign_rows())
    write_csv(TABLES / "validation_workflow_recommendations.csv", workflow_rows())
    print(f"Added context grouping to {len(rows)} rows and selected {len(selected)} next-review rows.")


if __name__ == "__main__":
    main()
