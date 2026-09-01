# Annotation data

This directory is the single entry point for the human pilot.

| Path | Purpose | Current state |
|---|---|---|
| `pilot_sample.csv` | Internal 87-item sample with context text and provenance | Ready; restricted |
| `item_key.csv` | Stable item IDs and provenance without context text | Ready |
| `sampling_manifest.csv` | Seed/band pool and realized counts | Ready |
| `sheets/annotator_A.csv` | Blank independently shuffled sheet | Ready; restricted |
| `sheets/annotator_B.csv` | Blank independently shuffled sheet | Ready; restricted |
| `annotation_provenance.yml` | Parameters, hashes, and gate status | Ready |
| `fixtures/` | Synthetic reliability-test data | Public; not real annotation |
| `reliability_report.md` | Real pilot reliability output | Not created |
| `disagreements.csv` | Real pilot review/adjudication queue | Not created |

Annotators must read `docs/annotation/PILOT_CODEBOOK.md`. They must not consult
LLM output or internal provenance fields while labeling.
