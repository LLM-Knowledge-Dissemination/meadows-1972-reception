# Citation-window QA

**Updated:** 2026-09-01

## Contract

An annotation-eligible context is exactly three explicit sentences: the seed-
citing sentence, its immediate predecessor, and its immediate successor.

S2 `contexts` strings are stored as unverified source snippets and are never
made eligible merely because they happen to contain three sentence-like
segments.

## Automated checks

- Every pilot row has non-empty `sentence_before`, `citing_sentence`, and
  `sentence_after` fields.
- Every pilot row has `context_window_complete == True`,
  `context_sentence_count == 3`, and `annotation_eligible == True`.
- S2-only rows have `annotation_eligible == False`.
- Multiple author/title markers in one citing sentence collapse to one context.
- Likely bibliography entries, anti-bot text, and unattributed title phrases
  receive explicit quality flags and are excluded from sampling.

## Review findings

Manual review across seeds, decades, routes, and work types found that the
earlier one-sentence extractor admitted many reference-list entries and generic
uses of phrases such as “limits to growth” and “small is beautiful.” The v1.1
quality gate therefore prioritizes precision for the human pilot. It reduced
the usable pool to 87 contexts.

Remaining risks for adjudicator review include OCR-induced sentence boundaries,
footnotes merged into body text, non-English abbreviations, and conservative
false-positive bibliography flags.
