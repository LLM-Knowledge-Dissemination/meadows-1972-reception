suppressPackageStartupMessages({
  library(dplyr)
  library(fs)
  library(purrr)
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/metadata_utils.R")

paths <- load_paths()
ensure_project_dirs(paths)

raw_dirs <- c(path_get(paths, "data.raw"), path_get(paths, "data.legacy_raw"))
raw_files <- raw_dirs[dir.exists(raw_dirs)] %>%
  purrr::map(~ fs::dir_ls(.x, regexp = "\\.(xls|xlsx|csv|tsv)$", recurse = FALSE)) %>%
  unlist(use.names = FALSE) %>%
  unique() %>%
  discard(~ fs::path_file(.x) %in% c("fail_log.csv"))

if (length(raw_files) == 0) stop("No raw bibliographic files found.", call. = FALSE)

metadata_raw <- purrr::map_dfr(raw_files, function(f) {
  read_bibliographic_file(f) %>%
    mutate(across(everything(), as.character)) %>%
    mutate(source_file = fs::path_file(f), source_path = f, .before = 1)
})

out <- fs::path(path_get(paths, "data.interim"), "metadata_raw.csv")
readr::write_csv(metadata_raw, out)
message("Wrote ", out, " (", nrow(metadata_raw), " rows).")
