#!/usr/bin/env python3
"""Prepare historical/foundational expansion validation artifacts.

No labels are filled and no router code is modified. This script creates a
22-row review packet and diagnostic tables for boundary-focused human coding.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"


HISTORICAL_INDICATORS = ["published", "publication", "1971", "1972", "history", "historical", "lineage", "influence", "audience", "debate", "reception", "landmark", "founding", "sold", "popularised", "public"]
FOUNDATIONAL_INDICATORS = ["resource", "scarcity", "scarcities", "limits", "growth", "future crisis", "finite", "biophysical", "carrying capacity", "overshoot", "collapse", "constraint", "population", "pollution", "catastrophic"]
UNCLEAR_INDICATORS = ["ocr", "truncated", "fragment", "incomplete", "damaged"]
DEBATE_INDICATORS = ["debate", "reception", "reaction", "reactions", "criticiz", "denounced", "defense", "silence", "insults"]


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


def text_for(row: Dict[str, str]) -> str:
    return clean(" ".join(row.get(field, "") for field in ("citation_sentence", "sentence_before", "sentence_after", "context_window", "legacy_snippet", "context_text")))


def has_any(text: str, terms: List[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def decision_question(row: Dict[str, str]) -> str:
    if row.get("priority_category") == "historical_publication_lineage":
        return "Is this truly historical/publication lineage, or is a substantive Meadows claim doing the citation work?"
    return "Is this truly a foundational Meadows claim, or is the citation mainly debate, reception, chronology, or publication history?"


def build_packet() -> List[Dict[str, Any]]:
    inputs = [
        read_csv(VALIDATION / "router_safe_worklist_historical_lineage.csv"),
        read_csv(VALIDATION / "router_safe_worklist_foundational_claims.csv"),
    ]
    rows = []
    for source_rows in inputs:
        for row in source_rows:
            rows.append({
                "context_group_id": row.get("context_group_id", ""),
                "title": row.get("title", ""),
                "year": row.get("year", ""),
                "venue": row.get("venue", ""),
                "citation_sentence": row.get("citation_sentence", ""),
                "sentence_before": row.get("sentence_before", ""),
                "sentence_after": row.get("sentence_after", ""),
                "context_window": row.get("context_window", ""),
                "legacy_snippet": row.get("legacy_snippet", ""),
                "router_primary_role": row.get("router_function", ""),
                "router_topic": row.get("router_topic", ""),
                "router_stance": row.get("router_stance", ""),
                "routing_reason": row.get("routing_reason", ""),
                "relevant_codebook_rule": row.get("relevant_codebook_rule", ""),
                "decision_question": decision_question(row),
                "human_is_seed_work_citation": "",
                "human_primary_role": "",
                "human_topic_or_discourse_area": "",
                "human_stance_toward_seed": "",
                "human_confidence": "",
                "human_notes": "",
                "review_status": "",
            })
    rows.sort(key=lambda row: (0 if row["router_primary_role"] == "historical_framing" else 1, row.get("year", ""), row["context_group_id"]))
    return rows


def six_case_examples() -> Dict[str, str]:
    examples = {}
    for row in read_csv(VALIDATION / "historical_foundational_six_case_review.csv"):
        role = row.get("consensus_primary_role", "")
        if role and role not in examples:
            examples[role] = clean(row.get("context_text", ""))[:260]
    return examples


def reference_sheet() -> List[Dict[str, Any]]:
    examples = six_case_examples()
    return [
        {
            "category": "historical_framing_indicators",
            "indicators": "publication history; chronology; intellectual lineage; influence; reception; debate; landmark status",
            "six_case_example": examples.get("historical_framing", ""),
            "coding_note": "Historical framing marks the citation's role in chronology, reception, or lineage rather than use of a Meadows claim as evidence.",
            "new_rule_created": "no",
        },
        {
            "category": "foundational_citation_indicators",
            "indicators": "resource constraints; limits claims; future crisis; biophysical constraints; substantive Meadows findings; carrying capacity; overshoot; collapse dynamics",
            "six_case_example": examples.get("foundational_citation", ""),
            "coding_note": "Foundational citation requires a substantive Meadows/LtG claim functioning as a premise in the citing author's argument.",
            "new_rule_created": "no",
        },
        {
            "category": "unclear_indicators",
            "indicators": "OCR damage; insufficient context; fragmentary citation",
            "six_case_example": examples.get("unclear", ""),
            "coding_note": "Use unclear when visible text cannot support a reliable function label.",
            "new_rule_created": "no",
        },
    ]


def coverage_projection(packet: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    progress = read_csv(TABLES / "validation_progress_after_consensus.csv")
    current = int(progress[0].get("new_human_coded_count", 54)) if progress else 54
    unresolved = int(progress[0].get("unresolved_count", 43)) if progress else 43
    additional = len(packet)
    total_validation = current + unresolved
    return [
        {
            "metric": "current_validated_coverage",
            "count": current,
            "denominator": total_validation,
            "coverage": round(current / total_validation, 4) if total_validation else "",
            "note": "After six completed historical/foundational consensus cases.",
        },
        {
            "metric": "projected_validated_coverage_after_22_rows",
            "count": current + additional,
            "denominator": total_validation,
            "coverage": round((current + additional) / total_validation, 4) if total_validation else "",
            "note": "Projection only; assumes all 22 expansion rows are coded.",
        },
        {
            "metric": "remaining_historical_foundational_uncertainty",
            "count": additional,
            "denominator": additional,
            "coverage": "",
            "note": "The 22 expansion rows are the immediate uncertainty set.",
        },
        {
            "metric": "remaining_router_boundary_uncertainty",
            "count": additional,
            "denominator": additional,
            "coverage": "",
            "note": "Router labels are unvalidated for these rows; no statistical inference.",
        },
    ]


def router_error_inventory() -> List[Dict[str, Any]]:
    consensus_rows = read_csv(VALIDATION / "historical_foundational_six_case_review.csv")
    rows = []
    for row in consensus_rows:
        text = text_for(row)
        router = row.get("router_primary_role", "")
        human = row.get("consensus_primary_role", "")
        if router == human:
            error_type = "agreement"
        elif router == "historical_framing" and human != "historical_framing":
            error_type = "false_historical_classification"
        elif router == "foundational_citation" and human != "foundational_citation":
            error_type = "false_foundational_classification"
        elif human == "unclear":
            error_type = "unclear_case"
        else:
            error_type = "other_disagreement"
        rows.append({
            "context_group_id": row.get("context_group_id", ""),
            "router_recommendation": router,
            "human_consensus": human,
            "agreement_yes_no": "yes" if router == human else "no",
            "error_type": error_type,
            "publication_language": str(has_any(text, ["published", "publication", "report", "book", "founding", "landmark"])).lower(),
            "resource_constraint_language": str(has_any(text, FOUNDATIONAL_INDICATORS)).lower(),
            "debate_language": str(has_any(text, DEBATE_INDICATORS)).lower(),
            "chronology_language": str(bool(re.search(r"\\b(19|20)\\d{2}\\b|1970s|since|after|before|as early", text.lower()))).lower(),
            "ocr_issues": str(human == "unclear" or has_any(text, UNCLEAR_INDICATORS) or len(text) < 120).lower(),
        })
    counts = Counter(row["error_type"] for row in rows)
    for row in rows:
        row["error_inventory_summary"] = " | ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    return rows


def ambiguity_score(row: Dict[str, Any]) -> int:
    text = text_for(row)
    historical = has_any(text, HISTORICAL_INDICATORS)
    foundational = has_any(text, FOUNDATIONAL_INDICATORS)
    debate = has_any(text, DEBATE_INDICATORS)
    short = len(text) < 180
    score = 0
    if historical and foundational:
        score += 3
    if row.get("router_primary_role") == "historical_framing" and foundational:
        score += 2
    if row.get("router_primary_role") == "foundational_citation" and debate:
        score += 2
    if short:
        score += 1
    return score


def coding_order(packet: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for row in packet:
        score = ambiguity_score(row)
        rows.append({
            "coding_sequence": 0,
            "context_group_id": row["context_group_id"],
            "title": row["title"],
            "year": row["year"],
            "router_primary_role": row["router_primary_role"],
            "expected_information_gain": "high" if score >= 4 else ("medium_high" if score >= 2 else "medium"),
            "boundary_ambiguity": "high" if score >= 4 else ("medium" if score >= 2 else "low"),
            "methodological_importance": "high",
            "coding_rationale": coding_rationale(row, score),
        })
    rows.sort(key=lambda row: ({"high": 1, "medium_high": 2, "medium": 3}[row["expected_information_gain"]], row["year"], row["context_group_id"]))
    for index, row in enumerate(rows, 1):
        row["coding_sequence"] = index
    return rows


def coding_rationale(row: Dict[str, Any], score: int) -> str:
    text = text_for(row)
    cues = []
    if has_any(text, HISTORICAL_INDICATORS):
        cues.append("historical cues")
    if has_any(text, FOUNDATIONAL_INDICATORS):
        cues.append("foundational/resource cues")
    if has_any(text, DEBATE_INDICATORS):
        cues.append("debate/reception cues")
    if len(text) < 180:
        cues.append("short context")
    return "; ".join(cues) or "baseline validation row"


def validate(packet: List[Dict[str, Any]]) -> None:
    if len(packet) != 22:
        raise ValueError(f"Expected 22 expansion rows, found {len(packet)}")
    if any(row.get("human_primary_role") for row in packet):
        raise ValueError("Human labels must remain blank in expansion packet")


def main() -> None:
    packet = build_packet()
    validate(packet)
    write_csv(VALIDATION / "historical_foundational_expansion_review_packet.csv", packet)
    write_csv(TABLES / "historical_foundational_boundary_reference_sheet.csv", reference_sheet())
    write_csv(TABLES / "validation_coverage_projection.csv", coverage_projection(packet))
    write_csv(TABLES / "historical_foundational_router_error_inventory.csv", router_error_inventory())
    write_csv(TABLES / "historical_foundational_coding_order.csv", coding_order(packet))
    print(f"Historical/foundational expansion packet rows: {len(packet)}")
    print("Router labels in packet: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(row['router_primary_role'] for row in packet).items())))


if __name__ == "__main__":
    main()
