suppressPackageStartupMessages({
  library(fs)
  library(yaml)
})

get_project_root <- function(start = getwd()) {
  start <- normalizePath(start, winslash = "/", mustWork = TRUE)
  candidates <- unique(c(
    start,
    dirname(start),
    dirname(dirname(start)),
    dirname(dirname(dirname(start)))
  ))

  for (candidate in candidates) {
    if (
      file.exists(file.path(candidate, "config", "paths.yml")) &&
        dir.exists(file.path(candidate, "scripts"))
    ) {
      return(candidate)
    }
  }

  stop("Could not locate project root from: ", start, call. = FALSE)
}

load_paths <- function(root = get_project_root()) {
  cfg <- yaml::read_yaml(file.path(root, "config", "paths.yml"))

  flatten <- function(x, prefix = NULL) {
    out <- list()
    for (nm in names(x)) {
      key <- if (is.null(prefix)) nm else paste(prefix, nm, sep = ".")
      if (is.list(x[[nm]]) && !is.null(names(x[[nm]]))) {
        out <- c(out, flatten(x[[nm]], key))
      } else {
        out[[key]] <- x[[nm]]
      }
    }
    out
  }

  flat <- flatten(cfg)
  lapply(flat, function(p) {
    if (is.character(p) && length(p) == 1 && !grepl("^(/|[A-Za-z]:)", p)) {
      fs::path(root, p)
    } else {
      p
    }
  })
}

ensure_project_dirs <- function(paths = load_paths()) {
  dir_keys <- grep("^(data|outputs|scripts)\\.", names(paths), value = TRUE)
  invisible(lapply(paths[dir_keys], function(p) fs::dir_create(p, recurse = TRUE)))
}

path_get <- function(paths, key) {
  if (!key %in% names(paths)) stop("Unknown path key: ", key, call. = FALSE)
  paths[[key]]
}
