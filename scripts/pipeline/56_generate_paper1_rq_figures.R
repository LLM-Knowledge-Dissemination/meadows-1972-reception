#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(readr)
  library(stringr)
  library(tidyr)
  library(svglite)
  library(grid)
})

root <- normalizePath(getwd(), mustWork = TRUE)
fig_dir <- file.path(root, "analysis", "figures", "paper1_rq")
table_dir <- file.path(root, "analysis", "tables", "paper1_rq")
manuscript_dir <- file.path(root, "manuscript")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)

palette_status <- c(
  automated_with_audit = "#4C78A8",
  hybrid_review_required = "#ECA64C",
  human_required = "#C84B4B",
  exploratory_only = "#8C8C8C",
  evidence_preserved = "#5A9A78",
  unresolved = "#A0A0A0"
)

palette_layers <- c(
  "Extraction layer" = "#5A9A78",
  "Classification layer" = "#4C78A8",
  "Ambiguity layer" = "#ECA64C"
)

theme_paper1_rq <- function(base_size = 11) {
  theme_minimal(base_size = base_size, base_family = "Helvetica") +
    theme(
      plot.title = element_text(face = "bold", size = base_size + 3, margin = margin(b = 4)),
      plot.subtitle = element_text(size = base_size, color = "#4D4D4D", margin = margin(b = 8)),
      plot.caption = element_text(size = base_size - 2, color = "#5A5A5A", hjust = 0, margin = margin(t = 8)),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      axis.title = element_text(color = "#333333"),
      axis.text = element_text(color = "#333333"),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = base_size - 1),
      strip.text = element_text(face = "bold", color = "#333333")
    )
}

save_figure <- function(plot, stem, width = 8, height = 5) {
  png_path <- file.path(fig_dir, paste0(stem, ".png"))
  svg_path <- file.path(fig_dir, paste0(stem, ".svg"))
  ggsave(png_path, plot, width = width, height = height, dpi = 300, bg = "white")
  ggsave(svg_path, plot, width = width, height = height, device = svglite::svglite, bg = "white")
  tibble(
    file_png = file.path("analysis", "figures", "paper1_rq", paste0(stem, ".png")),
    file_svg = file.path("analysis", "figures", "paper1_rq", paste0(stem, ".svg"))
  )
}

wrap_label <- function(x, width = 24) str_wrap(x, width = width)

# Figure 1 --------------------------------------------------------------------
workflow <- tibble(
  step = c(
    "Corpus", "Extraction", "Recovery", "Routing", "Classification",
    "Validation", "Automation Boundary", "Evidence-Preserving Deployment"
  ),
  x = seq_len(8),
  y = 1,
  rq = c("", "RQ1", "RQ1", "", "RQ2", "RQ2/RQ3", "RQ3", "RQ4"),
  stage_group = c("Corpus", "Extraction quality", "Extraction quality", "Classification", "Classification", "Validation", "Boundary", "Deployment")
)

write_csv(workflow, file.path(table_dir, "paper1_rq_figure1_workflow_source.csv"))

fig1_colors <- c(
  green = "#5A9B75",
  blue = "#4F7EAD",
  orange = "#F0A641",
  gray = "#9A9A9A",
  light_panel = "#F6F7F8",
  border = "#D9DEE3",
  text = "#222222",
  muted_text = "#4D4D4D"
)

fig1_regions <- tibble(
  rq_label = c("RQ1", "RQ2", "RQ3", "RQ4"),
  region_label = c(
    "Extraction /\nrecovery",
    "Function validation",
    "Boundary\nderivation",
    "Evidence\npreservation"
  ),
  xmin = c(1.65, 3.65, 6.65, 7.55),
  xmax = c(3.35, 6.35, 7.35, 8.45),
  x = c(2.5, 5, 7, 8),
  color = c(
    fig1_colors[["green"]],
    fig1_colors[["blue"]],
    fig1_colors[["orange"]],
    fig1_colors[["gray"]]
  )
)

fig1_subtitle_lookup <- c(
  Corpus = "cited-work corpus",
  Extraction = "context retrieval",
  Recovery = "context repair",
  Routing = "function pathways",
  Classification = "function assignment",
  Validation = "task-specific audits",
  `Automation Boundary` = "status derivation",
  `Evidence-Preserving Deployment` = "metadata retention"
)

