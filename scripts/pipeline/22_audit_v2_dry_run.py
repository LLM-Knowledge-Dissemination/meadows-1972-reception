#!/usr/bin/env python3
"""Audit the isolated v2 classifier dry run against human and v1 labels."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.python.llm_context_classifier import validate_v2_result


INPUT = ROOT / "analysis/data/llm_input/v2/citation_contexts_for_classification_v2.csv"
OUTPUT = ROOT / "analysis/data/llm_output/v2/citation_context_classifications_v2.csv"
OUTPUT_JSONL = ROOT / "analysis/data/llm_output/v2/citation_context_classifications_v2.jsonl"
DIAGNOSTIC = ROOT / "analysis/logs/llm_classification_diagnostic_v2.csv"
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"


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


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def boolish(value):
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else ""


def main():
    inputs = {row["context_group_id"]: row for row in read_csv(INPUT)}
    outputs = read_csv(OUTPUT)
    diagnostics = {row["context_group_id"]: row for row in read_csv(DIAGNOSTIC)}
    raw_results = read_jsonl(OUTPUT_JSONL)
    schema = json.loads((ROOT / "schemas/citation_context_classification_v2.schema.json").read_text(encoding="utf-8"))

    # Revalidate raw model JSON after the run so custom identifier and evidence
    # checks are reflected even if auditing rules were tightened post hoc.
    for index, output in enumerate(outputs):
        source = list(inputs.values())[index]
        raw = raw_results[index] if index < len(raw_results) else {}
        validation = validate_v2_result(raw, source, schema)
        output.update(validation)
        output["context_group_id"] = source["context_group_id"]
        output["context_id"] = source.get("canonical_context_id") or source.get("mention_level_id")
    write_csv(OUTPUT, outputs)
    for output in outputs:
        diagnostic = diagnostics.get(output["context_group_id"])
        if diagnostic:
            for field in (
                "schema_compliant",
                "all_nonempty_evidence_quotes_exact",
                "review_policy_compliant",
                "stance_evidence_policy_compliant",
            ):
                diagnostic[field] = output.get(field, "")
    write_csv(DIAGNOSTIC, list(diagnostics.values()))

    joined = []
    for output in outputs:
        source = inputs.get(output["context_group_id"], {})
        diagnostic = diagnostics.get(output["context_group_id"], {})
        human_function = source.get("human_primary_role", "")
        human_stance = source.get("human_stance_toward_seed", "")
        joined.append({
            **source,
            **output,
            "human_function_agreement": str(bool(human_function) and output["citation_function"] == human_function).lower() if human_function else "",
            "human_stance_agreement": str(bool(human_stance) and output["stance_toward_seed"] == human_stance).lower() if human_stance else "",
            "v1_function_agreement": str(output["citation_function"] == source.get("v1_llm_primary_role", "")).lower(),
            "v1_stance_agreement": str(output["stance_toward_seed"] == source.get("v1_llm_stance", "")).lower(),
            "retry_count": diagnostic.get("retries", ""),
            "latency_seconds": diagnostic.get("latency_seconds", ""),
        })

    successful = [row for row in joined if row["classification_mode"] == "openai_json_schema_v2"]
    human_function_rows = [row for row in successful if row.get("human_primary_role")]
    human_stance_rows = [row for row in successful if row.get("human_stance_toward_seed")]
    exact_quote_fields = ["evidence_quote_function_exact", "evidence_quote_topic_exact", "evidence_quote_stance_exact"]
    metrics = [
        ("attempted", len(joined)),
        ("successful", len(successful)),
        ("failed", len(joined) - len(successful)),
        ("schema_compliance_rate", mean(boolish(r["schema_compliant"]) for r in successful)),
        ("all_evidence_quotes_exact_rate", mean(boolish(r["all_nonempty_evidence_quotes_exact"]) for r in successful)),
        ("function_evidence_exact_rate", mean(boolish(r[exact_quote_fields[0]]) for r in successful)),
        ("topic_evidence_exact_rate", mean(boolish(r[exact_quote_fields[1]]) for r in successful)),
        ("stance_evidence_exact_rate", mean(boolish(r[exact_quote_fields[2]]) for r in successful)),
        ("review_policy_compliance_rate", mean(boolish(r["review_policy_compliant"]) for r in successful)),
        ("stance_evidence_policy_compliance_rate", mean(boolish(r["stance_evidence_policy_compliant"]) for r in successful)),
        ("evidence_category_token_error_rate", mean(boolish(r["evidence_uses_category_token"]) for r in successful)),
        ("needs_human_review_rate", mean(boolish(r["needs_human_review"]) for r in successful)),
        ("uncertainty_flag_rate", mean(bool(r["uncertainty_flags"]) and r["uncertainty_flags"] != "none" for r in successful)),
        ("limited_context_rate", mean(boolish(r["limited_context"]) for r in successful)),
        ("human_function_agreement_rate", mean(boolish(r["human_function_agreement"]) for r in human_function_rows)),
        ("human_stance_agreement_rate", mean(boolish(r["human_stance_agreement"]) for r in human_stance_rows)),
        ("v1_function_agreement_rate", mean(boolish(r["v1_function_agreement"]) for r in successful)),
        ("v1_stance_agreement_rate", mean(boolish(r["v1_stance_agreement"]) for r in successful)),
        ("supportive_count", sum(r["stance_toward_seed"] == "supportive" for r in successful)),
        ("critical_count", sum(r["stance_toward_seed"] == "critical" for r in successful)),
        ("critique_function_count", sum(r["citation_function"] == "critique" for r in successful)),
        ("mean_confidence_function", mean(float(r["confidence_function"]) for r in successful)),
        ("mean_confidence_topic", mean(float(r["confidence_topic"]) for r in successful)),
        ("mean_confidence_stance", mean(float(r["confidence_stance"]) for r in successful)),
        ("retry_rate", mean(int(r["retry_count"] or 0) > 0 for r in joined)),
    ]
    write_csv(TABLES / "llm_v2_dry_run_audit.csv", [{"metric": key, "value": value} for key, value in metrics])

    human_rows = [{
        "context_group_id": row["context_group_id"],
        "context_id": row["context_id"],
        "human_citation_function": row.get("human_primary_role", ""),
        "v2_citation_function": row["citation_function"],
        "function_agreement": row["human_function_agreement"],
        "human_stance": row.get("human_stance_toward_seed", ""),
        "v2_stance": row["stance_toward_seed"],
        "stance_agreement": row["human_stance_agreement"],
        "needs_human_review": row["needs_human_review"],
        "uncertainty_flags": row["uncertainty_flags"],
        "reasoning_summary": row["reasoning_summary"],
    } for row in successful if row.get("human_primary_role") or row.get("human_stance_toward_seed")]
    write_csv(TABLES / "llm_v2_human_agreement_dry_run.csv", human_rows)

    v1_rows = [{
        "context_group_id": row["context_group_id"],
        "context_id": row["context_id"],
        "v1_citation_function": row.get("v1_llm_primary_role", ""),
        "v2_citation_function": row["citation_function"],
        "function_agreement": row["v1_function_agreement"],
        "v1_topic": row.get("v1_llm_topic", ""),
        "v2_topic": row["topic_or_discourse_area"],
        "v1_stance": row.get("v1_llm_stance", ""),
        "v2_stance": row["stance_toward_seed"],
        "stance_agreement": row["v1_stance_agreement"],
        "human_citation_function": row.get("human_primary_role", ""),
        "human_stance": row.get("human_stance_toward_seed", ""),
        "needs_human_review": row["needs_human_review"],
    } for row in successful]
    write_csv(TABLES / "llm_v2_vs_v1_comparison_dry_run.csv", v1_rows)

    examples = []
    for row in successful:
        tags = []
        if row.get("human_primary_role") and not boolish(row["human_function_agreement"]):
            tags.append("v2_human_function_disagreement")
        if not boolish(row["v1_function_agreement"]):
            tags.append("v2_v1_function_disagreement")
        if row["stance_toward_seed"] in {"supportive", "critical", "mixed"}:
            tags.append("evaluative_stance_review")
        if boolish(row["needs_human_review"]) or row["uncertainty_flags"] != "none":
            tags.append("uncertainty_or_review")
        if not boolish(row["all_nonempty_evidence_quotes_exact"]):
            tags.append("evidence_quote_failure")
        if tags:
            examples.append({
                "example_types": " | ".join(tags),
                "context_group_id": row["context_group_id"],
                "context_id": row["context_id"],
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
                "confidence_function": row["confidence_function"],
                "confidence_stance": row["confidence_stance"],
                "uncertainty_flags": row["uncertainty_flags"],
                "needs_human_review": row["needs_human_review"],
                "reasoning_summary": row["reasoning_summary"],
            })
    write_csv(VALIDATION / "llm_v2_dry_run_examples.csv", examples)

    print(f"Audited {len(joined)} v2 rows; {len(successful)} successful; {len(human_function_rows)} with human function labels.")
    print("Function distribution:", dict(Counter(row["citation_function"] for row in successful)))
    print("Stance distribution:", dict(Counter(row["stance_toward_seed"] for row in successful)))


if __name__ == "__main__":
    main()
