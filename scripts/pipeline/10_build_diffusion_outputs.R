suppressPackageStartupMessages({
  library(readr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/diffusion_analysis.R")

paths <- load_paths()
read_or_empty <- function(path) if (file.exists(path) && file.info(path)$size > 0) readr::read_csv(path, show_col_types = FALSE) else tibble::tibble()

works <- read_or_empty(file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv"))
contexts <- read_or_empty(file.path(path_get(paths, "data.processed"), "citation_contexts_enriched.csv"))
llm <- read_or_empty(file.path(path_get(paths, "data.llm_output"), "citation_context_classifications.csv"))

tables <- build_diffusion_tables(works, contexts, llm)
write_diffusion_outputs(tables, path_get(paths, "outputs.tables"), path_get(paths, "outputs.figures"))

message("Wrote diffusion tables and figures.")
