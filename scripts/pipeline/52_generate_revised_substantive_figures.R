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
fig_dir <- file.path(root, "analysis", "figures", "substantive_revised")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

function_order <- c(
  "historical_framing",
  "foundational_citation",
  "modeling_simulation_reference"
)

function_labels <- c(
  historical_framing = "Historical\nframing",
  foundational_citation = "Foundational\ncitation",
  modeling_simulation_reference = "Modeling /\nsimulation"
)

legend_labels <- c(
  historical_framing = "Historical framing",
  foundational_citation = "Foundational citation",
  modeling_simulation_reference = "Modeling / simulation"
)

function_colors <- c(
  historical_framing = "#2F6B9A",
  foundational_citation = "#D97918",
  modeling_simulation_reference = "#3C8D40",
  unclear = "#8E8E8E"
)

theme_journal <- function(base_size = 11) {
  theme_minimal(base_size = base_size) +
    theme(
      plot.title = element_text(face = "bold", size = base_size + 2, margin = margin(b = 4)),
      plot.subtitle = element_text(size = base_size, color = "#444444", margin = margin(b = 8)),
      plot.caption = element_text(size = base_size - 2, color = "#555555", hjust = 0),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.key.width = unit(1.1, "lines"),
      axis.title.x = element_text(margin = margin(t = 8)),
      axis.title.y = element_text(margin = margin(r = 8))
    )
}

save_pair <- function(plot, stem, width = 7.2, height = 4.8) {
  png_path <- file.path(fig_dir, paste0(stem, ".png"))
  pdf_path <- file.path(fig_dir, paste0(stem, ".pdf"))
  ggsave(png_path, plot, width = width, height = height, dpi = 320, bg = "white")
  ggsave(pdf_path, plot, width = width, height = height, device = "pdf", bg = "white")
  list(png = png_path, pdf = pdf_path)
}

format_pct <- function(x) paste0("(", sprintf("%.1f", 100 * x), "%)")

short_field_label <- function(x) {
  recode(
    x,
    "ECOLOGICAL ECONOMICS" = "Ecological Economics",
    "ENERGY POLICY" = "Energy Policy",
    "Environment Development and Sustainability" = "Env. Development & Sustainability",
    "ANNUAL REVIEW OF ENVIRONMENT AND RESOURCES, VOL 43" = "Annual Review Env. & Resources",
    "Other" = "Other",
    .default = x
  )
}

reorder_factor_by_total <- function(group, total) {
  totals <- tapply(total, group, max)
  factor(group, levels = names(sort(totals, decreasing = FALSE)))
}

figure1 <- read_csv(file.path(tables_dir, "figure1_citation_function_distribution.csv"), show_col_types = FALSE) %>%
  mutate(
    citation_function = factor(citation_function, levels = function_order),
    label = paste0(n_contexts, "\n", format_pct(pct_contexts))
  )

p1 <- ggplot(figure1, aes(citation_function, n_contexts, fill = citation_function)) +
  geom_col(width = 0.62) +
  geom_text(aes(label = label), vjust = -0.25, lineheight = 0.95, size = 3.7) +
  scale_x_discrete(labels = function_labels) +
  scale_fill_manual(values = function_colors, guide = "none") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.2))) +
  labs(
    title = "Citation Function Distribution",
    subtitle = "Reviewed substantive contexts only (n = 43)",
    x = NULL,
    y = "Context count",
    caption = "Bibliography-only and unresolved records excluded."
  ) +
  theme_journal()
p1_paths <- save_pair(p1, "figure1_citation_function_distribution_revised")

figure2_raw <- read_csv(file.path(tables_dir, "figure2_citation_function_by_decade.csv"), show_col_types = FALSE)
figure2 <- figure2_raw %>%
  mutate(
    decade = if_else(is.na(decade) | decade == "", "Unknown", str_to_title(decade)),
    citation_function = factor(citation_function, levels = function_order)
  )

complete_decades <- expand_grid(
  decade = unique(figure2$decade),
  citation_function = factor(function_order, levels = function_order)
) %>%
  left_join(figure2, by = c("decade", "citation_function")) %>%
  mutate(n_contexts = replace_na(n_contexts, 0))

decade_totals <- complete_decades %>%
  group_by(decade) %>%
  summarise(total = sum(n_contexts), .groups = "drop")

