#!/usr/bin/env python3
"""Prepare modeling/simulation validation packet and review aids."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"

DECISION_QUESTION = (
    "Does the citation event discuss World3, system dynamics, simulations, scenarios, "
    "forecasts, projections, assumptions, sensitivity, feedback, model performance, or model comparison?"
)

HUMAN_FIELDS = [
    "human_is_seed_work_citation",
    "human_primary_role",
    "human_topic_or_discourse_area",
    "human_stance_toward_seed",
    "human_confidence",
    "human_notes",
    "review_status",
]

MODELING_TERMS = [
    "world3",
    "world 3",
    "system dynamics",
    "simulation",
    "model",
    "scenario",
    "forecast",
    "projection",
    "assumption",
    "sensitivity",
    "feedback",
    "performance",
    "variables",
    "components",
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


def text_for(row: Dict[str, str]) -> str:
    return clean(" ".join(row.get(field, "") for field in ("citation_sentence", "context_window", "legacy_snippet")))


def key_modeling_cue(row: Dict[str, str]) -> str:
    text = text_for(row)
    lower = text.lower()
    for term in MODELING_TERMS:
        index = lower.find(term)
        if index >= 0:
            start = max(0, index - 70)
            end = min(len(text), index + len(term) + 110)
            return clean(text[start:end])
    return clean(row.get("citation_sentence", ""))[:220]


def possible_confound(row: Dict[str, str]) -> str:
    text = text_for(row).lower()
    confounds = []
    if any(term in text for term in ("published", "publication", "history", "landmark", "founding", "influence")):
        confounds.append("historical/publication cue")
    if any(term in text for term in ("resource", "growth", "collapse", "pollution", "population", "food")):
        confounds.append("substantive resource/growth claim")
    if len(text) < 160:
        confounds.append("short context")
    return " | ".join(confounds) or "none_obvious"


def blank_human(row: Dict[str, Any]) -> Dict[str, Any]:
    for field in HUMAN_FIELDS:
        row[field] = ""
    return row


def packet_rows() -> List[Dict[str, Any]]:
    rows = []
    for row in read_csv(VALIDATION / "router_safe_worklist_modeling.csv"):
        rows.append(blank_human({
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
            "rule_hits": row.get("rule_hits", ""),
            "relevant_codebook_rule": row.get("relevant_codebook_rule", ""),
            "decision_question": DECISION_QUESTION,
        }))
    rows.sort(key=lambda item: (item.get("year", ""), item.get("context_group_id", "")))
    return rows


def side_by_side(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for index, row in enumerate(rows, 1):
        out.append({
            "row_number": index,
            "context_group_id": row["context_group_id"],
            "short_title": short_title(row["title"]),
            "citation_sentence": row["citation_sentence"],
            "key_modeling_cue": key_modeling_cue(row),
            "possible_confound": possible_confound(row),
            "reviewer_question": DECISION_QUESTION,
            "blank_human_primary_role": "",
            "blank_human_notes": "",
        })
    return out


def merge_template(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "context_group_id": row["context_group_id"],
            "human_is_seed_work_citation": "",
            "human_primary_role": "",
            "human_topic_or_discourse_area": "",
            "human_stance_toward_seed": "",
            "human_confidence": "",
            "human_notes": "",
            "review_status": "",
        }
        for row in rows
    ]


def write_guidance() -> None:
    text = """# Modeling/Simulation Validation Guidance

Decision question:

Does the citation event discuss World3, system dynamics, simulations, scenarios, forecasts, projections, assumptions, sensitivity, feedback, model performance, or model comparison?

Code as `modeling_simulation_reference` when the citation event explicitly discusses:

- World3
- system dynamics
- model structure
- simulations
- scenarios
- forecasts/projections
- assumptions
- sensitivity
- feedback
- model performance
- comparison with other models
- variables/components of the LTG model

Do not code as modeling merely because:

- the citing article itself uses a model
- the article title contains "model"
- Meadows is discussed historically
- Meadows is cited for a substantive resource/growth claim without model discussion

If the citation invokes a prediction or conclusion but not model structure/process, use `foundational_citation`.

If the citation discusses publication history, influence, or reception, use `historical_framing`.

If the text is too short or OCR-damaged, use `unclear`.
"""
    (VALIDATION / "modeling_validation_guidance.md").write_text(text, encoding="utf-8")


def validate(rows: List[Dict[str, Any]]) -> None:
    if len(rows) != 11:
        raise ValueError(f"Expected 11 modeling rows, found {len(rows)}")
    ids = [row["context_group_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Modeling validation packet has duplicate context_group_id values")
    for row in rows:
        for field in HUMAN_FIELDS:
            if row.get(field, "") != "":
                raise ValueError(f"Human field {field} was not blank for {row['context_group_id']}")


def main() -> None:
    rows = packet_rows()
    validate(rows)
    write_csv(VALIDATION / "modeling_validation_packet.csv", rows)
    write_guidance()
    write_csv(TABLES / "modeling_validation_side_by_side.csv", side_by_side(rows))
    write_csv(VALIDATION / "modeling_validation_merge_template.csv", merge_template(rows))
    print(f"Modeling validation rows: {len(rows)}")
    print("Human fields blank: yes")


if __name__ == "__main__":
    main()
