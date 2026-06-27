#!/usr/bin/env python3
"""Corpus characterization (analysis-only on existing build outputs).

NOT in scope: new extraction, annotation, codebook, labeling. Pure analysis
of the census + sampled-yield data already on disk.

Produces:
  analysis/corpus_production/sampling_manifest.csv
  analysis/corpus_production/yield_projection_stratified.csv
  analysis/corpus_production/coverage_bias_profile.csv
  analysis/corpus_production/pre1990_projection_ci.csv

(The companion memo CORPUS_CHARACTERIZATION.md is written separately by the
author of this analysis pass.)
"""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import CORPUS_DIR, now_iso

CENSUS = CORPUS_DIR / "citing_census.csv"
S2_ATT = CORPUS_DIR / "contexts_s2_attempted.csv"
OA_ATT = CORPUS_DIR / "contexts_oa_attempted.csv"
S2_CTX = CORPUS_DIR / "contexts_s2.csv"
OA_CTX = CORPUS_DIR / "contexts_oa.csv"
COMBINED = CORPUS_DIR / "contexts_combined.csv"

OUT_SAMPLING = CORPUS_DIR / "sampling_manifest.csv"
OUT_YIELD = CORPUS_DIR / "yield_projection_stratified.csv"
OUT_COVBIAS = CORPUS_DIR / "coverage_bias_profile.csv"
OUT_PRE1990 = CORPUS_DIR / "pre1990_projection_ci.csv"

# Nominal targets from the build (matches scripts/corpus/03_*.py and 04_*.py
# defaults; the build report records the same).
NOMINAL_S2_PER_STRATUM = 120
NOMINAL_S2_DECADES = {"2010s", "2020s"}
NOMINAL_OA_PER_STRATUM = 20
NOMINAL_OA_DECADES = {"1970s", "1980s", "1990s", "2000s", "2010s", "2020s"}
SEEDS_ACTIVE = [
    "meadows_1972_limits_to_growth",
    "commoner_1971_closing_circle",
    "schumacher_1974_small_is_beautiful",
]
DECADES_ORDER = ["1970s", "1980s", "1990s", "2000s", "2010s", "2020s", "unknown"]
Z = 1.959963984540054  # qnorm(0.975)


