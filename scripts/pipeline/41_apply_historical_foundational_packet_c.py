#!/usr/bin/env python3
"""Apply Packet C adjudications and final boundary diagnostics."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"


ADJUDICATIONS = {
    "cg_scale_7ce353eeec7b": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "very_high", "Landmark-status citation describing LTG influence and status as a foundational environmental text."),
    "cg_scale_bb17ca457eca": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "high", "Citation used because LTG raised concerns about material scarcity and exhaustible resources."),
    "cg_scale_3f22b644fd1b": ("no", "unclear", "limits_to_growth", "neutral_descriptive", "high", "Phrase appears conceptual rather than a clear citation event to Meadows et al. 1972."),
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


def pct(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def apply_packet_c() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "historical_foundational_packet_C.csv")
    ids = {row["context_group_id"] for row in rows}
    if ids != set(ADJUDICATIONS):
        raise ValueError(f"Packet C IDs do not match adjudications; missing={set(ADJUDICATIONS)-ids}, extra={ids-set(ADJUDICATIONS)}")
    coded = []
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
            "coding_batch": "Packet C",
            "coder": "human_adjudication_chatgpt_assisted",
        })
        coded.append(out)
    write_csv(VALIDATION / "historical_foundational_packet_C_coded.csv", coded)
    return coded


def disagreement_type(row: Dict[str, str]) -> str:
    router = row.get("router_primary_role", "")
    human = row.get("human_primary_role", "")
    if router == human:
        return "agreement"
    if router == "historical_framing" and human == "foundational_citation":
        return "historical_to_foundational"
    if router == "historical_framing" and human == "modeling_simulation_reference":
        return "historical_to_modeling"
    if router == "historical_framing" and human == "unclear":
        return "historical_to_unclear"
    if router == "foundational_citation" and human == "historical_framing":
        return "foundational_to_historical"
    if router == "foundational_citation" and human == "modeling_simulation_reference":
        return "foundational_to_modeling"
    if router == "foundational_citation" and human == "unclear":
        return "foundational_to_unclear"
    return "other"


def agreement_rows(rows: List[Dict[str, Any]], output: Path) -> None:
    total = len(rows)
    agreement = sum(1 for row in rows if row["router_primary_role"] == row["human_primary_role"])
    role_counts = Counter(row["human_primary_role"] for row in rows)
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
            "total_rows": total,
            "router_agreement_count": agreement,
            "router_agreement_rate": pct(agreement, total),
            "router_disagreement_count": total - agreement,
            "router_disagreement_rate": pct(total - agreement, total),
            "historical_cases": role_counts["historical_framing"],
            "foundational_cases": role_counts["foundational_citation"],
            "unclear_cases": role_counts["unclear"],
        })
    write_csv(output, out)


def confusion_matrix(rows: List[Dict[str, Any]], output: Path) -> None:
    counts = Counter((row["router_primary_role"], row["human_primary_role"]) for row in rows)
    write_csv(output, [
        {"router_primary_role": router, "human_primary_role": human, "count": count}
        for (router, human), count in sorted(counts.items())
    ])


def error_inventory(rows: List[Dict[str, Any]], output: Path) -> None:
    counts = Counter(disagreement_type(row) for row in rows)
    out = []
    for row in rows:
        out.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "disagreement_type": disagreement_type(row),
            "topic": row["human_topic_or_discourse_area"],
            "confidence": row["human_confidence"],
            "error_inventory_summary": " | ".join(f"{key}={value}" for key, value in sorted(counts.items())),
        })
    write_csv(output, out)


def final_rows(packet_c: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for row in read_csv(TABLES / "historical_foundational_combined_agreement_v2.csv"):
        rows.append(dict(row))
    for row in packet_c:
        rows.append({
            "source": "packet_C",
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
        })
    return rows


def final_outputs(packet_c: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = final_rows(packet_c)
    write_csv(TABLES / "historical_foundational_final_agreement.csv", rows)
    confusion_matrix(rows, TABLES / "historical_foundational_final_confusion_matrix.csv")
    role_counts = Counter(row["human_primary_role"] for row in rows)
    router_counts = Counter(row["router_primary_role"] for row in rows)
    types = Counter(disagreement_type(row) for row in rows)
    agreement = sum(1 for row in rows if row["agreement_yes_no"] == "yes")
    summary = [{
        "total_adjudicated": len(rows),
        "human_historical_framing_count": role_counts["historical_framing"],
        "human_foundational_citation_count": role_counts["foundational_citation"],
        "human_modeling_simulation_reference_count": role_counts["modeling_simulation_reference"],
        "human_unclear_count": role_counts["unclear"],
        "router_historical_framing_count": router_counts["historical_framing"],
        "router_foundational_citation_count": router_counts["foundational_citation"],
        "router_modeling_simulation_reference_count": router_counts["modeling_simulation_reference"],
        "router_unclear_count": router_counts["unclear"],
        "agreement_count": agreement,
        "agreement_rate": pct(agreement, len(rows)),
        "disagreement_count": len(rows) - agreement,
        "disagreement_rate": pct(len(rows) - agreement, len(rows)),
        "historical_to_foundational": types["historical_to_foundational"],
        "historical_to_modeling": types["historical_to_modeling"],
        "historical_to_unclear": types["historical_to_unclear"],
        "foundational_to_historical": types["foundational_to_historical"],
        "foundational_to_modeling": types["foundational_to_modeling"],
        "foundational_to_unclear": types["foundational_to_unclear"],
        "other": sum(count for key, count in types.items() if key not in {"agreement", "historical_to_foundational", "historical_to_modeling", "historical_to_unclear", "foundational_to_historical", "foundational_to_modeling", "foundational_to_unclear"}),
    }]
    write_csv(TABLES / "historical_foundational_final_summary.csv", summary)
    return rows


def validation_assessment(final: List[Dict[str, Any]]) -> None:
    roles = Counter(row["human_primary_role"] for row in final)
    types = Counter(disagreement_type(row) for row in final)
    agreement = sum(1 for row in final if row["agreement_yes_no"] == "yes")
    rows = [
        {
            "assessment_question": "Does the historical/foundational distinction appear stable?",
            "answer": "yes_for_human_adjudication",
            "evidence": f"Final human labels include {roles['historical_framing']} historical and {roles['foundational_citation']} foundational cases, with {roles['modeling_simulation_reference']} modeling and {roles['unclear']} unclear.",
            "recommendation": "Keep the distinction for validation diagnostics; retain modeling and unclear as separate outcomes.",
        },
        {
            "assessment_question": "Is the category distribution balanced?",
            "answer": "reasonably_balanced",
            "evidence": f"Historical={roles['historical_framing']}; foundational={roles['foundational_citation']}; total={len(final)}.",
            "recommendation": "Use only as diagnostic balance for the reviewed set.",
        },
        {
            "assessment_question": "What are the dominant disagreement patterns?",
            "answer": "historical_to_foundational_then_foundational_to_historical",
            "evidence": f"historical_to_foundational={types['historical_to_foundational']}; foundational_to_historical={types['foundational_to_historical']}; unclear/modeling disagreements also present.",
            "recommendation": "Review disagreement examples before any future router refinement.",
        },
        {
            "assessment_question": "Does the router systematically overcall historical framing?",
            "answer": "yes_in_this_reviewed_boundary_set",
            "evidence": f"historical_to_foundational={types['historical_to_foundational']} and historical_to_unclear={types['historical_to_unclear']}; agreement={agreement}/{len(final)}.",
            "recommendation": "Treat as validation evidence only; no router change here.",
        },
        {
            "assessment_question": "Is current evidence sufficient to justify future router refinement?",
            "answer": "sufficient_to_plan_refinement_not_to_implement",
            "evidence": "All 28 boundary rows are adjudicated, but changes should be designed and tested separately.",
            "recommendation": "Prepare candidate refinements in a later phase with held-out validation.",
        },
        {
            "assessment_question": "What additional validation would be most informative?",
            "answer": "modeling_and_extraction_recovery",
            "evidence": "One modeling case emerged inside the boundary review and 49 extraction-recovery rows remain.",
            "recommendation": "Validate modeling next, then extraction-recovery rows.",
        },
    ]
    write_csv(TABLES / "historical_foundational_boundary_validation_assessment.csv", rows)


def validation_progress() -> None:
    total_validation_rows = 97
    prior = read_csv(TABLES / "validation_progress_after_packet_B.csv")
    previous = int(prior[0].get("total_validated_rows", 73)) if prior else 73
    packet_c_count = len(read_csv(VALIDATION / "historical_foundational_packet_C_coded.csv"))
    total = previous + packet_c_count
    extraction = len(read_csv(VALIDATION / "extraction_recovery_review_packet.csv"))
    rows = [{
        "total_validated_rows": total,
        "percent_validated": pct(total, total_validation_rows),
        "remaining_router_safe_rows": 62,
        "remaining_extraction_recovery_rows": extraction,
        "remaining_unresolved_boundary_cases": 0,
        "next_recommended_validation_target": "modeling packet",
    }]
    write_csv(TABLES / "validation_progress_after_packet_C.csv", rows)


def next_priority() -> None:
    rows = [
        {
            "validation_target": "modeling packet",
            "rank": 1,
            "expected_information_gain": "high",
            "methodological_importance": "high",
            "likely_impact_on_classifier_performance": "high",
            "effort_required": "low",
            "recommendation": "recommended next validation target",
        },
        {
            "validation_target": "extraction-recovery review packet",
            "rank": 2,
            "expected_information_gain": "high",
            "methodological_importance": "high",
            "likely_impact_on_classifier_performance": "medium_high",
            "effort_required": "high",
            "recommendation": "next after modeling",
        },
        {
            "validation_target": "remaining router-safe bibliography rows",
            "rank": 3,
            "expected_information_gain": "medium",
            "methodological_importance": "medium",
            "likely_impact_on_classifier_performance": "medium",
            "effort_required": "medium",
            "recommendation": "use to validate structural bibliography rule",
        },
        {
            "validation_target": "OCR/unclear rows",
            "rank": 4,
            "expected_information_gain": "medium",
            "methodological_importance": "medium_high",
            "likely_impact_on_classifier_performance": "medium",
            "effort_required": "medium",
            "recommendation": "small n; useful for abstention diagnostics",
        },
    ]
    write_csv(TABLES / "next_validation_priority_assessment.csv", rows)


def main() -> None:
    packet_c = apply_packet_c()
    agreement_rows(packet_c, TABLES / "historical_foundational_packet_C_agreement.csv")
    confusion_matrix(packet_c, TABLES / "historical_foundational_packet_C_confusion_matrix.csv")
    error_inventory(packet_c, TABLES / "historical_foundational_packet_C_error_inventory.csv")
    final = final_outputs(packet_c)
    validation_assessment(final)
    validation_progress()
    next_priority()
    agreement = sum(1 for row in packet_c if row["router_primary_role"] == row["human_primary_role"])
    print(f"Packet C rows coded: {len(packet_c)}")
    print(f"Packet C agreement: {agreement}/{len(packet_c)}")
    print("Packet C human roles: " + ", ".join(f"{key}={value}" for key, value in sorted(Counter(row['human_primary_role'] for row in packet_c).items())))


if __name__ == "__main__":
    main()
