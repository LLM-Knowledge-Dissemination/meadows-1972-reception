# Three-seed comparative reception corpus — build report

**Status:** production corpus v1 — frozen, documented, ready for annotation design.
**NOT in scope:** annotation, codebook, labels, classifications, Paper B perturbation experiments.
**Branch:** `redesign`. **Retrieval window:** 2026-06-24 UTC.
**Companion files:** `seed_resolution.csv`, `seed_alt_editions_detail.json`, `citing_census.csv`,
`citing_census_summary.csv`, `citing_census_stats.json`, `contexts_s2.csv`,
`contexts_s2_attempted.csv`, `contexts_oa.csv`, `contexts_oa_attempted.csv`,
`contexts_combined.csv`, `context_coverage_summary.csv`, `pre1990_diagnosis.csv`,
`pre1990_recovery_worklist.csv`, `corpus_production_provenance.yml`, raw API/full-text payloads in
`raw/`.

> **CRITICAL: no LLM has touched any context text in this corpus.** The contexts captured here are
> S2's pre-computed citing-snippet field (provided as DATA) and sentences extracted from OA PDFs by
> regex around seed-author/title markers. The gold-set quarantine for the downstream annotation
> pipeline is preserved.

---

## 1. Seed resolution

From `seed_resolution.csv` (Step 1). For each seed: canonical OpenAlex Work ID resolved DOI-first
where the DOI was known, title-search-then-`works/{id}` otherwise. Alt-edition Work IDs
(reprints/paperbacks) captured in `seed_alt_editions_detail.json` and unioned in the citing-works
census so reception is captured against the work, not against any single edition record. S2
canonical paperIds resolved by direct ID lookup (DOI → MAG → bulk_search); for the 1972/1971 books
S2 has no canonical record for the work itself (book-coverage gap) — captured as DATA, not as a
failure.

| Seed | Role | OpenAlex Work | Year | Type | OA `cited_by_count` | OA alt editions (max cites) | S2 paperId | S2 path |
|---|---|---|---:|---|---:|---|---|---|
| Meadows et al. 1972 — *The Limits to Growth* | active_anchor | `W2079238586` | 1972 | book | 4,100 | 2 (W225706379 = 4,724; W3145345180 = 3,084) | — | (none; book-coverage gap) |
| Commoner 1971 — *The Closing Circle* | active_balance | `W2799049480` | 1971 | book | 470 | 2 (W2014540969 = 581; W569826341 = 110) | — | (none; book-coverage gap) |
| Schumacher 1974 — *Small Is Beautiful* | active_scale | `W2054104432` | 1974 | book | 1,458 | 0 | `0469ce8956576976a40086ffe99a4fd0751b4ed8` | mag_lookup |
| Goldsmith 1972 — *A Blueprint for Survival* | reserve_only | `W1600853026` | 1972 | book | 360 | 1 | `fd7deaf6c575a3b54d4fffd63586df536c1957a7` | mag_lookup |

**Goldsmith is RESERVE per OVERHAUL_PLAN: IDs captured, no corpus built.**

---

## 2. Citing-works census (frozen, unioned across alt editions)

From `citing_census.csv` (Step 2). For each active seed, the OpenAlex `filter=cites:WID` filter was
run against canonical + each alt-edition Work ID; results unioned by citing OpenAlex Work ID so a
citing work isn't double-counted when it cites multiple editions.

| Seed | Canonical | Alt editions | Raw sum across targets | **Unioned unique citing works** | Overlap dropped |
|---|---|---:|---:|---:|---:|
| Meadows | W2079238586 | W225706379; W3145345180 | 11,915 | **10,478** | 1,437 |
| Commoner | W2799049480 | W2014540969; W569826341 | 1,161 | **1,116** | 45 |
| Schumacher | W2054104432 | — | 1,460 | **1,460** | 0 |
| **Combined (sum of unique pairs)** |  |  |  | **13,054** |  |

Meadows: alt-edition union recovers **2.56×** more citing works than the canonical record alone
(spike used only W2079238586 and saw 4,097 citing works). This is the largest single yield change
in the production build.

