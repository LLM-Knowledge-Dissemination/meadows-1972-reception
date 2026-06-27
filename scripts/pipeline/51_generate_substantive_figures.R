#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(stringr)
  library(tidyr)
})

root <- normalizePath(getwd(), mustWork = TRUE)
tables_dir <- file.path(root, "analysis", "tables")
fig_dir <- file.path(root, "analysis", "figures", "substantive")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

function_labels <- c(
  historical_framing = "Historical framing",
  foundational_citation = "Foundational citation",
  modeling_simulation_reference = "Modeling/simulation"
)

function_colors <- c(
  historical_framing = "#4C78A8",
  foundational_citation = "#F58518",
  modeling_simulation_reference = "#54A24B"
)

theme_substantive <- function(base_size = 11) {
  theme_minimal(base_size = base_size) +
    theme(
      panel.grid.minor = element_blank(),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      legend.position = "bottom",
      axis.title.x = element_text(margin = margin(t = 8)),
      axis.title.y = element_text(margin = margin(r = 8))
    )
}

save_plot_pair <- function(plot, stem, width = 8, height = 5.2) {
  png_path <- file.path(fig_dir, paste0(stem, ".png"))
  pdf_path <- file.path(fig_dir, paste0(stem, ".pdf"))
  ggsave(png_path, plot, width = width, height = height, dpi = 320, bg = "white")
  ggsave(pdf_path, plot, width = width, height = height, device = "pdf", bg = "white")
  list(png = png_path, pdf = pdf_path)
}

format_pct <- function(x) paste0(round(100 * x, 1), "%")

fig1 <- read_csv(file.path(tables_dir, "figure1_citation_function_distribution.csv"), show_col_types = FALSE) %>%
  mutate(
    citation_function = factor(citation_function, levels = names(function_labels)),
    label = paste0(n_contexts, " (", format_pct(pct_contexts), ")")
  )

p1 <- ggplot(fig1, aes(x = citation_function, y = n_contexts, fill = citation_function)) +
  geom_col(width = 0.68) +
  geom_text(aes(label = label), vjust = -0.35, size = 3.5) +
  scale_x_discrete(labels = function_labels) +
  scale_fill_manual(values = function_colors, guide = "none") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.14))) +
  labs(
    title = "Citation function distribution",
    x = NULL,
    y = "Human-reviewed substantive contexts",
    caption = "Source: frozen v2.0 substantive corpus; bibliography-only and unresolved records excluded."
  ) +
  theme_substantive()
p1_paths <- save_plot_pair(p1, "figure1_citation_function_distribution")

fig2_raw <- read_csv(file.path(tables_dir, "figure2_citation_function_by_decade.csv"), show_col_types = FALSE)
fig2 <- fig2_raw %>%
  filter(decade != "unknown") %>%
  mutate(citation_function = factor(citation_function, levels = names(function_labels)))
decade_totals <- fig2 %>%
  group_by(decade) %>%
  summarise(total = sum(n_contexts), .groups = "drop")

p2 <- ggplot(fig2, aes(x = decade, y = n_contexts, fill = citation_function)) +
  geom_col(width = 0.72) +
  geom_text(
    data = decade_totals,
    aes(x = decade, y = total, label = paste0("n=", total)),
    inherit.aes = FALSE,
    vjust = -0.35,
    size = 3.2
  ) +
  scale_fill_manual(values = function_colors, labels = function_labels, name = NULL) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.16))) +
  labs(
    title = "Citation function by decade",
    x = "Decade",
    y = "Context count",
    caption = "Counts are decade-level totals from the substantive corpus; no smoothing or trend model applied."
  ) +
  theme_substantive()
p2_paths <- save_plot_pair(p2, "figure2_citation_function_by_decade")

fig3_raw <- read_csv(file.path(tables_dir, "figure3_modeling_persistence.csv"), show_col_types = FALSE)
fig3 <- fig3_raw %>%
  mutate(decade = if_else(is.na(decade) | decade == "", "unknown", decade)) %>%
  count(decade, name = "n_contexts") %>%
  mutate(decade = factor(decade, levels = c(sort(setdiff(unique(decade), "unknown")), "unknown")))

