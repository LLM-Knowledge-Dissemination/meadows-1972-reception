#!/usr/bin/env python3
"""Create frozen methodology package v2.0 from existing artifacts only."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "analysis/frozen_methodology/v2_0"
ARTIFACTS = FREEZE / "source_artifacts"
DATE_FROZEN = "2026-06-07"
VERSION = "v2.0"


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


def copy_artifact(source: str, dest_name: str | None = None) -> Path | None:
    src = ROOT / source
    if not src.exists():
        return None
    rel_dest = Path(dest_name or source)
    dest = ARTIFACTS / rel_dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def pct(n: int, d: int) -> str:
    return f"{(n / d):.4f}" if d else "not_calculated"


def first(rows: List[Dict[str, str]]) -> Dict[str, str]:
    return rows[0] if rows else {}


def copied_artifacts() -> List[Dict[str, str]]:
    sources = [
        ("analysis/validation/citation_context_codebook.md", None, "validation"),
        ("prompts/citation_context_classification_v2.md", "prompts/citation_context_classification_v2.md", "prompt"),
        ("schemas/citation_context_classification_v2.schema.json", "schemas/citation_context_classification_v2.schema.json", "schema"),
        ("scripts/python/v2_preclassification_router.py", None, "router"),
        ("analysis/tables/router_safe_category_definition.csv", None, "router"),
        ("analysis/tables/v2_router_rule_hits.csv", None, "router"),
        ("analysis/tables/v2_router_audit.csv", None, "router"),
        ("analysis/validation/context_window_improvement_plan.md", None, "extraction"),
        ("analysis/validation/extraction_recovery_review_guidance.md", None, "recovery"),
        ("analysis/tables/extraction_recovery_effect_framework.csv", None, "recovery"),
        ("analysis/tables/extraction_recovery_before_after.csv", None, "recovery"),
        ("analysis/tables/extraction_recovery_effect_estimates.csv", None, "recovery"),
        ("analysis/tables/extraction_recovery_validation_dataset.csv", None, "recovery"),
        ("analysis/validation/extraction_recovery_packet_A.csv", None, "recovery"),
        ("analysis/validation/extraction_recovery_packet_B.csv", None, "recovery"),
        ("analysis/validation/extraction_recovery_packet_C.csv", None, "recovery"),
        ("scripts/R/validation_compare.R", None, "validation"),
        ("scripts/R/validation_sampling.R", None, "validation"),
        ("scripts/pipeline/24_test_v2_validation.py", None, "validation"),
        ("scripts/pipeline/35_prepare_historical_foundational_six_case_review.py", None, "adjudication"),
        ("scripts/pipeline/36_apply_historical_foundational_consensus.py", None, "adjudication"),
        ("scripts/pipeline/39_apply_historical_foundational_packet_a.py", None, "adjudication"),
        ("scripts/pipeline/40_apply_historical_foundational_packet_b.py", None, "adjudication"),
        ("scripts/pipeline/41_apply_historical_foundational_packet_c.py", None, "adjudication"),
        ("scripts/pipeline/43_apply_modeling_validation.py", None, "adjudication"),
        ("scripts/pipeline/44_prepare_extraction_recovery_validation.py", None, "validation"),
        ("scripts/pipeline/45_prepare_router_safe_spotcheck.py", None, "validation"),
        ("scripts/pipeline/46_prepare_final_router_safe_audit.py", None, "validation"),
        ("analysis/validation/manual_adjudication_log.csv", None, "adjudication"),
        ("analysis/validation/targeted_calibration_adjudication_log.csv", None, "adjudication"),
        ("analysis/validation/historical_foundational_packet_A_coded.csv", None, "adjudication"),
        ("analysis/validation/historical_foundational_packet_B_coded.csv", None, "adjudication"),
        ("analysis/validation/historical_foundational_packet_C_coded.csv", None, "adjudication"),
        ("analysis/validation/modeling_validation_coded.csv", None, "adjudication"),
        ("analysis/tables/historical_foundational_final_summary.csv", None, "decision_log"),
        ("analysis/tables/historical_foundational_boundary_validation_assessment.csv", None, "decision_log"),
        ("analysis/tables/modeling_validation_assessment.csv", None, "decision_log"),
        ("analysis/tables/pre_freeze_methodology_assessment.csv", None, "decision_log"),
        ("analysis/tables/pre_methodology_freeze_status.csv", None, "decision_log"),
        ("analysis/tables/router_safe_audit_progress.csv", None, "audit"),
        ("analysis/validation/bibliography_audit_sample.csv", None, "audit"),
        ("analysis/validation/router_safe_batch_A_review_packet.csv", None, "audit"),
        ("analysis/tables/router_safe_stratum_agreement_template.csv", None, "audit"),
        ("analysis/logs/v2_hybrid_pilot100_payload_manifest.json", None, "audit"),
        ("analysis/logs/v2_hybrid_regression1_payload_manifest.json", None, "audit"),
        ("analysis/logs/v2_regression2_payload_manifest.json", None, "audit"),
    ]
    copied: List[Dict[str, str]] = []
    for source, dest_name, component in sources:
        dest = copy_artifact(source, dest_name)
        if dest:
            copied.append({
                "component": component,
                "source_file": source,
                "frozen_file": dest.relative_to(FREEZE).as_posix(),
            })
    return copied


def write_manifest(copied: List[Dict[str, str]]) -> None:
    descriptions = {
        "extraction": "Context-window and citation-context extraction documentation used before v2 classification.",
        "recovery": "Extraction-recovery datasets, review guidance, before/after diagnostics, and review packets.",
        "router": "Implemented deterministic v2 preclassification router and router-safe category definitions.",
        "schema": "Frozen JSON schema for v2 citation-context classification outputs.",
        "prompt": "Frozen v2 prompt used for schema-based citation-context classification.",
        "validation corpus": "Human-coded and review-ready validation corpora used for methodology diagnostics.",
        "audit procedures": "Router-safe, bibliography, regression, and payload-withholding audit procedures.",
    }
    rows = [
        {
            "component": "extraction",
            "file_path": "source_artifacts/analysis/validation/context_window_improvement_plan.md",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["extraction"],
        },
        {
            "component": "recovery",
            "file_path": "source_artifacts/analysis/tables/extraction_recovery_validation_dataset.csv",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["recovery"],
        },
        {
            "component": "router",
            "file_path": "source_artifacts/scripts/python/v2_preclassification_router.py",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["router"],
        },
        {
            "component": "schema",
            "file_path": "source_artifacts/schemas/citation_context_classification_v2.schema.json",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["schema"],
        },
        {
            "component": "prompt",
            "file_path": "source_artifacts/prompts/citation_context_classification_v2.md",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["prompt"],
        },
        {
            "component": "validation corpus",
            "file_path": "source_artifacts/analysis/validation",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["validation corpus"],
        },
        {
            "component": "audit procedures",
            "file_path": "source_artifacts/analysis/tables/router_safe_audit_progress.csv",
            "version": VERSION,
            "date_frozen": DATE_FROZEN,
            "description": descriptions["audit procedures"],
        },
    ]
    write_csv(FREEZE / "methodology_manifest.csv", rows)
    write_csv(FREEZE / "copied_artifacts_manifest.csv", copied)


def validation_numbers() -> Dict[str, Any]:
    hf = first(read_csv(ROOT / "analysis/tables/historical_foundational_final_summary.csv"))
    model = first(read_csv(ROOT / "analysis/tables/modeling_validation_agreement.csv"))
    recovery = {row["metric"]: row["value"] for row in read_csv(ROOT / "analysis/tables/extraction_recovery_effect_estimates.csv")}
    progress = first(read_csv(ROOT / "analysis/tables/validation_progress_after_modeling.csv"))
    router_audit = first(read_csv(ROOT / "analysis/tables/router_safe_audit_progress.csv"))
    biblio_rows = read_csv(ROOT / "analysis/validation/bibliography_audit_sample.csv")
    extraction_packets: List[Dict[str, str]] = []
    for name in ["A", "B", "C"]:
        extraction_packets += read_csv(ROOT / f"analysis/validation/extraction_recovery_packet_{name}.csv")
    extraction_human_reviewed = sum(
        1 for row in extraction_packets
        if any((row.get(field) or "").strip() for field in [
            "human_recovery_helpful",
            "human_recovery_changed_interpretation",
            "human_recovery_increased_confidence",
            "human_recovery_reduced_uncertainty",
        ])
    )
    return {
        "hf": hf,
        "model": model,
        "recovery": recovery,
        "progress": progress,
        "router_audit": router_audit,
        "bibliography_sample_size": len(biblio_rows),
        "extraction_packet_rows": len(extraction_packets),
        "extraction_human_reviewed": extraction_human_reviewed,
    }


def write_validation_summary(nums: Dict[str, Any]) -> None:
    hf = nums["hf"]
    model = nums["model"]
    recovery = nums["recovery"]
    router = nums["router_audit"]
    rows = [
        {
            "validation_area": "Historical/Foundation Validation",
            "reviewed_rows": hf.get("total_adjudicated", "0"),
            "agreement_rate": hf.get("agreement_rate", "not_calculated"),
            "disagreement_count": hf.get("disagreement_count", "not_calculated"),
            "major_error_modes": f"historical_to_foundational={hf.get('historical_to_foundational')}; historical_to_unclear={hf.get('historical_to_unclear')}; foundational_to_historical={hf.get('foundational_to_historical')}; foundational_to_modeling={hf.get('foundational_to_modeling')}; foundational_to_unclear={hf.get('foundational_to_unclear')}",
            "additional_metrics": f"historical={hf.get('human_historical_framing_count')}; foundational={hf.get('human_foundational_citation_count')}; modeling={hf.get('human_modeling_simulation_reference_count')}; unclear={hf.get('human_unclear_count')}",
        },
        {
            "validation_area": "Modeling Validation",
            "reviewed_rows": model.get("total_adjudicated", "0"),
            "agreement_rate": model.get("agreement_rate", "not_calculated"),
            "disagreement_count": model.get("disagreement_count", "not_calculated"),
            "major_error_modes": f"modeling_to_foundational={model.get('modeling_to_foundational')}; modeling_to_unclear={model.get('modeling_to_unclear')}; false_positives={model.get('false_positives')}; false_negatives={model.get('false_negatives')}",
            "additional_metrics": f"modeling={model.get('modeling_simulation_reference_count')}; foundational={model.get('foundational_citation_count')}; unclear={model.get('unclear_count')}",
        },
        {
            "validation_area": "Router-Safe Audit",
            "reviewed_rows": router.get("batch_A_coded_rows", "0"),
            "agreement_rate": "not_calculated_from_existing_labels",
            "disagreement_count": "not_calculated_from_existing_labels",
            "major_error_modes": "not_calculated_from_existing_labels",
            "additional_metrics": f"batch_A_total={router.get('batch_A_total_rows')}; remaining_audit_rows={router.get('remaining_audit_rows')}; percent_complete={router.get('percent_complete')}",
        },
        {
            "validation_area": "Bibliography Audit",
            "reviewed_rows": router.get("bibliography_audit_coded_rows", "0"),
            "agreement_rate": "not_calculated_from_existing_labels",
            "disagreement_count": "not_calculated_from_existing_labels",
            "major_error_modes": "not_calculated_from_existing_labels",
            "additional_metrics": f"sample_size={nums['bibliography_sample_size']}; precision_estimate=not_calculated_from_existing_labels",
        },
        {
            "validation_area": "Extraction Recovery Review",
            "reviewed_rows": nums["extraction_human_reviewed"],
            "agreement_rate": "not_applicable",
            "disagreement_count": "not_applicable",
            "major_error_modes": "human_review_fields_blank_in_existing_recovery_packets",
            "additional_metrics": f"processed_rows={recovery.get('extraction_recovery_rows_processed')}; recovered={recovery.get('recoverability_status_recovered')}; partially_recovered={recovery.get('recoverability_status_partially_recovered')}; expected_likely_improves={recovery.get('expected_effect_likely_improves')}; expected_no_change={recovery.get('expected_effect_no_change')}; confidence_increases=not_calculated_from_existing_labels; uncertainty_reductions=not_calculated_from_existing_labels; interpretation_changes=not_calculated_from_existing_labels",
        },
    ]
    write_csv(FREEZE / "validation_summary.csv", rows)


def write_validation_report(nums: Dict[str, Any]) -> None:
    hf = nums["hf"]
    model = nums["model"]
    progress = nums["progress"]
    router = nums["router_audit"]
    text = f"""# Validation Metrics Report

