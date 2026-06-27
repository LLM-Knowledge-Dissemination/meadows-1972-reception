#!/usr/bin/env python3
"""OA disentangle + representativeness + recovery scoping.

Analysis-only on existing build outputs. Extends scripts/corpus/. Reuses
lib_corpus helpers + Wilson CI math. NOT in scope: extraction, annotation,
labeling.

Produces:
  analysis/corpus_production/oa_joint_yield.csv
  analysis/corpus_production/sample_vs_census_oa.csv
  analysis/corpus_production/yield_projection_oa_honest.csv
  analysis/corpus_production/oa_vs_nonoa_metadata.csv
  analysis/corpus_production/targeted_recovery_scope.csv

Pure-Python IRLS logistic regression used for Step 1's adjusted effects (no
scipy/numpy in the .venv). The implementation is deliberately small — only
appropriate for the ~885-row, ~10-coefficient problem here.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_corpus import CORPUS_DIR, now_iso

CENSUS = CORPUS_DIR / "citing_census.csv"
S2_ATT = CORPUS_DIR / "contexts_s2_attempted.csv"
OA_ATT = CORPUS_DIR / "contexts_oa_attempted.csv"
COMBINED = CORPUS_DIR / "contexts_combined.csv"

OUT_JOINT = CORPUS_DIR / "oa_joint_yield.csv"
OUT_SAMPLE_VS_CENSUS = CORPUS_DIR / "sample_vs_census_oa.csv"
OUT_OA_HONEST = CORPUS_DIR / "yield_projection_oa_honest.csv"
OUT_OA_VS_NON = CORPUS_DIR / "oa_vs_nonoa_metadata.csv"
OUT_TARGETED = CORPUS_DIR / "targeted_recovery_scope.csv"

DECADES_ORDER = ["1970s", "1980s", "1990s", "2000s", "2010s", "2020s", "unknown"]
SEEDS_ACTIVE = [
    "meadows_1972_limits_to_growth",
    "commoner_1971_closing_circle",
    "schumacher_1974_small_is_beautiful",
]
Z = 1.959963984540054  # qnorm(0.975)
NON_ARTICLE_TYPES = {"book", "book-chapter", "book-section", "dissertation",
                      "report", "reference-entry", "review", "editorial",
                      "paratext", "letter", "other"}


# ----- math helpers ----------------------------------------------------------

def wilson_ci(k: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    z2 = Z * Z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (Z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def mat_mul(A, B):
    n, k = len(A), len(A[0])
    m = len(B[0])
    out = [[0.0] * m for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        for j in range(m):
            s = 0.0
            for r in range(k):
                s += Ai[r] * B[r][j]
            out[i][j] = s
    return out


def mat_T(A):
    return [list(c) for c in zip(*A)]


def mat_inv(M):
    """Gauss-Jordan inverse for small square matrices."""
    n = len(M)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        # partial pivot
        pivot = col
        for r in range(col + 1, n):
            if abs(aug[r][col]) > abs(aug[pivot][col]):
                pivot = r
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError(f"Singular at column {col}")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        # scale row
        s = aug[col][col]
        aug[col] = [x / s for x in aug[col]]
        # eliminate other rows
        for r in range(n):
            if r != col and abs(aug[r][col]) > 1e-15:
                factor = aug[r][col]
                aug[r] = [aug[r][i] - factor * aug[col][i] for i in range(2 * n)]
    return [row[n:] for row in aug]


def sigmoid(x: float) -> float:
    if x >= 0:
        e = math.exp(-x)
        return 1.0 / (1.0 + e)
    e = math.exp(x)
    return e / (1.0 + e)


def logistic_irls(X: list[list[float]], y: list[int],
                  max_iter: int = 50, tol: float = 1e-7,
                  l2: float = 1e-4) -> tuple[list[float], list[float]]:
    """Fit logistic via IRLS / Newton-Raphson. Returns (beta, SE_beta).

    l2 = small ridge penalty for numerical stability (separation, near-empty
    cells). The penalty regularizes coefficients toward 0 by 1e-4; effect on
    parameter estimates is negligible relative to small-sample noise here.
    """
    n = len(X)
    p = len(X[0])
    beta = [0.0] * p
    for it in range(max_iter):
        # Compute eta = Xβ, mu = sigmoid(eta), w = mu*(1-mu)
        eta = [sum(X[i][j] * beta[j] for j in range(p)) for i in range(n)]
        mu = [sigmoid(e) for e in eta]
        w = [max(1e-8, m * (1 - m)) for m in mu]
        # Compute X' W X + l2*I and X' (y - mu) - l2 * beta
        XtWX = [[0.0] * p for _ in range(p)]
        Xtr = [0.0] * p
        for i in range(n):
            xi = X[i]
            wi = w[i]
            ri = y[i] - mu[i]
            for j in range(p):
                Xtr[j] += xi[j] * ri
                XtWXj = XtWX[j]
                xij_wi = xi[j] * wi
                for k in range(p):
                    XtWXj[k] += xij_wi * xi[k]
        for j in range(p):
            XtWX[j][j] += l2
            Xtr[j] -= l2 * beta[j]
        try:
            inv = mat_inv(XtWX)
        except ValueError:
            break
        delta = [sum(inv[j][k] * Xtr[k] for k in range(p)) for j in range(p)]
        new_beta = [beta[j] + delta[j] for j in range(p)]
        max_change = max(abs(d) for d in delta)
        beta = new_beta
        if max_change < tol:
            break
    # Standard errors: diag(inv(X'WX))
    eta = [sum(X[i][j] * beta[j] for j in range(p)) for i in range(n)]
    mu = [sigmoid(e) for e in eta]
    w = [max(1e-8, m * (1 - m)) for m in mu]
    XtWX = [[0.0] * p for _ in range(p)]
    for i in range(n):
        xi = X[i]
        wi = w[i]
        for j in range(p):
            XtWXj = XtWX[j]
            xij_wi = xi[j] * wi
            for k in range(p):
                XtWXj[k] += xij_wi * xi[k]
    for j in range(p):
        XtWX[j][j] += l2
    inv = mat_inv(XtWX)
    se = [math.sqrt(max(0.0, inv[j][j])) for j in range(p)]
    return beta, se


# ----- data plumbing ---------------------------------------------------------

def load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def is_oa_bool(s: str) -> bool:
    return s == "True"


def type_collapsed(t: str) -> str:
    """Collapse work-type into 4-level field for the joint cross-tab."""
    if not t:
        return "other"
    if t == "article":
        return "article"
    if t in {"book-chapter", "book-section"}:
        return "book_chapter"
    if t == "book":
        return "book"
    if t in {"dissertation", "report", "preprint", "review", "editorial",
              "paratext", "letter", "reference-entry", "other"}:
        return "other_serial_or_non_article"
    return "other_serial_or_non_article"


def main() -> None:
    print(f"[{now_iso()}] OA disentangle / representativeness / recovery")

    census = load(CENSUS)
    s2_att = load(S2_ATT)
    oa_att = load(OA_ATT)
    combined = load(COMBINED)

    # ----- Build attempt + yield pair sets -----
    s2_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in s2_att}
    oa_fetched_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in oa_att
                         if r["fetch_status"] == "fetched"}
    attempt_pairs = s2_pairs | oa_fetched_pairs    # 885
    yielder_pairs = {(r["seed_id"], r["citing_openalex_id"]) for r in combined}  # 141
    print(f"  attempts={len(attempt_pairs)}  yielders={len(yielder_pairs)}")

    # Index census by (seed, citing) for joins
    cen_idx = {(r["seed_id"], r["citing_openalex_id"]): r for r in census}
    sum_census = len(census)

    # =====================================================================
    # 1) JOINT STRATIFICATION + adjusted logistic
    # =====================================================================
    # Cross-tab: (decade × OA × type_collapsed) yield rates over the 885 sample.
    cell_n: dict[tuple, int] = defaultdict(int)
    cell_k: dict[tuple, int] = defaultdict(int)
    cell_n_census: dict[tuple, int] = defaultdict(int)
    for key in attempt_pairs:
        r = cen_idx[key]
        cell = (r["citing_decade"], "OA" if is_oa_bool(r["citing_is_oa"]) else "non-OA",
                type_collapsed(r["citing_type"]))
        cell_n[cell] += 1
        if key in yielder_pairs:
            cell_k[cell] += 1
    for r in census:
        cell = (r["citing_decade"], "OA" if is_oa_bool(r["citing_is_oa"]) else "non-OA",
                type_collapsed(r["citing_type"]))
        cell_n_census[cell] += 1

    joint_rows = []
    for cell in sorted(cell_n_census.keys(), key=lambda c: (
            DECADES_ORDER.index(c[0]) if c[0] in DECADES_ORDER else 99,
            c[1], c[2])):
        d, oa, t = cell
        n = cell_n[cell]
        k = cell_k[cell]
        N = cell_n_census[cell]
        p, lo, hi = wilson_ci(k, n)
        joint_rows.append({
            "decade": d,
            "oa_status": oa,
            "type_collapsed": t,
            "n_attempts": n,
            "k_yielders": k,
            "yield_rate": f"{p:.4f}" if n else "",
            "yield_rate_wilson95_lo": f"{lo:.4f}" if n else "",
            "yield_rate_wilson95_hi": f"{hi:.4f}" if n else "",
            "census_N": N,
            "census_share": f"{(N/sum_census):.4f}",
        })

    # Logistic regression: yield ~ decade + oa + type_collapsed.
    # Reference levels (dropped from one-hot): decade=2010s (largest sample),
    # oa=non-OA (largest census), type_collapsed=article (largest sample).
    DECADE_LEVELS = ["1970s", "1980s", "1990s", "2000s", "2020s"]  # 2010s = reference
    OA_LEVELS = ["OA"]                                              # non-OA = reference
    TYPE_LEVELS = ["book_chapter", "book", "other_serial_or_non_article"]  # article = ref

    X = []
    y = []
    coef_names = ["(Intercept)"] + [f"decade={d}" for d in DECADE_LEVELS] \
                  + [f"oa_status={o}" for o in OA_LEVELS] \
                  + [f"type_collapsed={t}" for t in TYPE_LEVELS]
    for key in attempt_pairs:
        r = cen_idx[key]
        row = [1.0]
        for lvl in DECADE_LEVELS:
            row.append(1.0 if r["citing_decade"] == lvl else 0.0)
        for lvl in OA_LEVELS:
            row.append(1.0 if (("OA" if is_oa_bool(r["citing_is_oa"]) else "non-OA") == lvl) else 0.0)
        for lvl in TYPE_LEVELS:
            row.append(1.0 if type_collapsed(r["citing_type"]) == lvl else 0.0)
        X.append(row)
        y.append(1 if key in yielder_pairs else 0)

    try:
        beta, se = logistic_irls(X, y)
        logistic_rows = []
        for name, b, s in zip(coef_names, beta, se):
            lo_b = b - Z * s
            hi_b = b + Z * s
            logistic_rows.append({
                "term": name,
                "beta_log_odds": f"{b:+.4f}",
                "se": f"{s:.4f}",
                "wald95_lo": f"{lo_b:+.4f}",
                "wald95_hi": f"{hi_b:+.4f}",
                "odds_ratio": f"{math.exp(b):.4f}",
                "odds_ratio_wald95_lo": f"{math.exp(lo_b):.4f}",
                "odds_ratio_wald95_hi": f"{math.exp(hi_b):.4f}",
                "reference_levels_dropped": "decade=2010s, oa_status=non-OA, type_collapsed=article",
                "l2_ridge": "1e-4",
            })
    except Exception as e:
        print(f"  logistic failed: {e}")
        logistic_rows = []

    # Write joint cross-tab + logistic as two blocks in oa_joint_yield.csv
    with OUT_JOINT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(joint_rows[0].keys()))
        w.writeheader()
        for r in joint_rows:
            w.writerow(r)
        f.write("\n")
        w2 = csv.writer(f)
        w2.writerow(["--- adjusted logistic (IRLS, ridge l2=1e-4) ---"])
        if logistic_rows:
            w2.writerow(list(logistic_rows[0].keys()))
            for r in logistic_rows:
                w2.writerow(list(r.values()))
    print(f"  wrote {OUT_JOINT} ({len(joint_rows)} cross-tab + {len(logistic_rows)} logistic terms)")

    # =====================================================================
    # 2) SAMPLE-vs-CENSUS OA fractions per decade
    # =====================================================================
    svc_rows = []
    for d in DECADES_ORDER:
        # census OA share for this decade
        N_d = sum(1 for r in census if r["citing_decade"] == d)
        N_oa = sum(1 for r in census if r["citing_decade"] == d and is_oa_bool(r["citing_is_oa"]))
        # sample OA share
        n_d = 0
        n_oa = 0
        for key in attempt_pairs:
            r = cen_idx[key]
            if r["citing_decade"] != d:
                continue
            n_d += 1
            if is_oa_bool(r["citing_is_oa"]):
                n_oa += 1
        census_oa = (N_oa / N_d) if N_d else 0.0
        sample_oa = (n_oa / n_d) if n_d else 0.0
        diff = sample_oa - census_oa
        # CI on sample OA fraction
        _, lo, hi = wilson_ci(n_oa, n_d)
        flag = ""
        if n_d > 0:
            if not (lo <= census_oa <= hi):
                flag = "DIVERGENT — sample OA fraction Wilson 95% CI does not cover census OA share"
            elif abs(diff) >= 0.10:
                flag = "WIDE — |sample - census| >= 10pp but CI overlaps"
            else:
                flag = "OK"
        else:
            flag = "EMPTY — no sample for this decade"
        svc_rows.append({
            "decade": d,
            "census_N": N_d,
            "census_OA_N": N_oa,
            "census_OA_fraction": f"{census_oa:.4f}",
            "sample_n": n_d,
            "sample_OA_n": n_oa,
            "sample_OA_fraction": f"{sample_oa:.4f}",
            "sample_OA_wilson95_lo": f"{lo:.4f}",
            "sample_OA_wilson95_hi": f"{hi:.4f}",
            "diff_sample_minus_census": f"{diff:+.4f}",
            "representativeness_flag": flag,
        })
    with OUT_SAMPLE_VS_CENSUS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(svc_rows[0].keys()))
        w.writeheader()
        for r in svc_rows:
            w.writerow(r)
    print(f"  wrote {OUT_SAMPLE_VS_CENSUS}")

    # =====================================================================
    # 3) OA-HONEST RE-PROJECTION via (decade × OA) joint strata
    # =====================================================================
    # Use the same joint sample/census cells, but collapsed across type.
    joint2_cell_n: dict[tuple, int] = defaultdict(int)
    joint2_cell_k: dict[tuple, int] = defaultdict(int)
    joint2_cell_N: dict[tuple, int] = defaultdict(int)
    for key in attempt_pairs:
        r = cen_idx[key]
        cell = (r["citing_decade"], "OA" if is_oa_bool(r["citing_is_oa"]) else "non-OA")
        joint2_cell_n[cell] += 1
        if key in yielder_pairs:
            joint2_cell_k[cell] += 1
    for r in census:
        cell = (r["citing_decade"], "OA" if is_oa_bool(r["citing_is_oa"]) else "non-OA")
        joint2_cell_N[cell] += 1

    oa_honest_rows = []
    total_proj = 0.0
    total_lo = 0.0
    total_hi = 0.0
    for cell in sorted(joint2_cell_N.keys(),
                       key=lambda c: (DECADES_ORDER.index(c[0]) if c[0] in DECADES_ORDER else 99, c[1])):
        d, oa = cell
        n = joint2_cell_n[cell]
        k = joint2_cell_k[cell]
        N = joint2_cell_N[cell]
        p, lo, hi = wilson_ci(k, n)
        proj = p * N
        proj_lo = lo * N
        proj_hi = hi * N
        oa_honest_rows.append({
            "decade": d,
            "oa_status": oa,
            "sample_n": n,
            "yield_k": k,
            "rate": f"{p:.4f}" if n else "",
            "rate_wilson95_lo": f"{lo:.4f}" if n else "",
            "rate_wilson95_hi": f"{hi:.4f}" if n else "",
            "census_N": N,
            "projected_yielders": f"{proj:.1f}",
            "projected_yielders_lo": f"{proj_lo:.1f}",
            "projected_yielders_hi": f"{proj_hi:.1f}",
            "note": ("BORROWED — non-OA cell empty in sample; rate borrowed from sample's overall non-OA rate"
                      if n == 0 and oa == "non-OA" else
                      "EMPTY — no sample" if n == 0 else
                      ""),
        })
        total_proj += proj
        total_lo += proj_lo
        total_hi += proj_hi

    # Where any cell had n=0 (e.g., the pre-2010 non-OA cells, since we never
    # attempted non-OA pre-2010), borrow the sample's overall NON-OA rate
    # for the corresponding non-OA cells. This is the "what-if non-OA pre-2010
    # yields like 2010s+2020s non-OA" assumption — surfaced explicitly so the
    # author can choose to floor it instead.
    overall_non_oa_n = sum(joint2_cell_n[c] for c in joint2_cell_n if c[1] == "non-OA")
    overall_non_oa_k = sum(joint2_cell_k[c] for c in joint2_cell_n if c[1] == "non-OA")
    non_oa_p, non_oa_lo, non_oa_hi = wilson_ci(overall_non_oa_k, overall_non_oa_n)
    borrowed_proj = 0.0
    borrowed_lo = 0.0
    borrowed_hi = 0.0
    for row in oa_honest_rows:
        if row["note"] == "BORROWED — non-OA cell empty in sample; rate borrowed from sample's overall non-OA rate":
            N = row["census_N"]
            row["rate"] = f"{non_oa_p:.4f} (borrowed)"
            row["rate_wilson95_lo"] = f"{non_oa_lo:.4f}"
            row["rate_wilson95_hi"] = f"{non_oa_hi:.4f}"
            row["projected_yielders"] = f"{non_oa_p * N:.1f}"
            row["projected_yielders_lo"] = f"{non_oa_lo * N:.1f}"
            row["projected_yielders_hi"] = f"{non_oa_hi * N:.1f}"
            borrowed_proj += non_oa_p * N
            borrowed_lo += non_oa_lo * N
            borrowed_hi += non_oa_hi * N

    # Recompute totals after borrowing
    final_proj = sum(float(r["projected_yielders"].split()[0]) if r["projected_yielders"] else 0.0
                      for r in oa_honest_rows)
    final_lo = sum(float(r["projected_yielders_lo"]) if r["projected_yielders_lo"] else 0.0
                    for r in oa_honest_rows)
    final_hi = sum(float(r["projected_yielders_hi"]) if r["projected_yielders_hi"] else 0.0
                    for r in oa_honest_rows)

    # Contexts per yielder (reuse the mean from earlier characterization)
    y_to_n = defaultdict(int)
    for r in combined:
        y_to_n[(r["seed_id"], r["citing_openalex_id"])] += 1
    n_ctx = list(y_to_n.values())
    mean_ctx = sum(n_ctx) / len(n_ctx)
    var_ctx = sum((x - mean_ctx) ** 2 for x in n_ctx) / len(n_ctx)
    se_ctx = math.sqrt(var_ctx) / math.sqrt(len(n_ctx))
    ctx_lo = mean_ctx - Z * se_ctx
    ctx_hi = mean_ctx + Z * se_ctx
    proj_contexts = final_proj * mean_ctx
    proj_contexts_lo = final_lo * max(0.0, ctx_lo)
    proj_contexts_hi = final_hi * ctx_hi

    with OUT_OA_HONEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(oa_honest_rows[0].keys()))
        w.writeheader()
        for r in oa_honest_rows:
            w.writerow(r)
        f.write("\n")
        w2 = csv.writer(f)
        w2.writerow(["headline", "metric", "point", "ci_lo", "ci_hi", "units"])
        w2.writerow(["oa_honest", "projected_yielding_works",
                     f"{final_proj:.0f}", f"{final_lo:.0f}", f"{final_hi:.0f}",
                     "citing works (decade x OA joint strata; non-OA pre-2010 borrowed from overall non-OA rate)"])
        w2.writerow(["oa_honest", "contexts_per_yielder_mean", f"{mean_ctx:.3f}",
                     f"{ctx_lo:.3f}", f"{ctx_hi:.3f}", f"contexts per yielding work (n={len(n_ctx)} yielders)"])
        w2.writerow(["oa_honest", "projected_contexts",
                     f"{proj_contexts:.0f}", f"{proj_contexts_lo:.0f}", f"{proj_contexts_hi:.0f}",
                     "extracted citing-context strings"])
        # Reconciliation
        w2.writerow([])
        w2.writerow(["reconciliation_vs_prior_estimates"])
        # OA-marginal: apply OA rate to OA census, non-OA rate to non-OA census
        oa_only_n = sum(joint2_cell_n[c] for c in joint2_cell_n if c[1] == "OA")
        oa_only_k = sum(joint2_cell_k[c] for c in joint2_cell_n if c[1] == "OA")
        N_oa_total = sum(joint2_cell_N[c] for c in joint2_cell_N if c[1] == "OA")
        N_non_total = sum(joint2_cell_N[c] for c in joint2_cell_N if c[1] == "non-OA")
        p_oa, lo_oa, hi_oa = wilson_ci(oa_only_k, oa_only_n)
        marginal_proj = p_oa * N_oa_total + non_oa_p * N_non_total
        marginal_lo = lo_oa * N_oa_total + non_oa_lo * N_non_total
        marginal_hi = hi_oa * N_oa_total + non_oa_hi * N_non_total
        # Decade-only marginal from prior characterization: 2628 [1402, 4332]
        w2.writerow(["estimator", "projected_yielders_point", "ci_lo", "ci_hi", "source"])
        w2.writerow(["naive_overall_rate", "2080", "1784", "2414",
                     "0.1593 * 13054 — single overall mean, flattens strata"])
        w2.writerow(["decade_only_stratified", "2628", "1402", "4332",
                     "yield_projection_stratified.csv — decade strata only"])
        w2.writerow(["oa_marginal_only", f"{marginal_proj:.0f}", f"{marginal_lo:.0f}", f"{marginal_hi:.0f}",
                     "rate by OA status applied to OA and non-OA census subsets"])
        w2.writerow(["oa_decade_joint_oa_honest", f"{final_proj:.0f}", f"{final_lo:.0f}", f"{final_hi:.0f}",
                     "decade x OA joint strata; pre-2010 non-OA cells borrow overall non-OA rate"])

    print(f"  wrote {OUT_OA_HONEST}")
    print(f"    decade-only stratified (prior): 2,628 [1,402, 4,332]")
    print(f"    OA-marginal only:              {marginal_proj:.0f} [{marginal_lo:.0f}, {marginal_hi:.0f}]")
    print(f"    decade x OA joint (OA-honest): {final_proj:.0f} [{final_lo:.0f}, {final_hi:.0f}]")

    # =====================================================================
    # 4) OA vs NON-OA full-census metadata comparison
    # =====================================================================
    # Compare distributions on full census (not sample) across observable
    # metadata: primary field, primary source (venue), decade, seed,
    # cited_by_count buckets, type. No contexts involved.
    def fmt_pct(x): return f"{x*100:.2f}%"

    def share_by(field_fn, value_fn) -> dict:
        """Returns {bucket: (oa_count, non_oa_count)}."""
        out = defaultdict(lambda: [0, 0])
        for r in census:
            b = value_fn(r)
            if is_oa_bool(r["citing_is_oa"]):
                out[b][0] += 1
            else:
                out[b][1] += 1
        return out

    N_oa_total = sum(1 for r in census if is_oa_bool(r["citing_is_oa"]))
    N_non_total = sum(1 for r in census if not is_oa_bool(r["citing_is_oa"]))

    def emit_rows(dimension: str, levels: list[str],
                   shares: dict, writer) -> None:
        for lvl in levels:
            oa_n, non_n = shares.get(lvl, [0, 0])
            oa_share = oa_n / N_oa_total if N_oa_total else 0.0
            non_share = non_n / N_non_total if N_non_total else 0.0
            diff = oa_share - non_share
            writer.writerow({
                "dimension": dimension,
                "level": lvl,
                "OA_count": oa_n,
                "non_OA_count": non_n,
                "OA_share_of_OA_subset": f"{oa_share:.4f}",
                "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
                "diff_OA_minus_non_OA": f"{diff:+.4f}",
                "absolute_diff_pp": f"{abs(diff)*100:.2f}",
            })

    oa_vs_non_rows = []
    # Decade
    dec_shares = share_by(None, lambda r: r["citing_decade"])
    for d in DECADES_ORDER:
        oa_n, non_n = dec_shares.get(d, [0, 0])
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "decade", "level": d,
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    # Type
    type_shares = share_by(None, lambda r: r["citing_type"] or "unknown")
    for t in sorted(type_shares.keys(),
                     key=lambda x: -(type_shares[x][0] + type_shares[x][1]))[:10]:
        oa_n, non_n = type_shares[t]
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "type", "level": t,
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    # Primary field (top 12)
    field_shares = share_by(None, lambda r: r["citing_primary_field"] or "unknown")
    for fld in sorted(field_shares.keys(),
                       key=lambda x: -(field_shares[x][0] + field_shares[x][1]))[:12]:
        oa_n, non_n = field_shares[fld]
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "primary_field", "level": fld,
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    # Top venues
    venue_shares = share_by(None, lambda r: r["citing_primary_source"] or "unknown")
    for v in sorted(venue_shares.keys(),
                     key=lambda x: -(venue_shares[x][0] + venue_shares[x][1]))[:10]:
        oa_n, non_n = venue_shares[v]
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "primary_source_top10", "level": v[:80],
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    # Seed
    seed_shares = share_by(None, lambda r: r["seed_id"])
    for s in SEEDS_ACTIVE:
        oa_n, non_n = seed_shares.get(s, [0, 0])
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "seed_id", "level": s,
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    # Cited-by-count buckets
    def bucket_cbc(s: str) -> str:
        try:
            n = int(s)
        except Exception:
            return "unknown"
        if n == 0:
            return "0"
        if n < 5:
            return "1-4"
        if n < 25:
            return "5-24"
        if n < 100:
            return "25-99"
        if n < 500:
            return "100-499"
        return "500+"
    cbc_shares = share_by(None, lambda r: bucket_cbc(r["citing_cited_by_count"]))
    for b in ["0", "1-4", "5-24", "25-99", "100-499", "500+", "unknown"]:
        oa_n, non_n = cbc_shares.get(b, [0, 0])
        oa_share = oa_n / N_oa_total if N_oa_total else 0.0
        non_share = non_n / N_non_total if N_non_total else 0.0
        oa_vs_non_rows.append({
            "dimension": "cited_by_count_bucket", "level": b,
            "OA_count": oa_n, "non_OA_count": non_n,
            "OA_share_of_OA_subset": f"{oa_share:.4f}",
            "non_OA_share_of_non_OA_subset": f"{non_share:.4f}",
            "diff_OA_minus_non_OA": f"{(oa_share - non_share):+.4f}",
            "absolute_diff_pp": f"{abs(oa_share - non_share)*100:.2f}",
        })
    with OUT_OA_VS_NON.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(oa_vs_non_rows[0].keys()))
        w.writeheader()
        for r in oa_vs_non_rows:
            w.writerow(r)
        f.write("\n")
        w2 = csv.writer(f)
        w2.writerow(["totals"])
        w2.writerow(["census_total", sum_census])
        w2.writerow(["OA_total", N_oa_total, f"{N_oa_total/sum_census:.4f}"])
        w2.writerow(["non_OA_total", N_non_total, f"{N_non_total/sum_census:.4f}"])
    print(f"  wrote {OUT_OA_VS_NON}")

    # =====================================================================
    # 5) TARGETED RECOVERY SCOPING
    # =====================================================================
    # Count NON-YIELDING works in comparative-critical strata. These are the
    # works a targeted manual/library recovery pass would entail.
    non_yielders_in_census: set = set()
    for r in census:
        key = (r["seed_id"], r["citing_openalex_id"])
        # A work is a non-yielder if it's NOT in the yielder pair set.
        if key not in yielder_pairs:
            non_yielders_in_census.add(key)

    def count_in(filter_fn) -> dict:
        """Return non-OA / OA / total counts for the filter."""
        nz = na = oa_n = non_n = 0
        for r in census:
            if not filter_fn(r):
                continue
            key = (r["seed_id"], r["citing_openalex_id"])
            nz += 1
            if key in non_yielders_in_census:
                na += 1
            if is_oa_bool(r["citing_is_oa"]):
                oa_n += 1
            else:
                non_n += 1
        return {"total": nz, "non_yielders": na,
                "OA": oa_n, "non_OA": non_n,
                "non_OA_non_yielders": sum(
                    1 for r in census
                    if filter_fn(r)
                    and (r["seed_id"], r["citing_openalex_id"]) in non_yielders_in_census
                    and not is_oa_bool(r["citing_is_oa"])
                )}

    targeted_rows = []
    # Commoner pre-1990
    f = lambda r: r["seed_id"] == "commoner_1971_closing_circle" and r["citing_decade"] in {"1970s", "1980s"}
    c = count_in(f)
    targeted_rows.append({"scope": "commoner_pre1990",
                          "description": "Commoner 1971: 1970s + 1980s citing works",
                          **c})
    # Schumacher pre-1990
    f = lambda r: r["seed_id"] == "schumacher_1974_small_is_beautiful" and r["citing_decade"] in {"1970s", "1980s"}
    c = count_in(f)
    targeted_rows.append({"scope": "schumacher_pre1990",
                          "description": "Schumacher 1974: 1970s + 1980s citing works",
                          **c})
    # Meadows pre-1990 (for comparison)
    f = lambda r: r["seed_id"] == "meadows_1972_limits_to_growth" and r["citing_decade"] in {"1970s", "1980s"}
    c = count_in(f)
    targeted_rows.append({"scope": "meadows_pre1990_for_context",
                          "description": "Meadows 1972: 1970s + 1980s citing works (for context)",
                          **c})
    # Books / book-chapters / dissertations / reports across all three seeds
    BOOKLIKE = {"book", "book-chapter", "book-section", "dissertation", "report"}
    f = lambda r: (r["citing_type"] in BOOKLIKE)
    c = count_in(f)
    targeted_rows.append({"scope": "books_chapters_dissertations_reports_all_seeds",
                          "description": "All seeds: book, book-chapter, book-section, dissertation, report",
                          **c})
    # Per-seed for that bookcase
    for seed in SEEDS_ACTIVE:
        f = lambda r, _s=seed: r["seed_id"] == _s and r["citing_type"] in BOOKLIKE
        c = count_in(f)
        targeted_rows.append({"scope": f"booklike_{seed.split('_')[0]}",
                              "description": f"{seed.split('_')[0].capitalize()}: book + book-chapter + book-section + dissertation + report",
                              **c})

    with OUT_TARGETED.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scope", "description", "total",
                                            "non_yielders", "OA", "non_OA",
                                            "non_OA_non_yielders"])
        w.writeheader()
        for r in targeted_rows:
            w.writerow(r)
    print(f"  wrote {OUT_TARGETED} ({len(targeted_rows)} scopes)")

    print(f"\nfinished_at={now_iso()}")


if __name__ == "__main__":
    main()
