suppressPackageStartupMessages({
  library(digest)
  library(dplyr)
  library(fs)
  library(purrr)
  library(readr)
  library(stringr)
})

source("scripts/helpers/project_paths.R")

paths <- load_paths()
hit_files <- fs::dir_ls(path_get(paths, "data.pdf_hits"), glob = "*_hits.csv", recurse = FALSE)

contexts <- purrr::map_dfr(hit_files, function(f) {
  df <- tryCatch(readr::read_csv(f, show_col_types = FALSE), error = function(e) tibble::tibble())
  if (nrow(df) == 0) return(tibble::tibble())
  if (!"source_document_id" %in% names(df)) df$source_document_id <- NA_character_
  if (!"pdf_base" %in% names(df)) df$pdf_base <- NA_character_
  if (!"htid" %in% names(df)) df$htid <- NA_character_
  if (!"snippet_hash" %in% names(df)) df$snippet_hash <- NA_character_
  df %>%
    mutate(
      hits_file = fs::path_file(f),
      source_document_id = coalesce(source_document_id, pdf_base, htid, fs::path_ext_remove(fs::path_file(f)) %>% str_remove("_hits$")),
      snippet_norm = str_squish(str_to_lower(snippet)),
      snippet_hash = if_else(
        is.na(snippet_hash),
        vapply(snippet_norm, digest, character(1), algo = "xxhash64"),
        as.character(snippet_hash)
      )
    )
})

if (!"semantic_label" %in% names(contexts)) contexts$semantic_label <- NA_character_
if (!"citation_section" %in% names(contexts)) contexts$citation_section <- NA_character_
if (!"citation_function" %in% names(contexts)) contexts$citation_function <- NA_character_
if (!"citation_position" %in% names(contexts)) contexts$citation_position <- NA_character_
if (!"label" %in% names(contexts)) contexts$label <- NA_character_
if (!"is_biblio_any" %in% names(contexts)) contexts$is_biblio_any <- FALSE

contexts <- contexts %>%
  mutate(
    semantic_label = case_when(
      !is.na(semantic_label) ~ semantic_label,
      label == "MEADOWS_CITATION" ~ "MEADOWS_1972_BOOK",
      label == "CANONICAL_LTG_CONCEPT" ~ "LIMITS_TO_GROWTH_DISCOURSE",
      label == "LTG_MENTION_WEAK" ~ "LOW_CONFIDENCE",
      TRUE ~ "LOW_CONFIDENCE"
    ),
    citation_section = case_when(
      !is.na(citation_section) ~ citation_section,
      citation_position %in% c("BODY", "BIBLIO") ~ citation_position,
      is_biblio_any ~ "BIBLIO",
      TRUE ~ "BODY"
    ),
    citation_function = case_when(
      !is.na(citation_function) ~ citation_function,
      str_detect(str_to_lower(snippet), "\\b(critique|criticis|refut|controvers|wrong|failed|debate)\\b") ~ "critique",
      str_detect(str_to_lower(snippet), "\\b(model|models|simulation|system\\s+dynamics|world3|scenario|forecast)\\b") ~ "modeling_simulation_reference",
      str_detect(str_to_lower(snippet), "\\b(policy|governance|planning|regulation|sustainable\\s+development)\\b") ~ "policy_governance_framing",
      str_detect(str_to_lower(snippet), "\\b(historical|history|early|classic|seminal|landmark|foundational)\\b") ~ "historical_framing",
      str_detect(str_to_lower(snippet), "\\b(sustainab|ecological\\s+limits|planetary\\s+boundaries|overshoot|collapse|growth)\\b") ~ "sustainability_limits_to_growth_discourse",
      semantic_label == "MEADOWS_1972_BOOK" ~ "foundational_citation",
      TRUE ~ "background_or_ambiguous"
    )
  ) %>%
  distinct(source_document_id, snippet_hash, .keep_all = TRUE) %>%
  arrange(source_document_id, page)

readr::write_csv(contexts, file.path(path_get(paths, "data.processed"), "citation_contexts.csv"))
message("Wrote citation contexts: ", nrow(contexts), " rows.")