## Validation Coverage

- Total validation rows: 97
- Reviewed rows recorded in validation-progress table: {progress.get('total_validated_rows')}
- Coverage: {progress.get('percent_validated')} ({float(progress.get('percent_validated', 0)) * 100:.1f}%)

## Agreement Metrics

- Historical/foundational boundary: {hf.get('agreement_count')}/{hf.get('total_adjudicated')} agreement, agreement rate {hf.get('agreement_rate')}.
- Modeling/simulation: {model.get('agreement_count')}/{model.get('total_adjudicated')} agreement, agreement rate {model.get('agreement_rate')}.
- Router-safe Batch A audit: {router.get('batch_A_coded_rows')} coded of {router.get('batch_A_total_rows')} prepared; agreement not calculated from existing labels.
- Bibliography audit: {router.get('bibliography_audit_coded_rows')} coded of {router.get('bibliography_audit_total_rows')} sampled; precision not calculated from existing labels.

## Error Inventory

- Historical vs foundational confusion: historical -> foundational {hf.get('historical_to_foundational')}; foundational -> historical {hf.get('foundational_to_historical')}.
- Modeling edge cases: modeling -> foundational {model.get('modeling_to_foundational')}; modeling -> unclear {model.get('modeling_to_unclear')}.
- Bibliography false positives: not calculated from existing bibliography-audit labels.
- OCR issues: unclear/OCR remains a small but explicit abstention category; one router-safe OCR row remains in the audit frame.
- Extraction failures: 49 extraction-recovery rows were processed; 37 recovered and 12 partially recovered. Existing recovery packets contain no filled human recovery outcome fields.

