#!/usr/bin/env python3
"""Lightweight deterministic checks for v2 output acceptance rules."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.python.llm_context_classifier import (
    CONTROLLED_ABSTENTION,
    build_v2_user_payload,
    read_csv,
    validate_v2_input_file,
    validate_v2_result,
    v2_run_paths,
    v2_withheld_fields,
)
from scripts.python.v2_preclassification_router import route_context


schema = json.loads((ROOT / "schemas/citation_context_classification_v2.schema.json").read_text(encoding="utf-8"))
row = read_csv(ROOT / "analysis/validation/v2_classifier_pilot_input_100_ready.csv")[0]
base = {
    "context_id": row["canonical_context_id"],
    "context_group_id": row["context_group_id"],
    "citation_function": "unclear",
    "topic_or_discourse_area": "unclear",
    "stance_toward_seed": "unclear",
    "evidence_quote_function": CONTROLLED_ABSTENTION,
    "evidence_quote_topic": CONTROLLED_ABSTENTION,
    "evidence_quote_stance": CONTROLLED_ABSTENTION,
    "confidence_function": 0.4,
    "confidence_topic": 0.4,
    "confidence_stance": 0.4,
    "uncertainty_flags": ["missing_surrounding_context"],
    "needs_human_review": True,
    "reasoning_summary": "Evidence is insufficient; human review is required.",
}


def assert_invalid(mutator, expected_error):
    result = copy.deepcopy(base)
    mutator(result)
    validation = validate_v2_result(result, row, schema)
    assert not validation["deterministically_valid"]
    assert expected_error in validation["validation_errors"]


assert validate_v2_result(base, row, schema)["deterministically_valid"]
assert_invalid(lambda x: x.update(context_id=""), "identifier_mismatch")
assert_invalid(lambda x: x.update(evidence_quote_function="historical_framing"), "category_token_as_evidence")
assert_invalid(lambda x: x.update(citation_function="historical_framing"), "unsupported_label_without_evidence")
assert_invalid(lambda x: x.update(uncertainty_flags=["none", "snippet_too_short"]), "invalid_uncertainty_flags")
assert_invalid(
    lambda x: x.update(stance_toward_seed="supportive", evidence_quote_stance=CONTROLLED_ABSTENTION),
    "stance_evidence_failure",
)

next_rows = validate_v2_input_file(ROOT / "analysis/validation/v2_regression_set_next_ready.csv")
next_payload = json.loads(build_v2_user_payload(next_rows[0]))
withheld = set(v2_withheld_fields(next_rows[0].keys()))
assert len(next_rows) == 16
assert set(next_payload).isdisjoint(withheld)
assert next_payload["comparison_labels_withheld_from_model"] is True
paths = v2_run_paths(ROOT, "v2_regression2")
assert paths["output_file"].as_posix().endswith("analysis/data/llm_output/v2/v2_regression2_classifications.csv")
assert paths["diagnostic_file"].as_posix().endswith("analysis/logs/v2_regression2_diagnostic.csv")


def router_row(text, **extra):
    row = {
        "context_group_id": "test_group",
        "canonical_context_id": "test_context",
        "mention_level_id": "test_context",
        "citation_sentence": text,
        "sentence_before": "Before sentence.",
        "sentence_after": "After sentence.",
        "context_window": text,
        "snippet_clean": text,
        "bibliography_detected": "false",
        "bibliography_score": "0",
        "extraction_confidence": "0.9",
        "citation_section": "",
    }
    row.update(extra)
    return row


assert route_context(router_row("In 1992, the United Nations' Earth Summit conception of the past (Meadows et al. 1972).")).routed_citation_function == "unclear"
assert route_context(router_row("Meadows D, Meadows D, Randers J and Behrens W (1972) The Limits to Growth.", bibliography_detected="true")).routed_citation_function == "bibliographic_only"
assert route_context(router_row("This result resembles the classic Limits to Growth simulations (Meadows et al., 1972).")).routed_citation_function == "modeling_simulation_reference"
assert route_context(router_row("Since The Limits to Growth, exhaustible resources constrain economic growth (Meadows et al., 1972).")).routed_citation_function == "foundational_citation"
assert route_context(router_row("The LTG research is documented in three publications (Meadows et al. 1972; Meadows et al. 1992).")).routed_citation_function == "historical_framing"
policy_route = route_context(router_row("More than 50 years since the Club of Rome released its report on Limits to Growth (Meadows 1972), policy debates continue."))
assert policy_route.send_to_llm and policy_route.routed_citation_function == "policy_governance_framing"

print("V2 deterministic validation checks passed.")
