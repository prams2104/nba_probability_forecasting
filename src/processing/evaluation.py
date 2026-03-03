"""
ECE 143: Sportsbook Calibration & Evaluation (Sportsbook-Only).

This module evaluates the accuracy of traditional sportsbook predictions
(no-vig probabilities from moneyline odds) against actual NBA game outcomes.
It computes Brier Score, Log Loss, and a suite of Probability Calibration
Curves (Reliability Diagrams) with confidence intervals and segment breakdowns.

Data sources:
  - **Kaggle (recommended):** Loads `data/raw/nba_2008-2025.csv` directly.
    ~19,820 games have moneyline odds (seasons 2008–2022 fully, 2023 partial).
    Use this for statistically meaningful calibration analysis.
  - **master_events.csv (legacy):** Output of main.py Polymarket merge.
    512 games, but only 17 have moneylines (Kaggle drops them for 2023–2025).
    Kept for methodology/story; not recommended for evaluation.

Phase 3 additions (Zitian & Yu-Jung):
  - Bootstrap 95% CI on Brier Score
  - Segmented calibration: Regular Season vs Playoffs
  - Segmented calibration: Confidence tiers (strong / moderate / coin-flip)
  - Brier Score temporal trend by season
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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_kaggle_for_evaluation(filepath: str = DEFAULT_KAGGLE_PATH) -> pd.DataFrame:
    """
    Load Kaggle NBA sportsbook data and prepare for evaluation.

    Filters to rows with valid moneyline odds, applies no-vig conversion,
    and returns a dataframe with fair_prob_home, score_home, score_away.
    Use this for the main evaluation (~19,820 games).

    Preserves 'season', 'regular', and 'playoffs' columns for segmentation.
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


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

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
    return float(np.mean((probabilities - outcomes) ** 2))


def log_loss(probabilities: np.ndarray, outcomes: np.ndarray, eps: float = 1e-15) -> float:
    """
    Log Loss (cross-entropy): penalizes confident wrong predictions.

    Formula: -(1/n) * sum( y_i*log(p_i) + (1-y_i)*log(1-p_i) ).

    We clip probabilities to [eps, 1-eps] to avoid log(0). Lower is better.
    """
    p = np.clip(probabilities, eps, 1.0 - eps)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p)))


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


