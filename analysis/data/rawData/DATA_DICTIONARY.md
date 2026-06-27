# Raw-data dictionary and corpus-size lineage

Scope: documents (1) the five Web of Science `savedrecs*.xls` exports under this
directory and the harmonized columns derived from them downstream, and (2) the
explicit filter chain that turns 4,610 raw records into the various corpus and
subset sizes that appear in Paper 1.

Companion machine-readable provenance: [`config/data_provenance.yml`](../../../config/data_provenance.yml).

---

## 1. Source exports

Five "Save to Excel — full record" exports from Web of Science (Clarivate),
Microsoft Excel binary `.xls` (CDFV2 OLE compound document).
Per-file record counts confirmed from the `source_file` column of
[`analysis/data/interim/metadata_raw.csv`](../interim/metadata_raw.csv).

| File | Records | File-system mtime | Notes |
|---|---:|---|---|
| `savedrecs.xls`   | 1000 | 2025-04-12 09:58:21 PDT | xls metadata: Last Saved By "Chism, Greg Thomas (gchism)" on Microsoft Macintosh Excel. |
| `savedrecs_1.xls` | 1000 | 2025-04-11 14:51:58 PDT | |
| `savedrecs_2.xls` | 1000 | 2025-04-11 14:52:23 PDT | |
| `savedrecs_3.xls` |  998 | 2025-04-11 14:52:40 PDT | |
| `savedrecs_4.xls` |  612 | 2025-04-11 14:53:15 PDT | |
| **Total**         | **4,610** | snapshot range 11–12 April 2025 | matches Methods §2.1; matches `analysis/tables/pipeline_counts.csv` `harmonized_records`. |

The four `_1`–`_4` files were saved in a 77-second window on 2025-04-11; the
fifth (`savedrecs.xls`, no suffix) on 2025-04-12. Both dates are author-attested
by embedded xls metadata.

WoS query string, indexes/editions, timespan, and search date are author-supply
fields tracked in `config/data_provenance.yml` and listed in
`analysis/results/author_supply_checklist.md`. They are intentionally not
populated here.

---

## 2. Harmonized columns (81 fields)

After ingest by
[`scripts/pipeline/01_ingest_raw_metadata.R`](../../../scripts/pipeline/01_ingest_raw_metadata.R),
the five exports are concatenated into
[`analysis/data/interim/metadata_raw.csv`](../interim/metadata_raw.csv) with 81
columns preserving the original WoS field tags plus two ingest-trace fields
(`source_file`, `source_path`). The harmonization step in
[`scripts/R/metadata_utils.R`](../../../scripts/R/metadata_utils.R) then writes
[`analysis/data/processed/works_harmonized.csv`](../processed/works_harmonized.csv)
with 20 normalized columns retained for downstream use.

| Column | Source | Definition |
|---|---|---|
| `source_row` | derived | Row index within the original .xls export. |
| `source_file` | trace | One of `savedrecs.xls` … `savedrecs_4.xls`. |
| `source_record_id` | derived | WoS UT/accession ID (when available). |
| `doi` | WoS `DI` | Cleaned/normalized DOI. |
| `title` | WoS `TI` | Article/book title. |
| `authors` | WoS `AU` | Semicolon-separated author list. |
| `year` | WoS `PY` | Publication year. |
| `venue` | WoS `SO` | Source title (journal, book). |
| `document_type` | WoS `DT` | Document type. |
| `abstract` | WoS `AB` | Abstract text. |
| `keywords` | WoS `DE` + `ID` | Author + indexed keywords. |
| `addresses` | WoS `C1` | Author addresses. |
| `cited_references` | WoS `CR` | **Empty in these exports** — see note below. |
| `database` | WoS `UT` prefix | Source database (Web of Science / Clarivate). |
| `title_norm` | derived | Lower-cased title for fuzzy matching. |
| `authors_norm` | derived | Normalized author block for fuzzy matching. |
| `doi_safe` | derived | DOI stripped to canonical form for exact matching. |
| `work_key` | derived | Stable identifier used downstream (often DOI-based). |
| `duplicate_group` | derived | Cluster ID assigned in dedup pass. |
| `is_duplicate` | derived | TRUE for non-canonical members of a duplicate cluster. |

Note on `cited_references`: not populated in these exports (the "Save to Excel"
option used did not include the CR field). The manuscript Methods §2.1 records
this and consequently makes no co-citation or bibliographic-coupling claims.