## Methodological Conclusions

- The historical/foundational distinction is usable for diagnostic coding but remains a known router weakness in boundary cases.
- Modeling/simulation references appear codable when explicit model, simulation, scenario, World3, or system-dynamics evidence is present.
- Bibliography-only routing and router-safe precision are prepared for audit but not quantified from existing human labels.
- Extraction recovery has documented before/after diagnostics, but human-coded recovery benefit metrics are not present in the current files.
- Substantive Meadows analyses should use this frozen methodology without modification.
"""
    write_text(FREEZE / "validation_metrics_report.md", text)


def write_router_spec() -> None:
    text = """# Router Specification

Frozen version: v2.0

Implemented source: `source_artifacts/scripts/python/v2_preclassification_router.py`.

## Routing Categories

- `bibliographic_only`
- `unclear`
- `modeling_simulation_reference`
- `foundational_citation`
- `policy_governance_framing` as an LLM gray-zone route
- `historical_framing`
- `llm_gray_zone` when deterministic rules do not settle the function

## Rule Hierarchy

The implemented router checks in this order:

1. Missing context: deterministic `unclear`, confidence 0.35, human review required.
2. Bibliography/reference-list material: deterministic `bibliographic_only`, confidence 0.92.
3. Missing seed identification, severe OCR, or incoherent context: deterministic `unclear`, confidence 0.42, human review required.
4. Weak scenario/projection language overlapping with historical framing: `llm_gray_zone`, routed as `modeling_simulation_reference`, confidence 0.58, human review required.
5. Explicit modeling/simulation language: deterministic `modeling_simulation_reference`, confidence 0.88.
6. Foundational resource/growth claim without policy hit: deterministic `foundational_citation`, confidence 0.86.
7. Policy/governance language without modeling or foundational hit: `llm_gray_zone`, confidence 0.62.
8. Historical/publication-lineage language: deterministic `historical_framing`, confidence 0.84.
9. Remaining coherent ambiguous context: `llm_gray_zone`, confidence 0.50.

