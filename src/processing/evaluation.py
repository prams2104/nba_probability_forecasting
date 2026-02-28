"""
ECE 143: Sportsbook Calibration & Evaluation (Sportsbook-Only).

This module evaluates the accuracy of traditional sportsbook predictions
(no-vig probabilities from moneyline odds) against actual NBA game outcomes.
It computes Brier Score, Log Loss, and a Probability Calibration Curve
(Reliability Diagram) with a confidence distribution histogram.

Data sources:
  - **Kaggle (recommended):** Loads `data/raw/nba_2008-2025.csv` directly.
    ~19,820 games have moneyline odds (seasons 2008–2022 fully, 2023 partial).
    Use this for statistically meaningful calibration analysis.
  - **master_events.csv (legacy):** Output of main.py Polymarket merge.
    512 games, but only 17 have moneylines (Kaggle drops them for 2023–2025).
    Kept for methodology/story; not recommended for evaluation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.processing.quant_logic import apply_no_vig_probabilities

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_KAGGLE_PATH = "data/raw/nba_2008-2025.csv"
DEFAULT_MASTER_PATH = "data/processed/master_events.csv"
DEFAULT_OUTPUT_PLOT = "data/processed/sportsbook_calibration.png"


def load_kaggle_for_evaluation(filepath: str = DEFAULT_KAGGLE_PATH) -> pd.DataFrame:
    """
    Load Kaggle NBA sportsbook data and prepare for evaluation.

    Filters to rows with valid moneyline odds, applies no-vig conversion,
    and returns a dataframe with fair_prob_home, score_home, score_away.
    Use this for the main evaluation (~19,820 games).
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Kaggle file not found: {filepath}")

    df = pd.read_csv(path)
    df = df.rename(columns={
        "home": "home_team",
        "away": "away_team",
        "moneyline_home": "home_odds",
        "moneyline_away": "away_odds",
    })

    mask = df["home_odds"].notna() & df["away_odds"].notna()
    df = df[mask].copy()
    if df.empty:
        raise ValueError("No rows with valid moneyline odds in Kaggle file.")

    df = apply_no_vig_probabilities(df)
    return df


def load_master_events(filepath: str = DEFAULT_MASTER_PATH) -> pd.DataFrame:
    """
    Load the master events dataset produced by the main pipeline.

    Expected columns include: home_team, away_team, score_home, score_away,
    fair_prob_home, fair_prob_away, game_time, etc.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Master events file not found: {filepath}")
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("Master events file is empty.")
    return df


def compute_ground_truth(df: pd.DataFrame) -> pd.Series:
    """
    Determine the binary ground truth for each game: did the home team win?

    Returns a Series of 1 (home win) or 0 (away win). Used as the target
    for Brier Score and Log Loss, and for the calibration curve.
    """
    return (df["score_home"] > df["score_away"]).astype(int)


def brier_score(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Brier Score (Brier 1950): mean squared error between predicted
    probabilities and binary outcomes.

    Formula: (1/n) * sum((p_i - y_i)^2), where p_i = P(home win), y_i in {0,1}.

    Range: [0, 1]. Lower is better. 0 = perfect predictions.
    """
    return np.mean((probabilities - outcomes) ** 2)


def log_loss(probabilities: np.ndarray, outcomes: np.ndarray, eps: float = 1e-15) -> float:
    """
    Log Loss (cross-entropy): penalizes confident wrong predictions.

    Formula: -(1/n) * sum( y_i*log(p_i) + (1-y_i)*log(1-p_i) ).

    We clip probabilities to [eps, 1-eps] to avoid log(0). Lower is better.
    """
    p = np.clip(probabilities, eps, 1.0 - eps)
    return -np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p))


