suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(stringr)
})

write_method_tables <- function(metadata, contexts, seed_edges, table_dir, llm = dplyr::tibble(), canonical = dplyr::tibble()) {
  dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
  readr::write_csv(
    tibble::tibble(
      dataset = c("harmonized_records", "canonical_works", "citation_contexts", "seed_citing_documents", "llm_or_fallback_classifications"),
      n = c(nrow(metadata), nrow(canonical), nrow(contexts), nrow(seed_edges), nrow(llm))
    ),
    file.path(table_dir, "pipeline_counts.csv")
  )

  if (nrow(contexts) > 0) {
    contexts %>%
      count(semantic_label, citation_function, sort = TRUE) %>%
      readr::write_csv(file.path(table_dir, "citation_context_functions.csv"))
  }

  if (nrow(llm) > 0) {
    llm %>%
      count(llm_is_seed_work_citation, llm_primary_role, classification_mode, sort = TRUE) %>%
      readr::write_csv(file.path(table_dir, "llm_context_classifications.csv"))
  }
}

write_diffusion_figures <- function(diffusion, figure_dir) {
  dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
  if (nrow(diffusion) == 0 || all(is.na(diffusion$year))) return(invisible(NULL))
  yearly <- diffusion %>%
    filter(!is.na(year)) %>%
    group_by(year) %>%
    summarise(n_citing_works = sum(n_citing_works), .groups = "drop")
  p <- ggplot(yearly, aes(year, n_citing_works)) +
    geom_col(fill = "#2F6F73") +
    labs(x = "Publication year", y = "Works citing Meadows et al. 1972") +
    theme_minimal(base_size = 11)
  ggsave(file.path(figure_dir, "citing_works_by_year.png"), p, width = 7, height = 4, dpi = 300)
}
