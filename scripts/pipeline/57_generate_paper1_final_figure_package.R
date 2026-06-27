#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(dplyr)
  library(ggplot2)
  library(grid)
  library(readr)
  library(stringr)
  library(tidyr)
  library(svglite)
})

root <- normalizePath(getwd(), mustWork = TRUE)
fig_dir <- file.path(root, "analysis", "figures", "paper1_rq")
table_dir <- file.path(root, "analysis", "tables", "paper1_rq")
dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(table_dir, recursive = TRUE, showWarnings = FALSE)

colors <- list(
  green = "#5A9A78",
  blue = "#4C78A8",
  orange = "#ECA64C",
  red = "#C84B4B",
  gray = "#8C8C8C",
  light_gray = "#F3F5F7",
  dark_blue = "#163A5F",
  text = "#1F2933",
  muted = "#53616F",
  border = "#D8DEE6"
)

theme_final <- function(base_size = 12) {
  theme_minimal(base_size = base_size, base_family = "Helvetica") +
    theme(
      plot.title = element_text(face = "bold", size = base_size + 4, margin = margin(b = 4)),
      plot.subtitle = element_text(size = base_size, color = colors$muted, margin = margin(b = 10)),
      plot.caption = element_text(size = base_size - 3, color = colors$muted, hjust = 0, margin = margin(t = 8)),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      panel.grid.minor = element_blank(),
      panel.grid.major.y = element_blank(),
      axis.title = element_text(color = colors$text),
      axis.text = element_text(color = colors$text),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = base_size - 2),
      strip.text = element_text(face = "bold", color = colors$text)
    )
}

save_plot <- function(plot, stem, width = 9, height = 5.5) {
  png_path <- file.path(fig_dir, paste0(stem, ".png"))
  svg_path <- file.path(fig_dir, paste0(stem, ".svg"))
  ggsave(png_path, plot, width = width, height = height, dpi = 300, bg = "white")
  ggsave(svg_path, plot, width = width, height = height, device = svglite::svglite, bg = "white")
}

wrap_label <- function(x, width = 24) str_wrap(x, width = width)

# Figure 0 --------------------------------------------------------------------
draw_box <- function(x, y, w, h, fill, border, title, subtitle,
                     title_size = 16, subtitle_size = 9.3, title_color = colors$text) {
  grid.roundrect(
    x = x, y = y, width = w, height = h,
    r = unit(0.028, "npc"),
    gp = gpar(fill = fill, col = border, lwd = 1.35)
  )
  grid.text(
    title,
    x = x, y = y + h * 0.13,
    gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = title_size, col = title_color)
  )
  grid.text(
    subtitle,
    x = x, y = y - h * 0.18,
    gp = gpar(fontfamily = "Helvetica", fontsize = subtitle_size, col = colors$muted)
  )
}

