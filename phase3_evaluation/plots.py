"""
Phase 3 — Visualization Functions.

Generates publication-quality plots for the ECE 143 presentation:
  1. Calibration Curve (Reliability Diagram)
  2. Brier Score by Probability Bucket

Authors: Zitian & Yu-Jung (Phase 3)
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import (
    brier_score,
    calibration_bins,
    brier_by_bucket,
    bootstrap_brier_ci,
)

# Consistent styling
plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.5,
    "grid.linestyle": "--",
})

OUTPUT_DIR = Path(__file__).parent / "output"


def _save(fig: plt.Figure, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ── 1. Calibration Curve (Reliability Diagram) ──────────────────────────

def plot_calibration_curve(prob: np.ndarray, outcome: np.ndarray,
                           n_bins: int = 10) -> Path:
    """
    Calibration Curve with confidence distribution histogram.

    Top panel: predicted probability (x) vs observed win rate (y).
               Points on the diagonal = perfect calibration.
    Bottom panel: histogram of predicted probabilities (confidence distribution).
    """
    cal = calibration_bins(prob, outcome, n_bins=n_bins)
    valid = cal.dropna(subset=["mean_predicted", "mean_actual"])

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8, 8), height_ratios=[1.5, 1], sharex=True,
    )

    # Top: calibration
    ax1.plot([0, 1], [0, 1], "k--", lw=1.5, label="Perfect calibration")
    ax1.scatter(
        valid["mean_predicted"], valid["mean_actual"],
        s=60, color="steelblue", edgecolors="white", lw=1.5, zorder=3,
    )
    ax1.plot(
        valid["mean_predicted"], valid["mean_actual"],
        color="steelblue", alpha=0.6, lw=1.5,
    )
    # Sample fraction bars
    total = valid["count"].sum()
    ax1.bar(
        valid["mean_predicted"], valid["count"] / total,
        width=0.9 / n_bins, alpha=0.25, color="steelblue", label="Sample fraction",
    )
    ax1.set_ylabel("Actual Home Win Rate")
    ax1.set_ylim(-0.05, 1.05)
    ax1.set_xlim(-0.05, 1.05)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.set_title(
        "Probability Calibration Curve (Reliability Diagram)\n"
        "Sportsbook No-Vig Probabilities vs Actual Home Win Rate"
    )

    # Bottom: histogram
    ax2.hist(prob, bins=n_bins, range=(0, 1), color="steelblue",
             alpha=0.7, edgecolor="white")
    ax2.set_xlabel("Predicted Probability (fair_prob_home)")
    ax2.set_ylabel("Count")
    ax2.set_title("Distribution of Predicted Confidence")

    plt.tight_layout()
    return _save(fig, "calibration_curve.png")


# ── 2. Brier Score by Probability Bucket ─────────────────────────────────

def plot_brier_by_bucket(prob: np.ndarray, outcome: np.ndarray,
                         n_bins: int = 10) -> Path:
    """
    Bar chart: Brier Score per probability bucket.

    Shows whether the sportsbook is more accurate for strong favorites
    or for close games. The 0.25 random-baseline line is shown for reference.
    """
    bb = brier_by_bucket(prob, outcome, n_bins=n_bins)
    valid = bb.dropna(subset=["brier"])

    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(
        valid["bin_center"], valid["brier"],
        width=0.08, color="steelblue", alpha=0.85, edgecolor="white",
        label="Brier Score per bucket",
    )
    # Annotate count on each bar
    for _, row in valid.iterrows():
        ax.text(
            row["bin_center"], row["brier"] + 0.005,
            f'n={int(row["count"])}', ha="center", va="bottom", fontsize=8,
        )

    ax.axhline(0.25, color="coral", ls="--", lw=1.8,
               label="Random baseline (0.25)")
    overall = brier_score(prob, outcome)
    ax.axhline(overall, color="green", ls="--", lw=1.5,
               label=f"Overall Brier: {overall:.4f}")

    ax.set_xlabel("Predicted Probability Bucket")
    ax.set_ylabel("Brier Score (lower is better)")
    ax.set_title("Brier Score by Probability Bucket\n"
                 "Sportsbook Accuracy Across Confidence Levels")
    ax.set_xlim(-0.05, 1.05)
    brier_max = valid["brier"].max()
    y_top = max(brier_max * 1.3, 0.30) if not np.isnan(brier_max) else 0.30
    ax.set_ylim(0, y_top)
    ax.legend(fontsize=9)

    plt.tight_layout()
    return _save(fig, "brier_by_bucket.png")


# ── 3. Segmented Calibration: Regular Season vs Playoffs ─────────────────

def plot_segmented_calibration(df: pd.DataFrame, n_bins: int = 10) -> Path:
    """Side-by-side calibration curves for Regular Season vs Playoffs."""
    segments = {
        "Regular Season": df[df["regular"] == True],
        "Playoffs": df[df["playoffs"] == True],
    }
    colors = {"Regular Season": "steelblue", "Playoffs": "coral"}

    # Warn if any games are flagged as both
    overlap = df[(df["regular"] == True) & (df["playoffs"] == True)]
    if not overlap.empty:
        print(f"WARNING: {len(overlap)} games flagged as both regular and playoffs")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    for ax, (label, seg) in zip(axes, segments.items()):
        seg = seg.dropna(subset=["fair_prob_home"])
        if seg.empty:
            ax.text(0.5, 0.5, f"No data ({label})", ha="center", va="center",
                    transform=ax.transAxes)
            ax.set_title(label)
            continue

        prob = seg["fair_prob_home"].values
        outcome = seg["home_won"].values
        cal = calibration_bins(prob, outcome, n_bins=n_bins)
        valid = cal.dropna(subset=["mean_predicted", "mean_actual"])
        b = brier_score(prob, outcome)

        ax.plot([0, 1], [0, 1], "k--", lw=1.5, label="Perfect calibration")
        ax.scatter(valid["mean_predicted"], valid["mean_actual"], s=70,
                   color=colors[label], edgecolors="white", lw=1.5, zorder=3)
        ax.plot(valid["mean_predicted"], valid["mean_actual"],
                color=colors[label], alpha=0.6, lw=1.5)
        ax.set_title(f"{label}\nN = {len(seg):,}  |  Brier = {b:.4f}")
        ax.set_xlabel("Predicted Probability")
        ax.set_ylabel("Actual Home Win Rate")
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=8)

    fig.suptitle("Calibration: Regular Season vs Playoffs",
                 fontsize=14, fontweight="bold")
    plt.tight_layout()
    return _save(fig, "segmented_by_game_type.png")


# ── 4. Calibration by Confidence Tier ────────────────────────────────────

def plot_confidence_tiers(df: pd.DataFrame, n_bins: int = 10) -> Path:
    """
    Overlaid calibration curves for three confidence tiers:
      - Strong fav (>=65%)
      - Moderate fav (55-65%)
      - Near coin-flip (<55%)
    """
    df = df.dropna(subset=["fair_prob_home", "fair_prob_away"]).copy()
    df["max_prob"] = df[["fair_prob_home", "fair_prob_away"]].max(axis=1)

    tiers = {
        "Strong fav (>=65%)":     df["max_prob"] >= 0.65,
        "Moderate fav (55-65%)":  (df["max_prob"] >= 0.55) & (df["max_prob"] < 0.65),
        "Near coin-flip (<55%)":  df["max_prob"] < 0.55,
    }
    tier_colors = ["#2196F3", "#4CAF50", "#FF9800"]

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(9, 10), height_ratios=[2, 1], sharex=True,
    )

    ax_top.plot([0, 1], [0, 1], "k--", lw=1.5, label="Perfect calibration")

    for (label, mask), color in zip(tiers.items(), tier_colors):
        seg = df[mask]
        if len(seg) < 20:
            continue
        prob = seg["fair_prob_home"].values
        outcome = seg["home_won"].values
        cal = calibration_bins(prob, outcome, n_bins=n_bins)
        valid = cal.dropna(subset=["mean_predicted", "mean_actual"])
        b = brier_score(prob, outcome)
        ax_top.plot(
            valid["mean_predicted"], valid["mean_actual"], "o-",
            color=color, lw=2, ms=7,
            label=f"{label}  (N={len(seg):,}, Brier={b:.4f})",
        )

    ax_top.set_ylabel("Actual Home Win Rate")
    ax_top.set_ylim(-0.05, 1.05)
    ax_top.set_xlim(-0.05, 1.05)
    ax_top.legend(fontsize=9, loc="upper left")
    ax_top.set_title("Calibration by Prediction Confidence Tier")

    colors_iter = iter(tier_colors)
    for label, mask in tiers.items():
        ax_bot.hist(df[mask]["fair_prob_home"].values, bins=n_bins,
                    range=(0, 1), alpha=0.5, label=label,
                    color=next(colors_iter), edgecolor="white")
    ax_bot.set_xlabel("Predicted Probability")
    ax_bot.set_ylabel("Count")
    ax_bot.legend(fontsize=8)

    plt.tight_layout()
    return _save(fig, "segmented_by_confidence.png")


# ── 5. Brier Score by Season ─────────────────────────────────────────────

def plot_brier_by_season(df: pd.DataFrame, n_bootstrap: int = 500) -> Path:
    """
    Bar chart of mean Brier Score per season with 95% bootstrap CI.

    Shows whether sportsbook accuracy changed over the 2008-2022 era.
    """
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
        return None

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(x, means, yerr=[lowers, uppers], capsize=4,
           color="steelblue", alpha=0.8, ecolor="darkblue",
           error_kw={"linewidth": 1.5})

    valid_df = df.dropna(subset=["fair_prob_home"])
    overall = brier_score(valid_df["fair_prob_home"].values,
                          valid_df["home_won"].values)
    ax.axhline(overall, color="coral", ls="--", lw=1.8,
               label=f"Overall mean: {overall:.4f}")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("NBA Season")
    ax.set_ylabel("Mean Brier Score")
    ax.set_title("Sportsbook Brier Score by Season\n(95% Bootstrap CI)")
    ax.legend(fontsize=10)
    ax.set_ylim(0, max(means) * 1.25)

    plt.tight_layout()
    return _save(fig, "brier_by_season.png")
