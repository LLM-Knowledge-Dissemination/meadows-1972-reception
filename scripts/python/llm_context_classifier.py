from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List
import hashlib

from scripts.python.v2_preclassification_router import route_context, route_to_record


V2_REQUIRED_FIELDS = [
    "context_id",
    "context_group_id",
    "citation_function",
    "topic_or_discourse_area",
    "stance_toward_seed",
    "evidence_quote_function",
    "evidence_quote_topic",
    "evidence_quote_stance",
    "confidence_function",
    "confidence_topic",
    "confidence_stance",
    "uncertainty_flags",
    "needs_human_review",
    "reasoning_summary",
]

V2_INPUT_REQUIRED_FIELDS = {
    "context_group_id",
    "citation_sentence",
    "sentence_before",
    "sentence_after",
    "snippet_clean",
    "bibliography_detected",
    "bibliography_score",
    "extraction_confidence",
}
V2_PAYLOAD_FIELDS = [
    "context_group_id",
    "representative_context_id",
    "title_for_traceability_only",
    "year_for_traceability_only",
    "venue_for_traceability_only",
    "citation_sentence",
    "sentence_before",
    "sentence_after",
    "legacy_snippet",
    "bibliography_detected",
    "bibliography_score",
    "extraction_confidence",
    "limited_context",
    "needs_human_review_expected",
    "comparison_labels_withheld_from_model",
    "traceability",
]
V2_WITHHELD_FIELD_PATTERNS = (
    "human_",
    "v1_",
    "fallback_",
    "manual_",
    "adjudicat",
    "review_reason",
    "human_notes",
)

CONTROLLED_ABSTENTION = "insufficient_evidence"
POSITIVE_STANCE_CUES = [
    "accurate", "confirmed", "correct", "success", "successful", "valid",
    "valuable", "useful", "support", "endors", "adopt", "agree", "remarkable",
    "still relevant", "proved", "vindicat",
]
NEGATIVE_STANCE_CUES = [
    "wrong", "failed", "failure", "flawed", "incorrect", "reject", "critic",
    "unhelpful", "inaccurate", "invalid", "mistaken", "overestimated",
    "underestimated", "did not", "does not", "not borne out", "refut",
]


ROLE_FALLBACKS = {
    "critique": ["critique", "criticis", "refut", "controvers", "wrong", "failed", "debate"],
    "modeling_simulation_reference": ["model", "simulation", "system dynamics", "world3", "scenario", "forecast"],
    "policy_governance_framing": ["policy", "governance", "planning", "regulation", "sustainable development"],
    "historical_framing": ["historical", "history", "early", "classic", "seminal", "landmark", "foundational"],
    "sustainability_limits_to_growth_discourse": ["sustainab", "ecological limits", "planetary boundaries", "overshoot", "collapse", "growth"],
}


