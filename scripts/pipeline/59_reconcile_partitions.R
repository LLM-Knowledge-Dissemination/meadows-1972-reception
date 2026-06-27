#!/usr/bin/env Rscript

## Reconciles the three partitions of the 1,590-row contextual corpus that
## circulate in Paper 1 (evidence levels; review flags; review-burden split).
##
## Inputs (read-only):
##   - analysis/data/final/meadows_context_classification.csv (record-level corpus)
##
## Outputs:
##   - analysis/results/review_burden_partition.csv
##       Long-form reconciliation: headline counts (substantive / audit / no-review),
##       evidence-level counts, review-flag counts, and per-cell rule decomposition.
##       Each row carries `expected` (from current manuscript / committed labels),
##       `found` (derived here from record-level data), and a `match` flag.
##
## Review-burden split rule (from scripts/pipeline/56_generate_paper1_rq_figures.R
## lines 526-538, retained as the canonical definition):
##
##   substantive_review = needs_human_review
##                        | human_review_status %in% {human_reviewed,
##                                                    unresolved_or_rejected}
##   audit_review       = !substantive_review
##                        & (citation_function == "bibliographic_only"
##                           | human_review_status %in%
##                             {router_safe_not_human_reviewed,
##                              hybrid_accepted_not_human_reviewed})
##   no_review          = otherwise (should be 0 under the current policy split)
##
## This script intentionally does NOT silently force any partition. If the
## record-level data produced a number that differed from the manuscript's
## hardcoded counts, the CSV would record `match = FALSE` for that row.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tidyr)
})

set.seed(42L)  ## no stochastic computation; set for reproducibility hygiene

root <- normalizePath(getwd(), mustWork = TRUE)
corpus_path <- file.path(
  root, "analysis", "data", "final", "meadows_context_classification.csv"
)
out_path <- file.path(root, "analysis", "results", "review_burden_partition.csv")
dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)

corpus <- read_csv(corpus_path, show_col_types = FALSE)
n_total <- nrow(corpus)

partitioned <- corpus %>%
  mutate(
    is_needs_review = isTRUE(TRUE) & (needs_human_review %in% c(TRUE, "true", "TRUE")),
    is_needs_review = needs_human_review %in% c(TRUE, "true", "TRUE"),
    in_substantive_review = is_needs_review |
      human_review_status %in% c("human_reviewed", "unresolved_or_rejected"),
    in_audit_review = !in_substantive_review &
      (citation_function == "bibliographic_only" |
        human_review_status %in% c(
          "router_safe_not_human_reviewed",
          "hybrid_accepted_not_human_reviewed"
        )),
    in_no_review = !in_substantive_review & !in_audit_review
  )

stopifnot(
  "partition is not a true partition" =
    all(rowSums(as.matrix(partitioned[, c(
      "in_substantive_review", "in_audit_review", "in_no_review"
    )])) == 1L)
)

n_substantive <- sum(partitioned$in_substantive_review)
n_audit <- sum(partitioned$in_audit_review)
n_no_review <- sum(partitioned$in_no_review)

n_needs_review <- sum(partitioned$is_needs_review)
n_already_reviewed_not_flag <- sum(
  !partitioned$is_needs_review & partitioned$human_review_status == "human_reviewed"
)
n_unresolved_not_flag <- sum(
  !partitioned$is_needs_review &
    partitioned$human_review_status == "unresolved_or_rejected"
)

n_evidence_level_1 <- sum(partitioned$evidence_level ==
  "Level 1: traditional bibliometric evidence")
n_evidence_level_2 <- sum(partitioned$evidence_level ==
  "Level 2: human-reviewed contextual evidence")
n_evidence_level_3 <- sum(partitioned$evidence_level ==
  "Level 3: validated deterministic-router evidence")
n_evidence_level_4 <- sum(partitioned$evidence_level ==
  "Level 4: hybrid accepted but not human-reviewed")
n_evidence_level_5 <- sum(partitioned$evidence_level ==
  "Level 5: unresolved gray-zone / not usable")

n_no_review_flag <- sum(!partitioned$is_needs_review)

n_bibliographic_only <- sum(partitioned$citation_function == "bibliographic_only")
n_usable_for_substantive <- sum(
  partitioned$usable_for_substantive_analysis %in% c(TRUE, "true", "TRUE")
)

## Expected counts from the manuscript / committed tables:
##   1,590 corpus rows (Methods §2.1 / Table 1)
##   1,395 + 65 + 36 + 24 + 70 evidence levels (Table 1)
##   870 needs-review / 720 no-flag (Table 1)
##   662 bibliography-only (Table 1)
##   95 usable for substantive analysis (Table 1)
##   949 substantive / 641 audit / 0 no-review (review-burden split; Methods §2.9)

