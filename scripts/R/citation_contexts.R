suppressPackageStartupMessages({
  library(digest)
  library(dplyr)
  library(fs)
  library(pdftools)
  library(readr)
  library(stringr)
  library(tibble)
})

clean_pdf_text <- function(x) {
  x %>%
    str_replace_all("‚Ä¶", "...") %>%
    str_replace_all("‚Äì|‚Äî", "-") %>%
    str_replace_all("‚Äï|‚Äò|‚Äô", "'") %>%
    str_replace_all("‚Äú|‚Äù|‚Äñ", "\"") %>%
    str_replace_all("Ô¨Å", "fi") %>%
    str_replace_all("Ô¨Æ", "fl") %>%
    str_replace_all("Ô¨Ç", "ffi") %>%
    str_replace_all("Ô¨È", "ffl") %>%
    str_replace_all("[\r\t]+", " ") %>%
    str_replace_all("\\s*\\n\\s*", " ") %>%
    str_replace_all("-\\s+(?=[a-z])", "") %>%
    str_replace_all("\\s{2,}", " ") %>%
    str_trim()
}

is_probably_pdf <- function(path) {
  con <- file(path, "rb")
  on.exit(close(con), add = TRUE)
  sig <- readBin(con, what = "raw", n = 4)
  length(sig) >= 4 && rawToChar(sig) == "%PDF"
}

append_csv <- function(df, path) {
  if (!fs::file_exists(path)) readr::write_csv(df, path) else readr::write_csv(df, path, append = TRUE)
}

looks_like_bibliography <- function(snippet) {
  s_low <- str_to_lower(snippet)
  s_raw <- snippet
  score <- 0L
  score <- score + ifelse(str_detect(s_low, "\\b(references|bibliography|works\\s+cited|literature\\s+cited)\\b"), 2L, 0L)
  score <- score + ifelse(str_detect(s_low, "\\bdoi\\b|\\b10\\.\\d{4,9}/"), 2L, 0L)
  score <- score + ifelse(str_detect(s_low, "\\bpp\\.?\\s*\\d+\\b|\\bvol\\.?\\b|\\bno\\.?\\b|\\bed\\.?\\b"), 1L, 0L)
  score <- score + ifelse(str_count(s_low, "\\b(19|20)\\d{2}\\b") >= 2, 1L, 0L)
  score <- score + ifelse(str_count(s_raw, ",") >= 4, 1L, 0L)
  score >= 3
}

page_bibliography_context <- function(page_text) {
  p_low <- str_to_lower(str_squish(page_text))
  p_raw <- str_squish(page_text)
  score <- 0L
  score <- score + ifelse(str_detect(p_low, "^\\s*(references|bibliography|works\\s+cited|literature\\s+cited)\\b"), 3L, 0L)
  score <- score + ifelse(str_count(p_low, "\\b(19|20)\\d{2}\\b") >= 5, 1L, 0L)
  score <- score + ifelse(str_count(p_raw, ",") >= 20, 1L, 0L)
  score <- score + ifelse(str_count(p_low, "\\b10\\.\\d{4,9}/") >= 2, 1L, 0L)
  tibble(is_biblio_page = score >= 4, biblio_score = score)
}

extract_sentence_window <- function(text, start, end, min_chars = 350, max_chars = 1400, hard_window = 1800) {
  n <- nchar(text)
  if (n == 0) return(text)
  left_hard <- max(1, start - hard_window)
  right_hard <- min(n, end + hard_window)
  left_chunk <- substr(text, left_hard, start)
  right_chunk <- substr(text, end, right_hard)
  left_breaks <- gregexpr("[\\.\\?!;:]", left_chunk, perl = TRUE)[[1]]
  right_breaks <- gregexpr("[\\.\\?!;:]", right_chunk, perl = TRUE)[[1]]
  left <- left_hard + ifelse(left_breaks[[1]] == -1, 1, max(left_breaks))
  right <- end + ifelse(right_breaks[[1]] == -1, nchar(right_chunk), min(right_breaks))
  if ((right - left + 1) < min_chars) {
    extra <- ceiling((min_chars - (right - left + 1)) / 2)
    left <- max(1, left - extra)
    right <- min(n, right + extra)
  }
  if ((right - left + 1) > max_chars) {
    mid <- floor((start + end) / 2)
    left <- max(1, mid - floor(max_chars / 2))
    right <- min(n, mid + floor(max_chars / 2))
  }
  substr(text, left, right) %>% str_squish()
}

