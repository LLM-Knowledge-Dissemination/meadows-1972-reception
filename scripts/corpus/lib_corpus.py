"""Shared library for the production corpus build (analysis/corpus_production/).

Same shape as scripts/spike/lib_spike.py — separate copy so the production
artifacts have their own dedicated raw/ tree and don't co-mingle with the
spike's exploratory raw files.

All requests:
  - OpenAlex polite pool via mailto= (OPENALEX_EMAIL).
  - S2 API key if SEMANTIC_SCHOLAR_API_KEY is set; else public rate limit
    (note this in the provenance manifest).
  - Persist raw JSON to analysis/corpus_production/raw/ for reproducibility.
  - Sidecar .meta.json records URL, retrieved_at_utc, http_status, user_agent.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "analysis" / "corpus_production"
RAW_DIR = CORPUS_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

OPENALEX_EMAIL = os.environ.get("OPENALEX_EMAIL") or "gchism@arizona.edu"
S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or os.environ.get("S2_API_KEY")

OPENALEX_BASE = "https://api.openalex.org"
S2_BASE = "https://api.semanticscholar.org/graph/v1"
USER_AGENT = "meadows-1972-bibliometrics-corpus/2026.06 (mailto:" + OPENALEX_EMAIL + ")"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _save_raw(name_stem: str, payload: dict | list, url: str, status: int,
              subdir: str | None = None) -> Path:
    target_dir = RAW_DIR if subdir is None else (RAW_DIR / subdir)
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{name_stem}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    side = target_dir / f"{name_stem}.meta.json"
    side.write_text(json.dumps({
        "url": url,
        "retrieved_at_utc": now_iso(),
        "http_status": status,
        "user_agent": USER_AGENT,
    }, indent=2))
    return out


def openalex_get(path: str, params: dict | None = None, save_as: str | None = None,
                 max_retries: int = 4, subdir: str | None = None) -> dict:
    params = dict(params or {})
    params.setdefault("mailto", OPENALEX_EMAIL)
    url = f"{OPENALEX_BASE}/{path.lstrip('/')}"
    backoff = 1.0
    last_status = None
    for _ in range(max_retries):
        r = requests.get(url, params=params,
                         headers={"User-Agent": USER_AGENT}, timeout=60)
        last_status = r.status_code
        if r.status_code == 200:
            body = r.json()
            if save_as:
                _save_raw(save_as, body, r.url, r.status_code, subdir=subdir)
            return body
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        r.raise_for_status()
    raise RuntimeError(f"OpenAlex GET failed after {max_retries} tries; "
                       f"last_status={last_status} url={url}")


def openalex_paginate(path: str, base_params: dict | None = None,
                      page_size: int = 200, max_pages: int | None = None,
                      raw_stem: str | None = None,
                      subdir: str | None = None) -> dict:
    params = dict(base_params or {})
    params.setdefault("per-page", page_size)
    params.setdefault("cursor", "*")
    all_results: list[dict] = []
    pages_meta: list[dict] = []
    page_no = 0
    first_meta: dict | None = None
    while True:
        page_no += 1
        body = openalex_get(
            path, params=params,
            save_as=(f"{raw_stem}_page{page_no:04d}" if raw_stem else None),
            subdir=subdir,
        )
        meta = body.get("meta", {})
        if first_meta is None:
            first_meta = dict(meta)
        results = body.get("results", []) or []
        all_results.extend(results)
        next_cursor = (meta or {}).get("next_cursor")
        pages_meta.append({"page": page_no, "count": len(results),
                           "cursor_in": params.get("cursor"),
                           "next_cursor": next_cursor})
        if not next_cursor or not results:
            break
        if max_pages and page_no >= max_pages:
            break
        params["cursor"] = next_cursor
        time.sleep(0.12)
    return {"meta": first_meta or {}, "results": all_results,
            "pages_fetched": page_no, "pages_meta": pages_meta}


def s2_get(path: str, params: dict | None = None, save_as: str | None = None,
           max_retries: int = 8, initial_backoff: float = 5.0,
           subdir: str | None = None) -> dict:
    url = f"{S2_BASE}/{path.lstrip('/')}"
    headers = {"User-Agent": USER_AGENT}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    backoff = float(initial_backoff)
    last_status = None
    for _ in range(max_retries):
        r = requests.get(url, params=params or {}, headers=headers, timeout=60)
        last_status = r.status_code
        if r.status_code == 200:
            body = r.json()
            if save_as:
                _save_raw(save_as, body, r.url, r.status_code, subdir=subdir)
            return body
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 1.8, 60)
            continue
        r.raise_for_status()
    raise RuntimeError(f"S2 GET failed after {max_retries} tries; "
                       f"last_status={last_status} url={url}")


def sha256_short(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()[:16]


def decade_of(year) -> str:
    if isinstance(year, int) and 1900 <= year <= 2100:
        return f"{(year // 10) * 10}s"
    return "unknown"
