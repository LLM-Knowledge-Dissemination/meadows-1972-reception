#!/usr/bin/env python3
"""Prepare reviewer packets and extraction-recovery execution tables.

No LLM calls or classification scaling are performed here. The outputs are
human-review packages and before/after evidence-window estimates.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
PROCESSED = ROOT / "analysis/data/processed"


PRIORITY_ORDER = {
    "historical_publication_lineage": 1,
    "foundational_resource_constraint_claim": 2,
    "modeling_simulation_reference": 3,
    "bibliography_only": 4,
    "severe_ocr_unclear": 5,
}

CATEGORY_LABELS = {
    "clear_historical_publication_lineage": "historical_publication_lineage",
    "explicit_foundational_resource_constraint_claim": "foundational_resource_constraint_claim",
    "explicit_modeling_simulation_language": "modeling_simulation_reference",
    "true_bibliography_only": "bibliography_only",
    "severe_ocr_incoherent_unclear_human_review": "severe_ocr_unclear",
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


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def text_len(text: str) -> int:
    return len(clean_text(text))


def split_sentences(text: str) -> List[str]:
    text = clean_text(text)
    if not text:
        return []
    protected = (
        text.replace("et al.", "et al<prd>")
        .replace("e.g.", "e<prd>g<prd>")
        .replace("i.e.", "i<prd>e<prd>")
    )
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [part.replace("<prd>", ".").strip() for part in parts if part.strip()]


def find_citation_sentence(sentences: List[str]) -> Tuple[str, str, str]:
    if not sentences:
        return "", "", ""
    pattern = re.compile(r"meadows|limits to growth|club of rome|world3|world 3|1972", re.I)
    index = next((idx for idx, sentence in enumerate(sentences) if pattern.search(sentence)), 0)
    before = sentences[index - 1] if index > 0 else ""
    sentence = sentences[index]
    after = sentences[index + 1] if index + 1 < len(sentences) else ""
    return before, sentence, after


def codebook_rule(category: str) -> str:
    return {
        "bibliography_only": "Require actual reference-list material; body-text publication history is historical framing, not bibliography-only.",
        "modeling_simulation_reference": "Prefer modeling when the citation event explicitly discusses World3, system dynamics, simulations, scenarios, forecasts, projections, assumptions, feedback, sensitivity, or model performance.",
        "foundational_resource_constraint_claim": "Code foundational when a visible Meadows/LtG claim about resource constraints or growth limits is used as a substantive premise.",
        "historical_publication_lineage": "Code historical framing when the citation marks chronology, influence, adoption, publication history, or intellectual lineage rather than a substantive claim.",
        "severe_ocr_unclear": "Use unclear with human review when OCR damage or missing context prevents reliable function or stance coding.",
    }.get(category, "Use the three-dimension coding model and exact visible evidence.")


def router_evidence(row: Dict[str, str]) -> str:
    category = CATEGORY_LABELS.get(row.get("stratum_category", ""), row.get("stratum_category", ""))
    if category == "bibliography_only":
        return row.get("legacy_snippet") or row.get("context_window") or row.get("citation_sentence", "")
    return row.get("citation_sentence") or row.get("context_window") or row.get("legacy_snippet", "")


def router_safe_packets() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    spot = read_csv(VALIDATION / "router_safe_spotcheck_sample.csv")
    plan = {row["category"]: row for row in read_csv(TABLES / "router_safe_validation_plan.csv")}
    packet: List[Dict[str, Any]] = []
    for row in spot:
        category = CATEGORY_LABELS.get(row.get("stratum_category", ""), row.get("stratum_category", ""))
        packet.append({
            "review_priority_order": PRIORITY_ORDER.get(category, 99),
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "priority_category": category,
            "router_category": row.get("stratum_category", ""),
            "router_function": row.get("router_citation_function", ""),
            "router_topic": row.get("router_topic_or_discourse_area", ""),
            "router_stance": row.get("router_stance_toward_seed", ""),
            "routing_reason": row.get("routing_reason", ""),
            "rule_hits": row.get("rule_hits", ""),
            "citation_sentence": row.get("citation_sentence", ""),
            "sentence_before": row.get("sentence_before", ""),
            "sentence_after": row.get("sentence_after", ""),
            "context_window": row.get("context_window", ""),
            "legacy_snippet": row.get("legacy_snippet", ""),
            "bibliography_ocr_extraction_flags": " | ".join(
                part for part in [
                    "bibliography_detected" if str(row.get("bibliography_detected", "")).lower() == "true" else "",
                    row.get("ocr_or_bibliography_flags", ""),
                    f"citation_section={row.get('citation_section', '')}" if row.get("citation_section") else "",
                    f"extraction_confidence={row.get('extraction_confidence', '')}" if row.get("extraction_confidence") else "",
                ] if part
            ),
            "exact_evidence_used_by_router": router_evidence(row),
            "relevant_codebook_decision_rule": codebook_rule(category),
            "validation_plan_risk_level": plan.get(category, {}).get("estimated_risk_level", ""),
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "spotcheck_result": "",
            "spotcheck_issue_type": "",
        })
    packet.sort(key=lambda row: (row["review_priority_order"], row["year"], row["context_group_id"]))
    adjudication = [dict(row) for row in packet]
    progress = []
    counts = Counter(row["priority_category"] for row in packet)
    for category in sorted(PRIORITY_ORDER, key=PRIORITY_ORDER.get):
        rows = [row for row in packet if row["priority_category"] == category]
        progress.append({
            "category": category,
            "rows_prepared": counts[category],
            "human_coded_rows": sum(1 for row in rows if present(row.get("human_primary_role"))),
            "human_fields_ready": "yes",
            "review_priority_order": PRIORITY_ORDER[category],
            "remaining_action": "human-code reviewer packet rows",
        })
    return packet, adjudication, progress


def historical_foundational_packets() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    casebook = read_csv(TABLES / "historical_foundational_casebook.csv")
    assessment = read_csv(TABLES / "historical_foundational_rule_assessment.csv")
    rule_note = "; ".join(f"{row.get('question')}: {row.get('answer')}" for row in assessment)
    packet = []
    for row in casebook:
        packet.append({
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "context_text": row.get("context_text", ""),
            "router_recommendation": row.get("router_recommendation", ""),
            "prior_recommendation": row.get("human_recommendation", ""),
            "human_label_if_available": row.get("human_recommendation", ""),
            "relevant_codebook_rule": "Historical framing marks chronology, influence, adoption, publication history, or lineage; foundational citation uses a substantive Meadows/LtG claim as a premise.",
            "resource_constraint_language_present": row.get("resource_constraint_language_present", ""),
            "publication_lineage_language_present": row.get("publication_lineage_language_present", ""),
            "chronology_language_present": row.get("chronology_language_present", ""),
            "substantive_premise_present": row.get("substantive_premise_present", ""),
            "risk_of_overfitting": row.get("risk_of_overfitting", ""),
            "rule_assessment_summary": rule_note,
            "consensus_primary_role": "",
            "consensus_stance_toward_seed": "",
            "consensus_confidence": "",
            "consensus_notes": "",
            "consensus_rule_implication": "",
        })
    consensus = [
        {
            "review_item": "historical_foundational_boundary_cases",
            "rows_prepared": len(packet),
            "consensus_completed_rows": 0,
            "new_router_rule_applied": "no",
            "current_rule_assessment": "not justified yet",
            "next_action": "complete consensus fields in adjudication packet",
        }
    ]
    return packet, consensus


def evidence_quality(citation: str, before: str, after: str, window: str, ocr: bool) -> str:
    if not present(window) and not present(citation):
        return "source_missing"
    if ocr:
        return "low_ocr_risk"
    if present(citation) and (present(before) or present(after)):
        return "high"
    if present(citation) or text_len(window) >= 180:
        return "medium"
    return "low_short_context"


def repair_context(row: Dict[str, str]) -> Dict[str, Any]:
    original = (
        row.get("context_text")
        or row.get("context_window")
        or " ".join(
            part
            for part in [
                row.get("sentence_before", ""),
                row.get("citation_sentence", ""),
                row.get("sentence_after", ""),
                row.get("legacy_snippet", ""),
            ]
            if present(part)
        )
    )
    cleaned = clean_text(original)
    sentences = split_sentences(original)
    before, citation, after = find_citation_sentence(sentences)
    original_citation = row.get("citation_sentence", "")
    original_before = row.get("sentence_before", "")
    original_after = row.get("sentence_after", "")
    original_window = row.get("context_window") or row.get("context_text", "")
    repaired_citation = citation if citation and not present(original_citation) else original_citation
    repaired_before = before if before and not present(original_before) else original_before
    repaired_after = after if after and not present(original_after) else original_after
    repaired_window = " ".join(part for part in [repaired_before, repaired_citation, repaired_after] if present(part)) or cleaned
    ocr = str(row.get("ocr_indicators", "")).lower() == "true"
    generic = str(row.get("generic_title_mention", "")).lower() == "true" or str(row.get("generic_limits_to_growth_mention", "")).lower() == "true"

    if not present(original):
        status = "source_missing"
        method = "no source context available"
    elif present(repaired_citation) and (present(repaired_before) or present(repaired_after)):
        status = "recovered"
        method = "sentence split from available raw context"
    elif present(repaired_citation) or text_len(repaired_window) >= 160:
        status = "partially_recovered"
        method = "partial sentence reconstruction from available raw context"
    else:
        status = "not_recoverable"
        method = "available context remains too short or incoherent"

    before_quality = evidence_quality(original_citation, original_before, original_after, original_window, ocr)
    after_quality = evidence_quality(repaired_citation, repaired_before, repaired_after, repaired_window, ocr)
    effect = "likely_improves" if quality_rank(after_quality) > quality_rank(before_quality) else "no_change"
    if status in {"source_missing", "not_recoverable"}:
        effect = "unknown" if status == "source_missing" else "no_change"
    if generic and status != "source_missing":
        effect = "likely_improves" if effect == "no_change" else effect

    return {
        "context_group_id": row.get("context_group_id", ""),
        "title": row.get("title", ""),
        "year": row.get("year", ""),
        "failure_mode": row.get("failure_mode", ""),
        "original_snippet_context": original,
        "original_citation_sentence": original_citation,
        "original_sentence_before": original_before,
        "original_sentence_after": original_after,
        "original_context_window": original_window,
        "repaired_citation_sentence": repaired_citation,
        "repaired_sentence_before": repaired_before,
        "repaired_sentence_after": repaired_after,
        "repaired_context_window": repaired_window,
        "raw_ocr_text_preserved": original,
        "cleaned_display_text": cleaned,
        "recovery_method": method,
        "recoverability_status": status,
        "evidence_quality_before": before_quality,
        "evidence_quality_after": after_quality,
        "expected_effect_on_classification": effect,
        "needs_human_review_after_repair": "true",
        "notes": repair_notes(row, status, generic, ocr),
    }


def quality_rank(value: str) -> int:
    return {
        "source_missing": 0,
        "low_short_context": 1,
        "low_ocr_risk": 1,
        "medium": 2,
        "high": 3,
    }.get(value, 0)


def repair_notes(row: Dict[str, str], status: str, generic: bool, ocr: bool) -> str:
    notes = [f"status={status}"]
    if ocr:
        notes.append("OCR risk remains; raw text preserved")
    if generic:
        notes.append("seed-identification check required")
    if str(row.get("bibliography_indicators", "")).lower() == "true":
        notes.append("bibliography/body-text ambiguity check required")
    return "; ".join(notes)


def extraction_recovery_tables() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    recovery = read_csv(PROCESSED / "extraction_recovery_dataset.csv")
    gray_by_id = {row.get("context_group_id", ""): row for row in read_csv(TABLES / "gray_zone_analysis.csv")}
    enriched_recovery = []
    for row in recovery:
        source = gray_by_id.get(row.get("context_group_id", ""), {})
        merged = dict(source)
        merged.update(row)
        if source:
            merged.setdefault("context_window", source.get("context_window", ""))
            merged.setdefault("citation_sentence", source.get("citation_sentence", ""))
            merged.setdefault("sentence_before", source.get("sentence_before", ""))
            merged.setdefault("sentence_after", source.get("sentence_after", ""))
            merged.setdefault("legacy_snippet", source.get("legacy_snippet", ""))
        enriched_recovery.append(merged)
    repaired = [repair_context(row) for row in enriched_recovery]
    before_after = []
    for row in repaired:
        before_after.append({
            "context_group_id": row["context_group_id"],
            "failure_mode": row["failure_mode"],
            "context_length_before": text_len(row["original_context_window"]),
            "context_length_after": text_len(row["repaired_context_window"]),
            "citation_sentence_before_present": str(present(row["original_citation_sentence"])).lower(),
            "citation_sentence_after_present": str(present(row["repaired_citation_sentence"])).lower(),
            "adjacent_sentence_before_present": str(present(row["original_sentence_before"]) or present(row["original_sentence_after"])).lower(),
            "adjacent_sentence_after_present": str(present(row["repaired_sentence_before"]) or present(row["repaired_sentence_after"])).lower(),
            "evidence_quality_before": row["evidence_quality_before"],
            "evidence_quality_after": row["evidence_quality_after"],
            "recoverability_status": row["recoverability_status"],
            "expected_effect_on_classification": row["expected_effect_on_classification"],
        })
    counts = Counter(row["recoverability_status"] for row in repaired)
    effect_counts = Counter(row["expected_effect_on_classification"] for row in repaired)
    estimates = [
        {
            "metric": "extraction_recovery_rows_processed",
            "value": len(repaired),
            "note": "No classification rerun performed.",
        },
        *[
            {"metric": f"recoverability_status_{status}", "value": count, "note": ""}
            for status, count in sorted(counts.items())
        ],
        *[
            {"metric": f"expected_effect_{effect}", "value": count, "note": "Effect estimate is evidence-quality only."}
            for effect, count in sorted(effect_counts.items())
        ],
        {
            "metric": "human_review_required_after_repair",
            "value": sum(1 for row in repaired if row["needs_human_review_after_repair"] == "true"),
            "note": "All repaired rows require human review before any classification rerun.",
        },
    ]
    return repaired, before_after, estimates


def progress_summary(
    router_packet: List[Dict[str, Any]],
    hf_packet: List[Dict[str, Any]],
    repaired: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    statuses = Counter(row["recoverability_status"] for row in repaired)
    return [
        {"metric": "router_safe_rows_prepared", "value": len(router_packet), "remaining_blockers": "human coding not yet entered"},
        {"metric": "historical_foundational_rows_prepared", "value": len(hf_packet), "remaining_blockers": "consensus fields blank"},
        {"metric": "extraction_recovery_rows_processed", "value": len(repaired), "remaining_blockers": "manual review required after repair"},
        {"metric": "extraction_rows_recovered", "value": statuses.get("recovered", 0), "remaining_blockers": ""},
        {"metric": "extraction_rows_partially_recovered", "value": statuses.get("partially_recovered", 0), "remaining_blockers": ""},
        {"metric": "extraction_rows_not_recoverable", "value": statuses.get("not_recoverable", 0), "remaining_blockers": ""},
        {"metric": "extraction_rows_source_missing", "value": statuses.get("source_missing", 0), "remaining_blockers": ""},
        {"metric": "human_coding_fields_ready", "value": "yes", "remaining_blockers": "human adjudication not completed"},
    ]


def main() -> None:
    router_packet, router_sheet, router_progress = router_safe_packets()
    write_csv(VALIDATION / "router_safe_spotcheck_reviewer_packet.csv", router_packet)
    write_csv(VALIDATION / "router_safe_spotcheck_adjudication_sheet.csv", router_sheet)
    write_csv(TABLES / "router_safe_spotcheck_progress.csv", router_progress)

    hf_packet, hf_consensus = historical_foundational_packets()
    write_csv(VALIDATION / "historical_foundational_adjudication_packet.csv", hf_packet)
    write_csv(TABLES / "historical_foundational_consensus_review.csv", hf_consensus)

    repaired, before_after, estimates = extraction_recovery_tables()
    write_csv(PROCESSED / "extraction_recovery_repaired.csv", repaired)
    write_csv(TABLES / "extraction_recovery_before_after.csv", before_after)
    write_csv(TABLES / "extraction_recovery_effect_estimates.csv", estimates)
    write_csv(TABLES / "execution_phase_progress_summary.csv", progress_summary(router_packet, hf_packet, repaired))

    print(f"Router-safe reviewer packet rows: {len(router_packet)}")
    print(f"Historical/foundational packet rows: {len(hf_packet)}")
    print(f"Extraction recovery processed rows: {len(repaired)}")
    print("Recovery statuses: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(row['recoverability_status'] for row in repaired).items())))


if __name__ == "__main__":
    main()
