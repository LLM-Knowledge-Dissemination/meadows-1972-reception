suppressPackageStartupMessages({
  library(digest)
  library(dplyr)
  library(purrr)
  library(stringr)
  library(tibble)
})

sentence_containing_match <- function(snippet, match) {
  if (is.na(snippet) || !nzchar(snippet)) return(NA_character_)
  parts <- unlist(strsplit(snippet, "(?<=[.!?])\\s+", perl = TRUE))
  if (!is.na(match) && nzchar(match)) {
    hit <- parts[str_detect(str_to_lower(parts), fixed(str_to_lower(match)))]
    if (length(hit) > 0) return(str_squish(hit[[1]]))
  }
  str_squish(parts[[min(length(parts), ceiling(length(parts) / 2))]])
}

matched_seed_variant <- function(snippet) {
  s <- str_to_lower(snippet)
  case_when(
    str_detect(s, "meadows\\s+et\\s+al\\.?\\s*,?\\s*(19)?72") ~ "meadows_et_al_1972",
    str_detect(s, "\\(\\s*meadows[^)]*(19)?72\\s*\\)") ~ "parenthetical_meadows_1972",
    str_detect(s, "limits\\s+to\\s+growth") & str_detect(s, "club\\s+of\\s+rome") ~ "limits_to_growth_club_of_rome",
    str_detect(s, "limits\\s+to\\s+growth") ~ "limits_to_growth_title_only",
    TRUE ~ "unknown_variant"
  )
}

false_positive_risk <- function(snippet, semantic_label) {
  s <- str_to_lower(snippet)
  case_when(
    semantic_label == "MEADOWS_1972_BOOK" ~ "low",
    str_detect(s, "limits\\s+to\\s+growth") & !str_detect(s, "meadows|club\\s+of\\s+rome|world3|world\\s+model") ~ "high_generic_limits_phrase",
    semantic_label == "LOW_CONFIDENCE" ~ "medium_low_confidence",
    TRUE ~ "medium"
  )
}

context_confidence <- function(score, citation_section, false_positive_risk, bib_like = FALSE, biblio_score = 0, citation_sentence = NA_character_) {
  base <- pmin(1, pmax(0.1, as.numeric(score) / 8))
  base <- ifelse(citation_section == "BIBLIO" | bib_like | biblio_score >= 4, pmin(base, 0.65), base)
  base <- ifelse(false_positive_risk == "high_generic_limits_phrase", pmin(base, 0.45), base)
  base <- ifelse(is.na(citation_sentence) | nchar(citation_sentence) < 80, pmin(base, 0.65), base)
  base <- ifelse(!is.na(citation_sentence) & nchar(citation_sentence) >= 160, pmin(1, base + 0.05), base)
  round(base, 3)
}

enrich_citation_contexts <- function(contexts, canonical_works) {
  if (!"hit_id" %in% names(contexts)) contexts$hit_id <- NA_character_
  if (!"pdf_base" %in% names(contexts)) contexts$pdf_base <- NA_character_
  if (!"htid" %in% names(contexts)) contexts$htid <- NA_character_
  if (!"hits_file" %in% names(contexts)) contexts$hits_file <- NA_character_
  if (!"sentence_before" %in% names(contexts)) contexts$sentence_before <- NA_character_
  if (!"citation_sentence" %in% names(contexts)) contexts$citation_sentence <- NA_character_
  if (!"sentence_after" %in% names(contexts)) contexts$sentence_after <- NA_character_
  if (!"section_heading" %in% names(contexts)) contexts$section_heading <- NA_character_
  if (!"bib_like" %in% names(contexts)) contexts$bib_like <- FALSE
  if (!"biblio_score" %in% names(contexts)) contexts$biblio_score <- 0

  works_key <- canonical_works %>%
    transmute(
      work_id,
      normalized_doi,
      doi_safe = str_replace_all(normalized_doi, "[^A-Za-z0-9]+", "_"),
      year,
      canonical_title,
      venue,
      document_type,
      source_database
    ) %>%
    filter(!is.na(doi_safe), doi_safe != "")

  contexts %>%
    mutate(
      source_document_id = coalesce(source_document_id, pdf_base, htid),
      source_document_key = source_document_id,
      context_id = coalesce(hit_id, vapply(paste(source_document_id, page, match, snippet_hash, sep = "||"), digest, character(1), algo = "xxhash64")),
      mention_type = case_when(
        citation_section == "BIBLIO" ~ "bibliography_only",
        semantic_label == "MEADOWS_1972_BOOK" ~ "body_text_seed_citation",
        semantic_label == "LIMITS_TO_GROWTH_DISCOURSE" ~ "body_text_ltg_discourse",
        TRUE ~ "ambiguous_body_text_mention"
      ),
      matched_seed_variant = matched_seed_variant(snippet),
      false_positive_risk = false_positive_risk(snippet, semantic_label),
      sentence = coalesce(citation_sentence, mapply(sentence_containing_match, snippet, match, USE.NAMES = FALSE)),
      citation_sentence = sentence,
      surrounding_sentence_window = snippet,
      extraction_method = "regex_anchor_pdf_text_structured_sentence_window_v2",
      extraction_confidence = context_confidence(score, citation_section, false_positive_risk, bib_like, biblio_score, citation_sentence),
      source_file = hits_file
    ) %>%
    left_join(works_key, by = c("source_document_key" = "doi_safe")) %>%
    mutate(
      work_id = coalesce(work_id, paste0("UNMATCHED_", source_document_key)),
      abstract_mention = FALSE,
      title_metadata_mention = FALSE
    )
}
