#!/usr/bin/env python3
"""Prepare final router-safe audit packets and blank agreement scaffolds."""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"

RANDOM_SEED = 1972

AUDIT_HUMAN_FIELDS = [
    "human_is_bibliography_only",
    "human_confidence",
    "human_notes",
    "review_status",
]

BATCH_A_HUMAN_FIELDS = [
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


def blank_fields(row: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    for field in fields:
        row[field] = ""
    return row


def bibliography_sample() -> List[Dict[str, Any]]:
    rng = random.Random(RANDOM_SEED)
    sample_rows: List[Dict[str, Any]] = []
    for batch_name in ("C", "D"):
        rows = read_csv(VALIDATION / f"router_safe_batch_{batch_name}.csv")
        if len(rows) < 10:
            raise ValueError(f"Batch {batch_name} has fewer than 10 rows")
        sampled = rng.sample(rows, 10)
        sampled.sort(key=lambda item: int(item.get("batch_row_number", "0") or 0))
        for row in sampled:
            out = {
                "random_seed": RANDOM_SEED,
                "source_batch": f"Batch {batch_name}",
                "context_group_id": row.get("context_group_id", ""),
                "citation_sentence": row.get("citation_sentence", ""),
                "context_window": row.get("context_window", ""),
                "router_primary_role": row.get("router_primary_role", ""),
                "routing_reason": row.get("routing_reason", ""),
            }
            sample_rows.append(blank_fields(out, AUDIT_HUMAN_FIELDS))
    return sample_rows


def batch_a_review_packet() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "router_safe_batch_A.csv")
    if len(rows) != 24:
        raise ValueError(f"Expected 24 Batch A rows, found {len(rows)}")
    out_rows: List[Dict[str, Any]] = []
    for row in rows:
        out = {
            "context_group_id": row.get("context_group_id", ""),
            "title": row.get("title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "citation_sentence": row.get("citation_sentence", ""),
            "sentence_before": row.get("sentence_before", ""),
            "sentence_after": row.get("sentence_after", ""),
            "context_window": row.get("context_window", ""),
            "router_primary_role": row.get("router_primary_role", ""),
            "router_topic": row.get("router_topic", ""),
            "router_stance": row.get("router_stance", ""),
            "routing_reason": row.get("routing_reason", ""),
            "rule_hits": row.get("rule_hits", ""),
        }
        out_rows.append(blank_fields(out, BATCH_A_HUMAN_FIELDS))
    return out_rows


def agreement_template() -> List[Dict[str, Any]]:
    return [
        {
            "stratum": stratum,
            "audited_rows": "",
            "agreement_count": "",
            "disagreement_count": "",
            "agreement_rate": "",
            "false_positive_count": "",
            "false_negative_count": "",
            "notes": "",
        }
        for stratum in [
            "historical_framing",
            "foundational_citation",
            "modeling_simulation_reference",
            "bibliography_only",
            "unclear",
        ]
    ]


def audit_progress(batch_a_count: int, bibliography_count: int) -> List[Dict[str, Any]]:
    coded = 0
    total = batch_a_count + bibliography_count
    return [{
        "batch_A_total_rows": batch_a_count,
        "batch_A_coded_rows": 0,
        "bibliography_audit_total_rows": bibliography_count,
        "bibliography_audit_coded_rows": 0,
        "remaining_audit_rows": total - coded,
        "percent_complete": 0,
    }]


def freeze_status() -> List[Dict[str, Any]]:
    return [{
        "historical_foundational_validation_complete": "yes",
        "modeling_validation_complete": "yes",
        "extraction_review_substantially_complete": "yes",
        "router_safe_audit_pending": "yes",
        "methodology_freeze_readiness": "not_ready_pending_router_safe_audit",
        "status_note": "Final router-safe Batch A coding and bibliography audit are prepared but not adjudicated.",
    }]


def validate_blank(rows: List[Dict[str, Any]], fields: List[str]) -> None:
    for row in rows:
        for field in fields:
            if row.get(field, "") != "":
                raise ValueError(f"Expected blank {field} for {row.get('context_group_id', '<unknown>')}")


def main() -> None:
    sample = bibliography_sample()
    batch_a = batch_a_review_packet()
    validate_blank(sample, AUDIT_HUMAN_FIELDS)
    validate_blank(batch_a, BATCH_A_HUMAN_FIELDS)

    write_csv(VALIDATION / "bibliography_audit_sample.csv", sample)
    write_csv(VALIDATION / "router_safe_batch_A_review_packet.csv", batch_a)
    write_csv(TABLES / "router_safe_stratum_agreement_template.csv", agreement_template())
    write_csv(TABLES / "router_safe_audit_progress.csv", audit_progress(len(batch_a), len(sample)))
    write_csv(TABLES / "pre_methodology_freeze_status.csv", freeze_status())

    print(f"Batch A rows: {len(batch_a)}")
    print(f"Bibliography audit sample rows: {len(sample)}")
    print(f"Random seed: {RANDOM_SEED}")


if __name__ == "__main__":
    main()
