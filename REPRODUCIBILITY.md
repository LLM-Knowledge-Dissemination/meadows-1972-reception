# Reproducibility model

This is the **public reproducibility scaffold** for the Limits to Growth
reception study. It ships:

- **Corpus IDs and hashes** — every citing-work in the census is identified by
  its OpenAlex ID + DOI (when known). For OA full-text contexts, the
  per-document SHA-256 (first 16 hex chars) is recorded so re-fetched bytes
  can be verified.
- **Extraction scripts** — the numbered scripts in `scripts/corpus/` are the
  canonical retrieval and context-window pipeline. They
  call OpenAlex (CC0) and Semantic Scholar with a documented polite-pool
  user-agent (`gchism@arizona.edu`) and write raw responses + provenance
  sidecars.
- **Annotation protocol** — the pre-pilot codebook is in
  `docs/annotation/PILOT_CODEBOOK.md`; sampler and reliability tooling are
  under `scripts/annotation/` and `scripts/R/krippendorff.R`. Synthetic test
  fixtures live in `analysis/annotation/fixtures/`.
- **Summary tables and provenance** — the corpus census, coverage summaries,
  yield projections, OA-honest projections, and provenance YAMLs are included
  verbatim.

## What is NOT shipped, and why

Raw citation-context **text** (sentences extracted from OA full text, S2
context snippets, and WoS-licensed records)
is **not** redistributed here. Re-fetching the source bytes with the included
scripts and the published IDs + hashes reconstructs the contexts under the
re-fetcher's own access rights. Human annotation has not started, so no gold
labels are claimed or shipped in v0.2.

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
3. Follow `README.md` and `analysis/corpus_production/BUILD_REPORT.md`.
4. Run `make tests` to verify the sentence-window and R method helpers.
