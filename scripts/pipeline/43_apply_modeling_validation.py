#!/usr/bin/env python3
"""Apply modeling/simulation adjudications and write diagnostic validation tables."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"

ADJUDICATIONS = {
    "cg_scale_6b415fdf2f3f": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "high", "Explicit reference to Limits to Growth simulation."),
    "cg_scale_a9febdca9b54": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "high", "Modelling the Earth as a whole system."),
    "cg_scale_07adf41e9f5d": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "very_high", "Explicit discussion of structural equations and computer simulations."),
    "cg_scale_c6bc3962a719": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "very_high", "Direct discussion of model architecture and Forrester lineage."),
    "cg_scale_d35d19dd2024": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "very_high", "Explicit World3 discussion and quantitative prediction framework."),
    "cg_scale_0dd1cf88e49f": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "medium_high", "Long-term environmental scenarios discussed as model outputs."),
    "cg_scale_03250e4c46bf": ("no", "unclear", "systems_modeling", "neutral_descriptive", "high", "Publication metadata / insufficient citation context."),
    "cg_scale_a5a248e638d7": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "very_high", "Explicit inheritance from World3 model."),
    "cg_scale_aff47bffced1": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "medium", "Refers to collapse scenario outcome rather than model structure."),
    "cg_scale_cf7056eb3380": ("yes", "modeling_simulation_reference", "systems_modeling", "neutral_descriptive", "high", "Discussion of LTG scenarios and their behavior."),
    "cg_scale_858bfa0bf3a3": ("no", "unclear", "systems_modeling", "neutral_descriptive", "high", "Phrase-level mention without sufficient citation context."),
}


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


def pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def disagreement_type(row: Dict[str, str]) -> str:
    router = row.get("router_primary_role", "")
    human = row.get("human_primary_role", "")
    if router == human:
        return "agreement"
    if router == "modeling_simulation_reference" and human == "foundational_citation":
        return "modeling_to_foundational"
    if router == "modeling_simulation_reference" and human == "unclear":
        return "modeling_to_unclear"
    if router == "foundational_citation" and human == "modeling_simulation_reference":
        return "foundational_to_modeling"
    return "other"


def apply_adjudications() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "modeling_validation_packet.csv")
    ids = {row["context_group_id"] for row in rows}
    expected = set(ADJUDICATIONS)
    if ids != expected:
        raise ValueError(f"Modeling packet IDs do not match adjudications; missing={expected - ids}, extra={ids - expected}")

    coded: List[Dict[str, Any]] = []
    for row in rows:
        seed, role, topic, stance, confidence, notes = ADJUDICATIONS[row["context_group_id"]]
        out = dict(row)
        out.update({
            "human_is_seed_work_citation": seed,
            "human_primary_role": role,
            "human_topic_or_discourse_area": topic,
            "human_stance_toward_seed": stance,
            "human_confidence": confidence,
            "human_notes": notes,
            "review_status": "coded",
            "coding_batch": "modeling_validation",
            "coder": "human_adjudication_chatgpt_assisted",
        })
        coded.append(out)
    write_csv(VALIDATION / "modeling_validation_coded.csv", coded)
    return coded


def write_agreement(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    agreement = sum(1 for row in rows if row["router_primary_role"] == row["human_primary_role"])
    role_counts = Counter(row["human_primary_role"] for row in rows)
    type_counts = Counter(disagreement_type(row) for row in rows)
    out = []
    for row in rows:
        out.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "human_topic_or_discourse_area": row["human_topic_or_discourse_area"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "disagreement_type": disagreement_type(row),
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
            "total_adjudicated": total,
            "agreement_count": agreement,
            "agreement_rate": pct(agreement, total),
            "disagreement_count": total - agreement,
            "disagreement_rate": pct(total - agreement, total),
            "modeling_simulation_reference_count": role_counts["modeling_simulation_reference"],
            "foundational_citation_count": role_counts["foundational_citation"],
            "unclear_count": role_counts["unclear"],
            "modeling_to_foundational": type_counts["modeling_to_foundational"],
            "modeling_to_unclear": type_counts["modeling_to_unclear"],
            "foundational_to_modeling": type_counts["foundational_to_modeling"],
            "false_positives": type_counts["modeling_to_foundational"] + type_counts["modeling_to_unclear"],
            "false_negatives": type_counts["foundational_to_modeling"],
        })
    write_csv(TABLES / "modeling_validation_agreement.csv", out)


def write_confusion_and_errors(rows: List[Dict[str, Any]]) -> None:
    confusion = Counter((row["router_primary_role"], row["human_primary_role"]) for row in rows)
    write_csv(TABLES / "modeling_validation_confusion_matrix.csv", [
        {"router_primary_role": router, "human_primary_role": human, "count": count}
        for (router, human), count in sorted(confusion.items())
    ])

    type_counts = Counter(disagreement_type(row) for row in rows)
    write_csv(TABLES / "modeling_validation_error_inventory.csv", [
        {
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "disagreement_type": disagreement_type(row),
            "topic": row["human_topic_or_discourse_area"],
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
            "error_inventory_summary": " | ".join(f"{key}={value}" for key, value in sorted(type_counts.items())),
        }
        for row in rows
    ])


def write_assessment(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    agreement = sum(1 for row in rows if row["router_primary_role"] == row["human_primary_role"])
    roles = Counter(row["human_primary_role"] for row in rows)
    types = Counter(disagreement_type(row) for row in rows)
    rows_out = [
        {
            "assessment_question": "Does modeling appear to be a distinct citation function?",
            "answer": "yes_in_this_adjudicated_packet",
            "evidence": f"{roles['modeling_simulation_reference']} of {total} adjudicated rows were coded modeling_simulation_reference; agreement={agreement}/{total}.",
            "conservative_note": "Distinctness is strongest when the context explicitly mentions simulations, World3, system dynamics, scenarios, model architecture, or model behavior.",
        },
        {
            "assessment_question": "Is human coding consistent?",
            "answer": "mostly_consistent",
            "evidence": f"Human coding produced {roles['modeling_simulation_reference']} modeling, {roles['foundational_citation']} foundational, and {roles['unclear']} unclear outcomes.",
            "conservative_note": "Consistency should still be checked against future held-out modeling-like cases.",
        },
        {
            "assessment_question": "Are disagreements concentrated in specific edge cases?",
            "answer": "yes",
            "evidence": f"Disagreements were modeling_to_foundational={types['modeling_to_foundational']} and modeling_to_unclear={types['modeling_to_unclear']}.",
            "conservative_note": "The edge cases are scenario outcome without model-process discussion and metadata/phrase-level mentions.",
        },
        {
            "assessment_question": "Are scenario outcomes being confused with model discussion?",
            "answer": "some_evidence",
            "evidence": f"modeling_to_foundational={types['modeling_to_foundational']}.",
            "conservative_note": "A cited collapse or resource-scarcity outcome should remain foundational unless the model process, assumptions, variables, or scenario behavior is explicit.",
        },
        {
            "assessment_question": "Are metadata/phrase-level mentions the main source of uncertainty?",
            "answer": "yes_for_unclear_cases",
            "evidence": f"modeling_to_unclear={types['modeling_to_unclear']}.",
            "conservative_note": "Short metadata-only or phrase-level contexts should be left unclear rather than forced into modeling.",
        },
    ]
    write_csv(TABLES / "modeling_validation_assessment.csv", rows_out)


def write_progress() -> None:
    total_validation_rows = 97
    historical_foundational_validated = 28
    modeling_validated = len(read_csv(VALIDATION / "modeling_validation_coded.csv"))
    previous = int(read_csv(TABLES / "validation_progress_after_packet_C.csv")[0]["total_validated_rows"])
    total = previous + modeling_validated
    bibliography_pending = len(read_csv(VALIDATION / "router_safe_worklist_bibliography.csv"))
    ocr_pending = len(read_csv(VALIDATION / "router_safe_worklist_ocr_unclear.csv"))
    extraction_pending = len(read_csv(VALIDATION / "extraction_recovery_review_packet.csv"))
    rows = [{
        "total_validated_rows": total,
        "percent_validated": pct(total, total_validation_rows),
        "historical_foundational_validated": historical_foundational_validated,
        "modeling_validated": modeling_validated,
        "extraction_recovery_pending": extraction_pending,
        "bibliography_pending": bibliography_pending,
        "OCR_pending": ocr_pending,
    }]
    write_csv(TABLES / "validation_progress_after_modeling.csv", rows)


def write_priorities() -> None:
    rows = [
        {
            "validation_target": "extraction-recovery review",
            "rank": 1,
            "expected_information_gain": "high",
            "methodological_importance": "high",
            "effort_required": "high",
            "expected_impact_on_classifier_reliability": "high",
            "rationale": "Extraction quality affects whether downstream citation-function labels are valid at all.",
        },
        {
            "validation_target": "bibliography validation",
            "rank": 2,
            "expected_information_gain": "medium_high",
            "methodological_importance": "high",
            "effort_required": "medium",
            "expected_impact_on_classifier_reliability": "medium_high",
            "rationale": "Bibliography-only detection supports exclusion/abstention logic and false-positive control.",
        },
        {
            "validation_target": "OCR/unclear validation",
            "rank": 3,
            "expected_information_gain": "medium",
            "methodological_importance": "medium_high",
            "effort_required": "low",
            "expected_impact_on_classifier_reliability": "medium",
            "rationale": "Small set but useful for abstention and context-quality policy.",
        },
        {
            "validation_target": "remaining router-safe categories",
            "rank": 4,
            "expected_information_gain": "medium",
            "methodological_importance": "medium",
            "effort_required": "medium",
            "expected_impact_on_classifier_reliability": "medium",
            "rationale": "Useful only after extraction and bibliography checks are less uncertain.",
        },
    ]
    write_csv(TABLES / "post_modeling_validation_priorities.csv", rows)


def write_freeze_assessment() -> None:
    rows = [
        {
            "assessment_dimension": "overall_validation_maturity",
            "status": "nearly_validation_complete_not_frozen",
            "evidence": "Historical/foundational boundary validation and modeling validation are complete, but extraction-recovery and bibliography validation remain pending.",
            "conservative_assessment": "Do not freeze methodology until extraction quality and bibliography-only classification are reviewed.",
        },
        {
            "assessment_dimension": "boundary_validation",
            "status": "complete_for_current_boundary_set",
            "evidence": "28 historical/foundational boundary cases adjudicated; unresolved boundary cases reported as 0.",
            "conservative_assessment": "Use as diagnostic evidence; future router refinement should be tested separately.",
        },
        {
            "assessment_dimension": "modeling_validation",
            "status": "complete_for_current_modeling_packet",
            "evidence": "11 modeling-router rows adjudicated.",
            "conservative_assessment": "Modeling appears codable, but edge cases require explicit model-process evidence.",
        },
        {
            "assessment_dimension": "extraction_review",
            "status": "additional_validation_needed",
            "evidence": f"{len(read_csv(VALIDATION / 'extraction_recovery_review_packet.csv'))} extraction-recovery rows remain pending.",
            "conservative_assessment": "Extraction uncertainty can dominate classification error and should be addressed before freeze.",
        },
        {
            "assessment_dimension": "remaining_uncoded_rows",
            "status": "additional_targeted_validation_needed",
            "evidence": f"Bibliography pending={len(read_csv(VALIDATION / 'router_safe_worklist_bibliography.csv'))}; OCR pending={len(read_csv(VALIDATION / 'router_safe_worklist_ocr_unclear.csv'))}.",
            "conservative_assessment": "Targeted review remains more useful than broad scaling.",
        },
    ]
    write_csv(TABLES / "pre_freeze_methodology_assessment.csv", rows)


def main() -> None:
    coded = apply_adjudications()
    write_agreement(coded)
    write_confusion_and_errors(coded)
    write_assessment(coded)
    write_progress()
    write_priorities()
    write_freeze_assessment()
    agreement = sum(1 for row in coded if row["router_primary_role"] == row["human_primary_role"])
    print(f"Modeling rows adjudicated: {len(coded)}")
    print(f"Agreement: {agreement}/{len(coded)} ({pct(agreement, len(coded))})")


if __name__ == "__main__":
    main()
