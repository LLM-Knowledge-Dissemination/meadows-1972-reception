suppressPackageStartupMessages({
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/metadata_utils.R")
source("scripts/R/canonical_works.R")

paths <- load_paths()
metadata_path <- file.path(path_get(paths, "data.processed"), "works_harmonized.csv")
if (!file.exists(metadata_path)) stop("Run 02_harmonize_and_deduplicate.R first.", call. = FALSE)

metadata <- readr::read_csv(metadata_path, show_col_types = FALSE)
out <- build_canonical_works(metadata)

readr::write_csv(out$canonical_works, file.path(path_get(paths, "data.processed"), "canonical_works.csv"))
readr::write_csv(out$duplicate_clusters, file.path(path_get(paths, "data.processed"), "duplicate_clusters.csv"))
readr::write_csv(out$record_map, file.path(path_get(paths, "data.processed"), "work_record_map.csv"))
readr::write_csv(out$ambiguous_matches, file.path(path_get(paths, "data.processed"), "ambiguous_duplicate_matches.csv"))

message("Wrote canonical works: ", nrow(out$canonical_works))
message("Duplicate clusters: ", nrow(out$duplicate_clusters))
message("Ambiguous duplicate candidate pairs: ", nrow(out$ambiguous_matches))
