#!/usr/bin/env Rscript

## Anti-drift checker for Paper 1.
##
## For each canonical number that should flow from a source CSV into the
## manuscript, this script:
##   1. derives the value from the source CSV (the source of truth);
##   2. searches manuscript/paper1_full_manuscript_scientometrics_v1.qmd for
##      occurrences using a set of accepted display patterns (e.g., "1,590"
##      and "1590" are both acceptable display forms of 1590);
##   3. writes one row per number to analysis/results/manuscript_number_diff.csv
##      with: number_label, code_value, code_source, manuscript_value(s),
##      locations (line numbers), match.
##
## Scope:
##   - Numeric values (corpus counts, validation k/n, Wilson CI bounds,
##     review-burden counts, hours, reduction percents, lineage counts,
##     policy seconds).
##   - Excluded by guard: automation_status string values
##     (automated_with_audit, hybrid_review_required, human_required,
##     exploratory_only). These are §2.7 rule outputs pending the grounding
##     decision; see analysis/results/decision_rule_validation_memo.md.
##
## Failure mode: when a manuscript occurrence does not match the code value,
## the script DOES NOT modify the manuscript. The row is recorded with
## match = FALSE so an author/maintainer can decide.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
  library(tidyr)
  library(tibble)
})

set.seed(42L)

root <- normalizePath(getwd(), mustWork = TRUE)
manuscript_path <- file.path(
  root, "manuscript", "paper1_full_manuscript_scientometrics_v1.qmd"
)
out_path <- file.path(root, "analysis", "results", "manuscript_number_diff.csv")
dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)

manuscript_lines <- readLines(manuscript_path)

## --- Pull canonical values from source CSVs ----------------------------------

validation_intervals <- read_csv(
  file.path(root, "analysis", "results", "validation_intervals.csv"),
  show_col_types = FALSE
)
review_burden_partition <- read_csv(
  file.path(root, "analysis", "results", "review_burden_partition.csv"),
  show_col_types = FALSE
)
fig6_source <- read_csv(
  file.path(root, "analysis", "tables", "paper1_rq",
            "paper1_final_fig6_review_burden_source.csv"),
  show_col_types = FALSE
)

get_partition_val <- function(class_name) {
  row <- review_burden_partition[
    review_burden_partition$partition_class == class_name, ]
  if (nrow(row) != 1L) {
    stop("missing partition_class: ", class_name, call. = FALSE)
  }
  as.integer(row$found)
}
get_validation_val <- function(area, field) {
  row <- validation_intervals[validation_intervals$validation_area == area, ]
  if (nrow(row) != 1L) {
    stop("missing validation_area: ", area, call. = FALSE)
  }
  row[[field]]
}
fmt_int_alt <- function(n) {
  ## A 4-digit integer in the manuscript may be displayed as "1590" or "1,590".
  if (n >= 1000) {
    formatted <- format(n, big.mark = ",", scientific = FALSE, trim = TRUE)
    unique(c(as.character(n), formatted))
  } else {
    as.character(n)
  }
}
fmt_rate_pct <- function(p, digits = 1) {
  sprintf(paste0("%.", digits, "f%%"), 100 * p)
}
fmt_ci_bound <- function(p, digits = 2) {
  sprintf(paste0("%.", digits, "f"), p)
}
fmt_hours <- function(h, digits = 1) {
  sprintf(paste0("%.", digits, "f"), h)
}

## --- Canonical number registry -----------------------------------------------
##
## Each row is a number we expect to flow from a source CSV to the manuscript.
## display_patterns is a list of regexes; a manuscript line matches the number
## if any pattern matches.

