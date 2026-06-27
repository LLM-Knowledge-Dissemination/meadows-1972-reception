suppressPackageStartupMessages({
  library(readr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/validation_sampling.R")

paths <- load_paths()
contexts_path <- file.path(path_get(paths, "data.processed"), "citation_contexts_enriched.csv")
if (!file.exists(contexts_path)) contexts_path <- file.path(path_get(paths, "data.processed"), "citation_contexts.csv")
llm_path <- file.path(path_get(paths, "data.llm_output"), "citation_context_classifications.csv")

contexts <- readr::read_csv(contexts_path, show_col_types = FALSE)
llm <- if (file.exists(llm_path) && file.info(llm_path)$size > 0) {
  readr::read_csv(llm_path, show_col_types = FALSE)
} else {
  tibble::tibble()
}

sample <- build_validation_sample(contexts, llm)
out <- file.path(path_get(paths, "data.validation"), "citation_context_validation_sample.csv")
readr::write_csv(sample, out)
message("Wrote validation sample: ", out, " (", nrow(sample), " rows).")