draw_architecture_v3 <- function() {
  grid.newpage()
  grid.rect(gp = gpar(fill = "white", col = NA))
  grid.text(
    "Conceptual Architecture Of Evidence-Bounded Contextual Bibliometrics",
    x = 0.5, y = 0.955,
    gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = 17.5, col = colors$text)
  )
  grid.text(
    "A framework for deciding what contextual bibliometric outputs can responsibly support",
    x = 0.5, y = 0.918,
    gp = gpar(fontfamily = "Helvetica", fontsize = 10, col = colors$muted)
  )

  label_x <- 0.20
  box_x <- 0.58
  grid.text("Framework", x = label_x, y = 0.79, just = "right",
            gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = 10, col = colors$blue))
  draw_box(
    x = box_x, y = 0.79, w = 0.68, h = 0.15,
    fill = "#EEF5FC", border = colors$blue,
    title = "Evidence-Bounded Contextual Bibliometrics",
    subtitle = "Framework: validation evidence determines what outputs can support",
    title_size = 16.2
  )

  grid.lines(unit(c(box_x, box_x), "npc"), unit(c(0.713, 0.666), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.text("Mechanism", x = label_x, y = 0.59, just = "right",
            gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = 10, col = colors$green))
  draw_box(
    x = box_x, y = 0.59, w = 0.58, h = 0.13,
    fill = "#EEF8F2", border = colors$green,
    title = "Workflow Reliability",
    subtitle = "Mechanism: evidentiary status remains traceable across workflow stages",
    title_size = 15
  )

  grid.lines(unit(c(box_x, box_x), "npc"), unit(c(0.523, 0.486), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(0.41, 0.75), "npc"), unit(c(0.486, 0.486), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(0.41, 0.41), "npc"), unit(c(0.486, 0.455), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(0.75, 0.75), "npc"), unit(c(0.486, 0.455), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))

  grid.text("Design features", x = label_x, y = 0.38, just = "right",
            gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = 10, col = colors$orange))
  draw_box(
    x = 0.41, y = 0.38, w = 0.31, h = 0.15,
    fill = "#FFF5E8", border = colors$orange,
    title = "Automation Boundaries",
    subtitle = "Design feature: which tasks may be\nautomated, audited, or adjudicated",
    title_size = 12.8,
    subtitle_size = 8.6
  )
  draw_box(
    x = 0.75, y = 0.38, w = 0.31, h = 0.15,
    fill = colors$light_gray, border = colors$gray,
    title = "Evidence Preservation",
    subtitle = "Design feature: how evidence levels,\nreview status, and uncertainty remain visible",
    title_size = 12.8,
    subtitle_size = 8.6
  )

  grid.lines(unit(c(0.41, 0.41), "npc"), unit(c(0.303, 0.255), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(0.75, 0.75), "npc"), unit(c(0.303, 0.255), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(0.41, 0.75), "npc"), unit(c(0.255, 0.255), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))
  grid.lines(unit(c(box_x, box_x), "npc"), unit(c(0.255, 0.223), "npc"), gp = gpar(col = "#A2ABB5", lwd = 1.05))

  grid.text("Outcome", x = label_x, y = 0.155, just = "right",
            gp = gpar(fontfamily = "Helvetica", fontface = "bold", fontsize = 10, col = colors$dark_blue))
  draw_box(
    x = box_x, y = 0.155, w = 0.58, h = 0.13,
    fill = "#EEF3F8", border = colors$dark_blue,
    title = "Claims Governance",
    subtitle = "Outcome: permissible claims align with evidentiary status",
    title_size = 15,
    title_color = colors$dark_blue
  )

  grid.text(
    "Conceptual hierarchy, not a processing pipeline",
    x = 0.58, y = 0.045,
    gp = gpar(fontfamily = "Helvetica", fontsize = 9, col = colors$muted)
  )
}

svglite::svglite(file.path(fig_dir, "paper1_framework_architecture_v3.svg"), width = 9.5, height = 6.2)
draw_architecture_v3()
dev.off()
png(file.path(fig_dir, "paper1_framework_architecture_v3.png"), width = 2850, height = 1860, res = 300)
draw_architecture_v3()
dev.off()