p2 <- ggplot(complete_decades, aes(decade, n_contexts, fill = citation_function)) +
  geom_col(position = position_dodge(width = 0.74), width = 0.66) +
  geom_text(
    data = decade_totals,
    aes(x = decade, y = total + 0.5, label = paste0("n=", total)),
    inherit.aes = FALSE,
    size = 3.1,
    color = "#444444"
  ) +
  scale_fill_manual(values = function_colors, labels = legend_labels) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18)), breaks = scales::pretty_breaks()) +
  labs(
    title = "Citation Function By Decade",
    subtitle = "Grouped counts; no fitted trend",
    x = "Decade",
    y = "Context count",
    caption = "Decade sample sizes are shown above each group."
  ) +
  theme_journal()
p2_paths <- save_pair(p2, "figure2_citation_function_by_decade_clustered", width = 8.4, height = 5.1)

figure3 <- read_csv(file.path(tables_dir, "figure3_modeling_persistence.csv"), show_col_types = FALSE) %>%
  mutate(
    year_label = if_else(is.na(year) | year == "", "Unknown year", as.character(year)),
    year_sort = suppressWarnings(as.integer(year)),
    year_sort = if_else(is.na(year_sort), 9999L, year_sort)
  ) %>%
  arrange(year_sort, context_group_id) %>%
  mutate(
    context_index = row_number(),
    year_label = factor(year_label, levels = unique(year_label))
  )

p3 <- ggplot(figure3, aes(year_label, context_index)) +
  geom_point(color = function_colors[["modeling_simulation_reference"]], size = 3.2, alpha = 0.95) +
  scale_y_continuous(breaks = NULL) +
  labs(
    title = "Modeling / Simulation References Over Time",
    subtitle = "Each point is a reviewed modeling/simulation context; counts are small.",
    x = "Year",
    y = "Individual reviewed contexts",
    caption = "Unknown-year records are shown separately rather than imputed."
  ) +
  theme_journal() +
  theme(axis.text.x = element_text(angle = 35, hjust = 1))
p3_paths <- save_pair(p3, "figure3_modeling_persistence_dotplot", width = 8.2, height = 4.7)

figure4_raw <- read_csv(file.path(tables_dir, "figure4_field_function_distribution.csv"), show_col_types = FALSE)
field_totals <- figure4_raw %>%
  group_by(field_or_venue) %>%
  summarise(field_total = sum(n_contexts), .groups = "drop") %>%
  arrange(desc(field_total), field_or_venue)
top_fields <- field_totals %>%
  filter(field_total >= 2, field_or_venue != "", field_or_venue != "unknown", !is.na(field_or_venue)) %>%
  pull(field_or_venue)

figure4 <- figure4_raw %>%
  mutate(
    field_group = if_else(field_or_venue %in% top_fields, field_or_venue, "Other"),
    field_group = short_field_label(field_group),
    citation_function = factor(citation_function, levels = function_order)
  ) %>%
  group_by(field_group, citation_function) %>%
  summarise(n_contexts = sum(n_contexts), .groups = "drop") %>%
  group_by(field_group) %>%
  mutate(field_total = sum(n_contexts)) %>%
  ungroup() %>%
  mutate(field_group = reorder_factor_by_total(field_group, field_total))

p4 <- ggplot(figure4, aes(field_group, n_contexts, fill = citation_function)) +
  geom_col(width = 0.72) +
  coord_flip() +
  scale_fill_manual(values = function_colors, labels = legend_labels) +
  labs(
    title = "Citation Function By Field Or Venue",
    subtitle = "Sparse and unknown field/venue values aggregated as Other",
    x = NULL,
    y = "Context count",
    caption = "field_or_venue is a proxy label; this figure is for cautious comparison only."
  ) +
  theme_journal() +
  theme(axis.text.y = element_text(size = 9.5))
p4_paths <- save_pair(p4, "figure4_field_function_distribution_revised", width = 8.4, height = 5.2)

figure5 <- complete_decades %>%
  filter(citation_function %in% c("historical_framing", "foundational_citation"))

p5 <- ggplot(figure5, aes(decade, n_contexts, fill = citation_function)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.64) +
  scale_fill_manual(values = function_colors, labels = legend_labels[c("historical_framing", "foundational_citation")]) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.14)), breaks = scales::pretty_breaks()) +
  labs(
    title = "Historical Framing And Foundational Citation By Decade",
    subtitle = "Comparison of reviewed contexts; not a transition claim",
    x = "Decade",
    y = "Context count",
    caption = "Use as a descriptive comparison only."
  ) +
  theme_journal()
p5_paths <- save_pair(p5, "figure5_historical_vs_foundational_by_decade", width = 8.0, height = 4.8)

