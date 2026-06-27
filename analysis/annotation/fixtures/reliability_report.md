# Pilot reliability report

**Paired items (both annotators returned the sheet for the same item):** 12
**Items with at least one disagreement on function / stance / depth:** 4  (see `disagreements.csv`)
**Bootstrap iterations:** 1000; **seed:** 20260625

**Thresholds** (from `docs/annotation/PILOT_CODEBOOK.md` §10):
- >= 0.80 → firm
- 0.667–0.80 → tentative
- < 0.667 → axis revised / re-piloted

## Per-axis alpha

| Axis | Method | n (both labeled) | α (point) | 95% bootstrap CI | Threshold |
|---|---|---:|---:|---|---|
| function | nominal | 12 | 0.781 | [0.389, 1.000] | TENTATIVE (0.667-0.80) |
| stance | ordinal | 12 | 0.749 | [0.042, 1.000] | TENTATIVE (0.667-0.80) |
| depth | nominal | 12 | 0.635 | [-0.095, 1.000] | BELOW_THRESHOLD (<0.667) |

## Per-class one-vs-rest alpha (nominal axes)

| Axis | Class | α (point) | 95% bootstrap CI | n units | n positive |
|---|---|---:|---|---:|---:|
| function | Background | 0.839 | [0.420, 1.000] | 12 | 11 |
| function | CompareContrast | 0.635 | [-0.095, 1.000] | 12 | 3 |
| function | Extends | 1.000 | [1.000, 1.000] | 12 | 2 |
| function | Future | 1.000 | [1.000, 1.000] | 12 | 2 |
| function | Motivation | 0.635 | [-0.095, 1.000] | 12 | 3 |
| function | Uses | 0.635 | [-0.095, 1.000] | 12 | 3 |
| depth | Perfunctory | 0.635 | [-0.095, 1.000] | 12 | 3 |
| depth | Substantive | 0.635 | [-0.095, 1.000] | 12 | 21 |

## Notes

- α computed with `irr::kripp.alpha`. Wrapper + bootstrap in `scripts/R/krippendorff.R`. Unit-tested against the canonical Krippendorff C example (nominal α = 0.7434).
- Bootstrap CI: resamples units (columns) with replacement, n_boot iterations, reports the 2.5%–97.5% percentile interval.
- One-vs-rest per-class alpha is reported only for nominal axes (function, depth). For stance (ordinal) the per-axis ordinal α is the relevant summary.
- Items with only one annotator's label on an axis are excluded from that axis's α denominator (kripp.alpha cannot use single-coder units for pair reliability).

