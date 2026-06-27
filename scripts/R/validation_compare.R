suppressPackageStartupMessages({
  library(dplyr)
  library(purrr)
  library(readr)
  library(rlang)
  library(stringr)
  library(tibble)
})

blank_to_na <- function(x) {
  x <- as.character(x)
  x[!nzchar(str_trim(x))] <- NA_character_
  x
}

map_rule_role <- function(x) {
  dplyr::recode(
    x,
    sustainability_limits_to_growth_discourse = "sustainability_discourse",
    methodological_comparison = "methods_comparison",
    background_or_ambiguous = "unclear",
    .default = x
  )
}

safe_agreement <- function(x, y) {
  keep <- !is.na(x) & !is.na(y)
  if (!any(keep)) return(NA_real_)
  mean(x[keep] == y[keep])
}

confusion_table <- function(data, truth, prediction, table_name) {
  truth <- rlang::ensym(truth)
  prediction <- rlang::ensym(prediction)
  data %>%
    filter(!is.na(!!truth), !is.na(!!prediction)) %>%
    count(!!truth, !!prediction, name = "n") %>%
    mutate(table = table_name, .before = 1)
}

classification_metrics <- function(data, truth, prediction, label_col = "label") {
  truth_sym <- rlang::ensym(truth)
  pred_sym <- rlang::ensym(prediction)
  labels <- sort(unique(na.omit(c(data[[rlang::as_string(truth_sym)]], data[[rlang::as_string(pred_sym)]]))))
  purrr::map_dfr(labels, function(label) {
    tp <- sum(data[[rlang::as_string(truth_sym)]] == label & data[[rlang::as_string(pred_sym)]] == label, na.rm = TRUE)
    fp <- sum(data[[rlang::as_string(truth_sym)]] != label & data[[rlang::as_string(pred_sym)]] == label, na.rm = TRUE)
    fn <- sum(data[[rlang::as_string(truth_sym)]] == label & data[[rlang::as_string(pred_sym)]] != label, na.rm = TRUE)
    precision <- ifelse(tp + fp == 0, NA_real_, tp / (tp + fp))
    recall <- ifelse(tp + fn == 0, NA_real_, tp / (tp + fn))
    tibble(!!label_col := label, true_positive = tp, false_positive = fp, false_negative = fn, precision = precision, recall = recall)
  })
}

