suppressPackageStartupMessages({
  library(dplyr)
  library(fs)
  library(purrr)
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/citation_contexts.R")

paths <- load_paths()
ensure_project_dirs(paths)

pdfs <- fs::dir_ls(path_get(paths, "data.pdf"), glob = "*.pdf", recurse = FALSE)
if (length(pdfs) == 0) stop("No PDFs found in analysis/data/pdf.", call. = FALSE)

limit <- Sys.getenv("MEADOWS_LIMIT_PDFS", unset = "")
if (nzchar(limit)) pdfs <- head(pdfs, as.integer(limit))

results <- purrr::map_dfr(
  pdfs,
  parse_one_pdf,
  text_dir = path_get(paths, "data.pdf_text"),
  hits_dir = path_get(paths, "data.pdf_hits"),
  log_dir = path_get(paths, "outputs.logs"),
  save_pages = TRUE,
  overwrite = identical(Sys.getenv("MEADOWS_OVERWRITE_HITS"), "true")
)

readr::write_csv(results, file.path(path_get(paths, "outputs.logs"), "context_extraction_summary.csv"))
message("Parsed ", nrow(results), " PDFs.")
