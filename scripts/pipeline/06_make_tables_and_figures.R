suppressPackageStartupMessages({
  library(readr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/report_tables.R")

paths <- load_paths()
read_or_empty <- function(path) if (file.exists(path)) readr::read_csv(path, show_col_types = FALSE) else tibble::tibble()

metadata <- read_or_empty(file.path(path_get(paths, "data.processed"), "works_harmonized.csv"))
contexts <- read_or_empty(file.path(path_get(paths, "data.processed"), "citation_contexts.csv"))
seed_edges <- read_or_empty(file.path(path_get(paths, "data.derived"), "meadows_1972_seed_edges.csv"))
diffusion <- read_or_empty(file.path(path_get(paths, "data.derived"), "diffusion_by_year_venue_type.csv"))
llm <- read_or_empty(file.path(path_get(paths, "data.llm_output"), "citation_context_classifications.csv"))
canonical <- read_or_empty(file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv"))

write_method_tables(metadata, contexts, seed_edges, path_get(paths, "outputs.tables"), llm = llm, canonical = canonical)
write_diffusion_figures(diffusion, path_get(paths, "outputs.figures"))

message("Wrote report tables and figures.")
