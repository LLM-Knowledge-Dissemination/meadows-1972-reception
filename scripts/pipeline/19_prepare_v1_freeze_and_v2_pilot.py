#!/usr/bin/env python3
"""Build boundary, context-window, and v2 pilot artifacts without running an LLM."""

from __future__ import annotations

import csv
import hashlib
import random
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"
SAMPLE = VALIDATION / "citation_context_validation_sample.csv"
BOUNDARY_REVIEW = TABLES / "historical_foundational_boundary_review.csv"
PDF_DIR = ROOT / "analysis/data/pdf"
BENCHMARK = VALIDATION / "v1_benchmark"

BENCHMARK_SOURCES = {
    "citation_context_validation_sample.csv": SAMPLE,
    "manual_adjudication_log.csv": VALIDATION / "manual_adjudication_log.csv",
    "validation_adjudication_progress.csv": TABLES / "validation_adjudication_progress.csv",
    "validation_llm_human_agreement_partial.csv": TABLES / "validation_llm_human_agreement_partial.csv",
    "validation_fallback_human_agreement_partial.csv": TABLES / "validation_fallback_human_agreement_partial.csv",
    "validation_inconsistency_flags.csv": TABLES / "validation_inconsistency_flags.csv",
    "validation_remaining_review_priorities.csv": TABLES / "validation_remaining_review_priorities.csv",
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def freeze_v1_if_missing():
    """Create the v1 snapshot once; routine reruns must never overwrite it."""
    BENCHMARK.mkdir(parents=True, exist_ok=True)
    for name, source in BENCHMARK_SOURCES.items():
        destination = BENCHMARK / name
        if destination.exists():
            continue
        if not source.exists():
            raise FileNotFoundError(f"Cannot freeze missing benchmark source: {source}")
        shutil.copy2(source, destination)

    manifest = []
    for path in sorted(BENCHMARK.glob("*.csv")):
        if path.name == "manifest_sha256.csv":
            continue
        manifest.append({
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        })
    write_csv(BENCHMARK / "manifest_sha256.csv", manifest)


def normalized_fallback(row):
    return {
        "sustainability_limits_to_growth_discourse": "sustainability_discourse",
        "background_or_ambiguous": "unclear",
        "methodological_comparison": "methods_comparison",
    }.get(row.get("rule_citation_function", ""), row.get("rule_citation_function", ""))


def boundary_type(row):
    llm, fallback = row["llm_primary_role"], normalized_fallback(row)
    if {llm, fallback} == {"historical_framing", "foundational_citation"}:
        return "historical_vs_foundational"
    if {llm, fallback} == {"historical_framing", "modeling_simulation_reference"}:
        return "historical_vs_modeling"
    if "sustainability_discourse" in {llm, fallback}:
        return "topic_sustainability_vs_function"
    if "modeling_simulation_reference" in {llm, fallback}:
        return "modeling_vs_other_function"
    return "repeated_variant_inconsistent_labels"


def reviewer_question(row):
    return {
        "historical_vs_foundational": "Does Meadows mark history/influence, or supply a substantive intellectual premise?",
        "historical_vs_modeling": "Does this citation event explicitly discuss a model/simulation/assumption, or only historical lineage?",
        "topic_sustainability_vs_function": "Is sustainability only the topic, and what rhetorical function does the citation actually perform?",
        "modeling_vs_other_function": "Is modeling visible in this citation event rather than merely elsewhere in the paper?",
        "repeated_variant_inconsistent_labels": "Should all mention variants in this context group receive one grouped citation-function label?",
    }[boundary_type(row)]


def issue_score(row):
    reason = row.get("review_reason", "")
    weights = {
        "ocr_noise": 100,
        "snippet_too_short": 95,
        "missing_surrounding_context": 90,
        "bibliography_only": 85,
        "repeated_context_different_mentions": 70,
        "fallback_llm_primary_role_disagreement": 60,
        "high_llm_confidence_with_uncertainty": 55,
        "low_extraction_confidence": 50,
    }
    return sum(weight for issue, weight in weights.items() if issue in reason)


def blank_structured_fields(row):
    copy = dict(row)
    copy.update({
        "old_snippet_clean": row["snippet_clean"],
        "sentence_before": "",
        "citation_sentence": "",
        "sentence_after": "",
        "section_heading": "",
        "context_window": "",
        "bibliography_detected": "TRUE" if row.get("citation_section") == "BIBLIO" else "FALSE",
        "bibliography_score": "",
        "extraction_issue_flags": row["review_reason"],
        "new_window_improves_review": "",
        "new_window_notes": "",
    })
    return copy


def main():
    freeze_v1_if_missing()
    rows = read_csv(SAMPLE)
    boundary_ids = {row["context_id"] for row in read_csv(BOUNDARY_REVIEW)}
    boundary_rows = [row for row in rows if row["context_id"] in boundary_ids]
    boundary_rows.sort(key=lambda row: ({"high": 0, "medium": 1, "low": 2}.get(row["review_priority"], 3), -issue_score(row), row["context_id"]))
    packet = []
    for row in boundary_rows:
        item = {
            "boundary_type": boundary_type(row),
            "review_priority": row["review_priority"],
            "review_reason": row["review_reason"],
            "context_group_id": row["context_group_id"],
            "is_repeated_context": row["is_repeated_context"],
            "mention_variant_count": row["mention_variant_count"],
            "context_id": row["context_id"],
            "title": row["title"],
            "year": row["year"],
            "venue": row["venue"],
            "snippet_clean": row["snippet_clean"],
            "context_window": row.get("context_window", ""),
            "fallback_primary_role": normalized_fallback(row),
            "llm_primary_role": row["llm_primary_role"],
            "llm_stance": row["llm_stance_toward_meadows"],
            "llm_confidence": row["llm_confidence"],
            "llm_uncertainty_flags": row["llm_uncertainty_flags"],
            "recommended_question_for_reviewer": reviewer_question(row),
            "human_primary_role": row["human_primary_role"],
            "human_discourse_category": row["human_discourse_category"],
            "human_stance_toward_seed": row["human_stance_toward_seed"],
            "human_false_positive_flag": row["human_false_positive_flag"],
            "human_confidence": row["human_confidence"],
            "human_notes": row["human_notes"],
        }
        packet.append(item)
    write_csv(VALIDATION / "boundary_case_adjudication_packet.csv", packet)

    pilot_candidates = sorted(rows, key=lambda row: (-issue_score(row), row["context_group_id"], row["context_id"]))
    selected, seen_groups = [], Counter()
    for row in pilot_candidates:
        if issue_score(row) == 0:
            continue
        if seen_groups[row["context_group_id"]] >= 2:
            continue
        selected.append(blank_structured_fields(row))
        seen_groups[row["context_group_id"]] += 1
        if len(selected) == 20:
            break
    pilot_fields = [
        "context_id", "context_group_id", "source_document_id", "title", "year", "venue", "page",
        "citation_section", "mention_type", "matched_seed_variant", "false_positive_risk",
        "old_snippet_clean", "sentence_before", "citation_sentence", "sentence_after",
        "section_heading", "context_window", "bibliography_detected", "bibliography_score",
        "extraction_confidence", "extraction_issue_flags", "review_priority",
        "llm_primary_role", "llm_stance_toward_meadows", "llm_confidence", "llm_uncertainty_flags",
        "new_window_improves_review", "new_window_notes",
    ]
    write_csv(VALIDATION / "context_window_pilot_20.csv", selected, pilot_fields)

    reextracted = []
    comparison = []
    for row in selected:
        pdf = PDF_DIR / f"{row['context_id'].split('|')[0]}.pdf"
        status = "source_pdf_missing" if not pdf.exists() else "ready_for_reextraction"
        reextracted.append({
            **row,
            "reextraction_status": status,
            "source_pdf_expected": str(pdf.relative_to(ROOT)),
            "new_extraction_confidence": "",
        })
        comparison.append({
            "context_id": row["context_id"],
            "context_group_id": row["context_group_id"],
            "old_snippet_length": len(row["old_snippet_clean"]),
            "new_context_length": "",
            "citation_sentence_exists": "",
            "sentence_before_exists": "",
            "sentence_after_exists": "",
            "old_bibliography_detected": "",
            "new_bibliography_detected": "",
            "old_extraction_confidence": row["extraction_confidence"],
            "new_extraction_confidence": "",
            "row_now_more_reviewable": "",
            "comparison_status": status,
        })
    write_csv(VALIDATION / "context_window_pilot_reextracted.csv", reextracted)
    write_csv(TABLES / "context_window_pilot_comparison.csv", comparison)

    mandatory_ids = set()
    for row in rows:
        if (
            row["human_primary_role"]
            or row["review_priority"] == "high"
            or row["context_id"] in boundary_ids
            or row["llm_primary_role"] in {"critique", "bibliographic_only"}
            or row["llm_stance_toward_meadows"] == "supportive"
            or any(flag in row["review_reason"] for flag in ("bibliography_only", "ocr_noise", "snippet_too_short", "missing_surrounding_context"))
        ):
            mandatory_ids.add(row["context_id"])
    mandatory = [row for row in rows if row["context_id"] in mandatory_ids]
    lower = [row for row in rows if row["context_id"] not in mandatory_ids]
    random.Random(42).shuffle(lower)
    v2 = mandatory + lower[: max(0, 97 - len(mandatory))]
    v2_rows = []
    for row in v2:
        v2_rows.append({
            "context_group_id": row["context_group_id"],
            "mention_level_id": row["context_id"],
            "is_repeated_context": row["is_repeated_context"],
            "mention_variant_count": row["mention_variant_count"],
            "title": row["title"],
            "year": row["year"],
            "venue": row["venue"],
            "page": row["page"],
            "citation_section": row["citation_section"],
            "mention_type": row["mention_type"],
            "snippet_clean": row["snippet_clean"],
            "context_window": row.get("context_window", ""),
            "citation_sentence": row.get("citation_sentence", ""),
            "sentence_before": row.get("sentence_before", ""),
            "sentence_after": row.get("sentence_after", ""),
            "section_heading": row.get("section_heading", ""),
            "bibliography_detected": row.get("bibliography_detected", ""),
            "bibliography_score": row.get("bibliography_score", ""),
            "v1_llm_primary_role": row["llm_primary_role"],
            "v1_llm_topic": row["llm_discourse_category"],
            "v1_llm_stance": row["llm_stance_toward_meadows"],
            "v1_llm_confidence": row["llm_confidence"],
            "v1_llm_evidence_quote": row["llm_evidence_quote"],
            "v1_llm_uncertainty_flags": row["llm_uncertainty_flags"],
            "fallback_primary_role": normalized_fallback(row),
            "human_is_seed_work_citation": row["human_is_seed_work_citation"],
            "human_primary_role": row["human_primary_role"],
            "human_discourse_category": row["human_discourse_category"],
            "human_stance_toward_seed": row["human_stance_toward_seed"],
            "human_false_positive_flag": row["human_false_positive_flag"],
            "human_confidence": row["human_confidence"],
            "review_priority": row["review_priority"],
            "review_reason": row["review_reason"],
        })
    write_csv(VALIDATION / "v2_classifier_pilot_input_100.csv", v2_rows)
    print(f"Wrote {len(packet)} boundary rows, {len(selected)} context-window pilot rows, and {len(v2_rows)} v2 pilot inputs.")


if __name__ == "__main__":
    main()
