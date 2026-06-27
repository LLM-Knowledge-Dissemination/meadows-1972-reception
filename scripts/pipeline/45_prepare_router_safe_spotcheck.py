#!/usr/bin/env python3
"""Prepare router-safe spot-check master packet and validation scaffolds."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
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

REVIEW_QUESTION = "Does the human-coded citation function, topic, and stance match the router-safe classification?"


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


def canonical_stratum(row: Dict[str, str]) -> str:
    role = row.get("router_function", "")
    category = row.get("priority_category", "")
    if role == "bibliographic_only":
        return "bibliography_only"
    if role == "historical_framing":
        return "historical_framing"
    if role == "foundational_citation":
        return "foundational_citation"
    if role == "modeling_simulation_reference":
        return "modeling_simulation_reference"
    if role == "bibliography_only":
        return "bibliography_only"
    if role == "unclear" or "ocr" in category.lower():
        return "unclear/OCR"
    return role or "unclear/OCR"


def info_gain_score(row: Dict[str, str]) -> int:
    score = 0
    risk = row.get("validation_plan_risk_level", "").lower()
    flags = row.get("bibliography_ocr_extraction_flags", "").lower()
    category = row.get("priority_category", "").lower()
    if risk == "high":
        score += 30
    elif risk == "medium":
        score += 20
    elif risk == "low":
        score += 10
    if "low_extraction_confidence" in flags:
        score += 8
    if "ocr" in flags or "ocr" in category:
        score += 8
    if canonical_stratum(row) in {"bibliography_only", "unclear/OCR"}:
        score += 6
    try:
        score += max(0, 10 - int(float(row.get("review_priority_order", "10"))))
    except ValueError:
        pass
    return score


def master_packet() -> List[Dict[str, Any]]:
    reviewer = read_csv(VALIDATION / "router_safe_spotcheck_reviewer_packet.csv")
    adjudication = read_csv(VALIDATION / "router_safe_spotcheck_adjudication_sheet.csv")
    if len(reviewer) != 95:
        raise ValueError(f"Expected 95 router-safe reviewer rows, found {len(reviewer)}")
    reviewer_ids = [row.get("context_group_id", "") for row in reviewer]
    adjudication_ids = [row.get("context_group_id", "") for row in adjudication]
    if reviewer_ids != adjudication_ids:
        raise ValueError("Reviewer and adjudication packet context IDs do not align")

    rows: List[Dict[str, Any]] = []
    for row in reviewer:
        out: Dict[str, Any] = {
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "citation_sentence": row.get("citation_sentence", ""),
            "sentence_before": row.get("sentence_before", ""),
            "sentence_after": row.get("sentence_after", ""),
            "context_window": row.get("context_window", ""),
            "router_primary_role": row.get("router_function", ""),
            "router_topic": row.get("router_topic", ""),
            "router_stance": row.get("router_stance", ""),
            "routing_reason": row.get("routing_reason", ""),
            "rule_hits": row.get("rule_hits", ""),
            "confidence": row.get("validation_plan_risk_level", ""),
            "review_question": REVIEW_QUESTION,
            "stratum": canonical_stratum(row),
            "review_priority_order": row.get("review_priority_order", ""),
            "priority_category": row.get("priority_category", ""),
            "information_gain_score": info_gain_score(row),
        }
        for field in HUMAN_FIELDS:
            out[field] = ""
        rows.append(out)

    ids = [row["context_group_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate context_group_id values in router-safe master packet")
    for row in rows:
        for field in HUMAN_FIELDS:
            if row[field] != "":
                raise ValueError(f"Human field {field} was not blank for {row['context_group_id']}")
    return rows


def strata_summary(rows: List[Dict[str, Any]]) -> None:
    counts = Counter(row["stratum"] for row in rows)
    order = [
        "historical_framing",
        "foundational_citation",
        "modeling_simulation_reference",
        "bibliography_only",
        "unclear/OCR",
    ]
    out = []
    for stratum in order:
        out.append({"stratum": stratum, "row_count": counts[stratum]})
    write_csv(TABLES / "router_safe_strata_summary.csv", out)


def create_batches(rows: List[Dict[str, Any]]) -> None:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["stratum"]].append(row)
    for group_rows in groups.values():
        group_rows.sort(key=lambda item: (-int(item["information_gain_score"]), item["year"], item["context_group_id"]))

    order = [
        "historical_framing",
        "foundational_citation",
        "modeling_simulation_reference",
        "bibliography_only",
        "unclear/OCR",
    ]
    interleaved: List[Dict[str, Any]] = []
    while any(groups[stratum] for stratum in order):
        for stratum in order:
            if groups[stratum]:
                interleaved.append(groups[stratum].pop(0))

    batch_sizes = {"A": 24, "B": 24, "C": 24, "D": len(interleaved) - 72}
    start = 0
    for label, size in batch_sizes.items():
        packet = []
        for index, row in enumerate(interleaved[start:start + size], 1):
            out = dict(row)
            out["review_batch"] = f"Batch {label}"
            out["batch_row_number"] = index
            packet.append(out)
        write_csv(VALIDATION / f"router_safe_batch_{label}.csv", packet)
        start += size


def write_agreement_framework() -> None:
    rows = [
        {"metric": "agreement_rate", "definition": "Share of reviewed rows where human_primary_role equals router_primary_role.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "disagreement_rate", "definition": "Share of reviewed rows where human_primary_role differs from router_primary_role.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "false_historical", "definition": "Router historical_framing but human role is not historical_framing.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "false_foundational", "definition": "Router foundational_citation but human role is not foundational_citation.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "false_modeling", "definition": "Router modeling_simulation_reference but human role is not modeling_simulation_reference.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "false_bibliography", "definition": "Router bibliography_only but human role is not bibliography_only.", "calculation_status": "future_metric_no_calculation_yet"},
        {"metric": "false_unclear", "definition": "Router unclear/OCR but human role is not unclear.", "calculation_status": "future_metric_no_calculation_yet"},
    ]
    write_csv(TABLES / "router_safe_agreement_framework.csv", rows)


def write_status(rows: List[Dict[str, Any]]) -> None:
    progress = read_csv(TABLES / "validation_progress_after_modeling.csv")
    current_validated = progress[0].get("total_validated_rows", "87") if progress else "87"
    extraction_progress = "prepared_for_review"
    rows_out = [{
        "total_validated_rows": current_validated,
        "extraction_review_progress": extraction_progress,
        "router_safe_rows_remaining": len(rows),
        "bibliography_rows_remaining": sum(1 for row in rows if row["stratum"] == "bibliography_only"),
        "OCR_rows_remaining": sum(1 for row in rows if row["stratum"] == "unclear/OCR"),
        "validation_maturity_assessment": "nearly_validation_complete",
        "conservative_note": "Router-safe spot-check and extraction-recovery review remain before a validation freeze.",
    }]
    write_csv(TABLES / "pre_final_validation_status.csv", rows_out)


def main() -> None:
    rows = master_packet()
    write_csv(VALIDATION / "router_safe_spotcheck_master_packet.csv", rows)
    strata_summary(rows)
    create_batches(rows)
    write_agreement_framework()
    write_status(rows)
    counts = Counter(row["stratum"] for row in rows)
    print(f"Router-safe spot-check rows: {len(rows)}")
    print("Strata: " + ", ".join(f"{key}={counts[key]}" for key in sorted(counts)))


if __name__ == "__main__":
    main()
