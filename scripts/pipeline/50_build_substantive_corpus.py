#!/usr/bin/env python3
"""Build filtered substantive-analysis corpus and source tables."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
FINAL = ANALYSIS / "data/final"
TABLES = ANALYSIS / "tables"
VALIDATION = ANALYSIS / "validation"

ALLOWED_LEVELS = {
    "Level 2: human-reviewed contextual evidence",
    "Level 3: validated deterministic-router evidence",
    "Level 4: hybrid accepted but not human-reviewed",
}
SUBSTANTIVE_FUNCTIONS = {
    "historical_framing",
    "foundational_citation",
    "modeling_simulation_reference",
}


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


def is_substantive(row: Dict[str, str]) -> bool:
    function = row.get("citation_function", "")
    return (
        row.get("usable_for_substantive_analysis", "").lower() == "true"
        and row.get("evidence_level") in ALLOWED_LEVELS
        and function not in {"bibliographic_only", "bibliography_only", "unclear"}
    )


def pct(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def build_substantive() -> List[Dict[str, str]]:
    rows = [row for row in read_csv(FINAL / "contextual_corpus_final.csv") if is_substantive(row)]
    fields = [
        "context_group_id",
        "title",
        "year",
        "decade",
        "venue",
        "field_or_venue",
        "citation_function",
        "topic_or_discourse_area",
        "stance_toward_seed",
        "evidence_level",
        "classification_source",
        "human_review_status",
    ]
    write_csv(FINAL / "substantive_contexts.csv", rows, fields)
    return rows


def summary_tables(rows: List[Dict[str, str]]) -> None:
    total = len(rows)
    out: List[Dict[str, Any]] = [{"summary_dimension": "total_contexts", "category": "all", "n_contexts": total, "pct_contexts": 1 if total else 0}]
    for field, label in [
        ("evidence_level", "evidence_level"),
        ("citation_function", "citation_function"),
        ("decade", "decade"),
        ("venue", "venue"),
        ("field_or_venue", "field"),
    ]:
        counts = Counter(row.get(field, "") or "unknown" for row in rows)
        for category, n in sorted(counts.items()):
            out.append({"summary_dimension": label, "category": category, "n_contexts": n, "pct_contexts": pct(n, total)})
    write_csv(TABLES / "substantive_corpus_summary.csv", out)

    mix: List[Dict[str, Any]] = []
    for fn in ["overall"] + sorted({row["citation_function"] for row in rows}):
        subset = rows if fn == "overall" else [row for row in rows if row["citation_function"] == fn]
        counts = Counter(row["evidence_level"] for row in subset)
        mix.append({
            "citation_function": fn,
            "total_contexts": len(subset),
            "level_2_count": counts["Level 2: human-reviewed contextual evidence"],
            "level_3_count": counts["Level 3: validated deterministic-router evidence"],
            "level_4_count": counts["Level 4: hybrid accepted but not human-reviewed"],
        })
    write_csv(TABLES / "substantive_corpus_evidence_mix.csv", mix)


def distribution(rows: List[Dict[str, str]], group_fields: List[str], path: Path, functions: Iterable[str] | None = None) -> None:
    functions = set(functions or [row["citation_function"] for row in rows])
    subset = [row for row in rows if row["citation_function"] in functions]
    totals = Counter(tuple(row.get(field, "") or "unknown" for field in group_fields) for row in subset)
    counts = Counter(tuple(row.get(field, "") or "unknown" for field in group_fields + ["citation_function"]) for row in subset)
    out = []
    for key, n in sorted(counts.items()):
        group_key = key[:len(group_fields)]
        record = dict(zip(group_fields, group_key))
        record.update({
            "citation_function": key[-1],
            "n_contexts": n,
            "pct_contexts": pct(n, totals[group_key]),
        })
        out.append(record)
    write_csv(path, out)


def figure_sources(rows: List[Dict[str, str]]) -> None:
    fig_rows = [row for row in rows if row["citation_function"] in SUBSTANTIVE_FUNCTIONS]
    total = len(fig_rows)
    write_csv(TABLES / "figure1_citation_function_distribution.csv", [
        {
            "citation_function": fn,
            "n_contexts": n,
            "pct_contexts": pct(n, total),
        }
        for fn, n in sorted(Counter(row["citation_function"] for row in fig_rows).items())
    ])
    distribution(fig_rows, ["decade"], TABLES / "figure2_citation_function_by_decade.csv", SUBSTANTIVE_FUNCTIONS)
    write_csv(TABLES / "figure3_modeling_persistence.csv", [
        {
            "context_group_id": row["context_group_id"],
            "year": row["year"],
            "decade": row["decade"],
            "field": row["field_or_venue"],
            "venue": row["venue"],
            "evidence_level": row["evidence_level"],
        }
        for row in rows if row["citation_function"] == "modeling_simulation_reference"
    ])
    distribution(fig_rows, ["field_or_venue"], TABLES / "figure4_field_function_distribution.csv", SUBSTANTIVE_FUNCTIONS)


def claim_support(rows: List[Dict[str, str]]) -> None:
    readiness = {row["claim"]: row for row in read_csv(TABLES / "substantive_analysis_readiness.csv")}
    claim_names = [
        "traditional diffusion",
        "venue diffusion",
        "field diffusion",
        "historical framing prevalence",
        "foundational citation prevalence",
        "modeling persistence",
        "foundational-to-historical transition",
        "topic distributions",
        "stance distributions",
    ]
    out = []
    for claim in claim_names:
        readiness_key = "topic/discourse distributions" if claim == "topic distributions" else claim
        r = readiness.get(readiness_key, {})
        if claim == "historical framing prevalence":
            subset = [row for row in rows if row["citation_function"] == "historical_framing"]
        elif claim == "foundational citation prevalence":
            subset = [row for row in rows if row["citation_function"] == "foundational_citation"]
        elif claim == "modeling persistence":
            subset = [row for row in rows if row["citation_function"] == "modeling_simulation_reference"]
        elif claim == "foundational-to-historical transition":
            subset = [row for row in rows if row["citation_function"] in {"foundational_citation", "historical_framing"}]
        else:
            subset = rows
        levels = Counter(row["evidence_level"] for row in subset)
        level_distribution = " | ".join(
            f"{level}={levels[level]}"
            for level in [
                "Level 2: human-reviewed contextual evidence",
                "Level 3: validated deterministic-router evidence",
                "Level 4: hybrid accepted but not human-reviewed",
            ]
        )
        out.append({
            "claim_name": claim,
            "evidence_available": len(subset),
            "evidence_level_distribution": level_distribution,
            "validation_strength": r.get("basis", ""),
            "readiness_status": r.get("readiness", "not_ready"),
        })
    write_csv(TABLES / "claim_support_matrix.csv", out)


def human_confidence_rank(value: str) -> int:
    return {
        "very_high": 5,
        "high": 4,
        "medium_high": 3,
        "medium": 2,
        "low_medium": 1,
        "low": 0,
    }.get((value or "").strip().lower(), -1)


def human_confidence_by_context() -> Dict[str, str]:
    confidence: Dict[str, str] = {}
    for path in [
        VALIDATION / "historical_foundational_packet_A_coded.csv",
        VALIDATION / "historical_foundational_packet_B_coded.csv",
        VALIDATION / "historical_foundational_packet_C_coded.csv",
        VALIDATION / "modeling_validation_coded.csv",
        VALIDATION / "router_safe_batch_A_coded.csv",
    ]:
        for row in read_csv(path):
            context_id = row.get("context_group_id", "")
            if not context_id:
                continue
            current = confidence.get(context_id, "")
            candidate = row.get("human_confidence", "")
            if human_confidence_rank(candidate) > human_confidence_rank(current):
                confidence[context_id] = candidate
    return confidence


def exemplars(rows: List[Dict[str, str]]) -> None:
    confidence = human_confidence_by_context()
    corpus_rows = [row for row in read_csv(FINAL / "contextual_corpus_final.csv") if is_substantive(row)]
    text_by_context = {
        row["context_group_id"]: row.get("citation_sentence", "")
        for row in corpus_rows
        if row.get("context_group_id")
    }
    out = []
    for fn in sorted(SUBSTANTIVE_FUNCTIONS):
        subset = [row for row in rows if row.get("citation_function") == fn and row.get("human_review_status") == "human_reviewed"]
        subset.sort(key=lambda row: (-human_confidence_rank(confidence.get(row.get("context_group_id", ""), "")), row.get("year", ""), row.get("context_group_id", "")))
        for row in subset[:10]:
            out.append({
                "context_group_id": row.get("context_group_id", ""),
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "citation_sentence": text_by_context.get(row.get("context_group_id", ""), ""),
                "citation_function": fn,
            })
    write_csv(TABLES / "exemplar_contexts.csv", out)


def main() -> None:
    rows = build_substantive()
    summary_tables(rows)
    figure_sources(rows)
    claim_support(rows)
    exemplars(rows)
    print(f"Substantive contexts: {len(rows)}")
    print("Evidence levels: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(row["evidence_level"] for row in rows).items())))
    print("Citation functions: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(row["citation_function"] for row in rows).items())))


if __name__ == "__main__":
    main()
