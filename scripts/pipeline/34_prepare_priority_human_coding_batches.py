#!/usr/bin/env python3
"""Create priority human-coding batches from existing validation worklists.

No judgments are filled here. The outputs are reviewer-ready CSVs with a
shared schema and blank human-coding fields.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"


BATCH_FIELDS = [
    "source_file",
    "review_batch",
    "review_priority",
    "context_group_id",
    "title",
    "year",
    "venue",
    "context_text",
    "citation_sentence",
    "sentence_before",
    "sentence_after",
    "context_window",
    "legacy_snippet",
    "router_primary_role",
    "router_stance",
    "router_topic",
    "routing_reason",
    "relevant_codebook_rule",
    "decision_question",
    "human_is_seed_work_citation",
    "human_primary_role",
    "human_topic_or_discourse_area",
    "human_stance_toward_seed",
    "human_confidence",
    "human_notes",
    "review_status",
]

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


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def blank_human_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    for field in HUMAN_FIELDS:
        row[field] = ""
    return row


def from_historical_foundational(row: Dict[str, str], source_file: str) -> Dict[str, Any]:
    return blank_human_fields({
        "source_file": source_file,
        "review_batch": "batch_1",
        "review_priority": "1_historical_foundational_consensus",
        "context_group_id": row.get("context_group_id", ""),
        "title": row.get("title", ""),
        "year": row.get("year", ""),
        "venue": "",
        "context_text": row.get("context_text", ""),
        "citation_sentence": "",
        "sentence_before": "",
        "sentence_after": "",
        "context_window": row.get("context_text", ""),
        "legacy_snippet": row.get("context_text", ""),
        "router_primary_role": row.get("router_recommendation", ""),
        "router_stance": "",
        "router_topic": "",
        "routing_reason": "historical/foundational consensus worklist",
        "relevant_codebook_rule": row.get("relevant_codebook_rule", ""),
        "decision_question": row.get("decision_question", ""),
    })


def from_router(row: Dict[str, str], source_file: str, batch: str, priority: str) -> Dict[str, Any]:
    context = row.get("context_window") or row.get("citation_sentence") or row.get("legacy_snippet", "")
    return blank_human_fields({
        "source_file": source_file,
        "review_batch": batch,
        "review_priority": priority,
        "context_group_id": row.get("context_group_id", ""),
        "title": row.get("title", ""),
        "year": row.get("year", ""),
        "venue": row.get("venue", ""),
        "context_text": context,
        "citation_sentence": row.get("citation_sentence", ""),
        "sentence_before": row.get("sentence_before", ""),
        "sentence_after": row.get("sentence_after", ""),
        "context_window": row.get("context_window", ""),
        "legacy_snippet": row.get("legacy_snippet", ""),
        "router_primary_role": row.get("router_function", ""),
        "router_stance": row.get("router_stance", ""),
        "router_topic": row.get("router_topic", ""),
        "routing_reason": row.get("routing_reason", ""),
        "relevant_codebook_rule": row.get("relevant_codebook_rule", ""),
        "decision_question": decision_question_for_router(row.get("priority_category", "")),
    })


def decision_question_for_router(category: str) -> str:
    return {
        "historical_publication_lineage": "Is the citation event historical/publication lineage, or is a substantive Meadows claim doing the work?",
        "foundational_resource_constraint_claim": "Is a substantive Meadows/LtG resource-constraint claim being used as a premise?",
        "modeling_simulation_reference": "Does the citation event itself discuss modeling, simulation, scenarios, projections, World3, or system dynamics?",
        "severe_ocr_unclear": "Is the context too damaged or ambiguous to support a substantive label?",
        "bibliography_only": "Is this true reference-list material rather than body-text publication history?",
    }.get(category, "Code the visible citation function, topic, and stance from the supplied context only.")


def from_extraction(row: Dict[str, str], source_file: str, batch: str, priority: str) -> Dict[str, Any]:
    context = row.get("repaired_context_window") or row.get("original_snippet_context", "")
    return blank_human_fields({
        "source_file": source_file,
        "review_batch": batch,
        "review_priority": priority,
        "context_group_id": row.get("context_group_id", ""),
        "title": row.get("title", ""),
        "year": row.get("year", ""),
        "venue": row.get("venue", ""),
        "context_text": context,
        "citation_sentence": row.get("repaired_citation_sentence", ""),
        "sentence_before": row.get("repaired_sentence_before", ""),
        "sentence_after": row.get("repaired_sentence_after", ""),
        "context_window": row.get("repaired_context_window", ""),
        "legacy_snippet": row.get("original_snippet_context", ""),
        "router_primary_role": "",
        "router_stance": "",
        "router_topic": "",
        "routing_reason": f"extraction recovery: {row.get('failure_mode', '')}; {row.get('expected_effect_on_classification', '')}",
        "relevant_codebook_rule": "Review repaired evidence only after confirming the context is now sufficient; preserve uncertainty for OCR, generic mentions, and bibliography/body-text ambiguity.",
        "decision_question": "Is the repaired context sufficient to code seed identification, citation function, topic, and stance?",
    })


def build_batches() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    hf_path = "analysis/tables/historical_foundational_consensus_worklist.csv"
    hist_path = "analysis/validation/router_safe_worklist_historical_lineage.csv"
    found_path = "analysis/validation/router_safe_worklist_foundational_claims.csv"
    modeling_path = "analysis/validation/router_safe_worklist_modeling.csv"
    ocr_path = "analysis/validation/router_safe_worklist_ocr_unclear.csv"
    extraction_path = "analysis/validation/extraction_recovery_review_packet.csv"

    batch1: List[Dict[str, Any]] = []
    batch1.extend(from_historical_foundational(row, hf_path) for row in read_csv(ROOT / hf_path))
    batch1.extend(from_router(row, hist_path, "batch_1", "2_historical_lineage_spotcheck") for row in read_csv(ROOT / hist_path))
    batch1.extend(from_router(row, found_path, "batch_1", "3_foundational_claim_spotcheck") for row in read_csv(ROOT / found_path))

    batch2: List[Dict[str, Any]] = []
    batch2.extend(from_router(row, modeling_path, "batch_2", "1_modeling_spotcheck") for row in read_csv(ROOT / modeling_path))
    batch2.extend(from_router(row, ocr_path, "batch_2", "2_ocr_unclear_spotcheck") for row in read_csv(ROOT / ocr_path))

    extraction_rows = read_csv(ROOT / extraction_path)
    likely_improves = [row for row in extraction_rows if row.get("expected_effect_on_classification") == "likely_improves"]
    remaining = [row for row in extraction_rows if row.get("expected_effect_on_classification") != "likely_improves"]
    batch2.extend(from_extraction(row, extraction_path, "batch_2", "3_extraction_recovery_likely_improves") for row in likely_improves)

    batch3: List[Dict[str, Any]] = []
    batch3.extend(from_extraction(row, extraction_path, "batch_3", "1_remaining_extraction_recovery") for row in remaining)

    for batch in (batch1, batch2, batch3):
        batch.sort(key=lambda row: (row["review_priority"], row.get("year", ""), row["context_group_id"], row["source_file"]))
    return batch1, batch2, batch3


def tracker(batches: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    priorities = {
        "batch_1": "highest",
        "batch_2": "high",
        "batch_3": "medium",
    }
    rows = []
    for name, batch_rows in batches.items():
        source_files = sorted(set(row["source_file"] for row in batch_rows))
        rows.append({
            "batch": name,
            "row_count": len(batch_rows),
            "source_files": " | ".join(source_files),
            "priority": priorities[name],
            "coding_status": "not_started",
            "completed_count": 0,
            "remaining_count": len(batch_rows),
            "blocker_notes": "human coding not yet entered",
        })
    return rows


def merge_template(all_rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for row in all_rows:
        key = (row["context_group_id"], row["source_file"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "context_group_id": row["context_group_id"],
            "source_file": row["source_file"],
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "review_status": "",
        })
    return out


def duplicate_context_groups(all_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = Counter(row["context_group_id"] for row in all_rows)
    rows = []
    for group_id, count in sorted(counts.items()):
        if count <= 1:
            continue
        matches = [row for row in all_rows if row["context_group_id"] == group_id]
        rows.append({
            "context_group_id": group_id,
            "occurrence_count": count,
            "batches": " | ".join(sorted(set(row["review_batch"] for row in matches))),
            "source_files": " | ".join(sorted(set(row["source_file"] for row in matches))),
            "titles": " | ".join(sorted(set(row["title"] for row in matches))),
        })
    return rows


def main() -> None:
    batch1, batch2, batch3 = build_batches()
    batches = {
        "batch_1": batch1,
        "batch_2": batch2,
        "batch_3": batch3,
    }
    write_csv(VALIDATION / "priority_human_coding_batch_1.csv", batch1, BATCH_FIELDS)
    write_csv(VALIDATION / "priority_human_coding_batch_2.csv", batch2, BATCH_FIELDS)
    write_csv(VALIDATION / "priority_human_coding_batch_3.csv", batch3, BATCH_FIELDS)
    write_csv(TABLES / "human_coding_execution_tracker.csv", tracker(batches))
    all_rows = batch1 + batch2 + batch3
    write_csv(VALIDATION / "human_coding_merge_template.csv", merge_template(all_rows))
    write_csv(TABLES / "human_coding_duplicate_context_groups.csv", duplicate_context_groups(all_rows))

    print(f"Batch 1 rows: {len(batch1)}")
    print(f"Batch 2 rows: {len(batch2)}")
    print(f"Batch 3 rows: {len(batch3)}")
    print(f"Duplicate context groups: {len(duplicate_context_groups(all_rows))}")


if __name__ == "__main__":
    main()
