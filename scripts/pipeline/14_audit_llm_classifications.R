suppressPackageStartupMessages({
  library(readr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/llm_audit.R")

paths <- load_paths()

read_or_empty <- function(path) {
  if (file.exists(path) && file.info(path)$size > 0) readr::read_csv(path, show_col_types = FALSE) else tibble::tibble()
}

llm <- read_or_empty(file.path(path_get(paths, "data.llm_output"), "citation_context_classifications.csv"))
input_rows <- read_or_empty(file.path(path_get(paths, "data.llm_input"), "citation_contexts_for_classification.csv"))
audit <- read_audit_jsonl(file.path(path_get(paths, "outputs.audit"), "llm_classification_audit.jsonl"))

if (nrow(llm) == 0 || nrow(input_rows) == 0) {
  stop("LLM classifications or input snapshot missing; run scripts/pipeline/07_classify_contexts_llm.py first.")
}

out <- build_llm_audit(llm, input_rows, audit)

readr::write_csv(out$joined, file.path(path_get(paths, "outputs.tables"), "llm_classification_audit_joined.csv"))
readr::write_csv(out$summary, file.path(path_get(paths, "outputs.tables"), "llm_test_audit.csv"))
readr::write_csv(out$distributions$confidence, file.path(path_get(paths, "outputs.tables"), "llm_confidence_distribution.csv"))
readr::write_csv(out$distributions$role, file.path(path_get(paths, "outputs.tables"), "llm_role_distribution.csv"))
readr::write_csv(out$distributions$discourse, file.path(path_get(paths, "outputs.tables"), "llm_discourse_distribution.csv"))
readr::write_csv(out$distributions$stance, file.path(path_get(paths, "outputs.tables"), "llm_stance_distribution.csv"))
readr::write_csv(out$distributions$uncertainty_flags, file.path(path_get(paths, "outputs.tables"), "llm_uncertainty_flag_distribution.csv"))
readr::write_csv(out$confusion, file.path(path_get(paths, "outputs.tables"), "llm_fallback_role_confusion.csv"))
readr::write_csv(out$disagreements, file.path(path_get(paths, "data.validation"), "llm_fallback_disagreements.csv"))
readr::write_csv(out$examples, file.path(path_get(paths, "data.validation"), "llm_audit_examples.csv"))

message("Wrote LLM audit outputs.")