extract_structured_sentences <- function(text, start, end) {
  n <- nchar(text)
  if (n == 0) {
    return(tibble(sentence_before = NA_character_, citation_sentence = NA_character_, sentence_after = NA_character_))
  }
  left_hard <- max(1, start - 1800)
  right_hard <- min(n, end + 1800)
  chunk <- substr(text, left_hard, right_hard)
  local_start <- start - left_hard + 1
  local_end <- end - left_hard + 1
  protected_chunk <- str_replace_all(
    chunk,
    regex("\\b(et\\s+al|e\\.g|i\\.e|fig|eq|no|pp|vol)\\.", ignore_case = TRUE),
    function(x) str_replace_all(x, "\\.", "~")
  )
  boundaries <- str_locate_all(protected_chunk, "(?<=[.!?])\\s+")[[1]]
  sentence_starts <- c(1L, boundaries[, "end"] + 1L)
  sentence_ends <- c(boundaries[, "start"] - 1L, nchar(chunk))
  hit_index <- which(sentence_starts <= local_start & sentence_ends >= local_end)
  if (length(hit_index) == 0) hit_index <- which.min(abs(sentence_starts - local_start))
  i <- hit_index[[1]]
  sentence_at <- function(j) {
    if (j < 1 || j > length(sentence_starts)) return(NA_character_)
    str_squish(substr(chunk, sentence_starts[[j]], sentence_ends[[j]]))
  }
  tibble(
    sentence_before = sentence_at(i - 1L),
    citation_sentence = sentence_at(i),
    sentence_after = sentence_at(i + 1L)
  )
}

detect_section_heading <- function(text, start) {
  left <- substr(text, max(1, start - 500), max(1, start - 1))
  candidates <- str_extract_all(left, "(?:^|[.!?]\\s+)(\\d+(?:\\.\\d+)*\\s+)?[A-Z][A-Za-z0-9 &:/-]{3,80}(?=\\s+[A-Z])")[[1]]
  if (length(candidates) == 0) return(NA_character_)
  str_squish(tail(candidates, 1))
}

classify_meadows_context <- function(snippet, is_biblio = FALSE) {
  s <- str_to_lower(snippet)
  has_title <- str_detect(s, "\\blimits\\s+to\\s+growth\\b")
  has_meadows <- str_detect(s, "\\bmeadows\\b")
  has_1972 <- str_detect(s, "\\b(19)?72\\b")
  has_club <- str_detect(s, "club\\s+of\\s+rome")
  has_modeling <- str_detect(s, "\\b(model|models|simulation|system\\s+dynamics|world3|scenario|forecast)\\b")
  has_critique <- str_detect(s, "\\b(critique|criticis|refut|controvers|wrong|failed|debate|limits\\s+to\\s+growth\\s+debate)\\b")
  has_policy <- str_detect(s, "\\b(policy|governance|planning|regulation|development\\s+strategy|sustainable\\s+development)\\b")
  has_history <- str_detect(s, "\\b(historical|history|early|classic|seminal|landmark|foundational)\\b")
  has_sustainability <- str_detect(s, "\\b(sustainab|ecological\\s+limits|planetary\\s+boundaries|overshoot|collapse|growth)\\b")

  semantic_label <- case_when(
    has_meadows && has_1972 ~ "MEADOWS_1972_BOOK",
    has_title && (has_club || has_modeling || has_critique || has_sustainability) ~ "LIMITS_TO_GROWTH_DISCOURSE",
    TRUE ~ "LOW_CONFIDENCE"
  )

  citation_function <- case_when(
    has_critique ~ "critique",
    has_modeling ~ "modeling_simulation_reference",
    has_policy ~ "policy_governance_framing",
    has_history ~ "historical_framing",
    has_sustainability ~ "sustainability_limits_to_growth_discourse",
    has_meadows && has_1972 ~ "foundational_citation",
    TRUE ~ "background_or_ambiguous"
  )

  score <- 0L +
    ifelse(has_meadows, 3L, 0L) +
    ifelse(has_1972, 2L, 0L) +
    ifelse(has_title, 2L, 0L) +
    ifelse(has_club, 1L, 0L) -
    ifelse(is_biblio, 1L, 0L)

  tibble(
    score = score,
    semantic_label = semantic_label,
    citation_function = citation_function,
    citation_section = if_else(is_biblio, "BIBLIO", "BODY"),
    has_title = has_title,
    has_meadows = has_meadows,
    has_1972 = has_1972,
    has_club = has_club,
    has_modeling = has_modeling,
    has_critique = has_critique,
    has_policy = has_policy,
    has_history = has_history,
    has_sustainability = has_sustainability
  )
}

