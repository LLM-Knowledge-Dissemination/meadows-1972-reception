#!/usr/bin/env python3
"""Prepare extraction-recovery validation dataset and review packets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"
PROCESSED = ROOT / "analysis/data/processed"

HUMAN_FIELDS = [
    "human_recovery_helpful",
    "human_recovery_changed_interpretation",
    "human_recovery_increased_confidence",
    "human_recovery_reduced_uncertainty",
    "human_notes",
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


def csv_ids(paths: Iterable[Path]) -> Set[str]:
    ids: Set[str] = set()
    for path in paths:
        for row in read_csv(path):
            value = row.get("context_group_id", "").strip()
            if value:
                ids.add(value)
    return ids


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "1"}


def present(value: Any) -> bool:
    return bool(str(value or "").strip())


def lookup(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    return {row.get("context_group_id", ""): row for row in rows if row.get("context_group_id", "")}


def likely_improves(row: Dict[str, str]) -> bool:
    return row.get("expected_effect_on_classification", "") == "likely_improves"


def no_change(row: Dict[str, str]) -> bool:
    return row.get("expected_effect_on_classification", "") == "no_change"


def is_historical_foundational_ambiguity(row: Dict[str, str]) -> bool:
    text = " ".join([
        row.get("failure_mode", ""),
        row.get("original_context", ""),
        row.get("repaired_context", ""),
    ]).lower()
    return "historical_vs_foundational" in text or ("historical" in text and "foundational" in text)


def is_modeling_ambiguity(row: Dict[str, str]) -> bool:
    text = " ".join([
        row.get("failure_mode", ""),
        row.get("original_context", ""),
        row.get("repaired_context", ""),
    ]).lower()
    terms = ("world3", "world 3", "system dynamics", "simulation", "model", "scenario", "projection", "forecast")
    return any(term in text for term in terms)


def quality_score(value: str) -> int:
    ranks = {
        "high": 3,
        "medium_high": 3,
        "medium": 2,
        "low_short_context": 1,
        "low": 1,
    }
    return ranks.get(str(value or "").strip().lower(), 0)


def priority_score(row: Dict[str, str]) -> int:
    score = 0
    if truthy(row.get("expected_likely_improvement", "")):
        score += 100
    if truthy(row.get("previous_gray_zone_membership", "")):
        score += 30
    if truthy(row.get("historical_foundational_ambiguity", "")):
        score += 20
    if truthy(row.get("modeling_ambiguity", "")):
        score += 15
    if row.get("recovery_status") == "recovered":
        score += 5
    score += max(0, quality_score(row.get("evidence_quality_after", "")) - quality_score(row.get("evidence_quality_before", "")))
    return score


def build_dataset() -> List[Dict[str, Any]]:
    review_packet = read_csv(VALIDATION / "extraction_recovery_review_packet.csv")
    repaired = lookup(read_csv(PROCESSED / "extraction_recovery_repaired.csv"))
    before_after = lookup(read_csv(TABLES / "extraction_recovery_before_after.csv"))
    gray_zone_ids = csv_ids([
        TABLES / "gray_zone_case_review_packet.csv",
        TABLES / "gray_zone_analysis.csv",
    ])

    rows: List[Dict[str, Any]] = []
    for packet_row in review_packet:
        context_id = packet_row.get("context_group_id", "")
        repaired_row = repaired.get(context_id, {})
        before_row = before_after.get(context_id, {})

        original_context = (
            repaired_row.get("original_context_window")
            or packet_row.get("original_snippet_context")
            or repaired_row.get("original_snippet_context")
        )
        original_sentence = (
            repaired_row.get("original_citation_sentence")
            or packet_row.get("original_citation_sentence")
        )
        original_surrounding = " ".join(
            part for part in [
                repaired_row.get("original_sentence_before") or packet_row.get("original_sentence_before"),
                original_sentence,
                repaired_row.get("original_sentence_after") or packet_row.get("original_sentence_after"),
            ]
            if present(part)
        )

        repaired_context = (
            repaired_row.get("repaired_context_window")
            or packet_row.get("repaired_context_window")
        )
        repaired_sentence = (
            repaired_row.get("repaired_citation_sentence")
            or packet_row.get("repaired_citation_sentence")
        )
        repaired_surrounding = " ".join(
            part for part in [
                repaired_row.get("repaired_sentence_before") or packet_row.get("repaired_sentence_before"),
                repaired_sentence,
                repaired_row.get("repaired_sentence_after") or packet_row.get("repaired_sentence_after"),
            ]
            if present(part)
        )

        row: Dict[str, Any] = {
            "context_group_id": context_id,
            "title": packet_row.get("title") or repaired_row.get("title", ""),
            "year": packet_row.get("year") or repaired_row.get("year", ""),
            "venue": packet_row.get("venue") or repaired_row.get("venue", ""),
            "failure_mode": packet_row.get("failure_mode") or repaired_row.get("failure_mode", ""),
            "original_context": original_context,
            "original_citation_sentence": original_sentence,
            "original_surrounding_text": original_surrounding,
            "repaired_context": repaired_context,
            "repaired_citation_sentence": repaired_sentence,
            "repaired_surrounding_text": repaired_surrounding,
            "recovery_status": packet_row.get("recoverability_status") or repaired_row.get("recoverability_status", ""),
            "expected_likely_improvement": str(likely_improves(packet_row) or likely_improves(repaired_row)).lower(),
            "expected_no_change": str(no_change(packet_row) or no_change(repaired_row)).lower(),
            "original_citation_present": str(present(original_sentence) or truthy(before_row.get("citation_sentence_before_present", ""))).lower(),
            "repaired_citation_present": str(present(repaired_sentence) or truthy(before_row.get("citation_sentence_after_present", ""))).lower(),
            "repaired_adjacent_sentence_present": str(
                present(repaired_row.get("repaired_sentence_before") or packet_row.get("repaired_sentence_before"))
                or present(repaired_row.get("repaired_sentence_after") or packet_row.get("repaired_sentence_after"))
                or truthy(before_row.get("adjacent_sentence_before_present", ""))
                or truthy(before_row.get("adjacent_sentence_after_present", ""))
            ).lower(),
            "evidence_quality_before": packet_row.get("evidence_quality_before") or repaired_row.get("evidence_quality_before", ""),
            "evidence_quality_after": packet_row.get("evidence_quality_after") or repaired_row.get("evidence_quality_after", ""),
            "needs_human_review_after_repair": packet_row.get("needs_human_review_after_repair") or repaired_row.get("needs_human_review_after_repair", ""),
            "previous_gray_zone_membership": str(context_id in gray_zone_ids).lower(),
        }
        row["historical_foundational_ambiguity"] = str(is_historical_foundational_ambiguity(row)).lower()
        row["modeling_ambiguity"] = str(is_modeling_ambiguity(row)).lower()
        row["priority_score"] = priority_score(row)
        for field in HUMAN_FIELDS:
            row[field] = ""
        rows.append(row)

    rows.sort(key=lambda item: (-int(item["priority_score"]), item["context_group_id"]))
    for index, row in enumerate(rows, 1):
        row["review_order"] = index
    return rows


def write_packets(rows: List[Dict[str, Any]]) -> None:
    packet_sizes = [16, 17, len(rows) - 33]
    start = 0
    for label, size in zip(("A", "B", "C"), packet_sizes):
        packet = []
        for row in rows[start:start + size]:
            out = dict(row)
            out["review_packet"] = f"Packet {label}"
            packet.append(out)
        write_csv(VALIDATION / f"extraction_recovery_packet_{label}.csv", packet)
        start += size


def write_guidance() -> None:
    text = """# Extraction-Recovery Review Guidance

