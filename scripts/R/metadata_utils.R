suppressPackageStartupMessages({
  library(dplyr)
  library(janitor)
  library(readr)
  library(readxl)
  library(stringdist)
  library(stringr)
  library(tibble)
})

normalize_doi <- function(x) {
  x %>%
    as.character() %>%
    str_squish() %>%
    str_remove("^https?://(dx\\.)?doi\\.org/") %>%
    str_remove("^doi:\\s*") %>%
    str_to_lower() %>%
    na_if("")
}

safe_doi_id <- function(x) {
  normalize_doi(x) %>%
    str_replace_all("[^A-Za-z0-9]+", "_") %>%
    str_replace_all("^_|_$", "")
}

doi_from_safe_id <- function(x) {
  x <- as.character(x)
  ifelse(
    str_detect(x, "^10_"),
    str_replace(x, "^10_", "10.") %>% str_replace("_", "/") %>% str_replace_all("_", "."),
    NA_character_
  )
}

normalize_title <- function(x) {
  x %>%
    as.character() %>%
    str_to_lower() %>%
    str_replace_all("&", " and ") %>%
    str_replace_all("[^a-z0-9]+", " ") %>%
    str_squish() %>%
    na_if("")
}

normalize_author_key <- function(x) {
  x %>%
    as.character() %>%
    str_to_lower() %>%
    str_replace_all("[^a-z,; ]+", " ") %>%
    str_squish() %>%
    na_if("")
}

read_bibliographic_file <- function(path) {
  ext <- tolower(tools::file_ext(path))
  if (ext %in% c("xls", "xlsx")) {
    readxl::read_excel(path, na = c(".", "", "NA")) %>% janitor::clean_names()
  } else if (ext %in% c("csv", "tsv")) {
    delim <- ifelse(ext == "tsv", "\t", ",")
    readr::read_delim(path, delim = delim, show_col_types = FALSE) %>% janitor::clean_names()
  } else {
    stop("Unsupported bibliographic file type: ", path, call. = FALSE)
  }
}

coalesce_columns <- function(df, candidates, default = NA_character_) {
  present <- intersect(candidates, names(df))
  if (length(present) == 0) return(rep(default, nrow(df)))
  out <- df[[present[[1]]]]
  if (length(present) > 1) {
    for (nm in present[-1]) out <- dplyr::coalesce(out, df[[nm]])
  }
  out
}

harmonize_metadata <- function(df, source_file = NA_character_) {
  tibble(
    source_row = seq_len(nrow(df)),
    source_file = source_file,
    source_record_id = coalesce_columns(df, c("ut_unique_wos_id", "accession_number", "eid", "id", "record_id")),
    doi = normalize_doi(coalesce_columns(df, c("doi", "book_doi", "di"))),
    title = coalesce_columns(df, c("article_title", "title", "ti", "source_title")),
    authors = coalesce_columns(df, c("authors", "au", "author_full_names")),
    year = suppressWarnings(as.integer(coalesce_columns(df, c("publication_year", "py", "year")))),
    venue = coalesce_columns(df, c("source_title", "journal", "journal_name", "publication_name", "so")),
    document_type = coalesce_columns(df, c("document_type", "dt", "type")),
    abstract = coalesce_columns(df, c("abstract", "ab")),
    keywords = coalesce_columns(df, c("author_keywords", "keywords", "de", "id")),
    addresses = coalesce_columns(df, c("addresses", "c1", "affiliations")),
    cited_references = coalesce_columns(df, c("cited_references", "cr", "references")),
    database = case_when(
      str_detect(tolower(source_file), "savedrecs") ~ "web_of_science_or_clarivate",
      TRUE ~ "unknown"
    )
  ) %>%
    mutate(
      title_norm = normalize_title(title),
      authors_norm = normalize_author_key(authors),
      doi_safe = safe_doi_id(doi),
      work_key = case_when(
        !is.na(doi) ~ paste0("doi:", doi),
        !is.na(title_norm) & !is.na(year) ~ paste("title_year:", title_norm, year),
        !is.na(title_norm) ~ paste("title:", title_norm),
        TRUE ~ paste0("row:", row_number())
      )
    )
}

deduplicate_works <- function(metadata, title_distance_threshold = 0.08) {
  doi_deduped <- metadata %>%
    group_by(doi) %>%
    mutate(duplicate_group = if_else(!is.na(doi), paste0("doi:", doi), NA_character_)) %>%
    ungroup()

  no_doi <- doi_deduped %>% filter(is.na(doi), !is.na(title_norm))
  if (nrow(no_doi) == 0) {
    return(doi_deduped %>% mutate(is_duplicate = duplicated(duplicate_group) & !is.na(duplicate_group)))
  }

  no_doi <- no_doi %>%
    arrange(year, title_norm) %>%
    mutate(title_group = NA_character_)

  group_id <- 0L
  for (i in seq_len(nrow(no_doi))) {
    if (!is.na(no_doi$title_group[[i]])) next
    group_id <- group_id + 1L
    group_name <- paste0("title:", group_id)
    same_year <- which(is.na(no_doi$title_group) & (is.na(no_doi$year) | is.na(no_doi$year[[i]]) | no_doi$year == no_doi$year[[i]]))
    distances <- stringdist::stringdist(no_doi$title_norm[[i]], no_doi$title_norm[same_year], method = "jw")
    matches <- same_year[distances <= title_distance_threshold]
    no_doi$title_group[matches] <- group_name
  }

  doi_deduped %>%
    left_join(no_doi %>% select(source_file, source_row, title_group), by = c("source_file", "source_row")) %>%
    mutate(
      duplicate_group = coalesce(duplicate_group, title_group, work_key),
      is_duplicate = duplicated(duplicate_group)
    ) %>%
    select(-title_group)
}