## Confidence Thresholds

The router uses fixed confidence constants in the implementation: bibliography 0.92, modeling 0.88, foundational 0.86, historical 0.84, policy gray-zone 0.62, weak modeling gray-zone 0.58, generic gray-zone 0.50, OCR/ambiguous unclear 0.42, and missing-context unclear 0.35.

## Abstention Logic

The controlled abstention value is `insufficient_evidence`. Missing, incoherent, ambiguous, or short contexts receive uncertainty flags and normally require human review. Deterministic outputs with limited context can still be forced to human review.

## Bibliography Routing

Bibliography routing is triggered by `citation_section == BIBLIO`, by `bibliography_detected` with short contexts, or by reference-list syntax matching the implemented bibliography pattern.

## OCR Routing

The router sends severe OCR or incoherent contexts to `unclear`, especially when seed identification is missing, parentheses are unbalanced in short text, or context is too short to identify the citation event.

## Modeling Routing

Modeling is prioritized over historical terms when explicit terms such as simulation, system dynamics, World3, scenario, projection, forecast, model, assumptions, feedback, sensitivity, or model performance are present.

## Historical Routing

Historical routing applies when visible terms indicate publication history, chronology, editions, influence, adoption, readership, landmark status, or intellectual lineage and no higher-priority modeling or foundational rule applies.

