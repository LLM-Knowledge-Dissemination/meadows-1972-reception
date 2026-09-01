# Project status

**Updated:** 2026-09-01
**Active branch:** `redesign`
**Stage:** human pilot prepared; annotation not started

## Completed

- Three-seed OpenAlex citing-work census: 13,054 unique seed/citing-work pairs.
- S2 Graph API context capture: 78 pre-computed snippets, all explicitly marked
  as unverified three-sentence windows.
- OA retrieval extension: 424 sampled works, 295 fetched, 129 failed.
- OA extraction: 327 detected occurrences from 126 citing works.
- Combined source corpus: 399 deduplicated rows from 179 citing works.
- Quality gate: 87 complete, attributable, non-bibliography three-sentence
  contexts from 69 citing works.
- Blank 87-item pilot sheets for two independently shuffled annotators.
- Reliability, disagreement, and adjudication tooling with synthetic fixtures.

## Pilot composition

The quality gate exhausts the eligible pool, so the pilot is not seed-balanced:

| Seed | Pilot contexts |
|---|---:|
| Meadows et al. | 48 |
| Commoner | 17 |
| Schumacher | 22 |
| **Total** | **87** |

This is acceptable for codebook and reliability testing. It must not be used
to estimate comparative prevalence across seeds.

## Current gates

1. Two human annotators independently label all 87 pilot items.
2. Run `scripts/annotation/03_reliability.R` and review every disagreement and
   flagged item.
3. Adjudicate, revise the codebook, and run a second pilot if any axis has
   Krippendorff's alpha below 0.667.
4. Before a main comparative annotation round, recover additional Commoner and
   Schumacher contexts or use design/analysis weights appropriate to the final
   sampling frame.
5. Paper B perturbation experiments remain gated on a frozen human gold set.

## Publication state

The public repository is a reproducibility scaffold. It does not yet contain
human labels or an adjudicated gold set. A local v0.2 export should be verified
before any remote update.
