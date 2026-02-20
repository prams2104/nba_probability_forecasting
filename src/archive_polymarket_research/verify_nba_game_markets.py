"""
Verification script to definitively check if Polymarket has individual NBA game markets.

This will search through active markets and identify any that look like actual NBA games
(not futures, not college basketball, not other sports).
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# NBA team names (full and common variations)
NBA_TEAMS = {
    'atlanta hawks', 'boston celtics', 'brooklyn nets', 'charlotte hornets',
    'chicago bulls', 'cleveland cavaliers', 'dallas mavericks', 'denver nuggets',
    'detroit pistons', 'golden state warriors', 'houston rockets', 'indiana pacers',
    'la clippers', 'los angeles clippers', 'los angeles lakers', 'la lakers',
    'memphis grizzlies', 'miami heat', 'milwaukee bucks', 'minnesota timberwolves',
    'new orleans pelicans', 'new york knicks', 'oklahoma city thunder', 'orlando magic',
    'philadelphia 76ers', 'phoenix suns', 'portland trail blazers', 'sacramento kings',
    'san antonio spurs', 'toronto raptors', 'utah jazz', 'washington wizards',
    # Common abbreviations/nicknames
    'hawks', 'celtics', 'nets', 'hornets', 'bulls', 'cavaliers', 'cavs',
    'mavericks', 'mavs', 'nuggets', 'pistons', 'warriors', 'rockets', 'pacers',
    'clippers', 'lakers', 'grizzlies', 'heat', 'bucks', 'timberwolves', 'wolves',
    'pelicans', 'knicks', 'thunder', 'magic', '76ers', 'sixers', 'suns',
    'trail blazers', 'blazers', 'kings', 'spurs', 'raptors', 'jazz', 'wizards'
}


def is_nba_game_title(title: str) -> bool:
    """Check if a title looks like an individual NBA game (not futures/season markets)."""
    title_lower = title.lower()
    
    # Exclude futures/season markets
    futures_keywords = [
        'champion', 'mvp', 'rookie of the year', 'playoffs', 'division winner',
        'conference champion', 'best record', 'worst record', 'defensive player',
        'sixth man', 'most improved', 'coach of the year', 'points per game',
        'rebounds per game', 'assists per game', 'blocks per game', 'steals per game',
        'win totals', 'seed', 'all-star', 'all star'
    ]
    
    if any(kw in title_lower for kw in futures_keywords):
        return False
    
    # Must contain "vs" or "@" (game matchup indicator)
    if ' vs ' not in title_lower and ' vs. ' not in title_lower and ' @ ' not in title_lower:
        return False
    
    # Check if both teams mentioned are NBA teams
    # Split by vs/@
    if ' vs ' in title_lower:
        parts = title_lower.split(' vs ')
    elif ' vs. ' in title_lower:
        parts = title_lower.split(' vs. ')
    elif ' @ ' in title_lower:
        parts = title_lower.split(' @ ')
    else:
        return False
    
    if len(parts) < 2:
        return False
    
    team1 = parts[0].strip()
    team2 = parts[1].strip()
    
    # Remove common suffixes
    for suffix in [' (w)', ' (women)', ' women', ' men', ' (m)']:
        team1 = team1.replace(suffix, '')
        team2 = team2.replace(suffix, '')
    
    # Check if either part contains NBA team names
    team1_match = any(nba_team in team1 for nba_team in NBA_TEAMS)
    team2_match = any(nba_team in team2 for nba_team in NBA_TEAMS)
    
    # Both teams should match NBA teams (or at least one clearly does)
    if team1_match and team2_match:
        return True
    
    # Also check if title explicitly mentions NBA
    if 'nba' in title_lower and (team1_match or team2_match):
        return True
    
    return False


def verify_nba_game_markets():
    """Search Polymarket for actual NBA game markets."""
    logger.info("="*70)
    logger.info("VERIFYING NBA GAME MARKETS ON POLYMARKET")
    logger.info("="*70)
    
    # Load cached active markets
    markets_path = Path('data/processed/active_nba_markets.csv')
    if markets_path.exists():
        logger.info("Loading cached active markets...")
        df = pd.read_csv(markets_path)
    else:
        logger.info("Fetching active markets from Polymarket...")
        from scripts.find_active_nba_markets import find_active_nba_markets
        df = find_active_nba_markets()
    
    logger.info(f"Total markets to check: {len(df)}\n")
    
    # Filter for game-like titles
    game_pattern = df['title'].str.contains(r'\bvs\.?\b|@', case=False, na=False)
    game_markets = df[game_pattern].copy()
    
    logger.info(f"Markets with 'vs' or '@': {len(game_markets)}")
    
    # Check each one
    nba_games = []
    non_nba_games = []
    
    for idx, row in game_markets.iterrows():
        title = row['title']
        if is_nba_game_title(title):
            nba_games.append(row)
        else:
            non_nba_games.append(row)
    
    logger.info("\n" + "="*70)
    logger.info("RESULTS")
    logger.info("="*70)
    logger.info(f"✅ Actual NBA game markets found: {len(nba_games)}")
    logger.info(f"❌ Non-NBA game markets (college/other): {len(non_nba_games)}")
    
    if nba_games:
        logger.info("\n" + "="*70)
        logger.info("NBA GAME MARKETS FOUND:")
        logger.info("="*70)
        for game in nba_games[:10]:  # Show first 10
            logger.info(f"  [{game['event_id']}] {game['title']}")
            logger.info(f"      Game Date: {game.get('game_date', 'N/A')}")
        
        # Save NBA games
        nba_df = pd.DataFrame(nba_games)
        output_path = Path('data/processed/verified_nba_game_markets.csv')
        nba_df.to_csv(output_path, index=False)
        logger.info(f"\n✓ Saved {len(nba_games)} NBA game markets to {output_path}")
        
        return True
    else:
        logger.info("\n" + "="*70)
        logger.info("NO NBA GAME MARKETS FOUND")
        logger.info("="*70)
        logger.info("Sample non-NBA games found:")
        for game in non_nba_games[:5]:
            logger.info(f"  [{game['event_id']}] {game['title']}")
        
        logger.info("\nCONCLUSION:")
        logger.info("Polymarket does NOT have individual NBA game markets.")
        logger.info("They only have season-long futures markets (champion, MVP, etc.).")
        logger.info("\nRecommendation: Proceed with Option A (Sportsbook-only evaluation)")
        
        return False


if __name__ == "__main__":
    has_nba_games = verify_nba_game_markets()
    
    if not has_nba_games:
        logger.info("\n" + "="*70)
        logger.info("GEMINI'S APPROACH VERDICT")
        logger.info("="*70)
        logger.info("❌ Gemini's 'Live Tracker' approach will NOT work")
        logger.info("   Reason: Polymarket doesn't list individual NBA games")
        logger.info("\n✅ Your best path forward:")
        logger.info("   1. Use 512 historical games for Sportsbook evaluation")
        logger.info("   2. Document Polymarket API limitations clearly")
        logger.info("   3. This is still academically rigorous and valuable")
