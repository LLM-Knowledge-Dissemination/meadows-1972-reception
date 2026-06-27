## Krippendorff's alpha + bootstrap CIs.
##
## Thin wrapper over irr::kripp.alpha that:
##   - exposes a tidy interface (data frame of coder labels per item),
##   - adds a bootstrap 95% CI (resample units),
##   - computes per-class one-vs-rest alpha for nominal axes.
##
## Used by scripts/annotation/03_reliability.R after annotator sheets return.
##
## QUARANTINE REMINDER: this file computes reliability on HUMAN labels only.
## It does not generate labels, does not call any model, and does not look at
## raw context text.

suppressPackageStartupMessages({
  library(irr)
})

#' Compute Krippendorff's alpha on a coder x unit matrix.
#'
#' @param mat numeric/integer matrix, n_coders x n_units, NAs allowed.
#' @param method "nominal" | "ordinal" | "interval" | "ratio".
#' @return list(value, n_units, n_coders, method).
krippendorff_alpha <- function(mat, method = c("nominal", "ordinal", "interval", "ratio")) {
  method <- match.arg(method)
  if (!is.matrix(mat)) mat <- as.matrix(mat)
  res <- irr::kripp.alpha(mat, method = method)
  list(value = res$value, n_units = res$raters * res$subjects / nrow(mat),
       n_coders = res$raters, method = method)
}


#' Bootstrap 95% CI for Krippendorff's alpha by resampling units (columns)
#' with replacement.
#'
#' @param mat coder x unit matrix.
#' @param method as above.
#' @param n_boot number of bootstrap iterations (default 1000).
#' @param conf confidence level (default 0.95).
#' @param seed RNG seed.
#' @return list(point, ci_lower, ci_upper, n_boot, method, n_units_valid).
bootstrap_alpha_ci <- function(mat, method = c("nominal", "ordinal", "interval", "ratio"),
                                n_boot = 1000L, conf = 0.95, seed = 20260625L) {
  method <- match.arg(method)
  if (!is.matrix(mat)) mat <- as.matrix(mat)
  n_units <- ncol(mat)
  point <- irr::kripp.alpha(mat, method = method)$value
  set.seed(seed)
  vals <- numeric(0)
  for (b in seq_len(n_boot)) {
    idx <- sample.int(n_units, n_units, replace = TRUE)
    sub <- mat[, idx, drop = FALSE]
    a <- tryCatch(irr::kripp.alpha(sub, method = method)$value, error = function(e) NA_real_)
    if (!is.na(a) && is.finite(a)) vals <- c(vals, a)
  }
  if (length(vals) < max(20L, n_boot / 10L)) {
    warning("bootstrap_alpha_ci: only ", length(vals), " valid replicates of ", n_boot,
            "; CI may be unreliable")
  }
  q <- stats::quantile(vals, probs = c((1 - conf) / 2, 1 - (1 - conf) / 2),
                       names = FALSE, na.rm = TRUE)
  list(point = point, ci_lower = q[1], ci_upper = q[2],
       n_boot = length(vals), conf = conf, method = method,
       n_units_valid = sum(colSums(!is.na(mat)) >= 2L))
}


#' Per-class one-vs-rest Krippendorff alpha for a nominal axis.
#'
#' For each class level c in the union of observed labels, build a binary
#' matrix (1 if label == c, 0 if label is something else; NA preserved as NA),
#' then compute nominal alpha + bootstrap CI on that binary matrix.
#'
#' @param mat coder x unit integer matrix of nominal labels.
#' @param class_labels optional character vector where names() are the integer
#'   encodings present in mat and values are the human-readable class names.
#'   When supplied, the returned `class` column uses the human names.
#' @param n_boot bootstrap iterations.
#' @param seed RNG seed.
#' @return data frame: class, alpha_point, alpha_ci_lo, alpha_ci_hi, n_units, n_pos.
per_class_one_vs_rest <- function(mat, class_labels = NULL,
                                    n_boot = 1000L, seed = 20260625L) {
  if (!is.matrix(mat)) mat <- as.matrix(mat)
  classes <- sort(unique(as.vector(mat[!is.na(mat)])))
  rows <- list()
  for (cls in classes) {
    bin <- ifelse(is.na(mat), NA_integer_, as.integer(mat == cls))
    a <- bootstrap_alpha_ci(bin, method = "nominal", n_boot = n_boot, seed = seed)
    human_name <- if (!is.null(class_labels) &&
                       as.character(cls) %in% names(class_labels)) {
      class_labels[[as.character(cls)]]
    } else {
      as.character(cls)
    }
    rows[[length(rows) + 1L]] <- data.frame(
      class = human_name,
      alpha_point = a$point,
      alpha_ci_lo = a$ci_lower,
      alpha_ci_hi = a$ci_upper,
      n_units = a$n_units_valid,
      n_pos = sum(bin == 1L, na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  }
  do.call(rbind, rows)
}


#' Categorize an alpha against the project's thresholds.
#' From PILOT_CODEBOOK.md: >=0.80 firm; 0.667..0.80 tentative; <0.667 redo.
alpha_threshold <- function(a) {
  if (is.na(a)) return("NA")
  if (a >= 0.80) return("FIRM (>=0.80)")
  if (a >= 0.667) return("TENTATIVE (0.667-0.80)")
  "BELOW_THRESHOLD (<0.667)"
}
