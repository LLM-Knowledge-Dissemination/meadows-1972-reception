#!/usr/bin/env python3
"""Apply initial human adjudications and audit the citation-context sample."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "analysis/validation/citation_context_validation_sample.csv"
PRE_ADJUDICATION = ROOT / "analysis/validation/citation_context_validation_sample_pre_adjudication.csv"
LOG = ROOT / "analysis/validation/manual_adjudication_log.csv"
TABLES = ROOT / "analysis/tables"
TARGETED_LOG = ROOT / "analysis/validation/targeted_calibration_adjudication_log.csv"

HUMAN_FIELDS = [
    "human_is_seed_work_citation",
    "human_primary_role",
    "human_discourse_category",
    "human_secondary_roles",
    "human_stance_toward_seed",
    "human_false_positive_flag",
    "human_confidence",
    "human_notes",
]


def adjudication(context_id, role, stance, confidence, notes, match_notes):
    return {
        "context_id": context_id,
        "human_primary_role": role,
        "human_stance_toward_seed": stance,
        "human_confidence": confidence,
        "human_notes": notes,
        "match_confidence": "high",
        "match_notes": match_notes,
    }


ADJUDICATIONS = [
    adjudication(
        "10_1002_sd_218|3|Meadows et al, 1972",
        "modeling_simulation_reference",
        "neutral_descriptive",
        "high",
        "Describes Meadows' whole-system modeling approach and growth-limits argument. Citation is descriptive rather than endorsing the conclusions.",
        "Matched the substantive whole-system modeling context; a separate bibliography-like row for this paper was not treated as this adjudication.",
    ),
    adjudication(
        "10_1007_s10551_022_05198_8|4|Limits to Growth",
        "modeling_simulation_reference",
        "neutral_descriptive",
        "medium",
        "Refers to Limits to Growth as a seminal publication and example of system modeling. Historical importance does not necessarily imply support.",
        "Matched the system-model/seminal-publication context.",
    ),
    adjudication(
        "10_1007_s10551_022_05198_8|5|(Meadows et al, 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Citation used to describe adoption of Limits to Growth within environmentalism. Historical diffusion rather than endorsement.",
        "Matched the environmentalism-adoption context.",
    ),
    adjudication(
        "10_1007_s10668_016_9842_3|4|(Meadows et al. 1972)",
        "sustainability_discourse",
        "supportive",
        "medium",
        "Author invokes Meadows' conclusions regarding demographic intervention and sustainability as support for a substantive argument.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s10806_021_09865_0|14|limits to growth",
        "sustainability_discourse",
        "supportive",
        "high",
        "Explicitly adopts the claim that there are limits to growth and argues for living within planetary boundaries. Clear endorsement.",
        "Matched the mention-string row already selected for human review; a repeated parenthetical mention row remains separately reviewable.",
    ),
    adjudication(
        "10_1016_j_enpol_2018_05_053|4|(Meadows et al. 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Describes Limits to Growth as a founding text of the environmental movement. Historical significance rather than support.",
        "Matched the founding-text context.",
    ),
    adjudication(
        "10_1016_j_enpol_2018_05_053|16|(Meadows et al. 1972)",
        "modeling_simulation_reference",
        "neutral_descriptive",
        "high",
        "References a model assumption from Limits to Growth. Citation is explanatory rather than evaluative.",
        "Matched the labor/model-assumption context.",
    ),
    adjudication(
        "10_1016_j_enpol_2019_111090|7|Limits to Growth",
        "modeling_simulation_reference",
        "supportive",
        "high",
        "Explicitly references the remarkable success of Limits to Growth in capturing long-term system behavior. Positive evaluation and endorsement.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1002_sdr_1645|9|(Meadows et al., 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Citation places the work within a lineage of growth and system dynamics studies. Historical positioning rather than substantive engagement.",
        "Matched the citation-bearing repeated context; the title-mention duplicate remains separately reviewable.",
    ),
    adjudication(
        "10_1002_sres_2421|32|Limits to Growth",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Discussion concerns funding history and institutional context surrounding the study rather than substantive claims.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s00146_021_01339_1|4|(Meadows 1972)",
        "unclear",
        "unclear",
        "low",
        "Context fragment too short to determine rhetorical function reliably. LLM uncertainty flag appropriate.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s10584_013_0834_0|6|Limits to Growth",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Citation situates Limits to Growth as an early environmental modeling effort. Historical description rather than endorsement.",
        "Matched first occurrence/title mention.",
    ),
    adjudication(
        "10_1007_s10584_013_0834_0|6|(Meadows et al., 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Same reasoning as previous row; duplicate citation context.",
        "Matched duplicate citation mention for the same context.",
    ),
    adjudication(
        "10_1007_s10612_022_09627_y|6|Limits to Growth",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Citation functions as a cultural and historical reference to Meadows' influence rather than substantive use of its arguments.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s10640_020_00422_3|2|Limits to Growth",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Discusses historical intellectual influence on economics rather than applying Meadows' framework.",
        "Matched first occurrence/title mention on page 2.",
    ),
    adjudication(
        "10_1007_s10640_020_00422_3|2|Meadows et al. 1972",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Historical benchmark reference. Influence rather than substantive support.",
        "Matched duplicate citation mention on page 2; excluded the bibliography-like page 10 context.",
    ),
    adjudication(
        "10_1007_s10668_010_9260_x|6|Limits to growth",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Appears in a list of intellectual roots of sustainability. Historical lineage citation.",
        "Matched the fuller intellectual-roots list context; repeated mentions remain separately reviewable.",
    ),
    adjudication(
        "10_1007_s10668_021_01716_2|16|Limits to Growth",
        "historical_framing",
        "neutral_descriptive",
        "medium",
        "'Seminal' denotes influence and importance, not endorsement. Historical benchmark citation.",
        "Matched first occurrence/title mention.",
    ),
    adjudication(
        "10_1007_s10668_021_01716_2|16|(Meadows et al., 1972)",
        "historical_framing",
        "neutral_descriptive",
        "medium",
        "Historical benchmark reference. Influence rather than substantive support.",
        "Matched duplicate citation mention for the same context.",
    ),
    adjudication(
        "10_1007_s10668_024_05077_4|4|Limits to Growth",
        "foundational_citation",
        "neutral_descriptive",
        "medium",
        "Author invokes a substantive argument from the book rather than merely referencing its historical importance.",
        "Matched the fuller title-mention context; repeated parenthetical mention remains separately reviewable.",
    ),
    adjudication(
        "10_1007_s10712_024_09844_w|10|(Meadows et al. 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Discussion concerns public awareness and historical influence of the report.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s10816_023_09617_6|3|Limits to Growth",
        "modeling_simulation_reference",
        "neutral_descriptive",
        "high",
        "Explicit model comparison. Citation functions as a simulation reference rather than historical framing.",
        "Unique title/year/context match.",
    ),
    adjudication(
        "10_1007_s11159_022_09981_7|4|(Meadows et al. 1972)",
        "historical_framing",
        "neutral_descriptive",
        "high",
        "Uses Meadows to situate historical concerns and debates rather than support a substantive claim.",
        "Unique title/year/context match.",
    ),
]


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_flags(value):
    return [part.strip() for part in (value or "").split("|") if part.strip() and part.strip() != "none"]


def normalized_fallback_role(value):
    return {
        "sustainability_limits_to_growth_discourse": "sustainability_discourse",
        "methodological_comparison": "methods_comparison",
        "background_or_ambiguous": "unclear",
    }.get(value, value)


def has_terms(text, terms):
    text = (text or "").lower()
    return any(term in text for term in terms)


def audit_flags(row, repeated_keys, duplicate_ids):
    flags = []
    context_id = row.get("context_id", "")
    repeated_key = "|".join(context_id.split("|")[:2])
    snippet = row.get("snippet_clean", "")
    evidence = f"{row.get('llm_evidence_quote', '')} {snippet}".lower()
    role = row.get("llm_primary_role", "")
    stance = row.get("llm_stance_toward_meadows", "")
    uncertainty = split_flags(row.get("llm_uncertainty_flags", ""))
    confidence = float(row.get("llm_confidence") or 0)
    extraction = float(row.get("extraction_confidence") or 0)
    fallback = normalized_fallback_role(row.get("rule_citation_function", ""))

    if context_id in duplicate_ids:
        flags.append("duplicate_context_id")
    if repeated_key in repeated_keys:
        flags.append("repeated_context_different_mentions")
    if not snippet.strip():
        flags.append("missing_context_window")
    for field in ("title", "year", "venue"):
        if not row.get(field, "").strip():
            flags.append(f"missing_{field}")
    if extraction < 0.75:
        flags.append("low_extraction_confidence")
    flags.extend(uncertainty)
    if row.get("false_positive_risk", "").startswith("high_"):
        flags.append("generic_limits_false_positive_risk")
    if (
        re.search(r"\blimits? to growth\b", snippet, re.I)
        and not has_terms(snippet, ["meadows", "club of rome", "world3", "1972", "limits to growth report", "limits to growth ("])
    ):
        flags.append("generic_limits_false_positive_risk")

    if "bibliography_only" in uncertainty and role not in ("bibliographic_only", "unclear"):
        flags.append("substantive_role_with_bibliography_only_uncertainty")
    if confidence >= 0.8 and uncertainty:
        flags.append("high_llm_confidence_with_uncertainty")
    if fallback and role and fallback != role:
        flags.append("fallback_llm_primary_role_disagreement")

    positive_terms = ["support", "success", "remarkable", "confirm", "valid", "need to", "necessary to", "must", "recognize these limits", "adopt"]
    negative_terms = ["critic", "fail", "wrong", "reject", "flaw", "overestimat", "underestimat", "pessimis", "inaccurate", "dispute"]
    policy_terms = ["policy", "govern", "regulat", "planning", "institution", "decision-making", "management", "strategy"]
    model_terms = ["model", "simulation", "scenario", "world3", "system dynamics", "forecast", "assumption", "projection", "feedback"]

    if stance == "supportive" and not has_terms(evidence, positive_terms):
        flags.append("supportive_stance_without_explicit_endorsement")
    if role == "critique" and not has_terms(evidence, negative_terms):
        flags.append("critique_without_explicit_negative_assessment")
    if role == "policy_governance_framing" and not has_terms(evidence, policy_terms):
        flags.append("policy_label_without_policy_content")
    if role == "modeling_simulation_reference" and not has_terms(evidence, model_terms):
        flags.append("modeling_label_without_model_content")
    if {role, fallback} == {"historical_framing", "foundational_citation"}:
        flags.append("historical_foundational_ambiguity")
    if {role, fallback} == {"historical_framing", "modeling_simulation_reference"}:
        flags.append("historical_modeling_ambiguity")

    return list(dict.fromkeys(flags))


def priority_for(flags, row):
    high = {
        "duplicate_context_id",
        "generic_limits_false_positive_risk",
        "bibliography_only",
        "snippet_too_short",
        "missing_surrounding_context",
        "fallback_llm_primary_role_disagreement",
        "supportive_stance_without_explicit_endorsement",
        "critique_without_explicit_negative_assessment",
        "policy_label_without_policy_content",
        "modeling_label_without_model_content",
        "substantive_role_with_bibliography_only_uncertainty",
    }
    if (
        row.get("llm_stance_toward_meadows") == "supportive"
        or row.get("llm_primary_role") == "critique"
        or split_flags(row.get("llm_uncertainty_flags", ""))
        or float(row.get("llm_confidence") or 0) < 0.75
        or float(row.get("extraction_confidence") or 0) < 0.75
    ):
        return "high"
    if any(flag in high for flag in flags):
        return "high"
    if flags or float(row.get("llm_confidence") or 0) < 0.75 or float(row.get("extraction_confidence") or 0) < 0.75:
        return "medium"
    return "low"


def agreement_rows(rows, prediction_field, comparison):
    dimensions = [
        ("primary_role", "human_primary_role", prediction_field),
        ("stance", "human_stance_toward_seed", "llm_stance_toward_meadows" if comparison == "llm_vs_human" else None),
    ]
    output = []
    for dimension, human_field, predicted_field in dimensions:
        if predicted_field is None:
            continue
        pairs = [
            (row.get(human_field, "").strip(), row.get(predicted_field, "").strip())
            for row in rows
            if row.get(human_field, "").strip() and row.get(predicted_field, "").strip()
        ]
        total = len(pairs)
        agreement_n = sum(human == predicted for human, predicted in pairs)
        for (human, predicted), n in sorted(Counter(pairs).items()):
            output.append(
                {
                    "comparison": comparison,
                    "dimension": dimension,
                    "human_label": human,
                    "predicted_label": predicted,
                    "n": n,
                    "is_agreement": human == predicted,
                    "agreement_n": agreement_n,
                    "total_n": total,
                    "agreement_rate": round(agreement_n / total, 4) if total else "",
                    "note": "Partial human-coded sample only; not final validation metrics.",
                }
            )
    return output


def main():
    rows = read_csv(SAMPLE)
    by_id = {row["context_id"]: row for row in rows}
    pre_rows = read_csv(PRE_ADJUDICATION) if PRE_ADJUDICATION.exists() else rows
    pre_by_id = {row["context_id"]: row for row in pre_rows}
    log_rows = []

    for item in ADJUDICATIONS:
        if item["context_id"] not in by_id:
            raise RuntimeError(f"Could not match adjudication: {item['context_id']}")
        row = by_id[item["context_id"]]
        previous_row = pre_by_id.get(item["context_id"], row)
        previous = {field: previous_row.get(field, "") for field in HUMAN_FIELDS}
        for field in ("human_primary_role", "human_stance_toward_seed", "human_confidence", "human_notes"):
            row[field] = item[field]
        log_row = {
            "matched_row_identifier": row["context_id"],
            "title": row["title"],
            "year": row["year"],
            "match_confidence": item["match_confidence"],
            "matching_notes": item["match_notes"],
        }
        for field in HUMAN_FIELDS:
            log_row[f"previous_{field}"] = previous[field]
            log_row[f"new_{field}"] = row.get(field, "")
        log_rows.append(log_row)

    id_counts = Counter(row["context_id"] for row in rows)
    duplicate_ids = {key for key, count in id_counts.items() if count > 1}
    repeated_groups = defaultdict(list)
    for row in rows:
        repeated_groups["|".join(row["context_id"].split("|")[:2])].append(row)
    repeated_keys = {
        key
        for key, group in repeated_groups.items()
        if len(group) > 1 and len({row["context_id"].split("|")[-1] for row in group}) > 1
    }

    for row in rows:
        flags = audit_flags(row, repeated_keys, duplicate_ids)
        row["review_priority"] = priority_for(flags, row)
        row["review_reason"] = " | ".join(flags) if flags else "no_automated_issue_detected"

    sample_fields = list(rows[0])
    for field in ("review_priority", "review_reason"):
        if field not in sample_fields:
            sample_fields.append(field)
    write_csv(SAMPLE, rows, sample_fields)
    write_csv(LOG, log_rows)

    human_rows = [row for row in rows if row.get("human_primary_role", "").strip()]
    remaining = [row for row in rows if not row.get("human_primary_role", "").strip()]
    flagged = [row for row in rows if row["review_reason"] != "no_automated_issue_detected"]
    targeted_count = len(read_csv(TARGETED_LOG)) if TARGETED_LOG.exists() else 0
    remaining_sorted = sorted(remaining, key=lambda row: ({"high": 0, "medium": 1, "low": 2}[row["review_priority"]], row["title"], row["context_id"]))

    progress = [
        {"metric": "validation_rows_total", "value": len(rows), "note": ""},
        {"metric": "manual_adjudications_matched", "value": len(log_rows), "note": "All supplied adjudications matched with high confidence."},
        {"metric": "targeted_calibration_adjudications_matched", "value": targeted_count, "note": "Second targeted calibration set."},
        {"metric": "total_logged_adjudications", "value": len(log_rows) + targeted_count, "note": "Initial plus targeted calibration adjudications."},
        {"metric": "human_coded_rows_current", "value": len(human_rows), "note": "Includes one pre-existing human-coded row outside the supplied adjudication set."},
        {"metric": "human_coded_rows_remaining", "value": len(remaining), "note": ""},
        {"metric": "remaining_high_priority", "value": sum(row["review_priority"] == "high" for row in remaining), "note": ""},
        {"metric": "remaining_medium_priority", "value": sum(row["review_priority"] == "medium" for row in remaining), "note": ""},
        {"metric": "remaining_low_priority", "value": sum(row["review_priority"] == "low" for row in remaining), "note": ""},
        {"metric": "duplicate_context_id_rows", "value": sum("duplicate_context_id" in row["review_reason"] for row in rows), "note": "Exact context_id duplicates."},
        {"metric": "repeated_context_different_mentions_rows", "value": sum("repeated_context_different_mentions" in row["review_reason"] for row in rows), "note": ""},
        {"metric": "context_window_column_present", "value": int("context_window" in rows[0]), "note": "snippet_clean was audited as the available context field."},
        {"metric": "missing_snippet_clean_rows", "value": sum(not row.get("snippet_clean", "").strip() for row in rows), "note": ""},
        {"metric": "missing_title_rows", "value": sum(not row.get("title", "").strip() for row in rows), "note": ""},
        {"metric": "missing_year_rows", "value": sum(not row.get("year", "").strip() for row in rows), "note": ""},
        {"metric": "missing_venue_rows", "value": sum(not row.get("venue", "").strip() for row in rows), "note": ""},
        {"metric": "low_extraction_confidence_rows", "value": sum(float(row.get("extraction_confidence") or 0) < 0.75 for row in rows), "note": "Threshold: extraction_confidence < 0.75."},
        {"metric": "snippet_too_short_rows", "value": sum("snippet_too_short" in split_flags(row.get("llm_uncertainty_flags", "")) for row in rows), "note": ""},
        {"metric": "bibliography_only_uncertainty_rows", "value": sum("bibliography_only" in split_flags(row.get("llm_uncertainty_flags", "")) for row in rows), "note": ""},
        {"metric": "missing_surrounding_context_rows", "value": sum("missing_surrounding_context" in split_flags(row.get("llm_uncertainty_flags", "")) for row in rows), "note": ""},
        {"metric": "generic_limits_false_positive_risk_rows", "value": sum("generic_limits_false_positive_risk" in row["review_reason"] for row in rows), "note": ""},
        {"metric": "fallback_llm_primary_role_disagreement_rows", "value": sum("fallback_llm_primary_role_disagreement" in row["review_reason"] for row in rows), "note": ""},
        {"metric": "high_llm_confidence_with_uncertainty_rows", "value": sum("high_llm_confidence_with_uncertainty" in row["review_reason"] for row in rows), "note": ""},
        {"metric": "supportive_without_explicit_endorsement_rows", "value": sum("supportive_stance_without_explicit_endorsement" in row["review_reason"] for row in rows), "note": "Heuristic lexical screen; requires human confirmation."},
        {"metric": "critique_without_explicit_negative_assessment_rows", "value": sum("critique_without_explicit_negative_assessment" in row["review_reason"] for row in rows), "note": "Heuristic lexical screen; requires human confirmation."},
    ]
    write_csv(TABLES / "validation_adjudication_progress.csv", progress)

    review_fields = [
        "context_id", "title", "year", "venue", "review_priority", "review_reason",
        "extraction_confidence", "llm_primary_role", "llm_stance_toward_meadows",
        "llm_confidence", "llm_uncertainty_flags", "rule_citation_function", "snippet_clean",
    ]
    write_csv(TABLES / "validation_remaining_review_priorities.csv", remaining_sorted, review_fields)
    write_csv(TABLES / "validation_inconsistency_flags.csv", flagged, review_fields)

    llm_agreement = agreement_rows(human_rows, "llm_primary_role", "llm_vs_human")
    fallback_rows = []
    for row in human_rows:
        copy = dict(row)
        copy["fallback_primary_role"] = normalized_fallback_role(row.get("rule_citation_function", ""))
        fallback_rows.append(copy)
    fallback_agreement = agreement_rows(fallback_rows, "fallback_primary_role", "fallback_vs_human")
    write_csv(TABLES / "validation_llm_human_agreement_partial.csv", llm_agreement)
    write_csv(TABLES / "validation_fallback_human_agreement_partial.csv", fallback_agreement)

    disagreements = [
        row for row in rows
        if normalized_fallback_role(row.get("rule_citation_function", "")) != row.get("llm_primary_role", "")
    ]
    for row in disagreements:
        row["fallback_primary_role_normalized"] = normalized_fallback_role(row.get("rule_citation_function", ""))
    disagreement_fields = review_fields[:5] + ["fallback_primary_role_normalized", "llm_primary_role", "llm_stance_toward_meadows", "llm_confidence", "llm_uncertainty_flags", "review_reason", "snippet_clean"]
    write_csv(TABLES / "validation_llm_fallback_disagreement_review.csv", disagreements, disagreement_fields)

    print(f"Applied {len(log_rows)} adjudications; {len(human_rows)} rows now human-coded; {len(remaining)} remain.")


if __name__ == "__main__":
    main()
