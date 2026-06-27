suppressPackageStartupMessages({
  library(dplyr)
  library(fs)
  library(httr)
  library(jsonlite)
  library(purrr)
  library(readr)
  library(stringr)
  library(tibble)
  library(tidyr)
})

split_cited_references <- function(x) {
  if (length(x) == 0) return(character(0))
  x <- x[[1]]
  if (is.na(x) || !nzchar(x)) return(character(0))
  str_split(x, ";\\s*|\\n+")[[1]] %>% str_squish() %>% discard(~ .x == "")
}

normalize_reference_key <- function(x) {
  x %>%
    str_to_lower() %>%
    str_replace_all("\\bdoi:?\\s*", "") %>%
    str_replace_all("[^a-z0-9]+", " ") %>%
    str_squish()
}

reference_key_to_openalex_id <- function(x) {
  id <- str_extract(x, "w[0-9]+")
  ifelse(is.na(id), NA_character_, paste0("https://openalex.org/", str_to_upper(id)))
}

extract_openalex_work_label <- function(x, fallback_id = NA_character_) {
  authorships <- x$authorships %||% list()
  authors <- vapply(head(authorships, 5), function(a) a$author$display_name %||% NA_character_, character(1))
  tibble(
    openalex_id = x$id %||% fallback_id,
    cited_reference_key = normalize_reference_key(x$id %||% fallback_id),
    reference_title = x$title %||% NA_character_,
    reference_year = x$publication_year %||% NA_integer_,
    reference_venue = x$primary_location$source$display_name %||% NA_character_,
    reference_authors = paste(na.omit(authors), collapse = " | ")
  )
}

read_openalex_label_from_cache <- function(openalex_id, cache_dir) {
  if (is.na(openalex_id) || !nzchar(openalex_id) || !dir.exists(cache_dir)) return(tibble())
  files <- fs::dir_ls(cache_dir, glob = "*.json", fail = FALSE)
  if (length(files) == 0) return(tibble())
  for (path in files) {
    parsed <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
    if (is.null(parsed)) next
    candidates <- if (!is.null(parsed$results)) parsed$results else list(parsed)
    for (candidate in candidates) {
      if (!is.null(candidate$id) && identical(candidate$id, openalex_id)) {
        return(extract_openalex_work_label(candidate, openalex_id))
      }
    }
  }
  tibble()
}

fetch_openalex_label <- function(openalex_id, cache_dir, enabled = FALSE, timeout_sec = 20) {
  cached <- read_openalex_label_from_cache(openalex_id, cache_dir)
  if (nrow(cached) > 0) return(cached %>% mutate(reference_resolution_source = "openalex_cache"))
  if (!isTRUE(enabled) || is.na(openalex_id) || !nzchar(openalex_id)) return(tibble())

  work_id <- str_extract(openalex_id, "W[0-9]+")
  if (is.na(work_id)) return(tibble())
  url <- paste0("https://api.openalex.org/works/", work_id)
  path <- fs::path(cache_dir, paste0("reference_", str_to_lower(work_id), ".json"))
  parsed <- tryCatch({
    resp <- httr::GET(url, httr::timeout(timeout_sec), httr::user_agent("meadows-1972-bibliometrics/0.1"))
    if (httr::status_code(resp) < 200 || httr::status_code(resp) >= 300) return(tibble())
    txt <- httr::content(resp, as = "text", encoding = "UTF-8")
    jsonlite::fromJSON(txt, simplifyVector = FALSE)
  }, error = function(e) NULL)
  if (is.null(parsed) || nrow(tibble::as_tibble(parsed["id"])) == 0) return(tibble())
  fs::dir_create(cache_dir, recurse = TRUE)
  writeLines(jsonlite::toJSON(parsed, auto_unbox = TRUE, pretty = TRUE, null = "null"), path, useBytes = TRUE)
  extract_openalex_work_label(parsed, openalex_id) %>% mutate(reference_resolution_source = "openalex_api")
}