make_fig1 <- function(show_stage_subtitles = FALSE) {
  workflow_labels <- workflow %>%
    mutate(
      stage_subtitle = unname(fig1_subtitle_lookup[step]),
      plot_label = if (show_stage_subtitles) {
        paste0(wrap_label(step, 15), "\n", stage_subtitle)
      } else {
        wrap_label(step, 15)
      }
    )

  ggplot(workflow_labels, aes(x, y)) +
    annotate(
      "rect",
      xmin = 0.55,
      xmax = 8.45,
      ymin = 0.76,
      ymax = 1.25,
      fill = fig1_colors[["light_panel"]],
      color = fig1_colors[["border"]],
      linewidth = 0.35
    ) +
    geom_rect(
      data = fig1_regions,
      aes(xmin = xmin, xmax = xmax, ymin = 0.78, ymax = 1.23),
      inherit.aes = FALSE,
      fill = grDevices::adjustcolor(fig1_regions$color, alpha.f = 0.11),
      color = NA
    ) +
    geom_segment(
      data = workflow_labels %>% filter(x < max(x)),
      aes(x = x + 0.36, xend = x + 0.64, y = y, yend = y),
      arrow = arrow(length = unit(0.08, "inches"), type = "closed"),
      linewidth = 0.36,
      color = "#8A8A8A"
    ) +
    geom_label(
      aes(label = plot_label),
      fill = "white",
      color = fig1_colors[["text"]],
      linewidth = 0.28,
      label.r = unit(0.12, "lines"),
      label.padding = unit(if_else(show_stage_subtitles, 0.18, 0.22), "lines"),
      size = if_else(show_stage_subtitles, 2.45, 2.95),
      lineheight = if_else(show_stage_subtitles, 0.82, 0.92)
    ) +
    geom_label(
      data = fig1_regions,
      aes(x = x, y = 1.44, label = rq_label),
      inherit.aes = FALSE,
      fill = "white",
      color = fig1_regions$color,
      linewidth = 0.28,
      label.r = unit(0.10, "lines"),
      label.padding = unit(0.16, "lines"),
      size = 2.8,
      fontface = "bold"
    ) +
    geom_segment(
      data = fig1_regions,
      aes(x = xmin + 0.1, xend = xmax - 0.1, y = 0.57, yend = 0.57),
      inherit.aes = FALSE,
      linewidth = 1.8,
      color = fig1_regions$color,
      lineend = "round"
    ) +
    geom_text(
      data = fig1_regions,
      aes(x = x, y = 0.42, label = region_label),
      inherit.aes = FALSE,
      size = 2.65,
      color = fig1_colors[["muted_text"]],
      lineheight = 0.95
    ) +
    scale_x_continuous(limits = c(0.45, 8.55), expand = c(0, 0)) +
    scale_y_continuous(limits = c(0.25, 1.63), expand = c(0, 0)) +
    labs(
      title = "Frozen Contextual Bibliometrics Workflow",
      subtitle = "The methods paper evaluates a staged workflow, not a single classifier.",
      caption = "RQ1 concerns extraction and recovery; RQ2 citation-function automation potential; RQ3 automation boundaries; RQ4 evidence-preserving deployment."
    ) +
    theme_void(base_size = 11, base_family = "Helvetica") +
    theme(
      plot.title = element_text(face = "bold", size = 14, margin = margin(b = 4)),
      plot.subtitle = element_text(size = 11, color = fig1_colors[["muted_text"]], margin = margin(b = 10)),
      plot.caption = element_text(size = 8.8, color = "#5A5A5A", hjust = 0, margin = margin(t = 8)),
      plot.title.position = "plot",
      plot.caption.position = "plot"
    )
}

fig1_clean <- make_fig1(show_stage_subtitles = FALSE)
fig1_subtitles <- make_fig1(show_stage_subtitles = TRUE)

fig1_files <- save_figure(fig1_clean, "paper1_rq_figure1_workflow", width = 11, height = 3.35)
fig1_clean_files <- save_figure(fig1_clean, "paper1_rq_figure1_workflow_clean", width = 11, height = 3.35)
fig1_subtitle_files <- save_figure(fig1_subtitles, "paper1_rq_figure1_workflow_subtitles", width = 11, height = 3.35)

# Figure 2 --------------------------------------------------------------------
error_raw <- read_csv(file.path(root, "analysis", "results", "error_taxonomy.csv"), show_col_types = FALSE)
error_layers <- error_raw %>%
  mutate(
    count = suppressWarnings(as.numeric(frequency)),
    layer = case_when(
      failure_type %in% c("OCR_damage", "short_context", "missing_adjacent_sentence", "extraction_failure") ~ "Extraction layer",
      failure_type %in% c("bibliography_false_positive", "modeling_false_positive", "modeling_false_negative") ~ "Classification layer",
      failure_type %in% c("historical_as_foundational", "foundational_as_historical", "mixed_function_citation", "topic_ambiguity", "stance_ambiguity") ~ "Ambiguity layer",
      TRUE ~ "Other"
    ),
    failure_label = recode(
      failure_type,
      OCR_damage = "OCR damage",
      short_context = "Short context",
      missing_adjacent_sentence = "Missing adjacent sentence",
      extraction_failure = "Extraction failure",
      bibliography_false_positive = "Bibliography false positive",
      modeling_false_positive = "Modeling false positive",
      modeling_false_negative = "Modeling false negative",
      historical_as_foundational = "Historical as foundational",
      foundational_as_historical = "Foundational as historical",
      mixed_function_citation = "Mixed-function citation",
      .default = str_replace_all(failure_type, "_", " ")
    )
  )
