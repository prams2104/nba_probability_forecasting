import pandas as pd
import numpy as np
import logging
from pathlib import Path

# --- STRICT ABSOLUTE IMPORTS ---
from src.extraction.gamma_api import fetch_polymarket_history_paginated
from src.matching.fuzzy_match import match_teams, audit_matches
from src.processing.quant_logic import apply_no_vig_probabilities
from scripts.diagnose_merge import diagnose_merge_readiness, print_diagnostic

# 1. Setup Professional Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("pipeline_execution.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# 3. Load & Prep Kaggle Sportsbook Data
def load_and_prep_sportsbook(filepath):
    logger.info(f"Loading sportsbook data from {filepath}...")
    df = pd.read_csv(filepath)

    # 1. Rename columns
    df = df.rename(columns={
        "date": "game_time",
        "home": "home_team",
        "away": "away_team",
        "moneyline_home": "home_odds",
        "moneyline_away": "away_odds",
    })

    # 2. Convert to datetime and EXPLICITLY set to UTC (naive YYYY-MM-DD -> UTC)
    df["game_time"] = pd.to_datetime(df["game_time"].astype(str) + " 19:00:00").dt.tz_localize("UTC")

    # 3. Target T-minus 1 hour
    df["target_snapshot_time"] = df["game_time"] - pd.Timedelta(hours=1)

    # 4. Standardize naming and normalize join keys (strip whitespace)
    df["sportsbook_event_name"] = (df["home_team"].astype(str) + " vs " + df["away_team"].astype(str)).str.strip()

    # 5. Game date for fallback merge
    df["game_date"] = df["game_time"].dt.date

    return df

# 4. Master Pipeline Execution
def main():
    logger.info("Initializing Step 1: Data Extraction & Matching Pipeline")
    
    # Setup directories
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    
    # Load Data
    poly_df = fetch_polymarket_history_paginated()
    sb_df = load_and_prep_sportsbook('data/raw/nba_2008-2025.csv')
    
    # Execute Fuzzy Matching
    logger.info("Executing RapidFuzz matching logic...")
    sb_event_list = sb_df['sportsbook_event_name'].unique().tolist()
    
    # Apply matching function row-by-row safely
    if not poly_df.empty:
        poly_df[['matched_sb_event', 'matching_score']] = poly_df.apply(
            lambda row: pd.Series(match_teams(row['poly_event_name'], sb_event_list)), 
            axis=1, 
            result_type='expand'
        )
    else:
        logger.warning("Polymarket DataFrame is empty! Creating dummy columns to prevent crash.")
        poly_df['matched_sb_event'] = None
        poly_df['matching_score'] = 0.0
    
    # Strict 90% Threshold Filter 
    logger.info("Applying strict 90% similarity threshold...")
    valid_matches = poly_df[poly_df['matching_score'] >= 90].copy()
    
    # Generate Audits
    logger.info("Generating manual review flags and 5% audit logs...")
    audit_matches(poly_df, score_col='matching_score') 
    
    # --- Normalize for merge ---
    valid_matches = valid_matches.copy()
    valid_matches["matched_sb_event"] = valid_matches["matched_sb_event"].astype(str).str.strip()
    valid_matches["game_date"] = valid_matches["timestamp"].dt.date
    valid_matches = valid_matches.sort_values("timestamp")

    sb_df = sb_df.sort_values("target_snapshot_time")

    # --- Ensure datetime64[ns, UTC] (merge_asof is dtype-sensitive) ---
    sb_df["target_snapshot_time"] = pd.to_datetime(sb_df["target_snapshot_time"], utc=True)
    valid_matches["timestamp"] = pd.to_datetime(valid_matches["timestamp"], utc=True)

    # --- Diagnostic: log dtypes, ranges, overlap before merge ---
    logger.info("Running merge_asof diagnostic...")
    diag = diagnose_merge_readiness(sb_df, valid_matches)
    print_diagnostic(diag)

    # --- Temporal Join (As-Of Merge) ---
    logger.info("Synchronizing temporal data (T-minus 1 hour)...")
    master_df = pd.merge_asof(
        sb_df,
        valid_matches,
        left_on="target_snapshot_time",
        right_on="timestamp",
        left_by="sportsbook_event_name",
        right_by="matched_sb_event",
        direction="backward",
    )

    # Drop rows where a match couldn't be synchronized temporally
    master_df = master_df.dropna(subset=["event_id"])

    # --- Fallback: if no temporal overlap, use game-date merge ---
    if len(master_df) == 0:
        logger.warning(
            "Temporal merge produced 0 rows. Falling back to game-date merge "
            "(match by date + event name)."
        )
        merged = sb_df.merge(
            valid_matches,
            left_on=["game_date", "sportsbook_event_name"],
            right_on=["game_date", "matched_sb_event"],
            how="inner",
            suffixes=("", "_poly"),
        )
        if merged.columns.duplicated().any():
            merged = merged.loc[:, ~merged.columns.duplicated()]
        master_df = merged.dropna(subset=["event_id"])

    logger.info("Applying No-Vig Fair Probability calculations...")
    master_df = apply_no_vig_probabilities(master_df)
    
    # Save final output
    output_path = 'data/processed/master_events.csv'
    master_df.to_csv(output_path, index=False)
    logger.info(f"Pipeline complete. Master dataset saved to {output_path} with {len(master_df)} synchronized events.")

if __name__ == "__main__":
    main()