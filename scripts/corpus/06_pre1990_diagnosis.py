#!/usr/bin/env python3
"""Step 4 — pre-1990 diagnosis. Data-driven per-seed comparison of RAW
citing-works vs. EXTRACTED-context counts for 1970s, 1980s, 1990s.

Computes per (seed, decade) for pre-1990 strata:
  - raw_works:           citing works in the OpenAlex census for that decade
  - sampled_works:       citing works actually attempted in extraction
  - extracted_works:     citing works that yielded >=1 context
  - extraction_rate:     extracted / sampled (Wilson 95% CI)
  - projected_extracted: extraction_rate * raw_works (estimate, with CI band)

Then classifies each (seed, decade) as:
  - COVERAGE_ARTIFACT  — raw works substantial (>=20), extraction rate <5%
                          → emits pre1990_recovery_worklist.csv rows
                          (the citing works whose contexts were not
                          extractable via S2 or OA full-text fallback)
  - REAL_TROUGH        — raw works themselves thin (<20) → records as a
                          candidate finding, not a gap
  - MIXED              — raw works substantial, extraction rate moderate
                          (5–25%) → likely BOTH artifact + trough

NOTE: the framing call (limitation vs finding; whether to fund manual
recovery) is the AUTHOR'S — this script presents numbers and surfaces
the worklist; it does not decide.

Outputs:
  analysis/corpus_production/pre1990_diagnosis.csv
  analysis/corpus_production/pre1990_recovery_worklist.csv
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import CORPUS_DIR, now_iso

CENSUS_CSV = CORPUS_DIR / "citing_census.csv"
S2_ATT = CORPUS_DIR / "contexts_s2_attempted.csv"
OA_ATT = CORPUS_DIR / "contexts_oa_attempted.csv"
S2_CTX = CORPUS_DIR / "contexts_s2.csv"
OA_CTX = CORPUS_DIR / "contexts_oa.csv"
OUT_DIAG = CORPUS_DIR / "pre1990_diagnosis.csv"
OUT_WORKLIST = CORPUS_DIR / "pre1990_recovery_worklist.csv"

DECADES_PRE1990 = ["1970s", "1980s"]
DECADES_FOR_DIAGNOSIS = ["1970s", "1980s", "1990s"]


def load_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open() as f:
        return list(csv.DictReader(f))


def wilson_ci(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    z = 1.959963984540054
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def classify(raw_n: int, sampled_n: int, extracted_n: int) -> str:
    if raw_n < 20:
        return "REAL_TROUGH"
    if sampled_n == 0:
        return "NOT_SAMPLED"
    rate = extracted_n / sampled_n
    if rate < 0.05:
        return "COVERAGE_ARTIFACT"
    if rate >= 0.25:
        return "EXTRACTION_OK_NOT_AN_ISSUE"
    return "MIXED_ARTIFACT_AND_TROUGH"


def main() -> None:
    census = load_csv(CENSUS_CSV)
    s2_att = load_csv(S2_ATT)
    oa_att = load_csv(OA_ATT)
    s2_ctx = load_csv(S2_CTX)
    oa_ctx = load_csv(OA_CTX)

    # raw works per (seed, decade)
    raw_by_sd: dict[tuple, int] = defaultdict(int)
    for r in census:
        raw_by_sd[(r["seed_id"], r["citing_decade"])] += 1

    # sampled (attempted) per (seed, decade): union of S2 attempts AND OA
    # attempts (where OA actually fetched the document, not failed)
    sampled_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in s2_att:
        sampled_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])
    for r in oa_att:
        if r.get("fetch_status") == "fetched":
            sampled_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])

    # extracted per (seed, decade): citing works yielding >=1 context
    yielded_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in s2_ctx:
        yielded_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])
    for r in oa_ctx:
        yielded_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])

    seeds = sorted({k[0] for k in raw_by_sd})

    # Diagnosis table
    diag_rows = []
    for s in seeds:
        for d in DECADES_FOR_DIAGNOSIS:
            raw_n = raw_by_sd.get((s, d), 0)
            sampled = sampled_pairs_by_sd.get((s, d), set())
            sampled_n = len(sampled)
            yielded = yielded_pairs_by_sd.get((s, d), set())
            extracted_n = len(yielded)
            p, lo, hi = wilson_ci(extracted_n, sampled_n)
            projected = p * raw_n
            proj_lo = lo * raw_n
            proj_hi = hi * raw_n
            verdict = classify(raw_n, sampled_n, extracted_n)
            diag_rows.append({
                "seed_id": s,
                "decade": d,
                "raw_works": raw_n,
                "sampled_works": sampled_n,
                "extracted_works": extracted_n,
                "extraction_rate": f"{p:.4f}",
                "extraction_rate_wilson95_lo": f"{lo:.4f}",
                "extraction_rate_wilson95_hi": f"{hi:.4f}",
                "projected_extracted_works": f"{projected:.1f}",
                "projected_extracted_wilson95_lo": f"{proj_lo:.1f}",
                "projected_extracted_wilson95_hi": f"{proj_hi:.1f}",
                "diagnosis": verdict,
                "author_framing_flag": (
                    "ARTIFACT — emit manual-recovery worklist; raw works exist but extraction failed"
                    if verdict == "COVERAGE_ARTIFACT" else
                    "TROUGH — record as candidate finding; raw citing pool itself thin"
                    if verdict == "REAL_TROUGH" else
                    "MIXED — likely both artifact and trough; author to decide split"
                    if verdict == "MIXED_ARTIFACT_AND_TROUGH" else
                    "NOT_SAMPLED — extraction pass did not cover this stratum"
                    if verdict == "NOT_SAMPLED" else
                    "EXTRACTION_OK — no recovery needed"
                ),
            })

    with OUT_DIAG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(diag_rows[0].keys()))
        w.writeheader()
        for r in diag_rows:
            w.writerow(r)
    print(f"[{now_iso()}] wrote {OUT_DIAG} ({len(diag_rows)} rows)")

    # Recovery worklist: pre-1990 citing works (1970s + 1980s) that were not
    # successfully extracted via either route. Emit the metadata needed for
    # later manual/library recovery (DOI, OA URL, title, year, type, seed).
    pre1990_attempted_pairs = set()
    for s in seeds:
        for d in DECADES_PRE1990:
            pre1990_attempted_pairs |= sampled_pairs_by_sd.get((s, d), set()).union(
                # Also include works NOT in the sample (so the worklist covers
                # everything pre-1990 in the raw census, not just the sample).
                set()
            )
    pre1990_extracted_pairs = set()
    for s in seeds:
        for d in DECADES_PRE1990:
            pre1990_extracted_pairs |= yielded_pairs_by_sd.get((s, d), set())

    worklist_rows = []
    for r in census:
        if r["citing_decade"] not in DECADES_PRE1990:
            continue
        if r["citing_openalex_id"] in pre1990_extracted_pairs:
            continue  # already extracted; not on the recovery list
        worklist_rows.append({
            "seed_id": r["seed_id"],
            "decade": r["citing_decade"],
            "citing_openalex_id": r["citing_openalex_id"],
            "citing_doi": r["citing_doi"],
            "citing_year": r["citing_year"],
            "citing_type": r["citing_type"],
            "citing_language": r.get("citing_language", ""),
            "citing_is_oa": r.get("citing_is_oa", ""),
            "citing_oa_url": r.get("citing_oa_url", ""),
            "citing_primary_field": r.get("citing_primary_field", ""),
            "citing_primary_source": r.get("citing_primary_source", ""),
            "citing_title": r.get("citing_title", ""),
            "extraction_attempted": (
                "yes" if r["citing_openalex_id"] in pre1990_attempted_pairs else "no"
            ),
            "recovery_recommendation": (
                "had OA URL but extraction yielded 0 — likely PDF parsing limitation; "
                "library physical/digital lookup recommended"
                if (r.get("citing_oa_url") or "").strip() and
                   r["citing_openalex_id"] in pre1990_attempted_pairs else
                "no OA URL and not attempted — library physical/digital lookup required"
                if not (r.get("citing_oa_url") or "").strip() else
                "OA URL present, not sampled in this run — extend automated extraction first"
            ),
        })

    with OUT_WORKLIST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(worklist_rows[0].keys())
                            if worklist_rows
                            else ["seed_id","decade","citing_openalex_id","citing_doi",
                                  "citing_year","citing_type","citing_language",
                                  "citing_is_oa","citing_oa_url","citing_primary_field",
                                  "citing_primary_source","citing_title",
                                  "extraction_attempted","recovery_recommendation"])
        w.writeheader()
        for r in worklist_rows:
            w.writerow(r)
    print(f"wrote {OUT_WORKLIST} ({len(worklist_rows)} pre-1990 recovery candidates)")
    print(f"\nfinished_at={now_iso()}")


if __name__ == "__main__":
    main()
