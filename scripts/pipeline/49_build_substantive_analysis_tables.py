#!/usr/bin/env python3
"""Build analysis-ready substantive tables from frozen v2.0 methodology outputs."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
VALIDATION = ANALYSIS / "validation"
TABLES = ANALYSIS / "tables"
FINAL = ANALYSIS / "data/final"
DERIVED = ANALYSIS / "data/derived"

FUNCTIONS = [
    "historical_framing",
    "foundational_citation",
    "modeling_simulation_reference",
    "bibliographic_only",
    "unclear",
    "other",
]


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


def normalize_function(value: str) -> str:
    value = (value or "").strip()
    if value in {"bibliography_only", "bibliographic_only"}:
        return "bibliographic_only"
    if value in {"historical_framing", "foundational_citation", "modeling_simulation_reference", "unclear"}:
        return value
    if not value:
        return "unclear"
    return "other"


def decade(year: Any) -> str:
    try:
        y = int(float(str(year).strip()))
        return f"{(y // 10) * 10}s"
    except Exception:
        return "unknown"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def row_base(row: Dict[str, str]) -> Dict[str, Any]:
    year = row.get("year", "")
    return {
        "context_group_id": row.get("context_group_id", ""),
        "title": row.get("title", ""),
        "year": year,
        "decade": row.get("decade") or decade(year),
        "venue": row.get("venue", ""),
        "field_or_venue": row.get("field_or_venue") or row.get("venue", ""),
        "citation_sentence": row.get("citation_sentence", ""),
        "context_window": row.get("context_window") or row.get("snippet_clean", ""),
    }


def priority(level: int) -> int:
    return {2: 5, 3: 4, 4: 3, 1: 2, 5: 1}.get(level, 0)


def upsert(records: Dict[str, Dict[str, Any]], row: Dict[str, Any]) -> None:
    key = row.get("context_group_id", "")
    if not key:
        return
    current = records.get(key)
    if current is None or priority(int(row["evidence_level_number"])) > priority(int(current["evidence_level_number"])):
        records[key] = row
        return
    if current and priority(int(row["evidence_level_number"])) == priority(int(current["evidence_level_number"])):
        # Prefer rows with more context text, keeping the same label precedence.
        if len(clean(row.get("context_window", ""))) > len(clean(current.get("context_window", ""))):
            records[key] = row


def make_record(row: Dict[str, str], function: str, topic: str, stance: str, source: str, level: int, review: str,
                uncertainty: str = "none", needs_review: str = "false") -> Dict[str, Any]:
    base = row_base(row)
    function = normalize_function(function)
    usable = level in {2, 3} and function not in {"unclear"}
    base.update({
        "citation_function": function,
        "topic_or_discourse_area": topic or "unclear",
        "stance_toward_seed": stance or "neutral_descriptive",
        "classification_source": source,
        "evidence_level": {
            1: "Level 1: traditional bibliometric evidence",
            2: "Level 2: human-reviewed contextual evidence",
            3: "Level 3: validated deterministic-router evidence",
            4: "Level 4: hybrid accepted but not human-reviewed",
            5: "Level 5: unresolved gray-zone / not usable",
        }[level],
        "evidence_level_number": level,
        "human_review_status": review,
        "uncertainty_flags": uncertainty or "none",
        "needs_human_review": str(needs_review).lower(),
        "usable_for_substantive_analysis": str(usable).lower(),
    })
    return base


def add_human_coded(records: Dict[str, Dict[str, Any]]) -> None:
    files = [
        VALIDATION / "historical_foundational_packet_A_coded.csv",
        VALIDATION / "historical_foundational_packet_B_coded.csv",
        VALIDATION / "historical_foundational_packet_C_coded.csv",
        VALIDATION / "historical_foundational_six_case_review.csv",
        VALIDATION / "modeling_validation_coded.csv",
        VALIDATION / "router_safe_batch_A_coded.csv",
    ]
    for path in files:
        for row in read_csv(path):
            role = row.get("human_primary_role") or row.get("consensus_primary_role")
            if role:
                upsert(records, make_record(
                    row,
                    role,
                    row.get("human_topic_or_discourse_area") or row.get("consensus_topic_or_discourse_area") or row.get("router_topic", ""),
                    row.get("human_stance_toward_seed") or row.get("consensus_stance_toward_seed") or row.get("router_stance", ""),
                    path.relative_to(ROOT).as_posix(),
                    2,
                    "human_reviewed",
                    "none",
                    "false",
                ))

    for row in read_csv(VALIDATION / "bibliography_audit_sample_coded.csv"):
        role = "bibliographic_only" if row.get("human_is_bibliography_only") == "yes" else row.get("human_corrected_primary_role", "unclear")
        pseudo = dict(row)
        pseudo.setdefault("title", "")
        pseudo.setdefault("year", "")
        pseudo.setdefault("venue", "")
        upsert(records, make_record(
            pseudo,
            role,
            "unclear",
            "neutral_descriptive",
            "analysis/validation/bibliography_audit_sample_coded.csv",
            2,
            "human_reviewed",
            "none",
            "false",
        ))


def add_router_safe(records: Dict[str, Dict[str, Any]]) -> None:
    for row in read_csv(VALIDATION / "router_safe_spotcheck_master_packet.csv"):
        if row.get("context_group_id") in records:
            continue
        upsert(records, make_record(
            row,
            row.get("router_primary_role", ""),
            row.get("router_topic", ""),
            row.get("router_stance", ""),
            "analysis/validation/router_safe_spotcheck_master_packet.csv",
            3,
            "router_safe_not_human_reviewed",
            "bibliography_precision_caveat" if normalize_function(row.get("router_primary_role", "")) == "bibliographic_only" else "none",
            "false",
        ))


def add_hybrid(records: Dict[str, Dict[str, Any]]) -> None:
    for path in [
        ANALYSIS / "data/llm_output/v2/v2_hybrid_pilot100_classifications.csv",
        ANALYSIS / "data/llm_output/v2/v2_regression2_classifications.csv",
        ANALYSIS / "data/llm_output/v2/v2_hybrid_regression1_classifications.csv",
    ]:
        for row in read_csv(path):
            if row.get("context_group_id") in records:
                continue
            valid = row.get("classification_status") in {"initial_valid", "router_valid"} or row.get("deterministically_valid", "").lower() == "true"
            level = 4 if valid and row.get("classification_source") == "llm" else (3 if row.get("classification_source") == "router" else 5)
            upsert(records, make_record(
                row,
                row.get("citation_function", ""),
                row.get("topic_or_discourse_area", ""),
                row.get("stance_toward_seed", ""),
                path.relative_to(ROOT).as_posix(),
                level,
                "hybrid_accepted_not_human_reviewed" if level == 4 else ("router_accepted_not_human_reviewed" if level == 3 else "unresolved_or_rejected"),
                row.get("uncertainty_flags", ""),
                row.get("needs_human_review", "false"),
            ))


def add_traditional_contexts(records: Dict[str, Dict[str, Any]]) -> None:
    # Legacy extraction contexts are retained as Level 1 structural evidence only.
    for row in read_csv(ANALYSIS / "data/processed/citation_contexts_enriched.csv"):
        context_id = row.get("context_id") or row.get("hit_id") or row.get("snippet_hash")
        if not context_id:
            continue
        synthetic = f"legacy_{context_id}"
        if synthetic in records:
            continue
        pseudo = {
            "context_group_id": synthetic,
            "title": row.get("canonical_title", ""),
            "year": row.get("year", ""),
            "venue": row.get("venue", ""),
            "field_or_venue": row.get("venue", ""),
            "citation_sentence": row.get("sentence", ""),
            "context_window": row.get("surrounding_sentence_window") or row.get("snippet", ""),
        }
        role = "bibliographic_only" if row.get("citation_section") == "BIBLIO" or row.get("mention_type") == "bibliography_only" else "unclear"
        upsert(records, make_record(
            pseudo,
            role,
            "unclear",
            "neutral_descriptive",
            "analysis/data/processed/citation_contexts_enriched.csv",
            1,
            "not_human_reviewed_traditional_context",
            "traditional_only",
            "true" if role == "unclear" else "false",
        ))


def build_corpus() -> List[Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    add_traditional_contexts(records)
    add_hybrid(records)
    add_router_safe(records)
    add_human_coded(records)
    rows = list(records.values())
    rows.sort(key=lambda r: (str(r.get("year", "")), r.get("context_group_id", "")))
    fields = [
        "context_group_id", "title", "year", "decade", "venue", "field_or_venue",
        "citation_sentence", "context_window", "citation_function", "topic_or_discourse_area",
        "stance_toward_seed", "classification_source", "evidence_level",
        "human_review_status", "uncertainty_flags", "needs_human_review",
        "usable_for_substantive_analysis",
    ]
    FINAL.mkdir(parents=True, exist_ok=True)
    write_csv(FINAL / "contextual_corpus_final.csv", rows, fields)
    return rows


def evidence_view(rows: List[Dict[str, Any]], view: str) -> List[Dict[str, Any]]:
    if view == "all_evidence_levels":
        return rows
    if view == "level_2_only":
        return [r for r in rows if int(r["evidence_level_number"]) == 2]
    if view == "level_2_plus_3":
        return [r for r in rows if int(r["evidence_level_number"]) in {2, 3}]
    if view == "excluding_bibliography_only":
        return [r for r in rows if r["citation_function"] != "bibliographic_only"]
    return rows


def grouped_counts(rows: List[Dict[str, Any]], group_fields: List[str], path: Path, include_views: bool = True) -> None:
    out = []
    views = ["all_evidence_levels", "level_2_only", "level_2_plus_3", "excluding_bibliography_only"] if include_views else ["all_evidence_levels"]
    for view in views:
        subset = evidence_view(rows, view)
        totals = Counter(tuple(r.get(f, "") for f in group_fields) for r in subset)
        counts = Counter(tuple(r.get(f, "") for f in group_fields + ["citation_function"]) for r in subset)
        for key, n in sorted(counts.items()):
            base = dict(zip(group_fields, key[:len(group_fields)]))
            fn = key[-1]
            total = totals[key[:len(group_fields)]]
            base.update({"evidence_view": view, "citation_function": fn, "n_contexts": n, "pct_contexts": round(n / total, 4) if total else 0})
            out.append(base)
    write_csv(path, out)


def foundational_historical(rows: List[Dict[str, Any]]) -> None:
    subset = [r for r in rows if r["citation_function"] in {"foundational_citation", "historical_framing"}]
    totals = Counter(r["decade"] for r in subset)
    out = []
    for (dec, fn), n in sorted(Counter((r["decade"], r["citation_function"]) for r in subset).items()):
        group = [r for r in subset if r["decade"] == dec and r["citation_function"] == fn]
        levels = Counter(r["evidence_level"] for r in group)
        out.append({
            "analysis_label": "hypothesis_testing_dataset_not_transition_claim",
            "decade": dec,
            "citation_function": fn,
            "n_contexts": n,
            "pct_within_foundational_historical": round(n / totals[dec], 4) if totals[dec] else 0,
            "evidence_level_composition": " | ".join(f"{k}={v}" for k, v in sorted(levels.items())),
            "n_human_reviewed": sum(1 for r in group if int(r["evidence_level_number"]) == 2),
            "n_router_derived": sum(1 for r in group if int(r["evidence_level_number"]) == 3),
            "n_unresolved": sum(1 for r in group if int(r["evidence_level_number"]) == 5),
        })
    write_csv(TABLES / "foundational_historical_by_decade.csv", out)


def modeling_table(rows: List[Dict[str, Any]]) -> None:
    out = [
        {
            "year": r["year"],
            "decade": r["decade"],
            "venue": r["venue"],
            "field_or_venue": r["field_or_venue"],
            "evidence_level": r["evidence_level"],
            "context_group_id": r["context_group_id"],
            "citation_sentence": r["citation_sentence"],
        }
        for r in rows if r["citation_function"] == "modeling_simulation_reference"
    ]
    write_csv(TABLES / "modeling_references_by_decade.csv", out)


def body_biblio(rows: List[Dict[str, Any]]) -> None:
    out = []
    for (level, status), n in sorted(Counter((r["evidence_level"], "bibliography_only" if r["citation_function"] == "bibliographic_only" else ("uncertain" if r["citation_function"] == "unclear" else "body_text_context")) for r in rows).items()):
        out.append({
            "context_type": status,
            "evidence_level": level,
            "n_contexts": n,
            "bibliography_precision_caveat": "bibliography audit precision approximately 80%" if status == "bibliography_only" else "",
        })
    write_csv(TABLES / "body_vs_bibliography_contexts.csv", out)


def network_bridge(rows: List[Dict[str, Any]]) -> None:
    top_refs = read_csv(TABLES / "top_cited_references.csv")
    function_counts = Counter(r["citation_function"] for r in rows if r["usable_for_substantive_analysis"] == "true")
    summary = " | ".join(f"{k}={v}" for k, v in sorted(function_counts.items()))
    out = []
    for ref in top_refs[:100]:
        rec = dict(ref)
        rec["contextual_citation_function_summary_available"] = "corpus_level_only"
        rec["usable_context_function_counts"] = summary
        rec["network_caution"] = "OpenAlex-derived networks are preliminary; do not infer cluster meaning from context summary alone."
        out.append(rec)
    write_csv(TABLES / "contextual_network_bridge.csv", out)


def readiness(rows: List[Dict[str, Any]]) -> None:
    usable = [r for r in rows if r["usable_for_substantive_analysis"] == "true"]
    level2 = [r for r in rows if int(r["evidence_level_number"]) == 2]
    rows_out = [
        ("traditional diffusion", "ready_for_analysis", "Traditional bibliometric/context-extraction evidence exists; preserve coverage caveats."),
        ("venue diffusion", "analyze_with_caveat", "Venue values available, but contextual labels are mixed evidence-level."),
        ("field diffusion", "exploratory_only", "Field labels are incomplete/proxy via field_or_venue."),
        ("historical framing prevalence", "analyze_with_caveat", f"{sum(1 for r in usable if r['citation_function']=='historical_framing')} usable contexts; boundary routing caveat applies."),
        ("foundational citation prevalence", "analyze_with_caveat", f"{sum(1 for r in usable if r['citation_function']=='foundational_citation')} usable contexts; boundary routing caveat applies."),
        ("foundational-to-historical transition", "exploratory_only", "Decade table prepared as hypothesis-testing dataset, not transition evidence."),
        ("modeling persistence", "analyze_with_caveat", f"{sum(1 for r in usable if r['citation_function']=='modeling_simulation_reference')} usable modeling contexts; explicit-model evidence strongest."),
        ("bibliography-only structural patterns", "analyze_with_caveat", "Bibliography audit precision is 80%; structural table available with caveat."),
        ("topic/discourse distributions", "exploratory_only", "Topic labels less validated than citation function labels."),
        ("stance distributions", "exploratory_only", "Stance is mostly neutral/unclear and requires explicit evidence."),
    ]
    write_csv(TABLES / "substantive_analysis_readiness.csv", [
        {"claim": claim, "readiness": status, "basis": basis, "n_level2_contexts": len(level2), "n_usable_contexts": len(usable)}
        for claim, status, basis in rows_out
    ])


def main() -> None:
    rows = build_corpus()
    grouped_counts(rows, ["year"], TABLES / "citation_function_by_year.csv")
    grouped_counts(rows, ["decade"], TABLES / "citation_function_by_decade.csv")
    foundational_historical(rows)
    modeling_table(rows)
    grouped_counts(rows, ["venue"], TABLES / "citation_function_by_venue.csv", include_views=False)
    grouped_counts(rows, ["field_or_venue"], TABLES / "citation_function_by_field_or_venue.csv", include_views=False)
    body_biblio(rows)
    network_bridge(rows)
    readiness(rows)
    print(f"Final contextual corpus rows: {len(rows)}")
    print("Evidence levels: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(r["evidence_level"] for r in rows).items())))
    print("Citation functions: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(r["citation_function"] for r in rows).items())))


if __name__ == "__main__":
    main()