def bootstrap_brier_ci(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """
    Bootstrap confidence interval for the mean Brier Score.

    Resamples (with replacement) n_bootstrap times and computes Brier Score
    for each resample. Returns the lower and upper percentile bounds.

    Args:
        probabilities: Predicted home-win probabilities.
        outcomes: Binary outcomes (1 = home win, 0 = away win).
        n_bootstrap: Number of bootstrap iterations (default 1000).
        ci: Confidence level, e.g. 0.95 for 95% CI.
        seed: Random seed for reproducibility.

    Returns:
        (lower_bound, upper_bound) of the bootstrap CI.
    """
    rng = np.random.default_rng(seed)
    n = len(probabilities)
    samples = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        samples[i] = np.mean((probabilities[idx] - outcomes[idx]) ** 2)
    alpha = 1.0 - ci
    lo, hi = np.percentile(samples, [100.0 * alpha / 2, 100.0 * (1.0 - alpha / 2)])
    return float(lo), float(hi)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _save_fig(fig: plt.Figure, output_path: str) -> None:
    """Save a matplotlib figure and close it."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved to %s", output_path)


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

    mean_pred, mean_actual, counts, _ = reliability_diagram_data(
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
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Calibration plot saved to %s", output_path)


def plot_segmented_calibration(
    df: pd.DataFrame,
    output_path: str,
    n_bins: int = 10,
) -> None:
    """
    Side-by-side calibration curves for Regular Season vs Playoffs.

    Requires 'regular' and 'playoffs' boolean columns (present in Kaggle raw).
    Shows how well the sportsbook calibrates for each game type, including
    per-segment Brier Scores and sample sizes.
    """
    if "regular" not in df.columns or "playoffs" not in df.columns:
        logger.warning("'regular'/'playoffs' columns not found; skipping segmented calibration.")
        return

    segments = {
        "Regular Season": df[df["regular"] == True].dropna(subset=["fair_prob_home"]).copy(),
        "Playoffs":       df[df["playoffs"] == True].dropna(subset=["fair_prob_home"]).copy(),
    }
    colors = {"Regular Season": "steelblue", "Playoffs": "coral"}

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for ax, (label, seg) in zip(axes, segments.items()):
        color = colors[label]
        if seg.empty:
            ax.text(0.5, 0.5, f"No data\n({label})", ha="center", va="center",
                    transform=ax.transAxes, fontsize=12)
            ax.set_title(label, fontsize=12)
            continue

        prob = seg["fair_prob_home"].values
        outcome = seg["home_won"].values
        mean_pred, mean_actual, _, _ = reliability_diagram_data(prob, outcome, n_bins=n_bins)
        valid = ~np.isnan(mean_pred) & ~np.isnan(mean_actual)
        b = brier_score(prob, outcome)

        ax.plot([0, 1], [0, 1], "k--", linewidth=1.5, label="Perfect calibration")
        ax.scatter(mean_pred[valid], mean_actual[valid], s=70, color=color,
                   edgecolors="white", linewidths=1.5, zorder=3)
        ax.plot(mean_pred[valid], mean_actual[valid], color=color, alpha=0.6, linewidth=1.5)
        ax.set_title(f"{label}\nN = {len(seg):,}  |  Brier = {b:.4f}", fontsize=12)
        ax.set_xlabel("Predicted probability (fair_prob_home)", fontsize=10)
        ax.set_ylabel("Actual home win rate", fontsize=10)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.7)

    fig.suptitle("Calibration Curve: Regular Season vs Playoffs", fontsize=14, fontweight="bold")
    plt.tight_layout()
    _save_fig(fig, output_path)


def plot_favorite_calibration(
    df: pd.DataFrame,
    output_path: str,
    n_bins: int = 10,
) -> None:
    """
    Overlaid calibration curves for three prediction-confidence tiers.

    Tiers are defined by max(fair_prob_home, fair_prob_away) — i.e. how
    confident the sportsbook is about the outcome, regardless of direction:
      - Strong favorite  : max prob >= 0.65
      - Moderate favorite: 0.55 <= max prob < 0.65
      - Near coin-flip   : max prob < 0.55

    Shows whether the sportsbook is better calibrated for clear favorites
    than for close games.
    """
    if "fair_prob_home" not in df.columns or "fair_prob_away" not in df.columns:
        logger.warning("fair_prob columns missing; skipping favorite calibration.")
        return

    df = df.dropna(subset=["fair_prob_home", "fair_prob_away"]).copy()
    df["_max_prob"] = df[["fair_prob_home", "fair_prob_away"]].max(axis=1)

    tiers = {
        "Strong fav (≥65%)":     df["_max_prob"] >= 0.65,
        "Moderate fav (55–65%)": (df["_max_prob"] >= 0.55) & (df["_max_prob"] < 0.65),
        "Near coin-flip (<55%)": df["_max_prob"] < 0.55,
    }
    tier_colors = ["#2196F3", "#4CAF50", "#FF9800"]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(9, 10), height_ratios=[2, 1], sharex=True
    )

    ax_top.plot([0, 1], [0, 1], "k--", linewidth=1.5, label="Perfect calibration", zorder=0)

    for (label, mask), color in zip(tiers.items(), tier_colors):
        seg = df[mask]
        if len(seg) < 20:
            continue
        prob = seg["fair_prob_home"].values
        outcome = seg["home_won"].values
        mean_pred, mean_actual, _, _ = reliability_diagram_data(prob, outcome, n_bins=n_bins)
        valid = ~np.isnan(mean_pred) & ~np.isnan(mean_actual)
        b = brier_score(prob, outcome)
        ax_top.plot(
            mean_pred[valid], mean_actual[valid], "o-", color=color,
            linewidth=2, markersize=7,
            label=f"{label}  (N={len(seg):,}, Brier={b:.4f})",
        )

    ax_top.set_ylabel("Actual home win rate", fontsize=11)
    ax_top.set_ylim(-0.05, 1.05)
    ax_top.set_xlim(-0.05, 1.05)
    ax_top.legend(fontsize=9, loc="upper left")
    ax_top.grid(True, linestyle="--", alpha=0.7)
    ax_top.set_title(
        "Calibration by Prediction Confidence Tier\nSportsbook No-Vig Probabilities", fontsize=13
    )

    # Bottom histogram: distribution per tier
    colors_iter = iter(tier_colors)
    for label, mask in tiers.items():
        ax_bot.hist(
            df[mask]["fair_prob_home"].values, bins=n_bins, range=(0, 1),
            alpha=0.5, label=label, color=next(colors_iter), edgecolor="white",
        )
    ax_bot.set_xlabel("Predicted probability (fair_prob_home)", fontsize=11)
    ax_bot.set_ylabel("Count", fontsize=11)
    ax_bot.legend(fontsize=8)
    ax_bot.grid(True, linestyle="--", alpha=0.7, axis="y")

    plt.tight_layout()
    _save_fig(fig, output_path)


def plot_brier_by_season(
    df: pd.DataFrame,
    output_path: str,
    n_bootstrap: int = 500,
) -> None:
    """
    Bar chart of mean Brier Score per season with 95% bootstrap CI error bars.

    Reveals whether sportsbook calibration improved, degraded, or remained
    stable across the 2008–2022 era. The overall mean is shown as a
    reference line.
    """
    if "season" not in df.columns or "fair_prob_home" not in df.columns:
        logger.warning("'season' column not found; skipping Brier-by-season plot.")
        return

    df = df.dropna(subset=["fair_prob_home"]).copy()
    seasons = sorted(df["season"].unique())

    means, lowers, uppers, labels = [], [], [], []
    for s in seasons:
        seg = df[df["season"] == s]
        if len(seg) < 10:
            continue
        prob = seg["fair_prob_home"].values
        out = seg["home_won"].values
        m = brier_score(prob, out)
        lo, hi = bootstrap_brier_ci(prob, out, n_bootstrap=n_bootstrap)
        means.append(m)
        lowers.append(m - lo)
        uppers.append(hi - m)
        labels.append(str(int(s)))

    if not means:
        logger.warning("No seasons with sufficient data; skipping Brier-by-season plot.")
        return

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(
        x, means, yerr=[lowers, uppers], capsize=4,
        color="steelblue", alpha=0.8, ecolor="darkblue",
        error_kw={"linewidth": 1.5}, label="Season Brier Score",
    )

    overall_mean = float(df["brier_sportsbook"].mean())
    ax.axhline(
        overall_mean, color="coral", linestyle="--", linewidth=1.8,
        label=f"Overall mean Brier: {overall_mean:.4f}",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("NBA Season (year season ended)", fontsize=11)
    ax.set_ylabel("Mean Brier Score", fontsize=11)
    ax.set_title(
        "Sportsbook Brier Score by Season\n(95% bootstrap CI error bars)", fontsize=13
    )
    ax.legend(fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    ax.set_ylim(0, max(means) * 1.25)

    plt.tight_layout()
    _save_fig(fig, output_path)


# ---------------------------------------------------------------------------
# Summary & entry point
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    """Print a formatted terminal summary of all evaluation metrics."""
    prob = df["fair_prob_home"].values
    outcome = df["home_won"].values
    n = len(df)
    b_mean = float(df["brier_sportsbook"].mean())
    ll_mean = float(df["logloss_sportsbook"].mean())
    source = df.attrs.get("_eval_source", "unknown")
    dataset_name = (
        "Kaggle raw (nba_2008-2025.csv)" if source == "kaggle" else "master_events.csv"
    )

    ci_lo, ci_hi = bootstrap_brier_ci(prob, outcome)

    W = 72
    print()
    print("=" * W)
    print("  ECE 143 — Sportsbook Calibration & Evaluation (Sportsbook-Only)")
    print("=" * W)
    print()
    print(f"  Dataset : {dataset_name}")
    print(f"  Games   : {n:,}")
    print()
    print("  ── Overall Metrics (lower is better) " + "─" * (W - 38))
    print(f"  Brier Score : {b_mean:.4f}  [{ci_lo:.4f}, {ci_hi:.4f}]  (95% bootstrap CI)")
    print(f"  Log Loss    : {ll_mean:.4f}")
    print()

    # Segmented by game type
    if "regular" in df.columns and "playoffs" in df.columns:
        print("  ── By Game Type " + "─" * (W - 17))
        for label, mask in [
            ("Regular Season", df["regular"] == True),
            ("Playoffs", df["playoffs"] == True),
        ]:
            seg = df[mask].dropna(subset=["fair_prob_home"])
            if len(seg) == 0:
                continue
            b = seg["brier_sportsbook"].mean()
            print(f"  {label:<18}: Brier = {b:.4f}  (N = {len(seg):,})")
        print()

    # Segmented by prediction confidence
    if "fair_prob_away" in df.columns:
        _df = df.copy()
        _df["_max_prob"] = _df[["fair_prob_home", "fair_prob_away"]].max(axis=1)
        print("  ── By Prediction Confidence " + "─" * (W - 29))
        tiers = [
            ("Strong fav  (≥65%)",    _df["_max_prob"] >= 0.65),
            ("Moderate fav (55–65%)", (_df["_max_prob"] >= 0.55) & (_df["_max_prob"] < 0.65)),
            ("Near coin-flip (<55%)", _df["_max_prob"] < 0.55),
        ]
        for label, mask in tiers:
            seg = _df[mask].dropna(subset=["fair_prob_home"])
            if len(seg) == 0:
                continue
            b = seg["brier_sportsbook"].mean()
            print(f"  {label:<26}: Brier = {b:.4f}  (N = {len(seg):,})")
        print()

    print("  ── Output Files " + "─" * (W - 17))
    print("  sportsbook_calibration.png     (overall calibration curve)")
    if source == "kaggle":
        print("  segmented_by_game_type.png     (Regular Season vs Playoffs)")
        print("  segmented_by_favorite.png      (confidence tiers)")
        print("  brier_by_season.png            (seasonal Brier trend)")
    print("=" * W)
    print()


def run_evaluation(
    source: str = "kaggle",
    filepath: Optional[str] = None,
    output_plot: str = DEFAULT_OUTPUT_PLOT,
    n_bins: int = 10,
) -> pd.DataFrame:
    """
    Run the full sportsbook-only evaluation: load data, compute metrics,
    generate all calibration plots, and print summary.

    For Kaggle source, produces four plots:
      1. sportsbook_calibration.png     — overall reliability diagram
      2. segmented_by_game_type.png     — Regular Season vs Playoffs
      3. segmented_by_favorite.png      — confidence tiers
      4. brier_by_season.png            — temporal Brier trend

    Args:
        source: "kaggle" (default) or "master_events".
        filepath: Override data path; uses default for source if None.
        output_plot: Path for the overall calibration plot.
        n_bins: Number of bins for reliability diagrams.

    Returns the evaluation dataframe (with home_won, brier_sportsbook, logloss_sportsbook).
    """
    df = evaluate_sportsbook(source=source, filepath=filepath)
    plot_calibration_curve(df, n_bins=n_bins, output_path=output_plot)

    if source == "kaggle":
        out_dir = str(Path(output_plot).parent)
        plot_segmented_calibration(
            df, output_path=f"{out_dir}/segmented_by_game_type.png", n_bins=n_bins
        )
        plot_favorite_calibration(
            df, output_path=f"{out_dir}/segmented_by_favorite.png", n_bins=n_bins
        )
        plot_brier_by_season(df, output_path=f"{out_dir}/brier_by_season.png")

    print_summary(df)
    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    run_evaluation(source="kaggle")
