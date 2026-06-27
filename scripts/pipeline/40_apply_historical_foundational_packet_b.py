#!/usr/bin/env python3
"""Apply Packet B adjudications and recompute boundary diagnostics."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"


ADJUDICATIONS = {
    "cg_scale_870ff89d3c3e": ("yes", "historical_framing", "economics_growth", "neutral_descriptive", "high", "Reception/critique history. Economists refuting LTG and debating resource economics."),
    "cg_scale_09b3b42fe17f": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "very_high", "Direct quotation of a core Meadows prediction. Textbook foundational citation."),
    "cg_scale_7d218ef13868": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "medium", "OCR-heavy, but visible function is substantive LTG proposition about population, industrialization, pollution, food, and resources."),
    "cg_scale_5858a73e5c8a": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "medium_high", "Mixed historical/substantive, but impact derives from LTG assessment of pollution, famine, and growth consequences."),
    "cg_scale_6e4e2c8d2ffb": ("yes", "modeling_simulation_reference", "population_resources", "neutral_descriptive", "high", "Citation describes variables/components used in the LTG system model. Modeling function dominates."),
    "cg_scale_d8f900dfbe3e": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "high", "Explicit reference to LTG prediction of economic collapse from resource exhaustion."),
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


def apply_packet_b() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "historical_foundational_packet_B.csv")
    ids = {row["context_group_id"] for row in rows}
    if ids != set(ADJUDICATIONS):
        raise ValueError(f"Packet B IDs do not match adjudications; missing={set(ADJUDICATIONS)-ids}, extra={ids-set(ADJUDICATIONS)}")
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
            "coding_batch": "Packet B",
            "coder": "human_adjudication_chatgpt_assisted",
        })
        coded.append(out)
    write_csv(VALIDATION / "historical_foundational_packet_B_coded.csv", coded)
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
    if human == "unclear":
        return "router_to_unclear"
    return "other"


def agreement_rows(rows: List[Dict[str, Any]], output: Path) -> None:
    total = len(rows)
    agreement = sum(1 for row in rows if row["router_primary_role"] == row["human_primary_role"])
    counts = Counter(disagreement_type(row) for row in rows)
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
            "false_historical_count": counts["historical_to_foundational"] + counts["historical_to_modeling"] + counts["historical_to_unclear"],
            "false_foundational_count": counts["foundational_to_historical"] + counts["foundational_to_modeling"],
            "modeling_cases": role_counts["modeling_simulation_reference"],
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


def combined_rows(packet_b: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined = []
    for row in read_csv(TABLES / "historical_foundational_combined_agreement.csv"):
        combined.append({
            "source": row["source"],
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": row["agreement_yes_no"],
            "confidence": row["confidence"],
            "notes": row["notes"],
        })
    for row in packet_b:
        combined.append({
            "source": "packet_B",
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
        })
    return combined


def combined_outputs(packet_b: List[Dict[str, Any]]) -> None:
    rows = combined_rows(packet_b)
    write_csv(TABLES / "historical_foundational_combined_agreement_v2.csv", rows)
    confusion_matrix(rows, TABLES / "historical_foundational_combined_confusion_matrix_v2.csv")
    source_counts = Counter(row["source"] for row in rows)
    role_counts = Counter(row["human_primary_role"] for row in rows)
    agreement = sum(1 for row in rows if row["agreement_yes_no"] == "yes")
    types = Counter(disagreement_type(row) for row in rows)
    summary = [{
        "original_six_count": source_counts["original_six"],
        "packet_A_count": source_counts["packet_A"],
        "packet_B_count": source_counts["packet_B"],
        "total_adjudicated": len(rows),
        "historical_framing_count": role_counts["historical_framing"],
        "foundational_citation_count": role_counts["foundational_citation"],
        "modeling_simulation_reference_count": role_counts["modeling_simulation_reference"],
        "unclear_count": role_counts["unclear"],
        "router_agreement_count": agreement,
        "router_agreement_rate": pct(agreement, len(rows)),
        "router_disagreement_count": len(rows) - agreement,
        "router_disagreement_rate": pct(len(rows) - agreement, len(rows)),
        "historical_to_foundational": types["historical_to_foundational"],
        "historical_to_modeling": types["historical_to_modeling"],
        "historical_to_unclear": types["historical_to_unclear"],
        "foundational_to_historical": types["foundational_to_historical"],
        "other": sum(count for key, count in types.items() if key not in {"agreement", "historical_to_foundational", "historical_to_modeling", "historical_to_unclear", "foundational_to_historical"}),
    }]
    write_csv(TABLES / "historical_foundational_combined_summary_v2.csv", summary)


def stability_assessment(packet_b: List[Dict[str, Any]]) -> None:
    combined = combined_rows(packet_b)
    total = len(combined)
    role_counts = Counter(row["human_primary_role"] for row in combined)
    agreement = sum(1 for row in combined if row["agreement_yes_no"] == "yes")
    types = Counter(disagreement_type(row) for row in combined)
    rows = [
        {
            "assessment_question": "Is the distinction stable?",
            "answer": "yes_for_human_adjudication",
            "evidence": f"{role_counts['historical_framing']} historical, {role_counts['foundational_citation']} foundational, {role_counts['modeling_simulation_reference']} modeling, {role_counts['unclear']} unclear across {total} adjudicated rows.",
            "recommendation": "Continue using the distinction for human validation; keep modeling and unclear as allowable outcomes.",
        },
        {
            "assessment_question": "Is the category distribution balanced?",
            "answer": "reasonably_balanced_between_historical_and_foundational",
            "evidence": f"Historical={role_counts['historical_framing']}; foundational={role_counts['foundational_citation']}; modeling/unclear are smaller but methodologically important.",
            "recommendation": "Complete Packet C before finalizing diagnostic proportions.",
        },
        {
            "assessment_question": "Is the router systematically biased?",
            "answer": "yes_toward_historical_in_current_adjudicated_set",
            "evidence": f"Historical-to-foundational={types['historical_to_foundational']}; historical-to-modeling={types['historical_to_modeling']}; historical-to-unclear={types['historical_to_unclear']}; agreement={agreement}/{total}.",
            "recommendation": "Do not change router yet; use this as diagnostic evidence after Packet C.",
        },
        {
            "assessment_question": "Is router refinement justified yet?",
            "answer": "not_yet",
            "evidence": "Packet C remains uncoded and current diagnostics are validation-only.",
            "recommendation": "Finish Packet C, then review whether a narrow refinement is warranted.",
        },
        {
            "assessment_question": "What additional evidence is still needed?",
            "answer": "packet_C_and_extraction_review",
            "evidence": "Three Packet C rows and extraction-recovery rows remain.",
            "recommendation": "Code Packet C next; keep extraction review separate.",
        },
    ]
    write_csv(TABLES / "historical_foundational_boundary_stability_assessment.csv", rows)


def validation_progress(packet_b: List[Dict[str, Any]]) -> None:
    prior = read_csv(TABLES / "validation_progress_after_packet_A.csv")
    previous = int(prior[0].get("total_human_coded_count", 67)) if prior else 67
    packet_c = read_csv(VALIDATION / "historical_foundational_packet_C.csv")
    extraction = read_csv(VALIDATION / "extraction_recovery_review_packet.csv")
    rows = [{
        "total_validated_rows": previous + len(packet_b),
        "packet_B_coded_count": len(packet_b),
        "remaining_packet_C_rows": len(packet_c),
        "remaining_router_safe_rows": len(packet_c) + 61 + 1,
        "remaining_extraction_recovery_rows": len(extraction),
        "remaining_unresolved_boundary_cases": len(packet_c),
    }]
    write_csv(TABLES / "validation_progress_after_packet_B.csv", rows)


def packet_c_readiness() -> None:
    rows = read_csv(VALIDATION / "historical_foundational_packet_C.csv")
    ids = [row.get("context_group_id", "") for row in rows]
    required = ["context_group_id", "citation_sentence", "context_window", "router_primary_role", "router_topic", "routing_reason", "reviewer_question"]
    missing_fields = [field for field in required if rows and field not in rows[0]]
    duplicate_ids = len(ids) - len(set(ids))
    write_csv(TABLES / "packet_C_readiness_check.csv", [{
        "row_count": len(rows),
        "duplicate_ids": duplicate_ids,
        "missing_fields": " | ".join(missing_fields),
        "coding_readiness": "ready" if rows and duplicate_ids == 0 and not missing_fields else "not_ready",
    }])


def main() -> None:
    packet_b = apply_packet_b()
    agreement_rows(packet_b, TABLES / "historical_foundational_packet_B_agreement.csv")
    confusion_matrix(packet_b, TABLES / "historical_foundational_packet_B_confusion_matrix.csv")
    error_inventory(packet_b, TABLES / "historical_foundational_packet_B_error_inventory.csv")
    combined_outputs(packet_b)
    stability_assessment(packet_b)
    validation_progress(packet_b)
    packet_c_readiness()
    agreement = sum(1 for row in packet_b if row["router_primary_role"] == row["human_primary_role"])
    print(f"Packet B rows coded: {len(packet_b)}")
    print(f"Packet B agreement: {agreement}/{len(packet_b)}")
    print("Packet B human roles: " + ", ".join(f"{key}={value}" for key, value in sorted(Counter(row['human_primary_role'] for row in packet_b).items())))


if __name__ == "__main__":
    main()
