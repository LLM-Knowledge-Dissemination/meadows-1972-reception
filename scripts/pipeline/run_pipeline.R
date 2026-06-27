stages <- c(
  "scripts/pipeline/00_setup.R",
  "scripts/pipeline/01_ingest_raw_metadata.R",
  "scripts/pipeline/02_harmonize_and_deduplicate.R",
  "scripts/pipeline/03_build_canonical_works.R",
  "scripts/pipeline/04_reconcile_external_metadata.R",
  "scripts/pipeline/03_extract_citation_contexts.R",
  "scripts/pipeline/04_consolidate_contexts.R",
  "scripts/pipeline/05_enrich_citation_contexts.R",
  "scripts/pipeline/05_build_networks_and_diffusion.R",
  "scripts/pipeline/07_classify_contexts_llm.py",
  "scripts/pipeline/06_make_tables_and_figures.R",
  "scripts/pipeline/08_build_validation_sample.R",
  "scripts/pipeline/09_compare_validation.R",
  "scripts/pipeline/10_build_diffusion_outputs.R",
  "scripts/pipeline/11_topic_clustering.R",
  "scripts/pipeline/12_write_data_inventory.R"
)

for (stage in stages) {
  message("\n==> ", stage)
  if (grepl("\\.py$", stage)) {
    system2("python3", stage, stdout = TRUE, stderr = TRUE)
  } else {
    source(stage, local = new.env(parent = globalenv()))
  }
}
