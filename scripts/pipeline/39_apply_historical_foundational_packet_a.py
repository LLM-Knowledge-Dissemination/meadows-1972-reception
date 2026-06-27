#!/usr/bin/env python3
"""Apply Packet A historical/foundational adjudications and diagnostics."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"


ADJUDICATIONS = {
    "cg_scale_02949b73c4ca": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Citation is purely chronological/publication lineage. No substantive Meadows claim is being used as evidence."),
    "cg_scale_19b779ab2843": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Debate/reception history. Citation concerns criticism and defense of Limits to Growth, not use of a Meadows substantive claim."),
    "cg_scale_542ac8d40469": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "very_high", "Explicit publication and organizational history. No substantive claim use."),
    "cg_scale_66c8a6b72324": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "very_high", "Organizational and intellectual-network history. Focus is Georgescu-Roegen's relationship with the Club of Rome and audience-building."),
    "cg_scale_862d74c47bc6": ("yes", "foundational_citation", "economics_growth", "neutral_descriptive", "medium", "Boundary case. Although sentence begins with publication history, broader context shifts to both works emphasizing dangers of economic growth; substantive argument is doing the work."),
    "cg_scale_d086883a1bb7": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Debate and reception history. Function is participation in public/intellectual controversy around Limits to Growth, not use of Meadows findings as evidence."),
    "cg_scale_ebde91a1ba9c": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Publication history and origin story. No substantive claim is being invoked."),
    "cg_scale_6cbe224cc554": ("yes", "foundational_citation", "population_resources", "neutral_descriptive", "very_high", "Clear substantive use. Author summarizes LTG prediction of collapse due to resource depletion, pollution, and agricultural limits."),
    "cg_scale_54cbcb563011": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Used as historical origin/example of environmental metaphors LIMITS and BOUNDARIES. Cultural/discursive history, not substantive Meadows claim."),
    "cg_scale_61e02752eaf6": ("yes", "historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "high", "Publication lineage and background description. Function is describing LTG corpus, not invoking a substantive finding."),
    "cg_scale_8a83c35f5d0a": ("yes", "foundational_citation", "economics_growth", "neutral_descriptive", "medium_high", "Boundary case. LTG popularized concerns about finite planetary limits and growth constraints; substantive idea is doing the work."),
    "cg_scale_bf36b14a09b5": ("yes", "foundational_citation", "economics_growth", "neutral_descriptive", "high", "Sentence links LTG to critical appraisal of unlimited growth and environmental crisis; functioning as substantive evidence for intellectual shift."),
    "cg_scale_fa79752b7d81": ("yes", "unclear", "historical_or_cultural_memory", "neutral_descriptive", "high", "Truncated extraction. Insufficient evidence to distinguish publication history from substantive argument."),
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


def apply_packet_a() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "historical_foundational_packet_A.csv")
    ids = {row["context_group_id"] for row in rows}
    if ids != set(ADJUDICATIONS):
        raise ValueError(f"Packet A IDs do not match adjudications; missing={set(ADJUDICATIONS)-ids}, extra={ids-set(ADJUDICATIONS)}")
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
            "coding_batch": "Packet A",
            "coder": "human_adjudication_chatgpt_assisted",
        })
        coded.append(out)
    write_csv(VALIDATION / "historical_foundational_packet_A_coded.csv", coded)
    return coded


def agreement_type(row: Dict[str, str]) -> str:
    router = row.get("router_primary_role", "")
    human = row.get("human_primary_role", "")
    if router == human:
        return "agreement"
    if router == "historical_framing" and human == "foundational_citation":
        return "false_historical"
    if router == "foundational_citation" and human == "historical_framing":
        return "false_foundational"
    if human == "unclear":
        return "human_unclear"
    return "other_disagreement"


def agreement_rows(rows: List[Dict[str, Any]], output: Path) -> None:
    total = len(rows)
    agreement = sum(1 for row in rows if row["router_primary_role"] == row["human_primary_role"])
    false_historical = sum(1 for row in rows if agreement_type(row) == "false_historical")
    false_foundational = sum(1 for row in rows if agreement_type(row) == "false_foundational")
    unclear = sum(1 for row in rows if row["human_primary_role"] == "unclear")
    out = []
    for row in rows:
        out.append({
            "context_group_id": row["context_group_id"],
            "title": row.get("title", ""),
            "venue": row.get("venue", ""),
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "human_topic_or_discourse_area": row["human_topic_or_discourse_area"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "disagreement_type": agreement_type(row),
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
            "total_rows": total,
            "router_agreement_count": agreement,
            "router_agreement_rate": pct(agreement, total),
            "router_disagreement_count": total - agreement,
            "router_disagreement_rate": pct(total - agreement, total),
            "false_historical_count": false_historical,
            "false_foundational_count": false_foundational,
            "unclear_human_labels": unclear,
        })
    write_csv(output, out)


def confusion_matrix(rows: List[Dict[str, Any]], output: Path) -> None:
    counts = Counter((row["router_primary_role"], row["human_primary_role"]) for row in rows)
    out = [
        {
            "router_primary_role": router,
            "human_primary_role": human,
            "count": count,
        }
        for (router, human), count in sorted(counts.items())
    ]
    write_csv(output, out)


def error_inventory(rows: List[Dict[str, Any]], output: Path) -> None:
    by_topic = defaultdict(lambda: {"n": 0, "agreement": 0})
    by_venue_title = defaultdict(lambda: {"n": 0, "agreement": 0})
    out = []
    for row in rows:
        agree = row["router_primary_role"] == row["human_primary_role"]
        by_topic[row["human_topic_or_discourse_area"]]["n"] += 1
        by_topic[row["human_topic_or_discourse_area"]]["agreement"] += int(agree)
        venue_title = f"{row.get('venue','')} | {row.get('title','')}"
        by_venue_title[venue_title]["n"] += 1
        by_venue_title[venue_title]["agreement"] += int(agree)
        out.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if agree else "no",
            "disagreement_type": agreement_type(row),
            "topic": row["human_topic_or_discourse_area"],
            "venue": row.get("venue", ""),
            "title": row.get("title", ""),
            "agreement_rate_for_topic": pct(by_topic[row["human_topic_or_discourse_area"]]["agreement"], by_topic[row["human_topic_or_discourse_area"]]["n"]),
            "agreement_by_venue_title_note": "venue/title group retained for diagnostic review; no corpus inference",
        })
    write_csv(output, out)


def combined_tables(packet_a: List[Dict[str, Any]]) -> None:
    six = read_csv(TABLES / "historical_foundational_consensus_merged.csv")
    combined = []
    for row in six:
        combined.append({
            "source": "original_six",
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["consensus_primary_role"],
            "agreement_yes_no": row["agreement_yes_no"],
            "confidence": row["confidence"],
            "notes": row["notes"],
        })
    for row in packet_a:
        combined.append({
            "source": "packet_A",
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if row["router_primary_role"] == row["human_primary_role"] else "no",
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
        })
    write_csv(TABLES / "historical_foundational_combined_agreement.csv", combined)
    confusion_matrix(combined, TABLES / "historical_foundational_combined_confusion_matrix.csv")
    source_counts = Counter(row["source"] for row in combined)
    role_counts = Counter(row["human_primary_role"] for row in combined)
    agreement = sum(1 for row in combined if row["agreement_yes_no"] == "yes")
    total = len(combined)
    summary = [{
        "original_six_count": source_counts["original_six"],
        "packet_A_count": source_counts["packet_A"],
        "total_count": total,
        "human_historical_framing_count": role_counts["historical_framing"],
        "human_foundational_citation_count": role_counts["foundational_citation"],
        "human_unclear_count": role_counts["unclear"],
        "router_agreement_count": agreement,
        "router_agreement_rate": pct(agreement, total),
        "router_disagreement_count": total - agreement,
        "router_disagreement_rate": pct(total - agreement, total),
    }]
    write_csv(TABLES / "historical_foundational_combined_summary.csv", summary)


def update_validation_progress(packet_a: List[Dict[str, Any]]) -> None:
    prev = read_csv(TABLES / "validation_progress_after_consensus.csv")
    previous_count = int(prev[0].get("new_human_coded_count", 54)) if prev else 54
    packet_b_rows = len(read_csv(VALIDATION / "historical_foundational_packet_B.csv"))
    packet_c_rows = len(read_csv(VALIDATION / "historical_foundational_packet_C.csv"))
    router_safe_remaining = packet_b_rows + packet_c_rows + 61 + 1
    extraction_remaining = len(read_csv(VALIDATION / "extraction_recovery_review_packet.csv"))
    rows = [{
        "previous_human_coded_count": previous_count,
        "packet_A_coded_count": len(packet_a),
        "total_human_coded_count": previous_count + len(packet_a),
        "remaining_packet_B_rows": packet_b_rows,
        "remaining_packet_C_rows": packet_c_rows,
        "remaining_router_safe_rows": router_safe_remaining,
        "remaining_extraction_recovery_rows": extraction_remaining,
        "next_recommended_coding_priority": "Packet B historical/foundational boundary rows",
    }]
    write_csv(TABLES / "validation_progress_after_packet_A.csv", rows)


def prepare_packet_b() -> None:
    rows = []
    for row in read_csv(VALIDATION / "historical_foundational_packet_B.csv"):
        out = {
            "context_group_id": row["context_group_id"],
            "citation_sentence": row.get("citation_sentence", ""),
            "context_window": row.get("context_window", ""),
            "router_primary_role": row.get("router_primary_role", ""),
            "router_topic": row.get("router_topic", ""),
            "routing_reason": row.get("routing_reason", ""),
            "decision_question": row.get("reviewer_question", ""),
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "review_status": "",
        }
        rows.append(out)
    write_csv(VALIDATION / "historical_foundational_packet_B_ready.csv", rows)


def main() -> None:
    packet_a = apply_packet_a()
    agreement_rows(packet_a, TABLES / "historical_foundational_packet_A_agreement.csv")
    confusion_matrix(packet_a, TABLES / "historical_foundational_packet_A_confusion_matrix.csv")
    error_inventory(packet_a, TABLES / "historical_foundational_packet_A_error_inventory.csv")
    combined_tables(packet_a)
    update_validation_progress(packet_a)
    prepare_packet_b()
    agreement = sum(1 for row in packet_a if row["router_primary_role"] == row["human_primary_role"])
    counts = Counter(row["human_primary_role"] for row in packet_a)
    print(f"Packet A rows coded: {len(packet_a)}")
    print(f"Packet A agreement: {agreement}/{len(packet_a)}")
    print("Packet A human roles: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
