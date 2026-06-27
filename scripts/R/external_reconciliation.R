suppressPackageStartupMessages({
  library(digest)
  library(dplyr)
  library(fs)
  library(httr)
  library(jsonlite)
  library(readr)
  library(stringr)
  library(tibble)
})

cache_key <- function(x) digest(x, algo = "xxhash64")

safe_write_json <- function(x, path) {
  fs::dir_create(fs::path_dir(path), recurse = TRUE)
  writeLines(jsonlite::toJSON(x, auto_unbox = TRUE, pretty = TRUE, null = "null"), path, useBytes = TRUE)
}

safe_read_json <- function(path) {
  if (!file.exists(path)) return(NULL)
  tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
}

openalex_url_for_work <- function(work) {
  if (!is.na(work$normalized_doi) && nzchar(work$normalized_doi)) {
    return(paste0("https://api.openalex.org/works/https://doi.org/", URLencode(work$normalized_doi, reserved = TRUE)))
  }
  if (!is.na(work$canonical_title) && nzchar(work$canonical_title)) {
    query <- URLencode(work$canonical_title, reserved = TRUE)
    return(paste0("https://api.openalex.org/works?search=", query, "&per-page=3"))
  }
  NA_character_
}

crossref_url_for_work <- function(work) {
  if (!is.na(work$normalized_doi) && nzchar(work$normalized_doi)) {
    return(paste0("https://api.crossref.org/works/", URLencode(work$normalized_doi, reserved = TRUE)))
  }
  if (!is.na(work$canonical_title) && nzchar(work$canonical_title)) {
    query <- URLencode(work$canonical_title, reserved = TRUE)
    return(paste0("https://api.crossref.org/works?query.title=", query, "&rows=3"))
  }
  NA_character_
}

fetch_cached_json <- function(url, cache_dir, enabled = FALSE, timeout_sec = 20) {
  if (is.na(url) || !nzchar(url)) return(list(status = "skipped_no_query", data = NULL, cache_path = NA_character_))
  path <- fs::path(cache_dir, paste0(cache_key(url), ".json"))
  cached <- safe_read_json(path)
  if (!is.null(cached)) return(list(status = "cache_hit", data = cached, cache_path = path))
  if (!isTRUE(enabled)) return(list(status = "skipped_api_disabled", data = NULL, cache_path = path))

  resp <- tryCatch(httr::GET(url, httr::timeout(timeout_sec), httr::user_agent("meadows-1972-bibliometrics/0.1")), error = function(e) e)
  if (inherits(resp, "error")) return(list(status = paste0("request_error:", conditionMessage(resp)), data = NULL, cache_path = path))
  if (httr::status_code(resp) < 200 || httr::status_code(resp) >= 300) {
    return(list(status = paste0("http_", httr::status_code(resp)), data = NULL, cache_path = path))
  }
  txt <- httr::content(resp, as = "text", encoding = "UTF-8")
  parsed <- tryCatch(jsonlite::fromJSON(txt, simplifyVector = FALSE), error = function(e) e)
  if (inherits(parsed, "error")) return(list(status = paste0("json_error:", conditionMessage(parsed)), data = NULL, cache_path = path))
  safe_write_json(parsed, path)
  list(status = "fetched", data = parsed, cache_path = path)
}

pick_openalex_result <- function(data, work) {
  if (is.null(data)) return(NULL)
  if (!is.null(data$id)) return(data)
  results <- data$results
  if (is.null(results) || length(results) == 0) return(NULL)
  results[[1]]
}

extract_openalex <- function(data, work) {
  x <- pick_openalex_result(data, work)
  if (is.null(x)) return(tibble())
  concepts <- x$concepts %||% list()
  institutions <- x$authorships %||% list()
  tibble(
    work_id = work$work_id,
    openalex_id = x$id %||% NA_character_,
    openalex_doi = str_remove(x$doi %||% NA_character_, "^https://doi.org/"),
    openalex_title = x$title %||% NA_character_,
    openalex_year = x$publication_year %||% NA_integer_,
    openalex_venue = x$primary_location$source$display_name %||% NA_character_,
    openalex_publisher = x$primary_location$source$host_organization_name %||% NA_character_,
    openalex_cited_by_count = x$cited_by_count %||% NA_integer_,
    openalex_is_oa = x$open_access$is_oa %||% NA,
    openalex_oa_status = x$open_access$oa_status %||% NA_character_,
    openalex_referenced_works = paste(unlist(x$referenced_works %||% list()), collapse = " | "),
    openalex_concepts = paste(vapply(concepts, function(c) c$display_name %||% NA_character_, character(1)), collapse = " | "),
    openalex_concept_scores = paste(vapply(concepts, function(c) as.character(c$score %||% NA_real_), character(1)), collapse = " | "),
    openalex_institutions = paste(unique(unlist(lapply(institutions, function(a) vapply(a$institutions %||% list(), function(i) i$display_name %||% NA_character_, character(1))))), collapse = " | "),
    openalex_countries = paste(unique(unlist(lapply(institutions, function(a) vapply(a$countries %||% list(), as.character, character(1))))), collapse = " | ")
  )
}

