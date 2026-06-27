suppressPackageStartupMessages({
  library(digest)
  library(dplyr)
  library(stringdist)
  library(stringr)
  library(tibble)
})

first_author_name <- function(authors) {
  authors <- as.character(authors)
  first <- str_split(authors, ";|\\|", n = 2, simplify = TRUE)[, 1]
  str_squish(first) %>% na_if("")
}

first_author_surname <- function(authors) {
  first <- first_author_name(authors)
  surname <- case_when(
    is.na(first) ~ NA_character_,
    str_detect(first, ",") ~ str_split(first, ",", n = 2, simplify = TRUE)[, 1],
    TRUE ~ word(first, -1)
  )
  surname %>%
    str_to_lower() %>%
    str_replace_all("[^a-z]+", "") %>%
    na_if("")
}

venue_key <- function(venue) {
  venue %>%
    as.character() %>%
    str_to_lower() %>%
    str_replace_all("[^a-z0-9]+", " ") %>%
    str_squish() %>%
    na_if("")
}

make_work_id <- function(cluster_id) {
  paste0("W", vapply(cluster_id, digest, character(1), algo = "xxhash64"))
}

first_nonempty <- function(x, default = NA_character_) {
  x <- as.character(x)
  x <- x[!is.na(x) & nzchar(x)]
  if (length(x) == 0) default else x[[1]]
}

first_nonmissing_num <- function(x) {
  x <- x[!is.na(x)]
  if (length(x) == 0) NA_real_ else x[[1]]
}

dedup_pair_score <- function(a, b) {
  title_sim <- 1 - stringdist::stringdist(a$title_norm, b$title_norm, method = "jw")
  author_match <- !is.na(a$first_author_key) && !is.na(b$first_author_key) && a$first_author_key == b$first_author_key
  year_close <- is.na(a$year) || is.na(b$year) || abs(a$year - b$year) <= 1
  venue_sim <- ifelse(is.na(a$venue_norm) || is.na(b$venue_norm), 0, 1 - stringdist::stringdist(a$venue_norm, b$venue_norm, method = "jw"))
  score <- 0.70 * title_sim + 0.15 * as.numeric(author_match) + 0.10 * as.numeric(year_close) + 0.05 * venue_sim
  max(0, min(1, score))
}

