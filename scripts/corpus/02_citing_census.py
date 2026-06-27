#!/usr/bin/env python3
"""Step 2 — frozen citing-works census for the 3 active seeds.

For each active seed (Meadows, Commoner, Schumacher; Goldsmith RESERVE excluded),
retrieve EVERY citing work via OpenAlex `filter=cites:WID`, UNIONING the
canonical Work ID with the alt-edition Work IDs from Step 1 so a citing work
isn't double-counted when it cites multiple editions of the same book.

Tabulate per seed by decade × type × primary-topic field and write the
combined per-work table + the per-seed cross-tabs. No labelling, no inference
— this is structured DATA capture for downstream steps.

Inputs:
  analysis/corpus_production/seed_resolution.csv  (active rows only)
  analysis/corpus_production/seed_alt_editions_detail.json

Outputs:
  analysis/corpus_production/citing_census.csv             (per-work, one row
                                                            per (seed, citing
                                                            work); contains
                                                            the alt-edition
                                                            attribution)
  analysis/corpus_production/citing_census_summary.csv     (decade × type ×
                                                            seed cross-tab)
  analysis/corpus_production/raw/citing_<seed>_oa_<wid>_page*.json
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import openalex_paginate, CORPUS_DIR, now_iso, decade_of

SEED_RES_CSV = CORPUS_DIR / "seed_resolution.csv"
EDITIONS_JSON = CORPUS_DIR / "seed_alt_editions_detail.json"
OUT_PER_WORK = CORPUS_DIR / "citing_census.csv"
OUT_SUMMARY = CORPUS_DIR / "citing_census_summary.csv"


def load_active_seeds() -> list[dict]:
    if not SEED_RES_CSV.exists():
        raise SystemExit("Run 01_resolve_seeds.py first.")
    with SEED_RES_CSV.open() as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["build_action"] == "build_corpus"]


def short_wid(url_or_id: str) -> str:
    return (url_or_id or "").split("/")[-1]


def load_editions() -> dict[str, list[dict]]:
    if not EDITIONS_JSON.exists():
        return {}
    return json.loads(EDITIONS_JSON.read_text())


def census_one_seed(seed_row: dict, editions: list[dict]) -> tuple[list[dict], dict]:
    """Retrieve all citing works for canonical + alt-edition Work IDs;
    union by citing OpenAlex Work ID. Returns (citing_works_unioned, stats)."""
    seed_id = seed_row["seed_id"]
    canonical = short_wid(seed_row["openalex_id"])
    alt_ids = [short_wid(e["id"]) for e in editions]
    all_target_ids = [canonical] + alt_ids
    print(f"  seed={seed_id}  canonical={canonical}  "
          f"alt_editions={len(alt_ids)}  total_filter_ids={len(all_target_ids)}")

    select = ("id,doi,ids,title,display_name,publication_year,type,type_crossref,"
              "cited_by_count,is_retracted,primary_topic,best_oa_location,"
              "primary_location,language")

    # Collect citing works per target Work ID, then union by citing OpenAlex ID
    seen: dict[str, dict] = {}              # citing_oa_id -> first-seen record
    seen_via: dict[str, list[str]] = {}     # citing_oa_id -> list of target seed/edition ids it cites
    per_target_counts: dict[str, int] = {}
    raw_subdir = f"citing_{seed_id}"

    for tgt in all_target_ids:
        page = openalex_paginate(
            "works",
            base_params={"filter": f"cites:{tgt}", "select": select},
            page_size=200,
            raw_stem=f"oa_filter_cites_{tgt}",
            subdir=raw_subdir,
        )
        per_target_counts[tgt] = len(page["results"])
        for r in page["results"]:
            cid = r.get("id")
            if not cid:
                continue
            if cid not in seen:
                seen[cid] = r
                seen_via[cid] = [tgt]
            else:
                seen_via[cid].append(tgt)
    union_n = len(seen)
    sum_raw = sum(per_target_counts.values())
    overlap = sum_raw - union_n
    print(f"    per-target: {per_target_counts}")
    print(f"    union={union_n}  raw_sum={sum_raw}  overlap={overlap}")

    citing_rows = []
    for cid, r in seen.items():
        ids = r.get("ids") or {}
        pt = r.get("primary_topic") or {}
        pt_field = ((pt.get("field") or {}).get("display_name")) if pt else None
        pt_subfield = ((pt.get("subfield") or {}).get("display_name")) if pt else None
        ploc = r.get("primary_location") or {}
        psrc = ((ploc.get("source") or {}).get("display_name")) if ploc else None
        best_oa = r.get("best_oa_location") or {}
        citing_rows.append({
            "seed_id": seed_id,
            "citing_openalex_id": cid,
            "citing_doi": r.get("doi") or "",
            "citing_mag": ids.get("mag") or "",
            "citing_pmid": ids.get("pmid") or "",
            "citing_year": r.get("publication_year") or "",
            "citing_decade": decade_of(r.get("publication_year")),
            "citing_type": r.get("type") or "",
            "citing_type_crossref": r.get("type_crossref") or "",
            "citing_is_retracted": bool(r.get("is_retracted")),
            "citing_language": r.get("language") or "",
            "citing_cited_by_count": r.get("cited_by_count") or 0,
            "citing_primary_topic": pt.get("display_name") if pt else "",
            "citing_primary_field": pt_field or "",
            "citing_primary_subfield": pt_subfield or "",
            "citing_primary_source": psrc or "",
            "citing_is_oa": bool(best_oa.get("is_oa")),
            "citing_oa_url": best_oa.get("pdf_url") or best_oa.get("landing_page_url") or "",
            "citing_title": (r.get("display_name") or r.get("title") or "")
                              .replace("\n", " ").replace("\r", " "),
            "cites_target_ids": "|".join(seen_via[cid]),
            "cites_n_target_editions": len(seen_via[cid]),
        })
    stats = {
        "seed_id": seed_id,
        "canonical_id": canonical,
        "alt_edition_ids": alt_ids,
        "per_target_counts": per_target_counts,
        "raw_sum_across_targets": sum_raw,
        "unioned_unique_citing_works": union_n,
        "overlap_dropped_by_union": overlap,
    }
    return citing_rows, stats


def main() -> None:
    print(f"[{now_iso()}] Step 2 — citing-works census (3 active seeds; "
          f"canonical + alt-edition union)\n")
    active = load_active_seeds()
    editions_by_seed = load_editions()
    print(f"  active seeds: {[s['seed_id'] for s in active]}")

    all_rows: list[dict] = []
    all_stats: list[dict] = []
    for s in active:
        print(f"\n-- {s['seed_id']} --")
        eds = editions_by_seed.get(s["seed_id"], [])
        rows, stats = census_one_seed(s, eds)
        all_rows.extend(rows)
        all_stats.append(stats)

    # Per-work CSV
    fieldnames = list(all_rows[0].keys())
    with OUT_PER_WORK.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"\nwrote {OUT_PER_WORK} ({len(all_rows)} rows; "
          f"{len({(r['seed_id'], r['citing_openalex_id']) for r in all_rows})} unique (seed,citing) pairs)")

    # Summary cross-tab: rows are decades + TOTAL, columns split per seed
    seeds_ordered = [s["seed_id"] for s in active]
    decade_order = ["1970s", "1980s", "1990s", "2000s", "2010s", "2020s", "unknown"]
    by_seed_decade: dict[tuple, int] = defaultdict(int)
    by_seed_decade_type: dict[tuple, int] = defaultdict(int)
    by_seed_type: dict[tuple, int] = defaultdict(int)
    by_seed_field: dict[tuple, int] = defaultdict(int)
    by_seed_oa: dict[tuple, int] = defaultdict(int)
    by_seed_total: Counter[str] = Counter()
    for r in all_rows:
        s = r["seed_id"]
        d = r["citing_decade"]
        t = r["citing_type"] or "unknown"
        f_ = r["citing_primary_field"] or "unknown"
        by_seed_decade[(s, d)] += 1
        by_seed_decade_type[(s, d, t)] += 1
        by_seed_type[(s, t)] += 1
        by_seed_field[(s, f_)] += 1
        by_seed_total[s] += 1
        if r["citing_is_oa"]:
            by_seed_oa[(s, d)] += 1

    with OUT_SUMMARY.open("w", newline="") as f:
        w = csv.writer(f)
        # Block A: decade x seed cross-tab (with OA rate)
        w.writerow(["dimension"] + [f"{s}_n" for s in seeds_ordered]
                   + [f"{s}_oa_n" for s in seeds_ordered])
        for d in decade_order:
            w.writerow([f"decade={d}"]
                       + [by_seed_decade[(s, d)] for s in seeds_ordered]
                       + [by_seed_oa[(s, d)] for s in seeds_ordered])
        w.writerow(["decade=TOTAL"]
                   + [by_seed_total[s] for s in seeds_ordered]
                   + [sum(by_seed_oa[(s, d)] for d in decade_order) for s in seeds_ordered])
        w.writerow([])
        # Block B: type x seed
        all_types = sorted({t for (s, t) in by_seed_type})
        w.writerow(["type"] + [f"{s}_n" for s in seeds_ordered])
        for t in all_types:
            w.writerow([f"type={t}"] + [by_seed_type[(s, t)] for s in seeds_ordered])
        w.writerow([])
        # Block C: top fields per seed
        w.writerow(["top_fields_per_seed"])
        for s in seeds_ordered:
            top = sorted(((f_, n) for ((ss, f_), n) in by_seed_field.items() if ss == s),
                         key=lambda x: -x[1])[:10]
            w.writerow([f"seed={s}", "field", "n"])
            for f_, n in top:
                w.writerow(["", f_, n])
            w.writerow([])
        # Block D: census stats (per-target, union, overlap)
        w.writerow(["census_stats_per_seed"])
        w.writerow(["seed_id", "canonical_id", "alt_edition_ids",
                    "raw_sum_across_targets", "unioned_unique_citing_works",
                    "overlap_dropped_by_union"])
        for st in all_stats:
            w.writerow([st["seed_id"], st["canonical_id"],
                        ";".join(st["alt_edition_ids"]),
                        st["raw_sum_across_targets"],
                        st["unioned_unique_citing_works"],
                        st["overlap_dropped_by_union"]])

    # Persist stats JSON too (for provenance manifest)
    stats_json = CORPUS_DIR / "citing_census_stats.json"
    stats_json.write_text(json.dumps({
        "started_at_utc": now_iso(),
        "active_seeds": [s["seed_id"] for s in active],
        "per_seed_stats": all_stats,
    }, indent=2))

    print(f"wrote {OUT_SUMMARY}")
    print(f"wrote {stats_json}")
    print(f"\nfinished_at={now_iso()}")
    # Headline
    print("\nHEADLINE (unioned unique citing works per seed):")
    for st in all_stats:
        print(f"  {st['seed_id']:42s} {st['unioned_unique_citing_works']:>6d}  "
              f"(raw sum {st['raw_sum_across_targets']}, overlap dropped {st['overlap_dropped_by_union']})")


if __name__ == "__main__":
    main()
