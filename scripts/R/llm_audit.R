suppressPackageStartupMessages({
  library(dplyr)
  library(jsonlite)
  library(lubridate)
  library(purrr)
  library(readr)
  library(stringr)
  library(tibble)
})

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x

map_rule_role <- function(x) {
  recode(
    x,
    sustainability_limits_to_growth_discourse = "sustainability_discourse",
    methodological_comparison = "methods_comparison",
    background_or_ambiguous = "unclear",
    .default = x
  )
}

confidence_bin <- function(x) {
  case_when(
    is.na(x) ~ "missing",
    x < 0.60 ~ "<0.60",
    x < 0.70 ~ "0.60-0.69",
    x < 0.80 ~ "0.70-0.79",
    x < 0.90 ~ "0.80-0.89",
    TRUE ~ "0.90-1.00"
  )
}

read_audit_jsonl <- function(path) {
  if (!file.exists(path) || file.info(path)$size == 0) return(tibble())
  lines <- readLines(path, warn = FALSE)
  records <- lapply(lines, jsonlite::fromJSON, simplifyVector = FALSE)
  bind_rows(lapply(records, function(x) {
    usage <- x$usage %||% list()
    tibble(
      context_id = x$context_id %||% NA_character_,
      model = x$model %||% NA_character_,
      mode = x$mode %||% NA_character_,
      status = x$status %||% NA_character_,
      retries = as.integer(x$retries %||% NA_integer_),
      error_type = x$error_type %||% NA_character_,
      error = x$error %||% NA_character_,
      started_at = x$started_at %||% NA_character_,
      ended_at = x$ended_at %||% NA_character_,
      input_tokens_audit = as.numeric(usage$input_tokens %||% NA_real_),
      output_tokens_audit = as.numeric(usage$output_tokens %||% NA_real_),
      total_tokens_audit = as.numeric(usage$total_tokens %||% NA_real_)
    )
  })) %>%
    mutate(
      started_at_time = lubridate::ymd_hms(started_at, quiet = TRUE),
      ended_at_time = lubridate::ymd_hms(ended_at, quiet = TRUE),
      latency_seconds = as.numeric(difftime(ended_at_time, started_at_time, units = "secs"))
    )
}