def reliability_diagram_data(
    probabilities: np.ndarray, outcomes: np.ndarray, n_bins: int = 10
) -> tuple:
    """
    Compute data for a Reliability Diagram (Calibration Curve).

    Bins predicted probabilities into n_bins. For each bin we compute:
    - mean_predicted: average predicted probability in the bin
    - mean_actual: fraction of games in the bin where home actually won (observed frequency)
    - count: number of samples in the bin

    Perfect calibration: mean_predicted ≈ mean_actual (points on the diagonal).
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(probabilities, bin_edges, right=False) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    mean_predicted = []
    mean_actual = []
    counts = []

    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() == 0:
            mean_predicted.append(np.nan)
            mean_actual.append(np.nan)
            counts.append(0)
        else:
            mean_predicted.append(probabilities[mask].mean())
            mean_actual.append(outcomes[mask].mean())
            counts.append(mask.sum())

    return (
        np.array(mean_predicted),
        np.array(mean_actual),
        np.array(counts),
        bin_edges,
    )


def evaluate_sportsbook(
    source: str = "kaggle",
    filepath: Optional[str] = None,
) -> pd.DataFrame:
    """
    Full sportsbook-only evaluation pipeline.

    1. Load data (Kaggle raw or master_events.csv).
    2. Compute ground truth (home_won).
    3. Compute Brier Score and Log Loss for fair_prob_home.
    4. Build calibration curve data (no plotting here).

    Args:
        source: "kaggle" (default) for ~19,820 games from Kaggle raw;
                "master_events" for 17 games from Polymarket merge output.
        filepath: Override path; if None, uses default for the chosen source.

    Returns the dataframe with added columns: home_won, brier_sportsbook, logloss_sportsbook.
    """
    if source == "kaggle":
        path = filepath or DEFAULT_KAGGLE_PATH
        df = load_kaggle_for_evaluation(path)
        df.attrs["_eval_source"] = "kaggle"
    else:
        path = filepath or DEFAULT_MASTER_PATH
        df = load_master_events(path)
        df = df.dropna(subset=["fair_prob_home"]).copy()
        df.attrs["_eval_source"] = "master_events"

    if df.empty:
        raise ValueError("No rows with valid fair_prob_home after loading.")
    if "fair_prob_home" not in df.columns:
        raise ValueError("Column 'fair_prob_home' not found. Ensure no-vig logic was applied.")

    # Ground truth: 1 if home won, 0 if away won
    df["home_won"] = compute_ground_truth(df)

    # Brier Score per game (for reporting we use the mean)
    df["brier_sportsbook"] = (df["fair_prob_home"] - df["home_won"]) ** 2

    # Log Loss per game (clip to avoid log(0))
    eps = 1e-15
    p = df["fair_prob_home"].clip(lower=eps, upper=1.0 - eps)
    df["logloss_sportsbook"] = -(
        df["home_won"] * np.log(p) + (1 - df["home_won"]) * np.log(1 - p)
    )

    return df


def plot_calibration_curve(
    df: pd.DataFrame,
    n_bins: int = 10,
    output_path: str = DEFAULT_OUTPUT_PLOT,
) -> None:
    """
    Generate a professional Probability Calibration Curve (Reliability Diagram)
    with a histogram subplot showing the distribution of predicted confidence.

    Top: Calibration curve — mean predicted probability (x) vs mean actual outcome (y).
         Perfect calibration is the diagonal. Bars show fraction of samples per bin.
    Bottom: Histogram of fair_prob_home (confidence distribution).
    """
    prob = df["fair_prob_home"].values
    outcome = df["home_won"].values

    mean_pred, mean_actual, counts, bin_edges = reliability_diagram_data(
        prob, outcome, n_bins=n_bins
    )

    # Mask NaN bins for plotting
    valid = ~np.isnan(mean_pred) & ~np.isnan(mean_actual)
    x_plot = mean_pred[valid]
    y_plot = mean_actual[valid]
    c_plot = counts[valid]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), height_ratios=[1.5, 1], sharex=True)

    # --- Top: Calibration curve ---
    ax1.plot([0, 1], [0, 1], "k--", label="Perfect calibration", linewidth=1.5)
    ax1.scatter(x_plot, y_plot, s=60, color="steelblue", edgecolors="white", linewidths=1.5, zorder=3)
    ax1.bar(
        x_plot,
        c_plot / c_plot.sum(),
        width=0.08,
        alpha=0.3,
        color="steelblue",
        label="Sample fraction per bin",
    )
    ax1.set_ylabel("Mean actual outcome (home win rate)", fontsize=11)
    ax1.set_ylim(-0.05, 1.05)
    ax1.set_xlim(-0.05, 1.05)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.7)
    ax1.set_title("Probability Calibration Curve (Reliability Diagram)\nSportsbook No-Vig Probabilities vs Actual Home Win Rate", fontsize=12)

    # --- Bottom: Histogram of predicted probabilities ---
    ax2.hist(
        prob,
        bins=n_bins,
        range=(0, 1),
        color="steelblue",
        alpha=0.7,
        edgecolor="white",
    )
    ax2.set_xlabel("Predicted probability (fair_prob_home)", fontsize=11)
    ax2.set_ylabel("Count", fontsize=11)
    ax2.set_title("Distribution of predicted confidence", fontsize=11)
    ax2.grid(True, linestyle="--", alpha=0.7, axis="y")

    plt.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Calibration plot saved to %s", output_path)


def print_summary(df: pd.DataFrame) -> None:
    """Print a clean, formatted terminal summary of evaluation metrics."""
    n = len(df)
    brier = df["brier_sportsbook"].mean()
    logloss = df["logloss_sportsbook"].mean()
    source = df.attrs.get("_eval_source", "unknown")
    dataset_name = (
        "Kaggle raw (nba_2008-2025.csv)" if source == "kaggle" else "master_events.csv"
    )

    print()
    print("=" * 70)
    print("  ECE 143 — Sportsbook Calibration & Evaluation (Sportsbook-Only)")
    print("=" * 70)
    print()
    print("  Dataset: {} (no-vig probabilities from moneyline odds)".format(dataset_name))
    print("  Sample size: {} NBA games".format(n))
    print()
    print("  --- Metrics (lower is better) ---")
    print("  Brier Score:  {:.4f}".format(brier))
    print("  Log Loss:     {:.4f}".format(logloss))
    print()
    print("  Output: sportsbook_calibration.png (calibration curve + histogram)")
    print("=" * 70)
    print()


def run_evaluation(
    source: str = "kaggle",
    filepath: Optional[str] = None,
    output_plot: str = DEFAULT_OUTPUT_PLOT,
    n_bins: int = 10,
) -> pd.DataFrame:
    """
    Run the full sportsbook-only evaluation: load data, compute metrics,
    plot calibration curve, and print summary.

    Args:
        source: "kaggle" (default) or "master_events".
        filepath: Override data path; uses default for source if None.
        output_plot: Path for calibration plot.
        n_bins: Number of bins for reliability diagram.

    Returns the evaluation dataframe (with home_won, brier_sportsbook, logloss_sportsbook).
    """
    df = evaluate_sportsbook(source=source, filepath=filepath)
    plot_calibration_curve(df, n_bins=n_bins, output_path=output_plot)
    print_summary(df)
    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    run_evaluation(source="kaggle")