manifest <- tibble::tribble(
  ~figure, ~source_table, ~output_png, ~output_pdf, ~change_made, ~caveat,
  "Figure 1 Revised", "analysis/tables/figure1_citation_function_distribution.csv",
  "analysis/figures/substantive_revised/figure1_citation_function_distribution_revised.png",
  "analysis/figures/substantive_revised/figure1_citation_function_distribution_revised.pdf",
  "Wrapped category labels and split count/percent labels across two lines.",
  "Reviewed substantive contexts only; n=43.",
  "Figure 2 Revised", "analysis/tables/figure2_citation_function_by_decade.csv",
  "analysis/figures/substantive_revised/figure2_citation_function_by_decade_clustered.png",
  "analysis/figures/substantive_revised/figure2_citation_function_by_decade_clustered.pdf",
  "Changed stacked bars to grouped bars and added decade sample-size labels.",
  "No fitted trend; small decade-level counts.",
  "Figure 3 Revised", "analysis/tables/figure3_modeling_persistence.csv",
  "analysis/figures/substantive_revised/figure3_modeling_persistence_dotplot.png",
  "analysis/figures/substantive_revised/figure3_modeling_persistence_dotplot.pdf",
  "Changed bar chart to one-point-per-context dot plot.",
  "Modeling n=10; unknown year shown separately.",
  "Figure 4 Revised", "analysis/tables/figure4_field_function_distribution.csv",
  "analysis/figures/substantive_revised/figure4_field_function_distribution_revised.png",
  "analysis/figures/substantive_revised/figure4_field_function_distribution_revised.pdf",
  "Shortened field labels and aggregated sparse/unknown groups as Other.",
  "field_or_venue is a proxy; many groups are sparse.",
  "Figure 5 Optional", "analysis/tables/figure2_citation_function_by_decade.csv",
  "analysis/figures/substantive_revised/figure5_historical_vs_foundational_by_decade.png",
  "analysis/figures/substantive_revised/figure5_historical_vs_foundational_by_decade.pdf",
  "Added grouped historical vs foundational comparison.",
  "Not a transition claim."
)
write_csv(manifest, file.path(fig_dir, "revised_figure_manifest.csv"))

interpretation <- c(
  "# Revised Figure Interpretation Packet",
  "",
  "Scope: figure-reading notes for revised publication-quality figures. These are not manuscript results text.",
  "",
  "## Figure 1 Revised",
  "",
  "- What changed from the original figure: labels were shortened/wrapped, and counts and percentages were split across two lines.",
  "- Why the revision improves readability: category names fit cleanly on the x-axis and numeric labels are easier to scan.",
  "- What the figure supports: the reviewed substantive corpus contains historical framing, foundational citation, and modeling/simulation references.",
  "- What not to claim yet: do not claim corpus-wide prevalence or dominance from this small reviewed subset.",
  "",
  "## Figure 2 Revised",
  "",
  "- What changed from the original figure: stacked bars were replaced with grouped bars by decade.",
  "- Why the revision improves readability: each function can be compared within decade without decoding stacked segments.",
  "- What the figure supports: decade-level counts can be inspected descriptively.",
  "- What not to claim yet: do not claim a fitted trend or a transition pattern.",
  "",
  "## Figure 3 Revised",
  "",
  "- What changed from the original figure: the bar chart was replaced by a dot plot with one point per modeling/simulation context.",
  "- Why the revision improves readability: individual contexts are visible and the graphic avoids implying a statistical trend.",
  "- What the figure supports: reviewed modeling/simulation references appear at multiple observed time points.",
  "- What not to claim yet: do not claim growth, decline, or persistence as a statistically estimated pattern.",
  "",
  "## Figure 4 Revised",
  "",
  "- What changed from the original figure: field/venue labels were shortened, sparse groups were aggregated, and horizontal bars were retained.",
  "- Why the revision improves readability: long labels no longer dominate the plot area, and sparse rows are less distracting.",
  "- What the figure supports: available field_or_venue proxies can be compared cautiously by citation function.",
  "- What not to claim yet: do not claim discipline-level diffusion patterns without stronger field normalization.",
  "",
  "## Figure 5 Optional",
  "",
  "- What changed from the original figure set: a focused historical-versus-foundational decade comparison was added.",
  "- Why the revision improves readability: it isolates the main boundary comparison from the modeling category.",
  "- What the figure supports: the reviewed historical and foundational contexts can be compared by decade.",
  "- What not to claim yet: do not describe this as evidence of a transition."
)
writeLines(interpretation, file.path(tables_dir, "figure_interpretation_packet_revised.md"))

message("Created revised substantive figures in ", fig_dir)
message("Figure 4 sparse/unknown source rows aggregated as Other: ",
        sum(!figure4_raw$field_or_venue %in% top_fields | is.na(figure4_raw$field_or_venue) | figure4_raw$field_or_venue == ""))