resolve_reference_labels <- function(reference_keys, cache_dir, enabled = FALSE, limit = 250) {
  keys <- unique(na.omit(reference_keys))
  keys <- head(keys, limit)
  ids <- reference_key_to_openalex_id(keys)

  cache_labels <- tibble()
  if (dir.exists(cache_dir)) {
    cache_labels <- fs::dir_ls(cache_dir, glob = "*.json", fail = FALSE) %>%
      purrr::map_dfr(function(path) {
        parsed <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
        if (is.null(parsed)) return(tibble())
        candidates <- if (!is.null(parsed$results)) parsed$results else list(parsed)
        purrr::map_dfr(candidates, extract_openalex_work_label)
      }) %>%
      distinct(openalex_id, .keep_all = TRUE)
  }

  cached <- cache_labels %>% filter(openalex_id %in% ids)
  missing_ids <- setdiff(ids, cached$openalex_id)
  fetched <- purrr::map_dfr(missing_ids, fetch_openalex_label, cache_dir = cache_dir, enabled = enabled)

  bind_rows(cached %>% mutate(reference_resolution_source = "openalex_cache"), fetched) %>%
    distinct(cited_reference_key, .keep_all = TRUE)
}

build_reference_edges <- function(metadata) {
  edges <- list()
  if ("cited_references" %in% names(metadata)) {
    edges[[length(edges) + 1]] <- metadata %>%
      mutate(citing_work_id = coalesce(work_id, work_key)) %>%
      select(citing_work_id, cited_references) %>%
      filter(!is.na(cited_references), cited_references != "") %>%
      rowwise() %>%
      mutate(cited_reference = list(split_cited_references(cited_references))) %>%
      ungroup() %>%
      select(-cited_references) %>%
      tidyr::unnest(cited_reference) %>%
      mutate(cited_reference_key = normalize_reference_key(cited_reference), reference_source = "raw_export") %>%
      filter(cited_reference_key != "")
  }
  if ("openalex_referenced_works" %in% names(metadata)) {
    edges[[length(edges) + 1]] <- metadata %>%
      filter(!is.na(openalex_referenced_works), openalex_referenced_works != "") %>%
      transmute(citing_work_id = work_id, cited_reference = openalex_referenced_works) %>%
      separate_rows(cited_reference, sep = "\\s*\\|\\s*") %>%
      mutate(cited_reference_key = normalize_reference_key(cited_reference), reference_source = "openalex") %>%
      filter(cited_reference_key != "")
  }
  bind_rows(edges) %>% distinct()
}

build_bibliographic_coupling <- function(reference_edges) {
  if (nrow(reference_edges) == 0) return(tibble())
  reference_edges %>%
    inner_join(reference_edges, by = "cited_reference_key", relationship = "many-to-many") %>%
    filter(citing_work_id.x < citing_work_id.y) %>%
    count(citing_work_id.x, citing_work_id.y, name = "shared_references") %>%
    rename(work_id_1 = citing_work_id.x, work_id_2 = citing_work_id.y) %>%
    arrange(desc(shared_references))
}

build_cocitation_edges <- function(reference_edges) {
  if (nrow(reference_edges) == 0) return(tibble())
  reference_edges %>%
    distinct(citing_work_id, cited_reference_key) %>%
    inner_join(., ., by = "citing_work_id", relationship = "many-to-many") %>%
    filter(cited_reference_key.x < cited_reference_key.y) %>%
    count(cited_reference_key.x, cited_reference_key.y, name = "co_citing_works") %>%
    rename(cited_reference_1 = cited_reference_key.x, cited_reference_2 = cited_reference_key.y) %>%
    arrange(desc(co_citing_works))
}

