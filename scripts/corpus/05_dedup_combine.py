#!/usr/bin/env python3
"""Step 3c — dedup + combine S2 and OA-PDF context rows.

Outputs:
  analysis/corpus_production/contexts_combined.csv  (deduplicated; one row
                                                     per unique (seed, citing,
                                                     normalized_text); carries
                                                     provenance for both
                                                     routes when the same
                                                     context surfaces in both)
  analysis/corpus_production/context_coverage_summary.csv  (per-seed and per
                                                            (seed, decade,
                                                            type) coverage =
                                                            citing works with
                                                            >=1 context /
                                                            citing works in
                                                            the sample,
                                                            with Wilson 95%
                                                            CIs)

Dedup logic:
  - Same (seed_id, citing_openalex_id, normalized_context_text) where
    normalized = lower + collapsed whitespace + first 240 chars.
  - When a context appears via both S2 and OA, retain ONE row with
    `routes=s2|openalex_oa_fulltext`; otherwise route is the sole source.
"""

from __future__ import annotations

import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import CORPUS_DIR, now_iso

S2_CTX = CORPUS_DIR / "contexts_s2.csv"
OA_CTX = CORPUS_DIR / "contexts_oa.csv"
S2_ATT = CORPUS_DIR / "contexts_s2_attempted.csv"
OA_ATT = CORPUS_DIR / "contexts_oa_attempted.csv"
OUT_COMBINED = CORPUS_DIR / "contexts_combined.csv"
OUT_COVERAGE = CORPUS_DIR / "context_coverage_summary.csv"

_WS_RE = re.compile(r"\s+")


def norm(text: str) -> str:
    t = (text or "").lower().strip()
    t = _WS_RE.sub(" ", t)
    return t[:240]


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
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