## Foundational Routing

Foundational routing applies when visible Meadows-related claims about finite resources, growth limits, population, food, pollution, overshoot, collapse, or resource constraints are used as substantive premises and no higher-priority modeling rule applies.
"""
    write_text(FREEZE / "router_specification.md", text)


def write_prompt_spec() -> None:
    text = """# Prompt Specification

Frozen prompt version: v2.0

Frozen prompt file: `source_artifacts/prompts/citation_context_classification_v2.md`.

## Expected Inputs

The v2 prompt expects traceable context-group inputs including context identifiers, citation sentence, optional preceding/following sentences, legacy snippet fallback, and limited traceability metadata. Human labels, fallback labels, v1 labels, and adjudication notes are withheld from model payloads when present.

## Expected Outputs

The model must return one JSON object matching `source_artifacts/schemas/citation_context_classification_v2.schema.json`.

## Validation Requirements

Outputs must be schema compliant, must preserve non-empty `context_id` and `context_group_id`, and must use allowable categorical values only.

## Evidence Requirements

Evidence fields must contain exact substrings from the supplied citation sentence or context window, or the controlled abstention value `insufficient_evidence`. Category labels, paraphrases, and invented evidence are invalid.

## Uncertainty Requirements

The prompt instructs aggressive human-review marking for short, OCR-noisy, bibliography-only, generic, ambiguous, missing-context, or repeated-variant cases. Any uncertainty flag other than `none` should normally imply `needs_human_review = true`.

The prompt text itself is copied unchanged into the frozen source artifacts.
"""
    write_text(FREEZE / "prompt_specification.md", text)


def write_schema_spec() -> None:
    schema = json.loads((ROOT / "schemas/citation_context_classification_v2.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]
    required = schema["required"]
    enums = {
        key: props[key].get("enum")
        for key in ["citation_function", "topic_or_discourse_area", "stance_toward_seed"]
    }
    text = f"""# Schema Specification

Frozen schema version: v2.0

Frozen schema file: `source_artifacts/schemas/citation_context_classification_v2.schema.json`.

## Required Fields

{chr(10).join(f'- `{field}`' for field in required)}

## Allowable Values

`citation_function`: {', '.join(enums['citation_function'])}

`topic_or_discourse_area`: {', '.join(enums['topic_or_discourse_area'])}

`stance_toward_seed`: {', '.join(enums['stance_toward_seed'])}

`uncertainty_flags`: snippet_too_short, bibliography_only, ocr_noise, ambiguous_referent, generic_limits_phrase, missing_surrounding_context, repeated_context_variant, non_english_or_translation_issue, none.