reconciliation <- tibble::tribble(
  ~partition_class, ~definition,                                                                              ~expected, ~found,
  ## --- aggregate corpus size ---
  "corpus_total",                "All contextual corpus rows (meadows_context_classification.csv)",            1590L,    n_total,

  ## --- review-burden split (the three classes referenced in Methods §2.9 / Table 5) ---
  "substantive_review",          "needs_human_review OR human_review_status in {human_reviewed, unresolved_or_rejected}", 949L, n_substantive,
  "audit_review",                "NOT substantive AND (citation_function == bibliographic_only OR human_review_status in {router_safe_not_human_reviewed, hybrid_accepted_not_human_reviewed})", 641L, n_audit,
  "no_review_required",          "NOT substantive AND NOT audit (residual under current policy split)",        0L,       n_no_review,

  ## --- substantive_review decomposition (surfaces the 949 > 870 tension) ---
  "substantive_decomp_needs_review",     "subset of substantive: needs_human_review == TRUE",                  870L,     n_needs_review,
  "substantive_decomp_already_reviewed", "subset of substantive: human_reviewed AND NOT needs_human_review",   NA_integer_, n_already_reviewed_not_flag,
  "substantive_decomp_unresolved",       "subset of substantive: unresolved_or_rejected AND NOT needs_human_review", NA_integer_, n_unresolved_not_flag,

  ## --- review-flag partition (Table 1) ---
  "review_flag_needs_review",    "needs_human_review == TRUE",                                                 870L,     n_needs_review,
  "review_flag_no_flag",         "needs_human_review == FALSE",                                                720L,     n_no_review_flag,

  ## --- evidence-level partition (Table 1) ---
  "evidence_level_1_traditional",        "evidence_level == 'Level 1: traditional bibliometric evidence'",     1395L,    n_evidence_level_1,
  "evidence_level_2_human_reviewed",     "evidence_level == 'Level 2: human-reviewed contextual evidence'",    65L,      n_evidence_level_2,
  "evidence_level_3_validated_router",   "evidence_level == 'Level 3: validated deterministic-router evidence'", 36L,    n_evidence_level_3,
  "evidence_level_4_hybrid_accepted",    "evidence_level == 'Level 4: hybrid accepted but not human-reviewed'", 24L,     n_evidence_level_4,
  "evidence_level_5_unresolved",         "evidence_level == 'Level 5: unresolved gray-zone / not usable'",     70L,      n_evidence_level_5,

  ## --- ancillary corpus counts referenced in Table 1 / Methods ---
  "bibliography_only_rows",      "citation_function == 'bibliographic_only'",                                  662L,     n_bibliographic_only,
  "usable_for_substantive_rows", "usable_for_substantive_analysis == TRUE",                                    95L,      n_usable_for_substantive
)

reconciliation <- reconciliation %>%
  mutate(
    match = if_else(is.na(expected), NA, expected == found),
    notes = case_when(
      partition_class == "substantive_decomp_needs_review" ~
        paste0("Surface the manuscript tension: substantive_review (",
               n_substantive,
               ") exceeds needs_human_review (",
               n_needs_review,
               ") because substantive_review is the union of needs-review + already-reviewed (",
               n_already_reviewed_not_flag,
               ") + unresolved_or_rejected-not-otherwise-flagged (",
               n_unresolved_not_flag,
               "). 870 + ",
               n_already_reviewed_not_flag, " + ",
               n_unresolved_not_flag, " = ",
               n_substantive, "."),
      partition_class == "substantive_decomp_already_reviewed" ~
        "No manuscript expected value; this is a definitional component disclosed for transparency.",
      partition_class == "substantive_decomp_unresolved" ~
        "No manuscript expected value; this is a definitional component disclosed for transparency.",
      TRUE ~ NA_character_
    )
  )

write_csv(reconciliation, out_path)

message("Wrote ", out_path, " (", nrow(reconciliation), " rows).")
message("Headline split: substantive=", n_substantive,
        " audit=", n_audit,
        " no_review=", n_no_review,
        " (total=", n_total, ").")
message("Substantive decomposition: ", n_needs_review, " needs-review + ",
        n_already_reviewed_not_flag, " already-reviewed-only + ",
        n_unresolved_not_flag, " unresolved-only = ", n_substantive,
        " (resolves the ", n_substantive, " > ", n_needs_review, " tension).")
