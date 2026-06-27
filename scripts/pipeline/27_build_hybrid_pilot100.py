#!/usr/bin/env python3
"""Build a stratified 100-context input for the hybrid v2 classifier."""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.python.llm_context_classifier import validate_v2_input_file, write_csv
from scripts.python.v2_preclassification_router import route_context


VALIDATION = ROOT / "analysis/validation"
PROCESSED = ROOT / "analysis/data/processed"
TABLES = ROOT / "analysis/tables"
OUT = VALIDATION / "v2_hybrid_pilot_100_input.csv"


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "t", "yes", "y", "1"}


def decade(year: str) -> str:
    try:
        y = int(float(year))
    except (TypeError, ValueError):
        return "unknown"
    return f"{(y // 10) * 10}s"


def group_id_for(row: Dict[str, str]) -> str:
    raw = row.get("context_id") or row.get("hit_id") or row.get("snippet_hash") or row.get("snippet", "")
    return "cg_extra_" + hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]


def normalize_existing(row: Dict[str, str]) -> Dict[str, str]:
    out = dict(row)
    out.setdefault("canonical_context_id", row.get("canonical_context_id") or row.get("mention_level_id") or row.get("context_id") or "")
    out.setdefault("mention_level_id", row.get("mention_level_id") or row.get("canonical_context_id") or row.get("context_id") or "")
    out.setdefault("snippet_clean", row.get("snippet_clean") or row.get("snippet") or "")
    out.setdefault("context_window", row.get("context_window") or row.get("surrounding_sentence_window") or row.get("snippet_clean") or "")
    out.setdefault("citation_sentence", row.get("citation_sentence") or row.get("sentence") or row.get("snippet_clean") or "")
    out.setdefault("sentence_before", row.get("sentence_before", ""))
    out.setdefault("sentence_after", row.get("sentence_after", ""))
    out.setdefault("bibliography_detected", row.get("bibliography_detected") or row.get("is_biblio_any") or "")
    out.setdefault("bibliography_score", row.get("bibliography_score") or row.get("biblio_score") or "0")
    out.setdefault("extraction_confidence", row.get("extraction_confidence") or "0.7")
    out.setdefault("title", row.get("title") or row.get("canonical_title") or "")
    out.setdefault("venue", row.get("venue", ""))
    out.setdefault("year", row.get("year", ""))
    out.setdefault("citation_section", row.get("citation_section") or "BODY")
    out.setdefault("mention_type", row.get("mention_type") or "")
    out.setdefault("page", row.get("page") or "")
    out.setdefault("group_member_count", row.get("group_member_count") or "1")
    out.setdefault("group_member_ids", row.get("group_member_ids") or out["mention_level_id"])
    out.setdefault("group_has_human_coding", row.get("group_has_human_coding") or ("yes" if row.get("human_primary_role") else "no"))
    out.setdefault("group_human_coded_member_ids", row.get("group_human_coded_member_ids") or (out["mention_level_id"] if row.get("human_primary_role") else ""))
    out.setdefault("group_human_primary_roles", row.get("group_human_primary_roles") or row.get("human_primary_role", ""))
    out.setdefault("group_human_stances", row.get("group_human_stances") or row.get("human_stance_toward_seed", ""))
    out.setdefault("group_human_label_conflict", row.get("group_human_label_conflict") or "no")
    out.setdefault("group_has_boundary_case", row.get("group_has_boundary_case") or ("yes" if row.get("review_priority") == "high" else "no"))
    out.setdefault("group_has_context_window_pilot", row.get("group_has_context_window_pilot") or "no")
    return out


