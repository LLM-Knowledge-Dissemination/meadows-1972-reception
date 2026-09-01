#!/usr/bin/env python3
"""Stratified annotation sampler.

QUARANTINE INVARIANT: this script does NOT call an LLM, does NOT generate any
labels, and does NOT write any label fields. It only reads the deduplicated
contexts produced by the production build and selects a stratified sample.
The downstream annotator sheets (02_make_sheets.py) carry blank label fields
only — the gold set stays LLM-uncontaminated.

Parameters (env vars; defaults shown):
  ANNOT_N_TOTAL=100             total target sample size
  ANNOT_PER_SEED=33             approximate per-seed budget (the actual count
                                will sum to ~ANNOT_PER_SEED * 3, with thin
                                cells taken near-completely)
  ANNOT_BANDS="pre2000,2000s,2010onward"   temporal bands
  ANNOT_SEED=20260625           RNG seed (records reproducibly in provenance)
  ANNOT_INPUT=analysis/corpus_production/contexts_combined.csv
  ANNOT_OVERSAMPLE_NON_ARTICLE=1   if 1, fill each (seed,band) cell with
                                    non-article items first, then articles
  ANNOT_REQUIRE_COMPLETE_WINDOW=1  if 1, exclude contexts without a verified
                                    before/citing/after sentence window
  ANNOT_GLOBAL_FILL=1             if 1, fill seed-cell shortfalls from the
                                    remaining eligible pool up to N_TOTAL

Outputs:
  analysis/annotation/pilot_sample.csv      — sampled items + full provenance
  analysis/annotation/sampling_manifest.csv — realized per-stratum counts with
                                              under-fill flags
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUT = Path(os.environ.get("ANNOT_INPUT", REPO / "analysis" / "corpus_production" / "contexts_combined.csv"))
OUT_DIR = REPO / "analysis" / "annotation"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_SAMPLE = OUT_DIR / "pilot_sample.csv"
OUT_MANIFEST = OUT_DIR / "sampling_manifest.csv"

N_TOTAL = int(os.environ.get("ANNOT_N_TOTAL", "100"))
PER_SEED = int(os.environ.get("ANNOT_PER_SEED", "33"))
RNG_SEED = int(os.environ.get("ANNOT_SEED", "20260625"))
OVERSAMPLE_NA = os.environ.get("ANNOT_OVERSAMPLE_NON_ARTICLE", "1") == "1"
REQUIRE_COMPLETE_WINDOW = os.environ.get("ANNOT_REQUIRE_COMPLETE_WINDOW", "1") == "1"
GLOBAL_FILL = os.environ.get("ANNOT_GLOBAL_FILL", "1") == "1"

BANDS = ["pre2000", "2000s", "2010onward"]
SEEDS = [
    "meadows_1972_limits_to_growth",
    "commoner_1971_closing_circle",
    "schumacher_1974_small_is_beautiful",
]


def band_of(decade: str) -> str:
    if decade in {"1970s", "1980s", "1990s"}:
        return "pre2000"
    if decade == "2000s":
        return "2000s"
    if decade in {"2010s", "2020s"}:
        return "2010onward"
    return "unknown"


def is_article(type_str: str) -> bool:
    return type_str == "article"


def sha256_short(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def is_true(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"missing input: {INPUT}")
    raw = INPUT.read_bytes()
    input_hash = sha256_short(raw)
    rows = list(csv.DictReader(raw.decode().splitlines()))
    if REQUIRE_COMPLETE_WINDOW:
        rows = [
            row for row in rows
            if is_true(row.get("annotation_eligible"))
            and is_true(row.get("context_window_complete"))
        ]
    if not rows:
        raise SystemExit("no annotation-eligible complete context windows in input")
    # Pool index: (seed, band) -> list of rows
    pool: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        b = band_of(r["citing_decade"])
        if b == "unknown":
            continue
        pool[(r["seed_id"], b)].append(r)

    # Per-(seed, band) target allocation:
    # - If pool size <= ceil(PER_SEED / N_BANDS) + small_floor (treat as
    #   POOL_EXHAUSTED): take all.
    # - Else: aim for roughly equal across bands, but redistribute any
    #   shortfall to the band(s) with the largest pool within the same seed.
    rng = random.Random(RNG_SEED)
    target_per_band = max(1, PER_SEED // len(BANDS))  # ~11

    realized: dict[tuple, list[dict]] = defaultdict(list)
    manifest_rows = []
    for seed in SEEDS:
        seed_total_taken = 0
        # First pass: decide per-band target; mark POOL_EXHAUSTED if pool size
        # is at or below the per-band target.
        per_band_target = {}
        for b in BANDS:
            n = len(pool[(seed, b)])
            if n <= target_per_band:
                per_band_target[b] = n
            else:
                per_band_target[b] = target_per_band
        # Redistribute shortfall: difference between PER_SEED and sum of
        # exhausted bands' takes goes to non-exhausted bands.
        sum_taken = sum(per_band_target.values())
        shortfall = max(0, PER_SEED - sum_taken)
        non_exhausted = [b for b in BANDS if per_band_target[b] == target_per_band]
        while shortfall > 0 and non_exhausted:
            for b in non_exhausted:
                if shortfall <= 0:
                    break
                if per_band_target[b] < len(pool[(seed, b)]):
                    per_band_target[b] += 1
                    shortfall -= 1
            # if all non-exhausted are full, stop
            if all(per_band_target[b] >= len(pool[(seed, b)]) for b in non_exhausted):
                break

        # Second pass: draw the sample per cell with non-article oversampling.
        for b in BANDS:
            cell = pool[(seed, b)]
            tgt = per_band_target[b]
            non_articles = [r for r in cell if not is_article(r["citing_type"])]
            articles = [r for r in cell if is_article(r["citing_type"])]
            rng.shuffle(non_articles)
            rng.shuffle(articles)
            chosen: list[dict] = []
            if OVERSAMPLE_NA:
                # take min(tgt, all non-articles) first
                take_na = min(len(non_articles), tgt)
                chosen.extend(non_articles[:take_na])
                # fill remainder from articles
                remainder = tgt - len(chosen)
                chosen.extend(articles[:remainder])
                # if still short (cell smaller than tgt), take remaining non-articles
                if len(chosen) < tgt:
                    chosen.extend(non_articles[take_na:tgt - len(chosen) + take_na])
            else:
                # combined uniform draw
                combined = non_articles + articles
                rng.shuffle(combined)
                chosen = combined[:tgt]
            realized[(seed, b)] = chosen
            seed_total_taken += len(chosen)
            pool_size = len(cell)
            flag = ("POOL_EXHAUSTED" if pool_size <= target_per_band
                    else "OK")
            if len(chosen) < tgt:
                flag = "UNDERFILLED_CELL_SMALLER_THAN_TARGET"
            manifest_rows.append({
                "seed_id": seed,
                "band": b,
                "pool_size": pool_size,
                "pool_non_article": len(non_articles),
                "pool_article": len(articles),
                "target": tgt,
                "realized_n": len(chosen),
                "realized_non_article": sum(1 for r in chosen if not is_article(r["citing_type"])),
                "realized_article": sum(1 for r in chosen if is_article(r["citing_type"])),
                "flag": flag,
            })
        # Manifest seed total
        manifest_rows.append({
            "seed_id": seed,
            "band": "TOTAL",
            "pool_size": sum(len(pool[(seed, b)]) for b in BANDS),
            "pool_non_article": sum(sum(1 for r in pool[(seed, b)] if not is_article(r["citing_type"]))
                                      for b in BANDS),
            "pool_article": sum(sum(1 for r in pool[(seed, b)] if is_article(r["citing_type"]))
                                  for b in BANDS),
            "target": PER_SEED,
            "realized_n": seed_total_taken,
            "realized_non_article": sum(
                sum(1 for r in realized[(seed, b)] if not is_article(r["citing_type"]))
                for b in BANDS),
            "realized_article": sum(
                sum(1 for r in realized[(seed, b)] if is_article(r["citing_type"]))
                for b in BANDS),
            "flag": "OK",
        })

    # If thin seed/band cells prevent the per-seed design from reaching the
    # pilot target, use remaining eligible contexts rather than weak contexts.
    # The pilot is a codebook/reliability exercise, not an inferential sample;
    # the manifest records the resulting imbalance explicitly.
    current_n = sum(len(items) for items in realized.values())
    if GLOBAL_FILL and current_n < N_TOTAL:
        chosen_ids = {
            (r["seed_id"], r["citing_openalex_id"], r.get("citing_sentence_normalized", ""))
            for items in realized.values() for r in items
        }
        remaining = [
            r for r in rows
            if (r["seed_id"], r["citing_openalex_id"], r.get("citing_sentence_normalized", ""))
            not in chosen_ids
        ]
        rng.shuffle(remaining)
        for r in remaining[:N_TOTAL - current_n]:
            realized[(r["seed_id"], band_of(r["citing_decade"]))].append(r)

        # Refresh manifest realized counts after global fill.
        for manifest in manifest_rows:
            seed = manifest["seed_id"]
            if manifest["band"] == "TOTAL":
                selected = [r for b in BANDS for r in realized[(seed, b)]]
            else:
                selected = realized[(seed, manifest["band"])]
            prior_n = manifest["realized_n"]
            manifest["realized_n"] = len(selected)
            manifest["realized_non_article"] = sum(
                1 for r in selected if not is_article(r["citing_type"])
            )
            manifest["realized_article"] = sum(
                1 for r in selected if is_article(r["citing_type"])
            )
            if len(selected) > prior_n:
                manifest["flag"] = "GLOBAL_FILL_TO_N_TOTAL"
            elif len(selected) < manifest["target"] and len(selected) == manifest["pool_size"]:
                manifest["flag"] = "POOL_EXHAUSTED"

    # Flatten + assign stable item ids
    flat: list[dict] = []
    counter = 0
    for seed in SEEDS:
        for b in BANDS:
            for r in realized[(seed, b)]:
                counter += 1
                # Stable item_id derived from (input_hash, seed, citing_id,
                # normalized_text) + sequential ordinal; reproducible across
                # re-runs with the same seed because the iteration order is
                # deterministic by (seeds, bands, per-cell shuffle seeded by
                # the rng).
                stem = f"{r['seed_id']}|{r['citing_openalex_id']}|{r.get('citing_sentence_normalized','')[:80]}"
                stable_hash = hashlib.sha256(stem.encode()).hexdigest()[:8]
                item_id = f"PILOT_{counter:03d}_{stable_hash}"
                flat.append({
                    "item_id": item_id,
                    "seed_id": r["seed_id"],
                    "band": b,
                    "citing_openalex_id": r["citing_openalex_id"],
                    "citing_doi": r.get("citing_doi", ""),
                    "citing_year": r.get("citing_year", ""),
                    "citing_decade": r.get("citing_decade", ""),
                    "citing_type": r.get("citing_type", ""),
                    "routes": r.get("routes", ""),
                    "n_routes": r.get("n_routes", ""),
                    "sentence_before": r.get("sentence_before", ""),
                    "citing_sentence": r.get("citing_sentence", ""),
                    "sentence_after": r.get("sentence_after", ""),
                    "context_text": r.get("context_text", ""),
                    "context_text_normalized": r.get("context_text_normalized", ""),
                    "citing_sentence_normalized": r.get("citing_sentence_normalized", ""),
                    "context_window_complete": r.get("context_window_complete", ""),
                    "context_sentence_count": r.get("context_sentence_count", ""),
                    "context_window_status": r.get("context_window_status", ""),
                    "match_document_fraction": r.get("match_document_fraction", ""),
                    "context_quality_flags": r.get("context_quality_flags", ""),
                    "annotation_eligible": r.get("annotation_eligible", ""),
                    "s2_match_reason": r.get("s2_match_reason", ""),
                    "s2_intents": r.get("s2_intents", ""),
                    "s2_is_influential": r.get("s2_is_influential", ""),
                    "oa_match_kind": r.get("oa_match_kind", ""),
                    "oa_url": r.get("oa_url", ""),
                    "oa_doc_sha256_16": r.get("oa_doc_sha256_16", ""),
                    "first_retrieved_at_utc": r.get("first_retrieved_at_utc", ""),
                })

    # Write pilot sample (internal — includes all provenance)
    fieldnames = list(flat[0].keys())
    with OUT_SAMPLE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in flat:
            w.writerow(r)
    print(f"wrote {OUT_SAMPLE}: {len(flat)} items")

    # Write manifest
    with OUT_MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()), lineterminator="\n")
        w.writeheader()
        for r in manifest_rows:
            w.writerow(r)
    print(f"wrote {OUT_MANIFEST}: {len(manifest_rows)} rows")

    # Headline
    print("\nrealized per (seed, band):")
    for seed in SEEDS:
        for b in BANDS:
            n = len(realized[(seed, b)])
            na = sum(1 for r in realized[(seed, b)] if not is_article(r["citing_type"]))
            print(f"  {seed[:30]:30s} {b:11s} n={n:3d} (non_article={na})")
    print(f"\nTOTAL items: {len(flat)}")
    print(f"input_hash:  {input_hash}")
    print(f"rng_seed:    {RNG_SEED}")


if __name__ == "__main__":
    main()