build_canonical_works <- function(metadata, threshold = 0.92, ambiguous_threshold = 0.86) {
  metadata <- metadata %>%
    filter(source_file != "fail_log.csv") %>%
    mutate(
      normalized_doi = normalize_doi(doi),
      normalized_title = normalize_title(title),
      first_author = first_author_name(authors),
      first_author_key = first_author_surname(authors),
      venue_norm = venue_key(venue),
      source_database = database,
      raw_record_id = paste(source_file, source_row, sep = "::")
    )

  metadata$duplicate_cluster_id <- NA_character_
  metadata$dedup_confidence <- NA_real_
  metadata$dedup_method <- NA_character_
  metadata$dedup_notes <- NA_character_

  doi_groups <- metadata %>%
    filter(!is.na(normalized_doi)) %>%
    group_by(normalized_doi) %>%
    summarise(rows = list(row_number()), .groups = "drop")

  for (doi in unique(metadata$normalized_doi[!is.na(metadata$normalized_doi)])) {
    idx <- which(metadata$normalized_doi == doi)
    metadata$duplicate_cluster_id[idx] <- paste0("doi:", doi)
    metadata$dedup_confidence[idx] <- 1
    metadata$dedup_method[idx] <- "exact_doi"
  }

  no_cluster <- which(is.na(metadata$duplicate_cluster_id) & !is.na(metadata$normalized_title))
  cluster_counter <- 0L
  ambiguous <- list()

  for (idx in no_cluster) {
    if (!is.na(metadata$duplicate_cluster_id[[idx]])) next
    cluster_counter <- cluster_counter + 1L
    cluster_id <- paste0("fuzzy:", cluster_counter)
    metadata$duplicate_cluster_id[[idx]] <- cluster_id
    metadata$dedup_confidence[[idx]] <- 0.75
    metadata$dedup_method[[idx]] <- "title_author_year_singleton"

    block <- which(
      is.na(metadata$duplicate_cluster_id) &
        !is.na(metadata$normalized_title) &
        (is.na(metadata$year) | is.na(metadata$year[[idx]]) | abs(metadata$year - metadata$year[[idx]]) <= 1) &
        (is.na(metadata$first_author_key) | is.na(metadata$first_author_key[[idx]]) | metadata$first_author_key == metadata$first_author_key[[idx]])
    )

    for (j in block) {
      score <- dedup_pair_score(metadata[idx, ], metadata[j, ])
      if (score >= threshold) {
        metadata$duplicate_cluster_id[[j]] <- cluster_id
        metadata$dedup_confidence[[j]] <- score
        metadata$dedup_method[[j]] <- "fuzzy_title_author_year"
      } else if (score >= ambiguous_threshold) {
        ambiguous[[length(ambiguous) + 1]] <- tibble(
          raw_record_id_1 = metadata$raw_record_id[[idx]],
          raw_record_id_2 = metadata$raw_record_id[[j]],
          title_1 = metadata$title[[idx]],
          title_2 = metadata$title[[j]],
          year_1 = metadata$year[[idx]],
          year_2 = metadata$year[[j]],
          first_author_1 = metadata$first_author[[idx]],
          first_author_2 = metadata$first_author[[j]],
          match_score = score,
          reason = "below_auto_merge_threshold"
        )
      }
    }
  }

  metadata <- metadata %>%
    mutate(
      duplicate_cluster_id = coalesce(duplicate_cluster_id, paste0("singleton:", raw_record_id)),
      dedup_confidence = coalesce(dedup_confidence, 0.5),
      dedup_method = coalesce(dedup_method, "insufficient_metadata_singleton"),
      work_id = make_work_id(duplicate_cluster_id)
    )

  canonical <- metadata %>%
    arrange(desc(!is.na(normalized_doi)), desc(!is.na(title)), desc(!is.na(year)), source_file, source_row) %>%
    group_by(work_id, duplicate_cluster_id) %>%
    summarise(
      canonical_title = first_nonempty(title),
      normalized_title = first_nonempty(normalized_title),
      doi = first_nonempty(doi),
      normalized_doi = first_nonempty(normalized_doi),
      year = first_nonmissing_num(year),
      authors = first_nonempty(authors),
      first_author = first_nonempty(first_author),
      venue = first_nonempty(venue),
      document_type = first_nonempty(document_type),
      source_database = paste(sort(unique(na.omit(source_database))), collapse = "; "),
      source_file = paste(sort(unique(source_file)), collapse = "; "),
      matched_seed_work = TRUE,
      dedup_confidence = min(dedup_confidence, na.rm = TRUE),
      external_ids = NA_character_,
      openalex_id = NA_character_,
      crossref_id = ifelse(!is.na(first_nonempty(normalized_doi)), paste0("doi:", first_nonempty(normalized_doi)), NA_character_),
      semantic_scholar_id = NA_character_,
      metadata_confidence = case_when(
        !is.na(first_nonempty(normalized_doi)) & !is.na(first_nonempty(title)) ~ 0.95,
        !is.na(first_nonempty(title)) & !is.na(first_nonmissing_num(year)) ~ 0.75,
        TRUE ~ 0.45
      ),
      notes = paste(sort(unique(na.omit(dedup_method))), collapse = "; "),
      n_source_records = n(),
      raw_record_ids = paste(raw_record_id, collapse = " | "),
      .groups = "drop"
    )

  clusters <- metadata %>%
    group_by(duplicate_cluster_id, work_id) %>%
    summarise(
      n_records = n(),
      dedup_confidence_min = min(dedup_confidence, na.rm = TRUE),
      dedup_methods = paste(sort(unique(dedup_method)), collapse = "; "),
      titles = paste(sort(unique(na.omit(title))), collapse = " | "),
      dois = paste(sort(unique(na.omit(normalized_doi))), collapse = " | "),
      raw_record_ids = paste(raw_record_id, collapse = " | "),
      .groups = "drop"
    )

  list(
    canonical_works = canonical,
    duplicate_clusters = clusters,
    record_map = metadata %>% select(raw_record_id, source_file, source_row, work_id, duplicate_cluster_id, dedup_confidence, dedup_method),
    ambiguous_matches = bind_rows(ambiguous)
  )
}