extract_hits_from_pages <- function(pages, pdf_path) {
  anchor_union <- paste(c(
    "limits\\s+to\\s+growth",
    "\\(\\s*meadows\\s*(et\\s+al\\.?)*\\s*,?\\s*(19)?72\\s*\\)",
    "\\bmeadows\\b\\s*(et\\s+al\\.?)*\\s*,?\\s*(19)?72\\b"
  ), collapse = "|")

  out <- list()
  for (i in seq_along(pages)) {
    txt <- pages[[i]]
    if (is.na(txt) || !nzchar(txt) || !str_detect(txt, regex(anchor_union, ignore_case = TRUE))) next
    page_ctx <- page_bibliography_context(txt)
    locs <- str_locate_all(txt, regex(anchor_union, ignore_case = TRUE))[[1]]
    if (nrow(locs) == 0) next
    for (k in seq_len(nrow(locs))) {
      snip <- extract_sentence_window(txt, locs[k, "start"], locs[k, "end"])
      structured <- extract_structured_sentences(txt, locs[k, "start"], locs[k, "end"])
      bib_like <- looks_like_bibliography(snip)
      is_biblio <- isTRUE(page_ctx$is_biblio_page[[1]]) || isTRUE(bib_like)
      out[[length(out) + 1]] <- tibble(
        source_document_id = fs::path_ext_remove(fs::path_file(pdf_path)),
        pdf_path = pdf_path,
        page = i,
        match = substr(txt, locs[k, "start"], locs[k, "end"]),
        snippet = snip,
        bib_like = bib_like,
        section_heading = detect_section_heading(txt, locs[k, "start"])
      ) %>%
        bind_cols(structured) %>%
        bind_cols(page_ctx) %>%
        bind_cols(classify_meadows_context(snip, is_biblio = is_biblio))
    }
  }

  hits <- bind_rows(out)
  if (nrow(hits) == 0) return(hits)
  hits %>%
    filter(!(citation_section == "BIBLIO" & semantic_label == "LOW_CONFIDENCE")) %>%
    mutate(
      snippet_norm = str_squish(str_to_lower(snippet)),
      snippet_hash = vapply(snippet_norm, digest, character(1), algo = "xxhash64"),
      hit_id = vapply(paste(source_document_id, page, match, snippet_hash, sep = "||"), digest, character(1), algo = "xxhash64")
    ) %>%
    distinct(source_document_id, snippet_hash, .keep_all = TRUE)
}

parse_one_pdf <- function(pdf_path, text_dir, hits_dir, log_dir, save_pages = TRUE, overwrite = FALSE) {
  base <- fs::path_ext_remove(fs::path_file(pdf_path))
  text_out <- fs::path(text_dir, paste0(base, "_pages.rds"))
  hits_out <- fs::path(hits_dir, paste0(base, "_hits.csv"))
  fail_log <- fs::path(log_dir, "pdf_parse_failures.csv")
  run_log <- fs::path(log_dir, "pdf_parse_runlog.csv")

  if (fs::file_exists(hits_out) && !isTRUE(overwrite)) {
    return(tibble(pdf_path = pdf_path, status = "skipped_existing", n_pages = NA_integer_, n_chars = NA_integer_, n_hits = NA_integer_))
  }

  fail <- function(reason, details = NA_character_) {
    append_csv(tibble(timestamp = as.character(Sys.time()), pdf_path = pdf_path, reason = reason, details = details), fail_log)
    readr::write_csv(tibble(), hits_out)
    tibble(pdf_path = pdf_path, status = reason, n_pages = NA_integer_, n_chars = NA_integer_, n_hits = 0L)
  }

  if (is.na(fs::file_info(pdf_path)$size) || fs::file_info(pdf_path)$size < 1024) return(fail("too_small"))
  if (!is_probably_pdf(pdf_path)) return(fail("bad_signature"))

  pages <- tryCatch(pdftools::pdf_text(pdf_path), error = function(e) e)
  if (inherits(pages, "error")) return(fail("pdftools_error", conditionMessage(pages)))

  pages <- lapply(pages, clean_pdf_text)
  n_pages <- length(pages)
  n_chars <- sum(nchar(pages), na.rm = TRUE)
  if (isTRUE(save_pages)) saveRDS(pages, text_out, compress = FALSE)

  hits <- if (n_chars < 500) tibble() else extract_hits_from_pages(pages, pdf_path)
  readr::write_csv(hits, hits_out)
  append_csv(tibble(timestamp = as.character(Sys.time()), pdf_path = pdf_path, n_pages = n_pages, n_chars = n_chars, n_hits = nrow(hits)), run_log)
  tibble(pdf_path = pdf_path, status = ifelse(n_chars < 500, "low_text_yield", "ok"), n_pages = n_pages, n_chars = n_chars, n_hits = nrow(hits))
}
