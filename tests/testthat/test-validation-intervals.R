library(testthat)

root <- normalizePath(file.path(getwd(), "../.."), mustWork = TRUE)
source(file.path(root, "scripts/R/validation_intervals.R"))

test_that("wilson_ci returns p_hat exactly k/n", {
  ci <- wilson_ci(16, 20)
  expect_equal(ci$p_hat, 0.8)
})

test_that("wilson_ci matches published Wilson 95% bounds for Bibliography 16/20", {
  ci <- wilson_ci(16, 20, conf = 0.95)
  expect_equal(ci$ci_lower, 0.5839, tolerance = 1e-3)
  expect_equal(ci$ci_upper, 0.9193, tolerance = 1e-3)
})

test_that("wilson_ci matches published Wilson 95% bounds for Historical 15/28", {
  ci <- wilson_ci(15, 28, conf = 0.95)
  expect_equal(ci$ci_lower, 0.3581, tolerance = 1e-3)
  expect_equal(ci$ci_upper, 0.7047, tolerance = 1e-3)
})

test_that("wilson_ci handles boundary k=0 and k=n without going outside [0,1]", {
  zero <- wilson_ci(0, 11)
  full <- wilson_ci(11, 11)
  expect_equal(zero$p_hat, 0)
  expect_equal(zero$ci_lower, 0)
  expect_gt(zero$ci_upper, 0)
  expect_equal(full$p_hat, 1)
  expect_lt(full$ci_lower, 1)
  expect_equal(full$ci_upper, 1)
})

test_that("wilson_ci rejects invalid inputs", {
  expect_error(wilson_ci(5, 0))
  expect_error(wilson_ci(-1, 10))
  expect_error(wilson_ci(11, 10))
  expect_error(wilson_ci(5, 10, conf = 0))
  expect_error(wilson_ci(5, 10, conf = 1))
  expect_error(wilson_ci(NA_real_, 10))
})

test_that("wilson_ci_df vectorizes over k and n", {
  res <- wilson_ci_df(c(16, 8), c(20, 11))
  expect_equal(length(res$p_hat), 2L)
  expect_equal(res$p_hat[1], 0.8)
  expect_equal(res$p_hat[2], 8 / 11)
  expect_error(wilson_ci_df(c(1, 2), 10))
})