build_seed_citation_edges <- function(contexts, seed_work_id = "seed_meadows_1972_limits_to_growth") {
  if (nrow(contexts) == 0) return(tibble())
  contexts %>%
    filter(semantic_label == "MEADOWS_1972_BOOK") %>%
    group_by(source_document_id) %>%
    summarise(
      seed_work_id = seed_work_id,
      n_contexts = n(),
      body_contexts = sum(citation_section == "BODY", na.rm = TRUE),
      bibliography_contexts = sum(citation_section == "BIBLIO", na.rm = TRUE),
      citation_functions = paste(sort(unique(citation_function)), collapse = "; "),
      pages = paste(sort(unique(page)), collapse = ", "),
      example_context = first(snippet),
      .groups = "drop"
    ) %>%
    rename(citing_document_id = source_document_id)
}

summarise_diffusion <- function(metadata, seed_edges) {
  metadata %>%
    mutate(
      source_document_id = coalesce(str_replace_all(normalized_doi, "[^A-Za-z0-9]+", "_"), work_id),
      database = if ("database" %in% names(.)) database else source_database
    ) %>%
    inner_join(seed_edges, by = c("source_document_id" = "citing_document_id")) %>%
    count(year, venue, document_type, database, name = "n_citing_works") %>%
    arrange(year, desc(n_citing_works))
}

summarise_networks <- function(reference_edges, cocitation_edges, bibliographic_coupling) {
  tibble(
    network = c("reference_edges", "cocitation_edges", "bibliographic_coupling"),
    n_edges = c(nrow(reference_edges), nrow(cocitation_edges), nrow(bibliographic_coupling)),
    n_nodes_or_works = c(
      length(unique(c(reference_edges$citing_work_id, reference_edges$cited_reference_key))),
      length(unique(c(cocitation_edges$cited_reference_1, cocitation_edges$cited_reference_2))),
      length(unique(c(bibliographic_coupling$work_id_1, bibliographic_coupling$work_id_2)))
    )
  )
}