def read_yaml_simple(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {
            "classification": {
                "enabled_env": "MEADOWS_ENABLE_LLM",
                "model_env": "MEADOWS_LLM_MODEL",
                "default_model": "gpt-5-nano",
                "max_contexts_env": "MEADOWS_LLM_LIMIT",
                "default_max_contexts": 0,
                "input_file": "analysis/data/processed/citation_contexts.csv",
                "output_file": "analysis/data/llm_output/citation_context_classifications.csv",
                "audit_file": "analysis/audit/llm_classification_audit.jsonl",
                "prompt_file": "prompts/citation_context_classification.md",
                "schema_file": "schemas/citation_context_classification.schema.json",
            }
        }
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_csv(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def context_id(row: Dict[str, str]) -> str:
    return row.get("context_id") or row.get("hit_id") or "|".join(
        [row.get("source_document_id", ""), row.get("page", ""), row.get("match", "")]
    )


def select_rows(rows: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    def priority(row: Dict[str, str]) -> int:
        label = row.get("semantic_label", "")
        section = row.get("citation_section", "")
        if label == "MEADOWS_1972_BOOK" and section == "BODY":
            return 0
        if label == "LIMITS_TO_GROWTH_DISCOURSE":
            return 1
        if label == "LOW_CONFIDENCE":
            return 2
        return 3

    selected = sorted(rows, key=priority)
    return selected if limit <= 0 else selected[:limit]


def select_v2_rows(rows: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
    """Select a deterministic dry-run set that includes difficult and lower-risk groups."""
    if limit <= 0 or limit >= len(rows):
        return rows

    def is_candidate(row: Dict[str, str]) -> bool:
        text = " ".join([
            row.get("v1_llm_primary_role", ""),
            row.get("v1_llm_stance", ""),
            row.get("fallback_primary_role", ""),
            row.get("review_reason", ""),
        ]).lower()
        return "critique" in text or "supportive" in text or "critical" in text

    buckets = [
        [r for r in rows if is_candidate(r)],
        [r for r in rows if r.get("group_has_context_window_pilot") == "yes"],
        [r for r in rows if r.get("group_has_boundary_case") == "yes"],
        [r for r in rows if r.get("group_has_human_coding") == "yes"],
        [r for r in rows if r.get("review_priority") != "high"],
        rows,
    ]
    selected: List[Dict[str, str]] = []
    seen = set()
    bucket_index = 0
    while len(selected) < limit and bucket_index < max(map(len, buckets), default=0):
        for bucket in buckets:
            if bucket_index >= len(bucket):
                continue
            row = bucket[bucket_index]
            group_id = row.get("context_group_id")
            if group_id not in seen:
                selected.append(row)
                seen.add(group_id)
                if len(selected) == limit:
                    break
        bucket_index += 1
    return selected


def select_v2_regression_rows(rows: List[Dict[str, str]], limit: int, prior_invalid_ids: set[str]) -> List[Dict[str, str]]:
    """Prioritize prior mechanical failures and stance-risk cases."""
    if limit <= 0 or limit >= len(rows):
        return rows

    def stance_risk(row: Dict[str, str]) -> bool:
        return row.get("v1_llm_stance") in {"supportive", "critical", "mixed"} or row.get("human_stance_toward_seed") in {"supportive", "critical", "mixed"}

    def bibliography_candidate(row: Dict[str, str]) -> bool:
        text = " ".join([
            row.get("v1_llm_primary_role", ""),
            row.get("v1_llm_uncertainty_flags", ""),
            row.get("human_notes", ""),
            row.get("review_reason", ""),
        ]).lower()
        return boolish(row.get("bibliography_detected")) or row.get("citation_section") == "BIBLIO" or "bibliograph" in text

    buckets = [
        [row for row in rows if row.get("context_group_id") in prior_invalid_ids],
        [row for row in rows if stance_risk(row)],
        [row for row in rows if bibliography_candidate(row)],
        [row for row in rows if row.get("group_has_boundary_case") == "yes"],
        [row for row in rows if row.get("group_has_context_window_pilot") == "yes"],
        rows,
    ]
    selected, seen = [], set()
    index = 0
    while len(selected) < limit and index < max(map(len, buckets), default=0):
        for bucket in buckets:
            if index >= len(bucket):
                continue
            row = bucket[index]
            group_id = row.get("context_group_id")
            if group_id not in seen:
                selected.append(row)
                seen.add(group_id)
                if len(selected) == limit:
                    break
        index += 1
    return selected


def fallback_classification(row: Dict[str, str]) -> Dict[str, Any]:
    snippet = (row.get("snippet") or "").lower()
    roles = []
    for role, needles in ROLE_FALLBACKS.items():
        if any(needle in snippet for needle in needles):
            roles.append(role)
    role_map = {
        "sustainability_limits_to_growth_discourse": "sustainability_discourse",
        "policy_governance_framing": "policy_governance_framing",
        "modeling_simulation_reference": "modeling_simulation_reference",
        "historical_framing": "historical_framing",
        "critique": "critique",
        "foundational_citation": "foundational_citation",
        "background_or_ambiguous": "unclear",
    }
    roles = [role_map.get(r, r) for r in roles]
    if not roles:
        roles = ["foundational_citation"] if row.get("semantic_label") == "MEADOWS_1972_BOOK" else ["unclear"]
    if row.get("citation_section") == "BIBLIO":
        roles = ["bibliographic_only"] + [r for r in roles if r != "bibliographic_only"]
    primary = roles[0]
    is_seed = "yes" if row.get("semantic_label") == "MEADOWS_1972_BOOK" else "ambiguous"
    confidence = 0.78 if is_seed == "yes" else 0.45
    if row.get("citation_section") == "BIBLIO":
        confidence = min(confidence, 0.65)
    discourse = "bibliographic_record" if row.get("citation_section") == "BIBLIO" else "limits_to_growth"
    if "modeling_simulation_reference" in roles:
        discourse = "system_dynamics_modeling"
    elif "policy_governance_framing" in roles:
        discourse = "environmental_policy"
    elif "sustainability_discourse" in roles:
        discourse = "sustainability"
    flags = ["bibliography_only"] if row.get("citation_section") == "BIBLIO" else ["missing_surrounding_context"]
    if row.get("semantic_label") != "MEADOWS_1972_BOOK":
        flags = list(dict.fromkeys(flags + ["ambiguous_referent"]))
    return {
        "context_id": context_id(row),
        "is_seed_work_citation": is_seed,
        "citation_role": primary,
        "citation_roles": roles,
        "primary_role": primary,
        "discourse_category": discourse,
        "stance_toward_meadows": "unclear",
        "stance_toward_seed": "unclear",
        "reasoning_summary": "Rule-based fallback classification; use LLM or human validation for interpretive claims.",
        "interpretive_summary": "Rule-based fallback classification; use LLM or human validation for interpretive claims.",
        "confidence": confidence,
        "evidence_quote": (row.get("snippet") or "")[:260],
        "uncertainty_flags": flags,
        "limitations": flags,
        "needs_human_review": confidence < 0.8 or row.get("semantic_label") != "MEADOWS_1972_BOOK",
    }


def build_user_payload(row: Dict[str, str]) -> str:
    payload = {
        "context_id": context_id(row),
        "source_document_id": row.get("source_document_id"),
        "page": row.get("page"),
        "rule_semantic_label": row.get("semantic_label"),
        "rule_citation_function": row.get("citation_function"),
        "citation_section": row.get("citation_section"),
        "matched_text": row.get("match"),
        "snippet": row.get("snippet"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def build_v2_user_payload(row: Dict[str, str]) -> str:
    citation_sentence = row.get("citation_sentence", "").strip()
    sentence_before = row.get("sentence_before", "").strip()
    sentence_after = row.get("sentence_after", "").strip()
    limited_context = not citation_sentence or not (sentence_before or sentence_after)
    payload = {
        "context_group_id": row.get("context_group_id"),
        "representative_context_id": row.get("canonical_context_id") or row.get("mention_level_id"),
        "title_for_traceability_only": row.get("title"),
        "year_for_traceability_only": row.get("year"),
        "venue_for_traceability_only": row.get("venue"),
        "citation_sentence": citation_sentence,
        "sentence_before": sentence_before,
        "sentence_after": sentence_after,
        "legacy_snippet": row.get("snippet_clean"),
        "bibliography_detected": boolish(row.get("bibliography_detected")),
        "bibliography_score": row.get("bibliography_score"),
        "extraction_confidence": row.get("extraction_confidence", ""),
        "limited_context": limited_context,
        "needs_human_review_expected": limited_context,
        "comparison_labels_withheld_from_model": True,
        "traceability": {
            "group_member_count": row.get("group_member_count"),
            "is_repeated_context": boolish(row.get("is_repeated_context")),
        },
    }
    # Human, v1, and fallback labels remain in the input snapshot/audit join but
    # are withheld from the model payload to avoid contaminating evaluation.
    return json.dumps(payload, ensure_ascii=False, indent=2)


def v2_withheld_fields(input_fields: Iterable[str]) -> List[str]:
    return sorted(
        field for field in input_fields
        if any(pattern in field.lower() for pattern in V2_WITHHELD_FIELD_PATTERNS)
    )


def validate_v2_input_file(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"MEADOWS_LLM_INPUT_FILE does not exist: {path}")
    rows = read_csv(path)
    if not rows:
        raise ValueError(f"V2 input file has no data rows: {path}")
    fields = set(rows[0])
    missing = sorted(V2_INPUT_REQUIRED_FIELDS - fields)
    if missing:
        raise ValueError(f"V2 input file is missing required fields: {', '.join(missing)}")
    if not ({"canonical_context_id", "mention_level_id"} & fields):
        raise ValueError("V2 input file requires canonical_context_id or mention_level_id.")
    blank_groups = [index + 2 for index, row in enumerate(rows) if not row.get("context_group_id", "").strip()]
    blank_ids = [
        index + 2 for index, row in enumerate(rows)
        if not (row.get("canonical_context_id", "").strip() or row.get("mention_level_id", "").strip())
    ]
    if blank_groups or blank_ids:
        raise ValueError(
            f"V2 input contains blank identifiers; context_group_id rows={blank_groups}, context_id rows={blank_ids}"
        )
    return rows


def v2_run_paths(root: Path, run_name: str = "") -> Dict[str, Path]:
    if run_name:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_name):
            raise ValueError("MEADOWS_LLM_RUN_NAME must contain only letters, numbers, underscores, or hyphens.")
        output_dir = root / "analysis/data/llm_output/v2"
        return {
            "input_snapshot": root / f"analysis/data/llm_input/v2/{run_name}_input.csv",
            "output_file": output_dir / f"{run_name}_classifications.csv",
            "output_jsonl": output_dir / f"{run_name}_classifications.jsonl",
            "initial_jsonl": output_dir / f"{run_name}_initial.jsonl",
            "repaired_jsonl": output_dir / f"{run_name}_repaired.jsonl",
            "audit_file": root / f"analysis/audit/v2/{run_name}_audit.jsonl",
            "diagnostic_file": root / f"analysis/logs/{run_name}_diagnostic.csv",
            "payload_manifest": root / f"analysis/logs/{run_name}_payload_manifest.json",
        }
    return {
        "input_snapshot": root / "analysis/data/llm_input/v2/regression/citation_contexts_for_classification_v2_regression.csv",
        "output_file": root / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression.csv",
        "output_jsonl": root / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression_accepted.jsonl",
        "initial_jsonl": root / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression_initial.jsonl",
        "repaired_jsonl": root / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression_repaired.jsonl",
        "audit_file": root / "analysis/audit/v2/regression/llm_classification_audit_v2_regression.jsonl",
        "diagnostic_file": root / "analysis/logs/llm_classification_diagnostic_v2_regression.csv",
        "payload_manifest": root / "analysis/logs/llm_classification_payload_manifest_v2_regression.json",
    }


def supplied_v2_context(row: Dict[str, str]) -> str:
    parts = [
        row.get("citation_sentence", ""),
        row.get("sentence_before", ""),
        row.get("sentence_after", ""),
        row.get("snippet_clean", ""),
    ]
    return "\n".join(part for part in parts if part)


def validate_v2_result(result: Dict[str, Any], row: Dict[str, str], schema: Dict[str, Any]) -> Dict[str, Any]:
    properties = schema["properties"]
    missing = [field for field in V2_REQUIRED_FIELDS if field not in result]
    invalid_categories = []
    for field in ("citation_function", "topic_or_discourse_area", "stance_toward_seed"):
        if result.get(field) not in properties[field]["enum"]:
            invalid_categories.append(field)
    invalid_confidence = []
    for field in ("confidence_function", "confidence_topic", "confidence_stance"):
        value = result.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
            invalid_confidence.append(field)
    flags = result.get("uncertainty_flags")
    invalid_flags = (
        not isinstance(flags, list)
        or not flags
        or any(flag not in properties["uncertainty_flags"]["items"]["enum"] for flag in (flags or []))
        or ("none" in (flags or []) and len(flags) > 1)
    )
    invalid_schema_fields = []
    if not isinstance(result.get("needs_human_review"), bool):
        invalid_schema_fields.append("needs_human_review")
    if not isinstance(result.get("reasoning_summary"), str) or len(result.get("reasoning_summary", "")) > properties["reasoning_summary"]["maxLength"]:
        invalid_schema_fields.append("reasoning_summary")
    for field in ("context_id", "context_group_id", "evidence_quote_function", "evidence_quote_topic", "evidence_quote_stance"):
        value = result.get(field)
        prop = properties[field]
        if not isinstance(value, str) or len(value) < prop.get("minLength", 0) or len(value) > prop.get("maxLength", float("inf")):
            invalid_schema_fields.append(field)
    supplied = supplied_v2_context(row)
    supplied_lower = supplied.lower()
    quote_exact = {}
    quote_valid = {}
    quote_abstained = {}
    empty_evidence = []
    for field in ("evidence_quote_function", "evidence_quote_topic", "evidence_quote_stance"):
        quote = result.get(field, "")
        if not isinstance(quote, str) or not quote.strip():
            empty_evidence.append(field)
            quote_exact[field] = False
            quote_valid[field] = False
            quote_abstained[field] = False
        else:
            quote_abstained[field] = quote == CONTROLLED_ABSTENTION
            quote_exact[field] = quote in supplied and not quote_abstained[field]
            quote_valid[field] = quote_abstained[field] or quote_exact[field]
    expected_context_id = row.get("canonical_context_id") or row.get("mention_level_id")
    expected_group_id = row.get("context_group_id")
    identifiers_match = result.get("context_id") == expected_context_id and result.get("context_group_id") == expected_group_id
    limited_context = not row.get("citation_sentence", "").strip() or not (
        row.get("sentence_before", "").strip() or row.get("sentence_after", "").strip()
    )
    uncertainty_flags = result.get("uncertainty_flags", [])
    clear_bibliography = (
        result.get("citation_function") == "bibliographic_only"
        and uncertainty_flags in (["none"], ["bibliography_only"])
        and quote_valid.get("evidence_quote_function", False)
    )
    review_expected = (
        (limited_context and not clear_bibliography)
        or (uncertainty_flags != ["none"] and not clear_bibliography)
    )
    review_policy_compliant = not review_expected or result.get("needs_human_review") is True
    category_tokens = {
        "historical_framing", "modeling_simulation_reference", "foundational_citation",
        "critique", "policy_governance_framing", "bibliographic_only", "unclear",
        "supportive", "neutral_descriptive", "critical", "mixed",
    }
    evidence_uses_category_token = any(result.get(field, "").strip() in category_tokens for field in quote_valid)
    evidence_assignment_compliant = (
        (result.get("citation_function") == "unclear" or not quote_abstained["evidence_quote_function"])
        and (result.get("topic_or_discourse_area") == "unclear" or not quote_abstained["evidence_quote_topic"])
        and (
            result.get("stance_toward_seed") in {"neutral_descriptive", "unclear"}
            or not quote_abstained["evidence_quote_stance"]
        )
    )
    evaluative_stance = result.get("stance_toward_seed") in {"supportive", "critical", "mixed"}
    stance_quote = str(result.get("evidence_quote_stance", "")).lower()
    positive_cue = any(cue in stance_quote for cue in POSITIVE_STANCE_CUES)
    negative_cue = any(cue in stance_quote for cue in NEGATIVE_STANCE_CUES)
    stance_cue_compliant = (
        result.get("stance_toward_seed") not in {"supportive", "critical", "mixed"}
        or (result.get("stance_toward_seed") == "supportive" and positive_cue and not negative_cue)
        or (result.get("stance_toward_seed") == "critical" and negative_cue and not positive_cue)
        or (result.get("stance_toward_seed") == "mixed" and positive_cue and negative_cue)
    )
    stance_evidence_policy_compliant = (
        not evaluative_stance
        or (
            bool(result.get("evidence_quote_stance", "").strip())
            and quote_exact["evidence_quote_stance"]
            and not evidence_uses_category_token
            and result.get("evidence_quote_stance") != CONTROLLED_ABSTENTION
            and stance_cue_compliant
        )
    )
    validation_errors = []
    if missing:
        validation_errors.append("missing_required_fields")
    if invalid_categories:
        validation_errors.append("invalid_category")
    if invalid_confidence:
        validation_errors.append("invalid_confidence")
    if invalid_flags:
        validation_errors.append("invalid_uncertainty_flags")
    if invalid_schema_fields:
        validation_errors.append("invalid_schema_fields")
    if not identifiers_match:
        validation_errors.append("identifier_mismatch")
    if empty_evidence:
        validation_errors.append("empty_evidence")
    if not all(quote_valid.values()):
        validation_errors.append("non_exact_evidence")
    if evidence_uses_category_token:
        validation_errors.append("category_token_as_evidence")
    if not evidence_assignment_compliant:
        validation_errors.append("unsupported_label_without_evidence")
    if not review_policy_compliant:
        validation_errors.append("review_policy_failure")
    if not stance_evidence_policy_compliant:
        validation_errors.append("stance_evidence_failure")
    accepted = not validation_errors
    return {
        "schema_compliant": not missing and not invalid_categories and not invalid_confidence and not invalid_flags and not invalid_schema_fields and identifiers_match,
        "deterministically_valid": accepted,
        "validation_errors": " | ".join(validation_errors),
        "identifiers_match": identifiers_match,
        "returned_context_id": result.get("context_id", ""),
        "returned_context_group_id": result.get("context_group_id", ""),
        "missing_required_fields": " | ".join(missing),
        "invalid_category_fields": " | ".join(invalid_categories),
        "invalid_confidence_fields": " | ".join(invalid_confidence),
        "invalid_uncertainty_flags": invalid_flags,
        "invalid_schema_fields": " | ".join(invalid_schema_fields),
        "empty_evidence_fields": " | ".join(empty_evidence),
        "evidence_quote_function_exact": quote_exact["evidence_quote_function"],
        "evidence_quote_topic_exact": quote_exact["evidence_quote_topic"],
        "evidence_quote_stance_exact": quote_exact["evidence_quote_stance"],
        "evidence_quote_function_abstained": quote_abstained["evidence_quote_function"],
        "evidence_quote_topic_abstained": quote_abstained["evidence_quote_topic"],
        "evidence_quote_stance_abstained": quote_abstained["evidence_quote_stance"],
        "all_evidence_fields_valid": all(quote_valid.values()),
        "all_nonabstention_evidence_quotes_exact": all(
            quote_exact[field] for field in quote_exact if not quote_abstained[field]
        ),
        "all_nonempty_evidence_quotes_exact": all(quote_exact.values()),
        "review_policy_compliant": review_policy_compliant,
        "evidence_uses_category_token": evidence_uses_category_token,
        "evidence_assignment_compliant": evidence_assignment_compliant,
        "stance_evidence_policy_compliant": stance_evidence_policy_compliant,
        "stance_cue_compliant": stance_cue_compliant,
    }


def build_v2_repair_payload(row: Dict[str, str], invalid_result: Dict[str, Any], validation: Dict[str, Any], schema: Dict[str, Any]) -> str:
    return json.dumps({
        "original_input": json.loads(build_v2_user_payload(row)),
        "invalid_output": {key: value for key, value in invalid_result.items() if key != "_usage"},
        "validation_errors": validation["validation_errors"].split(" | "),
        "required_schema": schema,
    }, ensure_ascii=False, indent=2)


def classify_with_openai(row: Dict[str, str], prompt: str, schema: Dict[str, Any], model: str) -> Dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": build_user_payload(row)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "citation_context_classification",
                "schema": schema,
                "strict": True,
            }
        },
    )
    result = json.loads(response.output_text)
    usage = getattr(response, "usage", None)
    if usage is not None:
        result["_usage"] = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return result


def classify_v2_with_openai(row: Dict[str, str], prompt: str, schema: Dict[str, Any], model: str) -> Dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        max_output_tokens=1200,
        input=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": build_v2_user_payload(row)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "citation_context_classification_v2",
                "schema": schema,
                "strict": True,
            }
        },
    )
    result = json.loads(response.output_text)
    usage = getattr(response, "usage", None)
    if usage is not None:
        result["_usage"] = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return result