error_known <- error_layers %>%
  filter(layer != "Other", !is.na(count)) %>%
  mutate(
    layer = factor(layer, levels = c("Extraction layer", "Classification layer", "Ambiguity layer")),
    failure_label = reorder(failure_label, count)
  )
unknown_errors <- error_layers %>%
  filter(layer != "Other", is.na(count)) %>%
  pull(failure_label)

write_csv(error_layers, file.path(table_dir, "paper1_rq_figure2_error_taxonomy_source.csv"))

fig2 <- ggplot(error_known, aes(count, failure_label, fill = layer)) +
  geom_col(width = 0.68) +
  geom_text(aes(label = count), hjust = -0.18, size = 3.2, color = "#222222") +
  scale_fill_manual(values = palette_layers) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.12))) +
  labs(
    title = "Extraction Versus Classification Failure Modes",
    subtitle = "Observed validation failures grouped by methodological layer; unknown frequencies are excluded.",
    x = "Observed count in validation records",
    y = NULL,
    caption = paste0(
      "Counts are shown only where available. Unknown frequencies not plotted: ",
      paste(unknown_errors, collapse = ", "), "."
    )
  ) +
  theme_paper1_rq()
fig2_files <- save_figure(fig2, "paper1_rq_figure2_failure_modes", width = 8.6, height = 5.2)

# Figure 3 --------------------------------------------------------------------
validation_raw <- read_csv(file.path(root, "analysis", "tables", "final_validation_summary.csv"), show_col_types = FALSE)
validation_metrics <- tibble(
  validation_task = c(
    "Extraction recovery helpfulness",
    "Bibliography audit precision",
    "Router-safe Batch A agreement",
    "Modeling agreement",
    "Historical/foundational agreement"
  ),
  numerator = c(10, 16, 18, 8, 15),
  denominator = c(11, 20, 24, 11, 28),
  caveat = c(
    "Human-review benefit, not classifier agreement",
    "Audit precision; small sample",
    "Spot-check agreement",
    "Requires explicit model-process evidence",
    "Boundary requires human adjudication"
  )
) %>%
  mutate(
    pct = numerator / denominator,
    metric_label = paste0(numerator, "/", denominator, " (", sprintf("%.1f", 100 * pct), "%)"),
    validation_task = factor(validation_task, levels = rev(validation_task))
  )
write_csv(validation_metrics, file.path(table_dir, "paper1_rq_figure3_validation_dashboard_source.csv"))

fig3 <- ggplot(validation_metrics, aes(pct, validation_task)) +
  geom_segment(aes(x = 0, xend = pct, yend = validation_task), linewidth = 1.2, color = "#D9D9D9") +
  geom_point(size = 4.2, color = "#4C78A8") +
  geom_text(aes(label = metric_label), hjust = -0.08, size = 3.2, color = "#222222") +
  geom_text(aes(x = 0.02, label = caveat), hjust = 0, nudge_y = -0.25, size = 2.55, color = "#666666") +
  annotate(
    "label",
    x = 0.48,
    y = 5.55,
    label = "Task-specific validation metrics -- not a full-corpus accuracy estimate.",
    fill = "#F6F6F6",
    color = "#333333",
    linewidth = 0.25,
    size = 3.1
  ) +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1), limits = c(0, 1.05), expand = c(0, 0)) +
  labs(
    title = "Task-Specific Validation Dashboard",
    subtitle = "Metrics vary because validation subsets measure different tasks and risks.",
    x = "Observed validation metric",
    y = NULL,
    caption = "Metrics are not pooled; they are not full-corpus accuracy or recall estimates."
  ) +
  theme_paper1_rq()
fig3_files <- save_figure(fig3, "paper1_rq_figure3_validation_dashboard", width = 9.2, height = 5.4)

# Figure 4 --------------------------------------------------------------------
boundary_source <- tibble(
  row_label = c(
    "Bibliography detection",
    "Router-safe contexts",
    "Modeling references",
    "Historical framing",
    "Foundational citations",
    "Historical/foundational boundary",
    "Topic/discourse labels",
    "Stance labels"
  ),
  validation_evidence = c(
    "Bibliography audit\n16/20 precision",
    "Router-safe Batch A\n18/24 agreement",
    "Modeling validation\n8/11 agreement",
    "Boundary validation\npart of 15/28",
    "Boundary validation\npart of 15/28",
    "28 adjudicated\n53.6% agreement",
    "Readiness notes\nnot directly validated",
    "Readiness notes\nnot directly validated"
  ),
  major_failure_mode = c(
    "False positives to\nbody-text uses",
    "False bibliography-only\nis dominant error",
    "Metadata / phrase-level /\noutcome-only false positives",
    "Confused with\nfoundational claims",
    "Resource language and\nreception overlap",
    "Boundary ambiguity;\nhuman judgment needed",
    "Proxy-like labels;\nexploratory",
    "Low variation;\nexplicit evidence needed"
  ),
  automation_status = c(
    "automated_with_audit",
    "automated_with_audit",
    "hybrid_review_required",
    "hybrid_review_required",
    "hybrid_review_required",
    "human_required",
    "exploratory_only",
    "exploratory_only"
  )
) %>%
  mutate(
    status_label = recode(
      automation_status,
      automated_with_audit = "Automated\nwith audit",
      hybrid_review_required = "Hybrid review\nrequired",
      human_required = "Human\nrequired",
      exploratory_only = "Exploratory\nonly"
    ),
    row_label = factor(row_label, levels = rev(row_label))
  )
