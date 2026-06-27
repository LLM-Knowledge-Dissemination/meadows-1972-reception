#!/usr/bin/env python3
"""Build Paper 1 methods infrastructure from frozen v2.0 outputs.

This script does not run classifications or modify the frozen methodology. It
summarizes existing labels, validation metrics, and audit outcomes.
"""

from __future__ import annotations

import csv
import importlib.util
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
FINAL = ANALYSIS / "data/final"
TABLES = ANALYSIS / "tables"
RESULTS = ANALYSIS / "results"
VALIDATION = ANALYSIS / "validation"


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


def write_md(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pct(n: int | float, d: int | float) -> float:
    return round(float(n) / float(d), 4) if d else 0.0


def clean_bool(value: str) -> str:
    return "true" if str(value).strip().lower() in {"true", "yes", "1"} else "false"


def level_number(level: str) -> int:
    match = re.search(r"Level\s+(\d+)", level or "")
    return int(match.group(1)) if match else 0


def confidence_maps() -> Dict[str, str]:
    confidence: Dict[str, str] = {}

    for row in read_csv(VALIDATION / "router_safe_spotcheck_master_packet.csv"):
        if row.get("context_group_id") and row.get("confidence"):
            confidence[row["context_group_id"]] = row["confidence"]

    rank = {"very_high": 5, "high": 4, "medium_high": 3, "medium": 2, "low_medium": 1, "low": 0}
    for path in [
        VALIDATION / "historical_foundational_packet_A_coded.csv",
        VALIDATION / "historical_foundational_packet_B_coded.csv",
        VALIDATION / "historical_foundational_packet_C_coded.csv",
        VALIDATION / "modeling_validation_coded.csv",
        VALIDATION / "router_safe_batch_A_coded.csv",
        VALIDATION / "bibliography_audit_sample_coded.csv",
    ]:
        for row in read_csv(path):
            context_id = row.get("context_group_id", "")
            candidate = row.get("human_confidence", "")
            if not context_id or not candidate:
                continue
            current = confidence.get(context_id, "")
            if rank.get(candidate, -1) > rank.get(current, -1):
                confidence[context_id] = candidate
    return confidence


def extraction_quality(row: Dict[str, str]) -> str:
    context = (row.get("context_window") or "").strip()
    sentence = (row.get("citation_sentence") or "").strip()
    if not context and not sentence:
        return "missing_context"
    if len(context) < 80:
        return "short_context"
    if row.get("citation_function") == "unclear":
        return "uncertain_or_ocr"
    return "usable_context"


def validation_status(row: Dict[str, str]) -> str:
    level = level_number(row.get("evidence_level", ""))
    if level == 2:
        return "human_reviewed"
    if level == 3:
        return "validated_router_derived"
    if level == 4:
        return "hybrid_accepted_not_human_reviewed"
    if level == 5:
        return "unresolved_gray_zone"
    return "traditional_or_unvalidated"


def build_corpus_dataset() -> List[Dict[str, Any]]:
    source = read_csv(FINAL / "contextual_corpus_final.csv")
    conf = confidence_maps()
    fields = [
        "context_group_id",
        "mention_id",
        "title",
        "year",
        "decade",
        "venue",
        "field_or_venue",
        "citation_sentence",
        "context_window",
        "citation_function",
        "topic_or_discourse_area",
        "stance_toward_seed",
        "classification_source",
        "evidence_level",
        "confidence",
        "uncertainty_flags",
        "needs_human_review",
        "human_review_status",
        "usable_for_substantive_analysis",
        "bibliography_only_flag",
        "extraction_quality_flag",
        "validation_status",
    ]
    rows: List[Dict[str, Any]] = []
    for row in source:
        fn = row.get("citation_function", "")
        out = {field: row.get(field, "") for field in fields}
        out["mention_id"] = row.get("mention_id", "")
        out["confidence"] = conf.get(row.get("context_group_id", ""), "not_recorded")
        out["bibliography_only_flag"] = "true" if fn in {"bibliographic_only", "bibliography_only"} else "false"
        out["extraction_quality_flag"] = extraction_quality(row)
        out["validation_status"] = validation_status(row)
        rows.append(out)

    write_csv(FINAL / "meadows_context_classification.csv", rows, fields)
    write_parquet_if_available(FINAL / "meadows_context_classification.parquet", rows, fields)
    return rows


def write_parquet_if_available(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    if importlib.util.find_spec("pyarrow") is not None:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore

        table = pa.Table.from_pylist([{field: row.get(field, "") for field in fields} for row in rows])
        pq.write_table(table, path)
        return
    if importlib.util.find_spec("pandas") is not None:
        import pandas as pd  # type: ignore

        pd.DataFrame(rows, columns=fields).to_parquet(path, index=False)
        return

    status = path.with_suffix(path.suffix + ".unavailable.txt")
    status.write_text(
        "Parquet output was requested, but no parquet writer is installed "
        "(missing pyarrow/pandas/fastparquet). CSV output is authoritative.\n",
        encoding="utf-8",
    )


def count_rows(rows: List[Dict[str, Any]], field: str, dimension: str) -> List[Dict[str, Any]]:
    counts = Counter((row.get(field, "") or "unknown") for row in rows)
    total = len(rows)
    return [
        {"dimension": dimension, "category": category, "n_contexts": n, "pct_contexts": pct(n, total)}
        for category, n in sorted(counts.items())
    ]


def grouped_by_time(rows: List[Dict[str, Any]], field: str, path: Path) -> None:
    groups: Dict[tuple[str, str], int] = Counter(
        ((row.get(field, "") or "unknown"), (row.get("citation_function", "") or "unknown"))
        for row in rows
    )
    totals = Counter((row.get(field, "") or "unknown") for row in rows)
    out = []
    for (time_value, fn), n in sorted(groups.items()):
        out.append({
            field: time_value,
            "citation_function": fn,
            "n_contexts": n,
            "pct_within_" + field: pct(n, totals[time_value]),
        })
    write_csv(path, out)


def corpus_summaries(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    unique = len({row.get("context_group_id", "") for row in rows if row.get("context_group_id", "")})
    summary = [
        {"metric": "total_context_rows", "value": total},
        {"metric": "unique_context_groups", "value": unique},
        {"metric": "bibliography_only_rows", "value": sum(1 for r in rows if r["bibliography_only_flag"] == "true")},
        {"metric": "needs_human_review_rows", "value": sum(1 for r in rows if r["needs_human_review"] == "true")},
        {"metric": "usable_for_substantive_analysis_rows", "value": sum(1 for r in rows if r["usable_for_substantive_analysis"] == "true")},
        {"metric": "unresolved_gray_zone_rows", "value": sum(1 for r in rows if r["validation_status"] == "unresolved_gray_zone")},
        {"metric": "parquet_status", "value": "created" if (FINAL / "meadows_context_classification.parquet").exists() else "unavailable_no_writer_installed"},
    ]
    for field in [
        "citation_function",
        "evidence_level",
        "classification_source",
        "confidence",
        "needs_human_review",
        "usable_for_substantive_analysis",
        "bibliography_only_flag",
        "validation_status",
    ]:
        for category, n in sorted(Counter((row.get(field, "") or "unknown") for row in rows).items()):
            summary.append({"metric": f"{field}::{category}", "value": n})
    write_csv(TABLES / "corpus_classification_summary.csv", summary)
    grouped_by_time(rows, "year", TABLES / "corpus_classification_by_year.csv")
    grouped_by_time(rows, "decade", TABLES / "corpus_classification_by_decade.csv")
    for field, path in [
        ("citation_function", TABLES / "corpus_classification_by_function.csv"),
        ("evidence_level", TABLES / "corpus_classification_by_evidence_level.csv"),
        ("confidence", TABLES / "corpus_classification_confidence.csv"),
        ("uncertainty_flags", TABLES / "corpus_classification_uncertainty_flags.csv"),
    ]:
        write_csv(path, count_rows(rows, field, field))


def validation_adjusted(rows: List[Dict[str, Any]]) -> None:
    raw = Counter(row.get("citation_function", "unknown") for row in rows)
    metrics = {
        "historical_framing": ("Historical/Foundation boundary agreement", 15, 28, "Boundary agreement is low; direct count adjustment is not recommended."),
        "foundational_citation": ("Historical/Foundation boundary agreement", 15, 28, "Boundary agreement is low; direct count adjustment is not recommended."),
        "modeling_simulation_reference": ("Modeling agreement", 8, 11, "Agreement supports audit-aware use, but corpus-wide adjustment remains sample-dependent."),
        "bibliographic_only": ("Bibliography precision", 16, 20, "Precision estimate applies to bibliography-only positives; adjusted estimate is illustrative."),
        "unclear": ("Router-safe/gray-zone audit evidence", 18, 24, "Unclear cases combine OCR, extraction, and unresolved classification; no defensible adjustment."),
        "other": ("No specific frozen validation metric", 0, 0, "No category-specific adjustment metric available."),
    }
    out = []
    for fn, count in sorted(raw.items()):
        metric, num, den, caveat = metrics.get(fn, ("No specific frozen validation metric", 0, 0, "No defensible adjustment metric available."))
        rate = pct(num, den) if den else ""
        recommend = "yes_precision_adjustment_only" if fn == "bibliographic_only" else "no"
        adjusted = round(count * rate, 1) if fn == "bibliographic_only" and rate != "" else ""
        out.append({
            "citation_function": fn,
            "raw_corpus_count": count,
            "applicable_validation_metric": metric,
            "validation_metric_value": f"{num}/{den} = {round(rate * 100, 1)}%" if den else "not_available",
            "adjusted_estimate_if_defensible": adjusted,
            "uncertainty_caveat": caveat,
            "adjustment_recommended": recommend,
        })
    write_csv(TABLES / "validation_adjusted_corpus_summary.csv", out)


def automation_framework(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    framework = [
        ("citation context extraction", "Extraction inventory and recovery review", "legacy extraction plus recovery packets; recovery helpful 10/11", "short windows; missing adjacent sentence; OCR damage", "automated_with_audit"),
        ("extraction recovery", "Extraction recovery Packet A human review", "helpful 10/11; confidence increased 10/11; uncertainty reduced 10/11", "benefit measured on reviewed subset only", "automated_with_audit"),
        ("bibliography-only detection", "Bibliography audit", "16/20 true bibliography-only = 80.0% precision", "false positives to historical, foundational, and modeling", "automated_with_audit"),
        ("modeling/simulation detection", "Modeling validation", "8/11 agreement = 72.7%; false negatives=0 in reviewed set", "metadata/phrase-level/outcome-only false positives", "hybrid_review_required"),
        ("historical framing", "Historical/foundational boundary validation", "part of 15/28 boundary agreement", "confused with substantive/foundational claims", "hybrid_review_required"),
        ("foundational citation", "Historical/foundational boundary validation", "part of 15/28 boundary agreement", "resource-language and historical reception overlap", "hybrid_review_required"),
        ("historical/foundational boundary resolution", "Six-case plus packets A/B/C adjudication", "28 adjudicated; agreement 53.6%", "boundary ambiguity; router over/under-calls", "human_required"),
        ("topic/discourse classification", "Readiness matrix and validation notes", "topic labels less validated than function labels", "topic labels exploratory and proxy-like", "exploratory_only"),
        ("stance classification", "Readiness matrix and validation notes", "stance mostly neutral/unclear; explicit evidence required", "low variation; hard to validate without text evidence", "exploratory_only"),
        ("corpus-wide deployment", "Final contextual corpus and validation summary", f"{len(rows)} rows classified with evidence levels preserved", "do not pool evidence levels; unresolved cases retained", "automated_with_audit"),
    ]
    out = [
        {
            "task": task,
            "validation_evidence": evidence,
            "empirical_performance": performance,
            "failure_modes": failures,
            "automation_status": status,
        }
        for task, evidence, performance, failures, status in framework
    ]
    write_csv(TABLES / "automation_boundary_framework.csv", out)

    examples = []
    by_function = defaultdict(list)
    for row in rows:
        by_function[row.get("citation_function", "")].append(row)
    task_to_function = {
        "bibliography-only detection": "bibliographic_only",
        "modeling/simulation detection": "modeling_simulation_reference",
        "historical framing": "historical_framing",
        "foundational citation": "foundational_citation",
        "historical/foundational boundary resolution": "historical_framing",
        "topic/discourse classification": "unclear",
        "stance classification": "unclear",
        "corpus-wide deployment": "bibliographic_only",
    }
    for item in out:
        fn = task_to_function.get(item["task"], "")
        candidates = by_function.get(fn, rows)
        chosen = next((r for r in candidates if r.get("citation_sentence") or r.get("context_window")), candidates[0] if candidates else {})
        examples.append({
            "task": item["task"],
            "automation_status": item["automation_status"],
            "context_group_id": chosen.get("context_group_id", ""),
            "citation_function": chosen.get("citation_function", ""),
            "citation_sentence": chosen.get("citation_sentence", ""),
            "example_note": item["failure_modes"],
        })
    write_csv(VALIDATION / "automation_boundary_examples.csv", examples)

    write_md(RESULTS / "automation_boundary_report.md", [
        "# Automation Boundary Report",
        "",
        "Scope: methods-paper audit of which tasks can be automated under the frozen v2.0 methodology.",
        "",
        "| Task | Automation Status | Empirical Performance | Main Failure Modes |",
        "|---|---|---|---|",
        *[
            f"| {r['task']} | {r['automation_status']} | {r['empirical_performance']} | {r['failure_modes']} |"
            for r in out
        ],
        "",
        "The methodology remains frozen; this report summarizes validation evidence only.",
    ])
    return out


def labor_analysis(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    already_human = sum(1 for r in rows if r["validation_status"] == "human_reviewed")
    router_safe = sum(1 for r in rows if r["validation_status"] == "validated_router_derived")
    bibliography_auto = sum(1 for r in rows if r["bibliography_only_flag"] == "true" and r["validation_status"] != "human_reviewed")
    manual_queue_ids = {
        r["context_group_id"]
        for r in rows
        if r["validation_status"] in {"human_reviewed", "unresolved_gray_zone"} or r["needs_human_review"] == "true"
    }
    hybrid_manual = len(manual_queue_ids)
    speeds = [("fast", 45), ("moderate", 90), ("slow", 180)]
    out = []
    for label, seconds in speeds:
        full_hours = total * seconds / 3600
        hybrid_hours = hybrid_manual * seconds / 3600
        avoided = full_hours - hybrid_hours
        out.append({
            "workflow": "fully_manual",
            "time_assumption": label,
            "seconds_per_context": seconds,
            "contexts_requiring_human_labor": total,
            "estimated_hours": round(full_hours, 2),
            "manual_hours_avoided_vs_full_manual": 0,
            "percent_reduction_vs_full_manual": 0,
            "assumptions": "Every corpus row receives manual coding.",
        })
        out.append({
            "workflow": "hybrid_frozen_v2_0",
            "time_assumption": label,
            "seconds_per_context": seconds,
            "contexts_requiring_human_labor": hybrid_manual,
            "estimated_hours": round(hybrid_hours, 2),
            "manual_hours_avoided_vs_full_manual": round(avoided, 2),
            "percent_reduction_vs_full_manual": round(100 * avoided / full_hours, 1) if full_hours else 0,
            "assumptions": "Human labor includes already-reviewed plus unresolved/needs-review rows; router-safe and bibliography-only automated rows reduce review burden.",
        })
    write_csv(TABLES / "human_effort_estimates.csv", out)
    write_md(RESULTS / "labor_reduction_assessment.md", [
        "# Human Labor Reduction Assessment",
        "",
        f"Total corpus rows: {total}.",
        f"Already human-reviewed rows: {already_human}.",
        f"Validated router-derived rows: {router_safe}.",
        f"Non-human-reviewed bibliography-only rows available for automated handling: {bibliography_auto}.",
        f"Hybrid manual-review estimate: {hybrid_manual} rows.",
        "",
        "Time assumptions: fast = 45 seconds/context; moderate = 90 seconds/context; slow = 180 seconds/context.",
        "",
        "Caveats: estimates are planning approximations, not measured timings. Bibliography-only automation uses an 80% precision audit estimate; unresolved and gray-zone contexts remain human-review candidates.",
    ])


def readiness_and_plan() -> None:
    readiness_rows = [
        ("corpus construction", "complete", "Final contextual corpus and corpus-wide classification dataset available", "none", "use frozen corpus for methods tables"),
        ("context extraction", "complete_with_caveat", "Extraction outputs and quality flags available", "document extraction failures", "report extraction quality caveats"),
        ("extraction recovery", "complete_with_caveat", "Recovery review helpful 10/11", "do not infer unreviewed recovery effects", "summarize as audit outcome"),
        ("classifier/router workflow", "complete", "Frozen v2.0 router/prompt/schema package available", "do not modify frozen logic", "document workflow as frozen"),
        ("validation", "complete_for_methods", "Final validation summary reconciled", "some category precision estimates small", "use validation summary table"),
        ("corpus-wide deployment", "complete", "1,590-row classification dataset created", "preserve evidence levels", "use corpus deployment summary"),
        ("automation boundary framework", "complete", "Boundary table and report created", "status is evidence-bound", "include as methods contribution"),
        ("labor reduction analysis", "complete", "Human effort estimates created", "planning estimates only", "include caveats"),
        ("reproducibility package", "complete", "Frozen methodology v2.0 package exists", "parquet writer unavailable in current environment", "reference freeze manifest"),
        ("manuscript figures", "partial", "Substantive figures exist; methods figures still need layout", "avoid Paper 2 interpretation", "prepare methods figure plan"),
        ("manuscript draft", "pending", "Methods artifacts available", "no prose drafted here", "draft after table/figure selection"),
    ]
    write_csv(RESULTS / "paper1_readiness_matrix.csv", [
        {
            "component": c,
            "status": s,
            "evidence_available": e,
            "remaining_work": r,
            "recommended_next_action": a,
        }
        for c, s, e, r, a in readiness_rows
    ])

    plan_rows = [
        ("workflow diagram", "Show frozen v2.0 pipeline and audit points", "analysis/frozen_methodology/v2_0/reproducibility_report.md", "ready", "diagram still needs rendering"),
        ("validation summary table", "Summarize validation evidence", "analysis/tables/final_validation_summary.csv", "ready", "small samples for some categories"),
        ("confusion matrix table", "Show category-specific disagreements", "analysis/tables/historical_foundational_final_confusion_matrix.csv; analysis/tables/modeling_validation_confusion_matrix.csv", "ready", "combine carefully"),
        ("automation boundary table", "Define where automation is acceptable", "analysis/tables/automation_boundary_framework.csv", "ready", "status values are validation-bound"),
        ("extraction recovery table", "Show recovery benefit outcomes", "analysis/tables/extraction_recovery_human_benefit_summary.csv", "ready", "reviewed subset only"),
        ("labor reduction table", "Estimate human time saved", "analysis/tables/human_effort_estimates.csv", "ready", "planning assumptions only"),
        ("corpus deployment summary table", "Describe full classified corpus", "analysis/tables/corpus_classification_summary.csv", "ready", "not Meadows impact results"),
        ("example citation contexts table", "Illustrate automation boundaries", "analysis/validation/automation_boundary_examples.csv", "ready", "examples are illustrative only"),
    ]
    write_csv(RESULTS / "paper1_figure_table_plan.csv", [
        {"item": i, "role_in_paper": role, "source_file": source, "readiness": ready, "caveat": caveat}
        for i, role, source, ready, caveat in plan_rows
    ])


def main() -> None:
    rows = build_corpus_dataset()
    corpus_summaries(rows)
    validation_adjusted(rows)
    automation_framework(rows)
    labor_analysis(rows)
    readiness_and_plan()
    print(f"Corpus-wide classification rows: {len(rows)}")
    print("Citation functions: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(r["citation_function"] for r in rows).items())))
    print("Evidence levels: " + "; ".join(f"{k}={v}" for k, v in sorted(Counter(r["evidence_level"] for r in rows).items())))
    print("Parquet: " + ("created" if (FINAL / "meadows_context_classification.parquet").exists() else "unavailable_no_writer_installed"))


if __name__ == "__main__":
    main()
