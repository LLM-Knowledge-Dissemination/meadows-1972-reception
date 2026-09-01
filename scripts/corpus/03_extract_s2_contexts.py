#!/usr/bin/env python3
"""Step 3a — extract citing CONTEXTS from Semantic Scholar Graph API.

Per active seed, walk the citing-works table and for each citing paper:
  - if it has a DOI, call paper/DOI:{doi}/references (limit=1000) and find
    the reference matching the seed (by ID-match against canonical/reprint
    forms, then title+author+year fallback);
  - record contexts/intents/isInfluential on the matched reference;
  - persist raw S2 response per paper for reproducibility.

This is DATA capture only — we store S2's pre-computed contexts/intents/
isInfluential fields verbatim, with no LLM in the loop.

Configurable via env vars:
  CORPUS_S2_DECADES   — comma list (default '2010s,2020s'; spike showed S2
                        Graph yield is structurally ~0% pre-2010)
  CORPUS_S2_N_PER     — per (seed × decade) sample size (default 200)
  CORPUS_S2_SEED      — RNG seed for stratified sampling (default 20260624)
  CORPUS_S2_CHECKPOINT — write checkpoint every N items (default 50)

Outputs:
  analysis/corpus_production/contexts_s2.csv          (one row per matched
                                                       (seed, citing) where
                                                       S2 had a reference list
                                                       AND a Meadows-class
                                                       reference)
  analysis/corpus_production/contexts_s2_attempted.csv (one row per attempted
                                                       lookup; includes
                                                       resolved/empty/no-match
                                                       outcomes so coverage
                                                       can be computed)
  analysis/corpus_production/raw/s2_refs/             (raw payloads)
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import s2_get, CORPUS_DIR, now_iso, S2_API_KEY
from context_windows import s2_snippet_fields

CENSUS_CSV = CORPUS_DIR / "citing_census.csv"
OUT_CONTEXTS = CORPUS_DIR / "contexts_s2.csv"
OUT_ATTEMPTED = CORPUS_DIR / "contexts_s2_attempted.csv"

DECADES_DEFAULT = os.environ.get("CORPUS_S2_DECADES", "2010s,2020s")
N_PER_DEFAULT = int(os.environ.get("CORPUS_S2_N_PER", "200"))
RNG_SEED = int(os.environ.get("CORPUS_S2_SEED", "20260624"))
CHECKPOINT_EVERY = int(os.environ.get("CORPUS_S2_CHECKPOINT", "50"))

REFS_FIELDS = ("contexts,intents,isInfluential,"
               "citedPaper.paperId,citedPaper.title,citedPaper.year,"
               "citedPaper.authors,citedPaper.externalIds")

# Canonical / known-reprint identifiers per active seed, used to match the
# seed reference inside each citing paper's S2 references list. Captured
# from seed_resolution.csv + seed_alt_editions_detail.json (Steps 1).
SEED_MATCH = {
    "meadows_1972_limits_to_growth": {
        "title_re": re.compile(r"limits\s*to\s*growth", re.IGNORECASE),
        "author_re": re.compile(r"\bmeadows\b", re.IGNORECASE),
        "year_window": (1972, 2025),  # editions span 1972..2018+ in S2 records
        "canonical_dois": {"10.1349/ddlp.1",
                            "10.9774/gleaf.978-1-907643-44-6_8",
                            "10.4324/9780429493744-3"},
        "canonical_mags": {"2079238586", "225706379", "2487267993", "3145345180"},
        "canonical_corpus_ids": {131868204, 156978832, 155565742, 145613959, 270281048},
    },
    "commoner_1971_closing_circle": {
        "title_re": re.compile(r"closing\s*circle", re.IGNORECASE),
        "author_re": re.compile(r"\bcommoner\b", re.IGNORECASE),
        "year_window": (1971, 2025),
        "canonical_dois": set(),
        "canonical_mags": {"2799049480", "2014540969", "569826341"},
        "canonical_corpus_ids": set(),
    },
    "schumacher_1974_small_is_beautiful": {
        "title_re": re.compile(r"small\s*is\s*beautiful", re.IGNORECASE),
        "author_re": re.compile(r"\bschumacher\b", re.IGNORECASE),
        "year_window": (1973, 2025),
        "canonical_dois": set(),
        "canonical_mags": {"2054104432"},
        "canonical_corpus_ids": set(),
    },
}


def is_seed_reference(ref: dict, seed_id: str) -> tuple[bool, str | None]:
    spec = SEED_MATCH[seed_id]
    cited = (ref or {}).get("citedPaper") or {}
    ext = cited.get("externalIds") or {}
    if (ext.get("DOI") or "").lower() in spec["canonical_dois"]:
        return True, "doi"
    if str(ext.get("MAG") or "") in spec["canonical_mags"]:
        return True, "mag"
    cid = ext.get("CorpusId")
    if cid and (cid in spec["canonical_corpus_ids"] or
                str(cid) in {str(c) for c in spec["canonical_corpus_ids"]}):
        return True, "corpusid"
    title = cited.get("title") or ""
    if spec["title_re"].search(title):
        name_blob = " ".join((a.get("name") or "") for a in (cited.get("authors") or []))
        if spec["author_re"].search(name_blob):
            return True, "title_plus_author"
        y0, y1 = spec["year_window"]
        if cited.get("year") and y0 <= cited["year"] <= y1:
            return True, "title_plus_year_window"
    return False, None


def stratified_sample(citing_rows: list[dict], n_per: int,
                       decades: list[str]) -> list[dict]:
    rng = random.Random(RNG_SEED)
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in citing_rows:
        if r["citing_decade"] not in decades:
            continue
        # Need at least DOI or MAG to look up in S2
        if not r["citing_doi"] and not r["citing_mag"]:
            continue
        by_key[(r["seed_id"], r["citing_decade"])].append(r)
    out = []
    for (seed_id, decade), pool in sorted(by_key.items()):
        rng.shuffle(pool)
        chosen = pool[:n_per]
        for r in chosen:
            r["_stratum"] = f"{seed_id}__{decade}"
        out.extend(chosen)
    return out


def write_checkpoint(contexts_rows: list[dict],
                      attempted_rows: list[dict],
                      contexts_fields: list[str],
                      attempted_fields: list[str]) -> None:
    if contexts_rows:
        with OUT_CONTEXTS.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=contexts_fields, lineterminator="\n")
            w.writeheader()
            for r in contexts_rows:
                w.writerow({k: r.get(k, "") for k in contexts_fields})
    with OUT_ATTEMPTED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=attempted_fields, lineterminator="\n")
        w.writeheader()
        for r in attempted_rows:
            w.writerow({k: r.get(k, "") for k in attempted_fields})


def main() -> None:
    if not CENSUS_CSV.exists():
        raise SystemExit("Run 02_citing_census.py first.")
    decades = [d.strip() for d in DECADES_DEFAULT.split(",") if d.strip()]
    n_per = N_PER_DEFAULT

    print(f"[{now_iso()}] Step 3a — S2 Graph API context extraction")
    print(f"  decades sampled: {decades}")
    print(f"  N per (seed x decade): {n_per}")
    print(f"  S2 auth: {'API key present' if S2_API_KEY else 'PUBLIC anon rate limit (slow)'}")
    print(f"  Checkpoint every {CHECKPOINT_EVERY} items\n")

    with CENSUS_CSV.open() as f:
        citing_rows = list(csv.DictReader(f))
    print(f"  loaded {len(citing_rows)} (seed, citing) pairs from census")

    sample = stratified_sample(citing_rows, n_per=n_per, decades=decades)
    print(f"  sample size: {len(sample)}\n")

    contexts_fields = [
        "seed_id", "citing_openalex_id", "citing_doi", "citing_year",
        "citing_decade", "citing_type", "match_reason",
        "ref_paperId", "ref_title", "ref_year", "ref_externalIds",
        "n_contexts", "context_index", "sentence_before", "citing_sentence",
        "sentence_after", "context_text", "context_window_complete",
        "context_sentence_count", "context_window_status", "intents", "is_influential",
        "s2_lookup_path", "retrieval_route", "retrieved_at_utc",
    ]
    attempted_fields = [
        "seed_id", "citing_openalex_id", "citing_doi", "citing_mag",
        "citing_year", "citing_decade", "citing_type",
        "lookup_id", "lookup_path",
        "s2_status",  # resolved_with_refs | resolved_empty_refs | unresolved
        "n_refs_in_s2", "seed_ref_found", "n_contexts_for_seed_ref",
        "retrieved_at_utc",
    ]

    contexts_rows: list[dict] = []
    attempted_rows: list[dict] = []

    for i, r in enumerate(sample, 1):
        seed_id = r["seed_id"]
        doi = (r["citing_doi"] or "").replace("https://doi.org/", "").replace("http://doi.org/", "")
        mag = r["citing_mag"] or ""
        wid = r["citing_openalex_id"].split("/")[-1]
        s2_body = None
        lookup_id = None
        lookup_path = None
        lookup_cascade = []
        if doi:
            lookup_cascade.append((f"DOI:{doi}", "doi"))
        if mag:
            lookup_cascade.append((f"MAG:{mag}", "mag"))
        for ident, path in lookup_cascade:
            try:
                s2_body = s2_get(
                    f"paper/{ident}/references",
                    params={"fields": REFS_FIELDS, "limit": 1000},
                    save_as=f"refs_{seed_id}_{wid}",
                    subdir="s2_refs",
                )
                lookup_id, lookup_path = ident, path
                break
            except Exception as e:
                # record failure path; continue trying other id
                continue
        retrieved_at = now_iso()
        if s2_body is None:
            attempted_rows.append({
                "seed_id": seed_id, "citing_openalex_id": r["citing_openalex_id"],
                "citing_doi": doi, "citing_mag": mag,
                "citing_year": r["citing_year"], "citing_decade": r["citing_decade"],
                "citing_type": r["citing_type"],
                "lookup_id": "", "lookup_path": "",
                "s2_status": "unresolved", "n_refs_in_s2": 0,
                "seed_ref_found": False, "n_contexts_for_seed_ref": 0,
                "retrieved_at_utc": retrieved_at,
            })
        else:
            refs = s2_body.get("data") or []
            matched = None
            match_reason = None
            for ref in refs:
                ok, reason = is_seed_reference(ref, seed_id)
                if ok:
                    matched = ref
                    match_reason = reason
                    break
            n_ref_ctx = len(matched.get("contexts") or []) if matched else 0
            status = ("resolved_empty_refs" if not refs
                       else "resolved_no_seed_match" if not matched
                       else "resolved_with_seed_ref")
            attempted_rows.append({
                "seed_id": seed_id, "citing_openalex_id": r["citing_openalex_id"],
                "citing_doi": doi, "citing_mag": mag,
                "citing_year": r["citing_year"], "citing_decade": r["citing_decade"],
                "citing_type": r["citing_type"],
                "lookup_id": lookup_id, "lookup_path": lookup_path,
                "s2_status": status, "n_refs_in_s2": len(refs),
                "seed_ref_found": bool(matched),
                "n_contexts_for_seed_ref": n_ref_ctx,
                "retrieved_at_utc": retrieved_at,
            })
            if matched and n_ref_ctx > 0:
                cited = matched.get("citedPaper") or {}
                ext = cited.get("externalIds") or {}
                base_row = {
                    "seed_id": seed_id,
                    "citing_openalex_id": r["citing_openalex_id"],
                    "citing_doi": doi,
                    "citing_year": r["citing_year"],
                    "citing_decade": r["citing_decade"],
                    "citing_type": r["citing_type"],
                    "match_reason": match_reason,
                    "ref_paperId": cited.get("paperId") or "",
                    "ref_title": (cited.get("title") or "")[:200],
                    "ref_year": cited.get("year") or "",
                    "ref_externalIds": json.dumps(ext, ensure_ascii=False),
                    "n_contexts": n_ref_ctx,
                    "intents": json.dumps(matched.get("intents") or []),
                    "is_influential": bool(matched.get("isInfluential")),
                    "s2_lookup_path": lookup_path,
                    "retrieval_route": "s2_graph_api_references",
                    "retrieved_at_utc": retrieved_at,
                }
                for j, ctx in enumerate(matched.get("contexts") or []):
                    row = dict(base_row)
                    row["context_index"] = j
                    row.update(s2_snippet_fields(ctx or ""))
                    contexts_rows.append(row)

        if i % CHECKPOINT_EVERY == 0:
            n_resolved = sum(1 for x in attempted_rows if x["s2_status"].startswith("resolved"))
            n_with_seed = sum(1 for x in attempted_rows if x["seed_ref_found"])
            print(f"  [{i}/{len(sample)}] resolved={n_resolved} "
                  f"with_seed_ref={n_with_seed} contexts_rows={len(contexts_rows)}")
            write_checkpoint(contexts_rows, attempted_rows,
                             contexts_fields, attempted_fields)

    write_checkpoint(contexts_rows, attempted_rows,
                     contexts_fields, attempted_fields)
    print(f"\nwrote {OUT_CONTEXTS} ({len(contexts_rows)} context rows)")
    print(f"wrote {OUT_ATTEMPTED} ({len(attempted_rows)} attempt rows)")
    print(f"finished_at={now_iso()}")


if __name__ == "__main__":
    main()