write_csv(boundary_source, file.path(table_dir, "paper1_rq_figure4_automation_boundary_source.csv"))

boundary_cells <- boundary_source %>%
  transmute(
    row_label,
    `Validation evidence` = validation_evidence,
    `Major failure mode` = major_failure_mode,
    `Automation status` = status_label,
    automation_status
  ) %>%
  pivot_longer(
    cols = c(`Validation evidence`, `Major failure mode`, `Automation status`),
    names_to = "column",
    values_to = "cell_text"
  ) %>%
  mutate(
    column = factor(column, levels = c("Validation evidence", "Major failure mode", "Automation status")),
    fill_status = if_else(column == "Automation status", automation_status, "blank")
  )

status_colors <- c(
  automated_with_audit = palette_status[["automated_with_audit"]],
  hybrid_review_required = palette_status[["hybrid_review_required"]],
  human_required = palette_status[["human_required"]],
  exploratory_only = palette_status[["exploratory_only"]],
  blank = "#FFFFFF"
)

fig4 <- ggplot(boundary_cells, aes(column, row_label)) +
  geom_tile(aes(fill = fill_status), color = "#D8D8D8", linewidth = 0.35) +
  geom_text(aes(label = cell_text), size = 2.65, lineheight = 0.92, color = "#222222") +
  scale_fill_manual(values = status_colors, guide = "none") +
  labs(
    title = "Automation Boundary Matrix",
    subtitle = "Task-level automation status derived from validation evidence and observed failure modes.",
    x = NULL,
    y = NULL,
    caption = "Statuses are evidence-bounded for this frozen workflow and do not claim automation replaces human coding."
  ) +
  theme_minimal(base_size = 10, base_family = "Helvetica") +
  theme(
    panel.grid = element_blank(),
    axis.text.x = element_text(face = "bold", color = "#222222", size = 10),
    axis.text.y = element_text(color = "#222222", size = 9.5),
    plot.title = element_text(face = "bold", size = 14, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 10.5, color = "#4D4D4D", margin = margin(b = 8)),
    plot.caption = element_text(size = 8.5, color = "#5A5A5A", hjust = 0, margin = margin(t = 8)),
    plot.title.position = "plot",
    plot.caption.position = "plot"
  )
fig4_files <- save_figure(fig4, "paper1_rq_figure4_automation_boundary_matrix", width = 10.2, height = 6.2)

# Figure 5 --------------------------------------------------------------------
corpus <- read_csv(file.path(root, "analysis", "data", "final", "meadows_context_classification.csv"), show_col_types = FALSE)

collapse_uncertainty <- function(x) {
  case_when(
    x == "traditional_only" ~ "Traditional only",
    x == "none" ~ "No flag",
    str_detect(x, "bibliography_precision_caveat") ~ "Bibliography precision caveat",
    str_detect(x, "ocr_noise|snippet_too_short|missing_surrounding_context|generic_limits_phrase") ~ "Extraction/context flag",
    str_detect(x, "bibliography_only") ~ "Bibliography-only flag",
    TRUE ~ "Other flag"
  )
}

deployment_source <- bind_rows(
  corpus %>%
    count(dimension = "Evidence level", category = evidence_level, name = "n") %>%
    mutate(category = str_remove(category, ":.*$")),
  corpus %>%
    count(dimension = "Review status", category = human_review_status, name = "n") %>%
    mutate(category = recode(
      category,
      human_reviewed = "Human reviewed",
      hybrid_accepted_not_human_reviewed = "Hybrid accepted",
      not_human_reviewed_traditional_context = "Traditional only",
      router_safe_not_human_reviewed = "Router-safe",
      unresolved_or_rejected = "Unresolved/rejected"
    )),
  corpus %>%
    mutate(category = if_else(needs_human_review, "Needs human review", "No review flag")) %>%
    count(dimension = "Review flag", category, name = "n"),
  corpus %>%
    mutate(category = collapse_uncertainty(uncertainty_flags)) %>%
    count(dimension = "Uncertainty flag", category, name = "n")
) %>%
  group_by(dimension) %>%
  mutate(
    pct = n / sum(n),
    label = if_else(pct >= 0.06, paste0(category, "\n", n), "")
  ) %>%
  ungroup() %>%
  mutate(dimension = factor(dimension, levels = rev(c("Evidence level", "Review status", "Review flag", "Uncertainty flag"))))