def enriched_to_v2(row: Dict[str, str]) -> Dict[str, str]:
    context_id = row.get("context_id") or row.get("hit_id") or group_id_for(row)
    return {
        "context_group_id": group_id_for(row),
        "mention_level_id": context_id,
        "is_repeated_context": "no",
        "mention_variant_count": "1",
        "title": row.get("canonical_title", ""),
        "year": row.get("year", ""),
        "venue": row.get("venue", ""),
        "page": row.get("page", ""),
        "citation_section": row.get("citation_section") or ("BIBLIO" if boolish(row.get("is_biblio_any")) else "BODY"),
        "mention_type": row.get("mention_type", ""),
        "snippet_clean": row.get("snippet") or "",
        "context_window": row.get("surrounding_sentence_window") or row.get("snippet") or "",
        "citation_sentence": row.get("sentence") or row.get("snippet") or "",
        "sentence_before": "",
        "sentence_after": "",
        "section_heading": row.get("section_heading", ""),
        "bibliography_detected": str(boolish(row.get("is_biblio_any")) or boolish(row.get("bib_like"))).lower(),
        "bibliography_score": row.get("biblio_score") or "0",
        "v1_llm_primary_role": "",
        "v1_llm_topic": "",
        "v1_llm_stance": "",
        "v1_llm_confidence": "",
        "v1_llm_evidence_quote": "",
        "v1_llm_uncertainty_flags": "",
        "fallback_primary_role": row.get("citation_function", ""),
        "human_is_seed_work_citation": "",
        "human_primary_role": "",
        "human_discourse_category": "",
        "human_stance_toward_seed": "",
        "human_false_positive_flag": "",
        "human_confidence": "",
        "review_priority": "medium" if row.get("false_positive_risk") == "high" else "low",
        "review_reason": "additional stratified hybrid pilot context",
        "human_notes": "",
        "extraction_confidence": row.get("extraction_confidence") or "0.6",
        "canonical_context_id": context_id,
        "group_member_count": "1",
        "group_member_ids": context_id,
        "group_has_human_coding": "no",
        "group_human_coded_member_ids": "",
        "group_human_primary_roles": "",
        "group_human_stances": "",
        "group_human_label_conflict": "no",
        "group_has_boundary_case": "no",
        "group_has_context_window_pilot": "no",
        "source_database": row.get("source_database", ""),
        "document_type": row.get("document_type", ""),
        "false_positive_risk": row.get("false_positive_risk", ""),
    }


def text(row: Dict[str, str]) -> str:
    return " ".join([
        row.get("citation_sentence", ""),
        row.get("context_window", ""),
        row.get("snippet_clean", ""),
        row.get("review_reason", ""),
    ]).lower()


def assign_stratum(row: Dict[str, str]) -> str:
    body = text(row)
    if row.get("group_has_human_coding") == "yes" or row.get("human_primary_role"):
        return "human_coded"
    if row.get("group_has_boundary_case") == "yes" or row.get("review_priority") == "high":
        return "boundary_case"
    if boolish(row.get("bibliography_detected")) or row.get("citation_section") == "BIBLIO" or "bibliograph" in body:
        return "bibliography_like"
    if any(term in body for term in ["ocr", "snippet_too_short", "low confidence"]) or safe_float(row.get("extraction_confidence")) < 0.55:
        return "ocr_or_low_confidence"
    if any(term in body for term in ["simulation", "system dynamics", "world3", "world 3", "model", "modelling", "modeling", "scenario", "forecast", "projection"]):
        return "modeling_simulation"
    if any(term in body for term in ["exhaustible resources", "finite planet", "resource", "constrain economic growth", "collapse", "overshoot", "population", "pollution"]):
        return "foundational_claim"
    if any(term in body for term in ["policy", "governance", "planning", "regulation", "management", "decision-making"]):
        return "policy_governance_ambiguity"
    if any(term in body for term in ["publication", "published", "influential", "famous", "seminal", "classic", "landmark", "50 years", "released its report", "followed by"]):
        return "historical_lineage"
    if "limits to growth" in body and "meadows" not in body:
        return "generic_limits_phrase"
    if len(body.split()) < 35:
        return "short_context"
    return "lower_risk_neutral_historical"


def safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.7


def sampling_reason(row: Dict[str, str], stratum: str) -> str:
    reasons = [stratum]
    if row.get("group_has_human_coding") == "yes" or row.get("human_primary_role"):
        reasons.append("human-coded")
    if row.get("group_has_boundary_case") == "yes":
        reasons.append("boundary")
    if row.get("group_has_context_window_pilot") == "yes":
        reasons.append("context-window")
    if boolish(row.get("bibliography_detected")):
        reasons.append("bibliography signal")
    return "; ".join(dict.fromkeys(reasons))