# Figure 1 --------------------------------------------------------------------
workflow <- tibble(
  step = c("Corpus", "Extraction", "Recovery", "Routing", "Classification", "Validation", "Automation Boundary", "Evidence-Preserving Deployment"),
  x = seq_len(8),
  y = 1
)
write_csv(workflow, file.path(table_dir, "paper1_final_fig1_workflow_source.csv"))
fig1_regions <- tibble(
  rq_label = c("RQ1", "RQ2", "RQ3", "RQ4"),
  region_label = c("Extraction /\nrecovery", "Function validation", "Boundary\nderivation", "Evidence\npreservation"),
  xmin = c(1.65, 3.65, 6.65, 7.55),
  xmax = c(3.35, 6.35, 7.35, 8.45),
  x = c(2.5, 5, 7, 8),
  color = c(colors$green, colors$blue, colors$orange, colors$gray)
)
fig1 <- ggplot(workflow, aes(x, y)) +
  annotate("rect", xmin = 0.55, xmax = 8.45, ymin = 0.76, ymax = 1.25,
           fill = "#F7F8FA", color = colors$border, linewidth = 0.35) +
  geom_rect(data = fig1_regions, aes(xmin = xmin, xmax = xmax, ymin = 0.78, ymax = 1.23),
            inherit.aes = FALSE, fill = grDevices::adjustcolor(fig1_regions$color, alpha.f = 0.12), color = NA) +
  geom_segment(data = workflow %>% filter(x < max(x)), aes(x = x + 0.36, xend = x + 0.64, y = y, yend = y),
               arrow = arrow(length = unit(0.08, "inches"), type = "closed"), linewidth = 0.36, color = "#8A8A8A") +
  geom_label(aes(label = wrap_label(step, 15)), fill = "white", color = colors$text,
             linewidth = 0.28, label.r = unit(0.10, "lines"), label.padding = unit(0.22, "lines"),
             size = 3.2, lineheight = 0.92) +
  geom_label(data = fig1_regions, aes(x = x, y = 1.46, label = rq_label), inherit.aes = FALSE,
             fill = "white", color = fig1_regions$color, linewidth = 0.28, label.r = unit(0.10, "lines"),
             label.padding = unit(0.18, "lines"), size = 4.2, fontface = "bold") +
  geom_segment(data = fig1_regions, aes(x = xmin + 0.1, xend = xmax - 0.1, y = 0.57, yend = 0.57),
               inherit.aes = FALSE, linewidth = 2.0, color = fig1_regions$color, lineend = "round") +
  geom_text(data = fig1_regions, aes(x = x, y = 0.41, label = region_label), inherit.aes = FALSE,
            size = 3.05, color = colors$muted, lineheight = 0.95) +
  scale_x_continuous(limits = c(0.45, 8.55), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0.25, 1.68), expand = c(0, 0)) +
  labs(
    title = "Frozen Contextual Bibliometrics Workflow",
    subtitle = "Implementation stages operationalize the framework; they do not define the framework itself.",
    caption = "RQ1 extraction/recovery; RQ2 function validation; RQ3 automation boundaries; RQ4 evidence-preserving deployment."
  ) +
  theme_void(base_size = 12, base_family = "Helvetica") +
  theme(
    plot.title = element_text(face = "bold", size = 16, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 12, color = colors$muted, margin = margin(b = 10)),
    plot.caption = element_text(size = 9, color = colors$muted, hjust = 0, margin = margin(t = 8)),
    plot.title.position = "plot",
    plot.caption.position = "plot"
  )
save_plot(fig1, "paper1_fig1_workflow", width = 11.5, height = 3.7)

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
unknown_errors <- error_layers %>% filter(layer != "Other", is.na(count)) %>% pull(failure_label)
error_known <- error_layers %>%
  filter(layer != "Other", !is.na(count)) %>%
  mutate(layer = factor(layer, levels = c("Extraction layer", "Classification layer", "Ambiguity layer")),
         failure_label = reorder(failure_label, count))
fig2 <- ggplot(error_known, aes(count, failure_label, fill = layer)) +
  geom_col(width = 0.68) +
  geom_text(aes(label = count), hjust = -0.18, size = 3.4, color = colors$text) +
  scale_fill_manual(values = c("Extraction layer" = colors$green, "Classification layer" = colors$blue, "Ambiguity layer" = colors$orange)) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.14))) +
  labs(
    title = "Extraction Versus Classification Failure Modes",
    subtitle = "Observed validation failures grouped by methodological layer; unknown frequencies are excluded.",
    x = "Observed count in validation records",
    y = NULL,
    caption = paste0("Counts are shown only where available. Unknown frequencies not plotted: ", paste(unknown_errors, collapse = ", "), ".")
  ) +
  theme_final()
