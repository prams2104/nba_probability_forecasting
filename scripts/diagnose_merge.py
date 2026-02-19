"""
Diagnostic script for merge_asof failure investigation.
Run BEFORE the temporal join to surface dtype mismatches, timestamp ranges, and overlap.
"""

import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def diagnose_merge_readiness(sb_df: pd.DataFrame, poly_df: pd.DataFrame) -> dict:
    """
    Diagnose both DataFrames for merge_asof compatibility.
    Returns a dict with all diagnostic info for logging/inspection.
    """
    diag = {}

    # --- Left (Sportsbook) ---
    diag["sb"] = {
        "rows": len(sb_df),
        "cols": list(sb_df.columns),
        "time_col": "target_snapshot_time",
        "by_col": "sportsbook_event_name",
        "time_dtype": str(sb_df["target_snapshot_time"].dtype),
        "time_min": sb_df["target_snapshot_time"].min(),
        "time_max": sb_df["target_snapshot_time"].max(),
        "time_tz": getattr(sb_df["target_snapshot_time"].dtype, "tz", None),
        "by_sample": sb_df["sportsbook_event_name"].head(3).tolist(),
        "by_nunique": sb_df["sportsbook_event_name"].nunique(),
        "by_has_whitespace": (sb_df["sportsbook_event_name"].astype(str).str.strip() != sb_df["sportsbook_event_name"].astype(str)).any(),
    }

    # --- Right (Polymarket, valid matches) ---
    if "timestamp" not in poly_df.columns or "matched_sb_event" not in poly_df.columns:
        diag["poly"] = {"error": "Missing timestamp or matched_sb_event columns"}
        return diag

    diag["poly"] = {
        "rows": len(poly_df),
        "time_col": "timestamp",
        "by_col": "matched_sb_event",
        "time_dtype": str(poly_df["timestamp"].dtype),
        "time_min": poly_df["timestamp"].min(),
        "time_max": poly_df["timestamp"].max(),
        "time_tz": getattr(poly_df["timestamp"].dtype, "tz", None),
        "by_sample": poly_df["matched_sb_event"].head(3).tolist(),
        "by_nunique": poly_df["matched_sb_event"].nunique(),
        "by_has_whitespace": (poly_df["matched_sb_event"].astype(str).str.strip() != poly_df["matched_sb_event"].astype(str)).any(),
    }

    # --- Overlap Analysis ---
    sb_min, sb_max = diag["sb"]["time_min"], diag["sb"]["time_max"]
    poly_min, poly_max = diag["poly"]["time_min"], diag["poly"]["time_max"]

    # For backward merge: we need poly.timestamp <= sb.target_snapshot_time
    # So we need at least one poly row with timestamp <= sb's max target
    overlap_lower = max(sb_min, poly_min)
    overlap_upper = min(sb_max, poly_max)
    temporal_overlap = overlap_lower <= overlap_upper

    diag["overlap"] = {
        "sb_range": (str(sb_min), str(sb_max)),
        "poly_range": (str(poly_min), str(poly_max)),
        "overlap_lower": str(overlap_lower),
        "overlap_upper": str(overlap_upper),
        "temporal_overlap_exists": temporal_overlap,
        "backward_merge_needs_poly_before_sb": "poly.timestamp <= sb.target_snapshot_time",
    }

    # --- Join Key Overlap ---
    sb_keys = set(sb_df["sportsbook_event_name"].astype(str).str.strip().unique())
    poly_keys = set(poly_df["matched_sb_event"].astype(str).str.strip().unique())
    key_intersection = sb_keys & poly_keys
    diag["keys"] = {
        "sb_unique_keys": len(sb_keys),
        "poly_unique_keys": len(poly_keys),
        "keys_in_both": len(key_intersection),
        "sample_intersection": list(key_intersection)[:5],
        "sb_only_sample": list(sb_keys - poly_keys)[:5],
        "poly_only_sample": list(poly_keys - sb_keys)[:5],
    }

    return diag


