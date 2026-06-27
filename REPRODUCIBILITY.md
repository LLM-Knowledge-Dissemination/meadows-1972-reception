# Reproducibility model

This is the **public reproducibility scaffold** for the Limits to Growth
reception study. It ships:

- **Corpus IDs and hashes** — every citing-work in the census is identified by
  its OpenAlex ID + DOI (when known). For OA full-text contexts, the
  per-document SHA-256 (first 16 hex chars) is recorded so re-fetched bytes
  can be verified.
- **Extraction scripts** — `scripts/corpus/01_resolve_seeds.py` through
  `04_extract_oa_pdf_contexts.py` are the canonical retrieval pipeline. They
  call OpenAlex (CC0) and Semantic Scholar with a documented polite-pool
  user-agent (`gchism@arizona.edu`) and write raw responses + provenance
  sidecars.
- **Annotation protocol** — the pilot codebook is in
  `docs/annotation/PILOT_CODEBOOK.md`; sampler and reliability tooling are
  under `scripts/annotation/` and `scripts/R/krippendorff.R`. Synthetic test
  fixtures live in `analysis/annotation/fixtures/`.
- **Summary tables and provenance** — the corpus census, coverage summaries,
  yield projections, OA-honest projections, and provenance YAMLs are included
  verbatim.

## What is NOT shipped, and why

Raw citation-context **text** (sentences extracted from OA full text, S2
context paragraphs, anti-bot challenge boilerplate, and WoS-licensed records)
is **not** redistributed here. Re-fetching the source bytes with the included
scripts and the published IDs + hashes reconstructs the contexts under the
re-fetcher's own access rights. The annotation gold *labels* (function /
stance / depth) ship keyed to context IDs, separated from the text.

The superseded v2.0 OpenAI classifier (prompts, schemas, audit logs) is not
included here; the methodological successor and its full prompting protocol
are disclosed in the manuscript and its supplementary materials.

## Layout

| Directory                            | Contents                                       |
|--------------------------------------|------------------------------------------------|
| `scripts/corpus/`                    | OpenAlex / S2 retrieval pipeline (01–05)       |
| `scripts/annotation/`                | Sampler + sheet generator + reliability runner |
| `scripts/R/`                         | Reliability + validation-interval helpers      |
| `scripts/pipeline/`                  | Pipeline driver scripts                        |
| `analysis/corpus_production/`        | Census, summaries, projections, raw sidecars   |
| `analysis/annotation/fixtures/`      | Synthetic test fixtures (NOT real annotation)  |
| `analysis/results/`                  | Validation interval + reconciliation tables    |
| `config/`                            | Paths, seed metadata, provenance               |
| `docs/`                              | Codebook + data-redistribution note            |
| `tests/`                             | Test suite                                     |

## Reproducing the analysis

1. `pip install -r requirements.txt`
2. Export `OPENALEX_EMAIL=gchism@arizona.edu` (or your own polite-pool address).
3. Run `python scripts/corpus/01_resolve_seeds.py` through `05_dedup_combine.py`.
4. `Rscript scripts/pipeline/13_run_tests.R` to verify the R helpers.
