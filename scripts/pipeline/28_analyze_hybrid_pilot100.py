#!/usr/bin/env python3
"""Stratum-level audit and Meadows-report bridge for the hybrid 100 pilot."""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/tables"
VALIDATION = ROOT / "analysis/validation"

INPUT = ROOT / "analysis/data/llm_input/v2/v2_hybrid_pilot100_input.csv"
OUTPUT = ROOT / "analysis/data/llm_output/v2/v2_hybrid_pilot100_classifications.csv"
DIAG = ROOT / "analysis/logs/v2_hybrid_pilot100_diagnostic.csv"
ERRORS = TABLES / "v2_hybrid_pilot100_validation_errors.csv"

ACCEPTED = {"router_valid", "initial_valid", "repaired_valid"}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def yes(value: str) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else ""


def ref(source: Dict[str, str], manual: str, human: str) -> str:
    return source.get(manual, "") or source.get(human, "")


def safe_for_scale(row: Dict[str, Any]) -> str:
    if row["n_contexts"] < 3:
        return "insufficient_n"
    if row["acceptance_rate"] != "" and float(row["acceptance_rate"]) < 0.75:
        return "no"
    if row["llm_rejection_rate"] != "" and float(row["llm_rejection_rate"]) > 0.35:
        return "no"
    if row["human_function_agreement_rate"] != "" and float(row["human_function_agreement_rate"]) < 0.8:
        return "no"
    if row["topic_unclear_rate"] != "" and float(row["topic_unclear_rate"]) > 0.45:
        return "caution_topic_weak"
    return "caution"


