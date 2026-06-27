suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(stringr)
  library(tibble)
})

stop_words_local <- c(
  "the","and","for","that","this","with","from","are","was","were","has","have","had","not","but","you","its","their",
  "about","into","than","then","such","also","more","most","can","may","will","would","could","should","between",
  "growth","limits","meadows"
)

tokenize_text <- function(x) {
  x %>%
    str_to_lower() %>%
    str_replace_all("[^a-z0-9]+", " ") %>%
    str_split("\\s+") %>%
    lapply(function(tokens) tokens[nchar(tokens) >= 3 & !tokens %in% stop_words_local])
}

build_tfidf_clusters <- function(docs, id_col = "doc_id", text_col = "text", k = 8, min_term_docs = 5, seed = 42) {
  docs <- docs %>% filter(!is.na(.data[[text_col]]), nzchar(.data[[text_col]]))
  if (nrow(docs) < 5) {
    return(list(assignments = tibble(), summaries = tibble(), representatives = tibble(), diagnostics = tibble(issue = "too_few_documents", n_docs = nrow(docs))))
  }
  toks <- tokenize_text(docs[[text_col]])
  vocab <- sort(unique(unlist(toks)))
  doc_freq <- vapply(vocab, function(term) sum(vapply(toks, function(tt) term %in% tt, logical(1))), integer(1))
  vocab <- vocab[doc_freq >= min_term_docs]
  if (length(vocab) < 5) {
    return(list(assignments = tibble(), summaries = tibble(), representatives = tibble(), diagnostics = tibble(issue = "too_few_terms", n_terms = length(vocab))))
  }

  mat <- matrix(0, nrow = nrow(docs), ncol = length(vocab), dimnames = list(NULL, vocab))
  for (i in seq_along(toks)) {
    tab <- table(toks[[i]])
    keep <- intersect(names(tab), vocab)
    mat[i, keep] <- as.numeric(tab[keep])
  }
  idf <- log((nrow(mat) + 1) / (colSums(mat > 0) + 1)) + 1
  tfidf <- sweep(mat, 2, idf, `*`)
  norm <- sqrt(rowSums(tfidf^2))
  tfidf <- tfidf / ifelse(norm == 0, 1, norm)

  set.seed(seed)
  n_distinct_points <- nrow(unique(as.data.frame(tfidf)))
  k <- min(k, max(2, nrow(tfidf) - 1), max(1, n_distinct_points))
  if (k < 2) {
    return(list(assignments = tibble(), summaries = tibble(), representatives = tibble(), diagnostics = tibble(issue = "too_few_distinct_vectors", n_docs = nrow(docs), n_terms = length(vocab))))
  }
  km <- kmeans(tfidf, centers = k, nstart = 20, iter.max = 100)

  assignments <- docs %>%
    transmute(doc_id = .data[[id_col]], text = .data[[text_col]], cluster = km$cluster)

  summaries <- lapply(sort(unique(km$cluster)), function(cl) {
    idx <- which(km$cluster == cl)
    term_scores <- colMeans(tfidf[idx, , drop = FALSE])
    tibble(
      cluster = cl,
      n_docs = length(idx),
      top_terms = paste(names(sort(term_scores, decreasing = TRUE))[1:min(12, length(term_scores))], collapse = " | ")
    )
  }) %>% bind_rows()

  representatives <- assignments %>%
    group_by(cluster) %>%
    slice_head(n = 5) %>%
    ungroup()

  list(assignments = assignments, summaries = summaries, representatives = representatives, diagnostics = tibble(issue = "ok", n_docs = nrow(docs), n_terms = length(vocab), k = k))
}
