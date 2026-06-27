#!/usr/bin/env python3
"""Apply final consensus labels for the six historical/foundational cases.

This updates only consensus/adjudication artifacts. Router outputs, LLM outputs,
and original validation labels are not modified.
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


CONSENSUS = {
    "cg_fd3b865d9333": {
        "consensus_primary_role": "foundational_citation",
        "consensus_confidence": "medium",
        "consensus_notes": "Resource-scarcity concern is being used as substantive evidence; historical period is secondary.",
        "distinction_stable_yes_no": "yes",
    },
    "cg_d1461f83c00e": {
        "consensus_primary_role": "historical_framing",
        "consensus_confidence": "medium",
        "consensus_notes": "Citation is primarily discussing debate, reception, and intellectual history.",
        "distinction_stable_yes_no": "yes",
    },
    "cg_9d082b6ad710": {
        "consensus_primary_role": "unclear",
        "consensus_confidence": "high",
        "consensus_notes": "Context too truncated/OCR damaged to reliably determine function.",
        "distinction_stable_yes_no": "no",
    },
    "cg_extra_6c5b9c5d7bf7": {
        "consensus_primary_role": "foundational_citation",
        "consensus_confidence": "high",
        "consensus_notes": "Resource-scarcity argument is functioning as a substantive premise.",
        "distinction_stable_yes_no": "yes",
    },
    "cg_extra_01b174e604c7": {
        "consensus_primary_role": "foundational_citation",
        "consensus_confidence": "low_medium",
        "consensus_notes": "Fragmentary context, but substantive limits/resource argument appears primary.",
        "distinction_stable_yes_no": "yes",
    },
    "cg_17981a2ea3ca": {
        "consensus_primary_role": "foundational_citation",
        "consensus_confidence": "high",
        "consensus_notes": "Meadows is being cited for future-crisis/limits claims rather than historical significance.",
        "distinction_stable_yes_no": "yes",
    },
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


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def pct(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def text_for(row: Dict[str, str]) -> str:
    return clean(" ".join(row.get(field, "") for field in ("context_text", "citation_sentence", "context_window", "legacy_snippet")))


def has_any(text: str, terms: List[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def case_flags(row: Dict[str, str], consensus: Dict[str, str]) -> Dict[str, str]:
    text = text_for(row)
    lower = text.lower()
    return {
        "publication_lineage_present": str(has_any(lower, ["published", "publication", "report", "book", "landmark", "founding", "lineage", "intellectual history"])).lower(),
        "substantive_meadows_claim_present": str(
            consensus["consensus_primary_role"] == "foundational_citation"
            or has_any(lower, ["resource scarc", "future crisis", "limits claims", "finite", "growth", "constraint", "catastrophic"])
        ).lower(),
        "resource_constraint_language_present": str(has_any(lower, ["resource", "scarcity", "scarcities", "limits", "growth", "finite", "crisis", "catastrophic"])).lower(),
        "chronology_language_present": str(bool(re.search(r"\b(19|20)\d{2}\b|1970s|period|as early|since|after|before", lower))).lower(),
        "debate_or_reception_language_present": str(has_any(lower, ["debate", "reception", "reactions", "silence", "defense", "intellectual history", "welcomed"])).lower(),
        "OCR_or_context_problem": str(consensus["consensus_primary_role"] == "unclear" or has_any(lower, ["ocr", "truncated"]) or len(text) < 120).lower(),
    }


def load_review_rows() -> List[Dict[str, str]]:
    rows = read_csv(VALIDATION / "historical_foundational_six_case_review.csv")
    ids = [row["context_group_id"] for row in rows]
    missing = sorted(set(CONSENSUS) - set(ids))
    extra = sorted(set(ids) - set(CONSENSUS))
    if missing or extra:
        raise ValueError(f"Consensus ID mismatch; missing={missing}, extra={extra}")
    return rows


def apply_consensus() -> List[Dict[str, Any]]:
    rows = load_review_rows()
    out = []
    for row in rows:
        label = CONSENSUS[row["context_group_id"]]
        updated = dict(row)
        updated["human_is_seed_work_citation"] = ""
        updated["consensus_primary_role"] = label["consensus_primary_role"]
        updated["consensus_topic_or_discourse_area"] = ""
        updated["consensus_stance_toward_seed"] = "neutral_descriptive"
        updated["consensus_confidence"] = label["consensus_confidence"]
        updated["consensus_notes"] = label["consensus_notes"]
        updated["distinction_stable_yes_no"] = label["distinction_stable_yes_no"]
        updated["rule_implication"] = ""
        updated["ready_to_merge"] = "yes"
        out.append(updated)
    write_csv(VALIDATION / "historical_foundational_six_case_review.csv", out)
    return out


def update_merge_template(rows: List[Dict[str, Any]]) -> None:
    merge_rows = []
    for row in rows:
        merge_rows.append({
            "context_group_id": row["context_group_id"],
            "consensus_primary_role": row["consensus_primary_role"],
            "consensus_topic_or_discourse_area": row["consensus_topic_or_discourse_area"],
            "consensus_stance_toward_seed": row["consensus_stance_toward_seed"],
            "consensus_confidence": row["consensus_confidence"],
            "consensus_notes": row["consensus_notes"],
            "distinction_stable_yes_no": row["distinction_stable_yes_no"],
            "rule_implication": row["rule_implication"],
            "ready_to_merge": row["ready_to_merge"],
        })
    write_csv(VALIDATION / "historical_foundational_six_case_merge_template.csv", merge_rows)


def consensus_review(rows: List[Dict[str, Any]]) -> None:
    review_rows = []
    for row in rows:
        review_rows.append({
            "context_group_id": row["context_group_id"],
            "title": row["title"],
            "year": row["year"],
            "router_primary_role": row.get("router_primary_role", ""),
            "consensus_primary_role": row["consensus_primary_role"],
            "consensus_stance_toward_seed": row["consensus_stance_toward_seed"],
            "consensus_confidence": row["consensus_confidence"],
            "consensus_notes": row["consensus_notes"],
            "distinction_stable_yes_no": row["distinction_stable_yes_no"],
            "ready_to_merge": row["ready_to_merge"],
            "new_router_rule_applied": "no",
        })
    write_csv(TABLES / "historical_foundational_consensus_review.csv", review_rows)


def merged_table(rows: List[Dict[str, Any]]) -> None:
    agreements = [row for row in rows if row.get("router_primary_role", "") == row["consensus_primary_role"]]
    total = len(rows)
    agreement_count = len(agreements)
    out = []
    for row in rows:
        out.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row.get("router_primary_role", ""),
            "consensus_primary_role": row["consensus_primary_role"],
            "agreement_yes_no": "yes" if row.get("router_primary_role", "") == row["consensus_primary_role"] else "no",
            "confidence": row["consensus_confidence"],
            "notes": row["consensus_notes"],
            "total_reviewed": total,
            "router_agreement_count": agreement_count,
            "router_disagreement_count": total - agreement_count,
            "router_agreement_rate": pct(agreement_count, total),
        })
    write_csv(TABLES / "historical_foundational_consensus_merged.csv", out)


def boundary_analysis(rows: List[Dict[str, Any]]) -> None:
    counts = Counter(row["consensus_primary_role"] for row in rows)
    disagreements = [row for row in rows if row.get("router_primary_role", "") != row["consensus_primary_role"]]
    examples = " | ".join(f"{row['context_group_id']}:{row.get('router_primary_role','')}->{row['consensus_primary_role']}" for row in disagreements)
    out = []
    for row in rows:
        flags = case_flags(row, row)
        out.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row.get("router_primary_role", ""),
            "consensus_primary_role": row["consensus_primary_role"],
            "total_reviewed": len(rows),
            "historical_framing_count": counts.get("historical_framing", 0),
            "foundational_citation_count": counts.get("foundational_citation", 0),
            "unclear_count": counts.get("unclear", 0),
            "router_agreement": "yes" if row.get("router_primary_role", "") == row["consensus_primary_role"] else "no",
            "router_disagreement": "no" if row.get("router_primary_role", "") == row["consensus_primary_role"] else "yes",
            "router_agreement_count": len(rows) - len(disagreements),
            "router_disagreement_count": len(disagreements),
            "router_agreement_rate": pct(len(rows) - len(disagreements), len(rows)),
            "disagreement_examples": examples,
            "boundary_characteristics": boundary_characteristics(flags),
            **flags,
        })
    write_csv(TABLES / "historical_foundational_boundary_analysis.csv", out)


def boundary_characteristics(flags: Dict[str, str]) -> str:
    labels = []
    for key, value in flags.items():
        if value == "true":
            labels.append(key)
    return " | ".join(labels)


def router_refinement_assessment(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    stable = sum(1 for row in rows if row["distinction_stable_yes_no"] == "yes")
    disagreements = sum(1 for row in rows if row.get("router_primary_role", "") != row["consensus_primary_role"])
    unclear = sum(1 for row in rows if row["consensus_primary_role"] == "unclear")
    rows_out = [
        {
            "assessment_question": "Whether the distinction appears reproducible",
            "answer": "partially_yes",
            "evidence": f"{stable}/{total} cases marked stable; {unclear}/{total} remains unclear due to context quality.",
            "recommendation": "Use the distinction for human coding, but do not treat it as fully automated.",
        },
        {
            "assessment_question": "Whether router rules should change",
            "answer": "not_automatically",
            "evidence": f"Router disagreed with consensus in {disagreements}/{total} cases, mostly by over-historical labeling.",
            "recommendation": "Do not implement a new router rule yet; draft a candidate rule only after more historical-lineage and foundational-claim rows are coded.",
        },
        {
            "assessment_question": "Whether extraction quality is a larger problem than routing",
            "answer": "no_for_this_six_case_set",
            "evidence": f"Router disagreed with consensus in {disagreements}/{total} cases; {unclear}/{total} case was explicitly unresolved because of truncated/OCR-damaged context.",
            "recommendation": "Treat routing/boundary specification as the larger issue for this six-case set, while preserving extraction review for truncated/OCR cases.",
        },
        {
            "assessment_question": "Whether additional validation is needed",
            "answer": "yes",
            "evidence": "Only six boundary cases have consensus labels.",
            "recommendation": "Code historical-lineage and foundational-claim spot-check batches next.",
        },
    ]
    write_csv(TABLES / "historical_foundational_router_refinement_assessment.csv", rows_out)


def validation_progress(rows: List[Dict[str, Any]]) -> None:
    coverage = {row["stratum"]: row for row in read_csv(TABLES / "validation_coverage_audit.csv")}
    previous = int(float(coverage.get("total_validation_sample", {}).get("human_coded_rows", 48)))
    new_count = previous + len(rows)
    total_validation = int(float(coverage.get("total_validation_sample", {}).get("total_rows", 97)))
    extraction_rows = len(read_csv(VALIDATION / "extraction_recovery_review_packet.csv"))
    gray_total = int(float(coverage.get("gray_zone", {}).get("total_rows", 55)))
    gray_human = int(float(coverage.get("gray_zone", {}).get("human_coded_rows", 18)))
    out = [
        {
            "previous_human_coded_count": previous,
            "new_human_coded_count": new_count,
            "unresolved_count": max(total_validation - new_count, 0),
            "historical_foundational_cases_resolved": len(rows),
            "remaining_boundary_cases": 0,
            "remaining_gray_zone_cases": max(gray_total - gray_human - len(rows), 0),
            "remaining_extraction_review_cases": extraction_rows,
            "next_recommended_validation_priority": "Code historical-lineage rows, then foundational-claim rows.",
        }
    ]
    write_csv(TABLES / "validation_progress_after_consensus.csv", out)


def next_human_coding_recommendations() -> None:
    recommendations = [
        ("historical-lineage rows", 1, "high", "high", "Resolve whether historical framing is over-assigned."),
        ("foundational-claim rows", 2, "high", "high", "Test whether substantive Meadows claims can be separated from chronology."),
        ("modeling rows", 3, "medium-high", "high", "Validate deterministic modeling category before any scaling."),
        ("extraction-recovery likely-improves rows", 4, "medium-high", "medium-high", "Check whether repaired context actually reduces ambiguity."),
        ("bibliography rows", 5, "medium", "medium", "Validate structural bibliography-only rule."),
        ("OCR rows", 6, "low-medium", "medium", "Small n; useful for abstention behavior but not broad rule refinement."),
    ]
    out = []
    for label, order, gain, value, note in recommendations:
        out.append({
            "coding_target": label,
            "suggested_coding_order": order,
            "expected_information_gain": gain,
            "expected_methodological_value": value,
            "notes": note,
            "human_labels_filled": "no",
        })
    write_csv(TABLES / "next_human_coding_recommendations.csv", out)


def validate(rows: List[Dict[str, Any]]) -> None:
    if len(rows) != 6:
        raise ValueError(f"Expected six rows, found {len(rows)}")
    if set(row["context_group_id"] for row in rows) != set(CONSENSUS):
        raise ValueError("Consensus rows do not match expected IDs")
    if any(row.get("ready_to_merge") != "yes" for row in rows):
        raise ValueError("All consensus rows must be ready_to_merge=yes")


def main() -> None:
    rows = apply_consensus()
    validate(rows)
    update_merge_template(rows)
    consensus_review(rows)
    merged_table(rows)
    boundary_analysis(rows)
    router_refinement_assessment(rows)
    validation_progress(rows)
    next_human_coding_recommendations()
    agreement = sum(1 for row in rows if row.get("router_primary_role") == row["consensus_primary_role"])
    counts = Counter(row["consensus_primary_role"] for row in rows)
    print(f"Consensus rows applied: {len(rows)}")
    print(f"Router agreement: {agreement}/{len(rows)}")
    print("Consensus counts: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


if __name__ == "__main__":
    main()
