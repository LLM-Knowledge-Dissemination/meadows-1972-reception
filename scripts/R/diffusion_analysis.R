suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(stringr)
  library(tidyr)
})

decade <- function(year) {
  ifelse(is.na(year), NA_integer_, floor(as.integer(year) / 10) * 10)
}

build_diffusion_tables <- function(works, contexts, llm = tibble()) {
  for (nm in c("openalex_concepts", "openalex_institutions", "openalex_countries")) {
    if (!nm %in% names(works)) works[[nm]] <- NA_character_
  }
  if (!"context_id" %in% names(llm)) llm$context_id <- character()
  context_roles <- contexts %>%
    mutate(context_id = coalesce(context_id, hit_id, snippet_hash)) %>%
    left_join(llm %>% distinct(context_id, .keep_all = TRUE) %>% select(context_id, starts_with("llm_")), by = "context_id") %>%
    mutate(
      role = coalesce(llm_primary_role, citation_function),
      stance = coalesce(llm_stance_toward_meadows, llm_stance_toward_seed),
      decade = decade(year)
    )

  works_fields <- works %>%
    select(work_id, year, openalex_concepts) %>%
    filter(!is.na(openalex_concepts), openalex_concepts != "") %>%
    separate_rows(openalex_concepts, sep = "\\s*\\|\\s*") %>%
    mutate(
      field = str_trim(openalex_concepts),
      decade = decade(year)
    ) %>%
    filter(field != "")

  context_fields <- context_roles %>%
    left_join(works_fields %>% select(work_id, field), by = "work_id", relationship = "many-to-many")

  list(
    yearly_citation_growth = works %>% count(year, name = "n_citing_works") %>% arrange(year),
    citation_growth_by_decade = works %>% mutate(decade = decade(year)) %>% count(decade, name = "n_citing_works") %>% arrange(decade),
    top_venues = works %>% count(venue, sort = TRUE, name = "n_citing_works") %>% filter(!is.na(venue), venue != ""),
    top_venues_by_decade = works %>% mutate(decade = decade(year)) %>% count(decade, venue, sort = TRUE, name = "n_citing_works") %>% filter(!is.na(venue), venue != ""),
    document_types = works %>% count(document_type, sort = TRUE, name = "n_citing_works"),
    field_concept_diffusion = works %>%
      select(work_id, year, openalex_concepts) %>%
      filter(!is.na(openalex_concepts), openalex_concepts != "") %>%
      separate_rows(openalex_concepts, sep = "\\s*\\|\\s*") %>%
      mutate(decade = decade(year)) %>%
      count(decade, openalex_concepts, sort = TRUE, name = "n_works"),
    works_by_field = works_fields %>% count(field, sort = TRUE, name = "n_works"),
    works_by_field_decade = works_fields %>% count(decade, field, sort = TRUE, name = "n_works"),
    citation_contexts_by_field = context_fields %>% filter(!is.na(field)) %>% count(field, mention_type, sort = TRUE, name = "n_contexts"),
    citation_roles_by_field = context_fields %>% filter(!is.na(field)) %>% count(field, role, sort = TRUE, name = "n_contexts"),
    institutional_diffusion = works %>%
      select(work_id, year, openalex_institutions) %>%
      filter(!is.na(openalex_institutions), openalex_institutions != "") %>%
      separate_rows(openalex_institutions, sep = "\\s*\\|\\s*") %>%
      mutate(decade = decade(year)) %>%
      count(decade, openalex_institutions, sort = TRUE, name = "n_works"),
    country_diffusion = works %>%
      select(work_id, year, openalex_countries) %>%
      filter(!is.na(openalex_countries), openalex_countries != "") %>%
      separate_rows(openalex_countries, sep = "\\s*\\|\\s*") %>%
      mutate(decade = decade(year)) %>%
      count(decade, openalex_countries, sort = TRUE, name = "n_works"),
    citation_roles_over_time = context_roles %>% count(decade, role, mention_type, name = "n_contexts") %>% arrange(decade, desc(n_contexts)),
    stance_over_time = context_roles %>% count(decade, stance, name = "n_contexts") %>% arrange(decade, desc(n_contexts)),
    body_vs_bibliography_trends = context_roles %>% count(decade, mention_type, name = "n_contexts") %>% arrange(decade, mention_type)
  )
}

write_diffusion_outputs <- function(tables, table_dir, figure_dir) {
  dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)
  dir.create(figure_dir, recursive = TRUE, showWarnings = FALSE)
  for (nm in names(tables)) readr::write_csv(tables[[nm]], file.path(table_dir, paste0(nm, ".csv")))

  yearly <- tables$yearly_citation_growth %>% filter(!is.na(year))
  if (nrow(yearly) > 0) {
    p <- ggplot(yearly, aes(year, n_citing_works)) +
      geom_col(fill = "#2F6F73") +
      theme_minimal(base_size = 11) +
      labs(x = "Year", y = "Citing works", title = "Meadows 1972 citing works by year")
    ggsave(file.path(figure_dir, "yearly_citation_growth.png"), p, width = 7, height = 4, dpi = 300)
  }

  roles <- tables$citation_roles_over_time %>% filter(!is.na(decade), !is.na(role), role != "")
  if (nrow(roles) > 0) {
    p <- ggplot(roles, aes(decade, n_contexts, fill = role)) +
      geom_col() +
      theme_minimal(base_size = 10) +
      labs(x = "Decade", y = "Citation contexts", fill = "Role", title = "Citation-context roles over time")
    ggsave(file.path(figure_dir, "citation_roles_over_time.png"), p, width = 8, height = 5, dpi = 300)
  }
}