save_plot(fig2, "paper1_fig2_failure_modes", width = 8.8, height = 5.3)

# Figure 3 --------------------------------------------------------------------
## Reads point estimates and Wilson 95% CIs from analysis/results/validation_intervals.csv
## (written by scripts/pipeline/58_validation_intervals.R from the frozen
## analysis/frozen_methodology/v2_0/validation_summary.csv). No numerators or
## denominators are inlined here.
##
## Faceted by metric_type so agreement / precision / helpfulness are not rendered
## as one rankable axis — they measure different quantities (validation
## subsets answer different methodological questions; see Methods §2.6).
validation_intervals_path <- file.path(root, "analysis", "results", "validation_intervals.csv")
if (!file.exists(validation_intervals_path)) {
  stop("Missing ", validation_intervals_path, ". Run scripts/pipeline/58_validation_intervals.R first.")
}
validation_intervals <- read_csv(validation_intervals_path, show_col_types = FALSE)

validation_task_labels <- c(
  "Historical/Foundation" = "Historical/foundational\nagreement",
  "Modeling"              = "Modeling\nagreement",
  "Router-Safe Batch A"   = "Router-safe Batch A\nagreement",
  "Bibliography Audit"    = "Bibliography audit\nprecision",
  "Extraction Recovery"   = "Extraction recovery\nhelpfulness"
)
metric_type_labels <- c(
  agreement   = "Agreement (human ↔ router/LLM)",
  precision   = "Precision (audit sample)",
  helpfulness = "Helpfulness (human-review benefit)"
)
metric_type_colors <- c(
  agreement   = colors$blue,
  precision   = colors$green,
  helpfulness = colors$orange
)

validation_plot_data <- validation_intervals %>%
  mutate(
    validation_task = factor(
      validation_task_labels[validation_area],
      levels = rev(unname(validation_task_labels))
    ),
    metric_type_label = factor(
      metric_type_labels[metric_type],
      levels = unname(metric_type_labels)
    ),
    point_label = sprintf("%d/%d (%.1f%%)", k, n, 100 * p_hat),
    ci_label = sprintf("95%% CI [%.2f, %.2f]", ci_lower, ci_upper)
  )

## Figure 3 source CSV: thin pass-through of validation_intervals.csv with the
## rendered labels appended, so the figure is self-contained but the numbers
## remain owned upstream by analysis/results/validation_intervals.csv.
write_csv(
  validation_intervals %>%
    mutate(
      point_label = sprintf("%d/%d (%.1f%%)", k, n, 100 * p_hat),
      ci_label = sprintf("95%% CI [%.2f, %.2f]", ci_lower, ci_upper)
    ),
  file.path(table_dir, "paper1_final_fig3_validation_dashboard_source.csv")
)

fig3 <- ggplot(validation_plot_data, aes(p_hat, validation_task, color = metric_type)) +
  geom_errorbar(aes(xmin = ci_lower, xmax = ci_upper), orientation = "y", width = 0.22, linewidth = 0.9) +
  geom_point(size = 4) +
  geom_text(aes(x = pmin(ci_upper + 0.04, 1.04), label = point_label),
            hjust = 0, size = 3.1, color = colors$text) +
  geom_text(aes(x = pmin(ci_upper + 0.04, 1.04), label = ci_label),
            hjust = 0, nudge_y = -0.32, size = 2.7, color = colors$muted) +
  facet_grid(metric_type_label ~ ., scales = "free_y", space = "free_y", switch = "y") +
  scale_color_manual(values = metric_type_colors, guide = "none") +
  scale_x_continuous(labels = scales::percent_format(accuracy = 1),
                     limits = c(0, 1.28), expand = c(0, 0),
                     breaks = c(0, 0.25, 0.5, 0.75, 1.0)) +
  labs(
    title = "Task-Specific Validation Metrics With Wilson 95% Confidence Intervals",
    subtitle = "Panels separate the metric type. Agreement, precision, and helpfulness measure different quantities and are not pooled.",
    x = "Validation metric (point estimate; bars are Wilson 95% CIs)",
    y = NULL,
    caption = "Point estimates and Wilson 95% CIs computed from analysis/results/validation_intervals.csv. Metrics are not full-corpus accuracy or recall estimates."
  ) +
  theme_final() +
  theme(
    strip.placement = "outside",
    strip.text.y.left = element_text(angle = 0, face = "bold", hjust = 1),
    panel.spacing.y = unit(0.6, "lines")
  )