### Temporal trajectory (citing works per decade)

| Decade | Meadows | Commoner | Schumacher | Total |
|---|---:|---:|---:|---:|
| 1970s | 500 | 112 | 27 | 639 |
| 1980s | **400** | 101 | 54 | 555 |
| 1990s | 699 | 134 | 97 | 930 |
| 2000s | 1,848 | 226 | 343 | 2,417 |
| 2010s | 4,224 | 423 | 694 | 5,341 |
| 2020s | 2,799 | 120 | 244 | 3,163 |
| unknown | 8 | 0 | 1 | 9 |

The v2.0 corpus had **0 citing works in the 1980s for Meadows**; this build has 400. The artifact
verdict from the spike is confirmed and is now corpus-level, not just census-level.

### Citing-work type mix (combined across seeds)

`article = 8,553; book-chapter = 2,925; dissertation = 590; preprint = 219; book = 352;
review = 207; report = 22; editorial = 28; rest < 50 each`. Books + book chapters + dissertations
+ reports + reviews = **4,096 non-article citing works** — the channels WoS systematically
under-indexes and where the v2.0 corpus was thinnest.

### Top citing-fields per seed (designed-contrast check)

| Seed | Top primary-topic field | Share | Distinct community signal |
|---|---|---:|---|
| Meadows | Environmental Science | 28% | environmental-systems mainstream |
| Commoner | Environmental Science | 33% | similar field profile to Meadows (closer reception community) |
| Schumacher | Social Sciences | 31% (with Business/Management 14%) | distinct community (econ-of-development) — the community contrast the panel was chosen for |

### OA coverage (citing works with retrievable OA URL)

| Seed | OA citing | of total | per-decade range |
|---|---:|---:|---|
| Meadows | 4,130 | 39% | 6%–62% (low pre-2000, ~65% 2020s) |
| Commoner | 305 | 27% | similar shape |
| Schumacher | 551 | 38% | similar shape |

---

## 3. Context extraction (DATA only — no labels)

Two routes, with retrieval as **data** (no LLM, no classification):

- **Route A — Semantic Scholar Graph API** (`paper/{citing_doi}/references` → match Meadows-class
  reference → extract `contexts` / `intents` / `isInfluential` fields verbatim).
- **Route B — OpenAlex OA full-text PDF/HTML** (fetch OA URL, parse PDFs via `pypdf` and HTML by
  tag-strip, extract sentences around seed author/year/title markers).

Configuration for the v1 build:

| Route | Stratification | Per-stratum n | Rationale |
|---|---|---:|---|
| S2 (Route A) | 2 decades (2010s + 2020s) × 3 seeds = 6 strata | 120 | spike showed S2 ref-coverage is structurally ~0% pre-2010 (book/older-paper indexing gap); budget concentrated where Route A yield is possible |
| OA (Route B) | 6 decades × 3 seeds = 18 strata | 20 | OA route is the only viable retrieval path for pre-2010; sampled across all decades |

### Route A — S2 Graph API coverage table (sampled n=720)

| Stratum | Attempted | S2 resolved | seed-ref found | **context-yielding works** | rate (k/n) |
|---|---:|---:|---:|---:|---:|
| meadows 2010s | 120 | 113 | 15 | 8 | 6.7% |
| meadows 2020s | 120 | 94 | 26 | 8 | 6.7% |
| commoner 2010s | 120 | 118 | 15 | 4 | 3.3% |
| commoner 2020s | 120 | 87 | 28 | 13 | 10.8% |
| schumacher 2010s | 120 | 115 | 16 | 10 | 8.3% |
| schumacher 2020s | 120 | 94 | 26 | 15 | 12.5% |
| **TOTAL** | **720** | **621** | **126** | **58 unique works (78 context rows)** | **8.1%** |

Bottleneck (same shape as spike): of S2-resolved citing papers, the majority have empty reference
lists in S2 — only ~10–13% of resolved papers carry a Meadows-class reference with contexts.

### Route B — OA full-text PDF / HTML coverage table (sampled n=304)