write_csv(deployment_source, file.path(table_dir, "paper1_rq_figure5_deployment_source.csv"))

deployment_palette <- c(
  "Level 1" = "#BDBDBD",
  "Level 2" = "#5A9A78",
  "Level 3" = "#4C78A8",
  "Level 4" = "#ECA64C",
  "Level 5" = "#8C8C8C",
  "Human reviewed" = "#5A9A78",
  "Hybrid accepted" = "#ECA64C",
  "Traditional only" = "#BDBDBD",
  "Router-safe" = "#4C78A8",
  "Unresolved/rejected" = "#8C8C8C",
  "Needs human review" = "#C84B4B",
  "No review flag" = "#4C78A8",
  "No flag" = "#5A9A78",
  "Bibliography precision caveat" = "#ECA64C",
  "Extraction/context flag" = "#C84B4B",
  "Bibliography-only flag" = "#9BBAD8",
  "Other flag" = "#8C8C8C"
)

fig5 <- ggplot(deployment_source, aes(n, dimension, fill = category)) +
  geom_col(width = 0.55, position = "stack", color = "white", linewidth = 0.25) +
  geom_text(
    aes(label = label),
    position = position_stack(vjust = 0.5),
    size = 2.45,
    color = "#222222",
    lineheight = 0.88
  ) +
  scale_fill_manual(values = deployment_palette, breaks = names(deployment_palette), drop = TRUE) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.02))) +
  labs(
    title = "Evidence-Preserving Corpus Deployment",
    subtitle = "Corpus-wide outputs retain evidence levels, review status, uncertainty flags, and review needs.",
    x = "Contexts",
    y = NULL,
    caption = "Preservation of flags does not validate every corpus-wide label or estimate corpus-wide recall."
  ) +
  theme_paper1_rq(base_size = 10) +
  theme(
    legend.position = "right",
    legend.text = element_text(size = 8),
    axis.text.y = element_text(face = "bold")
  )
fig5_files <- save_figure(fig5, "paper1_rq_figure5_evidence_preserving_deployment", width = 10.8, height = 5.4)

# Figure 6 --------------------------------------------------------------------
review_policy_counts <- corpus %>%
  mutate(
    substantive_review = needs_human_review |
      human_review_status %in% c("human_reviewed", "unresolved_or_rejected"),
    audit_review = !substantive_review &
      (
        citation_function == "bibliographic_only" |
          human_review_status %in% c(
            "router_safe_not_human_reviewed",
            "hybrid_accepted_not_human_reviewed"
          )
      )
  ) %>%
  summarise(
    manual_contexts = n(),
    hybrid_substantive_contexts = sum(substantive_review),
    hybrid_audit_contexts = sum(audit_review),
    hybrid_no_review_required_contexts = manual_contexts -
      hybrid_substantive_contexts - hybrid_audit_contexts,
    .groups = "drop"
  )

review_burden <- tibble(
  assumption_set = c("Fast", "Typical", "Conservative"),
  substantive_review_seconds = c(60, 90, 120),
  audit_review_seconds = c(20, 30, 45)
) %>%
  bind_cols(review_policy_counts[rep(1, nrow(.)), ]) %>%
  mutate(
    estimated_manual_hours = manual_contexts * substantive_review_seconds / 3600,
    estimated_hybrid_hours =
      (
        hybrid_substantive_contexts * substantive_review_seconds +
          hybrid_audit_contexts * audit_review_seconds
      ) / 3600,
    estimated_reduction_hours = estimated_manual_hours - estimated_hybrid_hours,
    estimated_reduction_percent = 100 * estimated_reduction_hours / estimated_manual_hours,
    assumption_label = paste0(
      assumption_set,
      "\n",
      substantive_review_seconds,
      "s substantive / ",
      audit_review_seconds,
      "s audit"
    )
  )

write_csv(review_burden, file.path(table_dir, "review_burden_assumptions.csv"))
write_csv(review_burden, file.path(table_dir, "paper1_rq_figure6_labor_source.csv"))

labor_plot <- review_burden %>%
  select(
    assumption_set,
    assumption_label,
    estimated_manual_hours,
    estimated_hybrid_hours,
    estimated_reduction_percent
  ) %>%
  pivot_longer(
    cols = c(estimated_manual_hours, estimated_hybrid_hours),
    names_to = "workflow",
    values_to = "estimated_hours"
  ) %>%
  mutate(
    workflow_label = recode(
      workflow,
      estimated_manual_hours = "Full manual review",
      estimated_hybrid_hours = "Frozen hybrid workflow"
    ),
    workflow_label = factor(
      workflow_label,
      levels = c("Full manual review", "Frozen hybrid workflow")
    ),
    assumption_label = factor(
      assumption_label,
      levels = review_burden$assumption_label
    )
  )

reduction_labels <- labor_plot %>%
  filter(workflow == "estimated_hybrid_hours") %>%
  mutate(
    label = paste0(
      sprintf("%.1f", estimated_reduction_percent),
      "% lower"
    )
  )