---

## 3. Corpus-size lineage: 4,610 → 43

Every transition below is an explicit, scripted filter (or partition). Counts
are reproduced from the committed CSVs at audit time (2026-06-21).

```
                                              4,610 raw records (5 WoS exports)
                                                |
                                                |  filter F1:
                                                |    harmonization + exact-DOI dedup
                                                |    + within-year fuzzy-title dedup
                                                |    (scripts/pipeline/01–03; uses
                                                |     scripts/R/canonical_works.R)
                                                |    drops 73 duplicates
                                                v
                                              4,537 canonical works
                                                |
                                                |  filter F2:
                                                |    retain only works whose citation
                                                |    of Meadows et al. (1972) yields a
                                                |    citation context (one row per
                                                |    context_group_id; multiple mentions
                                                |    per work are retained as separate
                                                |    rows; scripts/pipeline/04–05)
                                                |    drops 2,947 works without a usable
                                                |    extracted Meadows context;
                                                |    adds back per-mention rows
                                                v
                                              1,590 deployed contextual rows
                                              (analysis/data/final/
                                                meadows_context_classification.csv;
                                                analysis/data/final/
                                                contextual_corpus_final.csv)
                                                |
                                                |  partition P1 by evidence_level:
                                                |
                            +-------------------+-------------------+
                            |                                       |
                            v                                       v
                  1,395 Level 1                            195 Levels 2–5
                  traditional bibliometric                 contextual evidence
                  evidence only                            (Level 2: 65 human-reviewed
                  (evidence_level ==                       Level 3: 36 validated router
                   "Level 1: …";                           Level 4: 24 hybrid accepted
                   matches                                 Level 5: 70 unresolved)
                   analysis/data/processed/                = 65 + 36 + 24 + 70 = 195
                   citation_contexts.csv
                   row count 1,395)
                                                                    |
                                                                    |  filter F3:
                                                                    |    usable_for_substantive_analysis == TRUE
                                                                    |    (workflow flag set during
                                                                    |     classification; gates which
                                                                    |     records may support
                                                                    |     substantive claims)
                                                                    v
                                                          95 usable-for-substantive
                                                          rows
                                                                    |
                                                                    |  filter F4:
                                                                    |    additional substantive-context
                                                                    |    selection retained for Paper 2
                                                                    |    (analysis/data/final/
                                                                    |     substantive_contexts.csv;
                                                                    |     selection criteria reviewed
                                                                    |     for that paper)
                                                                    v
                                                          43 rows in
                                                          substantive_contexts.csv
```

### Filter and partition counts at a glance

| Step | Count | Filter / partition | Authoritative file |
|---|---:|---|---|
| Raw | 4,610 | 5 WoS exports (1000 + 1000 + 1000 + 998 + 612) | `analysis/data/interim/metadata_raw.csv` |
| F1: dedup | 4,537 | exact-DOI + within-year fuzzy-title (drops 73) | `analysis/data/processed/canonical_works.csv` |
| F2: contextual extraction | 1,590 | one row per citation mention of Meadows (1972) | `analysis/data/final/meadows_context_classification.csv` |
| P1a: Level 1 | 1,395 | `evidence_level == "Level 1: traditional bibliometric evidence"` | `analysis/data/processed/citation_contexts.csv` (also `meadows_context_classification.csv` filtered to Level 1) |
| P1b: Levels 2–5 | 195 | Level 2 + 3 + 4 + 5 (65 + 36 + 24 + 70) | filter of `meadows_context_classification.csv` |
| F3: usable | 95 | `usable_for_substantive_analysis == TRUE` | filter of `meadows_context_classification.csv` |
| F4: Paper-2 selection | 43 | manual substantive-context selection for Paper 2 | `analysis/data/final/substantive_contexts.csv` |

The review-burden partition (949 substantive review / 641 audit review / 0
no-review) is a separate, orthogonal partition of the 1,590 corpus; it is
derived in
[`scripts/pipeline/59_reconcile_partitions.R`](../../../scripts/pipeline/59_reconcile_partitions.R)
and written to
[`analysis/results/review_burden_partition.csv`](../../results/review_burden_partition.csv).
The 949 > 870 tension that prompted that script is documented in its decomposition
rows (substantive = 870 needs-review + 65 already-reviewed-only + 14 unresolved-only).
