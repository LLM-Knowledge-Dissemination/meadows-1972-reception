suppressPackageStartupMessages({
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/metadata_utils.R")
source("scripts/R/external_reconciliation.R")

paths <- load_paths()
works_path <- file.path(path_get(paths, "data.processed"), "canonical_works.csv")
if (!file.exists(works_path)) stop("Run 03_build_canonical_works.R first.", call. = FALSE)

works <- readr::read_csv(works_path, show_col_types = FALSE)
enabled <- identical(tolower(Sys.getenv("MEADOWS_ENABLE_EXTERNAL", "false")), "true")
limit_env <- Sys.getenv("MEADOWS_EXTERNAL_LIMIT", "")
limit <- if (nzchar(limit_env)) as.integer(limit_env) else Inf

out <- reconcile_external_metadata(
  works = works,
  cache_root = file.path(path_get(paths, "data.external"), "api_cache"),
  enabled = enabled,
  limit = limit
)

readr::write_csv(out$enriched, file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv"))
readr::write_csv(out$openalex, file.path(path_get(paths, "data.processed"), "openalex_enrichment.csv"))
readr::write_csv(out$crossref, file.path(path_get(paths, "data.processed"), "crossref_enrichment.csv"))
readr::write_csv(out$log, file.path(path_get(paths, "outputs.logs"), "external_reconciliation_log.csv"))

message("External reconciliation mode: ", ifelse(enabled, "API enabled", "cache/offline only"))
message("Wrote canonical_works_enriched.csv: ", nrow(out$enriched), " rows")
