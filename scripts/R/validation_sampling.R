suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
  library(tibble)
})

build_validation_sample <- function(contexts, llm = tibble(), n_per_stratum = 25, seed = 42) {
  set.seed(seed)

  if (!"hit_id" %in% names(contexts)) contexts$hit_id <- NA_character_
  if (!"snippet_hash" %in% names(contexts)) contexts$snippet_hash <- NA_character_
  if (!"match" %in% names(contexts)) contexts$match <- NA_character_
  context_key <- coalesce(
    contexts$hit_id,
    paste(contexts$source_document_id, contexts$page, contexts$match, sep = "|"),
    contexts$snippet_hash
  )

  if (nrow(llm) > 0 && "context_id" %in% names(llm)) {
    contexts <- contexts %>%
      mutate(context_id = context_key) %>%
      left_join(
        llm %>%
          select(
            context_id,
            starts_with("llm_"),
            model,
            classification_mode,
            classified_at
          ) %>%
          distinct(context_id, .keep_all = TRUE),
        by = "context_id"
      )
  } else {
    contexts <- contexts %>% mutate(context_id = context_key)
  }

  contexts <- contexts %>%
    mutate(
      validation_stratum = case_when(
        semantic_label == "MEADOWS_1972_BOOK" & citation_section == "BODY" ~ "direct_body_seed",
        semantic_label == "MEADOWS_1972_BOOK" & citation_section == "BIBLIO" ~ "direct_bibliography_seed",
        semantic_label == "LIMITS_TO_GROWTH_DISCOURSE" ~ "ltg_discourse_ambiguous",
        TRUE ~ "low_confidence_or_false_positive"
      ),
      snippet_clean = snippet %>%
        str_replace_all("\\s+", " ") %>%
        str_trim()
    )

  if ("classification_mode" %in% names(contexts) && any(contexts$classification_mode == "openai_json_schema", na.rm = TRUE)) {
    sampled_contexts <- contexts %>%
      filter(classification_mode == "openai_json_schema") %>%
      distinct(context_id, .keep_all = TRUE)
  } else {
    sampled_contexts <- contexts %>%
      group_by(validation_stratum) %>%
      group_modify(~ dplyr::slice_sample(.x, n = min(nrow(.x), n_per_stratum))) %>%
      ungroup()
  }

  sampled_contexts %>%
    transmute(
      context_id,
      validation_stratum,
      work_id = if ("work_id" %in% names(.)) work_id else NA_character_,
      title = if ("canonical_title" %in% names(.)) canonical_title else NA_character_,
      year = if ("year" %in% names(.)) year else NA_real_,
      venue = if ("venue" %in% names(.)) venue else NA_character_,
      source_database = if ("source_database" %in% names(.)) source_database else NA_character_,
      source_document_id,
      page,
      citation_section,
      mention_type = if ("mention_type" %in% names(.)) mention_type else citation_section,
      matched_seed_variant = if ("matched_seed_variant" %in% names(.)) matched_seed_variant else NA_character_,
      false_positive_risk = if ("false_positive_risk" %in% names(.)) false_positive_risk else NA_character_,
      rule_semantic_label = semantic_label,
      rule_citation_function = citation_function,
      rule_score = score,
      extraction_confidence = if ("extraction_confidence" %in% names(.)) extraction_confidence else NA_real_,
      section_heading = if ("section_heading" %in% names(.)) section_heading else NA_character_,
      sentence_before = if ("sentence_before" %in% names(.)) sentence_before else NA_character_,
      citation_sentence = if ("citation_sentence" %in% names(.)) citation_sentence else NA_character_,
      sentence_after = if ("sentence_after" %in% names(.)) sentence_after else NA_character_,
      context_window = if ("surrounding_sentence_window" %in% names(.)) surrounding_sentence_window else snippet_clean,
      bibliography_detected = if ("bib_like" %in% names(.)) bib_like else citation_section == "BIBLIO",
      bibliography_score = if ("biblio_score" %in% names(.)) biblio_score else NA_real_,
      llm_is_seed_work_citation = if ("llm_is_seed_work_citation" %in% names(.)) llm_is_seed_work_citation else NA_character_,
      llm_primary_role = if ("llm_primary_role" %in% names(.)) llm_primary_role else NA_character_,
      llm_discourse_category = if ("llm_discourse_category" %in% names(.)) llm_discourse_category else NA_character_,
      llm_stance_toward_meadows = if ("llm_stance_toward_meadows" %in% names(.)) llm_stance_toward_meadows else NA_character_,
      llm_confidence = if ("llm_confidence" %in% names(.)) llm_confidence else NA_real_,
      llm_reasoning_summary = if ("llm_interpretive_summary" %in% names(.)) llm_interpretive_summary else NA_character_,
      llm_evidence_quote = if ("llm_evidence_quote" %in% names(.)) llm_evidence_quote else NA_character_,
      llm_uncertainty_flags = if ("llm_uncertainty_flags" %in% names(.)) llm_uncertainty_flags else NA_character_,
      llm_needs_human_review = if ("llm_needs_human_review" %in% names(.)) llm_needs_human_review else NA,
      llm_model = if ("model" %in% names(.)) model else NA_character_,
      llm_classification_mode = if ("classification_mode" %in% names(.)) classification_mode else NA_character_,
      llm_error_type = if ("error_type" %in% names(.)) error_type else NA_character_,
      llm_error_message = if ("error_message" %in% names(.)) error_message else NA_character_,
      snippet_clean,
      human_is_seed_work_citation = "",
      human_primary_role = "",
      human_discourse_category = "",
      human_secondary_roles = "",
      human_stance_toward_seed = "",
      human_false_positive_flag = "",
      human_confidence = "",
      human_notes = ""
    )
}