compare_validation_labels <- function(sample) {
  sample <- sample %>%
    mutate(
      rule_primary_role = map_rule_role(rule_citation_function),
      rule_is_seed_work_citation = case_when(
        rule_semantic_label == "MEADOWS_1972_BOOK" ~ "yes",
        rule_semantic_label == "LIMITS_TO_GROWTH_DISCOURSE" ~ "ambiguous",
        TRUE ~ NA_character_
      ),
      human_is_seed_work_citation = blank_to_na(human_is_seed_work_citation),
      human_primary_role = blank_to_na(human_primary_role),
      human_discourse_category = blank_to_na(human_discourse_category),
      human_stance_toward_seed = blank_to_na(human_stance_toward_seed),
      human_false_positive_flag = blank_to_na(human_false_positive_flag),
      llm_is_seed_work_citation = blank_to_na(llm_is_seed_work_citation),
      llm_primary_role = blank_to_na(llm_primary_role),
      llm_discourse_category = blank_to_na(llm_discourse_category),
      llm_stance_toward_meadows = blank_to_na(llm_stance_toward_meadows),
      llm_needs_human_review = blank_to_na(llm_needs_human_review),
      has_human_label = !is.na(human_is_seed_work_citation) |
        !is.na(human_primary_role) |
        !is.na(human_discourse_category) |
        !is.na(human_stance_toward_seed) |
        !is.na(human_false_positive_flag)
    )

  fallback_llm_summary <- bind_rows(
    tibble(metric = "fallback_llm_rows_available", value = sum(!is.na(sample$llm_primary_role))),
    tibble(metric = "fallback_llm_seed_status_agreement_rate", value = safe_agreement(sample$rule_is_seed_work_citation, sample$llm_is_seed_work_citation)),
    tibble(metric = "fallback_llm_primary_role_agreement_rate", value = safe_agreement(sample$rule_primary_role, sample$llm_primary_role)),
    tibble(metric = "fallback_llm_llm_review_rate", value = mean(sample$llm_needs_human_review %in% c("TRUE", "true", "1"), na.rm = TRUE))
  )

  fallback_llm_confusion <- bind_rows(
    confusion_table(sample, rule_is_seed_work_citation, llm_is_seed_work_citation, "fallback_vs_llm_seed_status"),
    confusion_table(sample, rule_primary_role, llm_primary_role, "fallback_vs_llm_primary_role")
  )

  if (!any(sample$has_human_label)) {
    return(list(
      summary = tibble(metric = "human_labels_available", value = 0),
      disagreements = tibble(),
      confusion = tibble(),
      metrics = tibble(),
      fallback_llm_summary = fallback_llm_summary,
      fallback_llm_confusion = fallback_llm_confusion,
      human_fallback_confusion = tibble(),
      human_fallback_metrics = tibble()
    ))
  }

  labeled <- sample %>% filter(has_human_label)
  summary <- bind_rows(
    tibble(metric = "human_labels_available", value = nrow(labeled)),
    tibble(metric = "seed_status_agreement_rate", value = safe_agreement(labeled$human_is_seed_work_citation, labeled$llm_is_seed_work_citation)),
    tibble(metric = "primary_role_agreement_rate", value = safe_agreement(labeled$human_primary_role, labeled$llm_primary_role)),
    tibble(metric = "discourse_category_agreement_rate", value = safe_agreement(labeled$human_discourse_category, labeled$llm_discourse_category)),
    tibble(metric = "stance_agreement_rate", value = safe_agreement(labeled$human_stance_toward_seed, labeled$llm_stance_toward_meadows)),
    tibble(metric = "llm_abstention_or_review_rate_labeled", value = mean(labeled$llm_needs_human_review %in% c("TRUE", "true", "1"), na.rm = TRUE))
  )

  disagreements <- labeled %>%
    filter(
      (!is.na(human_is_seed_work_citation) & human_is_seed_work_citation != llm_is_seed_work_citation) |
        (!is.na(human_primary_role) & human_primary_role != llm_primary_role) |
        (!is.na(human_discourse_category) & human_discourse_category != llm_discourse_category) |
        (!is.na(human_stance_toward_seed) & human_stance_toward_seed != llm_stance_toward_meadows)
    )

  confusion <- bind_rows(
    confusion_table(labeled, human_is_seed_work_citation, llm_is_seed_work_citation, "seed_work_status"),
    confusion_table(labeled, human_primary_role, llm_primary_role, "primary_role"),
    confusion_table(labeled, human_discourse_category, llm_discourse_category, "discourse_category"),
    confusion_table(labeled, human_stance_toward_seed, llm_stance_toward_meadows, "stance")
  )

  metrics <- bind_rows(
    classification_metrics(labeled, human_is_seed_work_citation, llm_is_seed_work_citation) %>% mutate(task = "seed_work_status", .before = 1),
    classification_metrics(labeled, human_primary_role, llm_primary_role) %>% mutate(task = "primary_role", .before = 1),
    classification_metrics(labeled, human_discourse_category, llm_discourse_category) %>% mutate(task = "discourse_category", .before = 1),
    classification_metrics(labeled, human_stance_toward_seed, llm_stance_toward_meadows) %>% mutate(task = "stance", .before = 1)
  )

  human_fallback_confusion <- bind_rows(
    confusion_table(labeled, human_is_seed_work_citation, rule_is_seed_work_citation, "human_vs_fallback_seed_status"),
    confusion_table(labeled, human_primary_role, rule_primary_role, "human_vs_fallback_primary_role")
  )

  human_fallback_metrics <- bind_rows(
    classification_metrics(labeled, human_is_seed_work_citation, rule_is_seed_work_citation) %>% mutate(task = "seed_work_status", .before = 1),
    classification_metrics(labeled, human_primary_role, rule_primary_role) %>% mutate(task = "primary_role", .before = 1)
  )

  list(
    summary = summary,
    disagreements = disagreements,
    confusion = confusion,
    metrics = metrics,
    fallback_llm_summary = fallback_llm_summary,
    fallback_llm_confusion = fallback_llm_confusion,
    human_fallback_confusion = human_fallback_confusion,
    human_fallback_metrics = human_fallback_metrics
  )
}
