# Three-seed comparative reception corpus — build report

**Status:** production corpus v1.1; citation-window correction and OA retrieval
extension complete; human pilot prepared.
**Base retrieval:** 2026-06-24 UTC. **OA extension:** 2026-09-01 UTC.
**Not completed:** human labels, adjudication, main annotation, or Paper B
experiments.

## Seed panel and citing census

OpenAlex citing works were unioned across canonical and alternate-edition IDs.

| Seed | Unique citing works |
|---|---:|
| Meadows et al. 1972 — *The Limits to Growth* | 10,478 |
| Commoner 1971 — *The Closing Circle* | 1,116 |
| Schumacher 1973/1974 — *Small Is Beautiful* | 1,460 |
| **Total seed/citing-work pairs** | **13,054** |

Goldsmith 1972 remains a resolved reserve seed and is not included in the
active corpus.

## Context sources

No LLM produced, expanded, or classified context text.

### Semantic Scholar route

The citing-paper census came from OpenAlex. For a stratified sample of OpenAlex
citing works, the pipeline looked up each citing paper by DOI or MAG in the
Semantic Scholar Graph API, requested its reference list, matched the seed
reference, and copied the reference-level `contexts`, `intents`, and
`isInfluential` fields.

The 78 returned `contexts` strings are S2 pre-computed snippets. They are not
assumed to be three sentences and are marked
`s2_precomputed_context_unverified`. An S2-only row is not annotation-eligible.

### OA full-text route

The OA route sampled up to 30 works per seed/decade stratum. Thin pre-2000
strata produced an actual sample of 424 works. Of these, 295 documents were
fetched and 129 failed or remained inaccessible. Cached documents from the
base build were reused; uncached rows were retrieved on 2026-09-01.

The extractor detected 327 occurrences in 126 citing works. For each occurrence
it records the sentence containing the seed marker and the immediately
preceding/following sentences.

## Explicit annotation unit

An annotation-eligible row must have all three non-empty fields:

1. `sentence_before`
2. `citing_sentence`
3. `sentence_after`

It must also pass source-quality rules. The pipeline excludes incomplete
document-edge windows, likely bibliography-only entries, network/anti-bot
boilerplate, S2-only unverified snippets, and seed-title phrases without nearby
seed attribution.

## Current counts

| Measure | Count |
|---|---:|
| S2 source rows | 78 |
| OA source rows | 327 |
| Combined deduplicated rows | 399 |
| Combined citing works yielding any source row | 179 |
| Complete, attributable, non-bibliography contexts | 87 |
| Citing works contributing eligible contexts | 69 |

Quality outcomes for the 327 OA rows:

| Non-exclusive quality outcome | Rows |
|---|---:|
| No quality flag | 92 |
| Likely bibliography-only flag | 209 |
| Unattributed seed-title phrase flag | 21 |
| Citing sentence missing seed attribution flag | 139 |

Three unflagged OA rows are incomplete document-edge windows, leaving 89 OA
rows marked eligible before cross-route deduplication and 87 combined rows.

## Pilot

The sampler uses every eligible combined context because the quality-gated pool
contains 87 rows. The resulting pilot is 48 Meadows, 17 Commoner, and 22
Schumacher contexts. This pilot tests the codebook and reliability process; it
is not a balanced comparative prevalence sample.

Both annotator sheets contain the same 87 items in different deterministic
orders. All label fields are blank. No real reliability or adjudication output
exists until the human sheets return.

## Reproduction

```sh
CORPUS_OA_N_PER=30 CORPUS_OA_CACHE_PREFERRED=1 \
  .venv/bin/python3 scripts/corpus/04_extract_oa_pdf_contexts.py
.venv/bin/python3 scripts/corpus/09_migrate_context_schema.py
.venv/bin/python3 scripts/corpus/05_dedup_combine.py
.venv/bin/python3 scripts/annotation/01_sample.py
.venv/bin/python3 scripts/annotation/02_make_sheets.py
```

For a network-free OA rebuild, replace `CORPUS_OA_CACHE_PREFERRED=1` with
`CORPUS_OA_CACHE_ONLY=1`.

## Limitations and next gate

- OA availability and successful parsing remain biased toward recent,
  article-based, and born-digital literature.
- The sentence splitter is deterministic and tested but cannot repair all OCR
  or layout damage.
- The eligible pool is seed-imbalanced, especially for Commoner.
- Automated bibliography and attribution flags are conservative screening
  rules and should be audited during pilot adjudication.
- The next valid project action is independent human pilot annotation—not LLM
  labeling or Paper B experimentation.
