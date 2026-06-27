.PHONY: setup metadata canonical external contexts networks figures llm validation topics inventory tests report findings pipeline

setup:
	Rscript scripts/pipeline/00_setup.R

metadata:
	Rscript scripts/pipeline/01_ingest_raw_metadata.R
	Rscript scripts/pipeline/02_harmonize_and_deduplicate.R

canonical:
	Rscript scripts/pipeline/03_build_canonical_works.R

external:
	Rscript scripts/pipeline/04_reconcile_external_metadata.R

contexts:
	Rscript scripts/pipeline/03_extract_citation_contexts.R
	Rscript scripts/pipeline/04_consolidate_contexts.R
	Rscript scripts/pipeline/05_enrich_citation_contexts.R

networks:
	Rscript scripts/pipeline/05_build_networks_and_diffusion.R

figures:
	Rscript scripts/pipeline/06_make_tables_and_figures.R

llm:
	python3 scripts/pipeline/07_classify_contexts_llm.py

validation:
	Rscript scripts/pipeline/08_build_validation_sample.R
	Rscript scripts/pipeline/09_compare_validation.R

topics:
	Rscript scripts/pipeline/11_topic_clustering.R

inventory:
	Rscript scripts/pipeline/12_write_data_inventory.R

tests:
	Rscript scripts/pipeline/13_run_tests.R

report:
	quarto render reports/methodology.qmd --output-dir ../analysis/reports

findings:
	quarto render reports/findings_preliminary.qmd --output-dir ../analysis/reports

pipeline:
	Rscript scripts/pipeline/run_pipeline.R
