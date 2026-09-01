#!/usr/bin/env python3
"""Migrate the frozen S2 context table to the explicit window schema.

This performs no API calls.  It preserves S2's pre-computed context strings
verbatim (apart from whitespace normalization) and marks them unverified for
three-sentence annotation.  OA contexts are rebuilt from the frozen local
document cache by ``04_extract_oa_pdf_contexts.py`` before this script runs.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_windows import s2_snippet_fields
from lib_corpus import CORPUS_DIR


S2_CONTEXTS = CORPUS_DIR / "contexts_s2.csv"


def main() -> None:
    if not S2_CONTEXTS.exists():
        raise SystemExit(f"missing input: {S2_CONTEXTS}")
    with S2_CONTEXTS.open(newline="") as f:
        rows = list(csv.DictReader(f))
        original_fields = list(rows[0]) if rows else []
    if not rows:
        raise SystemExit("S2 context table is empty")

    window_fields = [
        "sentence_before",
        "citing_sentence",
        "sentence_after",
        "context_window_complete",
        "context_sentence_count",
        "context_window_status",
    ]
    output_fields = []
    for field in original_fields:
        if field == "context_text":
            output_fields.extend(window_fields[:3])
            output_fields.append("context_text")
            output_fields.extend(window_fields[3:])
        elif field not in window_fields:
            output_fields.append(field)

    for row in rows:
        row.update(s2_snippet_fields(row.get("context_text", "")))

    with S2_CONTEXTS.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in output_fields} for row in rows)
    print(f"migrated {S2_CONTEXTS} ({len(rows)} S2 snippets; all marked unverified)")


if __name__ == "__main__":
    main()