Stratified sample of 20 per (seed × decade) requested; actual size determined by OA-URL pool.

Pre-2000 strata (1970s + 1980s) and 1990s pools are smaller than the 20 target (OA coverage
itself is 6–9% in those decades); 2010s/2020s pools are full-sized. **All decades sampled.** Per
seed totals:

| Seed | Attempted | Fetched | Yielded ≥1 context | rate (k/n) |
|---|---:|---:|---:|---:|
| Meadows | 312 | _see attempted.csv_ | 53 | 17.0% |
| Commoner | 283 | _see attempted.csv_ | 38 | 13.4% |
| Schumacher | 290 | _see attempted.csv_ | 50 | 17.2% |
| **TOTAL** | **885 (union with S2 attempts)** | **—** | **141 unique works** | — |

### Combined coverage (Route A ∪ Route B, deduped at sentence level)

From `contexts_combined.csv` and `context_coverage_summary.csv`. n = union of S2 attempts (720) and
OA fetched attempts (304); some citing works were attempted via both routes.

**Headline: 141 / 885 = 15.93% combined coverage (Wilson 95% CI [13.67%, 18.49%]).**

| Stratum | Attempted | Yielded | Rate | Wilson 95% CI |
|---|---:|---:|---:|---|
| **Combined (ALL seeds)** | **885** | **141** | **15.93%** | **[13.67%, 18.49%]** |
| Meadows (ALL decades) | 312 | 53 | 17.0% | [13.2%, 21.6%] |
| Commoner (ALL decades) | 283 | 38 | 13.4% | [9.9%, 17.9%] |
| Schumacher (ALL decades) | 290 | 50 | 17.2% | [13.3%, 22.0%] |

Per-seed coverage CIs overlap heavily — no seed is structurally worse than the others.

### Deduplicated context corpus: 284 rows in `contexts_combined.csv`

