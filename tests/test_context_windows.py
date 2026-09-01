#!/usr/bin/env python3
"""Unit tests for the explicit citation-context window contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "corpus"))

from context_windows import sentence_spans, s2_snippet_fields, three_sentence_window


class ContextWindowTests(unittest.TestCase):
    def test_complete_three_sentence_window(self):
        text = (
            "The debate began earlier. "
            "Meadows et al. (1972) modeled ecological overshoot. "
            "Later authors revised the assumptions."
        )
        start = text.index("Meadows")
        result = three_sentence_window(text, start, start + len("Meadows"))
        self.assertTrue(result["context_window_complete"])
        self.assertEqual(result["context_sentence_count"], 3)
        self.assertEqual(result["sentence_before"], "The debate began earlier.")
        self.assertIn("Meadows et al. (1972)", result["citing_sentence"])
        self.assertEqual(result["sentence_after"], "Later authors revised the assumptions.")

    def test_document_edge_is_not_annotation_eligible(self):
        text = "Meadows et al. (1972) modeled ecological overshoot. Later authors revised it."
        result = three_sentence_window(text, 0, len("Meadows"))
        self.assertFalse(result["context_window_complete"])
        self.assertEqual(result["context_sentence_count"], 2)

    def test_academic_abbreviation_does_not_split(self):
        text = (
            "Several models were compared. "
            "Meadows et al. (1972) supplied the baseline. "
            "The comparison remained influential."
        )
        self.assertEqual(len(sentence_spans(text)), 3)

    def test_finnish_citation_abbreviation_does_not_split(self):
        text = "Aiempi tutkimus taustoitti väitteen. Kasvun rajat julkaistiin (Meadows ym. 1972). Se herätti keskustelua."
        self.assertEqual(len(sentence_spans(text)), 3)

    def test_s2_snippet_is_never_claimed_as_verified_window(self):
        result = s2_snippet_fields(
            "Earlier work set the stage. Meadows et al. (1972) supplied the model. Later work revised it."
        )
        self.assertFalse(result["context_window_complete"])
        self.assertEqual(result["context_window_status"], "s2_precomputed_context_unverified")
        self.assertEqual(result["context_sentence_count"], 3)


if __name__ == "__main__":
    unittest.main()