save_plot(fig3, "paper1_fig3_validation_dashboard", width = 10.4, height = 6.4)

# Figure 4 --------------------------------------------------------------------
## GUARD: the automation_status values below are §2.7 rule outputs and are
## pending the grounding decision (see analysis/results/decision_rule_validation_memo.md).
## They are intentionally retained as inline literals to avoid creating a second
## source of truth that would collide with the grounding fix. The anti-drift
## checker (scripts/pipeline/60_check_manuscript_numbers.R) excludes status= values
## from its scope.
##
## Numeric content of the validation_evidence strings (16/20, 18/24, 8/11, 15/28
## numerators and denominators; 53.6% derived rate) is wired from
## analysis/frozen_methodology/v2_0/validation_summary.csv via
## analysis/results/validation_intervals.csv — no validation rates are inlined.
validation_intervals_for_fig4 <- validation_intervals %>%
  select(validation_area, k, n, p_hat)
get_kn <- function(area) {
  row <- validation_intervals_for_fig4[validation_intervals_for_fig4$validation_area == area, ]
  if (nrow(row) != 1L) stop("Missing validation_intervals row: ", area, call. = FALSE)
  list(k = as.integer(row$k), n = as.integer(row$n), p_hat = as.numeric(row$p_hat))
}
bib  <- get_kn("Bibliography Audit")
rsb  <- get_kn("Router-Safe Batch A")
mod  <- get_kn("Modeling")
hfb  <- get_kn("Historical/Foundation")

fmt_pct <- function(p) sprintf("%.1f%%", 100 * p)

boundary_source <- tibble(
  task = c("Bibliography detection", "Router-safe contexts", "Modeling references", "Historical framing", "Foundational citations", "Historical/foundational boundary", "Topic/discourse labels", "Stance labels"),
  validation_evidence = c(
    paste0("Bibliography audit\n", bib$k, "/", bib$n, " precision"),
    paste0("Router-safe Batch A\n", rsb$k, "/", rsb$n, " agreement"),
    paste0("Modeling validation\n", mod$k, "/", mod$n, " agreement"),
    paste0("Boundary validation\npart of ", hfb$k, "/", hfb$n),
    paste0("Boundary validation\npart of ", hfb$k, "/", hfb$n),
    paste0(hfb$n, " adjudicated\n", fmt_pct(hfb$p_hat), " agreement"),
    "Readiness notes\nnot directly validated",
    "Readiness notes\nnot directly validated"
  ),
  failure_mode = c("Body-text false positives", "Bibliography-only false positives", "Metadata / outcome-only cues", "Foundational overlap", "Reception / resource-language overlap", "Boundary ambiguity", "Proxy-like labels", "Low variation"),
  ## automation_status: §2.7 rule outputs — owned by the pending grounding decision; do NOT
  ## lift into a separate status CSV until that decision is made.
  automation_status = c("automated_with_audit", "automated_with_audit", "hybrid_review_required", "hybrid_review_required", "hybrid_review_required", "human_required", "exploratory_only", "exploratory_only")
) %>%
  mutate(
    status_label = recode(
      automation_status,
      automated_with_audit = "Automated\nwith audit",
      hybrid_review_required = "Hybrid review\nrequired",
      human_required = "Human\nrequired",
      exploratory_only = "Exploratory\nonly"
    ),
    task = factor(task, levels = rev(task))
  )