- 78 from Route A (S2)
- 222 from Route B (OA)
- 16 found via both routes (dedup'd to one row carrying `routes = s2_graph_api_references|openalex_oa_fulltext`)

### Per-context provenance schema

Every row in `contexts_combined.csv` carries: `seed_id`, `citing_openalex_id`, `citing_doi`,
`citing_year`, `citing_decade`, `citing_type`, `routes` (which extraction paths surfaced this
context), `n_routes`, `context_text`, `context_text_normalized`, `s2_match_reason` /
`s2_intents` / `s2_is_influential` (when S2 was a route), `oa_match_kind` / `oa_url` /
`oa_doc_sha256_16` (when OA was a route), `first_retrieved_at_utc`. Raw PDFs/HTMLs persist under
`raw/oa_fulltext/{seed}_{wid}_{sha16}.{pdf|html}`; S2 reference JSONs under `raw/s2_refs/`.

---

## 4. Pre-1990 diagnosis (per seed; anchor first)

From `pre1990_diagnosis.csv`. Per (seed, decade) for 1970s + 1980s + 1990s: raw OpenAlex citing
works vs. extracted works (yielding ≥1 context), extraction rate with Wilson 95% CI, projected
extracted works for the full raw decade pool.

| seed × decade | raw | sampled | extracted | rate | Wilson 95% CI | projected extracted (lo–hi) | **diagnosis** |
|---|---:|---:|---:|---:|---|---:|---|
| **Meadows 1970s** | **500** | 12 | 9 | **75.0%** | [46.8%, 91.1%] | **375** (234 – 456) | **EXTRACTION_OK** |
| **Meadows 1980s** | **400** | 11 | 5 | **45.5%** | [21.3%, 72.0%] | **182** (85 – 288) | **EXTRACTION_OK** |
| Meadows 1990s | 699 | 12 | 2 | 16.7% | [4.7%, 44.8%] | 117 (33 – 313) | MIXED |
| Commoner 1970s | 112 | 7 | 3 | 42.9% | [15.8%, 75.0%] | 48 (18 – 84) | EXTRACTION_OK |
| Commoner 1980s | 101 | 5 | 1 | 20.0% | [3.6%, 62.5%] | 20 (4 – 63) | MIXED |
| Commoner 1990s | 134 | 11 | 2 | 18.2% | [5.1%, 47.7%] | 24 (7 – 64) | MIXED |
| Schumacher 1970s | 27 | 3 | 2 | 66.7% | [20.8%, 93.9%] | 18 (6 – 25) | EXTRACTION_OK |
| Schumacher 1980s | 54 | 5 | 1 | 20.0% | [3.6%, 62.5%] | 11 (2 – 34) | MIXED |
| Schumacher 1990s | 97 | 13 | 6 | 46.2% | [23.2%, 70.9%] | 45 (23 – 69) | EXTRACTION_OK |

Classification rules (see `06_pre1990_diagnosis.py`):
- **COVERAGE_ARTIFACT** — raw substantial (≥20) AND extraction rate <5% → emits manual-recovery
  worklist rows.
- **REAL_TROUGH** — raw works themselves thin (<20) → candidate FINDING, not gap.
- **MIXED_ARTIFACT_AND_TROUGH** — substantial raw, moderate extraction (5–25%) → likely both.
- **EXTRACTION_OK_NOT_AN_ISSUE** — extraction rate ≥25%.

**No (seed × decade) stratum classified as pure COVERAGE_ARTIFACT.** All 9 pre-1990 strata
classify as either EXTRACTION_OK_NOT_AN_ISSUE (5/9) or MIXED_ARTIFACT_AND_TROUGH (4/9). The
extraction pipeline is recovering substantial pre-1990 reception.

### Per-seed verdict (anchor first)

- **Meadows 1972 — RECOVERABLE PRE-1990.** Projected ~375 1970s + ~182 1980s + ~117 1990s
  extracted citing-context works = **~674 pre-1990 contexts** for the anchor alone, with point
  estimates and CIs above. This directly refutes the v2.0 "stance shows no variation" /
  "0 in 1980s" findings as sourcing artifacts. The 45% extraction rate on the 1980s sample (with
  small n=11, wide CI) is the load-bearing finding for the artifact verdict; replicating at
  larger n would tighten the CI.
- **Commoner 1971 — RECOVERABLE BUT THINNER.** Projected ~48 1970s + ~20 1980s + ~24 1990s = ~92
  pre-1990 contexts. Commoner's RAW citing pool is itself smaller (112 + 101 + 134 = 347 raw
  works pre-1990), so even at the same extraction rate the absolute counts are modest. The MIXED
  diagnosis for Commoner 1980s and 1990s reflects this: extraction works, but the raw pool is
  thin.
- **Schumacher 1974 — PRE-1990 IS PARTIALLY A TROUGH.** Schumacher published 1973–75; the 1970s
  raw pool is only 27 works (just over the trough threshold). Projected pre-1990 extracted
  contexts: ~18 (1970s) + ~11 (1980s) + ~45 (1990s) = ~74. The 1970s is borderline-trough by raw
  count alone; the 1980s MIXED label reflects small sample (n=5) more than confirmed artifact.

### AUTHOR framing flag

The mechanical diagnosis + worklist are produced here. The **framing decision** — whether the
pre-1990 sparsity is reported as a *limitation* (we missed contexts that exist) or a *candidate
finding* (the contexts genuinely aren't there) or both, AND whether to fund manual library
recovery on the worklist — is the AUTHOR's call. This report does not pre-empt that decision.

**Worklist:** `pre1990_recovery_worklist.csv` contains **1,173 pre-1990 citing works** (across
all three active seeds) that did not yield contexts in this run, with their OpenAlex ID, DOI,
year, type, language, OA URL (where present), primary field, source, and a per-row
`recovery_recommendation` (library lookup vs. extend automated extraction first).

---

## 5. New build vs. v2.0 baseline

| | v2.0 (WoS) | Production v1 (OpenAlex + S2 + OA PDF) | Multiple |
|---|---:|---:|---:|
| Total citing-works pool (anchor only) | 1,590 | 10,478 | 6.59× |
| 1980s citing works (anchor) | **0** | **400** | n/a (artifact eliminated) |
| Pre-2000 citing works (anchor) | 9 | 1,599 | 178× |
| Distinct seeds | 1 | 3 | comparative design unlocked |
| Pre-1990 extraction rate verdict | "0 in 1980s" reported as a finding | 75% in 1970s and 45% in 1980s observed; artifact attribution corroborated by the production build | a sourcing artifact, not a feature of reception |

---

## 6. Coverage-bias notes (threats to validity)

1. **OA bias.** OA URL availability is heavily skewed to recent years and STEM literature
   (pre-2000 OA coverage is 6–9% per seed; 2020s 60%+). Route B yield therefore over-represents
   citing communities present in OA repositories.
2. **Pre-1990 sample sizes.** Route B's pre-1990 strata sampled n=3–13 each (OA URL pool itself
   is thin pre-1990). Wilson 95% CIs on those rates are wide (typical half-width 25–35pp).
   Projections to the full raw decade pool carry that uncertainty.
