library(testthat)

root <- normalizePath(file.path(getwd(), "../.."), mustWork = TRUE)
source(file.path(root, "scripts/R/metadata_utils.R"))
source(file.path(root, "scripts/R/context_enrichment.R"))
source(file.path(root, "scripts/R/network_analysis.R"))

test_that("DOI normalization removes DOI URL prefixes", {
  expect_equal(normalize_doi("https://doi.org/10.1000/ABC"), "10.1000/abc")
  expect_equal(normalize_doi("doi: 10.1000/ABC"), "10.1000/abc")
})

test_that("title normalization is stable", {
  expect_equal(normalize_title("The Limits-to-Growth!"), "the limits to growth")
})

test_that("reference splitting handles semicolon lists", {
  refs <- split_cited_references("A 1999; B 2000")
  expect_equal(length(refs), 2)
})

test_that("context false-positive risk catches generic limits phrase", {
  expect_equal(false_positive_risk("there are limits to growth in this sample", "LOW_CONFIDENCE"), "high_generic_limits_phrase")
})
