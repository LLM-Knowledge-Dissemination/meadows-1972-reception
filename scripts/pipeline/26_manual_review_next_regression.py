#!/usr/bin/env python3
"""Record manual review of the next v2 regression set and prepare a clean set."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"
NEXT = VALIDATION / "v2_regression_set_next.csv"
READY_SOURCE = VALIDATION / "v2_classifier_pilot_input_100_ready.csv"
PRIOR_OUTPUT = ROOT / "analysis/data/llm_output/v2/regression/citation_context_classifications_v2_regression.csv"


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


def rec(function, topic, stance="neutral_descriptive", confidence="high", review="no", notes="", keep="yes", why=""):
    return {
        "recommended_citation_function": function,
        "recommended_topic_or_discourse_area": topic,
        "recommended_stance_toward_seed": stance,
        "recommended_confidence": confidence,
        "recommended_needs_human_review": review,
        "recommended_notes": notes,
        "remain_in_next_regression": keep,
        "regression_inclusion_reason": why,
    }


REVIEWS = {
    "cg_0a6e8ce31095": rec("historical_framing", "system_dynamics_modeling", notes="The exact citation marks LtG as one of the first scenario exercises; adjacent model detail is topic/context.", why="Lower-risk historical/modeling control."),
    "cg_4a408f91a84c": rec("historical_framing", "historical_or_cultural_memory", notes="Body-text publication history, not reference-list bibliography and not model use in this event.", why="Retest rejected publication-history versus bibliography case."),
    "cg_5aed4f2c9ec1": rec("historical_framing", "economics_growth", notes="Marks the Club of Rome as a historical challenge to economics.", why="Lower-risk historical control."),
    "cg_6b6f82f07853": rec("unclear", "sustainability", "unclear", "low", "yes", "Severely interleaved OCR prevents a reliable citation-function or stance judgment.", why="Explicit abstention test for unreadable OCR."),
    "cg_75aecf0e86a4": rec("foundational_citation", "sustainability", confidence="medium", review="yes", notes="Attributes a substantive resource-limit claim, but the sentence is truncated.", why="Foundational/topic-separation control."),
    "cg_a402fc7c51f5": rec("foundational_citation", "limits_to_growth", confidence="medium", review="yes", notes="The event supplies the finite-planet growth-limit premise; no explicit policy/governance action appears.", why="Retest policy overreach and historical/foundational boundary."),
    "cg_80bb452dfb06": rec("modeling_simulation_reference", "system_dynamics_modeling", "supportive", "high", "yes", "Explicitly praises LtG's success in estimating variable tendencies; short legacy context still warrants review.", why="Retest short-but-sufficient modeling and supportive evidence."),
    "cg_9d95b2a45099": rec("foundational_citation", "economics_growth", "neutral_descriptive", "medium", "yes", "Attributes the premise that exhaustible resources constrain growth; visible wording does not explicitly endorse Meadows.", why="Retest short-but-sufficient foundational claim and stance conservatism."),
    "cg_01a5dd40f8b5": rec("historical_framing", "historical_or_cultural_memory", confidence="medium", review="yes", notes="Visible adoption/persistence language signals diffusion and historical influence, though OCR is fragmented.", why="Historical/foundational boundary with OCR."),
    "cg_1e4a61ca47f3": rec("historical_framing", "historical_or_cultural_memory", confidence="medium", review="yes", notes="Sales and founding-text language mark public influence and historical significance, not endorsement.", why="Retest rejected exact-evidence case and historical/foundational boundary."),
    "cg_6d850575d614": rec("modeling_simulation_reference", "system_dynamics_modeling", notes="Explicitly says the result resembles classic LtG simulations and describes their behavior.", why="Clear historical/modeling boundary test."),
    "cg_6edacb2f2d69": rec("modeling_simulation_reference", "system_dynamics_modeling", confidence="medium", review="yes", notes="The citation event discusses whole-Earth modeling; environmental planning is surrounding purpose, not function.", why="Policy-versus-modeling ambiguity test."),
    "cg_52c027f59473": rec("unclear", "environmental_policy", "unclear", "low", "yes", "The fragment mentions policy-making but does not reveal Meadows-specific rhetorical function.", keep="no", why="Exclude until human-coded or better context is extracted."),
    "cg_ea2b39202dd6": rec("historical_framing", "historical_or_cultural_memory", confidence="medium", review="yes", notes="The citation marks the report's release more than 50 years ago; policy is surrounding context only.", why="Policy-overreach versus historical-framing test."),
    "cg_f7beffb2fca3": rec("bibliographic_only", "unclear", "unclear", notes="Clear reference-list entry despite BODY structural flag.", review="yes", why="Known bibliography-only candidate and structural-flag repair test."),
    "cg_f22c3a98aa21": rec("historical_framing", "historical_or_cultural_memory", notes="Places LtG in a publication and intellectual lineage; it is body text, not bibliography-only.", why="Body-text lineage versus bibliography control."),
}


FAILURE_MODES = [
    ("historical framing mistaken for foundational use", "Historical influence, adoption, founding-text, or publication-lineage language is coded as substantive premise.", "cg_1e4a61ca47f3", "Inflates substantive uptake and supportive interpretations.", "Use historical framing for influence, adoption, sales, milestones, and lineage unless a Meadows claim is used as premise.", "prompt/codebook examples", "sometimes", "no"),
    ("foundational claim mistaken for historical framing", "A visible attributed Meadows claim used as premise is treated as chronology or background.", "cg_a402fc7c51f5", "Hides substantive conceptual use of the seed work.", "Use foundational citation when the event supplies a claim such as finite-resource constraints or growth limits.", "prompt decision order", "sometimes", "no"),
    ("modeling comparison mistaken for historical framing", "Simulation resemblance, model behavior, assumptions, or projections are reduced to historical importance.", "cg_6d850575d614", "Undercounts methodological/model diffusion.", "Any explicit resemblance/comparison to LtG simulation behavior or model assumptions is modeling_simulation_reference.", "prompt examples", "sometimes", "no"),
    ("policy/governance inferred from general urgency", "Policy is inferred from SDGs, urgency, document topic, or nearby planning language rather than the citation event.", "cg_a402fc7c51f5", "Overstates policy uptake.", "Require explicit policy, governance, planning, regulation, management, or institutional-decision work by the citation event.", "prompt hard requirement", "sometimes", "no"),
    ("bibliography-only confused with publication-history body text", "A body-text list of LtG editions/publications is coded as bibliography-only.", "cg_4a408f91a84c", "Removes interpretable historical diffusion evidence.", "Use bibliographic_only only for actual reference-list syntax/page context; body-text publication chronology is historical framing.", "prompt plus bibliography detector", "yes", "partly"),
    ("OCR corruption forced into substantive category", "Chronology or topic words inside syntactically incoherent OCR trigger a confident function.", "cg_6b6f82f07853", "Creates false interpretive precision.", "Severe incoherence forces unclear plus human review.", "prompt and extraction-quality gate", "yes", "yes"),
    ("short but sufficient context over-abstained", "The model uses unclear despite a visible attributed claim, model comparison, or explicit evaluative cue.", "cg_80bb452dfb06", "Loses valid substantive and modeling evidence.", "Judge whether the visible fragment itself contains sufficient exact evidence before abstaining for missing neighbors.", "prompt examples", "yes", "no"),
    ("generic title mention treated as seed-work citation", "A generic phrase or title mention is assumed to be Meadows 1972 without identifying evidence.", "cg_52c027f59473", "Introduces false-positive seed citations.", "Require author/year, Club of Rome, World3, or clear bibliographic identification; otherwise unclear.", "prompt seed-identification rule", "yes", "partly"),
    ("stance inferred without explicit evaluation", "Historical importance, topic agreement, or premise attribution is treated as support/critique.", "cg_1e4a61ca47f3", "Distorts discourse/stance trends.", "Supportive, critical, or mixed requires an exact evaluative quote; otherwise neutral_descriptive or unclear.", "prompt and deterministic stance validation", "sometimes", "yes"),
]


def context_text(row):
    parts = [row.get("sentence_before", ""), row.get("citation_sentence", ""), row.get("sentence_after", "")]
    return " ".join(x.strip() for x in parts if x.strip()) or row.get("snippet_clean", "")


def main():
    rows = read_csv(NEXT)
    prior = {row["context_group_id"]: row for row in read_csv(PRIOR_OUTPUT)}
    reviewed = []
    for row in rows:
        prior_row = prior.get(row["context_group_id"], {})
        reviewed.append({
            "context_group_id": row["context_group_id"],
            "representative_context_id": row.get("canonical_context_id") or row.get("mention_level_id"),
            "title": row["title"],
            "year": row["year"],
            "venue": row["venue"],
            "context_text": context_text(row),
            "known_human_function": row.get("human_primary_role", ""),
            "known_human_topic": row.get("human_discourse_category", ""),
            "known_human_stance": row.get("human_stance_toward_seed", ""),
            "v1_function": row.get("v1_llm_primary_role", ""),
            "v1_topic": row.get("v1_llm_topic", ""),
            "v1_stance": row.get("v1_llm_stance", ""),
            "prior_v2_function": prior_row.get("citation_function", ""),
            "prior_v2_topic": prior_row.get("topic_or_discourse_area", ""),
            "prior_v2_stance": prior_row.get("stance_toward_seed", ""),
            "prior_v2_status": prior_row.get("classification_status", ""),
            "issue_category": row["next_regression_selection_reason"],
            **REVIEWS[row["context_group_id"]],
        })
    write_csv(TABLES / "v2_regression_set_next_manual_review.csv", reviewed)

    failure_rows = [{
        "failure_mode": mode,
        "definition": definition,
        "example_context_group_id": example,
        "why_error_matters": matters,
        "proposed_decision_rule": rule,
        "prompt_schema_change_needed": prompt,
        "extraction_improvement_needed": extraction,
        "deterministic_validation_can_catch": deterministic,
    } for mode, definition, example, matters, rule, prompt, extraction, deterministic in FAILURE_MODES]
    write_csv(TABLES / "v2_decision_rule_failure_modes.csv", failure_rows)

    source = {row["context_group_id"]: row for row in read_csv(READY_SOURCE)}
    ready_ids = [row["context_group_id"] for row in reviewed if row["remain_in_next_regression"] == "yes"]
    # Add a second modeling case that explicitly discusses the Limits to Growth system model.
    ready_ids.append("cg_70117e9e7672")
    ready = []
    recommendations = {row["context_group_id"]: row for row in reviewed}
    for group_id in ready_ids:
        row = dict(source[group_id])
        if group_id in recommendations:
            recommendation = recommendations[group_id]
            row.update({
                "manual_recommended_citation_function": recommendation["recommended_citation_function"],
                "manual_recommended_topic_or_discourse_area": recommendation["recommended_topic_or_discourse_area"],
                "manual_recommended_stance_toward_seed": recommendation["recommended_stance_toward_seed"],
                "manual_recommended_confidence": recommendation["recommended_confidence"],
                "manual_recommended_needs_human_review": recommendation["recommended_needs_human_review"],
                "manual_regression_test_reason": recommendation["regression_inclusion_reason"],
            })
        else:
            row.update({
                "manual_recommended_citation_function": "modeling_simulation_reference",
                "manual_recommended_topic_or_discourse_area": "system_dynamics_modeling",
                "manual_recommended_stance_toward_seed": "neutral_descriptive",
                "manual_recommended_confidence": "medium",
                "manual_recommended_needs_human_review": "yes",
                "manual_regression_test_reason": "Second historical/modeling boundary and lower-context modeling control.",
            })
        ready.append(row)
    write_csv(VALIDATION / "v2_regression_set_next_ready.csv", ready)
    print(f"Reviewed {len(reviewed)} rows; prepared {len(ready)} ready rows; no API calls made.")


if __name__ == "__main__":
    main()
