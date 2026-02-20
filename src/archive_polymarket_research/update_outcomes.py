"""
Update prospective predictions with actual game outcomes.

After games complete, use this script to:
1. Load predictions from prospective_predictions.csv
2. Get actual outcomes (from NBA API or manual entry)
3. Update predictions file with results
4. Mark games as 'completed'
"""

import pandas as pd
import requests
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_game_outcome_from_nba_api(home_team: str, away_team: str, game_date: str) -> dict:
    """
    Get game outcome from NBA API.
    
    Options:
    1. NBA API (https://www.balldontlie.io/) - Free, no API key needed
    2. SportsDataIO NBA API - Requires API key
    3. Manual entry
    
    Returns dict with 'home_score', 'away_score', 'home_won'
    """
    # Option 1: Ball Don't Lie API (free, no key needed)
    try:
        # Convert team abbreviations to full names if needed
        # This is simplified - you may need team name mapping
        
        # Get games for date
        url = "https://www.balldontlie.io/api/v1/games"
        params = {
            "dates[]": game_date,  # Format: YYYY-MM-DD
            "per_page": 100
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        games = data.get('data', [])
        
        # Find matching game
        for game in games:
            # Match by team names (you'll need to map abbreviations)
            # This is simplified - enhance with your team mapping
            if (game['home_team']['abbreviation'].lower() == home_team.lower() or
                game['visitor_team']['abbreviation'].lower() == away_team.lower()):
                
                if game['status'] == 'Final':
                    return {
                        'home_score': game['home_team_score'],
                        'away_score': game['visitor_team_score'],
                        'home_won': 1 if game['home_team_score'] > game['visitor_team_score'] else 0,
                        'status': 'completed'
                    }
        
        return {'status': 'not_found'}
        
    except Exception as e:
        logger.error(f"Error fetching from NBA API: {e}")
        return {'status': 'error'}


def update_outcomes_manual(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Interactive function to manually update outcomes.
    
    Shows games that need outcomes and prompts for input.
    """
    pending = predictions_df[predictions_df['status'] == 'pending'].copy()
    
    if pending.empty:
        logger.info("No pending games to update.")
        return predictions_df
    
    logger.info(f"\nFound {len(pending)} games needing outcomes:")
    
    for idx, row in pending.iterrows():
        print(f"\n{'='*70}")
        print(f"Game: {row['away_team']} @ {row['home_team']}")
        print(f"Date: {row['game_date']}")
        print(f"Event ID: {row['event_id']}")
        
        # Try to get from API first
        outcome = get_game_outcome_from_nba_api(
            row['home_team'],
            row['away_team'],
            str(row['game_date'])[:10] if pd.notna(row['game_date']) else None
        )
        
        if outcome.get('status') == 'completed':
            home_score = outcome['home_score']
            away_score = outcome['away_score']
            home_won = outcome['home_won']
            logger.info(f"✓ Found outcome: {away_score} - {home_score} (Home {'won' if home_won else 'lost'})")
        else:
            # Manual entry
            print("\nEnter game outcome:")
            try:
                home_score = int(input("Home team score: "))
                away_score = int(input("Away team score: "))
                home_won = 1 if home_score > away_score else 0
            except ValueError:
                logger.warning("Invalid input. Skipping this game.")
                continue
        
        # Update dataframe
        predictions_df.loc[idx, 'home_score'] = home_score
        predictions_df.loc[idx, 'away_score'] = away_score
        predictions_df.loc[idx, 'home_won'] = home_won
        predictions_df.loc[idx, 'status'] = 'completed'
        predictions_df.loc[idx, 'outcome_updated_at'] = datetime.now().isoformat()
    
    return predictions_df


def update_outcomes_batch(predictions_file: str = 'data/processed/prospective_predictions.csv'):
    """
    Batch update outcomes for all pending games.
    """
    logger.info("Loading predictions...")
    df = pd.read_csv(predictions_file)
    
    if df.empty:
        logger.error("No predictions found.")
        return
    
    pending = df[df['status'] == 'pending'].copy()
    logger.info(f"Found {len(pending)} pending games")
    
    if pending.empty:
        logger.info("All games already completed.")
        return df
    
    # Try to get outcomes from API for all pending games
    updated_count = 0
    
    for idx, row in pending.iterrows():
        if pd.isna(row['game_date']):
            continue
        
        game_date_str = str(row['game_date'])[:10]  # YYYY-MM-DD
        
        outcome = get_game_outcome_from_nba_api(
            row['home_team'],
            row['away_team'],
            game_date_str
        )
        
        if outcome.get('status') == 'completed':
            df.loc[idx, 'home_score'] = outcome['home_score']
            df.loc[idx, 'away_score'] = outcome['away_score']
            df.loc[idx, 'home_won'] = outcome['home_won']
            df.loc[idx, 'status'] = 'completed'
            df.loc[idx, 'outcome_updated_at'] = datetime.now().isoformat()
            updated_count += 1
            logger.info(f"✓ Updated: {row['away_team']} @ {row['home_team']}")
    
    logger.info(f"\nUpdated {updated_count}/{len(pending)} games from API")
    
    # Save updated predictions
    df.to_csv(predictions_file, index=False)
    logger.info(f"Saved updated predictions to {predictions_file}")
    
    # Show remaining pending
    remaining = df[df['status'] == 'pending']
    if len(remaining) > 0:
        logger.info(f"\n{len(remaining)} games still pending:")
        logger.info("Run with --interactive flag to manually update remaining games")
    
    return df


if __name__ == "__main__":
    import sys
    
    if '--interactive' in sys.argv:
        # Interactive mode
        df = pd.read_csv('data/processed/prospective_predictions.csv')
        df = update_outcomes_manual(df)
        df.to_csv('data/processed/prospective_predictions.csv', index=False)
        logger.info("✓ Saved updated predictions")
    else:
        # Batch mode (try API for all pending)
        update_outcomes_batch()