## Validation Logic

The schema disallows additional properties, requires non-empty identifiers and evidence strings, constrains confidence fields to numbers from 0 to 1, and requires at least one uncertainty flag.

## Evidence Requirements

Evidence fields are strings with length 1-280 and must be exact context substrings or `insufficient_evidence` under the v2 validator.

## Identifier Requirements

`context_id` and `context_group_id` must be non-empty strings and are checked by deterministic validation routines against the input row.
"""
    write_text(FREEZE / "schema_specification.md", text)


def write_reproducibility_report(copied: List[Dict[str, str]]) -> None:
    text = """# Reproducibility Report

## Required Inputs

- Canonical citation-context and validation CSVs under `analysis/validation/`.
- Frozen prompt and schema under `prompts/` and `schemas/`.
- Deterministic v2 router implementation under `scripts/python/v2_preclassification_router.py`.
- Existing diagnostic logs under `analysis/logs/`.

## Required Scripts

- `scripts/pipeline/24_test_v2_validation.py`
- `scripts/pipeline/39_apply_historical_foundational_packet_a.py`
- `scripts/pipeline/40_apply_historical_foundational_packet_b.py`
- `scripts/pipeline/41_apply_historical_foundational_packet_c.py`
- `scripts/pipeline/43_apply_modeling_validation.py`
- `scripts/pipeline/44_prepare_extraction_recovery_validation.py`
- `scripts/pipeline/45_prepare_router_safe_spotcheck.py`
- `scripts/pipeline/46_prepare_final_router_safe_audit.py`

## Execution Order

1. Build or load validation sample and context windows.
2. Apply historical/foundational adjudication scripts.
3. Apply modeling validation adjudications.
4. Prepare extraction-recovery validation packets.
5. Prepare router-safe spot-check and bibliography audit packets.
6. Run deterministic v2 validation checks.
7. Use this frozen package for downstream analyses without changing router, prompt, schema, extraction, or validation labels.

## Frozen Benchmark References

- `source_artifacts/analysis/logs/v2_hybrid_regression1_payload_manifest.json`
- `source_artifacts/analysis/logs/v2_regression2_payload_manifest.json`
- `source_artifacts/analysis/logs/v2_hybrid_pilot100_payload_manifest.json`

## Checksum References

Checksums are written to `checksum_manifest_sha256.csv` for files in this frozen package.

## Audit Files

- `validation_summary.csv`
- `validation_metrics_report.md`
- `cost_runtime_summary.csv`
- `copied_artifacts_manifest.csv`
- Router-safe and bibliography audit templates copied under `source_artifacts/`.

## Frozen Artifact Count