def print_diagnostic(diag: dict) -> None:
    """Pretty-print diagnostic output."""
    logger.info("=" * 70)
    logger.info("MERGE_ASOF DIAGNOSTIC REPORT")
    logger.info("=" * 70)

    # Sportsbook
    sb = diag.get("sb", {})
    if "error" in sb:
        logger.info(f"Sportsbook: {sb['error']}")
    else:
        logger.info("\n[LEFT] Sportsbook (sb_df)")
        logger.info(f"  Rows: {sb['rows']}")
        logger.info(f"  Time column: {sb['time_col']} | dtype: {sb['time_dtype']} | tz: {sb['time_tz']}")
        logger.info(f"  Time range: {sb['time_min']} -> {sb['time_max']}")
        logger.info(f"  By column: {sb['by_col']} | nunique: {sb['by_nunique']}")
        logger.info(f"  Sample by keys: {sb['by_sample']}")
        logger.info(f"  Has trailing whitespace in by: {sb['by_has_whitespace']}")

    # Polymarket
    poly = diag.get("poly", {})
    if "error" in poly:
        logger.info(f"Polymarket: {poly['error']}")
    else:
        logger.info("\n[RIGHT] Polymarket (valid_matches)")
        logger.info(f"  Rows: {poly['rows']}")
        logger.info(f"  Time column: {poly['time_col']} | dtype: {poly['time_dtype']} | tz: {poly['time_tz']}")
        logger.info(f"  Time range: {poly['time_min']} -> {poly['time_max']}")
        logger.info(f"  By column: {poly['by_col']} | nunique: {poly['by_nunique']}")
        logger.info(f"  Sample by keys: {poly['by_sample']}")
        logger.info(f"  Has trailing whitespace in by: {poly['by_has_whitespace']}")

    # Overlap
    ov = diag.get("overlap", {})
    logger.info("\n[TEMPORAL OVERLAP]")
    logger.info(f"  SB range:   {ov.get('sb_range')}")
    logger.info(f"  Poly range: {ov.get('poly_range')}")
    logger.info(f"  Overlap window: {ov.get('overlap_lower')} -> {ov.get('overlap_upper')}")
    logger.info(f"  Temporal overlap exists: {ov.get('temporal_overlap_exists')}")
    logger.info(f"  Backward merge requires: {ov.get('backward_merge_needs_poly_before_sb')}")

    # Keys
    keys = diag.get("keys", {})
    logger.info("\n[JOIN KEY OVERLAP (by=)]")
    logger.info(f"  SB unique keys:   {keys.get('sb_unique_keys')}")
    logger.info(f"  Poly unique keys: {keys.get('poly_unique_keys')}")
    logger.info(f"  Keys in BOTH:     {keys.get('keys_in_both')}")
    logger.info(f"  Sample intersection: {keys.get('sample_intersection')}")
    if keys.get("sb_only_sample"):
        logger.info(f"  Sample SB-only keys: {keys['sb_only_sample']}")
    if keys.get("poly_only_sample"):
        logger.info(f"  Sample Poly-only keys: {keys['poly_only_sample']}")

    logger.info("=" * 70)


if __name__ == "__main__":
    # Minimal run: load data and diagnose (requires pipeline to have run or manual load)
    from src.extraction.gamma_api import fetch_polymarket_history_paginated
    from src.matching.fuzzy_match import match_teams

    Path("data/processed").mkdir(parents=True, exist_ok=True)

    # Load sportsbook
    sb_path = "data/raw/nba_2008-2025.csv"
    if not Path(sb_path).exists():
        logger.error(f"Sportsbook file not found: {sb_path}")
        raise FileNotFoundError(sb_path)

    sb_df = pd.read_csv(sb_path)
    sb_df = sb_df.rename(columns={
        "date": "game_time",
        "home": "home_team",
        "away": "away_team",
        "moneyline_home": "home_odds",
        "moneyline_away": "away_odds",
    })
    sb_df["game_time"] = pd.to_datetime(sb_df["game_time"] + " 19:00:00").dt.tz_localize("UTC")
    sb_df["target_snapshot_time"] = sb_df["game_time"] - pd.Timedelta(hours=1)
    sb_df["sportsbook_event_name"] = sb_df["home_team"] + " vs " + sb_df["away_team"]
    sb_df = sb_df.sort_values("target_snapshot_time")

    # Load Polymarket and match
    poly_df = fetch_polymarket_history_paginated()
    sb_event_list = sb_df["sportsbook_event_name"].unique().tolist()
    poly_df[["matched_sb_event", "matching_score"]] = poly_df.apply(
        lambda row: pd.Series(match_teams(row["poly_event_name"], sb_event_list)), axis=1
    )
    valid_matches = poly_df[poly_df["matching_score"] >= 90].copy().sort_values("timestamp")

    diag = diagnose_merge_readiness(sb_df, valid_matches)
    print_diagnostic(diag)
