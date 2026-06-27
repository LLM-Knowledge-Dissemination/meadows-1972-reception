## Wilson score 95% confidence intervals for binomial proportions.
##
## Used by scripts/pipeline/58_validation_intervals.R to compute CIs over the
## five task-specific validation metrics in
## analysis/frozen_methodology/v2_0/validation_summary.csv (read-only frozen
## source of truth). Pure function; no I/O.

#' Wilson score 95% (or other-level) confidence interval for a proportion k/n.
#'
#' Returns the analytic Wilson score interval (Wilson 1927). Preferred over the
#' normal-approximation interval for the small validation samples in this
#' project (n in {11, 20, 24, 28}). Bounded to [0, 1].
#'
#' @param k integer count of successes (0 <= k <= n).
#' @param n integer denominator (n > 0).
#' @param conf confidence level in (0, 1); default 0.95.
#' @return A list with elements p_hat, ci_lower, ci_upper.
wilson_ci <- function(k, n, conf = 0.95) {
  if (length(k) != 1L || length(n) != 1L) {
    stop("wilson_ci is scalar; vectorize with mapply or wilson_ci_df.", call. = FALSE)
  }
  if (!is.numeric(k) || !is.numeric(n) || is.na(k) || is.na(n)) {
    stop("k and n must be non-missing numeric.", call. = FALSE)
  }
  if (n <= 0) stop("n must be > 0.", call. = FALSE)
  if (k < 0 || k > n) stop("k must be in [0, n].", call. = FALSE)
  if (conf <= 0 || conf >= 1) stop("conf must be in (0, 1).", call. = FALSE)

  z <- stats::qnorm(1 - (1 - conf) / 2)
  p_hat <- k / n
  z2 <- z * z
  denom <- 1 + z2 / n
  centre <- (p_hat + z2 / (2 * n)) / denom
  half <- (z * sqrt((p_hat * (1 - p_hat) + z2 / (4 * n)) / n)) / denom

  list(
    p_hat = p_hat,
    ci_lower = max(0, centre - half),
    ci_upper = min(1, centre + half)
  )
}

#' Vectorized data-frame variant: returns a tibble-shaped list with p_hat,
#' ci_lower, ci_upper columns, one row per (k, n) pair.
wilson_ci_df <- function(k, n, conf = 0.95) {
  if (length(k) != length(n)) stop("k and n must have equal length.", call. = FALSE)
  out <- lapply(seq_along(k), function(i) wilson_ci(k[i], n[i], conf = conf))
  list(
    p_hat = vapply(out, `[[`, numeric(1), "p_hat"),
    ci_lower = vapply(out, `[[`, numeric(1), "ci_lower"),
    ci_upper = vapply(out, `[[`, numeric(1), "ci_upper")
  )
}
