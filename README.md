# Meadows 1972 Bibliometrics

This repository builds a comparative citation-reception corpus around three
early limits-to-growth books: Meadows et al. (1972), Commoner (1971), and
Schumacher (1973/1974).

## Current status

The current redesign has completed the citing-work census, two-route context
retrieval, explicit three-sentence context reconstruction, quality screening,
and a blank 87-item human pilot package. Human annotation, adjudication, the
main annotation round, and Paper B experiments have not begun.

Start with:

- [`STATUS.md`](STATUS.md) — completed work, current gates, and next actions.
- [`DATA_CATALOG.md`](DATA_CATALOG.md) — authoritative data locations and
  public/restricted status.
- [`analysis/corpus_production/BUILD_REPORT.md`](analysis/corpus_production/BUILD_REPORT.md)
  — current corpus counts and provenance.
- [`analysis/corpus_production/CONTEXT_WINDOW_QA.md`](analysis/corpus_production/CONTEXT_WINDOW_QA.md)
  — citation-window contract and quality exclusions.
- [`docs/annotation/PILOT_CODEBOOK.md`](docs/annotation/PILOT_CODEBOOK.md) —
  instructions for the human pilot.

## Citation-context contract

An annotation-eligible context contains exactly:

1. the sentence immediately before the citation;
2. the sentence containing the seed citation; and
3. the sentence immediately after the citation.

OA full text is used to reconstruct these fields locally. Semantic Scholar
Graph API `contexts` values are retained as source evidence but marked
`s2_precomputed_context_unverified`; they are not annotation-eligible unless a
locally reconstructed OA window is also available.

Reference-list entries, incomplete document-edge windows, network/anti-bot
boilerplate, and title phrases without seed attribution are excluded from the
pilot through explicit quality fields.

## Reproduction

Create the environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The numbered corpus scripts are authoritative:

```sh
.venv/bin/python3 scripts/corpus/01_resolve_seeds.py
.venv/bin/python3 scripts/corpus/02_citing_census.py
.venv/bin/python3 scripts/corpus/03_extract_s2_contexts.py
CORPUS_OA_N_PER=30 .venv/bin/python3 scripts/corpus/04_extract_oa_pdf_contexts.py
.venv/bin/python3 scripts/corpus/05_dedup_combine.py
.venv/bin/python3 scripts/annotation/01_sample.py
.venv/bin/python3 scripts/annotation/02_make_sheets.py
```

To reconstruct OA windows only from already cached source documents:

```sh
CORPUS_OA_N_PER=30 CORPUS_OA_CACHE_ONLY=1 \
  .venv/bin/python3 scripts/corpus/04_extract_oa_pdf_contexts.py
```

Run the method tests with `make tests`.

## Data boundaries

The development repository contains restricted source-derived context text.
The public export contains identifiers, hashes, scripts, aggregate results,
the codebook, and synthetic fixtures; it does not redistribute S2 snippets or
OA full-text passages. See
[`docs/reproducibility/data_redistribution_note.md`](docs/reproducibility/data_redistribution_note.md).