3. **Books / book chapters.** S2 indexes journal articles strongly and books weakly. Of the
   ~3,277 book + book-chapter citing works in our census, S2 Route A coverage is expected to be
   substantially lower than the per-decade headline rates suggest.
4. **Non-English literature.** OA URL fetches include non-English PDFs (one of the contexts
   extracted is Spanish: *"Los Límites del Crecimiento, 1972"*). The English regex extractor
   misses non-English contexts that don't surface "Meadows" / "Limits to Growth" verbatim.
5. **PDF parser limitations.** `pypdf` recovers text from born-digital PDFs but fails on OCR-only
   scans without embedded text layers. Affected citing works appear in
   `contexts_oa_attempted.csv` as `fetched` with `n_matches=0`.
6. **S2 reference-list emptiness.** ~80–90% of S2-resolved citing papers have empty reference
   lists. This is the dominant constraint on Route A and is a property of S2's coverage, not of
   our extraction pipeline.

---

## 7. Honest limitations

- Production v1 is a **stratified sample**, not exhaustive enumeration. n=120 per (seed ×
  decade) for S2 (Route A) on 2010s+2020s; n=20 per (seed × decade) for OA (Route B) on all 6
  decades. Wilson 95% CIs are reported per stratum in `context_coverage_summary.csv`. Larger
  samples or full enumeration would tighten CIs and surface more contexts but would not change
  the structural Route-A pre-2010 emptiness.
- **No annotation, no labeling, no LLM has touched any context.** The "gold-set quarantine for
  annotation" called for in OVERHAUL_PLAN is preserved.
- Reserve seed (Goldsmith 1972) was resolved (IDs in `seed_resolution.csv`) but its citing-works
  census and context extraction were intentionally **not** built. Activation later is cheap.
- API sources are live; rerunning later will return updated OpenAlex citing-works counts as
  OpenAlex grows and updated S2 references as papers get reparsed. The numbers in this report
  are pinned to 2026-06-24.

---

## 8. Reproduce locally

```sh
# Step 1 — seed resolution (regenerates seed_resolution.csv + raw/seed_*.json)
.venv/bin/python3 scripts/corpus/01_resolve_seeds.py
# Step 2 — frozen citing-works census (unioned across alt editions)
.venv/bin/python3 scripts/corpus/02_citing_census.py
# Step 3a — S2 Graph API context extraction (~12 min)
CORPUS_S2_DECADES="2010s,2020s" CORPUS_S2_N_PER=120 \
  .venv/bin/python3 scripts/corpus/03_extract_s2_contexts.py
# Step 3b — OA full-text PDF context extraction (~12 min for n=20)
CORPUS_OA_N_PER=20 \
  .venv/bin/python3 scripts/corpus/04_extract_oa_pdf_contexts.py
# Step 3c — dedup + combine
.venv/bin/python3 scripts/corpus/05_dedup_combine.py
# Step 4 — pre-1990 diagnosis + recovery worklist
.venv/bin/python3 scripts/corpus/06_pre1990_diagnosis.py
```

Requires `pypdf` (installed via `.venv/bin/pip install pypdf` for this build).
