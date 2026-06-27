#!/usr/bin/env python3
"""Step 1 — resolve all four seeds (3 active + Goldsmith reserve) to:
  - canonical OpenAlex Work ID (DOI lookup first; title-search last resort)
  - Semantic Scholar paperId via direct ID lookup (DOI -> MAG -> bulk-search;
    record which path worked, and explicitly note seeds for which S2 has no
    canonical record — books from the 1970s typically aren't indexed)
  - all known reprint/edition Work IDs from OpenAlex (so citing works aren't
    split across records during the cited_by census)

Outputs:
  analysis/corpus_production/seed_resolution.csv  (one row per seed)
  analysis/corpus_production/raw/seed_*.json      (raw API payloads)

This step makes no inference and writes no labels. The reserve seed
(Goldsmith) is resolved + recorded; its citing-set census is intentionally
NOT run.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import (
    openalex_get, s2_get, CORPUS_DIR, now_iso, OPENALEX_EMAIL, S2_API_KEY,
)

OUT_CSV = CORPUS_DIR / "seed_resolution.csv"

# Pre-vetted candidate seeds. DOIs are recorded where the spike confirmed
# them; for the others DOI is missing because the OpenAlex canonical record
# carries no DOI (book records from the 1970s often don't). Title/author/year
# windows are tight to avoid review-record false positives.
SEEDS = [
    {
        "seed_id":          "meadows_1972_limits_to_growth",
        "role":             "active_anchor",
        "canonical_title":  "The Limits to Growth",
        "author_required":  "Meadows",
        "year_window":      (1972, 1972),
        "known_doi":        "10.1349/ddlp.1",
        "spike_openalex_id": "W2079238586",
        "notes":            "Anchor seed; v2.0 primary; spike-confirmed canonical book record.",
    },
    {
        "seed_id":          "commoner_1971_closing_circle",
        "role":             "active_balance",
        "canonical_title":  "The Closing Circle",
        "author_required":  "Commoner",
        "year_window":      (1971, 1972),
        "known_doi":        None,
        "spike_openalex_id": "W2799049480",
        "notes":            "Selected for best pre-2000 decade balance (80/66/85 in 1970s/80s/90s).",
    },
    {
        "seed_id":          "schumacher_1974_small_is_beautiful",
        "role":             "active_scale",
        "canonical_title":  "Small is Beautiful",
        "author_required":  "Schumacher",
        "year_window":      (1973, 1975),
        "known_doi":        None,
        "spike_openalex_id": "W2054104432",
        "notes":            "Selected for highest raw citing count (1,460) + 38% OA coverage.",
    },
    {
        "seed_id":          "goldsmith_1972_blueprint_for_survival",
        "role":             "reserve_only",
        "canonical_title":  "A Blueprint for Survival",
        "author_required":  "Goldsmith",
        "year_window":      (1972, 1973),
        "known_doi":        None,
        "spike_openalex_id": "W1600853026",
        "notes":            "Reserve seed: resolve IDs only; do NOT build its corpus in this pass.",
    },
]


def title_match(t: str | None, canonical: str) -> bool:
    if not t:
        return False
    # title contains all words of canonical (case-insensitive)
    parts = [p for p in re.split(r"\s+", canonical.lower()) if len(p) > 2]
    low = t.lower()
    return all(p in low for p in parts)


def has_author(authorships: list[dict] | None, required: str) -> bool:
    blob = " ".join((a.get("author") or {}).get("display_name") or ""
                    for a in (authorships or []))
    return required.lower() in blob.lower()


def s2_has_author(authors: list[dict] | None, required: str) -> bool:
    blob = " ".join(a.get("name") or "" for a in (authors or []))
    return required.lower() in blob.lower()


def resolve_openalex(seed: dict) -> dict:
    """DOI-first; title-search fallback. Records the path used."""
    canonical: dict | None = None
    method = None
    runners_up: list[dict] = []
    # 1) DOI route (preferred)
    if seed["known_doi"]:
        try:
            body = openalex_get(
                f"works/doi:{seed['known_doi']}",
                save_as=f"seed_openalex_doi_{seed['seed_id']}",
            )
            if body and body.get("id"):
                canonical = body
                method = "doi_lookup"
        except Exception as e:
            method = f"doi_lookup_failed: {str(e)[:120]}"
    # 2) Title-search fallback
    if canonical is None:
        y0, y1 = seed["year_window"]
        body = openalex_get(
            "works",
            params={
                "filter": (f"publication_year:{y0}-{y1},"
                           f"title.search:{seed['canonical_title']}"),
                "per-page": 25,
                "select": "id,doi,ids,title,display_name,publication_year,type,"
                          "cited_by_count,authorships,primary_topic",
            },
            save_as=f"seed_openalex_titlesearch_{seed['seed_id']}",
        )
        cands = body.get("results") or []
        qualified = [w for w in cands
                     if title_match(w.get("display_name") or w.get("title"),
                                     seed["canonical_title"])
                     and has_author(w.get("authorships"), seed["author_required"])
                     and y0 <= (w.get("publication_year") or 0) <= y1]
        qualified.sort(key=lambda w: w.get("cited_by_count") or 0, reverse=True)
        if qualified:
            top = qualified[0]
            short_id = (top.get("id") or "").split("/")[-1]
            # Pull full canonical record for completeness
            canonical = openalex_get(
                f"works/{short_id}",
                save_as=f"seed_openalex_canonical_{seed['seed_id']}",
            )
            method = (method or "") + (";" if method else "") + "title_search_then_get"
            runners_up = [
                {"id": q.get("id"),
                 "cited_by_count": q.get("cited_by_count"),
                 "title": (q.get("display_name") or q.get("title") or "")[:80]}
                for q in qualified[1:5]
            ]
    return {"openalex_canonical": canonical, "openalex_method": method,
            "openalex_runners_up": runners_up}


def find_oa_alt_editions(seed: dict, canonical_oa: dict) -> list[dict]:
    """Find sibling OpenAlex Work IDs for known reprints/editions so the
    cited_by census can union them later. We retain them as DATA only — the
    Step-2 census uses one filter per active seed, so this list is recorded
    in seed_resolution.csv for traceability and future use."""
    y0, y1 = seed["year_window"]
    # Broaden the year window for reprint detection (+/- 60 years to catch
    # later editions like the 2007 Greenleaf reprint, 2018 Routledge, etc.)
    rep_y0, rep_y1 = max(1900, y0 - 5), 2025
    body = openalex_get(
        "works",
        params={
            "filter": (f"publication_year:{rep_y0}-{rep_y1},"
                       f"title.search:{seed['canonical_title']}"),
            "per-page": 100,
            "select": "id,doi,ids,title,display_name,publication_year,type,"
                      "cited_by_count,authorships",
        },
        save_as=f"seed_openalex_editions_{seed['seed_id']}",
    )
    canonical_id = (canonical_oa or {}).get("id")
    out = []
    for w in (body.get("results") or []):
        if (w.get("id") or "") == canonical_id:
            continue
        if not title_match(w.get("display_name") or w.get("title"),
                           seed["canonical_title"]):
            continue
        if not has_author(w.get("authorships"), seed["author_required"]):
            continue
        out.append({
            "id": w.get("id"),
            "year": w.get("publication_year"),
            "type": w.get("type"),
            "cited_by_count": w.get("cited_by_count"),
            "doi": w.get("doi"),
            "title": (w.get("display_name") or w.get("title") or "")[:80],
        })
    out.sort(key=lambda e: e.get("cited_by_count") or 0, reverse=True)
    return out[:15]


def resolve_s2(seed: dict, oa_canonical: dict | None) -> dict:
    """S2 resolution: DOI → MAG → bulk_search. Returns dict; records the
    resolution_path (or 'not_in_s2_index_book').

    NOTE: MAG (Microsoft Academic Graph) IDs are usually absent on post-2021
    records because MAG was discontinued; the OpenAlex canonical record may
    still carry a legacy MAG id, but S2 frequently maps a given MAG to a
    different (often-reprint) paper. Bulk_search is the real fallback.
    """
    record: list[dict] = []
    primary = None
    path = None
    # Helper to keep matching consistent
    def s2_qualifies(p: dict) -> bool:
        if not p:
            return False
        y0, y1 = seed["year_window"]
        return (title_match(p.get("title"), seed["canonical_title"])
                and s2_has_author(p.get("authors"), seed["author_required"])
                and (y0 <= (p.get("year") or 0) <= y1))

    fields = ("paperId,title,year,authors,externalIds,citationCount,"
              "referenceCount,influentialCitationCount,publicationTypes,"
              "publicationVenue,corpusId")
    # Pull doi/mag from OA canonical (if it has them)
    doi = ((oa_canonical or {}).get("doi") or "").replace("https://doi.org/", "")
    mag = ((oa_canonical or {}).get("ids") or {}).get("mag")
    # 1) DOI direct lookup
    if doi:
        attempt = {"strategy": "doi_lookup", "id": f"DOI:{doi}"}
        try:
            body = s2_get(f"paper/DOI:{doi}", params={"fields": fields},
                          save_as=f"seed_s2_doi_{seed['seed_id']}")
            attempt["result_paperId"] = body.get("paperId")
            attempt["qualifies"] = s2_qualifies(body)
            if s2_qualifies(body):
                primary = body
                path = "doi_lookup"
        except Exception as e:
            attempt["error"] = str(e)[:200]
        record.append(attempt)
    # 2) MAG direct lookup
    if primary is None and mag:
        attempt = {"strategy": "mag_lookup", "id": f"MAG:{mag}"}
        try:
            body = s2_get(f"paper/MAG:{mag}", params={"fields": fields},
                          save_as=f"seed_s2_mag_{seed['seed_id']}")
            attempt["result_paperId"] = body.get("paperId")
            attempt["qualifies"] = s2_qualifies(body)
            if s2_qualifies(body):
                primary = body
                path = "mag_lookup"
            else:
                attempt["note"] = ("MAG-resolved record exists but does not "
                                    "qualify as the canonical seed — likely a "
                                    "reprint/chapter; recorded but not used.")
        except Exception as e:
            attempt["error"] = str(e)[:200]
        record.append(attempt)
    # 3) Bulk search fallback
    if primary is None:
        try:
            body = s2_get("paper/search/bulk",
                          params={"query": (seed["canonical_title"] + " "
                                            + seed["author_required"]),
                                  "fields": fields,
                                  "sort": "citationCount:desc"},
                          save_as=f"seed_s2_bulk_{seed['seed_id']}")
            record.append({"strategy": "bulk_search",
                           "total": body.get("total"),
                           "returned": len(body.get("data") or [])})
            for cand in (body.get("data") or []):
                if s2_qualifies(cand):
                    primary = cand
                    path = "bulk_search"
                    break
        except Exception as e:
            record.append({"strategy": "bulk_search", "error": str(e)[:200]})
    return {"s2_resolution_attempts": record,
            "s2_primary": primary,
            "s2_resolution_path": path,
            "s2_has_canonical_record": bool(primary)}


_editions_detail: dict[str, list[dict]] = {}


def main() -> None:
    print(f"[{now_iso()}] resolving {len(SEEDS)} seeds (3 active + 1 reserve)")
    print(f"  OpenAlex polite pool mailto: {OPENALEX_EMAIL}")
    print(f"  S2: {'API key present' if S2_API_KEY else 'PUBLIC anon rate limit'}\n")

    out_rows = []
    for seed in SEEDS:
        print(f"-- {seed['seed_id']} ({seed['role']}) --")
        oa = resolve_openalex(seed)
        oa_can = oa.get("openalex_canonical") or {}
        if oa_can.get("id"):
            print(f"   OpenAlex: {oa_can.get('id')}  type={oa_can.get('type')}  "
                  f"year={oa_can.get('publication_year')}  "
                  f"cited_by={oa_can.get('cited_by_count')}  "
                  f"method={oa.get('openalex_method')}")
        else:
            print(f"   OpenAlex: NO MATCH  method={oa.get('openalex_method')}")

        editions = find_oa_alt_editions(seed, oa_can) if oa_can else []
        _editions_detail[seed["seed_id"]] = editions
        if editions:
            top_eds = ", ".join(f"{e['id'].split('/')[-1]}({e.get('year')}, "
                                f"cites={e.get('cited_by_count')})"
                                for e in editions[:3])
            print(f"   OA alt editions: {len(editions)} found "
                  f"({top_eds}{'...' if len(editions)>3 else ''})")

        s2 = resolve_s2(seed, oa_can)
        if s2["s2_has_canonical_record"]:
            sp = s2["s2_primary"]
            print(f"   S2: {sp.get('paperId')}  year={sp.get('year')}  "
                  f"path={s2['s2_resolution_path']}")
        else:
            print(f"   S2: NO canonical record found "
                  f"(strategies tried: {len(s2['s2_resolution_attempts'])})")

        out_rows.append({
            "seed_id": seed["seed_id"],
            "role": seed["role"],
            "canonical_title": seed["canonical_title"],
            "author_required": seed["author_required"],
            "year_window": f"{seed['year_window'][0]}-{seed['year_window'][1]}",
            "known_doi_input": seed["known_doi"] or "",
            "spike_openalex_id_input": seed["spike_openalex_id"],
            "openalex_id": oa_can.get("id") or "",
            "openalex_doi": oa_can.get("doi") or "",
            "openalex_mag": (oa_can.get("ids") or {}).get("mag") or "",
            "openalex_year": oa_can.get("publication_year") or "",
            "openalex_type": oa_can.get("type") or "",
            "openalex_cited_by_count": oa_can.get("cited_by_count") or "",
            "openalex_display_name": (oa_can.get("display_name") or "")[:200],
            "openalex_method": oa.get("openalex_method") or "",
            "openalex_alt_edition_ids": ";".join(e["id"].split("/")[-1] for e in editions),
            "openalex_alt_edition_count": len(editions),
            "openalex_alt_edition_max_cited_by": (max((e.get("cited_by_count") or 0) for e in editions) if editions else 0),
            "s2_paperId": (s2.get("s2_primary") or {}).get("paperId") or "",
            "s2_year": (s2.get("s2_primary") or {}).get("year") or "",
            "s2_resolution_path": s2.get("s2_resolution_path") or "",
            "s2_has_canonical_record": s2.get("s2_has_canonical_record"),
            "s2_note": ("S2 has no canonical record for the book itself "
                        "(book-coverage gap)") if not s2["s2_has_canonical_record"] else "",
            "build_action": ("build_corpus" if seed["role"].startswith("active")
                              else "reserve_no_corpus_build"),
            "notes": seed["notes"],
        })

    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    print(f"\nwrote {OUT_CSV}")
    # Persist the full per-seed editions detail alongside the CSV summary so
    # downstream steps (Step 2 census union) can use them without re-querying.
    editions_full = CORPUS_DIR / "seed_alt_editions_detail.json"
    editions_full.write_text(json.dumps(_editions_detail, indent=2, ensure_ascii=False))
    print(f"wrote {editions_full}")
    print(f"finished_at={now_iso()}")


if __name__ == "__main__":
    main()