registry <- tibble::tribble(
  ~number_label,                  ~code_value, ~code_source,                                                                 ~display_patterns,

  # --- Corpus size / Table 1 ----
  "corpus_total_rows",            "1590",      "review_burden_partition.csv: corpus_total",                                  list(fmt_int_alt(1590)),
  "evidence_level_1",             "1395",      "review_burden_partition.csv: evidence_level_1_traditional",                  list(fmt_int_alt(1395)),
  "evidence_level_2",             "65",        "review_burden_partition.csv: evidence_level_2_human_reviewed",               list("65"),
  "evidence_level_3",             "36",        "review_burden_partition.csv: evidence_level_3_validated_router",             list("36"),
  "evidence_level_4",             "24",        "review_burden_partition.csv: evidence_level_4_hybrid_accepted",              list("24"),
  "evidence_level_5",             "70",        "review_burden_partition.csv: evidence_level_5_unresolved",                   list("70"),
  "bibliography_only_rows",       "662",       "review_burden_partition.csv: bibliography_only_rows",                        list("662"),
  "needs_human_review_rows",      "870",       "review_burden_partition.csv: review_flag_needs_review",                      list("870"),
  "no_review_flag_rows",          "720",       "review_burden_partition.csv: review_flag_no_flag",                           list("720"),
  "usable_for_substantive_rows",  "95",        "review_burden_partition.csv: usable_for_substantive_rows",                   list("95"),

  # --- Review-burden split (Methods §2.9 / Table 5) ----
  "review_burden_substantive",    "949",       "review_burden_partition.csv: substantive_review",                            list("949"),
  "review_burden_audit",          "641",       "review_burden_partition.csv: audit_review",                                  list("641"),
  "review_burden_no_review",      "0",         "review_burden_partition.csv: no_review_required",                            list("\\b0\\b contexts are assigned to no-review-required"),

  # --- Validation k/n (Methods §2.6 / Table 3) ----
  "extraction_recovery_helpful",  "10/11",     "validation_intervals.csv: Extraction Recovery k/n",                          list("10/11"),
  "bibliography_audit_precision", "16/20",     "validation_intervals.csv: Bibliography Audit k/n",                           list("16/20"),
  "router_safe_agreement",        "18/24",     "validation_intervals.csv: Router-Safe Batch A k/n",                          list("18/24"),
  "modeling_agreement",           "8/11",      "validation_intervals.csv: Modeling k/n",                                     list("8/11"),
  "boundary_agreement",           "15/28",     "validation_intervals.csv: Historical/Foundation k/n",                        list("15/28"),
  "boundary_rate_pct",            "53.6%",     "validation_intervals.csv: Historical/Foundation 100*p_hat",                  list("53\\.6%"),

  # --- Wilson 95% CIs added to Table 3 ----
  "ci_extraction_recovery",       "[0.62, 0.98]", "validation_intervals.csv: Extraction Recovery [ci_lower, ci_upper] @ 2dp", list("\\[0\\.62, ?0\\.98\\]"),
  "ci_bibliography_audit",        "[0.58, 0.92]", "validation_intervals.csv: Bibliography Audit [ci_lower, ci_upper] @ 2dp",  list("\\[0\\.58, ?0\\.92\\]"),
  "ci_router_safe",               "[0.55, 0.88]", "validation_intervals.csv: Router-Safe Batch A [ci_lower, ci_upper] @ 2dp", list("\\[0\\.55, ?0\\.88\\]"),
  "ci_modeling",                  "[0.43, 0.90]", "validation_intervals.csv: Modeling [ci_lower, ci_upper] @ 2dp",            list("\\[0\\.43, ?0\\.90\\]"),
  "ci_boundary",                  "[0.36, 0.70]", "validation_intervals.csv: Historical/Foundation [ci_lower, ci_upper] @ 2dp", list("\\[0\\.36, ?0\\.70\\]"),

  # --- Table 5 review-burden hours and reduction percents (rounded display) ----
  "hours_manual_fast",            "26.5",      "fig6 source: estimated_manual_hours[Fast] @ 1dp",                            list("\\b26\\.5\\b"),
  "hours_manual_typical",         "39.8",      "fig6 source: estimated_manual_hours[Typical] @ 1dp",                         list("\\b39\\.8\\b"),
  "hours_manual_conservative",    "53.0",      "fig6 source: estimated_manual_hours[Conservative] @ 1dp",                    list("\\b53\\.0\\b", "\\b53\\b"),
  "hours_hybrid_fast",            "19.4",      "fig6 source: estimated_hybrid_hours[Fast] @ 1dp",                            list("\\b19\\.4\\b"),
  "hours_hybrid_typical",         "29.1",      "fig6 source: estimated_hybrid_hours[Typical] @ 1dp",                         list("\\b29\\.1\\b"),
  "hours_hybrid_conservative",    "39.6",      "fig6 source: estimated_hybrid_hours[Conservative] @ 1dp",                    list("\\b39\\.6\\b"),
  "reduction_pct_fast",           "26.9%",     "fig6 source: estimated_reduction_percent[Fast] @ 1dp",                       list("26\\.9% lower"),
  "reduction_pct_typical",        "26.9%",     "fig6 source: estimated_reduction_percent[Typical] @ 1dp",                    list("26\\.9% lower"),
  "reduction_pct_conservative",   "25.2%",     "fig6 source: estimated_reduction_percent[Conservative] @ 1dp",               list("25\\.2% lower"),
  "seconds_substantive_fast",     "60",        "fig6 source: substantive_review_seconds[Fast] (policy input)",               list("\\| Fast \\| 60 \\|", "\\b60 seconds\\b"),
  "seconds_substantive_typical",  "90",        "fig6 source: substantive_review_seconds[Typical] (policy input)",            list("\\| Typical \\| 90 \\|", "\\b90 seconds\\b"),
  "seconds_substantive_conservative","120",    "fig6 source: substantive_review_seconds[Conservative] (policy input)",       list("\\| Conservative \\| 120 \\|", "\\b120 seconds\\b"),
  "seconds_audit_fast",           "20",        "fig6 source: audit_review_seconds[Fast] (policy input)",                     list("\\| Fast \\| 60 \\| 20 \\|", "60 seconds per substantive review and 20 seconds"),
  "seconds_audit_typical",        "30",        "fig6 source: audit_review_seconds[Typical] (policy input)",                  list("\\| Typical \\| 90 \\| 30 \\|", "90 seconds and 30 seconds"),
  "seconds_audit_conservative",   "45",        "fig6 source: audit_review_seconds[Conservative] (policy input)",             list("\\| Conservative \\| 120 \\| 45 \\|", "120 seconds and 45 seconds"),

  # --- Corpus-size lineage (Methods §2.1) ----
  "lineage_raw_records",          "4610",      "config/data_provenance.yml: total_record_count",                             list("4,?610"),
  "lineage_canonical_works",      "4537",      "analysis/data/processed/canonical_works.csv row count",                      list("4,?537"),
  "lineage_savedrecs_per_file_a", "1,000",     "config/data_provenance.yml: export_files[savedrecs.xls].record_count",       list("1,000 \\+ 1,000 \\+ 1,000"),
  "lineage_savedrecs_998",        "998",       "config/data_provenance.yml: export_files[savedrecs_3.xls].record_count",     list("\\b998\\b"),
  "lineage_savedrecs_612",        "612",       "config/data_provenance.yml: export_files[savedrecs_4.xls].record_count",     list("\\b612\\b")
)