fig6 <- ggplot(labor_plot, aes(assumption_label, estimated_hours, fill = workflow_label)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.62) +
  geom_text(
    aes(label = sprintf("%.1f h", estimated_hours)),
    position = position_dodge(width = 0.72),
    vjust = -0.3,
    size = 3
  ) +
  geom_label(
    data = reduction_labels,
    aes(label = label, y = estimated_hours + max(labor_plot$estimated_hours) * 0.08),
    position = position_dodge(width = 0.72),
    fill = "#F6F6F6",
    color = "#333333",
    linewidth = 0.22,
    label.r = unit(0.08, "lines"),
    size = 2.8,
    show.legend = FALSE
  ) +
  annotate(
    "label",
    x = 2,
    y = max(labor_plot$estimated_hours) * 1.22,
    label = paste0(
      "Policy counts: ",
      review_policy_counts$hybrid_substantive_contexts,
      " substantive review; ",
      review_policy_counts$hybrid_audit_contexts,
      " audit review; ",
      review_policy_counts$hybrid_no_review_required_contexts,
      " no-review-required."
    ),
    fill = "#F6F6F6",
    color = "#333333",
    linewidth = 0.25,
    size = 3
  ) +
  scale_fill_manual(
    values = c("Full manual review" = "#9A9A9A", "Frozen hybrid workflow" = "#4C78A8"),
    breaks = c("Full manual review", "Frozen hybrid workflow")
  ) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.26))) +
  labs(
    title = "Estimated Human Review Burden Under Automation-Boundary Policies",
    subtitle = "Hybrid estimates limit substantive review to contexts flagged by the frozen automation-boundary policy.",
    x = "Review-policy assumption",
    y = "Estimated human review hours",
    caption = "Workflow-planning estimates derived from review-policy assumptions. They are not observed timing measurements or generalizable annotation rates."
  ) +
  theme_paper1_rq()
fig6_files <- save_figure(fig6, "paper1_rq_figure6_labor_reduction", width = 9.5, height = 5.4)

# Inventory and interpretation memo ------------------------------------------
inventory <- bind_rows(
  tibble(
    figure_number = 1,
    figure_title = "Frozen Contextual Bibliometrics Workflow",
    associated_RQ = "Overall; RQ1; RQ2; RQ3; RQ4",
    source_data = "analysis/tables/paper1_rq/paper1_rq_figure1_workflow_source.csv",
    supported_claim = "The paper evaluates a staged workflow, not a single classifier.",
    claim_not_supported = "Does not show empirical performance or Meadows impact.",
    status = "generated",
    notes = "Selected clean version; semantic colors map RQ1 green, RQ2 blue, RQ3 orange, and RQ4 gray. Subtitle alternative also exported."
  ) %>% bind_cols(fig1_files),
  tibble(
    figure_number = 2,
    figure_title = "Extraction Versus Classification Failure Modes",
    associated_RQ = "RQ1",
    source_data = "analysis/results/error_taxonomy.csv",
    supported_claim = "Extraction quality and classification quality are distinct methodological layers.",
    claim_not_supported = "Does not estimate all possible error frequencies in the corpus.",
    status = "generated",
    notes = "Unknown frequencies excluded from plotted counts."
  ) %>% bind_cols(fig2_files),
  tibble(
    figure_number = 3,
    figure_title = "Task-Specific Validation Dashboard",
    associated_RQ = "RQ2; RQ3",
    source_data = "analysis/tables/final_validation_summary.csv",
    supported_claim = "Validation metrics vary by task.",
    claim_not_supported = "Not a global workflow accuracy estimate and not corpus-wide recall.",
    status = "generated",
    notes = "Required annotation included."
  ) %>% bind_cols(fig3_files),
  tibble(
    figure_number = 4,
    figure_title = "Automation Boundary Matrix",
    associated_RQ = "RQ3",
    source_data = "analysis/tables/automation_boundary_framework.csv; analysis/tables/final_validation_summary.csv",
    supported_claim = "Contextual bibliometric automation should be task-specific and evidence-bounded.",
    claim_not_supported = "Does not claim automation replaces human coding or generalizes without local validation.",
    status = "generated",
    notes = "Signature matrix; row text kept concise."
  ) %>% bind_cols(fig4_files),
  tibble(
    figure_number = 5,
    figure_title = "Evidence-Preserving Corpus Deployment",
    associated_RQ = "RQ4",
    source_data = "analysis/data/final/meadows_context_classification.csv; corpus classification summary tables",
    supported_claim = "Corpus-wide deployment preserves uncertainty at scale.",
    claim_not_supported = "Does not validate every corpus-wide label.",
    status = "generated",
    notes = "Uses stacked bars across evidence, review, review-flag, and uncertainty dimensions."
  ) %>% bind_cols(fig5_files),
  tibble(
    figure_number = 6,
    figure_title = "Estimated Human Review Burden Under Automation-Boundary Policies",
    associated_RQ = "Implication; RQ3",
    source_data = "analysis/tables/paper1_rq/review_burden_assumptions.csv",
    supported_claim = "Automation boundaries may reduce human review burden by limiting substantive review to contexts where validation evidence indicates human judgment remains necessary.",
    claim_not_supported = "Not measured labor savings, observed coder productivity, or generalizable annotation rates.",
    status = "generated",
    notes = "Review-policy burden estimate; audit burden is included for automated/audit-eligible contexts."
  ) %>% bind_cols(fig6_files)
  ,
  tibble(
    figure_number = "Framework",
    figure_title = "Conceptual Architecture Of Evidence-Bounded Contextual Bibliometrics",
    file_svg = file.path("analysis", "figures", "paper1_rq", "paper1_framework_architecture.svg"),
    file_png = file.path("analysis", "figures", "paper1_rq", "paper1_framework_architecture.png"),
    associated_RQ = "Overall conceptual framing",
    source_data = "manuscript/paper1_framework_hierarchy_revision.md",
    supported_claim = "Evidence-bounded contextual bibliometrics is the framework; workflow reliability is the mechanism; automation boundaries and evidence preservation are design features; claims governance is the outcome.",
    claim_not_supported = "Not a workflow diagram, not empirical performance, and not a Meadows substantive finding.",
    status = "generated",
    notes = "Conceptual positioning figure; separate from Figure 1."
  )
) %>%
  select(figure_number, figure_title, file_svg, file_png, associated_RQ, source_data, supported_claim, claim_not_supported, status, notes)