build_filtered_network_tables <- function(reference_edges, cocitation_edges, bibliographic_coupling, works = tibble()) {
  ref_with_year <- reference_edges
  if (nrow(works) > 0 && "work_id" %in% names(works)) {
    ref_with_year <- reference_edges %>%
      left_join(works %>% select(work_id, year), by = c("citing_work_id" = "work_id")) %>%
      mutate(decade = ifelse(is.na(year), NA_integer_, floor(year / 10) * 10))
  } else {
    ref_with_year <- reference_edges %>% mutate(year = NA_integer_, decade = NA_integer_)
  }

  ref_counts <- reference_edges %>% count(cited_reference_key, name = "n_citing_works_reference")
  work_ref_counts <- reference_edges %>% distinct(citing_work_id, cited_reference_key) %>% count(citing_work_id, name = "n_references")

  cocitation_normalized <- cocitation_edges %>%
    left_join(ref_counts, by = c("cited_reference_1" = "cited_reference_key")) %>%
    rename(n_citing_works_ref1 = n_citing_works_reference) %>%
    left_join(ref_counts, by = c("cited_reference_2" = "cited_reference_key")) %>%
    rename(n_citing_works_ref2 = n_citing_works_reference) %>%
    mutate(
      association_strength = co_citing_works / sqrt(n_citing_works_ref1 * n_citing_works_ref2)
    )

  bibliographic_coupling_normalized <- bibliographic_coupling %>%
    left_join(work_ref_counts, by = c("work_id_1" = "citing_work_id")) %>%
    rename(n_references_work_1 = n_references) %>%
    left_join(work_ref_counts, by = c("work_id_2" = "citing_work_id")) %>%
    rename(n_references_work_2 = n_references) %>%
    mutate(
      normalized_shared_references = shared_references / sqrt(n_references_work_1 * n_references_work_2)
    )

  cocitation_by_decade <- ref_with_year %>%
    filter(!is.na(decade)) %>%
    distinct(decade, citing_work_id, cited_reference_key) %>%
    inner_join(., ., by = c("decade", "citing_work_id"), relationship = "many-to-many") %>%
    filter(cited_reference_key.x < cited_reference_key.y) %>%
    count(decade, cited_reference_key.x, cited_reference_key.y, name = "co_citing_works") %>%
    rename(cited_reference_1 = cited_reference_key.x, cited_reference_2 = cited_reference_key.y) %>%
    group_by(decade) %>%
    arrange(desc(co_citing_works), .by_group = TRUE) %>%
    slice_head(n = 100) %>%
    ungroup()

  ref_with_field <- reference_edges
  if (nrow(works) > 0 && "openalex_concepts" %in% names(works)) {
    top_fields <- works %>%
      transmute(primary_openalex_field = str_squish(str_extract(openalex_concepts, "^[^|]+"))) %>%
      filter(!is.na(primary_openalex_field), primary_openalex_field != "") %>%
      count(primary_openalex_field, sort = TRUE) %>%
      slice_head(n = 20) %>%
      pull(primary_openalex_field)
    ref_with_field <- reference_edges %>%
      left_join(
        works %>%
          transmute(work_id, primary_openalex_field = str_squish(str_extract(openalex_concepts, "^[^|]+"))),
        by = c("citing_work_id" = "work_id")
      ) %>%
      filter(primary_openalex_field %in% top_fields)
  } else {
    ref_with_field <- reference_edges %>% mutate(primary_openalex_field = NA_character_)
  }

  cocitation_by_field <- ref_with_field %>%
    filter(!is.na(primary_openalex_field), primary_openalex_field != "") %>%
    distinct(primary_openalex_field, citing_work_id, cited_reference_key) %>%
    inner_join(., ., by = c("primary_openalex_field", "citing_work_id"), relationship = "many-to-many") %>%
    filter(cited_reference_key.x < cited_reference_key.y) %>%
    count(primary_openalex_field, cited_reference_key.x, cited_reference_key.y, name = "co_citing_works") %>%
    rename(cited_reference_1 = cited_reference_key.x, cited_reference_2 = cited_reference_key.y) %>%
    group_by(primary_openalex_field) %>%
    arrange(desc(co_citing_works), .by_group = TRUE) %>%
    slice_head(n = 50) %>%
    ungroup()

  top_cited <- reference_edges %>%
    count(cited_reference_key, reference_source, sort = TRUE, name = "n_citing_works")

  top_cited_decade <- ref_with_year %>%
      count(decade, cited_reference_key, reference_source, sort = TRUE, name = "n_citing_works") %>%
      arrange(decade, desc(n_citing_works))

  top_bib <- bibliographic_coupling_normalized %>%
    arrange(desc(shared_references))
  if (nrow(works) > 0 && "work_id" %in% names(works)) {
    labels <- works %>%
      select(work_id, canonical_title, year, venue, first_author) %>%
      distinct(work_id, .keep_all = TRUE)
    top_bib <- top_bib %>%
      left_join(labels, by = c("work_id_1" = "work_id")) %>%
      rename(title_1 = canonical_title, year_1 = year, venue_1 = venue, first_author_1 = first_author) %>%
      left_join(labels, by = c("work_id_2" = "work_id")) %>%
      rename(title_2 = canonical_title, year_2 = year, venue_2 = venue, first_author_2 = first_author)
  }

  list(
    cocitation_min3 = cocitation_normalized %>% filter(co_citing_works >= 3),
    cocitation_min5 = cocitation_normalized %>% filter(co_citing_works >= 5),
    cocitation_top100 = cocitation_normalized %>% arrange(desc(co_citing_works), desc(association_strength)) %>% slice_head(n = 100),
    cocitation_by_decade_top100 = cocitation_by_decade,
    cocitation_by_field_top100 = cocitation_by_field,
    bibliographic_coupling_min3 = bibliographic_coupling_normalized %>% filter(shared_references >= 3),
    bibliographic_coupling_top100 = bibliographic_coupling_normalized %>% arrange(desc(shared_references), desc(normalized_shared_references)) %>% slice_head(n = 100),
    top_cited_references = top_cited,
    top_cited_references_by_decade = top_cited_decade,
    top_bibliographically_coupled_works = top_bib
  )
}

`%||%` <- function(x, y) if (is.null(x) || length(x) == 0) y else x
