#!/usr/bin/env python3
"""Sentence-window helpers shared by the citation-context extractors.

The annotation unit is explicit: the sentence containing the seed citation,
plus the immediately preceding and following sentences.  A context is
annotation-eligible only when all three sentences are present.  Semantic
Scholar ``contexts`` values are preserved as pre-computed snippets, but are
never represented as verified three-sentence windows because their boundaries
and centering are controlled by S2 rather than this pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_WS_RE = re.compile(r"\s+")
_BOUNDARY_RE = re.compile(r"[.!?](?:[\"'\u201d\u2019)\]]{0,2})\s+")
_NEXT_SENTENCE_RE = re.compile(r"[\"'\u201c\u2018(\[]*[A-Z0-9]")
_ABBREVIATION_RE = re.compile(
    r"(?:\b(?:al|etal|ym|fig|eq|e\.g|i\.e|no|pp|vol|vs|cf|dr|mr|mrs|ms|prof|"
    r"inc|jr|sr|st)\.|(?:\b[A-Z]\.){1,3})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SentenceSpan:
    start: int
    end: int
    text: str


def clean_sentence(text: str) -> str:
    """Collapse extraction whitespace without changing sentence content."""
    return _WS_RE.sub(" ", (text or "")).strip()


def sentence_spans(text: str) -> list[SentenceSpan]:
    """Split text into sentence spans while retaining source offsets.

    This is deliberately deterministic and dependency-free.  It avoids common
    academic abbreviations and initials, which are frequent around citations.
    """
    if not text or not text.strip():
        return []

    spans: list[SentenceSpan] = []
    start = 0
    for match in _BOUNDARY_RE.finditer(text):
        next_start = match.end()
        next_nonspace = text[next_start:next_start + 8].lstrip()
        if not next_nonspace or not _NEXT_SENTENCE_RE.match(next_nonspace):
            continue
        candidate = text[start:match.start() + 1].rstrip()
        if _ABBREVIATION_RE.search(candidate):
            continue
        end = match.start() + 1
        cleaned = clean_sentence(text[start:end])
        if cleaned:
            spans.append(SentenceSpan(start=start, end=end, text=cleaned))
        start = next_start

    cleaned = clean_sentence(text[start:])
    if cleaned:
        spans.append(SentenceSpan(start=start, end=len(text), text=cleaned))
    return spans


def three_sentence_window(text: str, match_start: int, match_end: int) -> dict:
    """Return the sentence containing a match and its immediate neighbors."""
    spans = sentence_spans(text)
    if not spans:
        return {
            "sentence_before": "",
            "citing_sentence": "",
            "sentence_after": "",
            "context_text": "",
            "context_window_complete": False,
            "context_sentence_count": 0,
            "context_window_status": "no_sentence_detected",
            "_citing_span_start": -1,
            "_citing_span_end": -1,
        }

    midpoint = max(0, (match_start + match_end) // 2)
    citing_index = next(
        (i for i, span in enumerate(spans) if span.start <= midpoint <= span.end),
        min(range(len(spans)), key=lambda i: abs(spans[i].start - midpoint)),
    )
    before = spans[citing_index - 1].text if citing_index > 0 else ""
    citing = spans[citing_index].text
    after = spans[citing_index + 1].text if citing_index + 1 < len(spans) else ""
    complete = bool(before and citing and after)
    pieces = [part for part in (before, citing, after) if part]
    status = "complete_three_sentence_window" if complete else "partial_document_edge_window"
    return {
        "sentence_before": before,
        "citing_sentence": citing,
        "sentence_after": after,
        "context_text": " ".join(pieces),
        "context_window_complete": complete,
        "context_sentence_count": len(pieces),
        "context_window_status": status,
        "_citing_span_start": spans[citing_index].start,
        "_citing_span_end": spans[citing_index].end,
    }


def s2_snippet_fields(snippet: str) -> dict:
    """Represent an S2 context without claiming a locally verified window."""
    cleaned = clean_sentence(snippet)
    return {
        "sentence_before": "",
        "citing_sentence": cleaned,
        "sentence_after": "",
        "context_text": cleaned,
        "context_window_complete": False,
        "context_sentence_count": len(sentence_spans(cleaned)),
        "context_window_status": "s2_precomputed_context_unverified",
    }
