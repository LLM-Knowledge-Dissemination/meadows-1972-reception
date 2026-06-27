suppressPackageStartupMessages({
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/validation_compare.R")

paths <- load_paths()
sample_path <- file.path(path_get(paths, "data.validation"), "citation_context_validation_sample.csv")
sample <- readr::read_csv(sample_path, show_col_types = FALSE)
out <- compare_validation_labels(sample)

readr::write_csv(out$summary, file.path(path_get(paths, "outputs.tables"), "validation_summary.csv"))
readr::write_csv(out$disagreements, file.path(path_get(paths, "data.validation"), "validation_disagreements.csv"))
readr::write_csv(out$confusion, file.path(path_get(paths, "outputs.tables"), "validation_confusion_matrices.csv"))
readr::write_csv(out$metrics, file.path(path_get(paths, "outputs.tables"), "validation_precision_recall.csv"))
readr::write_csv(out$fallback_llm_summary, file.path(path_get(paths, "outputs.tables"), "validation_fallback_llm_summary.csv"))
readr::write_csv(out$fallback_llm_confusion, file.path(path_get(paths, "outputs.tables"), "validation_fallback_llm_confusion.csv"))
readr::write_csv(out$human_fallback_confusion, file.path(path_get(paths, "outputs.tables"), "validation_human_fallback_confusion.csv"))
readr::write_csv(out$human_fallback_metrics, file.path(path_get(paths, "outputs.tables"), "validation_human_fallback_precision_recall.csv"))

message("Wrote validation comparison outputs.")