p3 <- ggplot(fig3, aes(x = decade, y = n_contexts)) +
  geom_col(fill = function_colors[["modeling_simulation_reference"]], width = 0.68) +
  geom_text(aes(label = n_contexts), vjust = -0.35, size = 3.4) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18))) +
  labs(
    title = "Modeling/simulation references over time",
    x = "Decade",
    y = "Modeling/simulation contexts",
    caption = "Small counts are shown directly; the figure should be read as persistence evidence, not a fitted trend."
  ) +
  theme_substantive()
p3_paths <- save_plot_pair(p3, "figure3_modeling_persistence")

fig4_raw <- read_csv(file.path(tables_dir, "figure4_field_function_distribution.csv"), show_col_types = FALSE)
field_totals <- fig4_raw %>%
  group_by(field_or_venue) %>%
  summarise(field_total = sum(n_contexts), .groups = "drop") %>%
  arrange(desc(field_total), field_or_venue)
top_fields <- field_totals %>%
  filter(field_total >= 2, field_or_venue != "", field_or_venue != "unknown", !is.na(field_or_venue)) %>%
  pull(field_or_venue)

fct_reorder_no_package <- function(x, by) {
  totals <- tapply(by, x, max)
  factor(x, levels = names(sort(totals, decreasing = FALSE)))
}

fig4 <- fig4_raw %>%
  mutate(
    field_group = if_else(field_or_venue %in% top_fields, field_or_venue, "Other"),
    citation_function = factor(citation_function, levels = names(function_labels))
  ) %>%
  group_by(field_group, citation_function) %>%
  summarise(n_contexts = sum(n_contexts), .groups = "drop") %>%
  group_by(field_group) %>%
  mutate(field_total = sum(n_contexts), pct_within_field = n_contexts / field_total) %>%
  ungroup() %>%
  mutate(field_group = fct_reorder_no_package(field_group, field_total))

p4 <- ggplot(fig4, aes(x = field_group, y = n_contexts, fill = citation_function)) +
  geom_col(width = 0.72) +
  coord_flip() +
  scale_fill_manual(values = function_colors, labels = function_labels, name = NULL) +
  labs(
    title = "Citation function by field or venue",
    x = NULL,
    y = "Context count",
    caption = "Fields/venues with fewer than two contexts, blanks, and sparse categories are aggregated as Other."
  ) +
  theme_substantive()
p4_paths <- save_plot_pair(p4, "figure4_field_function_distribution", width = 8.6, height = 6)

manifest <- tibble::tribble(
  ~figure, ~source_table, ~output_png, ~output_pdf, ~row_count, ~notes,
  "Figure 1", "analysis/tables/figure1_citation_function_distribution.csv",
  "analysis/figures/substantive/figure1_citation_function_distribution.png",
  "analysis/figures/substantive/figure1_citation_function_distribution.pdf",
  nrow(fig1), "Counts and percentages across three substantive citation-function categories.",
  "Figure 2", "analysis/tables/figure2_citation_function_by_decade.csv",
  "analysis/figures/substantive/figure2_citation_function_by_decade.png",
  "analysis/figures/substantive/figure2_citation_function_by_decade.pdf",
  nrow(fig2_raw), "Decade-level counts only; sample sizes labeled; unknown-decade rows are excluded from the plot.",
  "Figure 3", "analysis/tables/figure3_modeling_persistence.csv",
  "analysis/figures/substantive/figure3_modeling_persistence.png",
  "analysis/figures/substantive/figure3_modeling_persistence.pdf",
  nrow(fig3_raw), "Small modeling count; read conservatively as persistence, not trend.",
  "Figure 4", "analysis/tables/figure4_field_function_distribution.csv",
  "analysis/figures/substantive/figure4_field_function_distribution.png",
  "analysis/figures/substantive/figure4_field_function_distribution.pdf",
  nrow(fig4_raw), "Sparse fields aggregated into Other."
)
write_csv(manifest, file.path(fig_dir, "figure_source_manifest.csv"))