write_csv(boundary_source, file.path(table_dir, "paper1_final_fig4_automation_boundaries_source.csv"))
boundary_cells <- boundary_source %>%
  transmute(task, Task = as.character(task), `Validation evidence` = validation_evidence, `Failure mode` = failure_mode, `Automation status` = status_label, automation_status) %>%
  pivot_longer(cols = c(Task, `Validation evidence`, `Failure mode`, `Automation status`), names_to = "column", values_to = "cell_text") %>%
  mutate(
    column = factor(column, levels = c("Task", "Validation evidence", "Failure mode", "Automation status")),
    fill_status = if_else(column == "Automation status", automation_status, "blank")
  )
status_colors <- c(automated_with_audit = "#DCEAF7", hybrid_review_required = "#FFF0DA", human_required = "#F7DCDC", exploratory_only = "#E9E9E9", blank = "#FFFFFF")
status_text_colors <- c(automated_with_audit = colors$blue, hybrid_review_required = "#A65F00", human_required = colors$red, exploratory_only = "#555555", blank = colors$text)
fig4 <- ggplot(boundary_cells, aes(column, task)) +
  geom_tile(aes(fill = fill_status), color = "#D2D6DC", linewidth = 0.35) +
  geom_text(aes(label = cell_text, color = fill_status, fontface = if_else(column %in% c("Task", "Automation status"), "bold", "plain")),
            size = 3.18, lineheight = 0.93) +
  scale_fill_manual(values = status_colors, guide = "none") +
  scale_color_manual(values = status_text_colors, guide = "none") +
  labs(
    title = "Automation Boundary Matrix",
    subtitle = "Task-level automation status derived from validation evidence and observed failure modes.",
    x = NULL,
    y = NULL,
    caption = "Statuses are evidence-bounded for this frozen workflow and do not claim automation replaces human coding."
  ) +
  theme_minimal(base_size = 12, base_family = "Helvetica") +
  theme(
    panel.grid = element_blank(),
    axis.text.x = element_text(face = "bold", color = colors$text, size = 11),
    axis.text.y = element_blank(),
    axis.ticks = element_blank(),
    plot.title = element_text(face = "bold", size = 16, margin = margin(b = 4)),
    plot.subtitle = element_text(size = 12, color = colors$muted, margin = margin(b = 8)),
    plot.caption = element_text(size = 9, color = colors$muted, hjust = 0, margin = margin(t = 8)),
    plot.title.position = "plot",
    plot.caption.position = "plot"
  )
save_plot(fig4, "paper1_fig4_automation_boundaries", width = 11.2, height = 7.0)

# Figure 5 --------------------------------------------------------------------
corpus <- read_csv(file.path(root, "analysis", "data", "final", "meadows_context_classification.csv"), show_col_types = FALSE)
collapse_uncertainty <- function(x) {
  case_when(
    x == "traditional_only" ~ "Traditional only",
    x == "none" ~ "No flag",
    str_detect(x, "bibliography_precision_caveat") ~ "Bibliography caveat",
    str_detect(x, "ocr_noise|snippet_too_short|missing_surrounding_context|generic_limits_phrase") ~ "Extraction/context flag",
    str_detect(x, "bibliography_only") ~ "Bibliography-only flag",
    TRUE ~ "Other flag"
  )
}
deployment_source <- bind_rows(
  corpus %>% count(dimension = "Evidence level", category = str_remove(evidence_level, ":.*$"), name = "n"),
  corpus %>% count(dimension = "Review status", category = recode(human_review_status, human_reviewed = "Human reviewed", hybrid_accepted_not_human_reviewed = "Hybrid accepted", not_human_reviewed_traditional_context = "Traditional only", router_safe_not_human_reviewed = "Router-safe", unresolved_or_rejected = "Unresolved/rejected"), name = "n"),
  corpus %>% mutate(category = if_else(needs_human_review, "Needs human review", "No review flag")) %>% count(dimension = "Review flag", category, name = "n"),
  corpus %>% mutate(category = collapse_uncertainty(uncertainty_flags)) %>% count(dimension = "Uncertainty flag", category, name = "n")
) %>%
  group_by(dimension) %>%
  mutate(pct = n / sum(n), label = paste0(category, " (", n, ")")) %>%
  ungroup() %>%
  mutate(
    dimension = factor(dimension, levels = c("Evidence level", "Review status", "Review flag", "Uncertainty flag"))
  )
