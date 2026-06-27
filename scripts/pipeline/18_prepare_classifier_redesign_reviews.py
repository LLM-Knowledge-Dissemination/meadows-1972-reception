#!/usr/bin/env python3
"""Prepare conservative critique, supportive, and boundary review tables."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "analysis/validation/citation_context_validation_sample.csv"
TABLES = ROOT / "analysis/tables"

FIELDS = [
    "context_id", "context_group_id", "title", "year", "snippet_clean",
    "fallback_label", "llm_label", "llm_stance", "llm_confidence",
    "uncertainty_flags", "recommended_human_primary_role",
    "recommended_human_stance_toward_seed", "recommended_human_confidence",
    "recommended_human_notes", "safe_to_apply_automatically", "needs_manual_review",
]


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fallback(row):
    return {
        "sustainability_limits_to_growth_discourse": "sustainability_discourse",
        "background_or_ambiguous": "unclear",
        "methodological_comparison": "methods_comparison",
    }.get(row["rule_citation_function"], row["rule_citation_function"])


def base(row):
    return {
        "context_id": row["context_id"],
        "context_group_id": row.get("context_group_id", ""),
        "title": row["title"],
        "year": row["year"],
        "snippet_clean": row["snippet_clean"],
        "fallback_label": fallback(row),
        "llm_label": row["llm_primary_role"],
        "llm_stance": row["llm_stance_toward_meadows"],
        "llm_confidence": row["llm_confidence"],
        "uncertainty_flags": row["llm_uncertainty_flags"],
    }


def critique_recommendation(row):
    result = base(row)
    cid = row["context_id"]
    recommendations = {
        "10_1016_j_respol_2011_06_011|14|Limits to Growth": ("unclear", "neutral_descriptive", "low", "The fragment attributes a prediction but is too short to establish critique or another function.", "no", "yes"),
        "10_1016_j_respol_2011_06_011|14|(Meadows et al., 1972)": ("foundational_citation", "neutral_descriptive", "medium", "Attributes a substantive collapse prediction to Limits to Growth; no explicit negative assessment appears.", "no", "yes"),
        "10_1016_j_apgeog_2010_10_014|2|limits to growth": ("unclear", "neutral_descriptive", "low", "The fragment describes a debate but is truncated before its rhetorical function becomes clear.", "no", "yes"),
        "10_1016_j_apgeog_2010_10_014|2|(Meadows et al. 1972)": ("historical_framing", "neutral_descriptive", "high", "Places limits to growth within an historical debate; describing debate is not critique.", "yes", "no"),
        "10_1016_j_respol_2021_104393|5|(Meadows et al., 1972)": ("historical_framing", "neutral_descriptive", "low", "Mentions Freeman's critique historically, but OCR/context and bibliography-only uncertainty prevent a direct critical stance judgment.", "no", "yes"),
        "10_1016_j_techsoc_2021_101587|5|(Meadows et al., 1972)": ("historical_framing", "neutral_descriptive", "high", "Uses Limits to Growth as a famous historical debate; no explicit negative assessment is present.", "yes", "no"),
    }
    role, stance, confidence, notes, safe, manual = recommendations[cid]
    result.update({
        "recommended_human_primary_role": role,
        "recommended_human_stance_toward_seed": stance,
        "recommended_human_confidence": confidence,
        "recommended_human_notes": notes,
        "safe_to_apply_automatically": safe,
        "needs_manual_review": manual,
    })
    return result


def boundary_recommendation(row, group_labels):
    result = base(row)
    flags = row["llm_uncertainty_flags"]
    snippet = row["snippet_clean"].lower()
    low_context = any(flag in flags for flag in ("snippet_too_short", "ocr_noise", "bibliography_only", "missing_surrounding_context"))
    role = ""
    confidence = "low" if low_context else "medium"
    notes = "Boundary case requires manual comparison of rhetorical function and topic."
    if low_context:
        role = "unclear"
        notes = "Context is short, OCR-corrupted, bibliography-like, or missing surrounding text; do not force a boundary label."
    elif any(term in snippet for term in ("world3", "system dynamics", "simulation", "scenario", "model assumption", "model ")):
        role = "modeling_simulation_reference"
        notes = "The citation event explicitly discusses modeling, simulation, scenarios, or model assumptions."
    elif any(term in snippet for term in ("in the 1970s", "history", "historical", "seminal", "landmark", "publication", "famous debate", "first exercises", "early")):
        role = "historical_framing"
        notes = "The citation primarily locates the work in a historical lineage, event, or debate."
    elif any(term in snippet for term in ("authors argued", "argued that", "pointed out that", "predicted that", "constrain economic growth")):
        role = "foundational_citation"
        notes = "The citation invokes a substantive Meadows claim as an intellectual premise."
    if len(group_labels) > 1:
        notes += " Repeated mention variants in this context group received inconsistent LLM labels."
    result.update({
        "recommended_human_primary_role": role,
        "recommended_human_stance_toward_seed": "neutral_descriptive" if role else "",
        "recommended_human_confidence": confidence if role else "low",
        "recommended_human_notes": notes,
        "safe_to_apply_automatically": "no",
        "needs_manual_review": "yes",
    })
    return result


def main():
    rows = read_csv(SAMPLE)
    critique = [
        row for row in rows
        if row["llm_primary_role"] == "critique"
        or row["llm_stance_toward_meadows"] == "critical"
        or row["rule_citation_function"] == "critique"
        or "critique" in row["review_reason"]
    ]
    write_csv(TABLES / "critique_rows_review.csv", [critique_recommendation(row) for row in critique])

    supportive = [
        row for row in rows
        if not row["human_primary_role"]
        and (row["llm_stance_toward_meadows"] == "supportive" or "supportive_stance_without_explicit_endorsement" in row["review_reason"])
    ]
    supportive_rows = []
    for row in supportive:
        item = base(row)
        item.update({
            "recommended_human_primary_role": "",
            "recommended_human_stance_toward_seed": "unclear",
            "recommended_human_confidence": "low",
            "recommended_human_notes": "Supportive stance requires explicit endorsement or positive evaluation; review the exact evaluative cue.",
            "safe_to_apply_automatically": "no",
            "needs_manual_review": "yes",
        })
        supportive_rows.append(item)
    write_csv(TABLES / "remaining_supportive_rows_review.csv", supportive_rows)

    groups = defaultdict(list)
    for row in rows:
        groups[row.get("context_group_id", row["context_id"])].append(row)
    boundary_roles = {"historical_framing", "foundational_citation", "sustainability_discourse", "modeling_simulation_reference"}
    boundary = []
    for row in rows:
        fall = fallback(row)
        group_labels = {member["llm_primary_role"] for member in groups[row.get("context_group_id", row["context_id"])]}
        direct_pair = {row["llm_primary_role"], fall} == {"historical_framing", "foundational_citation"}
        involved_disagreement = row["llm_primary_role"] != fall and row["llm_primary_role"] in boundary_roles and fall in boundary_roles
        repeated_inconsistent = len(group_labels) > 1 and bool(group_labels & boundary_roles)
        if direct_pair or involved_disagreement or repeated_inconsistent:
            boundary.append(boundary_recommendation(row, group_labels))
    write_csv(TABLES / "historical_foundational_boundary_review.csv", boundary)
    print(f"Wrote {len(critique)} critique, {len(supportive)} supportive, and {len(boundary)} boundary review rows.")


if __name__ == "__main__":
    main()
