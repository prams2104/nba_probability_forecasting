"""
Phase 3 — Core Evaluation Metrics.

Computes Brier Score, Log Loss, and Calibration Analysis for sportsbook
no-vig probabilities against actual NBA game outcomes.

Authors: Zitian & Yu-Jung (Phase 3)
"""

import numpy as np
import pandas as pd


def brier_score(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Brier Score: mean squared error between predicted probabilities and
    binary outcomes.

    BS = (1/N) * Σ (p_i - o_i)^2

    Range [0, 1]. Lower is better. 0 = perfect, 0.25 = random baseline.
    """
    return float(np.mean((probabilities - outcomes) ** 2))


def log_loss(probabilities: np.ndarray, outcomes: np.ndarray,
             eps: float = 1e-15) -> float:
    """
    Log Loss (cross-entropy): penalizes confident wrong predictions heavily.

    LL = -(1/N) * Σ [ y_i * log(p_i) + (1 - y_i) * log(1 - p_i) ]

    Probabilities are clipped to [eps, 1-eps] to avoid log(0).
    """
    p = np.clip(probabilities, eps, 1.0 - eps)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p)))


def calibration_bins(probabilities: np.ndarray, outcomes: np.ndarray,
                     n_bins: int = 10) -> pd.DataFrame:
    """
    Compute calibration (reliability diagram) data.

    Bins predicted probabilities into n_bins equal-width intervals.
    For each bin, computes:
      - bin_center: midpoint of the bin
      - mean_predicted: average predicted probability
      - mean_actual: observed win rate (fraction of outcomes = 1)
      - count: number of samples

    Perfect calibration: mean_predicted ≈ mean_actual for every bin.
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    indices = np.digitize(probabilities, bin_edges, right=False) - 1
    indices = np.clip(indices, 0, n_bins - 1)

    rows = []
    for i in range(n_bins):
        mask = indices == i
        center = (bin_edges[i] + bin_edges[i + 1]) / 2
        if mask.sum() == 0:
            rows.append({
                "bin_center": center,
                "mean_predicted": np.nan,
                "mean_actual": np.nan,
                "count": 0,
            })
        else:
            rows.append({
                "bin_center": center,
                "mean_predicted": float(probabilities[mask].mean()),
                "mean_actual": float(outcomes[mask].mean()),
                "count": int(mask.sum()),
            })

    return pd.DataFrame(rows)


def bootstrap_brier_ci(probabilities: np.ndarray, outcomes: np.ndarray,
                       n_bootstrap: int = 1000, ci: float = 0.95,
                       seed: int = 42) -> tuple[float, float]:
    """
    Bootstrap 95% confidence interval for Brier Score.

    Resamples with replacement n_bootstrap times and returns the
    (lower, upper) percentile bounds.
    """
    rng = np.random.default_rng(seed)
    n = len(probabilities)
    scores = np.empty(n_bootstrap)
    for k in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        scores[k] = np.mean((probabilities[idx] - outcomes[idx]) ** 2)
    alpha = 1.0 - ci
    lo, hi = np.percentile(scores, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def brier_by_bucket(probabilities: np.ndarray, outcomes: np.ndarray,
                    n_bins: int = 10) -> pd.DataFrame:
    """
    Compute Brier Score per probability bucket.

    Returns a DataFrame with columns: bin_center, brier, count.
    Shows where the sportsbook performs best/worst.
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    indices = np.digitize(probabilities, bin_edges, right=False) - 1
    indices = np.clip(indices, 0, n_bins - 1)

    rows = []
    for i in range(n_bins):
        mask = indices == i
        center = (bin_edges[i] + bin_edges[i + 1]) / 2
        if mask.sum() == 0:
            rows.append({"bin_center": center, "brier": np.nan, "count": 0})
        else:
            b = float(np.mean((probabilities[mask] - outcomes[mask]) ** 2))
            rows.append({"bin_center": center, "brier": b, "count": int(mask.sum())})

    return pd.DataFrame(rows)