def repair_v2_with_openai(row: Dict[str, str], result: Dict[str, Any], validation: Dict[str, Any], repair_prompt: str, schema: Dict[str, Any], model: str) -> Dict[str, Any]:
    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        max_output_tokens=1200,
        input=[
            {"role": "system", "content": repair_prompt},
            {"role": "user", "content": build_v2_repair_payload(row, result, validation, schema)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "citation_context_classification_v2_repair",
                "schema": schema,
                "strict": True,
            }
        },
    )
    repaired = json.loads(response.output_text)
    usage = getattr(response, "usage", None)
    if usage is not None:
        repaired["_usage"] = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return repaired


def error_result(row: Dict[str, str], error: Exception) -> Dict[str, Any]:
    return {
        "context_id": context_id(row),
        "is_seed_work_citation": "",
        "citation_role": "",
        "citation_roles": [],
        "discourse_category": "",
        "stance_toward_meadows": "",
        "reasoning_summary": f"Classification failed: {type(error).__name__}",
        "confidence": "",
        "evidence_quote": "",
        "uncertainty_flags": ["missing_surrounding_context"],
        "needs_human_review": True,
        "_error_type": type(error).__name__,
        "_error_message": str(error),
    }


def flatten_result(row: Dict[str, str], result: Dict[str, Any], model: str, mode: str) -> Dict[str, Any]:
    output_hash = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    usage = result.get("_usage", {}) if isinstance(result.get("_usage", {}), dict) else {}
    citation_roles = list(dict.fromkeys(result.get("citation_roles", [])))
    uncertainty_flags = list(dict.fromkeys(result.get("uncertainty_flags", result.get("limitations", []))))
    return {
        "context_id": result.get("context_id", context_id(row)),
        "source_document_id": row.get("source_document_id"),
        "page": row.get("page"),
        "rule_semantic_label": row.get("semantic_label"),
        "rule_citation_function": row.get("citation_function"),
        "citation_section": row.get("citation_section"),
        "llm_is_seed_work_citation": result.get("is_seed_work_citation"),
        "llm_citation_roles": " | ".join(citation_roles),
        "llm_primary_role": result.get("citation_role") or result.get("primary_role"),
        "llm_discourse_category": result.get("discourse_category"),
        "llm_stance_toward_meadows": result.get("stance_toward_meadows") or result.get("stance_toward_seed"),
        "llm_stance_toward_seed": result.get("stance_toward_meadows") or result.get("stance_toward_seed"),
        "llm_interpretive_summary": result.get("reasoning_summary") or result.get("interpretive_summary"),
        "llm_confidence": result.get("confidence"),
        "llm_evidence_quote": result.get("evidence_quote"),
        "llm_uncertainty_flags": " | ".join(uncertainty_flags),
        "llm_limitations": " | ".join(uncertainty_flags),
        "llm_needs_human_review": result.get("needs_human_review"),
        "model": model,
        "classification_mode": mode,
        "prompt_version": "citation_context_classification_v3",
        "schema_version": "citation_context_classification_schema_v2",
        "input_hash": context_id(row),
        "output_hash": output_hash,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "error_type": result.get("_error_type"),
        "error_message": result.get("_error_message"),
        "classified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def flatten_v2_result(
    row: Dict[str, str],
    result: Dict[str, Any],
    model: str,
    mode: str,
    validation: Dict[str, Any],
    classification_status: str = "",
    initial_validation_errors: str = "",
    classification_source: str = "llm",
    routing: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    output_hash = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    usage = result.get("_usage", {}) if isinstance(result.get("_usage", {}), dict) else {}
    payload = build_v2_user_payload(row)
    return {
        "context_group_id": row.get("context_group_id"),
        "context_id": row.get("canonical_context_id") or row.get("mention_level_id"),
        "citation_function": result.get("citation_function", ""),
        "topic_or_discourse_area": result.get("topic_or_discourse_area", ""),
        "stance_toward_seed": result.get("stance_toward_seed", ""),
        "evidence_quote_function": result.get("evidence_quote_function", ""),
        "evidence_quote_topic": result.get("evidence_quote_topic", ""),
        "evidence_quote_stance": result.get("evidence_quote_stance", ""),
        "confidence_function": result.get("confidence_function", ""),
        "confidence_topic": result.get("confidence_topic", ""),
        "confidence_stance": result.get("confidence_stance", ""),
        "uncertainty_flags": " | ".join(result.get("uncertainty_flags", [])),
        "needs_human_review": result.get("needs_human_review", True),
        "reasoning_summary": result.get("reasoning_summary", ""),
        "limited_context": json.loads(payload)["limited_context"],
        "classification_status": classification_status,
        "classification_source": classification_source,
        "initial_validation_errors": initial_validation_errors,
        **(routing or {}),
        **validation,
        "model": model,
        "classification_mode": mode,
        "prompt_version": "citation_context_classification_v2",
        "schema_version": "citation_context_classification_v2",
        "input_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "output_hash": output_hash,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "error_type": result.get("_error_type", ""),
        "error_message": result.get("_error_message", ""),
        "classified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def v2_error_result(row: Dict[str, str], error: Exception) -> Dict[str, Any]:
    return {
        "context_id": row.get("canonical_context_id") or row.get("mention_level_id", ""),
        "context_group_id": row.get("context_group_id", ""),
        "citation_function": "",
        "topic_or_discourse_area": "",
        "stance_toward_seed": "",
        "evidence_quote_function": "",
        "evidence_quote_topic": "",
        "evidence_quote_stance": "",
        "confidence_function": "",
        "confidence_topic": "",
        "confidence_stance": "",
        "uncertainty_flags": ["missing_surrounding_context"],
        "needs_human_review": True,
        "reasoning_summary": f"Classification failed: {type(error).__name__}",
        "_error_type": type(error).__name__,
        "_error_message": str(error),
    }


def run_v2(root: Path, cfg: Dict[str, Any], enabled: bool, model: str, limit: int) -> None:
    input_override = os.getenv("MEADOWS_LLM_INPUT_FILE", "").strip()
    run_name = os.getenv("MEADOWS_LLM_RUN_NAME", "").strip()
    input_file = Path(input_override).expanduser() if input_override else root / "analysis/validation/v2_classifier_pilot_input_100_ready.csv"
    if not input_file.is_absolute():
        input_file = root / input_file
    paths = v2_run_paths(root, run_name)
    output_file = paths["output_file"]
    initial_jsonl = paths["initial_jsonl"]
    repaired_jsonl = paths["repaired_jsonl"]
    output_jsonl = paths["output_jsonl"]
    audit_file = paths["audit_file"]
    diagnostic_file = paths["diagnostic_file"]
    prompt = (root / "prompts/citation_context_classification_v2.md").read_text(encoding="utf-8")
    repair_prompt = (root / "prompts/citation_context_classification_v2_repair.md").read_text(encoding="utf-8")
    repair_enabled = os.getenv("MEADOWS_V2_ENABLE_REPAIR", "false").lower() == "true"
    schema = json.loads((root / "schemas/citation_context_classification_v2.schema.json").read_text(encoding="utf-8"))
    prior_output = root / "analysis/data/llm_output/v2/citation_context_classifications_v2.csv"
    prior_invalid_ids = {
        row["context_group_id"]
        for row in read_csv(prior_output)
        if row.get("deterministically_valid", row.get("all_nonempty_evidence_quotes_exact", "")).lower() != "true"
    } if prior_output.exists() else set()
    all_rows = validate_v2_input_file(input_file)
    rows = (all_rows if limit <= 0 else all_rows[:limit]) if input_override else select_v2_regression_rows(all_rows, limit, prior_invalid_ids)
    if run_name:
        existing = [path for path in paths.values() if path.exists() and path.stat().st_size > 0]
        if existing:
            raise FileExistsError(
                "Refusing to overwrite existing namespaced v2 run artifacts: "
                + ", ".join(str(path.relative_to(root)) for path in existing)
            )
    input_fields = list(all_rows[0])
    withheld_fields = v2_withheld_fields(input_fields)
    leaked_fields = sorted(set(V2_PAYLOAD_FIELDS) & set(withheld_fields))
    payload_manifest = {
        "run_name": run_name or "legacy_v2_regression",
        "input_file": str(input_file.relative_to(root) if input_file.is_relative_to(root) else input_file),
        "input_override_used": bool(input_override),
        "input_row_count": len(all_rows),
        "selected_row_count": len(rows),
        "limit": limit,
        "payload_fields_sent": V2_PAYLOAD_FIELDS,
        "withheld_fields_present_in_input": withheld_fields,
        "label_fields_excluded": not leaked_fields,
        "unexpected_label_fields_in_payload": leaked_fields,
    }
    if leaked_fields:
        raise ValueError(f"V2 payload leaks withheld comparison fields: {', '.join(leaked_fields)}")
    write_csv(paths["input_snapshot"], rows)
    paths["payload_manifest"].parent.mkdir(parents=True, exist_ok=True)
    paths["payload_manifest"].write_text(json.dumps(payload_manifest, indent=2), encoding="utf-8")
    print(f"V2 input: {input_file} ({len(all_rows)} rows; {len(rows)} selected).")
    print(f"V2 run name: {run_name or 'legacy_v2_regression'}")
    print(f"Payload label fields excluded: {payload_manifest['label_fields_excluded']}")

    for path in (initial_jsonl, repaired_jsonl, output_jsonl, audit_file, diagnostic_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    routes = {row.get("context_group_id"): route_context(row) for row in rows}
    route_records = []
    for row in rows:
        route = routes[row.get("context_group_id")]
        record = route_to_record(row, route)
        human_function = row.get("manual_recommended_citation_function") or row.get("human_primary_role", "")
        human_topic = row.get("manual_recommended_topic_or_discourse_area") or row.get("human_discourse_category", "")
        human_stance = row.get("manual_recommended_stance_toward_seed") or row.get("human_stance_toward_seed", "")
        record.update({
            "human_function_reference": human_function,
            "human_topic_reference": human_topic,
            "human_stance_reference": human_stance,
            "router_human_function_agreement": (
                str(route.routed_citation_function == human_function).lower()
                if human_function and not route.send_to_llm else ""
            ),
            "router_human_topic_agreement": (
                str(route.routed_topic_or_discourse_area == human_topic).lower()
                if human_topic and not route.send_to_llm else ""
            ),
            "router_human_stance_agreement": (
                str(route.routed_stance_toward_seed == human_stance).lower()
                if human_stance and not route.send_to_llm else ""
            ),
        })
        route_records.append(record)
    rule_hits = []
    llm_queue = []
    for row in rows:
        route = routes[row.get("context_group_id")]
        record = route_to_record(row, route)
        if route.send_to_llm:
            llm_queue.append({**row, **record})
        for rule in route.rule_hits:
            rule_hits.append({
                "run_name": run_name or "legacy_v2_regression",
                "context_group_id": row.get("context_group_id"),
                "context_id": row.get("canonical_context_id") or row.get("mention_level_id"),
                "rule_hit": rule,
                "routing_decision": route.routing_decision,
                "send_to_llm": route.send_to_llm,
            })
    router_prefix = run_name or "v2_router"
    router_audit_path = root / f"analysis/tables/{router_prefix}_router_audit.csv" if run_name else root / "analysis/tables/v2_router_audit.csv"
    router_rule_hits_path = root / f"analysis/tables/{router_prefix}_rule_hits.csv" if run_name else root / "analysis/tables/v2_router_rule_hits.csv"
    router_llm_queue_path = root / f"analysis/tables/{router_prefix}_llm_queue.csv" if run_name else root / "analysis/tables/v2_router_llm_queue.csv"
    write_csv(router_audit_path, [
        {"run_name": run_name or "legacy_v2_regression", **record} for record in route_records
    ])
    write_csv(router_rule_hits_path, rule_hits)
    write_csv(router_llm_queue_path, llm_queue)
    if run_name:
        write_csv(root / "analysis/tables/v2_router_audit.csv", [
            {"run_name": run_name or "legacy_v2_regression", **record} for record in route_records
        ])
        write_csv(root / "analysis/tables/v2_router_rule_hits.csv", rule_hits)
        write_csv(root / "analysis/tables/v2_router_llm_queue.csv", llm_queue)
    print(
        "V2 router: "
        f"{sum(not route.send_to_llm for route in routes.values())} deterministic, "
        f"{sum(route.send_to_llm for route in routes.values())} sent to LLM."
    )

    out_rows: List[Dict[str, Any]] = []
    for row in rows:
        started = dt.datetime.now(dt.timezone.utc)
        retries = 0
        repair_attempted = False
        initial_result: Dict[str, Any] = {}
        repaired_result: Dict[str, Any] = {}
        initial_validation: Dict[str, Any] = {}
        route = routes[row.get("context_group_id")]
        routing_record = route_to_record(row, route)
        try:
            if not route.send_to_llm:
                result = route.result or v2_error_result(row, RuntimeError("Router produced no deterministic result."))
                validation = validate_v2_result(result, row, schema)
                classification_status = "router_valid" if validation["deterministically_valid"] else "rejected_router_validation"
                mode = "deterministic_router_v2"
            elif not enabled:
                raise RuntimeError("V2 classification requires MEADOWS_ENABLE_LLM=true; no rule fallback is written to v2 outputs.")
            else:
                while True:
                    try:
                        result = classify_v2_with_openai(row, prompt, schema, model)
                        break
                    except Exception:
                        retries += 1
                        if retries > 2:
                            raise
                        time.sleep(2 * retries)
                initial_result = result
                initial_validation = validate_v2_result(initial_result, row, schema)
                append_jsonl(initial_jsonl, {
                    "context_group_id": row.get("context_group_id"),
                    "phase": "initial",
                    "routing": routing_record,
                    "output": {key: value for key, value in initial_result.items() if key != "_usage"},
                    "validation": initial_validation,
                })
                if initial_validation["deterministically_valid"]:
                    result = initial_result
                    validation = initial_validation
                    classification_status = "initial_valid"
                    mode = "openai_json_schema_v2"
                else:
                    if repair_enabled:
                        repair_attempted = True
                        repaired_result = repair_v2_with_openai(row, initial_result, initial_validation, repair_prompt, schema, model)
                        repair_validation = validate_v2_result(repaired_result, row, schema)
                        append_jsonl(repaired_jsonl, {
                            "context_group_id": row.get("context_group_id"),
                            "phase": "repair",
                            "routing": routing_record,
                            "output": {key: value for key, value in repaired_result.items() if key != "_usage"},
                            "validation": repair_validation,
                        })
                        result = repaired_result
                        validation = repair_validation
                        classification_status = "repaired_valid" if repair_validation["deterministically_valid"] else "rejected_after_repair"
                    else:
                        result = initial_result
                        validation = initial_validation
                        classification_status = "rejected_initial_validation"
                    if classification_status in {"rejected_after_repair", "rejected_initial_validation"}:
                        result["needs_human_review"] = True
                        validation = validate_v2_result(result, row, schema)
                    mode = "openai_json_schema_v2_repaired"
            status = classification_status
        except Exception as exc:
            result = v2_error_result(row, exc)
            mode = "openai_error_v2"
            validation = validate_v2_result(result, row, schema)
            classification_status = "api_error"
            status = "error"

        ended = dt.datetime.now(dt.timezone.utc)
        flat = flatten_v2_result(
            row,
            result,
            model,
            mode,
            validation,
            classification_status,
            initial_validation.get("validation_errors", ""),
            "llm" if route.send_to_llm else "deterministic_router",
            routing_record,
        )
        out_rows.append(flat)
        if classification_status in {"initial_valid", "repaired_valid"}:
            append_jsonl(output_jsonl, {
                "context_group_id": row.get("context_group_id"),
                "classification_status": classification_status,
                "output": {key: value for key, value in result.items() if key != "_usage"},
            })
        initial_usage = initial_result.get("_usage", {}) if initial_result else {}
        repair_usage = repaired_result.get("_usage", {}) if repaired_result else {}
        append_jsonl(audit_file, {
            "context_group_id": row.get("context_group_id"),
            "context_id": row.get("canonical_context_id") or row.get("mention_level_id"),
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "latency_seconds": (ended - started).total_seconds(),
            "model": model,
            "mode": mode,
            "status": status,
            "retries": retries,
            "repair_attempted": repair_attempted,
            "classification_source": flat["classification_source"],
            "routing": routing_record,
            "actual_api_call": route.send_to_llm,
            "input_hash": flat["input_hash"],
            "output_hash": flat["output_hash"],
            "initial_validation": initial_validation,
            "final_validation": validation,
            "initial_usage": initial_usage,
            "repair_usage": repair_usage,
            "validation": validation,
            "error_type": result.get("_error_type", ""),
            "error": result.get("_error_message", ""),
        })
        append_csv(diagnostic_file, {
            "context_group_id": flat["context_group_id"],
            "context_id": flat["context_id"],
            "status": status,
            "classification_status": classification_status,
            "model": model,
            "run_name": run_name or "legacy_v2_regression",
            "classification_source": flat["classification_source"],
            "actual_api_call": route.send_to_llm,
            "retries": retries,
            "repair_attempted": repair_attempted,
            **routing_record,
            "latency_seconds": (ended - started).total_seconds(),
            "schema_compliant": validation["schema_compliant"],
            "deterministically_valid": validation["deterministically_valid"],
            "validation_errors": validation["validation_errors"],
            "all_evidence_fields_valid": validation["all_evidence_fields_valid"],
            "all_nonabstention_evidence_quotes_exact": validation["all_nonabstention_evidence_quotes_exact"],
            "identifiers_match": validation["identifiers_match"],
            "stance_evidence_policy_compliant": validation["stance_evidence_policy_compliant"],
            "payload_fields_sent": " | ".join(V2_PAYLOAD_FIELDS),
            "withheld_fields": " | ".join(withheld_fields),
            "label_fields_excluded": not leaked_fields,
            "initial_input_tokens": initial_usage.get("input_tokens"),
            "initial_output_tokens": initial_usage.get("output_tokens"),
            "initial_total_tokens": initial_usage.get("total_tokens"),
            "repair_input_tokens": repair_usage.get("input_tokens"),
            "repair_output_tokens": repair_usage.get("output_tokens"),
            "repair_total_tokens": repair_usage.get("total_tokens"),
            "error_type": flat["error_type"],
            "error_message": flat["error_message"],
        })

    write_csv(output_file, out_rows)
    write_jsonl(output_jsonl, out_rows)
    print(f"Wrote isolated v2 regression output: {output_file} ({len(out_rows)} rows).")
    print(f"V2 regression diagnostic: {diagnostic_file}")


def main() -> None:
    root = Path.cwd()
    cfg = read_yaml_simple(root / "config" / "llm.yml")["classification"]
    enabled = os.getenv(cfg["enabled_env"], "false").lower() == "true"
    model = os.getenv(cfg["model_env"], cfg["default_model"])
    limit = int(os.getenv(cfg["max_contexts_env"], str(cfg["default_max_contexts"])))
    schema_version = os.getenv("MEADOWS_LLM_SCHEMA_VERSION", "v1").lower()

    if schema_version == "v2":
        run_v2(root, cfg, enabled, model, limit)
        return
    if schema_version != "v1":
        raise ValueError(f"Unsupported MEADOWS_LLM_SCHEMA_VERSION={schema_version!r}; expected v1 or v2.")

    input_file = root / cfg["input_file"]
    output_file = root / cfg["output_file"]
    audit_file = root / cfg["audit_file"]
    prompt = (root / cfg["prompt_file"]).read_text(encoding="utf-8")
    schema = json.loads((root / cfg["schema_file"]).read_text(encoding="utf-8"))

    rows = select_rows(read_csv(input_file), limit)
    input_snapshot = root / "analysis" / "data" / "llm_input" / "citation_contexts_for_classification.csv"
    write_csv(input_snapshot, rows)

    out_rows: List[Dict[str, Any]] = []
    for row in rows:
        started_at = dt.datetime.now(dt.timezone.utc).isoformat()
        retries = 0
        try:
            if enabled:
                while True:
                    try:
                        result = classify_with_openai(row, prompt, schema, model)
                        break
                    except Exception:
                        retries += 1
                        if retries > 2:
                            raise
                        time.sleep(2 * retries)
                mode = "openai_json_schema"
            else:
                result = fallback_classification(row)
                mode = "rule_fallback_llm_disabled"
            out_rows.append(flatten_result(row, result, model, mode))
            append_jsonl(audit_file, {
                "context_id": context_id(row),
                "started_at": started_at,
                "ended_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "model": model,
                "mode": mode,
                "status": "ok",
                "retries": retries,
                "input": build_user_payload(row),
                "output": result,
                "usage": result.get("_usage", {}),
            })
        except Exception as exc:
            result = error_result(row, exc)
            out_rows.append(flatten_result(row, result, model, "openai_error" if enabled else "fallback_error"))
            append_jsonl(audit_file, {
                "context_id": context_id(row),
                "started_at": started_at,
                "ended_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "model": model,
                "mode": "openai_json_schema" if enabled else "rule_fallback_llm_disabled",
                "status": "error",
                "retries": retries,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "input": build_user_payload(row),
            })
            if "insufficient_quota" in str(exc):
                break

    write_csv(output_file, out_rows)
    print(f"Wrote {output_file} ({len(out_rows)} rows).")
    print(f"Audit trail: {audit_file}")


if __name__ == "__main__":
    main()