extract_crossref <- function(data, work) {
  if (is.null(data$message)) return(tibble())
  msg <- data$message
  if (!is.null(msg$items)) msg <- msg$items[[1]]
  issued <- msg$issued$`date-parts`[[1]][[1]] %||% NA_integer_
  tibble(
    work_id = work$work_id,
    crossref_id = ifelse(!is.null(msg$DOI), paste0("doi:", tolower(msg$DOI)), NA_character_),
    crossref_doi = tolower(msg$DOI %||% NA_character_),
    crossref_title = paste(unlist(msg$title %||% NA_character_), collapse = " "),
    crossref_year = issued,
    crossref_publisher = msg$publisher %||% NA_character_,
    crossref_type = msg$type %||% NA_character_,
    crossref_reference_count = msg$`reference-count` %||% NA_integer_,
    crossref_is_referenced_by_count = msg$`is-referenced-by-count` %||% NA_integer_
  )
}

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x

reconcile_external_metadata <- function(works, cache_root, enabled = FALSE, limit = Inf) {
  openalex_cache <- fs::path(cache_root, "openalex")
  crossref_cache <- fs::path(cache_root, "crossref")
  fs::dir_create(openalex_cache, recurse = TRUE)
  fs::dir_create(crossref_cache, recurse = TRUE)

  if (is.finite(limit)) works_run <- head(works, limit) else works_run <- works
  logs <- list()
  openalex_rows <- list()
  crossref_rows <- list()

  for (i in seq_len(nrow(works_run))) {
    work <- works_run[i, ]
    oa <- fetch_cached_json(openalex_url_for_work(work), openalex_cache, enabled = enabled)
    cr <- fetch_cached_json(crossref_url_for_work(work), crossref_cache, enabled = enabled)
    logs[[length(logs) + 1]] <- tibble(work_id = work$work_id, source = "openalex", status = oa$status, cache_path = oa$cache_path)
    logs[[length(logs) + 1]] <- tibble(work_id = work$work_id, source = "crossref", status = cr$status, cache_path = cr$cache_path)
    openalex_rows[[length(openalex_rows) + 1]] <- extract_openalex(oa$data, work)
    crossref_rows[[length(crossref_rows) + 1]] <- extract_crossref(cr$data, work)
  }

  openalex <- bind_rows(openalex_rows)
  crossref <- bind_rows(crossref_rows)
  log <- bind_rows(logs)
  if (nrow(openalex) == 0 || !"work_id" %in% names(openalex)) {
    openalex <- tibble(work_id = character(), openalex_id = character(), openalex_doi = character())
  }
  if (nrow(crossref) == 0 || !"work_id" %in% names(crossref)) {
    crossref <- tibble(work_id = character(), crossref_id = character(), crossref_doi = character())
  }

  enriched <- works %>%
    left_join(openalex, by = "work_id") %>%
    left_join(crossref, by = "work_id") %>%
    mutate(
      openalex_id = coalesce(openalex_id.y, openalex_id.x),
      crossref_id = coalesce(crossref_id.y, crossref_id.x),
      normalized_doi = coalesce(normalized_doi, normalize_doi(openalex_doi), normalize_doi(crossref_doi)),
      external_ids = case_when(
        !is.na(openalex_id) & !is.na(crossref_id) ~ paste(openalex_id, crossref_id, sep = " | "),
        !is.na(openalex_id) ~ openalex_id,
        !is.na(crossref_id) ~ crossref_id,
        TRUE ~ external_ids
      ),
      metadata_confidence = case_when(
        !is.na(openalex_id) & !is.na(crossref_id) ~ pmax(metadata_confidence, 0.98, na.rm = TRUE),
        !is.na(openalex_id) | !is.na(crossref_id) ~ pmax(metadata_confidence, 0.90, na.rm = TRUE),
        TRUE ~ metadata_confidence
      ),
      notes = paste(notes, ifelse(!is.na(openalex_id) | !is.na(crossref_id), "external_metadata_enriched", "external_metadata_not_matched"), sep = "; ")
    ) %>%
    select(-openalex_id.x, -openalex_id.y, -crossref_id.x, -crossref_id.y)

  list(enriched = enriched, openalex = openalex, crossref = crossref, log = log)
}
