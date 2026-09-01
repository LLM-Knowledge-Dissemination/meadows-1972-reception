#!/usr/bin/env python3
"""Step 3b — extract citing CONTEXTS from OpenAlex OA full-text/PDF fallback.

For citing works that have an OpenAlex OA URL (PDF or HTML landing page),
fetch the document and extract sentences mentioning the seed (author surname
or canonical title fragment).

DATA capture only — no labels, no inference. Stores the raw extracted
sentence(s) plus a small surrounding window for downstream sampling /
annotation design.

Configurable via env vars:
  CORPUS_OA_N_PER     — per (seed × decade) sample size (default 30)
  CORPUS_OA_SEED      — RNG seed for stratified sampling (default 20260624)
  CORPUS_OA_DECADES   — comma list (default all 6 decades)
  CORPUS_OA_TIMEOUT   — per-request timeout seconds (default 25)
  CORPUS_OA_MAX_BYTES — cap on per-document bytes to fetch (default 8 MB;
                        prevents fetching huge journal PDFs by mistake)

Important: parsing PDFs in plain Python without external libs is
imperfect — we extract by scanning the raw PDF text stream for the seed
markers. HTML pages are scanned by tag-stripping. We accept that some
PDFs will yield 0 matches even when the citation is present (figure
captions, footnotes, multi-column layouts). This is documented in the
attempted-rows CSV as "fetched_but_no_match".

Outputs:
  analysis/corpus_production/contexts_oa.csv          (one row per (seed,
                                                       citing, occurrence))
  analysis/corpus_production/contexts_oa_attempted.csv (one row per (seed,
                                                       citing) attempt)
  analysis/corpus_production/raw/oa_fulltext/         (raw fetched bytes,
                                                       capped + hashed)
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import requests
from lib_corpus import CORPUS_DIR, now_iso, USER_AGENT
from context_windows import three_sentence_window

CENSUS_CSV = CORPUS_DIR / "citing_census.csv"
RAW_FT_DIR = CORPUS_DIR / "raw" / "oa_fulltext"
RAW_FT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CONTEXTS = CORPUS_DIR / "contexts_oa.csv"
OUT_ATTEMPTED = CORPUS_DIR / "contexts_oa_attempted.csv"

N_PER = int(os.environ.get("CORPUS_OA_N_PER", "30"))
RNG_SEED = int(os.environ.get("CORPUS_OA_SEED", "20260624"))
DECADES = [d.strip() for d in os.environ.get(
    "CORPUS_OA_DECADES", "1970s,1980s,1990s,2000s,2010s,2020s").split(",")]
TIMEOUT = float(os.environ.get("CORPUS_OA_TIMEOUT", "25"))
MAX_BYTES = int(os.environ.get("CORPUS_OA_MAX_BYTES", str(8 * 1024 * 1024)))
CACHE_ONLY = os.environ.get("CORPUS_OA_CACHE_ONLY", "0") == "1"
CACHE_PREFERRED = os.environ.get("CORPUS_OA_CACHE_PREFERRED", "0") == "1"

# Seed-detection patterns. We use BOTH the canonical-title fragment AND the
# author surname so we capture in-text citations like "(Meadows et al. 1972)"
# AND footnoted forms like "The Limits to Growth (Meadows 1972) ...".
SEED_PATTERNS = {
    "meadows_1972_limits_to_growth": {
        "author": re.compile(r"\bMeadows[,\s]+(?:D\.|Donella|Dennis)?[\w\s\.]*?\s*(?:19|')72\b|"
                              r"\bMeadows\s+et\s+al\.?\s*\(?\s*(?:19)?72", re.IGNORECASE),
        "author_short": re.compile(r"\bMeadows\b", re.IGNORECASE),
        "title": re.compile(r"Limits\s+to\s+Growth", re.IGNORECASE),
        "year": re.compile(r"\b1972\b"),
    },
    "commoner_1971_closing_circle": {
        "author": re.compile(r"\bCommoner[,\s]+(?:B\.|Barry)?[\w\s\.]*?\s*(?:19|')71\b|"
                              r"\bCommoner\s*\(?\s*(?:19)?71", re.IGNORECASE),
        "author_short": re.compile(r"\bCommoner\b", re.IGNORECASE),
        "title": re.compile(r"Closing\s+Circle", re.IGNORECASE),
        "year": re.compile(r"\b1971\b"),
    },
    "schumacher_1974_small_is_beautiful": {
        "author": re.compile(r"\bSchumacher[,\s]+(?:E\.|Ernst)?[\w\s\.]*?\s*(?:19|')7[34]\b|"
                              r"\bSchumacher\s*\(?\s*(?:19)?7[34]", re.IGNORECASE),
        "author_short": re.compile(r"\bSchumacher\b", re.IGNORECASE),
        "title": re.compile(r"Small\s*is\s*Beautiful", re.IGNORECASE),
        "year": re.compile(r"\b197[34]\b"),
    },
}

# Rudimentary PDF→text extraction: scan stream contents between BT / ET
# operators after FlateDecode. Without a PDF library this misses a lot;
# we accept the loss and flag fetched-but-no-match in the attempted table.
# For HTML, strip tags and decode entities.

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[\s\xa0]+")
def stratified_sample(rows: list[dict]) -> list[dict]:
    rng = random.Random(RNG_SEED)
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["citing_decade"] not in DECADES:
            continue
        if not (r.get("citing_oa_url") or "").strip():
            continue  # need an OA URL
        by_key[(r["seed_id"], r["citing_decade"])].append(r)
    out = []
    for (seed_id, decade), pool in sorted(by_key.items()):
        rng.shuffle(pool)
        out.extend(pool[:N_PER])
    return out


def safe_fetch(url: str) -> tuple[bytes | None, str, str | None]:
    """Returns (bytes, content_type, error_or_None). Caps bytes; chunk-wise."""
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT},
                          timeout=TIMEOUT, stream=True,
                          allow_redirects=True) as r:
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "") or ""
            buf = bytearray()
            for chunk in r.iter_content(64 * 1024):
                if not chunk:
                    break
                buf.extend(chunk)
                if len(buf) >= MAX_BYTES:
                    break
            return bytes(buf), ct, None
    except Exception as e:
        return None, "", str(e)[:200]


def text_from_html(blob: bytes) -> str:
    try:
        text = blob.decode("utf-8", errors="replace")
    except Exception:
        text = blob.decode("latin-1", errors="replace")
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def text_from_pdf(blob: bytes) -> str:
    """Extract text from a PDF using pypdf. Returns "" on parse failure.

    pypdf handles FlateDecode-compressed content streams (the common case
    for born-digital journal PDFs). OCR-scanned PDFs without embedded text
    layers still yield nothing — that's an unavoidable limitation; we
    document it in the attempted-rows CSV as fetched-but-no-match.
    """
    import io
    try:
        from pypdf import PdfReader
    except Exception:
        # Library absent: fall back to printable-ASCII heuristic.
        runs = re.findall(rb"[\x20-\x7e]{4,}", blob)
        text = b" ".join(runs).decode("latin-1", errors="replace")
        return _WS_RE.sub(" ", text).strip()
    try:
        reader = PdfReader(io.BytesIO(blob), strict=False)
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        text = "\n".join(parts)
        return _WS_RE.sub(" ", text).strip()
    except Exception:
        return ""


def detect_text_format(content_type: str, blob: bytes) -> str:
    ct = content_type.lower()
    if "pdf" in ct or blob[:5] == b"%PDF-":
        return "pdf"
    if "html" in ct or b"<html" in blob[:512].lower() or b"<!doctype html" in blob[:512].lower():
        return "html"
    return "other"


def load_cached_blob(seed_id: str, wid: str, sha16: str) -> tuple[bytes | None, str]:
    """Load a previously frozen OA document by its recorded hash."""
    if not sha16:
        return None, ""
    candidates = sorted(RAW_FT_DIR.glob(f"{seed_id}_{wid}_{sha16}.*"))
    if not candidates:
        return None, ""
    path = candidates[0]
    content_type = (
        "application/pdf" if path.suffix.lower() == ".pdf"
        else "text/html" if path.suffix.lower() == ".html"
        else "application/octet-stream"
    )
    return path.read_bytes(), content_type


def context_quality(text: str, seed_id: str, match: dict, window: dict) -> dict:
    """Attach conservative, reviewable exclusion flags to a context."""
    start = match["start"]
    fraction = (start / len(text)) if text else 0.0
    context_blob = window.get("context_text", "")
    citing = window.get("citing_sentence", "")
    preceding = text[max(0, start - 15000):start]
    reference_heading = bool(re.search(
        r"\b(?:references|bibliography|literature\s+cited)\b",
        preceding,
        re.IGNORECASE,
    ))
    seed_title = bool(SEED_PATTERNS[seed_id]["title"].search(context_blob))
    seed_author = bool(SEED_PATTERNS[seed_id]["author_short"].search(context_blob))
    citing_has_title = bool(SEED_PATTERNS[seed_id]["title"].search(citing))
    citing_has_author = bool(SEED_PATTERNS[seed_id]["author_short"].search(citing))
    citing_has_seed_year = bool(SEED_PATTERNS[seed_id]["year"].search(citing))
    citing_attributed = (
        (citing_has_author and citing_has_seed_year)
        or (citing_has_title and (citing_has_author or citing_has_seed_year))
    )
    years = re.findall(r"\b(?:18|19|20)\d{2}[a-z]?\b", context_blob, re.IGNORECASE)
    publisher_cue = bool(re.search(
        r"\b(?:press|publisher|new\s+york|london|bantam|knopf|universe\s+books|"
        r"harper|macmillan|routledge|springer|google\s+scholar|doi|https?://|vol\.?|pp?\.)\b",
        context_blob,
        re.IGNORECASE,
    ))
    numbered_entry = bool(re.match(r"\s*(?:\[?\d{1,3}\]?\s+)", citing))
    short_title_or_name = len(citing.split()) <= 18 and (seed_title or seed_author)
    neighbor_has_title = bool(SEED_PATTERNS[seed_id]["title"].search(
        window.get("sentence_before", "") + " " + window.get("sentence_after", "")
    ))
    reference_score = sum((
        fraction >= 0.75,
        reference_heading,
        publisher_cue,
        len(years) >= 2,
        numbered_entry,
        short_title_or_name,
    ))
    structured_entry = short_title_or_name and (
        publisher_cue or fraction >= 0.75 or (fraction >= 0.60 and neighbor_has_title)
    )
    bibliography_only = (seed_title or seed_author) and (
        reference_score >= 3 or structured_entry
    )
    boilerplate = bool(re.search(
        r"cloudflare|captcha|access\s+denied|verify\s+you\s+are\s+human|"
        r"attention\s+required|security\s+challenge",
        context_blob,
        re.IGNORECASE,
    ))
    flags = []
    if bibliography_only:
        flags.append("likely_bibliography_only")
    if match.get("match_kind") == "title_phrase_unattributed":
        flags.append("seed_attribution_ambiguous")
    if not citing_attributed:
        flags.append("citing_sentence_missing_seed_attribution")
    if boilerplate:
        flags.append("network_or_antibot_boilerplate")
    complete = bool(window.get("context_window_complete"))
    return {
        "match_document_fraction": f"{fraction:.6f}",
        "context_quality_flags": "|".join(flags),
        "annotation_eligible": complete and not flags,
    }


def find_seed_matches(text: str, seed_id: str) -> list[dict]:
    """Return one explicit sentence window per detected citing sentence."""
    pat = SEED_PATTERNS[seed_id]
    matches = []
    # Strict matches first (author+year combos)
    for m in pat["author"].finditer(text):
        matches.append({"start": m.start(), "end": m.end(),
                         "match_kind": "author_year_combo",
                         "matched": m.group(0)})
    # Title matches are retained for source audit, but an unaccompanied title
    # phrase is not annotation-eligible because phrases such as "limits to
    # growth" and "small is beautiful" can refer to other works or concepts.
    for m in pat["title"].finditer(text):
        nearby = text[max(0, m.start() - 250):min(len(text), m.end() + 250)]
        attributed = bool(pat["author_short"].search(nearby) or pat["year"].search(nearby))
        matches.append({"start": m.start(), "end": m.end(),
                         "match_kind": ("title_phrase_attributed" if attributed
                                        else "title_phrase_unattributed"),
                         "matched": m.group(0)})
    # Coincidence filter: surname + year in same neighborhood (200 chars)
    short_hits = list(pat["author_short"].finditer(text))
    year_positions = [m.start() for m in pat["year"].finditer(text)]
    year_set = set(year_positions)
    for hit in short_hits:
        # avoid duplicating author_year_combo hits
        if any(abs(hit.start() - m["start"]) < 20 for m in matches):
            continue
        # require a year within ±200 chars
        if any(abs(hit.start() - y) < 200 for y in year_set):
            matches.append({"start": hit.start(), "end": hit.end(),
                             "match_kind": "author_near_year",
                             "matched": hit.group(0)})
    # Sort matches, then dedupe multiple markers inside the same sentence.
    matches.sort(key=lambda m: m["start"])
    out = []
    seen_sentence_spans = set()
    for m in matches:
        explicit_window = three_sentence_window(text, m["start"], m["end"])
        citing_span = (
            explicit_window.pop("_citing_span_start"),
            explicit_window.pop("_citing_span_end"),
        )
        if citing_span in seen_sentence_spans:
            continue
        seen_sentence_spans.add(citing_span)
        # Retain the legacy character neighborhood for extraction audit only.
        s = max(0, m["start"] - 400)
        e = min(len(text), m["end"] + 400)
        window = text[s:e]
        out.append({
            **m,
            **explicit_window,
            **context_quality(text, seed_id, m, explicit_window),
            "sentence": explicit_window["citing_sentence"],
            "neighborhood": window[:1200],
        })
    return out


def main() -> None:
    if not CENSUS_CSV.exists():
        raise SystemExit("Run 02_citing_census.py first.")
    print(f"[{now_iso()}] Step 3b — OA full-text/PDF context extraction")
    print(f"  decades: {DECADES}  n_per (seed x decade): {N_PER}")
    print(f"  timeout={TIMEOUT}s  max_bytes={MAX_BYTES}\n")
    if CACHE_ONLY:
        print("  source mode: frozen local OA cache only (no network requests)\n")
    elif CACHE_PREFERRED:
        print("  source mode: reuse frozen OA cache, fetch only uncached sample rows\n")
    with CENSUS_CSV.open() as f:
        rows = list(csv.DictReader(f))
    print(f"  loaded {len(rows)} census rows")
    sample = stratified_sample(rows)
    print(f"  sample size: {len(sample)} (citing works with OA URLs)\n")

    contexts_fields = [
        "seed_id", "citing_openalex_id", "citing_doi", "citing_year",
        "citing_decade", "citing_type", "oa_url", "content_type",
        "match_index", "match_kind", "match_text",
        "sentence_before", "citing_sentence", "sentence_after",
        "context_text", "context_window_complete", "context_sentence_count",
        "context_window_status", "match_document_fraction",
        "context_quality_flags", "annotation_eligible", "sentence", "neighborhood",
        "doc_sha256_16", "retrieval_route",
        "retrieved_at_utc",
    ]
    attempted_fields = [
        "seed_id", "citing_openalex_id", "citing_doi", "citing_year",
        "citing_decade", "citing_type", "oa_url",
        "fetch_status", "content_type", "bytes", "text_format",
        "n_matches", "doc_sha256_16", "error", "retrieved_at_utc",
    ]

    contexts_rows: list[dict] = []
    attempted_rows: list[dict] = []
    prior_attempts = {}
    if (CACHE_ONLY or CACHE_PREFERRED) and OUT_ATTEMPTED.exists():
        with OUT_ATTEMPTED.open() as f:
            prior_attempts = {
                (row["seed_id"], row["citing_openalex_id"]): row
                for row in csv.DictReader(f)
            }

    for i, r in enumerate(sample, 1):
        seed_id = r["seed_id"]
        url = r["citing_oa_url"]
        wid = r["citing_openalex_id"].split("/")[-1]
        prior = prior_attempts.get((seed_id, r["citing_openalex_id"]), {})
        retrieved_at = prior.get("retrieved_at_utc") or now_iso()
        from_cache = False
        if CACHE_ONLY or CACHE_PREFERRED:
            blob, inferred_ct = load_cached_blob(seed_id, wid, prior.get("doc_sha256_16", ""))
            ct = prior.get("content_type") or inferred_ct
            from_cache = blob is not None
            err = None if from_cache else (prior.get("error") or "not present in frozen OA cache")
            if CACHE_PREFERRED and not from_cache:
                blob, ct, err = safe_fetch(url)
                retrieved_at = now_iso()
        else:
            blob, ct, err = safe_fetch(url)
        if blob is None:
            attempted_rows.append({
                "seed_id": seed_id, "citing_openalex_id": r["citing_openalex_id"],
                "citing_doi": r["citing_doi"], "citing_year": r["citing_year"],
                "citing_decade": r["citing_decade"], "citing_type": r["citing_type"],
                "oa_url": url, "fetch_status": prior.get("fetch_status") or "fetch_failed",
                "content_type": "", "bytes": 0, "text_format": "",
                "n_matches": 0, "doc_sha256_16": "",
                "error": err or "unknown", "retrieved_at_utc": retrieved_at,
            })
            if not CACHE_ONLY and not from_cache:
                time.sleep(0.5)
            continue
        sha16 = hashlib.sha256(blob).hexdigest()[:16]
        fmt = detect_text_format(ct, blob)
        # Persist raw bytes for reproducibility (named by hash)
        ext = ".pdf" if fmt == "pdf" else (".html" if fmt == "html" else ".bin")
        raw_path = RAW_FT_DIR / f"{seed_id}_{wid}_{sha16}{ext}"
        try:
            raw_path.write_bytes(blob)
        except Exception:
            pass
        text = (text_from_pdf(blob) if fmt == "pdf"
                else text_from_html(blob) if fmt == "html"
                else "")
        matches = find_seed_matches(text, seed_id) if text else []
        attempted_rows.append({
            "seed_id": seed_id, "citing_openalex_id": r["citing_openalex_id"],
            "citing_doi": r["citing_doi"], "citing_year": r["citing_year"],
            "citing_decade": r["citing_decade"], "citing_type": r["citing_type"],
            "oa_url": url, "fetch_status": "fetched",
            "content_type": ct, "bytes": len(blob), "text_format": fmt,
            "n_matches": len(matches), "doc_sha256_16": sha16,
            "error": "", "retrieved_at_utc": retrieved_at,
        })
        for j, m in enumerate(matches):
            contexts_rows.append({
                "seed_id": seed_id,
                "citing_openalex_id": r["citing_openalex_id"],
                "citing_doi": r["citing_doi"],
                "citing_year": r["citing_year"],
                "citing_decade": r["citing_decade"],
                "citing_type": r["citing_type"],
                "oa_url": url, "content_type": ct,
                "match_index": j, "match_kind": m["match_kind"],
                "match_text": m["matched"][:200],
                "sentence_before": m["sentence_before"],
                "citing_sentence": m["citing_sentence"],
                "sentence_after": m["sentence_after"],
                "context_text": m["context_text"],
                "context_window_complete": m["context_window_complete"],
                "context_sentence_count": m["context_sentence_count"],
                "context_window_status": m["context_window_status"],
                "match_document_fraction": m["match_document_fraction"],
                "context_quality_flags": m["context_quality_flags"],
                "annotation_eligible": m["annotation_eligible"],
                "sentence": m["sentence"],
                "neighborhood": m["neighborhood"],
                "doc_sha256_16": sha16,
                "retrieval_route": "openalex_oa_fulltext",
                "retrieved_at_utc": retrieved_at,
            })
        if i % 25 == 0:
            print(f"  [{i}/{len(sample)}] contexts={len(contexts_rows)} "
                  f"fetched={sum(1 for x in attempted_rows if x['fetch_status']=='fetched')}")
            with OUT_CONTEXTS.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=contexts_fields, lineterminator="\n")
                w.writeheader()
                for cr in contexts_rows:
                    w.writerow({k: cr.get(k, "") for k in contexts_fields})
            with OUT_ATTEMPTED.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=attempted_fields, lineterminator="\n")
                w.writeheader()
                for ar in attempted_rows:
                    w.writerow({k: ar.get(k, "") for k in attempted_fields})
        # Be polite to upstream OA servers
        if not CACHE_ONLY and not from_cache:
            time.sleep(0.3)

    with OUT_CONTEXTS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=contexts_fields, lineterminator="\n")
        w.writeheader()
        for cr in contexts_rows:
            w.writerow({k: cr.get(k, "") for k in contexts_fields})
    with OUT_ATTEMPTED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=attempted_fields, lineterminator="\n")
        w.writeheader()
        for ar in attempted_rows:
            w.writerow({k: ar.get(k, "") for k in attempted_fields})
    print(f"\nwrote {OUT_CONTEXTS} ({len(contexts_rows)} match rows)")
    print(f"wrote {OUT_ATTEMPTED} ({len(attempted_rows)} attempt rows)")
    print(f"finished_at={now_iso()}")


if __name__ == "__main__":
    main()
