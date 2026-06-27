#!/usr/bin/env python3
"""Prepare human-review worklists from execution-phase packets.

This script does not classify contexts or create final test sets. It only
reshapes existing packets into review worklists and candidate queues.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
PROCESSED = ROOT / "analysis/data/processed"


WORKLISTS = {
    "historical_publication_lineage": VALIDATION / "router_safe_worklist_historical_lineage.csv",
    "foundational_resource_constraint_claim": VALIDATION / "router_safe_worklist_foundational_claims.csv",
    "modeling_simulation_reference": VALIDATION / "router_safe_worklist_modeling.csv",
    "bibliography_only": VALIDATION / "router_safe_worklist_bibliography.csv",
    "severe_ocr_unclear": VALIDATION / "router_safe_worklist_ocr_unclear.csv",
}

CODING_ORDER = {
    "historical_publication_lineage": 1,
    "foundational_resource_constraint_claim": 2,
    "modeling_simulation_reference": 3,
    "bibliography_only": 4,
    "severe_ocr_unclear": 5,
}

FAILURE_ORDER = {
    "short_context": 1,
    "ocr_or_text_quality": 2,
    "evidence_quote_failure": 3,
    "uncertainty_policy_failure": 4,
    "historical_vs_foundational": 5,
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


def present(value: Any) -> bool:
    return bool(str(value or "").strip())


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def relevant_evidence_phrase(text: str) -> str:
    text = clean_text(text)
    if not text:
        return ""
    pattern = re.compile(r"(.{0,90}(meadows|limits to growth|club of rome|1972|resource|growth|publication|history|landmark).{0,120})", re.I)
    match = pattern.search(text)
    return clean_text(match.group(1)) if match else text[:240]


def historical_foundational_worklist() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "historical_foundational_adjudication_packet.csv")
    out = []
    for row in rows:
        context = row.get("context_text", "")
        out.append({
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "context_text": context,
            "current_recommendation": row.get("prior_recommendation", ""),
            "router_recommendation": row.get("router_recommendation", ""),
            "prior_human_label_if_available": row.get("human_label_if_available", ""),
            "relevant_evidence_phrase": relevant_evidence_phrase(context),
            "decision_question": "Is Meadows being used as a historical landmark/lineage marker, or is a substantive Meadows claim being used as a premise?",
            "consensus_primary_role": "",
            "consensus_stance_toward_seed": "",
            "consensus_confidence": "",
            "consensus_notes": "",
            "distinction_stable_yes_no": "",
        })
    return out


def router_safe_worklists() -> tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    packet = read_csv(VALIDATION / "router_safe_spotcheck_reviewer_packet.csv")
    grouped: Dict[str, List[Dict[str, Any]]] = {category: [] for category in WORKLISTS}
    for row in packet:
        category = row.get("priority_category", "")
        if category not in grouped:
            continue
        grouped[category].append({
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "priority_category": category,
            "router_function": row.get("router_function", ""),
            "router_topic": row.get("router_topic", ""),
            "router_stance": row.get("router_stance", ""),
            "routing_reason": row.get("routing_reason", ""),
            "rule_hits": row.get("rule_hits", ""),
            "citation_sentence": row.get("citation_sentence", ""),
            "sentence_before": row.get("sentence_before", ""),
            "sentence_after": row.get("sentence_after", ""),
            "context_window": row.get("context_window", ""),
            "legacy_snippet": row.get("legacy_snippet", ""),
            "router_evidence": row.get("exact_evidence_used_by_router", ""),
            "relevant_codebook_rule": row.get("relevant_codebook_decision_rule", ""),
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "spotcheck_result": "",
            "spotcheck_issue_type": "",
        })
    summary = []
    for category in sorted(grouped, key=lambda name: CODING_ORDER.get(name, 99)):
        rows = grouped[category]
        summary.append({
            "category": category,
            "row_count": len(rows),
            "recommended_coding_order": CODING_ORDER.get(category, 99),
            "worklist_file": str(WORKLISTS[category].relative_to(ROOT)),
            "human_fields_blank": "yes",
            "ready_for_human_coding": "yes" if rows else "no",
        })
    return grouped, summary


def extraction_review_packets() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    repaired = read_csv(PROCESSED / "extraction_recovery_repaired.csv")
    out = []
    for row in repaired:
        out.append({
            "sort_likely_improves": 0 if row.get("expected_effect_on_classification") == "likely_improves" else 1,
            "sort_recovered": 0 if row.get("recoverability_status") == "recovered" else 1,
            "sort_failure_mode": FAILURE_ORDER.get(row.get("failure_mode", ""), 99),
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "failure_mode": row.get("failure_mode", ""),
            "original_snippet_context": row.get("original_snippet_context", ""),
            "original_citation_sentence": row.get("original_citation_sentence", ""),
            "original_sentence_before": row.get("original_sentence_before", ""),
            "original_sentence_after": row.get("original_sentence_after", ""),
            "repaired_citation_sentence": row.get("repaired_citation_sentence", ""),
            "repaired_sentence_before": row.get("repaired_sentence_before", ""),
            "repaired_sentence_after": row.get("repaired_sentence_after", ""),
            "repaired_context_window": row.get("repaired_context_window", ""),
            "raw_ocr_text": row.get("raw_ocr_text_preserved", ""),
            "cleaned_display_text": row.get("cleaned_display_text", ""),
            "recoverability_status": row.get("recoverability_status", ""),
            "expected_effect_on_classification": row.get("expected_effect_on_classification", ""),
            "evidence_quality_before": row.get("evidence_quality_before", ""),
            "evidence_quality_after": row.get("evidence_quality_after", ""),
            "needs_human_review_after_repair": row.get("needs_human_review_after_repair", ""),
            "recovery_quality": "",
            "evidence_now_sufficient": "",
            "ambiguity_reduced": "",
            "repaired_context_primary_role": "",
            "repaired_context_stance": "",
            "repaired_context_confidence": "",
            "reviewer_notes": "",
        })
    out.sort(key=lambda row: (row["sort_likely_improves"], row["sort_recovered"], row["sort_failure_mode"], row["year"], row["context_group_id"]))
    sheet = [dict(row) for row in out]
    return out, sheet


def quality_rank(value: str) -> int:
    return {
        "source_missing": 0,
        "low_short_context": 1,
        "low_ocr_risk": 1,
        "medium": 2,
        "high": 3,
    }.get(value, 0)


def recovered_test_candidates(review_packet: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []
    for row in review_packet:
        reasons = []
        if row.get("expected_effect_on_classification") == "likely_improves":
            reasons.append("expected_effect_likely_improves")
        if row.get("recoverability_status") == "recovered":
            reasons.append("recoverability_status_recovered")
        if present(row.get("repaired_citation_sentence")):
            reasons.append("repaired_citation_sentence_present")
        if present(row.get("repaired_sentence_before")) or present(row.get("repaired_sentence_after")):
            reasons.append("repaired_adjacent_sentence_present")
        if quality_rank(row.get("evidence_quality_after", "")) > quality_rank(row.get("evidence_quality_before", "")):
            reasons.append("evidence_quality_improved")
        if not reasons:
            continue
        priority = candidate_priority(row, reasons)
        out = dict(row)
        out.update({
            "candidate_priority": priority,
            "reason_for_candidate_selection": " | ".join(reasons),
            "requires_human_confirmation_before_test": "true",
        })
        candidates.append(out)
    candidates.sort(key=lambda row: (row["candidate_priority"], row["sort_failure_mode"], row["context_group_id"]))
    return candidates


def candidate_priority(row: Dict[str, Any], reasons: List[str]) -> str:
    if "expected_effect_likely_improves" in reasons and "repaired_adjacent_sentence_present" in reasons:
        return "1_high"
    if "recoverability_status_recovered" in reasons:
        return "2_medium_high"
    return "3_medium"


def next_actions(
    hf: List[Dict[str, Any]],
    router_summary: List[Dict[str, Any]],
    extraction: List[Dict[str, Any]],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows = [
        action("historical_foundational_consensus", "analysis/validation/historical_foundational_adjudication_packet.csv", "analysis/tables/historical_foundational_consensus_worklist.csv", len(hf), "high", "yes", "no"),
        action("extraction_recovery_review", "analysis/data/processed/extraction_recovery_repaired.csv", "analysis/validation/extraction_recovery_review_packet.csv", len(extraction), "high", "yes", "no"),
        action("recovered_gray_zone_candidate_review", "analysis/validation/extraction_recovery_review_packet.csv", "analysis/validation/recovered_gray_zone_test_set_candidates.csv", len(candidates), "medium", "yes", "no"),
    ]
    for item in router_summary:
        rows.append(action(
            f"router_safe_{item['category']}",
            "analysis/validation/router_safe_spotcheck_reviewer_packet.csv",
            item["worklist_file"],
            item["row_count"],
            "high" if int(item["recommended_coding_order"]) <= 3 else "medium",
            "yes",
            "no",
        ))
    rows.sort(key=lambda row: ({"high": 1, "medium": 2, "low": 3}.get(row["assigned_priority"], 9), row["task"]))
    return rows


def action(task: str, input_file: str, output_file: str, row_count: int, priority: str, human: str, automation: str) -> Dict[str, Any]:
    return {
        "task": task,
        "input_file": input_file,
        "output_file": output_file,
        "row_count": row_count,
        "assigned_priority": priority,
        "requires_human_coding": human,
        "ready_for_next_automation": automation,
    }


def main() -> None:
    hf = historical_foundational_worklist()
    write_csv(TABLES / "historical_foundational_consensus_worklist.csv", hf)

    grouped, router_summary = router_safe_worklists()
    for category, rows in grouped.items():
        write_csv(WORKLISTS[category], rows)
    write_csv(TABLES / "router_safe_worklist_summary.csv", router_summary)

    extraction_packet, extraction_sheet = extraction_review_packets()
    write_csv(VALIDATION / "extraction_recovery_review_packet.csv", extraction_packet)
    write_csv(VALIDATION / "extraction_recovery_review_sheet.csv", extraction_sheet)

    candidates = recovered_test_candidates(extraction_packet)
    write_csv(VALIDATION / "recovered_gray_zone_test_set_candidates.csv", candidates)

    write_csv(TABLES / "validation_execution_next_actions.csv", next_actions(hf, router_summary, extraction_packet, candidates))

    print(f"Historical/foundational worklist rows: {len(hf)}")
    print("Router-safe worklist rows: " + ", ".join(f"{row['category']}={row['row_count']}" for row in router_summary))
    print(f"Extraction-recovery review rows: {len(extraction_packet)}")
    print(f"Recovered gray-zone candidates: {len(candidates)}")


if __name__ == "__main__":
    main()
