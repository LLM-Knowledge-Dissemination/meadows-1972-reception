#!/usr/bin/env python3
"""Apply the seven approved targeted-calibration human labels."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "analysis/validation/citation_context_validation_sample.csv"
LOG = ROOT / "analysis/validation/targeted_calibration_adjudication_log.csv"
MANUAL_LOG = ROOT / "analysis/validation/manual_adjudication_log.csv"

LABELS = {
    "10_1007_s13412_020_00636_3|4|(Meadows et al. 1972)": ("unclear", "unclear", "low", "Severe OCR corruption prevents reliably distinguishing historical framing from substantive conceptual use."),
    "10_1002_sd_281|2|(Meadows et al., 1972)": ("historical_framing", "neutral_descriptive", "high", "Places resource-scarcity fears in the 1970s; it does not invoke Meadows as a current intellectual anchor."),
    "10_1016_j_ecolecon_2010_06_020|24|Limits to Growth": ("unclear", "neutral_descriptive", "low", "Incomplete generic title mention without a clear Meadows citation or enough surrounding context."),
    "10_1016_j_enpol_2018_05_053|5|Limits to Growth": ("historical_framing", "neutral_descriptive", "medium", "Lists the 1972 report within the publication history of LTG. No model use appears in this specific citation context."),
    "10_1007_s10668_024_05077_4|4|(Meadows et al., 1972)": ("foundational_citation", "neutral_descriptive", "medium", "Invokes a substantive claim attributed to the book as background for the argument."),
    "10_1016_j_ecolecon_2006_02_011|5|Limits to Growth": ("historical_framing", "neutral_descriptive", "medium", "Uses the report as a historical event after which an intellectual position hardened."),
    "10_1016_j_iref_2024_103395|3|(Meadows et al., 1972)": ("foundational_citation", "supportive", "high", "Uses and adopts the substantive Meadows claim that exhaustible resources constrain economic growth."),
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = read_csv(SAMPLE)
    by_id = {row["context_id"]: row for row in rows}
    missing = sorted(set(LABELS) - set(by_id))
    if missing:
        raise RuntimeError(f"Could not match targeted calibration rows: {missing}")

    existing_log = read_csv(LOG) if LOG.exists() else []
    original_by_id = {row["matched_row_identifier"]: row for row in existing_log}
    log_rows = []

    for context_id, (role, stance, confidence, notes) in LABELS.items():
        row = by_id[context_id]
        original = original_by_id.get(context_id)
        previous_role = original["previous_human_primary_role"] if original else row.get("human_primary_role", "")
        previous_stance = original["previous_human_stance_toward_seed"] if original else row.get("human_stance_toward_seed", "")
        previous_confidence = original["previous_human_confidence"] if original else row.get("human_confidence", "")

        row["human_primary_role"] = role
        row["human_stance_toward_seed"] = stance
        row["human_confidence"] = confidence
        row["human_notes"] = notes

        log_rows.append(
            {
                "matched_row_identifier": context_id,
                "title": row["title"],
                "year": row["year"],
                "previous_human_primary_role": previous_role,
                "previous_human_stance_toward_seed": previous_stance,
                "previous_human_confidence": previous_confidence,
                "new_human_primary_role": role,
                "new_human_stance_toward_seed": stance,
                "new_human_confidence": confidence,
                "new_human_notes": notes,
                "match_confidence": "high",
                "matching_notes": "Exact context_id from the approved seven-row targeted calibration set.",
            }
        )

    write_csv(SAMPLE, rows, list(rows[0]))
    write_csv(LOG, log_rows, list(log_rows[0]))
    manual_rows = read_csv(MANUAL_LOG) if MANUAL_LOG.exists() else []
    manual_by_id = {row["matched_row_identifier"]: row for row in manual_rows}
    for log_row in log_rows:
        manual_by_id[log_row["matched_row_identifier"]] = log_row
    merged = list(manual_by_id.values())
    merged_fields = list(dict.fromkeys(key for row in merged for key in row))
    write_csv(MANUAL_LOG, merged, merged_fields)
    print(f"Applied {len(LABELS)} targeted calibration labels.")


if __name__ == "__main__":
    main()
