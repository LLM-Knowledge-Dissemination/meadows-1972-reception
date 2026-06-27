#!/usr/bin/env Rscript

## Computes Wilson score 95% CIs for the five task-specific validation metrics
## in analysis/frozen_methodology/v2_0/validation_summary.csv (frozen, read-only)
## and writes analysis/results/validation_intervals.csv.
##
## Extraction Recovery has agreement_count == "not_applicable"; its primary
## metric is helpfulness (helpful_count / reviewed_rows) and is labeled
## metric_type = "helpfulness". Bibliography Audit is labeled "precision".
## The other three rows are agreement rates.

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
})

set.seed(42L)  ## no stochastic computation here; set for reproducibility hygiene

root <- normalizePath(getwd(), mustWork = TRUE)
frozen_path <- file.path(
  root,
  "analysis", "frozen_methodology", "v2_0", "validation_summary.csv"
)
out_dir <- file.path(root, "analysis", "results")
out_path <- file.path(out_dir, "validation_intervals.csv")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

source(file.path(root, "scripts", "R", "validation_intervals.R"))

summary_raw <- read_csv(frozen_path, show_col_types = FALSE)

## Per-task input table. Each row pulls (k, n) directly from
## validation_summary.csv except Extraction Recovery, whose numerator
## (helpful_count = 10) is in the primary_metric narrative column.
inputs <- tibble::tribble(
  ~validation_area,        ~metric_type,    ~k_source_field,            ~n_source_field,
  "Historical/Foundation", "agreement",     "agreement_count",          "reviewed_rows",
  "Modeling",              "agreement",     "agreement_count",          "reviewed_rows",
  "Router-Safe Batch A",   "agreement",     "agreement_count",          "reviewed_rows",
  "Bibliography Audit",    "precision",     "agreement_count",          "reviewed_rows",
  "Extraction Recovery",   "helpfulness",   "helpful_from_primary_metric", "reviewed_rows"
)

helpful_from_primary <- function(s) {
  ## primary_metric for Extraction Recovery is e.g. "helpful 10/11; ..."
  m <- regmatches(s, regexpr("helpful\\s+\\d+/\\d+", s, ignore.case = TRUE))
  if (length(m) != 1L) stop("Could not parse helpfulness from: ", s, call. = FALSE)
  parts <- as.integer(strsplit(sub("(?i)helpful\\s+", "", m, perl = TRUE), "/")[[1]])
  list(k = parts[1], n = parts[2])
}

resolved <- vector("list", nrow(inputs))
for (i in seq_len(nrow(inputs))) {
  area <- inputs$validation_area[i]
  row <- summary_raw[summary_raw$validation_area == area, ]
  if (nrow(row) != 1L) {
    stop("validation_summary.csv row missing/duplicated for area: ", area, call. = FALSE)
  }
  n <- suppressWarnings(as.integer(row$reviewed_rows))
  if (inputs$k_source_field[i] == "helpful_from_primary_metric") {
    parsed <- helpful_from_primary(row$primary_metric)
    k <- parsed$k
    n_parsed <- parsed$n
    if (!is.na(n_parsed) && n_parsed != n) {
      stop(
        "Extraction Recovery primary_metric n (", n_parsed,
        ") disagrees with reviewed_rows (", n, "); investigate before computing CI.",
        call. = FALSE
      )
    }
  } else {
    k <- suppressWarnings(as.integer(row[[inputs$k_source_field[i]]]))
  }
  ci <- wilson_ci(k, n, conf = 0.95)
  resolved[[i]] <- tibble(
    validation_area = area,
    metric_type = inputs$metric_type[i],
    k = k,
    n = n,
    p_hat = ci$p_hat,
    ci_lower = ci$ci_lower,
    ci_upper = ci$ci_upper,
    ci_method = "Wilson score (1927) two-sided 95%"
  )
}

out <- bind_rows(resolved)

stopifnot(nrow(out) == 5L)
stopifnot(all(!is.na(out$p_hat)))
stopifnot(all(out$ci_lower >= 0 & out$ci_upper <= 1))

write_csv(out, out_path)

message("Wrote ", out_path, " (", nrow(out), " rows).")
