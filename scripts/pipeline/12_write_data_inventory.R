suppressPackageStartupMessages({
  library(dplyr)
  library(fs)
  library(readr)
  library(stringr)
})

source("scripts/helpers/project_paths.R")

paths <- load_paths()
root <- get_project_root()
files <- fs::dir_ls(file.path(root, "analysis"), recurse = TRUE, type = "file")

classify_role <- function(path) {
  rel <- fs::path_rel(path, root)
  case_when(
    str_detect(rel, "analysis/data/rawData|analysis/data/raw/") ~ "source_raw",
    str_detect(rel, "analysis/data/pdf/|analysis/data/ntrl/") ~ "source_full_text_or_pdf",
    str_detect(rel, "analysis/data/interim/") ~ "intermediate",
    str_detect(rel, "analysis/data/processed/") ~ "processed",
    str_detect(rel, "analysis/data/derived/") ~ "derived_analysis",
    str_detect(rel, "analysis/data/external/") ~ "external_cache",
    str_detect(rel, "analysis/data/llm_") ~ "llm_input_output",
    str_detect(rel, "analysis/figures|analysis/tables|analysis/reports") ~ "report_output",
    str_detect(rel, "analysis/validation") ~ "validation",
    str_detect(rel, "analysis/logs|analysis/audit") ~ "log_or_audit",
    TRUE ~ "other"
  )
}

inventory <- tibble(path = fs::path_rel(files, root)) %>%
  mutate(
    role = classify_role(file.path(root, path)),
    extension = tools::file_ext(path),
    size_bytes = file.info(file.path(root, path))$size,
    modified_at = as.character(file.info(file.path(root, path))$mtime),
    tracked_recommendation = case_when(
      role %in% c("source_raw", "validation") & size_bytes < 5000000 ~ "consider_tracking_or_documenting",
      role %in% c("source_full_text_or_pdf", "external_cache") ~ "usually_do_not_track_large_or_copyrighted_files",
      role %in% c("processed", "derived_analysis", "report_output", "log_or_audit", "llm_input_output") ~ "generated_reproducible_output",
      TRUE ~ "review"
    )
  ) %>%
  arrange(role, path)

readr::write_csv(inventory, file.path(root, "analysis", "data_inventory.csv"))
message("Wrote analysis/data_inventory.csv: ", nrow(inventory), " files")
