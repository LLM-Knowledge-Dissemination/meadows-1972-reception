#!/usr/bin/env python3
"""Prepare rapid adjudication workbook for historical/foundational rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"

HUMAN_FIELDS = [
    "human_is_seed_work_citation",
    "human_primary_role",
    "human_topic_or_discourse_area",
    "human_stance_toward_seed",
    "human_confidence",
    "human_notes",
    "review_status",
]


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


def blank_human(row: Dict[str, Any]) -> Dict[str, Any]:
    for field in HUMAN_FIELDS:
        row[field] = ""
    return row


def load_workbook_rows() -> List[Dict[str, Any]]:
    packet = {
        row["context_group_id"]: row
        for row in read_csv(VALIDATION / "historical_foundational_expansion_review_packet.csv")
    }
    order = read_csv(TABLES / "historical_foundational_coding_order.csv")
    rows: List[Dict[str, Any]] = []
    for order_row in order:
        source = packet.get(order_row["context_group_id"], {})
        if not source:
            continue
        rows.append(blank_human({
            "coding_order": int(order_row.get("coding_sequence", "999")),
            "expected_information_gain": order_row.get("expected_information_gain", ""),
            "boundary_ambiguity": order_row.get("boundary_ambiguity", ""),
            "context_group_id": source.get("context_group_id", ""),
            "title": source.get("title", ""),
            "year": source.get("year", ""),
            "venue": source.get("venue", ""),
            "citation_sentence": source.get("citation_sentence", ""),
            "sentence_before": source.get("sentence_before", ""),
            "sentence_after": source.get("sentence_after", ""),
            "context_window": source.get("context_window", ""),
            "router_primary_role": source.get("router_primary_role", ""),
            "router_topic": source.get("router_topic", ""),
            "routing_reason": source.get("routing_reason", ""),
            "key_boundary_features": order_row.get("coding_rationale", ""),
            "reviewer_question": source.get("decision_question", ""),
        }))
    rows.sort(key=lambda row: (
        row["coding_order"],
        {"high": 1, "medium_high": 2, "medium": 3}.get(row["expected_information_gain"], 9),
        {"high": 1, "medium": 2, "low": 3}.get(row["boundary_ambiguity"], 9),
    ))
    return rows


def summary_sheet(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": "",
            "agreement_yes_no": "",
            "disagreement_type": "",
            "confidence": "",
            "notes": "",
        }
        for row in rows
    ]


def merge_plan() -> List[Dict[str, str]]:
    return [
        {
            "step": "1",
            "source_files": "analysis/validation/historical_foundational_adjudication_workbook.csv; analysis/validation/historical_foundational_packet_A.csv; analysis/validation/historical_foundational_packet_B.csv; analysis/validation/historical_foundational_packet_C.csv",
            "merge_keys": "context_group_id",
            "expected_outputs": "completed human labels for 22 historical/foundational boundary rows",
            "agreement_calculations": "Compare router_primary_role with human_primary_role; set agreement_yes_no; classify disagreement_type as false_historical, false_foundational, unclear_or_context_problem, or other.",
            "validation_updates": "Update historical_foundational_adjudication_summary.csv after human coding; do not overwrite router outputs.",
        },
        {
            "step": "2",
            "source_files": "analysis/validation/historical_foundational_adjudication_summary.csv",
            "merge_keys": "context_group_id",
            "expected_outputs": "post-review agreement and boundary-error counts",
            "agreement_calculations": "Aggregate agreement_yes_no and disagreement_type after human fields are complete.",
            "validation_updates": "Update validation coverage counts only after review_status indicates completed.",
        },
    ]


def validate(rows: List[Dict[str, Any]]) -> None:
    if len(rows) != 22:
        raise ValueError(f"Expected 22 workbook rows, found {len(rows)}")
    ids = [row["context_group_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Workbook context_group_id values are not unique")
    for row in rows:
        for field in HUMAN_FIELDS:
            if row.get(field, "") != "":
                raise ValueError(f"Human field {field} was not blank for {row['context_group_id']}")


def main() -> None:
    rows = load_workbook_rows()
    validate(rows)
    write_csv(VALIDATION / "historical_foundational_adjudication_workbook.csv", rows)
    packet_a = [row for row in rows if row["boundary_ambiguity"] == "high"]
    packet_b = [row for row in rows if row["boundary_ambiguity"] == "medium"]
    packet_c = [row for row in rows if row["boundary_ambiguity"] not in {"high", "medium"}]
    write_csv(VALIDATION / "historical_foundational_packet_A.csv", packet_a)
    write_csv(VALIDATION / "historical_foundational_packet_B.csv", packet_b)
    write_csv(VALIDATION / "historical_foundational_packet_C.csv", packet_c)
    write_csv(VALIDATION / "historical_foundational_adjudication_summary.csv", summary_sheet(rows))
    write_csv(TABLES / "historical_foundational_post_review_merge_plan.csv", merge_plan())
    print(f"Workbook rows: {len(rows)}")
    print(f"Packet A rows: {len(packet_a)}")
    print(f"Packet B rows: {len(packet_b)}")
    print(f"Packet C rows: {len(packet_c)}")


if __name__ == "__main__":
    main()
