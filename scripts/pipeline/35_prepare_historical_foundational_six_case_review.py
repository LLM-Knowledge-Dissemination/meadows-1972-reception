#!/usr/bin/env python3
"""Prepare the six historical/foundational consensus cases for review.

This script only creates human-adjudication templates. It does not modify
existing human labels, LLM outputs, router outputs, or classifier artifacts.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"

ADJUDICATION_FIELDS = [
    "human_is_seed_work_citation",
    "consensus_primary_role",
    "consensus_topic_or_discourse_area",
    "consensus_stance_toward_seed",
    "consensus_confidence",
    "consensus_notes",
    "distinction_stable_yes_no",
    "rule_implication",
    "ready_to_merge",
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


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def short_title(title: str) -> str:
    title = clean(title)
    return title if len(title) <= 80 else title[:77].rstrip() + "..."


def evidence_phrase(row: Dict[str, str]) -> str:
    text = clean(row.get("citation_sentence") or row.get("context_text") or row.get("context_window"))
    match = re.search(
        r"(.{0,70}(Meadows|Limits to Growth|Club of Rome|1972|resource|growth|published|publication|historical|lineage).{0,110})",
        text,
        flags=re.I,
    )
    return clean(match.group(1)) if match else text[:220]


def likely_boundary(row: Dict[str, str]) -> str:
    text = clean(" ".join([row.get("context_text", ""), row.get("citation_sentence", "")])).lower()
    has_resource = any(term in text for term in ["resource", "growth", "limits", "finite", "scarcity", "collapse", "population"])
    has_history = any(term in text for term in ["published", "publication", "1972", "1970s", "history", "landmark", "lineage", "debate"])
    if has_resource and has_history:
        return "historical_vs_foundational"
    if has_resource:
        return "possible_foundational_claim"
    if has_history:
        return "possible_historical_lineage"
    return "unclear_boundary"


def blank_adjudication(row: Dict[str, Any]) -> Dict[str, Any]:
    for field in ADJUDICATION_FIELDS:
        row[field] = ""
    return row


def load_six_cases() -> List[Dict[str, str]]:
    consensus = read_csv(TABLES / "historical_foundational_consensus_worklist.csv")
    batch1 = {
        row.get("context_group_id", ""): row
        for row in read_csv(VALIDATION / "priority_human_coding_batch_1.csv")
        if row.get("review_priority") == "1_historical_foundational_consensus"
    }
    rows = []
    for row in consensus:
        batch_row = batch1.get(row.get("context_group_id", ""), {})
        rows.append({
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": batch_row.get("venue", ""),
            "context_text": row.get("context_text", "") or batch_row.get("context_text", ""),
            "citation_sentence": batch_row.get("citation_sentence", ""),
            "sentence_before": batch_row.get("sentence_before", ""),
            "sentence_after": batch_row.get("sentence_after", ""),
            "context_window": batch_row.get("context_window", "") or row.get("context_text", ""),
            "legacy_snippet": batch_row.get("legacy_snippet", "") or row.get("context_text", ""),
            "router_primary_role": row.get("router_recommendation", "") or batch_row.get("router_primary_role", ""),
            "router_topic": batch_row.get("router_topic", ""),
            "router_stance": batch_row.get("router_stance", ""),
            "routing_reason": batch_row.get("routing_reason", "") or "historical/foundational consensus review",
            "relevant_codebook_rule": row.get("relevant_codebook_rule", "") or batch_row.get("relevant_codebook_rule", ""),
            "decision_question": row.get("decision_question", "")
            or "Is Meadows being cited as a historical landmark/lineage marker, or is a substantive Meadows claim being used as a premise?",
        })
    return rows


def review_rows(cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    return [blank_adjudication(dict(row)) for row in cases]


def side_by_side(cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = []
    for index, row in enumerate(cases, 1):
        rows.append({
            "row_number": index,
            "context_group_id": row["context_group_id"],
            "short_title": short_title(row.get("title", "")),
            "citation_sentence": row.get("citation_sentence", ""),
            "key_evidence_phrase": evidence_phrase(row),
            "likely_boundary": likely_boundary(row),
            "reviewer_question": row.get("decision_question", ""),
            "blank_consensus_primary_role": "",
            "blank_consensus_notes": "",
        })
    return rows


def merge_template(cases: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    rows = []
    for row in cases:
        template_row = {"context_group_id": row["context_group_id"]}
        for field in ADJUDICATION_FIELDS[1:]:
            template_row[field] = ""
        rows.append(template_row)
    return rows


def write_guidance() -> None:
    text = """# Historical/Foundation Six-Case Guidance

Core decision question:

> Is Meadows being cited as a historical landmark/lineage marker, or is a substantive Meadows claim being used as a premise?

Coding guidance:

- `historical_framing`: Meadows is used as chronology, publication history, public memory, influence, debate, lineage, or landmark.
- `foundational_citation`: a substantive Meadows claim is used as a premise in the citing author's argument.
- `modeling_simulation_reference`: the citation event discusses World3, system dynamics, simulation, scenario, projection, assumptions, forecasts, or model comparison.
- Use `unclear` when the visible text is too short, OCR-damaged, or does not clearly identify Meadows 1972.
- Stance is usually `neutral_descriptive` unless there is explicit endorsement or criticism.
- Historical importance is not supportive stance.

Do not infer a final label from venue, title, or broader paper topic. Code only the visible citation event and leave uncertainty explicit.
"""
    (VALIDATION / "historical_foundational_six_case_guidance.md").write_text(text, encoding="utf-8")


def validate_outputs(cases: List[Dict[str, Any]], merge_rows: List[Dict[str, Any]]) -> None:
    if len(cases) != 6:
        raise ValueError(f"Expected exactly 6 cases; found {len(cases)}")
    ids = [row["context_group_id"] for row in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("context_group_id values are not unique")
    for row in cases:
        for field in ADJUDICATION_FIELDS:
            if row.get(field, "") != "":
                raise ValueError(f"Adjudication field {field} was not blank for {row['context_group_id']}")
    for row in merge_rows:
        for field in ADJUDICATION_FIELDS[1:]:
            if row.get(field, "") != "":
                raise ValueError(f"Merge template field {field} was not blank for {row['context_group_id']}")


def main() -> None:
    cases = load_six_cases()
    review = review_rows(cases)
    side = side_by_side(cases)
    merge = merge_template(cases)
    validate_outputs(review, merge)

    write_csv(VALIDATION / "historical_foundational_six_case_review.csv", review)
    write_guidance()
    write_csv(TABLES / "historical_foundational_six_case_side_by_side.csv", side)
    write_csv(VALIDATION / "historical_foundational_six_case_merge_template.csv", merge)

    print(f"Historical/foundational six-case review rows: {len(review)}")
    print(f"Unique context_group_id values: {len(set(row['context_group_id'] for row in review))}")
    print("Adjudication fields blank: yes")


if __name__ == "__main__":
    main()
