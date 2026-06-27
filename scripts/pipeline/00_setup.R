suppressPackageStartupMessages({
  library(fs)
})

source("scripts/helpers/project_paths.R")

paths <- load_paths()
ensure_project_dirs(paths)

message("Project directories are ready.")
