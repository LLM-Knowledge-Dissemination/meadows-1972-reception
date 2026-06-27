#!/usr/bin/env python3
"""Audit the repair-aware, label-withheld v2 regression run."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.python.llm_context_classifier import validate_v2_result, v2_run_paths


TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
ACCEPTED_STATUSES = {"initial_valid", "repaired_valid", "router_valid"}


def read_csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def yes(value):
    return str(value).strip().lower() in {"true", "yes", "1"}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else ""


def reference_label(source, manual_field, human_field):
    return source.get(manual_field, "") or source.get(human_field, "")


def intish(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def floatish(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main():
    run_name = os.getenv("MEADOWS_LLM_RUN_NAME", "").strip()
    paths = v2_run_paths(ROOT, run_name)
    input_path = paths["input_snapshot"]
    output_path = paths["output_file"]
    diagnostic_path = paths["diagnostic_file"]
    accepted_final_path = (
        ROOT / f"analysis/data/llm_output/v2/{run_name}_accepted_final.jsonl"
        if run_name else ROOT / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression_accepted_final.jsonl"
    )
    audit_table = TABLES / (f"{run_name}_audit.csv" if run_name else "llm_v2_regression_audit.csv")
    agreement_table = TABLES / (f"{run_name}_human_agreement.csv" if run_name else "llm_v2_regression_human_agreement.csv")
    v1_table = TABLES / (f"{run_name}_vs_v1.csv" if run_name else "llm_v2_regression_vs_v1.csv")
    error_table = TABLES / (f"{run_name}_validation_errors.csv" if run_name else "llm_v2_regression_validation_errors.csv")
    examples_file = VALIDATION / (f"{run_name}_examples.csv" if run_name else "llm_v2_regression_examples.csv")
    inputs = {row["context_group_id"]: row for row in read_csv(input_path)}
    diagnostics = {row["context_group_id"]: row for row in read_csv(diagnostic_path)}
    outputs = read_csv(output_path)
    if not inputs or not outputs:
        raise FileNotFoundError(f"Missing audit inputs for run {run_name or 'legacy_v2_regression'}")
    schema = json.loads((ROOT / "schemas/citation_context_classification_v2.schema.json").read_text(encoding="utf-8"))
    result_fields = [
        "context_id", "context_group_id", "citation_function", "topic_or_discourse_area",
        "stance_toward_seed", "evidence_quote_function", "evidence_quote_topic",
        "evidence_quote_stance", "confidence_function", "confidence_topic",
        "confidence_stance", "uncertainty_flags", "needs_human_review", "reasoning_summary",
    ]
    for output in outputs:
        source = inputs.get(output["context_group_id"], {})
        if output["classification_status"] in {"rejected_after_repair", "rejected_posthoc_validation"}:
            output["needs_human_review"] = "True"
        result = {field: output.get(field, "") for field in result_fields}
        for field in ("confidence_function", "confidence_topic", "confidence_stance"):
            try:
                result[field] = float(result[field])
            except ValueError:
                pass
        result["uncertainty_flags"] = [x.strip() for x in result["uncertainty_flags"].split("|") if x.strip()]
        result["needs_human_review"] = yes(result["needs_human_review"])
        validation = validate_v2_result(result, source, schema)
        output.update(validation)
        if output["classification_status"] in ACCEPTED_STATUSES and not validation["deterministically_valid"]:
            output["classification_status"] = "rejected_posthoc_validation"
    write_csv(output_path, outputs)
    for output in outputs:
        diagnostic = diagnostics.get(output["context_group_id"])
        if diagnostic:
            diagnostic["classification_status"] = output["classification_status"]
            diagnostic["deterministically_valid"] = output["deterministically_valid"]
            diagnostic["validation_errors"] = output["validation_errors"]
    write_csv(diagnostic_path, list(diagnostics.values()))
    joined = []
    for output in outputs:
        source = inputs.get(output["context_group_id"], {})
        diagnostic = diagnostics.get(output["context_group_id"], {})
        human_function = reference_label(source, "manual_recommended_citation_function", "human_primary_role")
        human_topic = reference_label(source, "manual_recommended_topic_or_discourse_area", "human_discourse_category")
        human_stance = reference_label(source, "manual_recommended_stance_toward_seed", "human_stance_toward_seed")
        joined.append({
            **source,
            **output,
            "human_function_agreement": str(output["citation_function"] == human_function).lower() if human_function else "",
            "human_topic_reference": human_topic,
            "human_topic_agreement": str(output["topic_or_discourse_area"] == human_topic).lower() if human_topic else "",
            "human_function_reference": human_function,
            "human_stance_reference": human_stance,
            "human_stance_agreement": str(output["stance_toward_seed"] == human_stance).lower() if human_stance else "",
            "v1_function_agreement": str(output["citation_function"] == source.get("v1_llm_primary_role", "")).lower(),
            "v1_stance_agreement": str(output["stance_toward_seed"] == source.get("v1_llm_stance", "")).lower(),
            "repair_attempted": diagnostic.get("repair_attempted", ""),
        })

    accepted = [row for row in joined if row["classification_status"] in ACCEPTED_STATUSES]
    write_jsonl(accepted_final_path, accepted)
    human_function = [row for row in accepted if row.get("human_function_reference")]
    human_topic = [row for row in accepted if row.get("human_topic_reference")]
    human_stance = [row for row in accepted if row.get("human_stance_reference")]
    supportive = [row for row in accepted if row["stance_toward_seed"] == "supportive"]
    critical = [row for row in accepted if row["stance_toward_seed"] == "critical"]
    metrics = [
        ("attempted", len(joined)),
        ("successful_api_calls", sum(yes(row.get("actual_api_call")) and row.get("classification_status") != "api_error" for row in diagnostics.values())),
        ("initial_valid", sum(row["classification_status"] == "initial_valid" for row in joined)),
        ("router_valid", sum(row["classification_status"] == "router_valid" for row in joined)),
        ("repaired_valid", sum(row["classification_status"] == "repaired_valid" for row in joined)),
        ("rejected_router_validation", sum(row["classification_status"] == "rejected_router_validation" for row in joined)),
        ("rejected_initial_validation", sum(row["classification_status"] == "rejected_initial_validation" for row in joined)),
        ("rejected_after_repair", sum(row["classification_status"] == "rejected_after_repair" for row in joined)),
        ("rejected_posthoc_validation", sum(row["classification_status"] == "rejected_posthoc_validation" for row in joined)),
        ("api_errors", sum(row["classification_status"] == "api_error" for row in joined)),
        ("deterministic_router_classifications", sum(row.get("classification_source") == "deterministic_router" for row in joined)),
        ("llm_classifications", sum(row.get("classification_source") == "llm" for row in joined)),
        ("api_calls_avoided_by_router", sum(row.get("classification_source") == "deterministic_router" for row in joined)),
        ("api_calls_including_retries_and_repairs", sum((1 + intish(row.get("retries")) + yes(row.get("repair_attempted"))) if yes(row.get("actual_api_call")) else 0 for row in diagnostics.values())),
        ("retry_count", sum(intish(row.get("retries")) for row in diagnostics.values())),
        ("runtime_seconds", sum(floatish(row.get("latency_seconds")) for row in diagnostics.values())),
        ("input_tokens", sum(intish(row.get("initial_input_tokens")) + intish(row.get("repair_input_tokens")) for row in diagnostics.values())),
        ("output_tokens", sum(intish(row.get("initial_output_tokens")) + intish(row.get("repair_output_tokens")) for row in diagnostics.values())),
        ("total_tokens", sum(intish(row.get("initial_total_tokens")) + intish(row.get("repair_total_tokens")) for row in diagnostics.values())),
        ("accepted_rate", mean(row["classification_status"] in ACCEPTED_STATUSES for row in joined)),
        ("schema_compliance_rate_accepted", mean(yes(row["schema_compliant"]) for row in accepted)),
        ("identifier_compliance_rate_accepted", mean(yes(row["identifiers_match"]) for row in accepted)),
        ("evidence_validity_rate_accepted", mean(yes(row["all_evidence_fields_valid"]) for row in accepted)),
        ("nonabstention_evidence_exactness_rate_accepted", mean(yes(row["all_nonabstention_evidence_quotes_exact"]) for row in accepted)),
        ("function_evidence_abstention_rate_accepted", mean(yes(row["evidence_quote_function_abstained"]) for row in accepted)),
        ("topic_evidence_abstention_rate_accepted", mean(yes(row["evidence_quote_topic_abstained"]) for row in accepted)),
        ("stance_evidence_abstention_rate_accepted", mean(yes(row["evidence_quote_stance_abstained"]) for row in accepted)),
        ("stance_policy_compliance_rate_accepted", mean(yes(row["stance_evidence_policy_compliant"]) for row in accepted)),
        ("needs_human_review_rate_accepted", mean(yes(row["needs_human_review"]) for row in accepted)),
        ("uncertainty_flag_rate_accepted", mean(row["uncertainty_flags"] != "none" for row in accepted)),
        ("human_function_agreement_rate_accepted", mean(yes(row["human_function_agreement"]) for row in human_function)),
        ("human_function_correct_accepted_rows", sum(yes(row["human_function_agreement"]) for row in human_function)),
        ("human_function_correct_accepted_over_attempted", sum(yes(row["human_function_agreement"]) for row in human_function) / len(joined) if joined else ""),
        ("human_topic_agreement_rate_accepted", mean(yes(row["human_topic_agreement"]) for row in human_topic)),
        ("human_stance_agreement_rate_accepted", mean(yes(row["human_stance_agreement"]) for row in human_stance)),
        ("v1_human_function_agreement_rate_same_accepted_rows", mean(row["v1_llm_primary_role"] == row["human_function_reference"] for row in human_function)),
        ("v1_human_stance_agreement_rate_same_accepted_rows", mean(row["v1_llm_stance"] == row["human_stance_reference"] for row in human_stance)),
        ("v1_function_agreement_rate_accepted", mean(yes(row["v1_function_agreement"]) for row in accepted)),
        ("supportive_count_accepted", len(supportive)),
        ("supportive_human_neutral_overcalls", sum(row.get("human_stance_toward_seed") == "neutral_descriptive" for row in supportive)),
        ("critical_count_accepted", len(critical)),
        ("critical_human_neutral_overcalls", sum(row.get("human_stance_toward_seed") == "neutral_descriptive" for row in critical)),
    ]
    write_csv(audit_table, [{"metric": key, "value": value} for key, value in metrics])

    errors = []
    for row in joined:
        initial = [x for x in row.get("initial_validation_errors", "").split(" | ") if x]
        final = [x for x in row.get("validation_errors", "").split(" | ") if x]
        for phase, values in (("initial", initial), ("final", final)):
            for error in values:
                errors.append({
                    "context_group_id": row["context_group_id"],
                    "context_id": row["context_id"],
                    "phase": phase,
                    "validation_error": error,
                    "classification_status": row["classification_status"],
                })
    write_csv(error_table, errors)

    agreement_fields = [
        "context_group_id", "context_id", "classification_status", "human_function_reference",
        "citation_function", "human_function_agreement", "human_stance_toward_seed",
        "human_topic_reference", "topic_or_discourse_area", "human_topic_agreement",
        "human_stance_reference", "stance_toward_seed", "human_stance_agreement", "needs_human_review",
        "uncertainty_flags", "validation_errors",
    ]
    write_csv(agreement_table, [row for row in accepted if row.get("human_function_reference") or row.get("human_stance_reference")], agreement_fields)

    v1_fields = [
        "context_group_id", "context_id", "classification_status", "v1_llm_primary_role",
        "citation_function", "v1_function_agreement", "v1_llm_stance", "stance_toward_seed",
        "v1_stance_agreement", "human_primary_role", "human_stance_toward_seed",
    ]
    write_csv(v1_table, accepted, v1_fields)

    examples = []
    for row in joined:
        tags = []
        if row["classification_status"] == "repaired_valid":
            tags.append("repaired_valid")
        if row["classification_status"] == "router_valid":
            tags.append("router_valid")
        if row["classification_status"] in {"rejected_after_repair", "rejected_router_validation", "rejected_posthoc_validation"}:
            tags.append(row["classification_status"])
        if row.get("human_function_agreement") == "false":
            tags.append("human_function_disagreement")
        if row.get("human_stance_agreement") == "false":
            tags.append("human_stance_disagreement")
        if row["stance_toward_seed"] in {"supportive", "critical", "mixed"}:
            tags.append("evaluative_stance")
        if tags:
            examples.append({
                "example_types": " | ".join(tags),
                "context_group_id": row["context_group_id"],
                "context_id": row["context_id"],
                "classification_status": row["classification_status"],
                "classification_source": row.get("classification_source", ""),
                "routing_decision": row.get("routing_decision", ""),
                "routing_reason": row.get("routing_reason", ""),
                "citation_sentence": row.get("citation_sentence", ""),
                "sentence_before": row.get("sentence_before", ""),
                "sentence_after": row.get("sentence_after", ""),
                "human_function": row.get("human_primary_role", ""),
                "v1_function": row.get("v1_llm_primary_role", ""),
                "v2_function": row["citation_function"],
                "human_stance": row.get("human_stance_toward_seed", ""),
                "v1_stance": row.get("v1_llm_stance", ""),
                "v2_stance": row["stance_toward_seed"],
                "evidence_quote_function": row["evidence_quote_function"],
                "evidence_quote_stance": row["evidence_quote_stance"],
                "initial_validation_errors": row["initial_validation_errors"],
                "final_validation_errors": row["validation_errors"],
                "needs_human_review": row["needs_human_review"],
                "reasoning_summary": row["reasoning_summary"],
            })
    write_csv(examples_file, examples)

    print("Statuses:", dict(Counter(row["classification_status"] for row in joined)))
    print(f"Accepted {len(accepted)}/{len(joined)}; human function labels on {len(human_function)} accepted rows.")


if __name__ == "__main__":
    main()
