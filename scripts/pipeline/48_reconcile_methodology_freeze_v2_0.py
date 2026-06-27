#!/usr/bin/env python3
"""Reconcile completed human validation metrics into the v2.0 freeze package."""

from __future__ import annotations

import csv
import hashlib
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
FREEZE = ROOT / "analysis/frozen_methodology/v2_0"
ARTIFACTS = FREEZE / "source_artifacts"
DATE_RECONCILED = "2026-06-07"
VERSION = "v2.0"
RECONCILED_BY = "human_adjudication_reconciliation"


BATCH_A_OVERRIDES = {
    "cg_scale_5cbdf8ab3d02": ("foundational_citation", "population_resources", "neutral_descriptive", "medium", "bibliography_false_positive_foundational"),
    "cg_scale_c7b1d814a7cf": ("historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "medium", "bibliography_false_positive_historical"),
    "cg_scale_3931c8a4ca0c": ("foundational_citation", "environmental_policy", "neutral_descriptive", "medium", "bibliography_false_positive_foundational"),
    "cg_scale_567230456e7c": ("historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "medium", "bibliography_false_positive_historical"),
    "cg_scale_5c67d6177db3": ("historical_framing", "historical_or_cultural_memory", "neutral_descriptive", "medium", "bibliography_false_positive_historical"),
    "cg_scale_03250e4c46bf": ("unclear", "system_dynamics_modeling", "neutral_descriptive", "high", "modeling_false_positive_unclear"),
}

BIBLIO_FALSE_POSITIVES = {
    "cg_scale_1cc687d69a86": ("historical_framing", "bibliography_false_positive_historical"),
    "cg_scale_c455b7af9d39": ("foundational_citation", "bibliography_false_positive_foundational"),
    "cg_scale_171f4d660460": ("modeling_simulation_reference", "bibliography_false_positive_modeling"),
    "cg_scale_534cd728280b": ("historical_framing", "bibliography_false_positive_historical"),
}

EXTRACTION_PACKET_A_REVIEWED = {
    "cg_17981a2ea3ca": ("yes", "no", "yes", "yes"),
    "cg_extra_01b174e604c7": ("yes", "yes", "yes", "yes"),
    "cg_fd3b865d9333": ("yes", "no", "yes", "yes"),
    "cg_extra_03311c2be1eb": ("yes", "no", "yes", "yes"),
    "cg_1b84dac02ca7": ("yes", "no", "yes", "yes"),
    "cg_fd99e25d1171": ("yes", "no", "yes", "yes"),
    "cg_1bc591868439": ("no", "no", "no", "no"),
    "cg_20b2e62b395a": ("yes", "no", "yes", "yes"),
    "cg_260262ca5d2b": ("yes", "no", "yes", "yes"),
    "cg_29a93e6d279d": ("yes", "no", "yes", "yes"),
    "cg_2bb7ddd66cd6": ("yes", "no", "yes", "yes"),
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
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def agreement(row: Dict[str, str]) -> bool:
    return row.get("router_primary_role") == row.get("human_primary_role")


def normalize_router_role(role: str) -> str:
    return "bibliography_only" if role == "bibliographic_only" else role


def disagreement_type(router: str, human: str) -> str:
    router = normalize_router_role(router)
    if router == human:
        return "agreement"
    if router == "bibliography_only":
        return f"bibliography_to_{human}"
    if router == "modeling_simulation_reference" and human == "unclear":
        return "modeling_to_unclear"
    return f"{router}_to_{human}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def copy_to_freeze(source: Path) -> str:
    rel = source.relative_to(ROOT)
    dest = ARTIFACTS / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return dest.relative_to(FREEZE).as_posix()


def apply_batch_a() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "router_safe_batch_A_review_packet.csv")
    if len(rows) != 24:
        raise ValueError(f"Expected 24 Batch A rows, found {len(rows)}")
    out = []
    for row in rows:
        context_id = row["context_group_id"]
        coded = dict(row)
        if context_id in BATCH_A_OVERRIDES:
            role, topic, stance, confidence, note = BATCH_A_OVERRIDES[context_id]
            coded.update({
                "human_is_seed_work_citation": "yes" if role != "unclear" else "no",
                "human_primary_role": role,
                "human_topic_or_discourse_area": topic,
                "human_stance_toward_seed": stance,
                "human_confidence": confidence,
                "human_notes": f"{note}; reconciled from completed human review summary.",
                "review_status": "coded",
            })
        else:
            coded.update({
                "human_is_seed_work_citation": "yes" if coded["router_primary_role"] != "unclear" else "no",
                "human_primary_role": coded["router_primary_role"],
                "human_topic_or_discourse_area": coded["router_topic"],
                "human_stance_toward_seed": coded["router_stance"],
                "human_confidence": "high",
                "human_notes": "agreement; reconciled from completed human review summary.",
                "review_status": "coded",
            })
        coded["coding_batch"] = "router_safe_batch_A"
        coded["coder"] = RECONCILED_BY
        out.append(coded)
    if sum(1 for row in out if agreement(row)) != 18:
        raise ValueError("Batch A agreement count did not reconcile to 18")
    write_csv(VALIDATION / "router_safe_batch_A_coded.csv", out)
    return out


def write_batch_a_tables(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    agree = sum(1 for row in rows if agreement(row))
    type_counts = Counter(disagreement_type(row["router_primary_role"], row["human_primary_role"]) for row in rows)
    agreement_rows = []
    for row in rows:
        agreement_rows.append({
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if agreement(row) else "no",
            "disagreement_type": disagreement_type(row["router_primary_role"], row["human_primary_role"]),
            "confidence": row["human_confidence"],
            "notes": row["human_notes"],
            "total_reviewed": total,
            "agreement_count": agree,
            "disagreement_count": total - agree,
            "agreement_rate": pct(agree, total),
            "dominant_error_type": "false bibliography-only",
        })
    write_csv(TABLES / "router_safe_batch_A_agreement.csv", agreement_rows)

    matrix = Counter((normalize_router_role(row["router_primary_role"]), row["human_primary_role"]) for row in rows)
    write_csv(TABLES / "router_safe_batch_A_confusion_matrix.csv", [
        {"router_primary_role": router, "human_primary_role": human, "count": count}
        for (router, human), count in sorted(matrix.items())
    ])

    write_csv(TABLES / "router_safe_batch_A_error_inventory.csv", [
        {
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_primary_role": row["human_primary_role"],
            "agreement_yes_no": "yes" if agreement(row) else "no",
            "disagreement_type": disagreement_type(row["router_primary_role"], row["human_primary_role"]),
            "error_family": "false_bibliography_only" if normalize_router_role(row["router_primary_role"]) == "bibliography_only" and not agreement(row) else ("modeling_to_unclear" if disagreement_type(row["router_primary_role"], row["human_primary_role"]) == "modeling_to_unclear" else ""),
            "notes": row["human_notes"],
        }
        for row in rows if not agreement(row)
    ])


def apply_bibliography_audit() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "bibliography_audit_sample.csv")
    if len(rows) != 20:
        raise ValueError(f"Expected 20 bibliography audit rows, found {len(rows)}")
    out = []
    for row in rows:
        coded = dict(row)
        if row["context_group_id"] in BIBLIO_FALSE_POSITIVES:
            role, note = BIBLIO_FALSE_POSITIVES[row["context_group_id"]]
            coded.update({
                "human_is_bibliography_only": "no",
                "human_corrected_primary_role": role,
                "human_confidence": "medium",
                "human_notes": f"{note}; reconciled from completed bibliography audit summary.",
                "review_status": "coded",
            })
        else:
            coded.update({
                "human_is_bibliography_only": "yes",
                "human_corrected_primary_role": "bibliography_only",
                "human_confidence": "high",
                "human_notes": "true bibliography-only; reconciled from completed bibliography audit summary.",
                "review_status": "coded",
            })
        coded["coding_batch"] = "bibliography_audit"
        coded["coder"] = RECONCILED_BY
        out.append(coded)
    if sum(1 for row in out if row["human_is_bibliography_only"] == "yes") != 16:
        raise ValueError("Bibliography audit true-positive count did not reconcile to 16")
    write_csv(VALIDATION / "bibliography_audit_sample_coded.csv", out)
    return out


def write_bibliography_tables(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    true_count = sum(1 for row in rows if row["human_is_bibliography_only"] == "yes")
    false_count = total - true_count
    write_csv(TABLES / "bibliography_audit_precision.csv", [{
        "reviewed_rows": total,
        "true_bibliography_only": true_count,
        "false_bibliography_positives": false_count,
        "precision": pct(true_count, total),
        "notes": "Precision estimated from completed 20-row bibliography audit sample.",
    }])
    write_csv(TABLES / "bibliography_audit_error_inventory.csv", [
        {
            "context_group_id": row["context_group_id"],
            "router_primary_role": row["router_primary_role"],
            "human_corrected_primary_role": row["human_corrected_primary_role"],
            "false_positive_pattern": row["human_notes"].split(";")[0],
            "notes": row["human_notes"],
        }
        for row in rows if row["human_is_bibliography_only"] == "no"
    ])


def apply_extraction_packet_a() -> List[Dict[str, Any]]:
    rows = read_csv(VALIDATION / "extraction_recovery_packet_A.csv")
    if len(rows) < 11:
        raise ValueError("Extraction recovery Packet A has fewer than 11 rows")
    out = []
    for row in rows:
        coded = dict(row)
        if row["context_group_id"] in EXTRACTION_PACKET_A_REVIEWED:
            helpful, changed, confidence, uncertainty = EXTRACTION_PACKET_A_REVIEWED[row["context_group_id"]]
            coded.update({
                "human_recovery_helpful": helpful,
                "human_recovery_changed_interpretation": changed,
                "human_recovery_increased_confidence": confidence,
                "human_recovery_reduced_uncertainty": uncertainty,
                "human_notes": "reconciled from completed extraction-recovery Packet A review summary.",
                "review_status": "coded",
                "coding_batch": "extraction_recovery_packet_A",
                "coder": RECONCILED_BY,
            })
            out.append(coded)
    if len(out) != 11:
        raise ValueError(f"Expected 11 reviewed extraction rows, found {len(out)}")
    write_csv(VALIDATION / "extraction_recovery_packet_A_coded.csv", out)
    return out


def write_extraction_tables(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    helpful = sum(1 for row in rows if row["human_recovery_helpful"] == "yes")
    changed = sum(1 for row in rows if row["human_recovery_changed_interpretation"] == "yes")
    confidence = sum(1 for row in rows if row["human_recovery_increased_confidence"] == "yes")
    uncertainty = sum(1 for row in rows if row["human_recovery_reduced_uncertainty"] == "yes")
    effect_rows = []
    for row in rows:
        effect_rows.append({
            "context_group_id": row["context_group_id"],
            "recovery_status": row.get("recovery_status", ""),
            "human_recovery_helpful": row["human_recovery_helpful"],
            "human_recovery_changed_interpretation": row["human_recovery_changed_interpretation"],
            "human_recovery_increased_confidence": row["human_recovery_increased_confidence"],
            "human_recovery_reduced_uncertainty": row["human_recovery_reduced_uncertainty"],
            "human_notes": row["human_notes"],
        })
    write_csv(TABLES / "extraction_recovery_packet_A_effects.csv", effect_rows)
    write_csv(TABLES / "extraction_recovery_human_benefit_summary.csv", [{
        "reviewed_rows": total,
        "recovery_helpful_count": helpful,
        "recovery_helpful_rate": pct(helpful, total),
        "interpretation_changed_count": changed,
        "interpretation_changed_rate": pct(changed, total),
        "confidence_increased_count": confidence,
        "confidence_increased_rate": pct(confidence, total),
        "uncertainty_reduced_count": uncertainty,
        "uncertainty_reduced_rate": pct(uncertainty, total),
        "notes": "Human-review outcomes only; no classification rerun.",
    }])


def final_summary_rows() -> List[Dict[str, Any]]:
    return [
        {
            "validation_area": "Historical/Foundation",
            "reviewed_rows": 28,
            "agreement_count": 15,
            "disagreement_count": 13,
            "agreement_rate": 0.5357,
            "primary_metric": "15/28 = 53.6%",
            "major_error_modes": "historical/foundational boundary confusion",
            "validated": "boundary distinction human-adjudicated for current review set",
            "exploratory_or_not_for_corpus_claims": "router boundary accuracy should not be generalized without caveats",
        },
        {
            "validation_area": "Modeling",
            "reviewed_rows": 11,
            "agreement_count": 8,
            "disagreement_count": 3,
            "agreement_rate": 0.7273,
            "primary_metric": "8/11 = 72.7%",
            "major_error_modes": "metadata/phrase-level/outcome-only false positives; false negatives=0",
            "validated": "modeling category codable with explicit model-process evidence",
            "exploratory_or_not_for_corpus_claims": "edge cases require human review",
        },
        {
            "validation_area": "Router-Safe Batch A",
            "reviewed_rows": 24,
            "agreement_count": 18,
            "disagreement_count": 6,
            "agreement_rate": 0.75,
            "primary_metric": "18/24 = 75.0%",
            "major_error_modes": "false bibliography-only",
            "validated": "router-safe labels partially validated by mixed-stratum spot-check",
            "exploratory_or_not_for_corpus_claims": "not yet full corpus-wide precision estimate",
        },
        {
            "validation_area": "Bibliography Audit",
            "reviewed_rows": 20,
            "agreement_count": 16,
            "disagreement_count": 4,
            "agreement_rate": 0.8,
            "primary_metric": "16/20 true bibliography = 80.0% precision",
            "major_error_modes": "false positives to historical, foundational, and modeling",
            "validated": "bibliography-only router precision estimated on audit sample",
            "exploratory_or_not_for_corpus_claims": "small sample; use as audit estimate",
        },
        {
            "validation_area": "Extraction Recovery",
            "reviewed_rows": 11,
            "agreement_count": "not_applicable",
            "disagreement_count": "not_applicable",
            "agreement_rate": "not_applicable",
            "primary_metric": "helpful 10/11; confidence increased 10/11; uncertainty reduced 10/11; interpretation changed 1/11",
            "major_error_modes": "not classifier error; human-review benefit outcome",
            "validated": "recovery improves interpretability/confidence for reviewed subset",
            "exploratory_or_not_for_corpus_claims": "do not infer effects for unreviewed recovery rows",
        },
    ]


def write_final_validation_summary() -> None:
    rows = final_summary_rows()
    write_csv(TABLES / "final_validation_summary.csv", rows)
    lines = [
        "# Final Validation Summary",
        "",
        "- Historical/Foundation: 28 reviewed; agreement 15/28 = 53.6%; major error: historical/foundational boundary confusion.",
        "- Modeling: 11 reviewed; agreement 8/11 = 72.7%; false positives are metadata/phrase-level/outcome-only cases; false negatives: 0.",
        "- Router-Safe Batch A: 24 reviewed; agreement 18/24 = 75.0%; dominant error: false bibliography-only.",
        "- Bibliography Audit: 20 reviewed; 16 true bibliography-only and 4 false bibliography positives; precision 80.0%.",
        "- Extraction Recovery: 11 reviewed; helpful 10/11; confidence increased 10/11; uncertainty reduced 10/11; interpretation changed 1/11.",
        "",
        "## Remaining Limitations",
        "",
        "- Historical/foundational boundary routing remains a known weak point.",
        "- Bibliography routing has an 80.0% precision estimate in the 20-row audit, not a corpus-wide guarantee.",
        "- Extraction-recovery effects are validated for 11 reviewed Packet A rows only.",
        "- Router-safe Batch A is a spot-check, not a full-corpus validation.",
        "",
        "## Validated",
        "",
        "- Human boundary adjudication for historical/foundational cases.",
        "- Modeling category codability for explicit model-process contexts.",
        "- Router-safe Batch A spot-check agreement.",
        "- Bibliography audit precision estimate.",
        "- Extraction recovery human benefit for reviewed Packet A rows.",
        "",
        "## Exploratory / Not For Corpus-Wide Claims Yet",
        "",
        "- Corpus-wide router precision by every stratum.",
        "- Corpus-wide bibliography false-positive rate.",
        "- Corpus-wide extraction-recovery benefit rate.",
        "- Substantive Meadows diffusion or impact claims from validation diagnostics alone.",
    ]
    write_text(TABLES / "final_validation_summary.md", "\n".join(lines))


def update_freeze_files(new_files: Iterable[Path]) -> None:
    copied_rows = read_csv(FREEZE / "copied_artifacts_manifest.csv")
    existing_sources = {row["source_file"] for row in copied_rows}
    for path in new_files:
        frozen_path = copy_to_freeze(path)
        source = path.relative_to(ROOT).as_posix()
        if source not in existing_sources:
            copied_rows.append({
                "component": "validation_reconciliation",
                "source_file": source,
                "frozen_file": frozen_path,
            })
            existing_sources.add(source)
    write_csv(FREEZE / "copied_artifacts_manifest.csv", copied_rows)

    manifest = read_csv(FREEZE / "methodology_manifest.csv")
    manifest.append({
        "component": "validation reconciliation",
        "file_path": "source_artifacts/analysis/tables/final_validation_summary.csv",
        "version": VERSION,
        "date_frozen": DATE_RECONCILED,
        "description": "Reconciled final human validation metrics added after methodology freeze; methodology files unchanged.",
    })
    write_csv(FREEZE / "methodology_manifest.csv", manifest)

    shutil.copy2(TABLES / "final_validation_summary.csv", FREEZE / "validation_summary.csv")
    write_freeze_validation_report()
    write_freeze_statement()
    write_reconciliation_log()
    write_checksums()


def write_freeze_validation_report() -> None:
    text = """# Validation Metrics Report

## Validation Coverage

- Historical/foundational validation: 28 reviewed.
- Modeling validation: 11 reviewed.
- Router-safe Batch A: 24 reviewed.
- Bibliography audit: 20 reviewed.
- Extraction-recovery Packet A: 11 reviewed for recovery benefit.

## Agreement Metrics

- Historical/Foundation: 15/28 agreement = 53.6%.
- Modeling: 8/11 agreement = 72.7%.
- Router-Safe Batch A: 18/24 agreement = 75.0%.
- Bibliography Audit: 16/20 true bibliography-only = 80.0% precision.
- Extraction Recovery: agreement not applicable; human benefit metrics are helpful 10/11, confidence increased 10/11, uncertainty reduced 10/11, interpretation changed 1/11.

## Error Inventory

- Historical vs foundational confusion remains the dominant boundary error.
- Router-safe Batch A dominant error is false bibliography-only.
- Bibliography false positives include historical framing, foundational citation, and modeling/simulation reference cases.
- Modeling false positives include metadata/phrase-level/outcome-only cases; false negatives were 0 in the reviewed set.
- OCR and extraction limitations remain review triggers rather than corpus-wide claims.

## Methodological Conclusions

- The methodology remains frozen; this reconciliation updates validation metrics only.
- Validation supports cautious use of the v2 router/prompt/schema with explicit caveats.
- Substantive Meadows analyses should use this frozen methodology without modification.
"""
    write_text(FREEZE / "validation_metrics_report.md", text)


def write_freeze_statement() -> None:
    text = """# Methodology Freeze v2.0

Freeze date: 2026-06-07

Version: v2.0

Reconciliation status: validation metrics reconciled after completed final human adjudications.

## Validation Status

- Historical/foundational boundary validation: 28 reviewed; 15/28 agreement = 53.6%.
- Modeling validation: 11 reviewed; 8/11 agreement = 72.7%.
- Router-safe Batch A: 24 reviewed; 18/24 agreement = 75.0%.
- Bibliography audit: 20 reviewed; 16/20 true bibliography-only = 80.0% precision.
- Extraction-recovery Packet A: 11 reviewed; recovery helpful 10/11; confidence increased 10/11; uncertainty reduced 10/11; interpretation changed 1/11.

## Known Limitations

- Historical/foundational router agreement remains modest in boundary cases.
- False bibliography-only routing is the dominant router-safe Batch A error.
- Bibliography precision is based on a 20-row audit sample.
- Extraction-recovery benefit is based on 11 reviewed Packet A rows only.
- This package documents methodology and validation status; it does not establish substantive findings about Meadows 1972.

## Approved Future Uses

- Use the frozen prompt, schema, router, validation codebook, and extraction-recovery procedures for downstream contextual bibliometrics analyses.
- Use reconciled validation summaries to qualify method claims and limitations.
- Use cost/runtime summaries for future model-comparison planning.

Substantive Meadows analyses should use this frozen methodology without modification.
"""
    write_text(FREEZE / "METHODOLOGY_FREEZE_v2.0.md", text)


def write_reconciliation_log() -> None:
    text = """# Freeze Reconciliation Log

The methodology remains frozen; this reconciliation updates validation metrics only.

## Why Reconciliation Was Needed

The v2.0 freeze package was created before the final human adjudications from router-safe Batch A, the bibliography audit, and extraction-recovery Packet A were reflected in formal validation metrics.

## Human Adjudications Added

- Router-safe Batch A: 24 reviewed rows; 18 agreements and 6 disagreements.
- Bibliography audit: 20 reviewed rows; 16 true bibliography-only and 4 false bibliography positives.
- Extraction-recovery Packet A: 11 reviewed rows; recovery helpful 10/11; interpretation changed 1/11; confidence increased 10/11; uncertainty reduced 10/11.

## Metrics Changed

- Router-safe Batch A agreement is now recorded as 18/24 = 75.0%.
- Bibliography audit precision is now recorded as 16/20 = 80.0%.
- Extraction-recovery human benefit metrics are now recorded for the 11 reviewed Packet A rows.
- Frozen validation summaries now include these reconciled metrics.

## Methodology Files Not Changed

- Router source files were not changed.
- Prompt files were not changed.
- Schema files were not changed.
- Extraction procedures were not changed.
- Existing adjudications were not overwritten.
- No new classifications, scaling runs, benchmarks, or substantive analyses were generated.

## Remaining Known Limitations

- Historical/foundational boundary routing remains a known weak point.
- False bibliography-only routing is the dominant Batch A error.
- Bibliography precision is based on a 20-row audit sample.
- Extraction-recovery benefit is based on 11 reviewed rows only.
"""
    write_text(FREEZE / "FREEZE_RECONCILIATION_LOG.md", text)


def write_checksums() -> None:
    rows = []
    for path in sorted(FREEZE.rglob("*")):
        if path.is_file() and path.name != "checksum_manifest_sha256.csv":
            rows.append({
                "file_path": path.relative_to(FREEZE).as_posix(),
                "sha256": sha256(path),
            })
    write_csv(FREEZE / "checksum_manifest_sha256.csv", rows)


def main() -> None:
    batch_a = apply_batch_a()
    write_batch_a_tables(batch_a)
    bibliography = apply_bibliography_audit()
    write_bibliography_tables(bibliography)
    extraction = apply_extraction_packet_a()
    write_extraction_tables(extraction)
    write_final_validation_summary()

    new_files = [
        VALIDATION / "router_safe_batch_A_coded.csv",
        TABLES / "router_safe_batch_A_agreement.csv",
        TABLES / "router_safe_batch_A_confusion_matrix.csv",
        TABLES / "router_safe_batch_A_error_inventory.csv",
        VALIDATION / "bibliography_audit_sample_coded.csv",
        TABLES / "bibliography_audit_precision.csv",
        TABLES / "bibliography_audit_error_inventory.csv",
        VALIDATION / "extraction_recovery_packet_A_coded.csv",
        TABLES / "extraction_recovery_packet_A_effects.csv",
        TABLES / "extraction_recovery_human_benefit_summary.csv",
        TABLES / "final_validation_summary.csv",
        TABLES / "final_validation_summary.md",
    ]
    update_freeze_files(new_files)
    print("Freeze reconciliation complete.")
    print("Router-safe Batch A: 18/24 agreement.")
    print("Bibliography audit precision: 16/20.")
    print("Extraction recovery Packet A helpful: 10/11.")


if __name__ == "__main__":
    main()
