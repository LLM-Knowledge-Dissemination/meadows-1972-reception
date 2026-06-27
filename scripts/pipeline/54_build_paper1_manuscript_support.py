#!/usr/bin/env python3
"""Create Paper 1 manuscript-support tables and planning files.

Reads existing validation and methods outputs only. Does not modify frozen
methodology, validation labels, or corpus classifications.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis"
TABLES = ANALYSIS / "tables"
RESULTS = ANALYSIS / "results"
VALIDATION = ANALYSIS / "validation"
PAPER1 = ROOT / "paper1"
PAPER1_TABLES = TABLES / "paper1"


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


def first_example(rows: List[Dict[str, str]], *fields: str) -> str:
    for row in rows:
        for field in fields:
            value = (row.get(field) or "").strip()
            if value:
                return value
    return "No representative example available in current validation files."


def taxonomy() -> List[Dict[str, Any]]:
    hf = read_csv(TABLES / "historical_foundational_final_summary.csv")
    hf_summary = hf[0] if hf else {}
    hf_rows = read_csv(TABLES / "historical_foundational_final_agreement.csv")
    biblio_errors = read_csv(TABLES / "bibliography_audit_error_inventory.csv")
    router_errors = read_csv(TABLES / "router_safe_batch_A_error_inventory.csv")
    modeling_errors = read_csv(TABLES / "modeling_validation_error_inventory.csv")
    recovery = read_csv(TABLES / "extraction_recovery_validation_dataset.csv")
    before_after = read_csv(TABLES / "extraction_recovery_before_after.csv")

    bibliography_ids = {
        row.get("context_group_id", "")
        for row in biblio_errors + router_errors
        if "bibliography" in (row.get("false_positive_pattern", "") + row.get("error_family", "") + row.get("notes", ""))
    }
    modeling_false_positive_rows = [
        row for row in modeling_errors
        if row.get("agreement_yes_no") == "no"
        and row.get("router_primary_role") == "modeling_simulation_reference"
        and row.get("human_primary_role") != "modeling_simulation_reference"
    ]
    ocr_rows = [row for row in recovery if row.get("failure_mode") == "ocr_or_text_quality" or "ocr" in row.get("evidence_quality_before", "")]
    short_rows = [row for row in recovery if row.get("failure_mode") == "short_context" or "short" in row.get("evidence_quality_before", "")]
    missing_adjacent_rows = [row for row in before_after if row.get("adjacent_sentence_before_present") == "false"]
    extraction_candidate_rows = recovery
    mixed_rows = [
        row for row in hf_rows
        if "Mixed" in row.get("notes", "") or "mixed" in row.get("notes", "") or row.get("confidence") in {"medium", "low_medium"}
    ]

    rows = [
        {
            "failure_type": "historical_as_foundational",
            "frequency": hf_summary.get("foundational_to_historical", "unknown"),
            "representative_example": first_example(
                [r for r in hf_rows if r.get("router_primary_role") == "foundational_citation" and r.get("human_primary_role") == "historical_framing"],
                "notes",
            ),
            "impact_severity": "high",
            "mitigation_strategy": "Human adjudication for historical/foundational boundary cases; preserve boundary caveat.",
        },
        {
            "failure_type": "foundational_as_historical",
            "frequency": hf_summary.get("historical_to_foundational", "unknown"),
            "representative_example": first_example(
                [r for r in hf_rows if r.get("router_primary_role") == "historical_framing" and r.get("human_primary_role") == "foundational_citation"],
                "notes",
            ),
            "impact_severity": "high",
            "mitigation_strategy": "Route resource/limits premise cases to human review; do not rely on chronology cues alone.",
        },
        {
            "failure_type": "bibliography_false_positive",
            "frequency": len({i for i in bibliography_ids if i}) if bibliography_ids else "unknown",
            "representative_example": first_example(biblio_errors + router_errors, "notes", "disagreement_type", "false_positive_pattern"),
            "impact_severity": "high",
            "mitigation_strategy": "Audit bibliography-only assignments; retain 80% precision caveat.",
        },
        {
            "failure_type": "modeling_false_positive",
            "frequency": len(modeling_false_positive_rows),
            "representative_example": first_example(modeling_false_positive_rows, "notes", "disagreement_type"),
            "impact_severity": "medium",
            "mitigation_strategy": "Require explicit model-process evidence; send phrase-level/model-title cases to review.",
        },
        {
            "failure_type": "modeling_false_negative",
            "frequency": "0",
            "representative_example": "No false negatives observed in the 11-row modeling validation set.",
            "impact_severity": "medium",
            "mitigation_strategy": "Continue audit checks before corpus-wide recall claims.",
        },
        {
            "failure_type": "OCR_damage",
            "frequency": len(ocr_rows) if ocr_rows else "unknown",
            "representative_example": first_example(ocr_rows, "original_context", "repaired_context"),
            "impact_severity": "high",
            "mitigation_strategy": "Use extraction recovery and mark unresolved OCR-damaged contexts as not usable.",
        },
        {
            "failure_type": "short_context",
            "frequency": len(short_rows) if short_rows else "unknown",
            "representative_example": first_example(short_rows, "original_context", "repaired_context"),
            "impact_severity": "medium",
            "mitigation_strategy": "Expand context windows where possible; mark short contexts for review.",
        },
        {
            "failure_type": "missing_adjacent_sentence",
            "frequency": len(missing_adjacent_rows) if missing_adjacent_rows else "unknown",
            "representative_example": first_example(missing_adjacent_rows, "context_group_id", "failure_mode"),
            "impact_severity": "medium",
            "mitigation_strategy": "Recovery pass should restore adjacent sentence when available.",
        },
        {
            "failure_type": "extraction_failure",
            "frequency": len(extraction_candidate_rows) if extraction_candidate_rows else "unknown",
            "representative_example": first_example(extraction_candidate_rows, "failure_mode", "original_context"),
            "impact_severity": "high",
            "mitigation_strategy": "Separate extraction-quality validation from classification accuracy.",
        },
        {
            "failure_type": "topic_ambiguity",
            "frequency": "unknown",
            "representative_example": "Topic labels were assessed as less validated than function labels in readiness materials.",
            "impact_severity": "medium",
            "mitigation_strategy": "Treat topic/discourse labels as exploratory until directly validated.",
        },
        {
            "failure_type": "stance_ambiguity",
            "frequency": "unknown",
            "representative_example": "Stance labels were mostly neutral/unclear and require explicit evidence.",
            "impact_severity": "medium",
            "mitigation_strategy": "Avoid stance claims without direct validation and exemplar review.",
        },
        {
            "failure_type": "mixed_function_citation",
            "frequency": len(mixed_rows) if mixed_rows else "unknown",
            "representative_example": first_example(mixed_rows, "notes"),
            "impact_severity": "medium",
            "mitigation_strategy": "Use adjudication notes and confidence flags; avoid forcing single-function claims when mixed.",
        },
        {
            "failure_type": "other",
            "frequency": "unknown",
            "representative_example": "No systematic count available for residual errors.",
            "impact_severity": "low",
            "mitigation_strategy": "Document as residual category; do not quantify without audit evidence.",
        },
    ]
    write_csv(RESULTS / "error_taxonomy.csv", rows)
    write_md(RESULTS / "error_taxonomy_summary.md", [
        "# Error Taxonomy Summary",
        "",
        "Scope: observed failure modes from validation and adjudication files. Counts are included only where available from project tables.",
        "",
        "| Failure Type | Frequency | Severity | Mitigation |",
        "|---|---:|---|---|",
        *[
            f"| {r['failure_type']} | {r['frequency']} | {r['impact_severity']} | {r['mitigation_strategy']} |"
            for r in rows
        ],
        "",
        "Rows marked `unknown` do not have a defensible count in the current validation record.",
    ])
    return rows


def publication_tables(error_rows: List[Dict[str, Any]]) -> None:
    corpus_summary = read_csv(TABLES / "corpus_classification_summary.csv")
    validation_summary = read_csv(TABLES / "final_validation_summary.csv")
    automation = read_csv(TABLES / "automation_boundary_framework.csv")
    labor = read_csv(TABLES / "human_effort_estimates.csv")

    core_metrics = {
        "total_context_rows",
        "unique_context_groups",
        "bibliography_only_rows",
        "needs_human_review_rows",
        "usable_for_substantive_analysis_rows",
        "unresolved_gray_zone_rows",
        "parquet_status",
    }
    table1 = [row for row in corpus_summary if row.get("metric") in core_metrics or row.get("metric", "").startswith(("citation_function::", "evidence_level::"))]
    write_csv(PAPER1_TABLES / "paper1_table1_corpus_summary.csv", table1)

    table2 = [
        {
            "validation_area": row.get("validation_area", ""),
            "reviewed_rows": row.get("reviewed_rows", ""),
            "agreement_or_primary_metric": row.get("primary_metric", ""),
            "major_error_modes": row.get("major_error_modes", ""),
            "use_caveat": row.get("exploratory_or_not_for_corpus_claims", ""),
        }
        for row in validation_summary
    ]
    write_csv(PAPER1_TABLES / "paper1_table2_validation_metrics.csv", table2)

    write_csv(PAPER1_TABLES / "paper1_table3_automation_boundary.csv", automation)
    write_csv(PAPER1_TABLES / "paper1_table4_error_taxonomy.csv", error_rows)
    write_csv(PAPER1_TABLES / "paper1_table5_labor_reduction.csv", labor)


def manuscript_outline() -> None:
    write_md(PAPER1 / "manuscript_outline.md", [
        "# Paper 1 Manuscript Outline",
        "",
        "## 1 Introduction",
        "",
        "- Problem",
        "- Literature gap",
        "- Contextual bibliometrics challenge",
        "- Contribution",
        "",
        "## 2 Methods",
        "",
        "- Corpus",
        "- Extraction",
        "- Recovery",
        "- Router",
        "- Classification",
        "- Validation",
        "- Adjudication",
        "",
        "## 3 Results",
        "",
        "- Validation",
        "- Automation boundary",
        "- Corpus deployment",
        "- Labor reduction",
        "",
        "## 4 Discussion",
        "",
        "- Automation limits",
        "- Human-in-the-loop workflows",
        "- Implications",
        "",
        "## 5 Limitations",
        "",
        "- Historical/foundational ambiguity",
        "- Topic labels",
        "- Stance labels",
        "- Corpus-specific limitations",
        "",
        "## 6 Conclusion",
        "",
        "- Methods contribution",
        "- Validation-based automation boundary",
        "- Reproducible frozen-methodology package",
        "- Next-step empirical applications",
    ])


def crosswalk_and_journals() -> None:
    crosswalk = [
        ("Introduction", "Table 1", "Establish corpus scale and evidence levels", "ready", "analysis/tables/paper1/paper1_table1_corpus_summary.csv"),
        ("Methods", "Figure 1", "Show frozen workflow from corpus to deployment", "ready", "analysis/figures/paper1/paper1_figure1_workflow.png"),
        ("Methods", "Table 2", "Summarize validation metrics", "ready", "analysis/tables/paper1/paper1_table2_validation_metrics.csv"),
        ("Results", "Figure 2", "Visualize validation outcomes", "ready", "analysis/figures/paper1/paper1_figure2_validation_summary.png"),
        ("Results", "Figure 3", "Visualize automation boundary status", "ready", "analysis/figures/paper1/paper1_figure3_automation_boundary.png"),
        ("Results", "Figure 4", "Compare manual and hybrid labor estimates", "ready", "analysis/figures/paper1/paper1_figure4_labor_reduction.png"),
        ("Results", "Table 3", "Document task-level automation boundary", "ready", "analysis/tables/paper1/paper1_table3_automation_boundary.csv"),
        ("Results", "Table 4", "Document error taxonomy", "ready", "analysis/tables/paper1/paper1_table4_error_taxonomy.csv"),
        ("Results", "Table 5", "Document labor reduction assumptions", "ready", "analysis/tables/paper1/paper1_table5_labor_reduction.csv"),
    ]
    write_csv(PAPER1 / "figure_table_crosswalk.csv", [
        {"section": s, "figure_or_table": ft, "purpose": p, "readiness": r, "source_file": src}
        for s, ft, p, r, src in crosswalk
    ])

    journals = [
        ("Scientometrics", "high", "medium_high", "high", "high", 1),
        ("Journal of Informetrics", "medium_high", "medium", "high", "high", 2),
        ("Quantitative Science Studies", "medium_high", "medium_high", "high", "very_high", 3),
        ("Research Evaluation", "medium", "medium", "medium_high", "medium", 4),
        ("Digital Scholarship in the Humanities", "medium", "high", "medium", "medium", 5),
        ("Journal of Documentation", "medium", "medium", "medium", "medium", 6),
    ]
    write_csv(PAPER1 / "journal_fit_matrix.csv", [
        {
            "journal": journal,
            "topical_fit": topical,
            "novelty_fit": novelty,
            "methods_fit": methods,
            "estimated_competitiveness": comp,
            "recommended_rank": rank,
        }
        for journal, topical, novelty, methods, comp, rank in journals
    ])


def update_readiness() -> None:
    path = RESULTS / "paper1_readiness_matrix.csv"
    rows = read_csv(path)
    updates = {
        "manuscript figures": ("complete", "Paper 1 figure package created", "figure aesthetics may still need journal-specific sizing", "review figures for target journal specs"),
        "manuscript draft": ("outline_complete", "Bullet outline and crosswalk created", "full prose draft not yet written", "draft methods-paper text from outline"),
    }
    seen = set()
    for row in rows:
        component = row.get("component", "")
        if component in updates:
            row["status"], row["evidence_available"], row["remaining_work"], row["recommended_next_action"] = updates[component]
            seen.add(component)
    additions = {
        "table package": ("complete", "Paper 1 tables 1-5 created", "formatting may need journal-specific changes", "review table widths"),
        "manuscript package": ("outline_complete", "Outline, crosswalk, journal fit matrix created", "full manuscript prose not drafted", "select target journal and draft"),
    }
    for component, values in additions.items():
        if component not in seen and not any(r.get("component") == component for r in rows):
            status, evidence, remaining, next_action = values
            rows.append({
                "component": component,
                "status": status,
                "evidence_available": evidence,
                "remaining_work": remaining,
                "recommended_next_action": next_action,
            })
    write_csv(path, rows)


def main() -> None:
    error_rows = taxonomy()
    publication_tables(error_rows)
    manuscript_outline()
    crosswalk_and_journals()
    update_readiness()
    print(f"Error taxonomy rows: {len(error_rows)}")
    print("Paper 1 table package rows: table1={}, table2={}, table3={}, table4={}, table5={}".format(
        len(read_csv(PAPER1_TABLES / "paper1_table1_corpus_summary.csv")),
        len(read_csv(PAPER1_TABLES / "paper1_table2_validation_metrics.csv")),
        len(read_csv(PAPER1_TABLES / "paper1_table3_automation_boundary.csv")),
        len(read_csv(PAPER1_TABLES / "paper1_table4_error_taxonomy.csv")),
        len(read_csv(PAPER1_TABLES / "paper1_table5_labor_reduction.csv")),
    ))


if __name__ == "__main__":
    main()
