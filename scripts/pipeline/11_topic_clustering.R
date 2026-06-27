suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/topic_analysis.R")

paths <- load_paths()
read_or_empty <- function(path) if (file.exists(path) && file.info(path)$size > 0) readr::read_csv(path, show_col_types = FALSE) else tibble::tibble()

works <- read_or_empty(file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv"))
contexts <- read_or_empty(file.path(path_get(paths, "data.processed"), "citation_contexts_enriched.csv"))
if (!"abstract" %in% names(works)) works$abstract <- NA_character_

work_docs <- works %>%
  transmute(doc_id = work_id, text = coalesce(abstract, canonical_title, normalized_title))
context_docs <- contexts %>%
  transmute(doc_id = context_id, text = surrounding_sentence_window)

work_clusters <- build_tfidf_clusters(work_docs, k = 10)
context_clusters <- build_tfidf_clusters(context_docs, k = 8)

out_dir <- path_get(paths, "data.derived")
readr::write_csv(work_clusters$assignments, file.path(out_dir, "topic_clusters_works.csv"))
readr::write_csv(work_clusters$summaries, file.path(path_get(paths, "outputs.tables"), "topic_cluster_summaries_works.csv"))
readr::write_csv(work_clusters$representatives, file.path(path_get(paths, "outputs.tables"), "topic_cluster_representatives_works.csv"))
readr::write_csv(work_clusters$diagnostics, file.path(path_get(paths, "outputs.logs"), "topic_clusters_works_diagnostic.csv"))

readr::write_csv(context_clusters$assignments, file.path(out_dir, "topic_clusters_contexts.csv"))
readr::write_csv(context_clusters$summaries, file.path(path_get(paths, "outputs.tables"), "topic_cluster_summaries_contexts.csv"))
readr::write_csv(context_clusters$representatives, file.path(path_get(paths, "outputs.tables"), "topic_cluster_representatives_contexts.csv"))
readr::write_csv(context_clusters$diagnostics, file.path(path_get(paths, "outputs.logs"), "topic_clusters_contexts_diagnostic.csv"))

message("Wrote lightweight topic cluster outputs.")
