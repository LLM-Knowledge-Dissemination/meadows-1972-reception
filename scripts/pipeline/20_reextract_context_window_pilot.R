suppressPackageStartupMessages({
  library(dplyr)
  library(pdftools)
  library(purrr)
  library(readr)
  library(stringr)
  library(tibble)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/citation_contexts.R")
source("scripts/R/context_enrichment.R")

paths <- load_paths()
pilot_path <- file.path(path_get(paths, "data.validation"), "context_window_pilot_20.csv")
pilot <- readr::read_csv(pilot_path, show_col_types = FALSE)

normalized_similarity <- function(x, y) {
  if (is.na(x) || is.na(y) || !nzchar(x) || !nzchar(y)) return(0)
  distance <- as.numeric(adist(str_to_lower(x), str_to_lower(y)))
  1 - distance / max(nchar(x), nchar(y), 1)
}

logical_text <- function(x) {
  ifelse(isTRUE(x), "TRUE", "FALSE")
}

extract_pilot_row <- function(row) {
  source_document_id <- row$source_document_id[[1]]
  pdf_path <- file.path(path_get(paths, "data.pdf"), paste0(source_document_id, ".pdf"))
  base <- as.list(row[1, ])
  updated_row <- function(values) {
    base[names(values)] <- values
    as_tibble(base)
  }

  failure <- function(status) {
    updated_row(list(
      reextraction_status = status,
      source_pdf = pdf_path,
      matched_new_hit_id = NA_character_,
      match_similarity = NA_real_,
      sentence_before = NA_character_,
      citation_sentence = NA_character_,
      sentence_after = NA_character_,
      section_heading = NA_character_,
      context_window = NA_character_,
      bibliography_detected = NA_character_,
      bibliography_score = NA_real_,
      new_extraction_confidence = NA_real_,
      automated_reviewability_assessment = "not_assessable"
    ))
  }

  if (!file.exists(pdf_path)) return(failure("source_pdf_missing"))
  pages <- tryCatch(pdftools::pdf_text(pdf_path), error = function(e) e)
  if (inherits(pages, "error")) return(failure("pdf_text_error"))
  pages <- lapply(pages, clean_pdf_text)
  hits <- extract_hits_from_pages(pages, pdf_path)
  if (nrow(hits) == 0) return(failure("no_seed_hits"))

  candidates <- hits %>% filter(page == as.integer(row$page[[1]]))
  if (nrow(candidates) == 0) return(failure("no_same_page_hit"))

  target_match <- sub("^.*\\|", "", row$context_id[[1]])
  candidates <- candidates %>%
    mutate(
      match_exact = str_to_lower(match) == str_to_lower(target_match),
      match_similarity = map2_dbl(snippet, row$old_snippet_clean[[1]], normalized_similarity)
    ) %>%
    arrange(desc(match_exact), desc(match_similarity))

  hit <- candidates %>% slice_head(n = 1)
  new_confidence <- context_confidence(
    hit$score,
    hit$citation_section,
    row$false_positive_risk[[1]],
    hit$bib_like,
    hit$biblio_score,
    hit$citation_sentence
  )
  reviewability <- if (
    !is.na(hit$citation_sentence[[1]]) &&
      nzchar(hit$citation_sentence[[1]]) &&
      (
        nchar(hit$snippet[[1]]) > nchar(row$old_snippet_clean[[1]]) ||
          !is.na(hit$sentence_before[[1]]) ||
          !is.na(hit$sentence_after[[1]])
      )
  ) "likely_improved" else "not_clearly_improved"

  updated_row(list(
    reextraction_status = "matched_new_hit",
    source_pdf = pdf_path,
    matched_new_hit_id = hit$hit_id[[1]],
    match_similarity = hit$match_similarity[[1]],
    sentence_before = hit$sentence_before[[1]],
    citation_sentence = hit$citation_sentence[[1]],
    sentence_after = hit$sentence_after[[1]],
    section_heading = hit$section_heading[[1]],
    context_window = hit$snippet[[1]],
    bibliography_detected = logical_text(hit$citation_section[[1]] == "BIBLIO"),
    bibliography_score = hit$biblio_score[[1]],
    new_extraction_confidence = new_confidence[[1]],
    automated_reviewability_assessment = reviewability
  ))
}

reextracted <- purrr::map_dfr(seq_len(nrow(pilot)), ~ extract_pilot_row(pilot[.x, ]))

comparison <- reextracted %>%
  transmute(
    context_id,
    context_group_id,
    reextraction_status,
    match_similarity,
    old_snippet_length = nchar(old_snippet_clean),
    new_context_length = nchar(context_window),
    citation_sentence_exists = !is.na(citation_sentence) & citation_sentence != "",
    sentence_before_exists = !is.na(sentence_before) & sentence_before != "",
    sentence_after_exists = !is.na(sentence_after) & sentence_after != "",
    section_heading_exists = !is.na(section_heading) & section_heading != "",
    old_bibliography_detected = ifelse(citation_section == "BIBLIO", "TRUE", "FALSE"),
    new_bibliography_detected = bibliography_detected,
    bibliography_detection_changed = old_bibliography_detected != new_bibliography_detected,
    old_extraction_confidence = extraction_confidence,
    new_extraction_confidence,
    extraction_confidence_change = new_extraction_confidence - old_extraction_confidence,
    row_now_more_reviewable = automated_reviewability_assessment,
    reviewer_new_window_improves_review = new_window_improves_review,
    reviewer_new_window_notes = new_window_notes
  )

readr::write_csv(reextracted, file.path(path_get(paths, "data.validation"), "context_window_pilot_reextracted.csv"), na = "")
readr::write_csv(comparison, file.path(path_get(paths, "outputs.tables"), "context_window_pilot_comparison.csv"), na = "")

structured_updates <- reextracted %>%
  select(
    context_id,
    context_window,
    citation_sentence,
    sentence_before,
    sentence_after,
    section_heading,
    bibliography_detected,
    bibliography_score
  )

v2_path <- file.path(path_get(paths, "data.validation"), "v2_classifier_pilot_input_100.csv")
if (file.exists(v2_path)) {
  v2 <- readr::read_csv(v2_path, show_col_types = FALSE) %>%
    left_join(structured_updates, by = c("mention_level_id" = "context_id"), suffix = c("", ".new")) %>%
    mutate(
      context_window = coalesce(context_window.new, context_window),
      citation_sentence = coalesce(citation_sentence.new, citation_sentence),
      sentence_before = coalesce(sentence_before.new, sentence_before),
      sentence_after = coalesce(sentence_after.new, sentence_after),
      section_heading = coalesce(section_heading.new, section_heading),
      bibliography_detected = coalesce(bibliography_detected.new, bibliography_detected),
      bibliography_score = coalesce(bibliography_score.new, bibliography_score)
    ) %>%
    select(-ends_with(".new"))
  readr::write_csv(v2, v2_path, na = "")
}

boundary_path <- file.path(path_get(paths, "data.validation"), "boundary_case_adjudication_packet.csv")
if (file.exists(boundary_path)) {
  boundary <- readr::read_csv(boundary_path, show_col_types = FALSE) %>%
    left_join(structured_updates %>% select(context_id, context_window), by = "context_id", suffix = c("", ".new")) %>%
    mutate(context_window = coalesce(context_window.new, context_window)) %>%
    select(-context_window.new)
  readr::write_csv(boundary, boundary_path, na = "")
}

message(
  "Re-extracted ", sum(reextracted$reextraction_status == "matched_new_hit"), " of ",
  nrow(reextracted), " pilot rows."
)
