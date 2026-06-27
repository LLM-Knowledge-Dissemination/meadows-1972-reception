#!/usr/bin/env python3
"""Write conservative human-review recommendations for boundary and context-window pilots."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/validation"
TABLES = ROOT / "analysis/tables"
SAMPLE = VALIDATION / "citation_context_validation_sample.csv"
BOUNDARY = VALIDATION / "boundary_case_adjudication_packet.csv"
WINDOWS = VALIDATION / "context_window_pilot_reextracted.csv"
SNAPSHOT = VALIDATION / "citation_context_validation_sample_pre_boundary_adjudication.csv"
LOG = VALIDATION / "manual_adjudication_log.csv"
V2_INPUT = VALIDATION / "v2_classifier_pilot_input_100.csv"
V2_READY = VALIDATION / "v2_classifier_pilot_input_100_ready.csv"

LOG_FIELDS = [
    "matched_row_identifier",
    "title",
    "year",
    "match_confidence",
    "matching_notes",
    "previous_human_is_seed_work_citation",
    "new_human_is_seed_work_citation",
    "previous_human_primary_role",
    "new_human_primary_role",
    "previous_human_discourse_category",
    "new_human_discourse_category",
    "previous_human_secondary_roles",
    "new_human_secondary_roles",
    "previous_human_stance_toward_seed",
    "new_human_stance_toward_seed",
    "previous_human_false_positive_flag",
    "new_human_false_positive_flag",
    "previous_human_confidence",
    "new_human_confidence",
    "previous_human_notes",
    "new_human_notes",
]


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


def append_csv(path: Path, rows):
    if not rows:
        return
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, extrasaction="ignore", lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def rec(role, stance="neutral_descriptive", confidence="high", notes="", safe="yes", reason=""):
    return {
        "recommended_human_primary_role": role,
        "recommended_human_stance_toward_seed": stance,
        "recommended_human_confidence": confidence,
        "recommended_human_notes": notes,
        "safe_to_apply": safe,
        "reason_not_safe_to_apply": reason,
    }


BOUNDARY_RECOMMENDATIONS = {
    "10_1007_s10584_013_0834_0|6|Limits to Growth": rec("historical_framing", notes="Identifies LtG as one of the first long-range global scenario exercises; modeling is described in adjacent text, but the citation sentence primarily marks historical precedence."),
    "10_1007_s10668_024_05077_4|4|Limits to Growth": rec("foundational_citation", confidence="medium", notes="Introduces a substantive claim attributed to the book; the claim is truncated but function is clearer than historical framing."),
    "10_1007_s12208_023_00364_8|1|Limits to Growth": rec("foundational_citation", confidence="medium", notes="Invokes the substantive proposition that limitless growth on a finite planet is impossible."),
    "10_1007_s10640_020_00422_3|2|Meadows et al. 1972": rec("historical_framing", notes="Places the Club of Rome report within a historical challenge to economics."),
    "10_1002_sdr_1645|9|(Meadows et al., 1972)": rec("historical_framing", notes="Places LtG in a publication sequence and lineage; the new window shows body-text chronology rather than a bibliography entry."),
    "10_1007_s10668_024_05077_4|4|(Meadows et al., 1972)": rec("foundational_citation", confidence="medium", notes="Attributes a substantive resource-limit argument to the book."),
    "10_1016_j_enpol_2018_05_053|5|Limits to Growth": rec("historical_framing", notes="Summarizes the LtG publication history in a background section."),
    "10_1016_j_ecolecon_2006_02_011|5|Limits to Growth": rec("historical_framing", notes="Uses LtG to mark a historical shift in the resource-substitution debate."),
    "10_1007_s13412_020_00636_3|4|(Meadows et al. 1972)": rec("unclear", stance="unclear", confidence="low", notes="OCR corruption prevents a reliable rhetorical-function judgment.", safe="no", reason="Severe OCR corruption and interleaved sentences."),
    "10_1007_s00146_021_01339_1|4|(Meadows 1972)": rec("historical_framing", confidence="medium", notes="States that limits to growth was not yet on the historical agenda.", safe="no", reason="OCR interleaving remains substantial."),
    "10_1007_s10584_013_0834_0|6|(Meadows et al., 1972)": rec("historical_framing", notes="Same historical scenario-lineage event as its grouped title variant."),
    "10_1007_s10640_020_00422_3|2|Limits to Growth": rec("historical_framing", notes="Same historical challenge-to-economics event as its grouped parenthetical variant."),
    "10_1007_s10668_010_9260_x|6|Limits to growth": rec("historical_framing", confidence="medium", notes="Lists LtG among intellectual antecedents in a historical lineage."),
    "10_1007_s11269_022_03373_0|12|Limits to Growth": rec("historical_framing", notes="Connects the publication of LtG to a subsequent historical change in ecological planning."),
    "10_1007_s11269_022_03373_0|5|(Meadows et al. 1972)": rec("historical_framing", notes="Chronologically locates the Club of Rome report alongside the 1972 UN conference."),
    "10_1007_s11269_022_03373_0|5|Limits to Growth": rec("historical_framing", notes="Same chronological event as the grouped parenthetical variant."),
    "10_1016_j_apgeog_2010_10_014|2|(Meadows et al. 1972)": rec("historical_framing", notes="Describes the historical focus of an earlier debate; no explicit negative assessment appears."),
    "10_1016_j_enpol_2018_05_053|5|Meadows et al. 1972": rec("historical_framing", notes="Same publication-history event as the grouped title variant."),
    "10_1016_j_iref_2024_103395|3|(Meadows et al., 1972)": rec("foundational_citation", confidence="medium", notes="Uses the substantive claim that exhaustible resources constrain economic growth.", safe="no", reason="Existing human stance is supportive, but the visible wording is attribution rather than explicit endorsement."),
    "10_1002_sd_281|2|(Meadows et al., 1972)": rec("historical_framing", notes="Uses Meadows to characterize environmental fears in the 1970s."),
    "10_1007_s43508_023_00063_4|1|(Meadows et al., 1972)": rec("historical_framing", notes="Uses the report as a historical alert and chronological marker."),
    "10_1016_j_ecolecon_2010_06_020|24|Limits to Growth": rec("unclear", stance="unclear", confidence="low", notes="The title mention is embedded in an incomplete discussion of technological optimism and divergence.", safe="no", reason="Generic title mention and insufficient context."),
    "10_1016_j_esd_2020_09_001|6|(Meadows et al., 1972)": rec("historical_framing", confidence="medium", notes="Places zero-growth discourse historically as a response to resource-limit awareness."),
    "10_1016_j_apgeog_2010_10_014|2|limits to growth": rec("historical_framing", confidence="medium", notes="Describes a historical debate; debate language alone is not critique."),
    "10_1002_sres_2421|32|Limits to Growth": rec("historical_framing", notes="Mentions the study as an earlier funded systems-research project."),
    "10_1007_s10612_022_09627_y|6|Limits to Growth": rec("historical_framing", notes="Describes Meadows' widely read work and intellectual influence."),
    "10_1007_s11159_022_09981_7|4|(Meadows et al. 1972)": rec("historical_framing", notes="Locates the report in the historical context of the Faure report."),
    "10_1007_s11213_024_09678_y|2|Limits to Growth": rec("historical_framing", notes="Marks LtG as an early point in the evolution of systems thinking for sustainability."),
    "10_1016_j_ecolecon_2021_107007|5|Limits to Growth": rec("foundational_citation", notes="Attributes the substantive environmental-limits-to-growth issue to the seed work."),
    "10_1016_j_enpol_2019_111090|7|Limits to Growth": rec("modeling_simulation_reference", stance="supportive", notes="Explicitly praises LtG's modeling success in estimating variable tendencies."),
    "10_1002_sdr_1645|9|Limits to Growth": rec("historical_framing", notes="Same publication-lineage event as the grouped parenthetical variant."),
    "10_1007_s10668_010_9260_x|6|(Meadows et al. 1972)": rec("historical_framing", confidence="medium", notes="Same intellectual-lineage list as its grouped title variant."),
    "10_1007_s11269_022_03373_0|12|(Meadows et al. 1972)": rec("policy_governance_framing", confidence="medium", notes="Links the report's publication to ecologists' interest in adaptive planning."),
    "10_1007_s12208_023_00364_8|1|(Meadows et al., 1972)": rec("foundational_citation", confidence="medium", notes="Invokes the substantive finite-planet growth-limit proposition."),
    "10_1016_j_ecolecon_2006_02_011|5|(Meadows et al. 1972)": rec("historical_framing", notes="Same historical resource-substitution debate event as its grouped title variant."),
    "10_1016_j_iref_2024_103395|3|Limits to Growth": rec("foundational_citation", confidence="medium", notes="Invokes the substantive resource-constraint claim."),
}


def window_rec(improves, assessment, changes, role, stance, confidence, notes):
    return {
        "new_window_improves_review": improves,
        "reviewability_assessment": assessment,
        "new_window_changes_label": changes,
        "new_window_recommended_role": role,
        "new_window_recommended_stance": stance,
        "new_window_confidence": confidence,
        "new_window_notes": notes,
    }


WINDOW_RECOMMENDATIONS = {
    "10_1007_s10584_013_0834_0|6|Limits to Growth": window_rec("yes", "improved", "no", "historical_framing", "neutral_descriptive", "high", "Adjacent text clarifies the modeling topic, but the exact citation sentence primarily marks historical precedence as one of the first scenario exercises."),
    "10_1016_j_jhydrol_2024_131248|3|Meadows et al., 1972": window_rec("yes", "improved", "no", "modeling_simulation_reference", "neutral_descriptive", "high", "Citation sentence explicitly discusses a quantitative simulation model and scenario testing."),
    "10_1007_s10668_024_05077_4|4|Limits to Growth": window_rec("yes", "improved", "no", "foundational_citation", "neutral_descriptive", "medium", "Preceding sentence clarifies sustainability framing, but the attributed claim remains truncated."),
    "10_1007_s12208_023_00364_8|1|Limits to Growth": window_rec("yes", "improved", "yes", "foundational_citation", "neutral_descriptive", "medium", "The citation sentence visibly attributes the finite-planet growth-limit proposition; contact-information OCR remains noisy."),
    "10_1007_s10640_020_00422_3|2|Meadows et al. 1972": window_rec("yes", "improved", "no", "historical_framing", "neutral_descriptive", "high", "Adjacent sentences establish a historical challenge to economics and its resource focus."),
    "10_1002_sdr_1645|9|(Meadows et al., 1972)": window_rec("yes", "improved", "no", "historical_framing", "neutral_descriptive", "high", "The window confirms chronological body-text discussion and resolves the bibliography-only uncertainty."),
    "10_1007_s11625_022_01157_4|1|Meadows et al. 1972": window_rec("yes", "improved", "no", "foundational_citation", "neutral_descriptive", "medium", "The broader context links Meadows to society-environment trajectory and ecological collapse, though OCR remains interleaved."),
    "10_1007_s10980_012_9777_5|6|Meadows 1972": window_rec("yes", "improved", "no", "foundational_citation", "neutral_descriptive", "medium", "Wider context identifies carrying capacity and modern ecological crisis; OCR still limits confidence."),
    "10_1007_s11625_021_00928_9|1|Meadows et al. 1972": window_rec("yes", "improved", "no", "foundational_citation", "neutral_descriptive", "medium", "The window clarifies that Meadows supports a substantive claim about growth-oriented value systems."),
    "10_1016_j_enpol_2018_05_053|5|Limits to Growth": window_rec("yes", "improved", "no", "historical_framing", "neutral_descriptive", "high", "Section and following sentence clarify publication history and the surrounding LtG background summary."),
    "10_1007_s11625_021_01080_0|2|Meadows et al. 1972": window_rec("yes", "improved", "no", "modeling_simulation_reference", "neutral_descriptive", "high", "The citation sentence explicitly identifies use of World3 and scenarios; OCR remains noisy but function is clear."),
    "10_1007_s10668_024_05077_4|4|(Meadows et al., 1972)": window_rec("yes", "improved", "yes", "foundational_citation", "neutral_descriptive", "medium", "The citation attributes a substantive claim rather than merely marking history; sentence remains truncated."),
    "10_1016_j_respol_2011_06_011|14|Limits to Growth": window_rec("yes", "improved", "yes", "critique", "critical", "high", "The following sentence explicitly objects to Meadows' predictions as flawed and unhelpful, establishing critique and critical stance."),
    "10_1016_j_ecolecon_2006_02_011|5|Limits to Growth": window_rec("yes", "improved", "no", "historical_framing", "neutral_descriptive", "high", "The adjacent discussion clearly positions LtG within a historical resource-substitution debate."),
    "10_1007_s13412_020_00636_3|4|(Meadows et al. 1972)": window_rec("no", "unchanged", "yes", "unclear", "unclear", "low", "Additional text remains severely interleaved; function and stance are still not reliable."),
    "10_1007_s13280_022_01800_5|15|(Meadows et al. 1972)": window_rec("yes", "improved", "yes", "foundational_citation", "neutral_descriptive", "medium", "The wider context shows a substantive risks-and-sustainability-paths premise, although OCR is interleaved."),
    "10_1007_s10551_023_05600_z|5|Meadows et al., 1972": window_rec("yes", "improved", "yes", "foundational_citation", "neutral_descriptive", "medium", "The citation supports a substantive claim that unsustainable growth may collapse society and environment; OCR remains noisy."),
    "10_1007_s00146_021_01339_1|4|(Meadows 1972)": window_rec("no", "unchanged", "no", "historical_framing", "neutral_descriptive", "low", "The historical-agenda signal remains visible, but additional OCR-interleaved text does not materially improve reviewability."),
    "10_1016_j_ecolecon_2019_106369|30|Limits to Growth": window_rec("yes", "improved", "no", "bibliographic_only", "unclear", "high", "Previous and following references confirm a bibliography entry."),
    "10_1007_s10798_023_09822_0|7|Meadows et al., 1972": window_rec("no", "unchanged", "yes", "unclear", "neutral_descriptive", "low", "The citation sentence remains truncated and only establishes prevalence in literature, not a clear rhetorical function."),
}


def review_boundary():
    rows = read_csv(BOUNDARY)
    reviewed = []
    for row in rows:
        recommendation = BOUNDARY_RECOMMENDATIONS[row["context_id"]]
        reviewed.append({**row, **recommendation})
    write_csv(TABLES / "boundary_case_review_recommendations.csv", reviewed)
    return reviewed


def apply_safe_boundary_labels(reviewed):
    if not SNAPSHOT.exists():
        shutil.copy2(SAMPLE, SNAPSHOT)

    sample = read_csv(SAMPLE)
    by_id = {row["context_id"]: row for row in sample}
    log_rows = []
    for recommendation in reviewed:
        if recommendation["safe_to_apply"] != "yes":
            continue
        row = by_id.get(recommendation["context_id"])
        if row is None or row.get("human_primary_role", "").strip():
            continue
        previous = dict(row)
        row["human_primary_role"] = recommendation["recommended_human_primary_role"]
        row["human_stance_toward_seed"] = recommendation["recommended_human_stance_toward_seed"]
        row["human_confidence"] = recommendation["recommended_human_confidence"]
        row["human_notes"] = recommendation["recommended_human_notes"]
        log_rows.append({
            "matched_row_identifier": row["context_id"],
            "title": row["title"],
            "year": row["year"],
            "match_confidence": "high",
            "matching_notes": "Boundary-case close review using the available snippet and re-extracted context window where present.",
            "previous_human_is_seed_work_citation": previous.get("human_is_seed_work_citation", ""),
            "new_human_is_seed_work_citation": row.get("human_is_seed_work_citation", ""),
            "previous_human_primary_role": previous.get("human_primary_role", ""),
            "new_human_primary_role": row["human_primary_role"],
            "previous_human_discourse_category": previous.get("human_discourse_category", ""),
            "new_human_discourse_category": row.get("human_discourse_category", ""),
            "previous_human_secondary_roles": previous.get("human_secondary_roles", ""),
            "new_human_secondary_roles": row.get("human_secondary_roles", ""),
            "previous_human_stance_toward_seed": previous.get("human_stance_toward_seed", ""),
            "new_human_stance_toward_seed": row["human_stance_toward_seed"],
            "previous_human_false_positive_flag": previous.get("human_false_positive_flag", ""),
            "new_human_false_positive_flag": row.get("human_false_positive_flag", ""),
            "previous_human_confidence": previous.get("human_confidence", ""),
            "new_human_confidence": row["human_confidence"],
            "previous_human_notes": previous.get("human_notes", ""),
            "new_human_notes": row["human_notes"],
        })

    write_csv(SAMPLE, sample)
    append_csv(LOG, log_rows)
    return len(log_rows)


def review_windows():
    rows = read_csv(WINDOWS)
    reviewed = []
    for row in rows:
        recommendation = WINDOW_RECOMMENDATIONS[row["context_id"]]
        citation_sentence = row.get("citation_sentence", "").strip()
        section_heading = row.get("section_heading", "").strip()
        issue_flags = row.get("extraction_issue_flags", "").lower()
        citation_sentence_complete = (
            "yes"
            if len(citation_sentence) >= 80 and citation_sentence[-1:] in ".?!"
            else "partial"
        )
        section_assessment = "not_available"
        if section_heading:
            section_assessment = "noisy" if section_heading.startswith(".") or len(section_heading) > 100 else "helpful"
        uncertainty_reduced = "yes" if recommendation["new_window_improves_review"] == "yes" else "no"
        if recommendation["new_window_improves_review"] == "yes" and ("ocr" in issue_flags or "trunc" in recommendation["new_window_notes"].lower()):
            uncertainty_reduced = "partial"
        reviewed.append({
            **row,
            **recommendation,
            "citation_sentence_complete": citation_sentence_complete,
            "adjacent_sentences_useful": "yes" if row.get("sentence_before", "").strip() or row.get("sentence_after", "").strip() else "no",
            "section_heading_assessment": section_assessment,
            "bibliography_detection_helpful": "yes" if recommendation["new_window_recommended_role"] == "bibliographic_only" else "not_material",
            "uncertainty_reduced": uncertainty_reduced,
        })
    write_csv(TABLES / "context_window_pilot_human_review_recommendations.csv", reviewed)
    return reviewed


def prepare_v2_ready(boundary_reviewed):
    """Keep one canonical mention per context group and aggregate traceability fields."""
    rows = read_csv(V2_INPUT)
    current_sample = {row["context_id"]: row for row in read_csv(SAMPLE)}
    human_fields = [
        "human_is_seed_work_citation",
        "human_primary_role",
        "human_discourse_category",
        "human_stance_toward_seed",
        "human_false_positive_flag",
        "human_confidence",
        "human_notes",
    ]
    for row in rows:
        current = current_sample.get(row["mention_level_id"], {})
        for field in human_fields:
            row[field] = current.get(field, row.get(field, ""))
        row["extraction_confidence"] = current.get("extraction_confidence", row.get("extraction_confidence", ""))
    boundary_ids = {row["context_id"] for row in boundary_reviewed}
    window_ids = {row["context_id"] for row in read_csv(WINDOWS)}
    groups = {}
    for row in rows:
        groups.setdefault(row["context_group_id"], []).append(row)

    ready = []
    for group_id, members in groups.items():
        def rank(row):
            return (
                bool(row.get("human_primary_role", "").strip()),
                bool(row.get("citation_sentence", "").strip()),
                row.get("review_priority") == "high",
                row.get("mention_level_id") in boundary_ids,
                len(row.get("context_window", "") or row.get("snippet_clean", "")),
            )

        canonical = dict(max(members, key=rank))
        human_roles = sorted({row["human_primary_role"] for row in members if row.get("human_primary_role", "").strip()})
        human_stances = sorted({row["human_stance_toward_seed"] for row in members if row.get("human_stance_toward_seed", "").strip()})
        human_member_ids = [row["mention_level_id"] for row in members if row.get("human_primary_role", "").strip()]
        canonical.update({
            "canonical_context_id": canonical["mention_level_id"],
            "group_member_count": len(members),
            "group_member_ids": " | ".join(row["mention_level_id"] for row in members),
            "group_has_human_coding": "yes" if human_roles or human_stances else "no",
            "group_human_coded_member_ids": " | ".join(human_member_ids),
            "group_human_primary_roles": " | ".join(human_roles),
            "group_human_stances": " | ".join(human_stances),
            "group_human_label_conflict": "yes" if len(human_roles) > 1 or len(human_stances) > 1 else "no",
            "group_has_boundary_case": "yes" if any(row["mention_level_id"] in boundary_ids for row in members) else "no",
            "group_has_context_window_pilot": "yes" if any(row["mention_level_id"] in window_ids for row in members) else "no",
        })
        ready.append(canonical)

    ready.sort(key=lambda row: (
        row["group_has_human_coding"] != "yes",
        row["group_has_boundary_case"] != "yes",
        row["group_has_context_window_pilot"] != "yes",
        row.get("review_priority") != "high",
        row["context_group_id"],
    ))
    write_csv(V2_READY, ready)
    return ready


def main():
    boundary = review_boundary()
    applied = apply_safe_boundary_labels(boundary)
    windows = review_windows()
    ready = prepare_v2_ready(boundary)
    print(f"Reviewed {len(boundary)} boundary rows; safely applied {applied} new labels; reviewed {len(windows)} context-window rows; prepared {len(ready)} canonical v2 groups.")


if __name__ == "__main__":
    main()