write_csv(deployment_source, file.path(table_dir, "paper1_final_fig5_evidence_preservation_source.csv"))
deployment_palette <- c(
  "Level 1" = "#BDBDBD", "Level 2" = colors$green, "Level 3" = colors$blue, "Level 4" = colors$orange, "Level 5" = "#5E6268",
  "Human reviewed" = colors$green, "Router-safe" = colors$blue, "Hybrid accepted" = colors$orange, "Traditional only" = "#BDBDBD", "Unresolved/rejected" = colors$red,
  "Needs human review" = colors$red, "No review flag" = "#A7B8C8",
  "Bibliography caveat" = colors$orange, "Bibliography-only flag" = "#9BBAD8", "Extraction/context flag" = colors$red, "No flag" = "#BDBDBD", "Other flag" = colors$gray
)
fig5 <- ggplot(deployment_source, aes(n, reorder(category, n), fill = category)) +
  geom_col(width = 0.62, show.legend = FALSE) +
  geom_text(aes(label = n), hjust = -0.12, size = 3, color = colors$text) +
  facet_grid(dimension ~ ., scales = "free_y", space = "free_y", switch = "y") +
  scale_fill_manual(values = deployment_palette, drop = FALSE) +
  scale_x_continuous(expand = expansion(mult = c(0, 0.14))) +
  labs(
    title = "Evidence-Preserving Corpus Deployment",
    subtitle = "Corpus-wide outputs retain evidence levels, review status, uncertainty flags, and review needs.",
    x = "Contexts",
    y = NULL,
    caption = "Preservation of flags does not validate every corpus-wide label or estimate corpus-wide recall."
  ) +
  theme_final(base_size = 11) +
  theme(
    strip.placement = "outside",
    strip.text.y.left = element_text(angle = 0, face = "bold", hjust = 1),
    panel.spacing.y = unit(0.6, "lines"),
    axis.text.y = element_text(size = 9.2),
    legend.position = "none"
  )
save_plot(fig5, "paper1_fig5_evidence_preservation", width = 9.6, height = 7.2)

# Figure 6 --------------------------------------------------------------------
## Contexts (manual / substantive / audit / no-review) are read from
## analysis/results/review_burden_partition.csv, written by
## scripts/pipeline/59_reconcile_partitions.R from the record-level corpus.
## Seconds-per-context are the only inline literals here — they are policy
## assumptions documented in Methods §2.9 (fast/typical/conservative), not data.
## All hours and reduction percents below are computed from contexts × seconds;
## they are not inlined.
partition_path <- file.path(root, "analysis", "results", "review_burden_partition.csv")
if (!file.exists(partition_path)) {
  stop("Missing ", partition_path, ". Run scripts/pipeline/59_reconcile_partitions.R first.")
}
partition <- read_csv(partition_path, show_col_types = FALSE)
get_partition_count <- function(class_name) {
  row <- partition[partition$partition_class == class_name, ]
  if (nrow(row) != 1L) stop("Missing partition row: ", class_name, call. = FALSE)
  as.integer(row$found)
}
n_manual <- get_partition_count("corpus_total")
n_substantive <- get_partition_count("substantive_review")
n_audit <- get_partition_count("audit_review")
n_no_review <- get_partition_count("no_review_required")

