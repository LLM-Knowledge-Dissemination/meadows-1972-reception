# Data catalog

This catalog identifies the authoritative artifacts. Files not listed here are
legacy, intermediate, or supporting material.

| Stage | Authoritative path | Contents | Public status |
|---|---|---|---|
| Seed resolution | `analysis/corpus_production/seed_resolution.csv` | Canonical and alternate seed IDs | Public |
| Citing census | `analysis/corpus_production/citing_census.csv` | One row per seed/citing-work pair | Public |
| S2 attempts | `analysis/corpus_production/contexts_s2_attempted.csv` | Lookup outcomes without source text | Public |
| S2 contexts | `analysis/corpus_production/contexts_s2.csv` | Source-derived S2 snippets | Restricted |
| OA attempts | `analysis/corpus_production/contexts_oa_attempted.csv` | Fetch outcomes, URLs, and hashes | Public/review |
| OA contexts | `analysis/corpus_production/contexts_oa.csv` | Explicit windows and quality fields | Restricted |
| Combined contexts | `analysis/corpus_production/contexts_combined.csv` | Deduplicated annotation-source corpus | Restricted |
| Pilot sample | `analysis/annotation/pilot_sample.csv` | 87 eligible items with context text | Restricted |
| Pilot key | `analysis/annotation/item_key.csv` | Item IDs and provenance without context text | Public after rights review |
| Annotator sheets | `analysis/annotation/sheets/` | Blank or returned human sheets | Restricted during pilot |
| Synthetic fixtures | `analysis/annotation/fixtures/` | Test-only fake annotation data | Public |
| Reliability output | `analysis/annotation/reliability_report.md` | Real pilot reliability; not created yet | Public after pilot |
| Disagreements | `analysis/annotation/disagreements.csv` | Real pilot review queue; not created yet | Restricted during adjudication |

## Annotation fields

Every candidate context carries `sentence_before`, `citing_sentence`,
`sentence_after`, `context_text`, `context_window_complete`,
`context_sentence_count`, `context_window_status`, `context_quality_flags`, and
`annotation_eligible`.

The annotator-visible `work_type` is the citing work's OpenAlex publication
type, such as `article`, `book-chapter`, `dissertation`, or `preprint`.