def main() -> None:
    s2 = load_csv(S2_CTX)
    oa = load_csv(OA_CTX)
    s2_att = load_csv(S2_ATT)
    oa_att = load_csv(OA_ATT)
    print(f"[{now_iso()}] Step 3c — dedup + combine")
    print(f"  S2 context rows:        {len(s2)}")
    print(f"  OA-PDF context rows:    {len(oa)}")
    print(f"  S2 attempted:           {len(s2_att)}")
    print(f"  OA attempted:           {len(oa_att)}")

    combined: dict[tuple, dict] = {}
    out_fields = [
        "seed_id", "citing_openalex_id", "citing_doi", "citing_year",
        "citing_decade", "citing_type", "routes", "n_routes",
        "context_text", "context_text_normalized",
        "s2_match_reason", "s2_intents", "s2_is_influential",
        "oa_match_kind", "oa_url", "oa_doc_sha256_16",
        "first_retrieved_at_utc",
    ]
    for r in s2:
        key = (r["seed_id"], r["citing_openalex_id"], norm(r.get("context_text", "")))
        if not key[2]:
            continue
        combined[key] = {
            "seed_id": r["seed_id"],
            "citing_openalex_id": r["citing_openalex_id"],
            "citing_doi": r.get("citing_doi", ""),
            "citing_year": r.get("citing_year", ""),
            "citing_decade": r.get("citing_decade", ""),
            "citing_type": r.get("citing_type", ""),
            "routes": "s2_graph_api_references",
            "n_routes": 1,
            "context_text": r.get("context_text", ""),
            "context_text_normalized": key[2],
            "s2_match_reason": r.get("match_reason", ""),
            "s2_intents": r.get("intents", ""),
            "s2_is_influential": r.get("is_influential", ""),
            "oa_match_kind": "",
            "oa_url": "",
            "oa_doc_sha256_16": "",
            "first_retrieved_at_utc": r.get("retrieved_at_utc", ""),
        }
    for r in oa:
        key = (r["seed_id"], r["citing_openalex_id"], norm(r.get("sentence", "")))
        if not key[2]:
            continue
        if key in combined:
            existing = combined[key]
            existing["routes"] = "s2_graph_api_references|openalex_oa_fulltext"
            existing["n_routes"] = 2
            existing["oa_match_kind"] = r.get("match_kind", "")
            existing["oa_url"] = r.get("oa_url", "")
            existing["oa_doc_sha256_16"] = r.get("doc_sha256_16", "")
        else:
            combined[key] = {
                "seed_id": r["seed_id"],
                "citing_openalex_id": r["citing_openalex_id"],
                "citing_doi": r.get("citing_doi", ""),
                "citing_year": r.get("citing_year", ""),
                "citing_decade": r.get("citing_decade", ""),
                "citing_type": r.get("citing_type", ""),
                "routes": "openalex_oa_fulltext",
                "n_routes": 1,
                "context_text": r.get("sentence", ""),
                "context_text_normalized": key[2],
                "s2_match_reason": "",
                "s2_intents": "",
                "s2_is_influential": "",
                "oa_match_kind": r.get("match_kind", ""),
                "oa_url": r.get("oa_url", ""),
                "oa_doc_sha256_16": r.get("doc_sha256_16", ""),
                "first_retrieved_at_utc": r.get("retrieved_at_utc", ""),
            }

    rows = list(combined.values())
    with OUT_COMBINED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  wrote {OUT_COMBINED} ({len(rows)} deduped context rows)")

    # Coverage = citing works with >=1 context / citing works attempted.
    # Attempted counts per route per stratum:
    s2_attempted_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in s2_att}
    oa_attempted_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in oa_att
                            if r.get("fetch_status") == "fetched"}
    all_attempted = s2_attempted_pairs | oa_attempted_pairs
    yielded_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in rows}

    # Per-seed strata + overall
    seeds = sorted({p[0] for p in all_attempted})
    decades = ["1970s", "1980s", "1990s", "2000s", "2010s", "2020s", "unknown"]

    att_by_stratum: dict[tuple, int] = defaultdict(int)
    yld_by_stratum: dict[tuple, int] = defaultdict(int)
    # Need decade per (seed, citing). Build from attempted CSVs.
    pair_decade: dict[tuple, str] = {}
    pair_type: dict[tuple, str] = {}
    for r in s2_att + oa_att:
        key = (r["seed_id"], r["citing_openalex_id"])
        pair_decade.setdefault(key, r.get("citing_decade") or "unknown")
        pair_type.setdefault(key, r.get("citing_type") or "unknown")
    for p in all_attempted:
        d = pair_decade.get(p, "unknown")
        att_by_stratum[(p[0], d)] += 1
    for p in yielded_pairs & all_attempted:
        d = pair_decade.get(p, "unknown")
        yld_by_stratum[(p[0], d)] += 1

    with OUT_COVERAGE.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scope", "seed_id", "decade", "type",
                    "attempted_n", "yielded_k", "rate",
                    "wilson95_lo", "wilson95_hi"])
        # Overall per seed
        for s in seeds:
            att = sum(att_by_stratum[(s, d)] for d in decades)
            yld = sum(yld_by_stratum[(s, d)] for d in decades)
            p, lo, hi = wilson_ci(yld, att)
            w.writerow(["per_seed", s, "ALL", "ALL", att, yld,
                        f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])
        # Per-seed by decade
        for s in seeds:
            for d in decades:
                att = att_by_stratum[(s, d)]
                yld = yld_by_stratum[(s, d)]
                if att == 0:
                    continue
                p, lo, hi = wilson_ci(yld, att)
                w.writerow(["per_seed_by_decade", s, d, "ALL", att, yld,
                            f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])
        # Combined across seeds
        att_all = len(all_attempted)
        yld_all = len(yielded_pairs & all_attempted)
        p, lo, hi = wilson_ci(yld_all, att_all)
        w.writerow(["combined", "ALL", "ALL", "ALL", att_all, yld_all,
                    f"{p:.4f}", f"{lo:.4f}", f"{hi:.4f}"])

    print(f"  wrote {OUT_COVERAGE}")
    print(f"\nfinished_at={now_iso()}")


if __name__ == "__main__":
    main()
