#!/usr/bin/env Rscript

## Reliability + disagreement ingest for the pilot annotation round.
##
## Reads the two annotator sheets, joins on item_id, and (if labels are
## present) computes Krippendorff's alpha per axis (function nominal,
## stance ordinal, depth nominal) with bootstrap 95% CIs, plus per-class
## one-vs-rest alphas for the nominal axes. Emits a reliability report
## (Markdown) + a disagreements CSV with an empty adjudication column.
##
## NO-OP GUARD: if BOTH sheets have all label columns blank (the state
## immediately after sheets are generated), the script exits cleanly
## with a status message — nothing computed, nothing claimed.
##
## QUARANTINE REMINDER: no LLM is invoked here either. The script only
## reads human-entered labels from CSVs.
##
## Inputs:
##   analysis/annotation/sheets/annotator_A.csv
##   analysis/annotation/sheets/annotator_B.csv
##
## Outputs (when labels are present):
##   analysis/annotation/reliability_report.md
##   analysis/annotation/disagreements.csv
##
## CLI override for the fixture mode:
##   Rscript scripts/annotation/03_reliability.R --fixture
## reads from analysis/annotation/fixtures/sheet_A.csv and sheet_B.csv
## instead, and writes outputs to analysis/annotation/fixtures/.

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(tidyr)
})

root <- normalizePath(getwd(), mustWork = TRUE)
source(file.path(root, "scripts/R/krippendorff.R"))

LABEL_COLS <- c("function", "stance", "depth", "flag", "notes")
SCORED_AXES <- list(
  list(name = "function", method = "nominal"),
  list(name = "stance",   method = "ordinal",
       order = c("Negative", "Neutral", "Positive")),
  list(name = "depth",    method = "nominal")
)
N_BOOT <- 1000L
BOOT_SEED <- 20260625L

args <- commandArgs(trailingOnly = TRUE)
fixture_mode <- any(args == "--fixture")

if (fixture_mode) {
  in_dir  <- file.path(root, "analysis", "annotation", "fixtures")
  sheet_a_path <- file.path(in_dir, "sheet_A.csv")
  sheet_b_path <- file.path(in_dir, "sheet_B.csv")
  out_dir <- in_dir
  cat("[fixture mode] reading from", in_dir, "\n")
} else {
  in_dir <- file.path(root, "analysis", "annotation", "sheets")
  sheet_a_path <- file.path(in_dir, "annotator_A.csv")
  sheet_b_path <- file.path(in_dir, "annotator_B.csv")
  out_dir <- file.path(root, "analysis", "annotation")
}
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
report_path <- file.path(out_dir, "reliability_report.md")
disagreements_path <- file.path(out_dir, "disagreements.csv")


## ---- read sheets (skip the 4-line header note + blank line) -------------
read_sheet <- function(path) {
  if (!file.exists(path)) stop("missing sheet: ", path)
  lines <- readLines(path)
  ## Find the CSV header row (starts with "item_id,")
  hdr_idx <- which(startsWith(lines, "item_id,"))[1]
  if (is.na(hdr_idx)) stop("could not find 'item_id,' header row in ", path)
  body <- paste(lines[hdr_idx:length(lines)], collapse = "\n")
  readr::read_csv(I(body), show_col_types = FALSE)
}

sheet_a <- read_sheet(sheet_a_path)
sheet_b <- read_sheet(sheet_b_path)
cat("loaded annotator A:", nrow(sheet_a), "rows; annotator B:", nrow(sheet_b), "rows\n")

## ---- NO-OP GUARD: all labels blank? -------------------------------------
all_blank <- function(df) {
  for (c in LABEL_COLS[1:3]) {  # function, stance, depth
    vals <- df[[c]]
    if (is.null(vals)) next
    if (any(!is.na(vals) & vals != "")) return(FALSE)
  }
  TRUE
}

if (all_blank(sheet_a) && all_blank(sheet_b)) {
  cat("\nBOTH annotator sheets have all label cells blank.\n")
  cat("No reliability computed; no outputs written. Re-run after sheets are returned.\n")
  cat("\n(This is the expected state immediately after 02_make_sheets.py.)\n")
  quit(status = 0)
}