def wilson_ci(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    z2 = Z * Z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (Z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def main() -> None:
    print(f"[{now_iso()}] characterizing corpus from build outputs")
    census = load(CENSUS)
    s2_att = load(S2_ATT)
    oa_att = load(OA_ATT)
    s2_ctx = load(S2_CTX)
    oa_ctx = load(OA_CTX)
    combined = load(COMBINED)

    # ----- Pool sizes per (seed, decade, route) ------------------------------
    # S2-eligible pool: census rows with DOI OR MAG (the S2 sample restricted
    # to these because lib_corpus.s2_get needs an external ID).
    s2_pool_by_sd: Counter = Counter()
    oa_pool_by_sd: Counter = Counter()  # citing_oa_url non-empty
    census_by_sd: Counter = Counter()
    for r in census:
        sd = (r["seed_id"], r["citing_decade"])
        census_by_sd[sd] += 1
        if r["citing_doi"] or r["citing_mag"]:
            s2_pool_by_sd[sd] += 1
        if (r["citing_oa_url"] or "").strip():
            oa_pool_by_sd[sd] += 1

    # ----- Realized attempts per (seed, decade, route) -----------------------
    s2_attempted_by_sd: Counter = Counter()
    for r in s2_att:
        s2_attempted_by_sd[(r["seed_id"], r["citing_decade"])] += 1
    oa_attempted_by_sd: Counter = Counter()  # all OA attempts (incl. fetch_failed)
    oa_fetched_by_sd: Counter = Counter()    # only fetch_status == "fetched"
    for r in oa_att:
        sd = (r["seed_id"], r["citing_decade"])
        oa_attempted_by_sd[sd] += 1
        if r["fetch_status"] == "fetched":
            oa_fetched_by_sd[sd] += 1

    # ----- Yielders per (seed, decade, route) --------------------------------
    s2_yield_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in s2_ctx:
        s2_yield_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])
    oa_yield_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in oa_ctx:
        oa_yield_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(r["citing_openalex_id"])

    # ----- Combined (union of routes) per (seed, decade) ---------------------
    combined_attempt_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    s2_att_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    oa_fetched_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in s2_att:
        sd = (r["seed_id"], r["citing_decade"])
        s2_att_pairs_by_sd[sd].add(r["citing_openalex_id"])
        combined_attempt_pairs_by_sd[sd].add(r["citing_openalex_id"])
    for r in oa_att:
        if r["fetch_status"] != "fetched":
            continue
        sd = (r["seed_id"], r["citing_decade"])
        oa_fetched_pairs_by_sd[sd].add(r["citing_openalex_id"])
        combined_attempt_pairs_by_sd[sd].add(r["citing_openalex_id"])
    combined_yield_pairs_by_sd: dict[tuple, set] = defaultdict(set)
    for r in combined:
        combined_yield_pairs_by_sd[(r["seed_id"], r["citing_decade"])].add(
            r["citing_openalex_id"])

    # =====================================================================
    # 1) SAMPLING MANIFEST
    # =====================================================================
    sm_rows = []
    sd_list = sorted({sd for sd in census_by_sd}, key=lambda x: (x[0], DECADES_ORDER.index(x[1]) if x[1] in DECADES_ORDER else 99))
    for seed, decade in sd_list:
        sd = (seed, decade)
        census_N = census_by_sd[sd]
        # S2 stratum (only 2010s/2020s sampled; others unfilled-by-design)
        s2_nom = NOMINAL_S2_PER_STRATUM if decade in NOMINAL_S2_DECADES else 0
        s2_pool = s2_pool_by_sd[sd]
        s2_real = s2_attempted_by_sd[sd]
        s2_y = len(s2_yield_pairs_by_sd[sd])
        s2_underfilled = (decade in NOMINAL_S2_DECADES) and (s2_real < s2_nom)
        s2_design_excluded = decade not in NOMINAL_S2_DECADES
        sm_rows.append({
            "seed_id": seed,
            "decade": decade,
            "route": "s2_graph_api",
            "census_pool_total": census_N,
            "route_eligible_pool": s2_pool,
            "nominal_target": s2_nom,
            "realized_sampled": s2_real,
            "yielded_works": s2_y,
            "underfilled_flag": "DESIGN_EXCLUDED" if s2_design_excluded
                                  else ("UNDERFILLED" if s2_underfilled else "OK"),
            "underfilled_reason": ("decade excluded by design (S2 has ~0% yield pre-2010 per spike)"
                                    if s2_design_excluded
                                    else ("realized<nominal — pool exhaustion"
                                          if s2_underfilled else "")),
        })
        # OA stratum (all decades sampled)
        oa_nom = NOMINAL_OA_PER_STRATUM if decade in NOMINAL_OA_DECADES else 0
        oa_pool = oa_pool_by_sd[sd]
        oa_real_all = oa_attempted_by_sd[sd]
        oa_real_fetched = oa_fetched_by_sd[sd]
        oa_y = len(oa_yield_pairs_by_sd[sd])
        oa_underfilled = (decade in NOMINAL_OA_DECADES) and (oa_real_all < min(oa_nom, oa_pool))
        oa_pool_exhausted = (decade in NOMINAL_OA_DECADES) and (oa_pool < oa_nom)
        sm_rows.append({
            "seed_id": seed,
            "decade": decade,
            "route": "openalex_oa_fulltext",
            "census_pool_total": census_N,
            "route_eligible_pool": oa_pool,
            "nominal_target": oa_nom,
            "realized_sampled": oa_real_all,
            "realized_sampled_fetched_ok": oa_real_fetched,
            "yielded_works": oa_y,
            "underfilled_flag": ("DESIGN_EXCLUDED" if decade not in NOMINAL_OA_DECADES
                                  else "POOL_EXHAUSTED" if oa_pool_exhausted
                                  else "UNDERFILLED" if oa_underfilled else "OK"),
            "underfilled_reason": ("OA URL pool smaller than nominal target"
                                    if oa_pool_exhausted else
                                    "realized<nominal — sampling under-fill"
                                    if oa_underfilled else ""),
        })
        # Combined union row per (seed, decade)
        comb_attempt = len(combined_attempt_pairs_by_sd[sd])
        comb_yield = len(combined_yield_pairs_by_sd[sd])
        sm_rows.append({
            "seed_id": seed,
            "decade": decade,
            "route": "COMBINED_UNION",
            "census_pool_total": census_N,
            "route_eligible_pool": comb_attempt,  # union of attempted across routes
            "nominal_target": "",
            "realized_sampled": comb_attempt,
            "yielded_works": comb_yield,
            "underfilled_flag": "OK",
            "underfilled_reason": "",
        })
    # Write
    field_order = [
        "seed_id", "decade", "route", "census_pool_total", "route_eligible_pool",
        "nominal_target", "realized_sampled", "realized_sampled_fetched_ok",
        "yielded_works", "underfilled_flag", "underfilled_reason",
    ]
    with OUT_SAMPLING.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=field_order)
        w.writeheader()
        for r in sm_rows:
            w.writerow({k: r.get(k, "") for k in field_order})

    # Reconciliation to 885 union (verify the reconstructed counts add up)
    total_union_attempts = sum(len(combined_attempt_pairs_by_sd[sd]) for sd in sd_list)
    total_union_yields = sum(len(combined_yield_pairs_by_sd[sd]) for sd in sd_list)
    print(f"\nSAMPLING MANIFEST: union attempts={total_union_attempts}, yields={total_union_yields}")
    print(f"  (matches BUILD_REPORT.md 885/141 if equal)")

    # =====================================================================
    # 2) CORRECTED STRATIFIED YIELD PROJECTION
    # =====================================================================
    # Apply per (seed, decade) UNION yield rate to census stratum population.
    # Wilson CIs per stratum on the rate; combined projected works = sum of
    # stratum projections; combined CI = sum of stratum lo bounds and sum of
    # stratum hi bounds (conservative — assumes maximally correlated; honest
    # because per-stratum sample sizes are small and combining variances
    # would understate uncertainty in that regime).
    yp_rows = []
    sum_proj_point = 0.0
    sum_proj_lo = 0.0
    sum_proj_hi = 0.0
    sum_census = 0
    sum_attempts = 0
    sum_yields = 0
    for seed, decade in sd_list:
        sd = (seed, decade)
        N = census_by_sd[sd]
        n = len(combined_attempt_pairs_by_sd[sd])
        k = len(combined_yield_pairs_by_sd[sd])
        p, lo, hi = wilson_ci(k, n)
        proj = p * N
        proj_lo = lo * N
        proj_hi = hi * N
        yp_rows.append({
            "seed_id": seed,
            "decade": decade,
            "census_N": N,
            "sampled_n_union": n,
            "yielded_k_union": k,
            "rate_point": f"{p:.4f}",
            "rate_wilson95_lo": f"{lo:.4f}",
            "rate_wilson95_hi": f"{hi:.4f}",
            "projected_yielding_works_point": f"{proj:.1f}",
            "projected_yielding_works_lo": f"{proj_lo:.1f}",
            "projected_yielding_works_hi": f"{proj_hi:.1f}",
        })
        sum_proj_point += proj
        sum_proj_lo += proj_lo
        sum_proj_hi += proj_hi
        sum_census += N
        sum_attempts += n
        sum_yields += k

    # Contexts per yielding work (sample mean from observed combined corpus)
    contexts_per_yielder = []
    yielder_to_n_contexts: dict[tuple, int] = defaultdict(int)
    for r in combined:
        yielder_to_n_contexts[(r["seed_id"], r["citing_openalex_id"])] += 1
    contexts_per_yielder = list(yielder_to_n_contexts.values())
    mean_ctx_per_yielder = sum(contexts_per_yielder) / len(contexts_per_yielder)
    var_ctx = sum((x - mean_ctx_per_yielder) ** 2 for x in contexts_per_yielder) / len(contexts_per_yielder)
    sd_ctx = math.sqrt(var_ctx)
    se_mean_ctx = sd_ctx / math.sqrt(len(contexts_per_yielder))
    ctx_lo = mean_ctx_per_yielder - Z * se_mean_ctx
    ctx_hi = mean_ctx_per_yielder + Z * se_mean_ctx

    proj_contexts_point = sum_proj_point * mean_ctx_per_yielder
    # Propagate by combining the two intervals (conservative product):
    proj_contexts_lo = sum_proj_lo * max(0.0, ctx_lo)
    proj_contexts_hi = sum_proj_hi * ctx_hi

    yp_rows.append({
        "seed_id": "TOTAL",
        "decade": "ALL",
        "census_N": sum_census,
        "sampled_n_union": sum_attempts,
        "yielded_k_union": sum_yields,
        "rate_point": f"{(sum_yields/sum_attempts):.4f}",
        "rate_wilson95_lo": "(see overall_wilson_below)",
        "rate_wilson95_hi": "(see overall_wilson_below)",
        "projected_yielding_works_point": f"{sum_proj_point:.0f}",
        "projected_yielding_works_lo": f"{sum_proj_lo:.0f}",
        "projected_yielding_works_hi": f"{sum_proj_hi:.0f}",
    })

    p_all, lo_all, hi_all = wilson_ci(sum_yields, sum_attempts)
    naive_proj = p_all * sum_census
    naive_lo = lo_all * sum_census
    naive_hi = hi_all * sum_census

    # Write the projection CSV with a small footer for the headline numbers
    with OUT_YIELD.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(yp_rows[0].keys()))
        w.writeheader()
        for r in yp_rows:
            w.writerow(r)
        # Append context-mean + projection lines as separate marker rows
        f.write("\n")
        w2 = csv.writer(f)
        w2.writerow(["headline", "metric", "point", "wilson95_lo", "wilson95_hi", "units"])
        w2.writerow(["stratified", "projected_yielding_works",
                     f"{sum_proj_point:.0f}", f"{sum_proj_lo:.0f}", f"{sum_proj_hi:.0f}",
                     "citing works in the 13,054-work census predicted to yield >=1 context"])
        w2.writerow(["stratified", "contexts_per_yielding_work_mean_observed",
                     f"{mean_ctx_per_yielder:.3f}", f"{ctx_lo:.3f}", f"{ctx_hi:.3f}",
                     f"contexts per yielding work (sample n={len(contexts_per_yielder)} yielders; sd={sd_ctx:.3f})"])
        w2.writerow(["stratified", "projected_contexts",
                     f"{proj_contexts_point:.0f}",
                     f"{proj_contexts_lo:.0f}", f"{proj_contexts_hi:.0f}",
                     "extracted citing-context strings (= projected_yielding_works * mean_contexts/yielder)"])
        w2.writerow(["naive_for_reference_only", "projected_yielding_works (naive 13,054 * overall rate)",
                     f"{naive_proj:.0f}", f"{naive_lo:.0f}", f"{naive_hi:.0f}",
                     "naive estimate — superseded by stratified above"])

    print(f"\nYIELD PROJECTION (stratified):")
    print(f"  yielding works: {sum_proj_point:.0f}  [{sum_proj_lo:.0f}, {sum_proj_hi:.0f}]")
    print(f"  contexts/yielder mean: {mean_ctx_per_yielder:.2f}  95% CI [{ctx_lo:.2f}, {ctx_hi:.2f}]")
    print(f"  projected contexts: {proj_contexts_point:.0f}  [{proj_contexts_lo:.0f}, {proj_contexts_hi:.0f}]")
    print(f"  (naive for reference: {naive_proj:.0f}  [{naive_lo:.0f}, {naive_hi:.0f}])")

    # =====================================================================
    # 3) COVERAGE-BIAS PROFILE
    # =====================================================================
    # Restrict to the 885 attempted (seed, citing) pairs; compare yielders
    # (n=141) vs non-yielders (n=744) by covariates from the census.
    # NB: combined_attempt_pairs_by_sd[(seed,decade)] stores citing_openalex_id
    # strings, so we re-key on (seed, citing) tuples to match census rows.
    attempt_pairs: set[tuple[str, str]] = set()
    for (seed, decade), ids in combined_attempt_pairs_by_sd.items():
        for cid in ids:
            attempt_pairs.add((seed, cid))
    # Map (seed, citing) -> full census row covariates
    census_idx: dict[tuple, dict] = {}
    for r in census:
        census_idx[(r["seed_id"], r["citing_openalex_id"])] = r
    yielders = set()
    for r in combined:
        yielders.add((r["seed_id"], r["citing_openalex_id"]))
    # Among the union of attempts:
    n_total = len(attempt_pairs)
    n_yield = sum(1 for p in attempt_pairs if p in yielders)

    # Covariates to slice on. For each level: yielders, non-yielders,
    # yield_rate, base rate in attempted, base rate in full census.
    def census_rate(field_value_filter) -> tuple[int, int]:
        """Returns (k_yield_in_attempts, n_in_attempts) for the filter, plus
        (n_in_full_census). Use closure for the field."""
        k = 0
        n = 0
        N = 0
        for r in census:
            if not field_value_filter(r):
                continue
            N += 1
            key = (r["seed_id"], r["citing_openalex_id"])
            if key in attempt_pairs:
                n += 1
                if key in yielders:
                    k += 1
        return k, n, N

    cb_rows = []
    # Decade
    for d in DECADES_ORDER:
        k, n, N = census_rate(lambda r, _d=d: r["citing_decade"] == _d)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "decade", "level": d,
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })
    # Type (top 8 by census count)
    type_counts = Counter(r["citing_type"] or "unknown" for r in census)
    top_types = [t for t, _ in type_counts.most_common(8)]
    for t in top_types:
        k, n, N = census_rate(lambda r, _t=t: (r["citing_type"] or "unknown") == _t)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "type", "level": t,
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })
    # Primary field (top 10)
    field_counts = Counter((r["citing_primary_field"] or "unknown") for r in census)
    top_fields = [f for f, _ in field_counts.most_common(10)]
    for fld in top_fields:
        k, n, N = census_rate(lambda r, _f=fld: (r["citing_primary_field"] or "unknown") == _f)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "primary_field", "level": fld,
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })
    # OA status
    for oa_flag in ("True", "False"):
        k, n, N = census_rate(lambda r, _f=oa_flag: r["citing_is_oa"] == _f)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "is_oa", "level": ("OA" if oa_flag == "True" else "non-OA"),
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })
    # Language
    lang_counts = Counter((r["citing_language"] or "unknown") for r in census)
    top_langs = [l for l, _ in lang_counts.most_common(6)]
    for lg in top_langs:
        k, n, N = census_rate(lambda r, _l=lg: (r["citing_language"] or "unknown") == _l)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "language", "level": lg,
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })
    # Seed
    for s in SEEDS_ACTIVE:
        k, n, N = census_rate(lambda r, _s=s: r["seed_id"] == _s)
        p, lo, hi = wilson_ci(k, n)
        cb_rows.append({
            "dimension": "seed_id", "level": s,
            "n_attempts_in_level": n, "k_yielders_in_level": k,
            "yield_rate": f"{p:.4f}",
            "yield_rate_wilson95_lo": f"{lo:.4f}",
            "yield_rate_wilson95_hi": f"{hi:.4f}",
            "n_in_full_census": N,
            "fraction_of_full_census": f"{(N/sum_census):.4f}",
            "fraction_of_attempts": f"{(n/n_total):.4f}" if n_total else "0",
            "delta_from_overall_rate": f"{(p - n_yield/n_total):+.4f}" if n_total else "0",
        })

    with OUT_COVBIAS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cb_rows[0].keys()))
        w.writeheader()
        for r in cb_rows:
            w.writerow(r)
    print(f"\nCOVERAGE-BIAS: wrote {OUT_COVBIAS} ({len(cb_rows)} rows)")

    # =====================================================================
    # 4) PRE-1990 PROJECTIONS WITH CIs
    # =====================================================================
    # Restate per (seed × decade) projections for 1970s + 1980s + 1990s with
    # Wilson 95% CI on the extraction rate and the resulting projected-count
    # range, replacing the bare point estimates in BUILD_REPORT §4.
    pre1990_rows = []
    for seed in SEEDS_ACTIVE:
        for decade in ["1970s", "1980s", "1990s"]:
            sd = (seed, decade)
            raw = census_by_sd[sd]
            sampled = len(combined_attempt_pairs_by_sd[sd])
            extracted = len(combined_yield_pairs_by_sd[sd])
            p, lo, hi = wilson_ci(extracted, sampled)
            proj_point = p * raw
            proj_lo = lo * raw
            proj_hi = hi * raw
            # Same diagnosis rules as 06_pre1990_diagnosis.py
            if raw < 20:
                diag = "REAL_TROUGH"
            elif sampled == 0:
                diag = "NOT_SAMPLED"
            elif p < 0.05:
                diag = "COVERAGE_ARTIFACT"
            elif p >= 0.25:
                diag = "EXTRACTION_OK_NOT_AN_ISSUE"
            else:
                diag = "MIXED_ARTIFACT_AND_TROUGH"
            pre1990_rows.append({
                "seed_id": seed,
                "decade": decade,
                "raw_works": raw,
                "sampled_n": sampled,
                "extracted_k": extracted,
                "rate_point": f"{p:.4f}",
                "rate_wilson95_lo": f"{lo:.4f}",
                "rate_wilson95_hi": f"{hi:.4f}",
                "projected_works_point": f"{proj_point:.1f}",
                "projected_works_lo": f"{proj_lo:.1f}",
                "projected_works_hi": f"{proj_hi:.1f}",
                "ci_half_width_works_units": f"{((proj_hi - proj_lo)/2):.1f}",
                "diagnosis": diag,
            })
    with OUT_PRE1990.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pre1990_rows[0].keys()))
        w.writeheader()
        for r in pre1990_rows:
            w.writerow(r)
    print(f"PRE-1990 CIs: wrote {OUT_PRE1990} ({len(pre1990_rows)} rows)")

    print(f"\nfinished_at={now_iso()}")


if __name__ == "__main__":
    main()