def add_sampling_metadata(row: Dict[str, str]) -> Dict[str, str]:
    row = normalize_existing(row)
    stratum = assign_stratum(row)
    route = route_context(row)
    row["stratum"] = stratum
    row["sampling_reason"] = sampling_reason(row, stratum)
    row["expected_router_behavior"] = "send_to_llm" if route.send_to_llm else route.routing_decision
    row["expected_human_review_need"] = str(route.force_needs_human_review).lower()
    row["has_human_label"] = "yes" if row.get("group_has_human_coding") == "yes" or row.get("human_primary_role") else "no"
    row["decade"] = decade(row.get("year", ""))
    row["field_or_venue"] = row.get("venue") or row.get("source_database") or "unknown"
    return row


def select_extra(existing: List[Dict[str, str]], n: int) -> List[Dict[str, str]]:
    enriched = read_csv(PROCESSED / "citation_contexts_enriched.csv")
    seen_contexts = {row.get("canonical_context_id") or row.get("mention_level_id") for row in existing}
    candidates = []
    for row in enriched:
        v2 = enriched_to_v2(row)
        if v2["canonical_context_id"] in seen_contexts:
            continue
        candidates.append(add_sampling_metadata(v2))
    targets = [
        "bibliography_like", "ocr_or_low_confidence", "modeling_simulation",
        "foundational_claim", "historical_lineage", "policy_governance_ambiguity",
        "generic_limits_phrase", "short_context", "lower_risk_neutral_historical",
    ]
    selected, seen_groups = [], set()
    for stratum in targets:
        for row in candidates:
            if row["stratum"] == stratum and row["context_group_id"] not in seen_groups:
                selected.append(row)
                seen_groups.add(row["context_group_id"])
                break
        if len(selected) >= n:
            return selected[:n]
    # Round-robin additional rows by underrepresented decade/venue.
    for row in sorted(candidates, key=lambda r: (Counter(x["decade"] for x in selected)[r["decade"]], Counter(x["field_or_venue"] for x in selected)[r["field_or_venue"]], r["context_group_id"])):
        if row["context_group_id"] in seen_groups:
            continue
        selected.append(row)
        seen_groups.add(row["context_group_id"])
        if len(selected) >= n:
            break
    return selected[:n]


def main() -> None:
    ready = [add_sampling_metadata(row) for row in read_csv(VALIDATION / "v2_classifier_pilot_input_100_ready.csv")]
    by_group: Dict[str, Dict[str, str]] = {}
    for row in ready:
        by_group.setdefault(row["context_group_id"], row)
    base = list(by_group.values())
    extra = select_extra(base, max(0, 100 - len(base)))
    combined = base + extra
    # Preserve human-coded and boundary rows, then distribute remaining rows.
    combined = sorted(
        combined,
        key=lambda r: (
            0 if r["has_human_label"] == "yes" else 1,
            0 if r.get("group_has_boundary_case") == "yes" else 1,
            r["stratum"],
            r["decade"],
            r["field_or_venue"],
            r["context_group_id"],
        ),
    )[:100]
    write_csv(OUT, combined)
    validate_v2_input_file(OUT)
    summary = []
    for key, values in {
        "stratum": [r["stratum"] for r in combined],
        "has_human_label": [r["has_human_label"] for r in combined],
        "decade": [r["decade"] for r in combined],
        "expected_router_behavior": [r["expected_router_behavior"] for r in combined],
    }.items():
        for value, count in Counter(values).most_common():
            summary.append({"field": key, "value": value, "n": count})
    write_csv(TABLES / "v2_hybrid_pilot100_input_composition.csv", summary)
    print(f"Wrote {OUT} with {len(combined)} rows.")
    print(Counter(r["stratum"] for r in combined))


if __name__ == "__main__":
    main()