## ---- pair items by item_id ----------------------------------------------
joined <- dplyr::inner_join(
  sheet_a |> select(item_id, dplyr::any_of(LABEL_COLS)),
  sheet_b |> select(item_id, dplyr::any_of(LABEL_COLS)),
  by = "item_id",
  suffix = c("_A", "_B")
)
cat("paired", nrow(joined), "items via item_id\n")

if (nrow(joined) == 0) {
  stop("no item_id overlap between sheets — check inputs")
}


## ---- Krippendorff per axis ----------------------------------------------
encode_axis <- function(col_a, col_b, ax) {
  if (ax$method == "ordinal" && !is.null(ax$order)) {
    lvl_to_int <- setNames(seq_along(ax$order), ax$order)
    a <- lvl_to_int[as.character(col_a)]
    b <- lvl_to_int[as.character(col_b)]
  } else {
    ## nominal: arbitrary numeric encoding (kripp.alpha treats them as labels)
    obs <- unique(c(as.character(col_a), as.character(col_b)))
    obs <- obs[!is.na(obs) & obs != ""]
    obs <- sort(obs)
    if (length(obs) == 0) return(NULL)
    lvl_to_int <- setNames(seq_along(obs), obs)
    a <- lvl_to_int[as.character(col_a)]
    b <- lvl_to_int[as.character(col_b)]
  }
  a[is.na(col_a) | col_a == ""] <- NA_integer_
  b[is.na(col_b) | col_b == ""] <- NA_integer_
  mat <- rbind(as.integer(a), as.integer(b))
  ## drop columns where BOTH are NA — kripp.alpha doesn't accept those
  keep <- colSums(!is.na(mat)) >= 1L
  ## Return both matrix and int->label decoder so per_class one-vs-rest can
  ## use human-readable class names in the report.
  int_to_label <- setNames(names(lvl_to_int), as.character(unname(lvl_to_int)))
  list(mat = mat[, keep, drop = FALSE], int_to_label = int_to_label)
}

per_axis_rows <- list()
per_class_rows <- list()

for (ax in SCORED_AXES) {
  ca <- joined[[paste0(ax$name, "_A")]]
  cb <- joined[[paste0(ax$name, "_B")]]
  if (is.null(ca) || is.null(cb)) next
  enc <- encode_axis(ca, cb, ax)
  if (is.null(enc) || ncol(enc$mat) == 0L) next
  mat <- enc$mat
  int_to_label <- enc$int_to_label
  ## Restrict to units where BOTH coders entered a label, otherwise the
  ## alpha is undefined for that unit pair.
  both_valid <- colSums(!is.na(mat)) == 2L
  mat_pair <- mat[, both_valid, drop = FALSE]
  if (ncol(mat_pair) < 2L) {
    per_axis_rows[[length(per_axis_rows) + 1L]] <- data.frame(
      axis = ax$name, method = ax$method,
      n_units_both_labeled = ncol(mat_pair),
      alpha_point = NA_real_, alpha_ci_lo = NA_real_, alpha_ci_hi = NA_real_,
      threshold = "INSUFFICIENT_DATA"
    )
    next
  }
  ci <- bootstrap_alpha_ci(mat_pair, method = ax$method, n_boot = N_BOOT, seed = BOOT_SEED)
  per_axis_rows[[length(per_axis_rows) + 1L]] <- data.frame(
    axis = ax$name, method = ax$method,
    n_units_both_labeled = ncol(mat_pair),
    alpha_point = round(ci$point, 4),
    alpha_ci_lo = round(ci$ci_lower, 4),
    alpha_ci_hi = round(ci$ci_upper, 4),
    threshold = alpha_threshold(ci$point)
  )
  if (ax$method == "nominal") {
    pc <- per_class_one_vs_rest(mat_pair, class_labels = int_to_label,
                                  n_boot = N_BOOT, seed = BOOT_SEED)
    pc$axis <- ax$name
    per_class_rows[[length(per_class_rows) + 1L]] <- pc
  }
}

per_axis_tbl <- do.call(rbind, per_axis_rows)
per_class_tbl <- if (length(per_class_rows)) do.call(rbind, per_class_rows) else NULL


