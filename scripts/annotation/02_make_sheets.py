#!/usr/bin/env python3
"""Annotator-sheet generator (BLANK label fields only).

QUARANTINE INVARIANT (do not relax):
  - No LLM, no model, no inference is invoked here.
  - The label columns (function, stance, depth, flag, notes) are written
    EMPTY for every row.
  - No "suggested" or pre-filled label is written under any circumstance.
  - The gold set stays LLM-uncontaminated.

For each annotator (A and B):
  - Row order is shuffled with a per-annotator RNG seed derived from
    BASE_SEED (env ANNOT_SEED) and the annotator letter.
  - Rows show the annotator: item_id, seed, citing_year, work_type,
    explicit sentence_before, citing_sentence, sentence_after fields, the
    combined three-sentence context, and BLANK
    label fields.
  - Internal provenance (citing_openalex_id, doi, route, etc.) is kept
    out of the annotator sheets and lives in item_key.csv alongside.
  - A header note above the data points to docs/annotation/PILOT_CODEBOOK.md.

Outputs:
  analysis/annotation/sheets/annotator_A.csv
  analysis/annotation/sheets/annotator_B.csv
  analysis/annotation/item_key.csv     (internal provenance keyed by item_id)
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IN_PILOT = REPO / "analysis" / "annotation" / "pilot_sample.csv"
SHEETS_DIR = REPO / "analysis" / "annotation" / "sheets"
SHEETS_DIR.mkdir(parents=True, exist_ok=True)
KEY_OUT = REPO / "analysis" / "annotation" / "item_key.csv"

BASE_SEED = int(os.environ.get("ANNOT_SEED", "20260625"))
ANNOTATORS = ["A", "B"]
CODEBOOK_PATH = "docs/annotation/PILOT_CODEBOOK.md"

# BLANK label columns — the quarantine. Do not pre-fill any of these.
LABEL_COLUMNS = ["function", "stance", "depth", "flag", "notes"]

# Columns the annotator sees in their sheet. Provenance fields like
# citing_openalex_id, citing_doi, route, retrieval metadata, S2/OA matching
# details, etc. are INTENTIONALLY excluded from annotator sheets to avoid
# leaking model-side signal (e.g., S2 intents) into annotation.
ANNOTATOR_VISIBLE = [
    "item_id",
    "seed",                # seed_id, but renamed for legibility
    "citing_year",
    "work_type",           # citing_type, renamed for legibility
    "sentence_before",
    "citing_sentence",
    "sentence_after",
    "context",             # context_text, renamed for legibility
]


def annotator_seed(annotator: str) -> int:
    """Deterministic per-annotator RNG seed for shuffle."""
    return BASE_SEED ^ int(hashlib.sha256(annotator.encode()).hexdigest()[:8], 16)


def main() -> None:
    if not IN_PILOT.exists():
        raise SystemExit(f"missing input: {IN_PILOT} (run 01_sample.py first)")
    with IN_PILOT.open() as f:
        rows = list(csv.DictReader(f))
    print(f"loaded {len(rows)} items from {IN_PILOT.name}")

    # ----- 1) Internal item_key.csv (provenance, NOT given to annotators) ---
    key_fields = [
        "item_id", "seed_id", "band", "citing_openalex_id", "citing_doi",
        "citing_year", "citing_decade", "citing_type", "routes", "n_routes",
        "context_window_complete", "context_sentence_count",
        "context_window_status", "match_document_fraction",
        "context_quality_flags", "annotation_eligible",
        "s2_match_reason", "s2_intents", "s2_is_influential",
        "oa_match_kind", "oa_url", "oa_doc_sha256_16",
        "first_retrieved_at_utc",
    ]
    with KEY_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=key_fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in key_fields})
    print(f"wrote {KEY_OUT} (internal — provenance for {len(rows)} items)")

    # ----- 2) Annotator sheets (BLANK label columns) ------------------------
    for annot in ANNOTATORS:
        sheet_path = SHEETS_DIR / f"annotator_{annot}.csv"
        # Independent shuffle per annotator. Same items, different order.
        shuffled = rows[:]
        rng = random.Random(annotator_seed(annot))
        rng.shuffle(shuffled)
        with sheet_path.open("w", newline="") as f:
            # Header note: 4 commented-out lines + 1 blank row before CSV
            # header. Spreadsheet apps usually display these as data rows; we
            # write them as cells in column A so the codebook reference and
            # quarantine reminder are visible when opened.
            w = csv.writer(f, lineterminator="\n")
            w.writerow([f"# Pilot annotation sheet — annotator {annot}"])
            w.writerow([f"# Codebook: {CODEBOOK_PATH}  (read first)"])
            w.writerow([f"# Label columns are BLANK. Fill in: function, stance, depth, flag (optional), notes (recommended on hesitations)."])
            w.writerow([f"# DO NOT consult an LLM or any model output for labels. The pilot's gold-set quarantine depends on this."])
            w.writerow([])
            # Proper CSV header on the next row
            header = ANNOTATOR_VISIBLE + LABEL_COLUMNS
            w.writerow(header)
            for r in shuffled:
                annotator_row = {
                    "item_id": r["item_id"],
                    "seed": r["seed_id"],
                    "citing_year": r["citing_year"],
                    "work_type": r["citing_type"],
                    "sentence_before": r["sentence_before"],
                    "citing_sentence": r["citing_sentence"],
                    "sentence_after": r["sentence_after"],
                    "context": r["context_text"],
                }
                # The QUARANTINE: every label column blank.
                for c in LABEL_COLUMNS:
                    annotator_row[c] = ""
                w.writerow([annotator_row[h] for h in header])
        print(f"wrote {sheet_path} ({len(shuffled)} rows; "
              f"shuffle_seed_for_{annot}={annotator_seed(annot)})")

    # ----- 3) Quarantine verification ---------------------------------------
    # Re-read each sheet and assert every label cell is empty.
    for annot in ANNOTATORS:
        sheet_path = SHEETS_DIR / f"annotator_{annot}.csv"
        with sheet_path.open() as f:
            reader = csv.reader(f)
            in_data = False
            label_idx_start = None
            n_data = 0
            n_label_nonblank = 0
            for row in reader:
                if not in_data:
                    if row and row[0] == "item_id":
                        in_data = True
                        label_idx_start = row.index("function")
                    continue
                if not row:
                    continue
                n_data += 1
                for c in row[label_idx_start:]:
                    if c.strip():
                        n_label_nonblank += 1
        if n_label_nonblank > 0:
            raise SystemExit(f"QUARANTINE VIOLATION: annotator_{annot}.csv has "
                              f"{n_label_nonblank} non-blank label cells across {n_data} rows.")
        print(f"  quarantine OK: annotator_{annot}.csv has 0 non-blank label cells across {n_data} data rows")


if __name__ == "__main__":
    main()