## --- Override the registry's hand-typed code_value for display values that
## --- are derived from source CSVs (sanity-check the table at runtime).

override_value <- function(label, value) {
  registry[registry$number_label == label, "code_value"] <<- as.character(value)
}

override_value("corpus_total_rows",            get_partition_val("corpus_total"))
override_value("evidence_level_1",             get_partition_val("evidence_level_1_traditional"))
override_value("evidence_level_2",             get_partition_val("evidence_level_2_human_reviewed"))
override_value("evidence_level_3",             get_partition_val("evidence_level_3_validated_router"))
override_value("evidence_level_4",             get_partition_val("evidence_level_4_hybrid_accepted"))
override_value("evidence_level_5",             get_partition_val("evidence_level_5_unresolved"))
override_value("bibliography_only_rows",       get_partition_val("bibliography_only_rows"))
override_value("needs_human_review_rows",      get_partition_val("review_flag_needs_review"))
override_value("no_review_flag_rows",          get_partition_val("review_flag_no_flag"))
override_value("usable_for_substantive_rows",  get_partition_val("usable_for_substantive_rows"))
override_value("review_burden_substantive",    get_partition_val("substantive_review"))
override_value("review_burden_audit",          get_partition_val("audit_review"))
override_value("review_burden_no_review",      get_partition_val("no_review_required"))
override_value("extraction_recovery_helpful",  paste0(get_validation_val("Extraction Recovery", "k"),  "/", get_validation_val("Extraction Recovery", "n")))
override_value("bibliography_audit_precision", paste0(get_validation_val("Bibliography Audit", "k"),    "/", get_validation_val("Bibliography Audit", "n")))
override_value("router_safe_agreement",        paste0(get_validation_val("Router-Safe Batch A", "k"),   "/", get_validation_val("Router-Safe Batch A", "n")))
override_value("modeling_agreement",           paste0(get_validation_val("Modeling", "k"),              "/", get_validation_val("Modeling", "n")))
override_value("boundary_agreement",           paste0(get_validation_val("Historical/Foundation", "k"), "/", get_validation_val("Historical/Foundation", "n")))
override_value("boundary_rate_pct",            fmt_rate_pct(get_validation_val("Historical/Foundation", "p_hat")))
override_value("ci_extraction_recovery",       sprintf("[%.2f, %.2f]", get_validation_val("Extraction Recovery", "ci_lower"),  get_validation_val("Extraction Recovery", "ci_upper")))
override_value("ci_bibliography_audit",        sprintf("[%.2f, %.2f]", get_validation_val("Bibliography Audit", "ci_lower"),    get_validation_val("Bibliography Audit", "ci_upper")))
override_value("ci_router_safe",               sprintf("[%.2f, %.2f]", get_validation_val("Router-Safe Batch A", "ci_lower"),   get_validation_val("Router-Safe Batch A", "ci_upper")))
override_value("ci_modeling",                  sprintf("[%.2f, %.2f]", get_validation_val("Modeling", "ci_lower"),              get_validation_val("Modeling", "ci_upper")))
override_value("ci_boundary",                  sprintf("[%.2f, %.2f]", get_validation_val("Historical/Foundation", "ci_lower"), get_validation_val("Historical/Foundation", "ci_upper")))
override_value("hours_manual_fast",            fmt_hours(fig6_source$estimated_manual_hours[fig6_source$assumption_set == "Fast"]))
override_value("hours_manual_typical",         fmt_hours(fig6_source$estimated_manual_hours[fig6_source$assumption_set == "Typical"]))
override_value("hours_manual_conservative",    fmt_hours(fig6_source$estimated_manual_hours[fig6_source$assumption_set == "Conservative"]))
override_value("hours_hybrid_fast",            fmt_hours(fig6_source$estimated_hybrid_hours[fig6_source$assumption_set == "Fast"]))
override_value("hours_hybrid_typical",         fmt_hours(fig6_source$estimated_hybrid_hours[fig6_source$assumption_set == "Typical"]))
override_value("hours_hybrid_conservative",    fmt_hours(fig6_source$estimated_hybrid_hours[fig6_source$assumption_set == "Conservative"]))
override_value("reduction_pct_fast",           fmt_rate_pct(fig6_source$estimated_reduction_percent[fig6_source$assumption_set == "Fast"] / 100))
override_value("reduction_pct_typical",        fmt_rate_pct(fig6_source$estimated_reduction_percent[fig6_source$assumption_set == "Typical"] / 100))
override_value("reduction_pct_conservative",   fmt_rate_pct(fig6_source$estimated_reduction_percent[fig6_source$assumption_set == "Conservative"] / 100))