## ---- Disagreement table -------------------------------------------------
disagree_rows <- joined |>
  rowwise() |>
  mutate(
    function_disagree = isTRUE(!is.na(`function_A`) && !is.na(`function_B`) &&
                                `function_A` != `function_B`),
    stance_disagree   = isTRUE(!is.na(`stance_A`) && !is.na(`stance_B`) &&
                                `stance_A` != `stance_B`),
    depth_disagree    = isTRUE(!is.na(`depth_A`) && !is.na(`depth_B`) &&
                                `depth_A` != `depth_B`),
    any_disagree = function_disagree | stance_disagree | depth_disagree
  ) |>
  ungroup() |>
  filter(any_disagree) |>
  mutate(adjudicated_function = "",
         adjudicated_stance   = "",
         adjudicated_depth    = "",
         adjudication_notes   = "")


## ---- Write report + disagreements --------------------------------------
write_report <- function(per_axis_tbl, per_class_tbl, n_disagree, n_paired, path) {
  lines <- character(0)
  lines <- c(lines,
             "# Pilot reliability report",
             "",
             paste0("**Paired items (both annotators returned the sheet for the same item):** ",
                    n_paired),
             paste0("**Items with at least one disagreement on function / stance / depth:** ",
                    n_disagree, "  (see `disagreements.csv`)"),
             paste0("**Bootstrap iterations:** ", N_BOOT, "; **seed:** ", BOOT_SEED),
             "",
             "**Thresholds** (from `docs/annotation/PILOT_CODEBOOK.md` §10):",
             "- >= 0.80 → firm",
             "- 0.667–0.80 → tentative",
             "- < 0.667 → axis revised / re-piloted",
             "",
             "## Per-axis alpha",
             "",
             "| Axis | Method | n (both labeled) | α (point) | 95% bootstrap CI | Threshold |",
             "|---|---|---:|---:|---|---|")
  for (i in seq_len(nrow(per_axis_tbl))) {
    r <- per_axis_tbl[i, ]
    ci <- if (!is.na(r$alpha_ci_lo)) sprintf("[%.3f, %.3f]", r$alpha_ci_lo, r$alpha_ci_hi) else "—"
    pt <- if (!is.na(r$alpha_point)) sprintf("%.3f", r$alpha_point) else "—"
    lines <- c(lines, sprintf("| %s | %s | %d | %s | %s | %s |",
                               r$axis, r$method, r$n_units_both_labeled, pt, ci, r$threshold))
  }
  if (!is.null(per_class_tbl) && nrow(per_class_tbl)) {
    lines <- c(lines, "",
               "## Per-class one-vs-rest alpha (nominal axes)",
               "",
               "| Axis | Class | α (point) | 95% bootstrap CI | n units | n positive |",
               "|---|---|---:|---|---:|---:|")
    for (i in seq_len(nrow(per_class_tbl))) {
      r <- per_class_tbl[i, ]
      ci <- sprintf("[%.3f, %.3f]", r$alpha_ci_lo, r$alpha_ci_hi)
      lines <- c(lines, sprintf("| %s | %s | %.3f | %s | %d | %d |",
                                 r$axis, r$class, r$alpha_point, ci, r$n_units, r$n_pos))
    }
  }
  lines <- c(lines,
             "",
             "## Notes",
             "",
             "- α computed with `irr::kripp.alpha`. Wrapper + bootstrap in `scripts/R/krippendorff.R`. Unit-tested against the canonical Krippendorff C example (nominal α = 0.7434).",
             "- Bootstrap CI: resamples units (columns) with replacement, n_boot iterations, reports the 2.5%–97.5% percentile interval.",
             "- One-vs-rest per-class alpha is reported only for nominal axes (function, depth). For stance (ordinal) the per-axis ordinal α is the relevant summary.",
             "- Items with only one annotator's label on an axis are excluded from that axis's α denominator (kripp.alpha cannot use single-coder units for pair reliability).",
             "")
  writeLines(lines, path)
}

write_report(per_axis_tbl, per_class_tbl, nrow(disagree_rows), nrow(joined), report_path)
cat("wrote", report_path, "\n")

if (nrow(disagree_rows) > 0) {
  out_cols <- c("item_id",
                "function_A", "function_B",
                "stance_A",   "stance_B",
                "depth_A",    "depth_B",
                "flag_A",     "flag_B",
                "notes_A",    "notes_B",
                "function_disagree", "stance_disagree", "depth_disagree",
                "adjudicated_function", "adjudicated_stance", "adjudicated_depth",
                "adjudication_notes")
  readr::write_csv(disagree_rows[, intersect(out_cols, names(disagree_rows))],
                    disagreements_path)
} else {
  cat("(no disagreements to write)\n")
}
cat("done.\n")
