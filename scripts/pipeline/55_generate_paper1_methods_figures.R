#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(stringr)
  library(tidyr)
  library(grid)
})

root <- normalizePath(getwd(), mustWork = TRUE)
tables_dir <- file.path(root, "analysis", "tables")
fig_dir <- file.path(root, "analysis", "figures", "paper1")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)

theme_paper1 <- function(base_size = 11) {
  theme_minimal(base_size = base_size) +
    theme(
      plot.title = element_text(face = "bold", size = base_size + 2, margin = margin(b = 5)),
      plot.subtitle = element_text(size = base_size, color = "#444444", margin = margin(b = 8)),
      plot.caption = element_text(size = base_size - 2, color = "#555555", hjust = 0),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      legend.position = "bottom",
      legend.title = element_blank()
    )
}

save_pair <- function(plot, stem, width = 8, height = 5) {
  png_path <- file.path(fig_dir, paste0(stem, ".png"))
  pdf_path <- file.path(fig_dir, paste0(stem, ".pdf"))
  ggsave(png_path, plot, width = width, height = height, dpi = 320, bg = "white")
  ggsave(pdf_path, plot, width = width, height = height, device = "pdf", bg = "white")
}

workflow <- tibble(
  step = c("Corpus", "Extraction", "Recovery", "Router", "Classification", "Validation", "Adjudication", "Corpus\nDeployment"),
  x = seq_len(8),
  y = 1
)

p1 <- ggplot(workflow, aes(x, y)) +
  geom_segment(
    data = workflow %>% filter(x < max(x)),
    aes(x = x + 0.36, xend = x + 0.64, y = y, yend = y),
    arrow = arrow(length = unit(0.13, "inches")),
    linewidth = 0.45,
    color = "#555555"
  ) +
  geom_label(
    aes(label = step),
    size = 3.2,
    linewidth = 0.35,
    label.r = unit(0.12, "lines"),
    fill = "white",
    color = "#222222",
    label.padding = unit(0.28, "lines")
  ) +
  scale_x_continuous(limits = c(0.5, 8.5)) +
  scale_y_continuous(limits = c(0.65, 1.35)) +
  labs(
    title = "Frozen Contextual Bibliometrics Workflow",
    subtitle = "Paper 1 methods pipeline from corpus construction to deployment",
    caption = "Workflow summarizes the frozen v2.0 methodology; it does not represent new classification activity."
  ) +
  theme_void(base_size = 11) +
  theme(
    plot.title = element_text(face = "bold", size = 13, margin = margin(b = 5)),
    plot.subtitle = element_text(size = 11, color = "#444444", margin = margin(b = 8)),
    plot.caption = element_text(size = 9, color = "#555555", hjust = 0),
    plot.title.position = "plot",
    plot.caption.position = "plot"
  )
save_pair(p1, "paper1_figure1_workflow", width = 10.5, height = 3.2)

validation <- read_csv(file.path(tables_dir, "final_validation_summary.csv"), show_col_types = FALSE) %>%
  transmute(
    metric = recode(
      validation_area,
      "Extraction Recovery" = "Recovery helpfulness",
      "Bibliography Audit" = "Bibliography precision",
      "Modeling" = "Modeling agreement",
      "Historical/Foundation" = "Historical/foundational agreement",
      "Router-Safe Batch A" = "Router-safe agreement",
      .default = validation_area
    ),
    value = case_when(
      validation_area == "Extraction Recovery" ~ 10 / 11,
      TRUE ~ suppressWarnings(as.numeric(agreement_rate))
    ),
    reviewed_rows = reviewed_rows
  ) %>%
  filter(metric %in% c(
    "Recovery helpfulness",
    "Bibliography precision",
    "Modeling agreement",
    "Historical/foundational agreement",
    "Router-safe agreement"
  )) %>%
  mutate(metric = factor(metric, levels = rev(c(
    "Recovery helpfulness",
    "Bibliography precision",
    "Router-safe agreement",
    "Modeling agreement",
    "Historical/foundational agreement"
  ))))