build_llm_audit <- function(llm, input_rows, audit = tibble()) {
  if (!"hit_id" %in% names(input_rows)) input_rows$hit_id <- NA_character_
  if (!"snippet_hash" %in% names(input_rows)) input_rows$snippet_hash <- NA_character_
  if (!"match" %in% names(input_rows)) input_rows$match <- NA_character_

  input_contexts <- input_rows %>%
    mutate(context_id = coalesce(hit_id, snippet_hash, paste(source_document_id, page, match, sep = "|"))) %>%
    select(
      context_id,
      source_document_id,
      page,
      snippet,
      rule_semantic_label = semantic_label,
      rule_citation_function = citation_function,
      citation_section
    )

  latest_audit <- audit %>%
    filter(context_id %in% llm$context_id, mode == "openai_json_schema") %>%
    arrange(context_id, ended_at_time) %>%
    group_by(context_id) %>%
    slice_tail(n = 1) %>%
    ungroup()

  joined <- llm %>%
    left_join(input_contexts, by = c("context_id", "source_document_id", "page", "rule_semantic_label", "rule_citation_function", "citation_section")) %>%
    left_join(
      latest_audit %>% select(context_id, status, retries, latency_seconds, error_type_audit = error_type),
      by = "context_id"
    ) %>%
    mutate(
      rule_primary_role = map_rule_role(rule_citation_function),
      role_agreement = rule_primary_role == llm_primary_role,
      seed_agreement = case_when(
        rule_semantic_label == "MEADOWS_1972_BOOK" ~ llm_is_seed_work_citation == "yes",
        rule_semantic_label == "LIMITS_TO_GROWTH_DISCOURSE" ~ llm_is_seed_work_citation %in% c("ambiguous", "no"),
        TRUE ~ NA
      ),
      confidence_bin = confidence_bin(as.numeric(llm_confidence)),
      has_uncertainty = !is.na(llm_uncertainty_flags) & llm_uncertainty_flags != "none" & llm_uncertainty_flags != "",
      has_error = classification_mode == "openai_error" | !is.na(error_type) & error_type != "",
      likely_overinterpretation_candidate = llm_stance_toward_meadows %in% c("supportive", "critical", "mixed") &
        as.numeric(llm_confidence) >= 0.80 &
        !str_detect(str_to_lower(coalesce(llm_evidence_quote, "")), "support|critic|wrong|valid|accur|success|failure|necessary|founding|remarkable|predict"),
      fallback_safer_candidate = !role_agreement &
        (has_uncertainty | llm_needs_human_review | as.numeric(llm_confidence) < 0.75),
      llm_improvement_candidate = !role_agreement &
        !has_uncertainty &
        as.numeric(llm_confidence) >= 0.80 &
        llm_primary_role %in% c("historical_framing", "modeling_simulation_reference", "bibliographic_only", "policy_governance_framing")
    )

  attempted <- nrow(llm)
  successful <- sum(llm$classification_mode == "openai_json_schema", na.rm = TRUE)
  failed <- sum(llm$classification_mode == "openai_error", na.rm = TRUE)

  summary <- tibble(
    metric = c(
      "attempted",
      "successful_classifications",
      "failed_classifications",
      "schema_compliance_rate",
      "retry_rate",
      "malformed_response_rate",
      "needs_human_review_rate",
      "uncertainty_flag_rate",
      "abstention_or_review_rate",
      "average_confidence",
      "median_confidence",
      "role_agreement_with_fallback",
      "role_disagreement_with_fallback",
      "seed_status_agreement_with_rules",
      "mean_latency_seconds",
      "median_latency_seconds",
      "total_input_tokens",
      "total_output_tokens",
      "total_tokens",
      "distinct_context_ids",
      "duplicate_context_id_rows"
    ),
    value = c(
      attempted,
      successful,
      failed,
      ifelse(attempted == 0, NA_real_, successful / attempted),
      mean(coalesce(joined$retries, 0L) > 0, na.rm = TRUE),
      0,
      mean(joined$llm_needs_human_review, na.rm = TRUE),
      mean(joined$has_uncertainty, na.rm = TRUE),
      mean(joined$llm_needs_human_review | joined$has_uncertainty | joined$llm_primary_role == "unclear", na.rm = TRUE),
      mean(as.numeric(joined$llm_confidence), na.rm = TRUE),
      median(as.numeric(joined$llm_confidence), na.rm = TRUE),
      mean(joined$role_agreement, na.rm = TRUE),
      mean(!joined$role_agreement, na.rm = TRUE),
      mean(joined$seed_agreement, na.rm = TRUE),
      mean(joined$latency_seconds, na.rm = TRUE),
      median(joined$latency_seconds, na.rm = TRUE),
      sum(as.numeric(joined$input_tokens), na.rm = TRUE),
      sum(as.numeric(joined$output_tokens), na.rm = TRUE),
      sum(as.numeric(joined$total_tokens), na.rm = TRUE),
      length(unique(joined$context_id)),
      nrow(joined) - length(unique(joined$context_id))
    )
  )

  distributions <- list(
    confidence = joined %>% count(confidence_bin, name = "n") %>% arrange(confidence_bin),
    role = joined %>% count(llm_primary_role, sort = TRUE, name = "n"),
    discourse = joined %>% count(llm_discourse_category, sort = TRUE, name = "n"),
    stance = joined %>% count(llm_stance_toward_meadows, sort = TRUE, name = "n"),
    uncertainty_flags = joined %>% count(llm_uncertainty_flags, sort = TRUE, name = "n")
  )

  confusion <- joined %>%
    count(rule_primary_role, llm_primary_role, name = "n") %>%
    arrange(desc(n))

  disagreements <- joined %>%
    filter(!role_agreement | has_uncertainty | llm_needs_human_review | likely_overinterpretation_candidate) %>%
    select(
      context_id,
      citation_section,
      rule_primary_role,
      llm_primary_role,
      llm_discourse_category,
      llm_stance_toward_meadows,
      llm_confidence,
      llm_uncertainty_flags,
      llm_needs_human_review,
      role_agreement,
      has_uncertainty,
      llm_improvement_candidate,
      fallback_safer_candidate,
      likely_overinterpretation_candidate,
      llm_evidence_quote,
      llm_interpretive_summary,
      snippet
    ) %>%
    arrange(role_agreement, desc(likely_overinterpretation_candidate), llm_confidence)

  examples <- bind_rows(
    disagreements %>% filter(llm_improvement_candidate) %>% slice_head(n = 8) %>% mutate(example_type = "llm_may_improve_specificity"),
    disagreements %>% filter(fallback_safer_candidate) %>% slice_head(n = 8) %>% mutate(example_type = "fallback_or_human_review_may_be_safer"),
    disagreements %>% filter(likely_overinterpretation_candidate) %>% slice_head(n = 8) %>% mutate(example_type = "possible_llm_overinterpretation"),
    disagreements %>% filter(llm_needs_human_review | has_uncertainty) %>% slice_head(n = 8) %>% mutate(example_type = "abstention_or_uncertainty_appropriate")
  ) %>%
    distinct(example_type, context_id, .keep_all = TRUE)

  list(
    joined = joined,
    summary = summary,
    distributions = distributions,
    confusion = confusion,
    disagreements = disagreements,
    examples = examples
  )
}