write_csv(inventory, file.path(fig_dir, "paper1_rq_figure_inventory.csv"))

memo_lines <- c(
  "# Paper 1 Figure Interpretation Memo",
  "",
  "This memo controls how the RQ-driven methods figures should be read. It follows the Paper 1 claims-control framework: no figure reports global accuracy, corpus-wide recall, or Meadows impact.",
  "",
  "## Conceptual Architecture: Evidence-Bounded Contextual Bibliometrics",
  "",
  "- What the figure shows: the conceptual hierarchy of the paper's primary methodological contribution. Evidence-Bounded Contextual Bibliometrics is the framework; Workflow Reliability is the mechanism; Automation Boundaries and Evidence Preservation are design features / operational components; Claims Governance is the outcome.",
  "- How to read it: read top to bottom as a conceptual architecture, not as a workflow diagram. The conceptual architecture figure presents the hierarchy of the framework, whereas Figure 1 presents the staged workflow through which the framework is implemented.",
  "- Manuscript location: Introduction framework paragraph; Discussion 4.1; Discussion 4.5; Conclusion.",
  "- Claim supported: Paper 1 contributes a framework in which task-specific validation evidence determines automation eligibility, review requirements, uncertainty preservation, and permissible claims.",
  "- Claim not supported: empirical performance, workflow chronology, corpus-wide accuracy, corpus-wide recall, or Meadows impact.",
  "- Reviewer risk: readers may conflate the framework with the workflow; keep the distinction explicit in caption and prose.",
  "- Suggested caption: Conceptual architecture of evidence-bounded contextual bibliometrics. Evidence-bounded contextual bibliometrics is the framework; workflow reliability is the mechanism through which it operates; automation boundaries and evidence preservation are design features that implement the framework in practice; claims governance, the explicit alignment of evidentiary status and permissible inference, is the outcome. The figure is conceptual and does not report empirical performance.",
  "- TODOs: none.",
  "",
  "## Figure 1: Frozen Contextual Bibliometrics Workflow",
  "",
  "- What the figure shows: the staged frozen workflow from corpus construction to evidence-preserving deployment, with RQ1-RQ4 located in the pipeline and stage annotations for extraction/recovery, function validation, boundary derivation, and evidence preservation.",
  "- How to read it: read left to right as a workflow architecture and visual legend for the figure set. RQ1/extraction-recovery is green, RQ2/function validation is blue, RQ3/automation-boundary derivation is orange, and RQ4/evidence-preserving deployment is gray.",
  "- Manuscript location: Introduction contribution paragraph; Methods workflow section.",
  "- Claim supported: the paper evaluates a staged workflow, not a single classifier.",
  "- Claim not supported: empirical performance or Meadows impact.",
  "- Reviewer risk: a reviewer may expect validation metrics here; direct them to Figure 3.",
  "- Suggested caption: Figure 1. Frozen contextual bibliometrics workflow. The workflow is organized into extraction/recovery (RQ1), function validation (RQ2), automation-boundary derivation (RQ3), and evidence-preserving deployment (RQ4). The figure shows the staged evidentiary workflow evaluated in the paper, not a single citation-classification model.",
  "- TODOs: none.",
  "",
  "## Figure 2: Extraction Versus Classification Failure Modes",
  "",
  "- What the figure shows: observed validation failure modes grouped into extraction, classification, and ambiguity layers.",
  "- How to read it: compare layers and known counts only; unknown frequencies are intentionally not plotted.",
  "- Manuscript location: Results 3.2 error taxonomy and failure modes; Discussion extraction failure.",
  "- Claim supported: extraction quality and classification quality are distinct methodological layers.",
  "- Claim not supported: total corpus error prevalence or all possible failure frequencies.",
  "- Reviewer risk: readers may treat counts as exhaustive corpus rates; the caption states they are validation-record counts only.",
  "- Suggested caption: Observed failure modes grouped by methodological layer. Counts are shown only where available in validation records; unknown frequencies are not imputed.",
  "- TODOs: none.",
  "",
  "## Figure 3: Task-Specific Validation Dashboard",
  "",
  "- What the figure shows: five task-specific validation metrics: historical/foundational agreement, modeling agreement, router-safe Batch A agreement, bibliography precision, and extraction recovery helpfulness.",
  "- How to read it: each metric belongs to a separate validation task; do not average or pool them.",
  "- Manuscript location: Results 3.1 validation performance; Results 3.3 automation boundary.",
  "- Claim supported: validation metrics vary by task.",
  "- Claim not supported: global workflow accuracy or corpus-wide recall.",
  "- Reviewer risk: a reviewer may ask for one accuracy estimate; this figure supports the argument against pooling.",
  "- Suggested caption: Task-specific validation metrics used to derive automation boundaries. Metrics are not pooled because validation subsets measure different tasks and risks.",
  "- TODOs: none.",
  "",
  "## Figure 4: Automation Boundary Matrix",
  "",
  "- What the figure shows: task-level validation evidence, major failure mode, and automation status.",
  "- How to read it: color indicates automation status; text explains why each status is evidence-bounded.",
  "- Manuscript location: Results 3.3 automation boundary; Discussion workflow reliability.",
  "- Claim supported: contextual bibliometric automation should be task-specific and evidence-bounded.",
  "- Claim not supported: automation replaces human coding or statuses generalize without local validation.",
  "- Reviewer risk: this is the signature figure, so any dense text should be checked at final journal width.",
  "- Suggested caption: Automation boundary matrix derived from task-specific validation evidence and observed failure modes.",
  "- TODOs: final layout check after target journal column width is known.",
  "",
  "## Figure 5: Evidence-Preserving Corpus Deployment",
  "",
  "- What the figure shows: corpus-wide preservation of evidence levels, review status, needs-review flags, and uncertainty flags.",
  "- How to read it: the bars show retained metadata dimensions, not a hierarchy of validated labels.",
  "- Manuscript location: Results 3.4 corpus-wide deployment; Discussion evidence preservation.",
  "- Claim supported: contextual bibliometric workflows can preserve uncertainty at scale.",
  "- Claim not supported: validation of every corpus-wide label.",
  "- Reviewer risk: readers may focus on Level 1 volume; emphasize that Level 1 is traditional bibliometric evidence, not contextual validation.",
  "- Suggested caption: Corpus-wide deployment preserves evidence levels, uncertainty, and review status rather than forcing all records into final substantive labels.",
  "- TODOs: none.",
  "",
  "## Figure 6: Estimated Human Review Burden Under Automation-Boundary Policies",
  "",
  "- What the figure shows: estimated human review hours for full manual review and the frozen hybrid workflow under fast, typical, and conservative review-policy assumptions.",
  "- How to read it: compare review burden under policies, not coder speed. Full manual review assigns substantive review to every context; the frozen hybrid workflow assigns substantive review only where the automation-boundary policy indicates human judgment remains necessary, with audit review added for automated/audit-eligible contexts.",
  "- Manuscript location: Results 3.5 labor reduction and reproducibility; Limitations.",
  "- Claim supported: automation boundaries may reduce human review burden by limiting substantive review to contexts where validation evidence indicates human judgment remains necessary.",
  "- Claim not supported: measured labor savings, observed coder productivity, or generalizable annotation rates.",
  "- Reviewer risk: readers may treat estimates as observed timings or as evidence of faster human coding; keep the review-policy annotation and caption visible.",
  "- Suggested caption: Estimated human review burden under automation-boundary policies. The full manual workflow assigns substantive review to all contexts; the frozen hybrid workflow limits substantive review to contexts requiring human judgment and applies audit review to automated/audit-eligible contexts. Estimates are workflow-planning estimates derived from policy assumptions, not observed timing measurements.",
  "- TODOs: none.",
  "",
  "## Quality Check",
  "",
  "- Every plotted value comes from source data or documented validation metrics.",
  "- Unknown values are not plotted as zero.",
  "- No figure implies global accuracy.",
  "- No figure implies corpus-wide recall.",
  "- No figure makes Meadows impact claims.",
  "- Topic/discourse and stance labels are marked exploratory in Figure 4.",
  "- Figures use a consistent restrained palette and typography.",
  "- SVG and PNG outputs were generated for every figure."
)
writeLines(memo_lines, file.path(manuscript_dir, "paper1_figure_interpretation_memo.md"))

message("Generated Paper 1 RQ figures, figure inventory, source tables, and interpretation memo.")
