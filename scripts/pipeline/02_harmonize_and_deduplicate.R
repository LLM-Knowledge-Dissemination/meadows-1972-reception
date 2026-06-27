suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/metadata_utils.R")

paths <- load_paths()
input <- file.path(path_get(paths, "data.interim"), "metadata_raw.csv")
if (!file.exists(input)) stop("Run 01_ingest_raw_metadata.R first.", call. = FALSE)

metadata_raw <- readr::read_csv(input, show_col_types = FALSE)

metadata <- split(metadata_raw, metadata_raw$source_file) %>%
  lapply(function(df) harmonize_metadata(df, source_file = df$source_file[[1]])) %>%
  bind_rows() %>%
  deduplicate_works()

readr::write_csv(metadata, file.path(path_get(paths, "data.processed"), "works_harmonized.csv"))
readr::write_csv(metadata %>% filter(is_duplicate), file.path(path_get(paths, "data.processed"), "works_potential_duplicates.csv"))

message("Wrote harmonized metadata: ", nrow(metadata), " rows; ", sum(metadata$is_duplicate, na.rm = TRUE), " potential duplicates.")
