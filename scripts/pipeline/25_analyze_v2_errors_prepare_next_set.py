#!/usr/bin/env python3
"""Analyze v2 regression errors and prepare, but do not run, the next set."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
REG_INPUT = ROOT / "analysis/data/llm_input/v2/regression/citation_contexts_for_classification_v2_regression.csv"
REG_OUTPUT = ROOT / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression.csv"
READY = VALIDATION / "v2_classifier_pilot_input_100_ready.csv"


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


ERROR_NOTES = {
    "cg_4a408f91a84c": (
        "rejected_after_repair | v1_correct_v2_wrong",
        "The model treated a body-text publication-history summary as bibliography-only and normalized OCR-bearing text, making the quote non-exact.",
        "Require bibliography-only to be actual reference-list material; classify publication chronology in body text as historical framing. Copy OCR text exactly.",
        "prompt-related | extraction-related",
    ),
    "cg_80bb452dfb06": (
        "rejected_posthoc | v1_correct_v2_wrong | stance_disagreement",
        "Missing structured sentences led v2 to abstain despite a legacy snippet explicitly discussing LtG model success; it also emitted contradictory uncertainty flags.",
        "When visible text explicitly evaluates simulation/model success, use modeling_simulation_reference and supportive stance; never combine none with another uncertainty flag.",
        "extraction-related | prompt-related",
    ),
    "cg_9d95b2a45099": (
        "accepted_wrong_function | accepted_wrong_stance | v1_correct_v2_wrong",
        "V2 was overly conservative on a short legacy snippet that still visibly attributes the claim that exhaustible resources constrain growth.",
        "A visible attributed Meadows claim used as a premise is foundational citation even when adjacent sentences are missing; stance remains unclear unless endorsement is explicit.",
        "prompt-related | extraction-related",
    ),
    "cg_a402fc7c51f5": (
        "accepted_wrong_function | v1_wrong_v2_wrong",
        "V2 inferred policy/governance from surrounding urgency and document context, although the citation event supplies a finite-planet growth-limit claim.",
        "Require an explicit policy/governance/planning/decision link in the citation event; otherwise a substantive attributed claim is foundational citation.",
        "prompt-related",
    ),
    "cg_01a5dd40f8b5": (
        "accepted_wrong_function | accepted_wrong_stance | v1_wrong_v2_wrong",
        "OCR-fragmented context made v2 abstain; the human code interprets adoption in environmentalism as historical influence.",
        "Adoption, influence, persistence, and intellectual lineage are historical framing when visible; otherwise use unclear and human review.",
        "extraction-related | category-design-related",
    ),
    "cg_1e4a61ca47f3": (
        "rejected_after_repair | v2_interpretively_correct_v1_wrong",
        "V2 identified historical framing correctly but repeatedly normalized or paraphrased OCR-bearing evidence instead of copying an exact substring.",
        "Repair must copy exact source characters or abstain and change unsupported topic/function labels to unclear; do not move a bad paraphrase between fields.",
        "prompt-related | model-behavior-related",
    ),
    "cg_6b6f82f07853": (
        "accepted_wrong_function | accepted_wrong_stance | v1_wrong_v2_wrong",
        "V2 forced historical framing from chronology words in severely interleaved OCR where the human code appropriately remains unclear.",
        "Severe OCR or syntactically incoherent citation sentences must force unclear plus human review, even when chronology words appear.",
        "extraction-related | prompt-related",
    ),
}


def context_text(row):
    parts = [row.get("sentence_before", ""), row.get("citation_sentence", ""), row.get("sentence_after", "")]
    structured = " ".join(part.strip() for part in parts if part.strip())
    return structured or row.get("snippet_clean", "")


def main():
    inputs = {row["context_group_id"]: row for row in read_csv(REG_INPUT)}
    outputs = {row["context_group_id"]: row for row in read_csv(REG_OUTPUT)}
    analysis = []
    for group_id, notes in ERROR_NOTES.items():
        source = inputs[group_id]
        output = outputs[group_id]
        error_type, cause, rule, issue_class = notes
        analysis.append({
            "context_group_id": group_id,
            "context_id": source.get("canonical_context_id") or source.get("mention_level_id"),
            "title": source["title"],
            "year": source["year"],
            "context_text_used_by_model": context_text(source),
            "human_function": source.get("human_primary_role", ""),
            "human_stance": source.get("human_stance_toward_seed", ""),
            "v1_function": source.get("v1_llm_primary_role", ""),
            "v1_stance": source.get("v1_llm_stance", ""),
            "v2_function": output.get("citation_function", ""),
            "v2_stance": output.get("stance_toward_seed", ""),
            "v2_evidence_quote": output.get("evidence_quote_function", ""),
            "classification_status": output.get("classification_status", ""),
            "validation_errors": output.get("validation_errors", ""),
            "error_type": error_type,
            "likely_cause": cause,
            "recommended_rule_change": rule,
            "issue_classification": issue_class,
        })
    write_csv(TABLES / "v2_regression_error_analysis.csv", analysis)
    write_csv(TABLES / "v2_repair_failure_diagnostics.csv", [
        {
            "context_group_id": "cg_4a408f91a84c",
            "repair_outcome": "failed",
            "initial_problem": "Normalized/paraphrased OCR-bearing function evidence was not an exact substring.",
            "repair_problem": "Repair abstained on function but repeated the same normalized non-exact quote as topic evidence and disabled required review.",
            "diagnosis": "Repair prompt/model behavior; exact evidence is available but was normalized instead of copied.",
            "recommendation": "Disable repair by default; directly reject. Retest opt-in repair only after exact character-copy instruction changes.",
        },
        {
            "context_group_id": "cg_1e4a61ca47f3",
            "repair_outcome": "failed",
            "initial_problem": "Function evidence paraphrased the OCR-bearing legacy snippet.",
            "repair_problem": "Repair moved the same non-exact paraphrase to topic evidence while abstaining on function.",
            "diagnosis": "Repair prompt/model behavior; the model did not copy source characters exactly.",
            "recommendation": "Disable repair by default; directly reject. Retest opt-in repair only after exact character-copy instruction changes.",
        },
    ])

    ready = read_csv(READY)
    prior_ids = set(inputs)
    selected = []
    seen = set()

    def add(row, reason, test):
        if row["context_group_id"] in seen or len(selected) >= 16:
            return
        selected.append({**row, "next_regression_selection_reason": reason, "next_regression_test": test})
        seen.add(row["context_group_id"])

    for row in ready:
        if row["context_group_id"] in prior_ids:
            add(row, "prior_regression_case", "Retest accepted-wrong, rejected, and control cases after revised function rules.")
    for row in ready:
        pair = {row.get("human_primary_role", ""), row.get("v1_llm_primary_role", "")}
        if {"historical_framing", "modeling_simulation_reference"}.issubset(pair):
            add(row, "historical_vs_modeling_boundary", "Apply model-use versus historical-lineage rule.")
    for row in ready:
        pair = {row.get("human_primary_role", ""), row.get("v1_llm_primary_role", "")}
        if {"historical_framing", "foundational_citation"}.issubset(pair):
            add(row, "historical_vs_foundational_boundary", "Apply substantive-premise versus chronology/lineage rule.")
    for row in ready:
        if row.get("v1_llm_primary_role") == "policy_governance_framing" or row.get("human_primary_role") == "policy_governance_framing":
            add(row, "policy_governance_ambiguity", "Require explicit policy/governance/planning/decision evidence.")
    bibliography_rows = []
    for row in ready:
        text = " ".join([
            row.get("v1_llm_primary_role", ""),
            row.get("v1_llm_uncertainty_flags", ""),
            row.get("human_notes", ""),
            row.get("review_reason", ""),
        ]).lower()
        if "bibliograph" in text or row.get("citation_section") == "BIBLIO" or row.get("bibliography_detected", "").lower() == "true":
            bibliography_rows.append(row)
    bibliography_rows.sort(key=lambda row: row.get("v1_llm_primary_role") != "bibliographic_only")
    for row in bibliography_rows:
        add(row, "bibliography_candidate", "Distinguish true reference-list material from body-text publication history.")
    for row in ready:
        if row.get("review_priority") != "high" and row.get("human_primary_role") == row.get("v1_llm_primary_role"):
            add(row, "lower_risk_control", "Confirm revised rules do not destabilize a lower-risk agreement case.")
    for row in ready:
        if row.get("human_primary_role") == row.get("v1_llm_primary_role") and row.get("human_primary_role"):
            add(row, "agreement_control", "Confirm revised rules preserve a human/v1 agreement case.")

    for row in selected:
        reasons = {row["next_regression_selection_reason"]}
        tests = {row["next_regression_test"]}
        pair = {row.get("human_primary_role", ""), row.get("v1_llm_primary_role", "")}
        text = " ".join([
            row.get("v1_llm_primary_role", ""),
            row.get("v1_llm_uncertainty_flags", ""),
            row.get("human_notes", ""),
            row.get("review_reason", ""),
        ]).lower()
        if "bibliograph" in text or row.get("citation_section") == "BIBLIO" or row.get("bibliography_detected", "").lower() == "true":
            reasons.add("bibliography_candidate")
            tests.add("Distinguish true reference-list material from body-text publication history.")
        if {"historical_framing", "modeling_simulation_reference"}.issubset(pair):
            reasons.add("historical_vs_modeling_boundary")
            tests.add("Apply model-use versus historical-lineage rule.")
        if {"historical_framing", "foundational_citation"}.issubset(pair):
            reasons.add("historical_vs_foundational_boundary")
            tests.add("Apply substantive-premise versus chronology/lineage rule.")
        if row.get("v1_llm_primary_role") == "policy_governance_framing" or row.get("human_primary_role") == "policy_governance_framing" or row["context_group_id"] == "cg_a402fc7c51f5":
            reasons.add("policy_governance_ambiguity")
            tests.add("Require explicit policy/governance/planning/decision evidence.")
        if row.get("human_primary_role") == row.get("v1_llm_primary_role") and row.get("human_primary_role"):
            reasons.add("agreement_control")
            tests.add("Confirm revised rules preserve a human/v1 agreement case.")
        row["next_regression_selection_reason"] = " | ".join(sorted(reasons))
        row["next_regression_test"] = " | ".join(sorted(tests))

    write_csv(VALIDATION / "v2_regression_set_next.csv", selected)
    print(f"Wrote {len(analysis)} error-analysis rows and {len(selected)} next-regression rows. No API calls were made.")


if __name__ == "__main__":
    main()