interpretation_packet <- c(
  "# Figure Interpretation Packet",
  "",
  "Scope: figure-reading notes for the frozen v2.0 substantive corpus. These notes are not manuscript prose and should not be used as final impact claims.",
  "",
  "## Figure 1: Citation Function Distribution",
  "",
  "- What the figure shows: counts and percentages for historical framing, foundational citation, and modeling/simulation references in the substantive corpus.",
  "- Strongest supported reading: all three functions are represented among human-reviewed substantive contexts.",
  "- Alternative readings: differences in bar height may reflect validation sampling and corpus construction as much as underlying citation practice.",
  "- Evidence-level caveats: the plotted substantive corpus is Level 2 human-reviewed evidence only after bibliography-only records are excluded.",
  "- Sample-size caveats: total n is 43; category counts are small.",
  "- What not to claim yet: do not claim corpus-wide prevalence or field-wide dominance from this figure alone.",
  "",
  "## Figure 2: Citation Function By Decade",
  "",
  "- What the figure shows: decade-level counts of citation functions, with visible decade sample sizes.",
  "- Strongest supported reading: the available reviewed contexts can be organized into decade-level function counts.",
  "- Alternative readings: apparent decade differences may reflect which rows were prioritized for validation.",
  "- Evidence-level caveats: the figure excludes bibliography-only, unresolved, and non-human-reviewed contexts.",
  "- Sample-size caveats: several decades have very small n; no smoothing or trend model is applied.",
  "- What not to claim yet: do not claim a historical transition without broader validated coverage.",
  "",
  "## Figure 3: Modeling/Simulation Persistence",
  "",
  "- What the figure shows: counts of modeling/simulation references by decade, including any unknown-date records.",
  "- Strongest supported reading: modeling/simulation references are present in the reviewed substantive set.",
  "- Alternative readings: sparse counts may indicate either limited persistence or limited validated coverage.",
  "- Evidence-level caveats: modeling labels are human-reviewed but still based on a small validation subset.",
  "- Sample-size caveats: modeling n is 10; this is too small for strong trend claims.",
  "- What not to claim yet: do not claim growth, decline, or sustained influence as a statistical pattern.",
  "",
  "## Figure 4: Field Or Venue Function Distribution",
  "",
  "- What the figure shows: citation-function counts by available field_or_venue values, with sparse groups aggregated as Other.",
  "- Strongest supported reading: function labels can be compared across the available venue/field proxies.",
  "- Alternative readings: venue/field differences may reflect sparse sampling, incomplete field labels, or validation priorities.",
  "- Evidence-level caveats: field_or_venue is a proxy and not a fully validated disciplinary classification.",
  "- Sample-size caveats: many field/venue groups contain one or two contexts.",
  "- What not to claim yet: do not claim discipline-level diffusion patterns without a larger field-normalized table."
)
writeLines(interpretation_packet, file.path(tables_dir, "figure_interpretation_packet.md"))

next_questions <- tibble::tribble(
  ~question, ~readiness, ~required_additional_table_or_figure, ~caveat,
  "Is historical framing common enough to warrant a main result?", "analyze_with_caveat",
  "Expanded function distribution with Level 2-only and Level 2+3 sensitivity views",
  "Historical/foundational boundary validation showed router weakness; use human-reviewed rows preferentially.",
  "Does modeling persistence appear as a distinct finding?", "analyze_with_caveat",
  "Modeling references by year/decade with exemplar-linked context table",
  "Modeling n is small; avoid trend claims.",
  "Are foundational and historical uses field-dependent?", "exploratory_only",
  "Field-normalized function table with sparse-field aggregation and validation coverage counts",
  "field_or_venue is a proxy and many groups are sparse.",
  "Is the transition hypothesis supported, exploratory, or not supported?", "exploratory_only",
  "Foundational vs historical by decade with evidence-level sensitivity and validation coverage notes",
  "Current table is hypothesis-generating only.",
  "Do network clusters align with citation functions?", "exploratory_only",
  "Contextual network bridge with cluster-level function summaries and coverage indicators",
  "Do not overinterpret OpenAlex-derived networks or sparse contextual labels."
)
write_csv(next_questions, file.path(tables_dir, "next_substantive_analysis_questions.csv"))

message("Created substantive figures in ", fig_dir)
message("Figure 4 groups: ", paste(levels(fig4$field_group), collapse = " | "))
message("Sparse fields aggregated into Other: ", sum(!fig4_raw$field_or_venue %in% top_fields | is.na(fig4_raw$field_or_venue) | fig4_raw$field_or_venue == ""))