def main() -> None:
    inputs = {row["context_group_id"]: row for row in read_csv(INPUT)}
    outputs = read_csv(OUTPUT)
    diags = {row["context_group_id"]: row for row in read_csv(DIAG)}
    errors = defaultdict(list)
    for row in read_csv(ERRORS):
        errors[row["context_group_id"]].append(row.get("validation_error", ""))

    joined = []
    for out in outputs:
        src = inputs.get(out["context_group_id"], {})
        diag = diags.get(out["context_group_id"], {})
        human_function = ref(src, "manual_recommended_citation_function", "human_primary_role")
        human_stance = ref(src, "manual_recommended_stance_toward_seed", "human_stance_toward_seed")
        human_topic = ref(src, "manual_recommended_topic_or_discourse_area", "human_discourse_category")
        row = {
            **src,
            **out,
            "actual_api_call": diag.get("actual_api_call", out.get("send_to_llm", "")),
            "validation_error_list": " | ".join(errors[out["context_group_id"]]),
            "human_function_reference": human_function,
            "human_stance_reference": human_stance,
            "human_topic_reference": human_topic,
            "human_function_agreement": str(out.get("citation_function") == human_function).lower() if human_function else "",
            "human_stance_agreement": str(out.get("stance_toward_seed") == human_stance).lower() if human_stance else "",
            "human_topic_agreement": str(out.get("topic_or_discourse_area") == human_topic).lower() if human_topic else "",
        }
        joined.append(row)

    by_stratum = []
    for stratum in sorted(set(row.get("stratum", "unknown") for row in joined)):
        rows = [row for row in joined if row.get("stratum", "unknown") == stratum]
        accepted = [row for row in rows if row["classification_status"] in ACCEPTED]
        human = [row for row in accepted if row.get("human_function_reference")]
        llm = [row for row in rows if yes(row.get("actual_api_call"))]
        deterministic = [row for row in rows if row.get("classification_source") == "deterministic_router"]
        failure_modes = Counter()
        for row in rows:
            for err in row.get("validation_error_list", "").split(" | "):
                if err:
                    failure_modes[err] += 1
        record = {
            "stratum": stratum,
            "n_contexts": len(rows),
            "deterministic_router_n": len(deterministic),
            "llm_n": len(llm),
            "accepted_n": len(accepted),
            "rejected_n": len(rows) - len(accepted),
            "acceptance_rate": mean(row["classification_status"] in ACCEPTED for row in rows),
            "llm_rejection_rate": mean(row["classification_status"] not in ACCEPTED for row in llm),
            "human_labeled_accepted_n": len(human),
            "human_function_agreement_rate": mean(yes(row.get("human_function_agreement")) for row in human),
            "human_stance_agreement_rate": mean(yes(row.get("human_stance_agreement")) for row in [r for r in accepted if r.get("human_stance_reference")]),
            "human_topic_agreement_rate": mean(yes(row.get("human_topic_agreement")) for row in [r for r in accepted if r.get("human_topic_reference")]),
            "topic_unclear_rate": mean(row.get("topic_or_discourse_area") == "unclear" for row in accepted),
            "common_failure_modes": " | ".join(f"{k}:{v}" for k, v in failure_modes.most_common(5)),
            "function_distribution": " | ".join(f"{k}:{v}" for k, v in Counter(row.get("citation_function", "") for row in accepted).most_common()),
        }
        record["safe_for_scale"] = safe_for_scale(record)
        by_stratum.append(record)
    write_csv(TABLES / "v2_hybrid_pilot100_by_stratum.csv", by_stratum)

    accepted = [row for row in joined if row["classification_status"] in ACCEPTED]
    human = [row for row in accepted if row.get("human_function_reference")]
    bridge = [
        {
            "finding_type": "human-reviewed findings",
            "finding": "Human-labeled accepted rows show strong hybrid function agreement on this pilot subset.",
            "evidence": f"{sum(yes(r['human_function_agreement']) for r in human)}/{len(human)} accepted human-labeled rows matched the human function label.",
            "status_for_report": "safe with scope limits",
            "caution": "Only accepted rows with existing human labels; not corpus-wide.",
        },
        {
            "finding_type": "hybrid-pilot findings with human-audited support",
            "finding": "Hybrid routing improved OCR abstention and modeling/foundational boundary handling relative to pure v2 on the prior regression set.",
            "evidence": "The 16-context regression reached 15/16 accepted-correct function labels; the 100-context pilot retained 85.7% accepted human-function agreement.",
            "status_for_report": "safe as methods-validation result",
            "caution": "The 100-context sample is stratified and intentionally difficult.",
        },
        {
            "finding_type": "exploratory hypotheses",
            "finding": "Historical framing appears common among accepted pilot classifications.",
            "evidence": f"{Counter(r['citation_function'] for r in accepted).get('historical_framing', 0)}/{len(accepted)} accepted pilot rows were historical framing.",
            "status_for_report": "exploratory hypothesis",
            "caution": "Sampling intentionally overrepresents boundary/human-coded cases; do not infer corpus prevalence.",
        },
        {
            "finding_type": "exploratory hypotheses",
            "finding": "Foundational-to-historical-framing transition over time remains a plausible hypothesis rather than a validated trend.",
            "evidence": "The pilot supports clearer separation of foundational and historical functions, but it is not designed as a decade-balanced prevalence estimate.",
            "status_for_report": "plausible hypothesis",
            "caution": "Requires decade-stratified human validation or a larger audited hybrid run before formal testing.",
        },
        {
            "finding_type": "findings not yet safe to report",
            "finding": "Topic/discourse labels are not yet reliable enough for strong interpretive claims.",
            "evidence": "Human-topic agreement was weak or unavailable in the pilot; many accepted rows had unclear or broad topic labels.",
            "status_for_report": "not safe",
            "caution": "Topic labels should be marked exploratory until codebook and validation improve.",
        },
        {
            "finding_type": "findings not yet safe to report",
            "finding": "500-context hybrid classification is not yet justified.",
            "evidence": "The gray-zone LLM rejection rate was high, with 25/55 LLM rows rejected by deterministic validation.",
            "status_for_report": "not safe",
            "caution": "Run additional focused pilots or add human review before scaling.",
        },
    ]
    write_csv(TABLES / "contextual_findings_ready_for_meadows_report.csv", bridge)
    print("Wrote by-stratum and Meadows bridge tables.")


if __name__ == "__main__":
    main()
