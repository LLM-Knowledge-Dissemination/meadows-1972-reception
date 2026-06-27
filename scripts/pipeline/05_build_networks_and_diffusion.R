suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

source("scripts/helpers/project_paths.R")
source("scripts/R/network_analysis.R")

paths <- load_paths()
metadata_path <- file.path(path_get(paths, "data.processed"), "canonical_works_enriched.csv")
if (!file.exists(metadata_path)) metadata_path <- file.path(path_get(paths, "data.processed"), "canonical_works.csv")
contexts_path <- file.path(path_get(paths, "data.processed"), "citation_contexts_enriched.csv")
if (!file.exists(contexts_path)) contexts_path <- file.path(path_get(paths, "data.processed"), "citation_contexts.csv")

metadata <- if (file.exists(metadata_path)) readr::read_csv(metadata_path, show_col_types = FALSE) else tibble::tibble()
contexts <- if (file.exists(contexts_path)) readr::read_csv(contexts_path, show_col_types = FALSE) else tibble::tibble()

reference_edges <- build_reference_edges(metadata)
bibliographic_coupling <- build_bibliographic_coupling(reference_edges)
cocitation_edges <- build_cocitation_edges(reference_edges)
seed_edges <- build_seed_citation_edges(contexts)
diffusion <- summarise_diffusion(metadata, seed_edges)
network_summary <- summarise_networks(reference_edges, cocitation_edges, bibliographic_coupling)
filtered_networks <- build_filtered_network_tables(reference_edges, cocitation_edges, bibliographic_coupling, metadata)

openalex_cache_dir <- file.path(path_get(paths, "data.external"), "api_cache", "openalex")
resolve_references <- tolower(Sys.getenv("MEADOWS_RESOLVE_REFERENCES", "false")) == "true"
reference_labels <- resolve_reference_labels(
  c(
    filtered_networks$top_cited_references$cited_reference_key,
    filtered_networks$cocitation_top100$cited_reference_1,
    filtered_networks$cocitation_top100$cited_reference_2
  ),
  cache_dir = openalex_cache_dir,
  enabled = resolve_references,
  limit = as.integer(Sys.getenv("MEADOWS_REFERENCE_RESOLUTION_LIMIT", "250"))
)

add_reference_label <- function(x, key_col, suffix) {
  if (nrow(reference_labels) == 0) return(x)
  x %>%
    left_join(reference_labels, by = setNames("cited_reference_key", key_col)) %>%
    rename_with(
      ~ paste0(.x, suffix),
      any_of(c("openalex_id", "reference_title", "reference_year", "reference_venue", "reference_authors", "reference_resolution_source"))
    )
}

filtered_networks$top_cited_references <- add_reference_label(filtered_networks$top_cited_references, "cited_reference_key", "")
filtered_networks$top_cited_references_by_decade <- add_reference_label(filtered_networks$top_cited_references_by_decade, "cited_reference_key", "")
filtered_networks$cocitation_top100 <- filtered_networks$cocitation_top100 %>%
  add_reference_label("cited_reference_1", "_1") %>%
  add_reference_label("cited_reference_2", "_2")
filtered_networks$cocitation_by_decade_top100 <- filtered_networks$cocitation_by_decade_top100 %>%
  add_reference_label("cited_reference_1", "_1") %>%
  add_reference_label("cited_reference_2", "_2")
filtered_networks$cocitation_by_field_top100 <- filtered_networks$cocitation_by_field_top100 %>%
  add_reference_label("cited_reference_1", "_1") %>%
  add_reference_label("cited_reference_2", "_2")

readr::write_csv(reference_edges, file.path(path_get(paths, "data.derived"), "reference_edges.csv"))
readr::write_csv(cocitation_edges, file.path(path_get(paths, "data.derived"), "cocitation_edges.csv"))
readr::write_csv(bibliographic_coupling, file.path(path_get(paths, "data.derived"), "bibliographic_coupling.csv"))
readr::write_csv(seed_edges, file.path(path_get(paths, "data.derived"), "meadows_1972_seed_edges.csv"))
readr::write_csv(diffusion, file.path(path_get(paths, "data.derived"), "diffusion_by_year_venue_type.csv"))
readr::write_csv(network_summary, file.path(path_get(paths, "outputs.tables"), "network_summary.csv"))
readr::write_csv(filtered_networks$cocitation_min3, file.path(path_get(paths, "data.derived"), "cocitation_edges_min3.csv"))
readr::write_csv(filtered_networks$cocitation_min5, file.path(path_get(paths, "data.derived"), "cocitation_edges_min5.csv"))
readr::write_csv(filtered_networks$cocitation_top100, file.path(path_get(paths, "data.derived"), "cocitation_edges_top100.csv"))
readr::write_csv(filtered_networks$cocitation_by_decade_top100, file.path(path_get(paths, "data.derived"), "cocitation_edges_by_decade_top100.csv"))
readr::write_csv(filtered_networks$cocitation_by_field_top100, file.path(path_get(paths, "data.derived"), "cocitation_edges_by_field_top100.csv"))
readr::write_csv(filtered_networks$bibliographic_coupling_min3, file.path(path_get(paths, "data.derived"), "bibliographic_coupling_min3.csv"))
readr::write_csv(filtered_networks$bibliographic_coupling_top100, file.path(path_get(paths, "data.derived"), "bibliographic_coupling_top100.csv"))
readr::write_csv(filtered_networks$top_cited_references, file.path(path_get(paths, "outputs.tables"), "top_cited_references.csv"))
readr::write_csv(filtered_networks$top_cited_references_by_decade, file.path(path_get(paths, "outputs.tables"), "top_cited_references_by_decade.csv"))
readr::write_csv(filtered_networks$top_bibliographically_coupled_works, file.path(path_get(paths, "outputs.tables"), "top_bibliographically_coupled_works.csv"))
readr::write_csv(reference_labels, file.path(path_get(paths, "outputs.tables"), "resolved_reference_labels.csv"))

if (nrow(reference_edges) == 0) {
  diagnostic <- tibble::tibble(
    issue = "no_reference_edges",
    explanation = "Current raw exports contain no cited-reference values and no OpenAlex/Semantic Scholar referenced-work cache has been populated.",
    recommended_fix = "Enable external reconciliation or re-export records with cited references."
  )
  readr::write_csv(diagnostic, file.path(path_get(paths, "outputs.logs"), "reference_network_diagnostic.csv"))
} else {
  diagnostic <- reference_edges %>%
    count(reference_source, name = "n_reference_edges") %>%
    mutate(
      issue = "reference_edges_available",
      explanation = paste0("Reference edges are available from ", reference_source, ". Raw WoS/Scopus cited-reference fields may still be empty."),
      recommended_fix = "Treat OpenAlex-derived networks as preliminary until coverage is assessed against source database exports."
    ) %>%
    select(issue, reference_source, n_reference_edges, explanation, recommended_fix)
  readr::write_csv(diagnostic, file.path(path_get(paths, "outputs.logs"), "reference_network_diagnostic.csv"))
}

message("Wrote network and diffusion outputs.")