## --- Scan manuscript ---------------------------------------------------------

scan_one <- function(patterns) {
  matched <- sapply(patterns, function(p) grepl(p, manuscript_lines, perl = TRUE))
  if (is.null(dim(matched))) matched <- matrix(matched, nrow = length(manuscript_lines))
  rows <- which(rowSums(matched) > 0L)
  if (!length(rows)) {
    return(list(values = NA_character_, locations = NA_character_, count = 0L))
  }
  found_strings <- vapply(rows, function(i) {
    all_hits <- unlist(lapply(patterns, function(p) {
      m <- regmatches(manuscript_lines[i], gregexpr(p, manuscript_lines[i], perl = TRUE))[[1]]
      if (length(m)) m else character(0)
    }))
    paste(unique(all_hits), collapse = ", ")
  }, character(1))
  list(
    values    = paste(unique(found_strings), collapse = "; "),
    locations = paste(rows, collapse = ", "),
    count     = length(rows)
  )
}

results <- registry %>%
  rowwise() %>%
  mutate(
    scan = list(scan_one(unlist(display_patterns))),
    manuscript_values = scan$values,
    manuscript_line_locations = scan$locations,
    manuscript_occurrence_count = scan$count,
    match = manuscript_occurrence_count > 0L
  ) %>%
  ungroup() %>%
  select(number_label, code_value, code_source,
         manuscript_values, manuscript_line_locations,
         manuscript_occurrence_count, match)

write_csv(results, out_path)

n_match <- sum(results$match)
n_total <- nrow(results)
message("Wrote ", out_path, " (", n_total, " canonical numbers; ",
        n_match, " found in manuscript; ", n_total - n_match,
        " unmatched flagged for review).")
if (n_match < n_total) {
  unmatched <- results$number_label[!results$match]
  message("Unmatched: ", paste(unmatched, collapse = ", "))
}