Use this review to judge whether recovery improves human interpretation of citation contexts.

Review questions:

1. Did recovery make the citation understandable?
2. Did recovery reveal the actual citation function?
3. Did recovery increase coding confidence?
4. Did recovery reduce ambiguity?
5. Would you have coded the citation differently after recovery?

Focus on:

- Interpretive gain
- Confidence gain
- Ambiguity reduction

Do not evaluate classifier performance in this sheet. Leave model or router behavior aside unless it helps explain why recovery matters for later human coding.
"""
    (VALIDATION / "extraction_recovery_review_guidance.md").write_text(text, encoding="utf-8")


def write_framework() -> None:
    rows = [
        {
            "outcome": "strong_improvement",
            "definition": "Function becomes identifiable, ambiguity is removed, and confidence materially increases.",
            "human_review_implication": "Mark recovery helpful, changed interpretation if applicable, increased confidence, and reduced uncertainty.",
            "scoring_status": "framework_only_no_scoring_yet",
        },
        {
            "outcome": "moderate_improvement",
            "definition": "Context is clearer and confidence improves, but final coding stays the same.",
            "human_review_implication": "Mark recovery helpful and increased confidence; changed interpretation may remain no.",
            "scoring_status": "framework_only_no_scoring_yet",
        },
        {
            "outcome": "minimal_improvement",
            "definition": "Readability improves, but coding and confidence are mostly unchanged.",
            "human_review_implication": "Mark recovery helpful only if the clearer text aids review.",
            "scoring_status": "framework_only_no_scoring_yet",
        },
        {
            "outcome": "no_improvement",
            "definition": "Interpretation is unchanged.",
            "human_review_implication": "Mark recovery not helpful unless there is a minor readability benefit worth noting.",
            "scoring_status": "framework_only_no_scoring_yet",
        },
        {
            "outcome": "negative_effect",
            "definition": "Recovery introduces uncertainty or makes the citation harder to interpret.",
            "human_review_implication": "Mark recovery not helpful and explain the source of new uncertainty.",
            "scoring_status": "framework_only_no_scoring_yet",
        },
    ]
    write_csv(TABLES / "extraction_recovery_effect_framework.csv", rows)


def write_progress(rows: List[Dict[str, Any]]) -> None:
    current = read_csv(TABLES / "validation_progress_after_modeling.csv")
    current_validated = current[0]["total_validated_rows"] if current else "87"
    rows_out = [{
        "current_validated_rows": current_validated,
        "remaining_recovery_review_rows": len(rows),
        "remaining_bibliography_rows": len(read_csv(VALIDATION / "router_safe_worklist_bibliography.csv")),
        "remaining_OCR_rows": len(read_csv(VALIDATION / "router_safe_worklist_ocr_unclear.csv")),
    }]
    write_csv(TABLES / "validation_progress_before_recovery_review.csv", rows_out)


def validate(rows: List[Dict[str, Any]]) -> None:
    if len(rows) != 49:
        raise ValueError(f"Expected 49 extraction-recovery rows, found {len(rows)}")
    ids = [row["context_group_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate context_group_id values in extraction recovery validation dataset")
    for row in rows:
        for field in HUMAN_FIELDS:
            if row.get(field, "") != "":
                raise ValueError(f"Human field {field} was not blank for {row['context_group_id']}")


def main() -> None:
    rows = build_dataset()
    validate(rows)
    write_csv(TABLES / "extraction_recovery_validation_dataset.csv", rows)
    write_packets(rows)
    write_guidance()
    write_framework()
    write_progress(rows)

    status_counts: Dict[str, int] = {}
    for row in rows:
        status_counts[row["recovery_status"]] = status_counts.get(row["recovery_status"], 0) + 1
    likely = sum(1 for row in rows if row["expected_likely_improvement"] == "true")
    gray = sum(1 for row in rows if row["previous_gray_zone_membership"] == "true")
    print(f"Extraction recovery rows: {len(rows)}")
    print(f"Likely improvement rows: {likely}")
    print(f"Prior gray-zone rows: {gray}")
    print("Recovery status: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())))


if __name__ == "__main__":
    main()