p2 <- ggplot(validation, aes(metric, value)) +
  geom_col(fill = "#4C78A8", width = 0.65) +
  geom_text(aes(label = paste0(round(100 * value, 1), "%")), hjust = -0.12, size = 3.4) +
  coord_flip() +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1), limits = c(0, 1.05), expand = expansion(mult = c(0, 0))) +
  labs(
    title = "Validation Summary Metrics",
    subtitle = "Frozen validation metrics used for Paper 1 methods claims",
    x = NULL,
    y = "Observed validation metric",
    caption = "Metrics use reviewed subsets only; recovery helpfulness is not classifier agreement."
  ) +
  theme_paper1()
save_pair(p2, "paper1_figure2_validation_summary", width = 8.2, height = 4.7)

boundary <- read_csv(file.path(tables_dir, "automation_boundary_framework.csv"), show_col_types = FALSE) %>%
  count(automation_status, name = "n_tasks") %>%
  mutate(
    automation_status = factor(
      automation_status,
      levels = c("automated_low_risk", "automated_with_audit", "hybrid_review_required", "human_required", "exploratory_only")
    ),
    status_label = recode(
      as.character(automation_status),
      automated_low_risk = "Automated\nlow risk",
      automated_with_audit = "Automated\nwith audit",
      hybrid_review_required = "Hybrid review\nrequired",
      human_required = "Human\nrequired",
      exploratory_only = "Exploratory\nonly"
    )
  )
boundary_colors <- c(
  automated_low_risk = "#4C78A8",
  automated_with_audit = "#72B7B2",
  hybrid_review_required = "#F58518",
  human_required = "#E45756",
  exploratory_only = "#8E8E8E"
)

p3 <- ggplot(boundary, aes(automation_status, n_tasks, fill = automation_status)) +
  geom_col(width = 0.62) +
  geom_text(aes(label = n_tasks), vjust = -0.3, size = 3.5) +
  scale_x_discrete(labels = boundary$status_label) +
  scale_fill_manual(values = boundary_colors, drop = FALSE, guide = "none") +
  scale_y_continuous(expand = expansion(mult = c(0, 0.18)), breaks = scales::pretty_breaks()) +
  labs(
    title = "Automation Boundary By Task",
    subtitle = "Task statuses assigned from project validation evidence",
    x = NULL,
    y = "Number of methods tasks",
    caption = "Status values are not performance claims outside the validated workflow."
  ) +
  theme_paper1()
save_pair(p3, "paper1_figure3_automation_boundary", width = 8.4, height = 4.8)

labor <- read_csv(file.path(tables_dir, "human_effort_estimates.csv"), show_col_types = FALSE) %>%
  mutate(
    workflow_label = recode(workflow, fully_manual = "Fully manual", hybrid_frozen_v2_0 = "Hybrid workflow"),
    time_assumption = factor(time_assumption, levels = c("fast", "moderate", "slow"), labels = c("Fast\n45 sec", "Moderate\n90 sec", "Slow\n180 sec"))
  )

p4 <- ggplot(labor, aes(time_assumption, estimated_hours, fill = workflow_label)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.62) +
  geom_text(
    aes(label = sprintf("%.1f", estimated_hours)),
    position = position_dodge(width = 0.72),
    vjust = -0.25,
    size = 3.1
  ) +
  scale_fill_manual(values = c("Fully manual" = "#9A9A9A", "Hybrid workflow" = "#4C78A8")) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.16))) +
  labs(
    title = "Estimated Human Coding Labor",
    subtitle = "Fully manual versus frozen hybrid workflow",
    x = "Time-per-context assumption",
    y = "Estimated hours",
    caption = "Planning estimate only; hybrid estimate includes already-reviewed and unresolved/needs-review rows."
  ) +
  theme_paper1()
save_pair(p4, "paper1_figure4_labor_reduction", width = 8.2, height = 4.8)

message("Created Paper 1 figures in ", fig_dir)