Copied source artifacts: """ + str(len(copied)) + """
"""
    write_text(FREEZE / "reproducibility_report.md", text)


def diagnostic_summary(path: Path) -> Dict[str, Any]:
    rows = read_csv(path)
    if not rows:
        return {}
    models = Counter(row.get("model", "unknown") or "unknown" for row in rows)
    run_names = Counter(row.get("run_name", path.stem) or path.stem for row in rows)
    api_calls = 0
    if "actual_api_call" in rows[0]:
        api_calls = sum(1 for row in rows if str(row.get("actual_api_call", "")).lower() == "true")
    else:
        api_calls = len(rows)
    accepted = 0
    rejected = 0
    errors = 0
    for row in rows:
        status = (row.get("status") or "").lower()
        cls = (row.get("classification_status") or "").lower()
        valid = str(row.get("deterministically_valid", "")).lower() == "true"
        if status == "error" or "api_error" in cls:
            errors += 1
        elif "rejected" in status or "rejected" in cls:
            rejected += 1
        elif status == "ok" or cls in {"initial_valid", "router_valid"} or valid:
            accepted += 1
    token_fields = [
        ("input_tokens", "output_tokens", "total_tokens"),
        ("initial_input_tokens", "initial_output_tokens", "initial_total_tokens"),
        ("repair_input_tokens", "repair_output_tokens", "repair_total_tokens"),
    ]
    input_tokens = output_tokens = total_tokens = 0
    for row in rows:
        for i_field, o_field, t_field in token_fields:
            input_tokens += int(float(row.get(i_field) or 0))
            output_tokens += int(float(row.get(o_field) or 0))
            total_tokens += int(float(row.get(t_field) or 0))
    runtime = sum(float(row.get("latency_seconds") or 0) for row in rows)
    return {
        "run_name": run_names.most_common(1)[0][0],
        "run_type": "failed_run" if "failed_runs" in path.as_posix() else ("hybrid" if "hybrid" in path.name else ("regression" if "regression" in path.name else "validation")),
        "source_file": path.relative_to(ROOT).as_posix(),
        "model": ";".join(f"{model}:{n}" for model, n in sorted(models.items())),
        "api_calls": api_calls,
        "rows": len(rows),
        "accepted_rows": accepted,
        "rejected_rows": rejected,
        "error_rows": errors,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "runtime_seconds": round(runtime, 3),
        "acceptance_rate": pct(accepted, len(rows)),
    }


def write_cost_runtime_summary() -> None:
    paths = [
        ROOT / "analysis/logs/llm_classification_diagnostic_v2.csv",
        ROOT / "analysis/logs/llm_classification_diagnostic_v2_regression.csv",
        ROOT / "analysis/logs/v2_hybrid_regression1_diagnostic.csv",
        ROOT / "analysis/logs/v2_regression2_diagnostic.csv",
        ROOT / "analysis/logs/v2_hybrid_pilot100_diagnostic.csv",
        ROOT / "analysis/logs/failed_runs/v2_regression2_gpt5nano_diagnostic.csv",
    ]
    rows = [diagnostic_summary(path) for path in paths if path.exists()]
    rows = [row for row in rows if row]
    write_csv(FREEZE / "cost_runtime_summary.csv", rows)


def write_freeze_statement(nums: Dict[str, Any]) -> None:
    progress = nums["progress"]
    text = f"""# Methodology Freeze v2.0

Freeze date: {DATE_FROZEN}

Version: {VERSION}

## Validation Status

- Historical/foundational boundary validation: complete for the 28 adjudicated boundary cases.
- Modeling validation: complete for the 11 adjudicated modeling-router cases.
- Recorded validation coverage: {progress.get('total_validated_rows')} of 97 rows ({progress.get('percent_validated')}).
- Router-safe and bibliography audit packets are prepared; coded agreement/precision values are not present in existing labels.
- Extraction-recovery diagnostics are prepared for 49 rows; human recovery outcome fields are blank in the current packet files.

## Known Limitations

- Historical/foundational router agreement is modest in boundary cases.
- Modeling is codable when explicit modeling evidence is present, but scenario-outcome and metadata-only cases remain edge cases.
- Bibliography precision is not yet calculated from human-coded audit labels.
- Extraction-recovery benefit metrics are not human-coded in the current files.
- The frozen package documents methodology and validation status; it does not establish substantive findings about Meadows 1972.

## Approved Future Uses

- Use the frozen prompt, schema, router, validation codebook, and extraction-recovery procedures for downstream contextual bibliometrics analyses.
- Use validation summaries to qualify method claims and limitations.
- Use cost/runtime summaries for future model-comparison planning.

Substantive Meadows analyses should use this frozen methodology without modification.
"""
    write_text(FREEZE / "METHODOLOGY_FREEZE_v2.0.md", text)


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
    FREEZE.mkdir(parents=True, exist_ok=True)
    copied = copied_artifacts()
    write_manifest(copied)
    nums = validation_numbers()
    write_validation_summary(nums)
    write_validation_report(nums)
    write_router_spec()
    write_prompt_spec()
    write_schema_spec()
    write_reproducibility_report(copied)
    write_cost_runtime_summary()
    write_freeze_statement(nums)
    write_checksums()
    print(f"Frozen methodology package: {FREEZE.relative_to(ROOT)}")
    print(f"Copied source artifacts: {len(copied)}")


if __name__ == "__main__":
    main()
