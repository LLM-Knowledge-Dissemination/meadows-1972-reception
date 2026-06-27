library(testthat)
suppressPackageStartupMessages(library(irr))

root <- normalizePath(file.path(getwd(), "../.."), mustWork = TRUE)
source(file.path(root, "scripts/R/krippendorff.R"))


## Published worked example: Krippendorff's "C" data (the canonical example
## documented in ?irr::kripp.alpha and reproduced in Krippendorff's textbook
## and Hayes & Krippendorff 2007). Known values are pinned to 4 decimal places.
## These are the values irr 0.84.x emits; if the package implementation drifts,
## this test will catch it before downstream reliability reports are trusted.
make_krippendorff_C <- function() {
  matrix(
    c(1, 1, NA, 1, 2, 2, 3, 2, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 2, 2,
      1, 2, 3, 4, 4, 4, 4, 4, 1, 1, 2, 1, 2, 2, 2, 2, NA, 5, 5, 5,
      NA, NA, 1, 1, NA, NA, 3, NA),
    nrow = 4
  )
}


test_that("krippendorff_alpha reproduces the Krippendorff C data canonical alphas", {
  mat <- make_krippendorff_C()
  expect_equal(krippendorff_alpha(mat, "nominal")$value,  0.7434, tolerance = 1e-3)
  expect_equal(krippendorff_alpha(mat, "ordinal")$value,  0.8154, tolerance = 1e-3)
  expect_equal(krippendorff_alpha(mat, "interval")$value, 0.8491, tolerance = 1e-3)
  expect_equal(krippendorff_alpha(mat, "ratio")$value,    0.7974, tolerance = 1e-3)
})


test_that("krippendorff_alpha is symmetric to row order (coder relabeling)", {
  mat <- make_krippendorff_C()
  v1 <- krippendorff_alpha(mat, "nominal")$value
  v2 <- krippendorff_alpha(mat[c(2, 1, 4, 3), ], "nominal")$value
  expect_equal(v1, v2, tolerance = 1e-12)
})


test_that("krippendorff_alpha equals 1 for perfect agreement", {
  mat <- rbind(c(1, 2, 3, 1, 2, 3),
               c(1, 2, 3, 1, 2, 3),
               c(1, 2, 3, 1, 2, 3))
  expect_equal(krippendorff_alpha(mat, "nominal")$value, 1.0, tolerance = 1e-12)
})


test_that("bootstrap_alpha_ci point matches krippendorff_alpha and brackets it", {
  mat <- make_krippendorff_C()
  res <- bootstrap_alpha_ci(mat, "nominal", n_boot = 200L, seed = 20260625L)
  expect_equal(res$point, 0.7434, tolerance = 1e-3)
  expect_lt(res$ci_lower, res$point + 1e-6)
  expect_gt(res$ci_upper, res$point - 1e-6)
})


test_that("per_class_one_vs_rest emits one row per observed class", {
  mat <- make_krippendorff_C()
  obs_classes <- sort(unique(as.vector(mat[!is.na(mat)])))
  res <- per_class_one_vs_rest(mat, n_boot = 50L)
  expect_equal(nrow(res), length(obs_classes))
  expect_setequal(res$class, as.character(obs_classes))
})


test_that("alpha_threshold maps to the project's three bands", {
  expect_equal(alpha_threshold(0.85), "FIRM (>=0.80)")
  expect_equal(alpha_threshold(0.70), "TENTATIVE (0.667-0.80)")
  expect_equal(alpha_threshold(0.50), "BELOW_THRESHOLD (<0.667)")
})
