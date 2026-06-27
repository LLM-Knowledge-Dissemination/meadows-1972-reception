suppressPackageStartupMessages({
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/context_enrichment.R")

paths <- load_paths()
contexts_path <- file.path(path_get(paths, "data.processed"), "citation_contexts.csv")
works_path <- file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv")
if (!file.exists(works_path)) works_path <- file.path(path_get(paths, "data.processed"), "canonical_works.csv")

contexts <- readr::read_csv(contexts_path, show_col_types = FALSE)
works <- readr::read_csv(works_path, show_col_types = FALSE)
out <- enrich_citation_contexts(contexts, works)

readr::write_csv(out, file.path(path_get(paths, "data.processed"), "citation_contexts_enriched.csv"))
message("Wrote citation_contexts_enriched.csv: ", nrow(out), " rows")
