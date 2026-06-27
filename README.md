# Meadows 1972 Bibliometrics

This repository studies how Meadows, Meadows, Randers, and Behrens' 1972 *The Limits to Growth* circulated, was cited, interpreted, and disseminated across scholarly and public knowledge networks over time.

## Project Status: Two-Paper Redesign (June 2026)

The project is in a **two-paper redesign** that supersedes the prior "Paper 1 nearing completion" plan. The current roadmap, target venues, gated sequence, and what is superseded vs. surviving are in [`docs/OVERHAUL_PLAN.md`](docs/OVERHAUL_PLAN.md). Start there.

The v2.0 line is checkpointed and not under active development:

- Tag `v2.0-paper1-freeze` — the v2.0 release-assembly state of the Paper 1 manuscript and frozen methodology package.
- Tag `v2.1-pre-overhaul` — the in-flight review work on top of v2.0 (decision-rule audit, Wilson-CI tooling, reconciliation/anti-drift scripts) captured immediately before this redesign began. Lives on branch `pre-overhaul-snapshot`.
- Branch `redesign` — current line of work; uses surviving infrastructure from v2.1 (see the OVERHAUL_PLAN's "surviving infrastructure" section).

Superseded v2.0-stage materials have been moved under [`archive/`](archive/) for historical reference and are not required to reproduce the current analysis.

The frozen v2.0 methodology package at `analysis/frozen_methodology/v2_0/` is read-only and is not modified by the redesign.

The project uses a staged reproducible pipeline. Older scripts in `src/` are preserved as legacy/reference work; new work uses `config/`, `scripts/R/`, and `scripts/pipeline/`.

## Current Audit

The existing project already contains valuable harvested material: bibliographic exports in `analysis/data/rawData/`, open PDFs in `analysis/data/pdf/`, extracted PDF text in `analysis/data/pdf_text/`, per-document citation hits in `analysis/data/pdf_hits/`, HathiTrust/NTRL-related files, derived hit tables, and validation samples.

The weakest parts of the previous structure were methodological rather than substantive:

- scripts mixed setup, API calls, parsing, analysis, and one-off inspection code;
- paths were hard-coded rather than configured;
- some scripts installed packages during execution;
- `src/parse_hathi_pdfs.R` reset generated outputs when run, making sourcing risky;
- validation depended on an in-memory object instead of a declared input file;
- DOI/title deduplication, citation-context classification, and network construction were not cleanly separated.

## Useful Patterns Adapted from `simonizer-public`

The Simonizer project provides a useful architectural model: a `config/` directory for conventions and paths, helper functions for project-root discovery, numbered pipeline scripts, reusable libraries separated from executable stages, human validation outputs, and explicit panel/network export stages.

This repo adapts those patterns without copying Simonizer's topic-specific agent-belief workflow. The Meadows project needs bibliographic ingestion, citation-context extraction, bibliometric networks, diffusion summaries, schema-based LLM interpretation, validation samples, audit trails, and Quarto reporting.

## Pipeline

Run individual stages:

```sh
Rscript scripts/pipeline/00_setup.R
Rscript scripts/pipeline/01_ingest_raw_metadata.R
Rscript scripts/pipeline/02_harmonize_and_deduplicate.R
Rscript scripts/pipeline/04_consolidate_contexts.R
Rscript scripts/pipeline/05_build_networks_and_diffusion.R
Rscript scripts/pipeline/06_make_tables_and_figures.R
```

Or use Make:

```sh
make metadata
make contexts
make networks
make figures
```

Optional schema-based LLM classification:

```sh
make llm
```

By default this writes a no-cost rule-fallback classification table and audit trail. To call an OpenAI-compatible client, set:

```sh
MEADOWS_ENABLE_LLM=true MEADOWS_LLM_LIMIT=25 python3 scripts/pipeline/07_classify_contexts_llm.py
```

Build the human validation sample:

```sh
make validation
```

`03_extract_citation_contexts.R` parses PDFs and can be expensive. For a smoke test:

```sh
MEADOWS_LIMIT_PDFS=5 Rscript scripts/pipeline/03_extract_citation_contexts.R
```

To overwrite existing per-PDF hit files:

```sh
MEADOWS_OVERWRITE_HITS=true Rscript scripts/pipeline/03_extract_citation_contexts.R
```

## Implemented Outputs

- `analysis/data/interim/metadata_raw.csv`
- `analysis/data/processed/works_harmonized.csv`
- `analysis/data/processed/canonical_works.csv`
- `analysis/data/processed/canonical_works_enriched.csv`
- `analysis/data/processed/duplicate_clusters.csv`
- `analysis/data/processed/ambiguous_duplicate_matches.csv`
- `analysis/data/processed/citation_contexts_enriched.csv`
- `analysis/data/processed/works_potential_duplicates.csv`
- `analysis/data/processed/citation_contexts.csv`
- `analysis/data/derived/reference_edges.csv`
- `analysis/data/derived/cocitation_edges.csv`
- `analysis/data/derived/bibliographic_coupling.csv`
- `analysis/data/derived/meadows_1972_seed_edges.csv`
- `analysis/data/derived/diffusion_by_year_venue_type.csv`
- `analysis/data/derived/topic_clusters_works.csv`
- `analysis/data/derived/topic_clusters_contexts.csv`
- `analysis/data/llm_input/citation_contexts_for_classification.csv`
- `analysis/data/llm_output/citation_context_classifications.csv`
- `analysis/audit/llm_classification_audit.jsonl`
- `analysis/validation/citation_context_validation_sample.csv`
- `analysis/validation/citation_context_codebook.md`
- `analysis/tables/pipeline_counts.csv`
- `analysis/tables/citation_context_functions.csv`
- `analysis/tables/llm_context_classifications.csv`
- `analysis/tables/network_summary.csv`
- `analysis/tables/yearly_citation_growth.csv`
- `analysis/tables/top_venues.csv`
- `analysis/tables/citation_roles_over_time.csv`
- `analysis/figures/citing_works_by_year.png`, when year matches are available
- `analysis/data_inventory.csv`

## Methodological Scope

The core design treats Meadows et al. 1972 as the seed work and builds a citing-work corpus around it. The implemented workflow supports:

- raw data ingestion;
- metadata harmonization;
- canonical work construction with DOI and fuzzy title/author/year deduplication;
- offline/cache-safe external reconciliation scaffolding for OpenAlex and Crossref;
- citation-context extraction from available PDF text;
- enriched context typing, including body-text, bibliography-only, ambiguous, and false-positive risk flags;
- seed-citation edge construction;
- cited-reference edge extraction where source records include references;
- bibliographic coupling;
- diffusion summaries by year, venue, document type, and database;
- schema-constrained LLM citation-context interpretation with audit trails;
- stratified human validation sampling;
- lightweight local topic clustering for titles/abstracts and citation-context windows;
- reproducible table and figure generation;
- Quarto methodology documentation.

The citation-context taxonomy includes foundational citation, critique, historical framing, modeling/simulation reference, sustainability/limits-to-growth discourse, policy/governance framing, methodological comparison, bibliography-only, and background/ambiguous use. Rule-based labels prioritize recall and transparency. Schema-based LLM labels improve interpretive accuracy, but publishable claims should use human-validated labels or report validation error rates.

## Quarto Report

The methodology file is:

```sh
reports/methodology.qmd
```

Render with:

```sh
quarto render reports/methodology.qmd --output-dir ../analysis/reports
```

## Data Limitations

Coverage bias, missing full text, OCR quality, DOI gaps, language coverage, and field-specific citation practices are central limitations. Bibliography-only references and body-text discussions should be analyzed separately because they imply different kinds of circulation and interpretation.
