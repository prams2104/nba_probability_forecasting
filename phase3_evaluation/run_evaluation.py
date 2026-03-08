"""
Phase 3 — Main Evaluation Script.

Loads the Kaggle NBA dataset (~19,820 games), computes no-vig fair
probabilities, evaluates sportsbook accuracy, and generates all plots.

Usage:
    cd nba_probability_forecasting
    python -m phase3_evaluation.run_evaluation

Authors: Zitian & Yu-Jung (Phase 3)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.processing.quant_logic import apply_no_vig_probabilities
from phase3_evaluation.metrics import (
    brier_score,
    log_loss,
    calibration_bins,
    bootstrap_brier_ci,
)
from phase3_evaluation.plots import (
    plot_calibration_curve,
    plot_brier_by_bucket,
    plot_segmented_calibration,
    plot_confidence_tiers,
    plot_brier_by_season,
)

RAW_DATA = PROJECT_ROOT / "data" / "raw" / "nba_2008-2025.csv"


def load_and_prepare(filepath: Path = RAW_DATA) -> pd.DataFrame:
    """
    Load Kaggle data, filter to valid moneylines, apply no-vig conversion,
    and compute ground truth (home_won).
    """
    df = pd.read_csv(filepath)
    df = df.rename(columns={
        "home": "home_team",
        "away": "away_team",
        "moneyline_home": "home_odds",
        "moneyline_away": "away_odds",
    })

    # Keep only games with valid moneyline odds
    df = df.dropna(subset=["home_odds", "away_odds"]).copy()

    # Apply no-vig fair probability conversion (Phase 1 logic)
    df = apply_no_vig_probabilities(df)

    # Ground truth: 1 = home win, 0 = away win
    df["home_won"] = (df["score_home"] > df["score_away"]).astype(int)

    # Per-game metrics for aggregation
    eps = 1e-15
    df["brier_sportsbook"] = (df["fair_prob_home"] - df["home_won"]) ** 2
    p = df["fair_prob_home"].clip(lower=eps, upper=1.0 - eps)
    df["logloss_sportsbook"] = -(
        df["home_won"] * np.log(p) + (1 - df["home_won"]) * np.log(1 - p)
    )

    return df


def print_summary(df: pd.DataFrame) -> None:
    """Print a formatted evaluation summary to the terminal."""
    prob = df["fair_prob_home"].values
    outcome = df["home_won"].values
    n = len(df)

    bs = brier_score(prob, outcome)
    ll = log_loss(prob, outcome)
    ci_lo, ci_hi = bootstrap_brier_ci(prob, outcome)

    W = 72
    print()
    print("=" * W)
    print("  Phase 3 — Sportsbook Calibration Evaluation")
    print("=" * W)
    print(f"  Dataset : Kaggle NBA (nba_2008-2025.csv)")
    print(f"  Games   : {n:,}")
    print()
    print("  -- Overall Metrics (lower is better) " + "-" * (W - 39))
    print(f"  Brier Score : {bs:.4f}  [{ci_lo:.4f}, {ci_hi:.4f}]  (95% CI)")
    print(f"  Log Loss    : {ll:.4f}")
    print()

    # By game type
    if "regular" in df.columns and "playoffs" in df.columns:
        print("  -- By Game Type " + "-" * (W - 18))
        for label, mask in [("Regular Season", df["regular"] == True),
                            ("Playoffs", df["playoffs"] == True)]:
            seg = df[mask].dropna(subset=["fair_prob_home"])
            if len(seg) > 0:
                b = brier_score(seg["fair_prob_home"].values,
                                seg["home_won"].values)
                print(f"  {label:<18}: Brier = {b:.4f}  (N = {len(seg):,})")
        print()

    # By confidence tier
    if "fair_prob_away" in df.columns:
        _df = df.copy()
        _df["max_prob"] = _df[["fair_prob_home", "fair_prob_away"]].max(axis=1)
        print("  -- By Prediction Confidence " + "-" * (W - 30))
        for label, mask in [
            ("Strong fav  (>=65%)",    _df["max_prob"] >= 0.65),
            ("Moderate fav (55-65%)", (_df["max_prob"] >= 0.55) & (_df["max_prob"] < 0.65)),
            ("Near coin-flip (<55%)", _df["max_prob"] < 0.55),
        ]:
            seg = _df[mask].dropna(subset=["fair_prob_home"])
            if len(seg) > 0:
                b = brier_score(seg["fair_prob_home"].values,
                                seg["home_won"].values)
                print(f"  {label:<26}: Brier = {b:.4f}  (N = {len(seg):,})")
        print()

    # Calibration table
    print("  -- Calibration Analysis " + "-" * (W - 26))
    cal = calibration_bins(prob, outcome, n_bins=10)
    for _, row in cal.iterrows():
        if row["count"] > 0:
            diff = row["mean_actual"] - row["mean_predicted"]
            # diff < 0 → actual < predicted → sportsbook overestimates
            direction = "overestimates" if diff < 0 else "underestimates"
            print(f"  Bucket {row['bin_center']:.1f}: "
                  f"predicted={row['mean_predicted']:.3f}  "
                  f"actual={row['mean_actual']:.3f}  "
                  f"({direction} by {abs(diff):.3f})  "
                  f"N={int(row['count'])}")
    print()
    print("=" * W)
    print()


def main():
    print("Loading data...")
    df = load_and_prepare()
    print(f"Loaded {len(df):,} games with valid moneyline odds.")

    # Print metrics summary
    print_summary(df)

    # Generate all plots
    prob = df["fair_prob_home"].values
    outcome = df["home_won"].values

    print("Generating plots...")
    p1 = plot_calibration_curve(prob, outcome)
    print(f"  [1/5] {p1}")

    p2 = plot_brier_by_bucket(prob, outcome)
    print(f"  [2/5] {p2}")

    p3 = plot_segmented_calibration(df)
    print(f"  [3/5] {p3}")

    p4 = plot_confidence_tiers(df)
    print(f"  [4/5] {p4}")

    p5 = plot_brier_by_season(df)
    if p5:
        print(f"  [5/5] {p5}")
    else:
        print("  [5/5] Skipped (insufficient season data)")

    print("\nAll plots saved to phase3_evaluation/output/")


if __name__ == "__main__":
    main()