review_burden <- tibble(
  assumption_set = c("Fast", "Typical", "Conservative"),
  substantive_review_seconds = c(60, 90, 120),
  audit_review_seconds = c(20, 30, 45)
) %>%
  mutate(
    manual_contexts = n_manual,
    hybrid_substantive_contexts = n_substantive,
    hybrid_audit_contexts = n_audit,
    hybrid_no_review_required_contexts = n_no_review,
    estimated_manual_hours = manual_contexts * substantive_review_seconds / 3600,
    estimated_hybrid_hours = (hybrid_substantive_contexts * substantive_review_seconds +
                                hybrid_audit_contexts * audit_review_seconds) / 3600,
    estimated_reduction_hours = estimated_manual_hours - estimated_hybrid_hours,
    estimated_reduction_percent = 100 * estimated_reduction_hours / estimated_manual_hours,
    assumption_label = paste0(assumption_set, "\n", substantive_review_seconds, "s substantive / ", audit_review_seconds, "s audit")
  )
write_csv(review_burden, file.path(table_dir, "paper1_final_fig6_review_burden_source.csv"))
labor_plot <- review_burden %>%
  select(assumption_set, assumption_label, estimated_manual_hours, estimated_hybrid_hours, estimated_reduction_percent) %>%
  pivot_longer(cols = c(estimated_manual_hours, estimated_hybrid_hours), names_to = "workflow", values_to = "estimated_hours") %>%
  mutate(
    workflow_label = recode(workflow, estimated_manual_hours = "Full manual review", estimated_hybrid_hours = "Frozen hybrid workflow"),
    workflow_label = factor(workflow_label, levels = c("Full manual review", "Frozen hybrid workflow")),
    assumption_label = factor(assumption_label, levels = review_burden$assumption_label)
  )
reduction_labels <- labor_plot %>% filter(workflow == "estimated_hybrid_hours") %>% mutate(label = paste0(sprintf("%.1f", estimated_reduction_percent), "% lower"))
fig6 <- ggplot(labor_plot, aes(assumption_label, estimated_hours, fill = workflow_label)) +
  geom_col(position = position_dodge(width = 0.72), width = 0.62) +
  geom_text(aes(label = sprintf("%.1f h", estimated_hours)), position = position_dodge(width = 0.72), vjust = -0.3, size = 3.2) +
  geom_label(data = reduction_labels, aes(label = label, y = estimated_hours + max(labor_plot$estimated_hours) * 0.08),
             position = position_dodge(width = 0.72), fill = "#F6F6F6", color = colors$text, linewidth = 0.22,
             label.r = unit(0.08, "lines"), size = 3, show.legend = FALSE) +
  annotate("label", x = 2, y = max(labor_plot$estimated_hours) * 1.22,
           label = paste0("Policy counts: ", n_substantive,
                          " substantive review; ", n_audit,
                          " audit review; ", n_no_review, " no-review-required."),
           fill = "#F6F6F6", color = colors$text, linewidth = 0.25, size = 3.2) +
  scale_fill_manual(values = c("Full manual review" = "#9A9A9A", "Frozen hybrid workflow" = colors$blue)) +
  scale_y_continuous(expand = expansion(mult = c(0, 0.26))) +
  labs(
    title = "Estimated Human Review Burden Under Automation-Boundary Policies",
    subtitle = "Hybrid estimates limit substantive review to contexts flagged by the frozen automation-boundary policy.",
    x = "Review-policy assumption",
    y = "Estimated human review hours",
    caption = "Workflow-planning estimates derived from review-policy assumptions. They are not observed timing measurements or generalizable annotation rates."
  ) +
  theme_final()
save_plot(fig6, "paper1_fig6_review_burden", width = 9.5, height = 5.4)

message("Generated final Paper 1 figure package.")
