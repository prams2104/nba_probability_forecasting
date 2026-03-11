"""
Collect prospective predictions for active NBA markets.

This script:
1. Finds active Polymarket NBA markets
2. Matches them to sportsbook odds (from API or manual collection)
3. Extracts T-minus 1 hour prices from both sources
4. Stores predictions for later evaluation after games complete

This solves the comparison problem: we collect BOTH Polymarket and Sportsbook data
for the SAME future games, ensuring fair comparison.
"""

import sys
import pandas as pd
import requests
import time
import logging
from datetime import datetime, timedelta
import json
from pathlib import Path

# Add project root to path for imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_polymarket_t_minus_1_price(event_id: int, clob_token: str, game_time: datetime) -> Optional[float]:
    """
    Extract T-minus 1 hour price from Polymarket for an ACTIVE market.
    This works because active markets have accessible price history.
    """
    try:
        target_time = game_time - timedelta(hours=1)
        target_ts = int(target_time.timestamp())
        
        # Get price history up to target time
        url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": clob_token,
            "interval": "max",
            "endTs": target_ts + 3600,  # 1 hour buffer
        }
        
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data or "history" not in data or not data["history"]:
            return None
        
        hist_df = pd.DataFrame(data["history"])
        if hist_df.empty:
            return None
        
        hist_df['t'] = pd.to_datetime(hist_df['t'], unit='s', utc=True)
        hist_df['p'] = hist_df['p'].astype(float)
        hist_df = hist_df.sort_values('t')
        
        target_dt = pd.to_datetime(target_time, utc=True)
        valid_prices = hist_df[hist_df['t'] <= target_dt]
        
        if valid_prices.empty:
            # Use earliest available price if no prices before target
            return float(hist_df.iloc[0]['p'])
        
        return float(valid_prices.iloc[-1]['p'])
        
    except Exception as e:
        logger.error(f"Error extracting Polymarket price for event {event_id}: {e}")
        return None


def get_sportsbook_odds_from_api(home_team: str, away_team: str, game_date: str) -> Optional[Dict]:
    """
    Get sportsbook odds from The Odds API.
    
    API Documentation: https://the-odds-api.com/liveapi/guides/v4/
    
    Returns dict with 'home_odds', 'away_odds', 'source', 'sportsbook_name'
    """
    API_KEY = "c570e219b316bd207fb09a90ff6f6d31"
    
    try:
        # The Odds API endpoint
        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
        params = {
            "apiKey": API_KEY,
            "regions": "us",  # US sportsbooks
            "markets": "h2h",  # Moneyline (head-to-head)
            "dateFormat": "iso",
            "oddsFormat": "american"  # American odds format (-120, +100)
        }
        
        # If game_date is provided, filter by date
        if game_date:
            # Format: YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DD
            if len(game_date) == 10:  # YYYY-MM-DD
                params["commenceTimeFrom"] = f"{game_date}T00:00:00Z"
                params["commenceTimeTo"] = f"{game_date}T23:59:59Z"
        
        logger.info(f"Fetching odds from The Odds API for {away_team} @ {home_team} on {game_date}")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        games_data = response.json()
        
        if not games_data:
            logger.warning(f"No games found for date {game_date}")
            return None
        
        # Team name mapping (abbreviations to full names for matching)
        team_mapping = {
            'atl': 'Atlanta Hawks', 'bos': 'Boston Celtics', 'bkn': 'Brooklyn Nets',
            'cha': 'Charlotte Hornets', 'chi': 'Chicago Bulls', 'cle': 'Cleveland Cavaliers',
            'dal': 'Dallas Mavericks', 'den': 'Denver Nuggets', 'det': 'Detroit Pistons',
            'gs': 'Golden State Warriors', 'hou': 'Houston Rockets', 'ind': 'Indiana Pacers',
            'lac': 'LA Clippers', 'lal': 'Los Angeles Lakers', 'mem': 'Memphis Grizzlies',
            'mia': 'Miami Heat', 'mil': 'Milwaukee Bucks', 'min': 'Minnesota Timberwolves',
            'no': 'New Orleans Pelicans', 'ny': 'New York Knicks', 'okc': 'Oklahoma City Thunder',
            'orl': 'Orlando Magic', 'phi': 'Philadelphia 76ers', 'phx': 'Phoenix Suns',
            'por': 'Portland Trail Blazers', 'sac': 'Sacramento Kings', 'sa': 'San Antonio Spurs',
            'tor': 'Toronto Raptors', 'utah': 'Utah Jazz', 'was': 'Washington Wizards'
        }
        
        home_full = team_mapping.get(home_team.lower(), home_team)
        away_full = team_mapping.get(away_team.lower(), away_team)
        
        # Find matching game
        for game in games_data:
            home_team_name = game.get('home_team', '')
            away_team_name = game.get('away_team', '')
            
            # Check if teams match (flexible matching)
            home_match = (home_team.lower() in home_team_name.lower() or 
                         home_full.lower() in home_team_name.lower() or
                         home_team_name.lower() in home_full.lower())
            away_match = (away_team.lower() in away_team_name.lower() or 
                         away_full.lower() in away_team_name.lower() or
                         away_team_name.lower() in away_full.lower())
            
            if home_match and away_match:
                # Found matching game, extract odds
                bookmakers = game.get('bookmakers', [])
                
                if not bookmakers:
                    logger.warning(f"No bookmakers found for game {home_team} vs {away_team}")
                    return None
                
                # Use first bookmaker (or you could average across multiple)
                bookmaker = bookmakers[0]
                markets = bookmaker.get('markets', [])
                
                if not markets:
                    logger.warning(f"No markets found for game {home_team} vs {away_team}")
                    return None
                
                h2h_market = markets[0]  # h2h market
                outcomes = h2h_market.get('outcomes', [])
                
                if len(outcomes) < 2:
                    logger.warning(f"Not enough outcomes found for game {home_team} vs {away_team}")
                    return None
                
                # Extract odds for home and away teams
                home_odds = None
                away_odds = None
                
                for outcome in outcomes:
                    outcome_name = outcome.get('name', '').lower()
                    odds = outcome.get('price')
                    
                    # Match to home/away team
                    if (home_team.lower() in outcome_name or 
                        home_full.lower() in outcome_name or
                        'home' in outcome_name):
                        home_odds = odds
                    elif (away_team.lower() in outcome_name or 
                          away_full.lower() in outcome_name or
                          'away' in outcome_name):
                        away_odds = odds
                
                if home_odds is not None and away_odds is not None:
                    logger.info(f"✓ Found odds: Home {home_odds}, Away {away_odds} from {bookmaker.get('title', 'Unknown')}")
                    return {
                        'home_odds': home_odds,
                        'away_odds': away_odds,
                        'source': 'the_odds_api',
                        'sportsbook_name': bookmaker.get('title', 'Unknown'),
                        'commence_time': game.get('commence_time')
                    }
                else:
                    logger.warning(f"Could not match odds to teams for {home_team} vs {away_team}")
        
        logger.warning(f"Game not found in API response: {away_team} @ {home_team} on {game_date}")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching odds from API: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_sportsbook_odds_from_api: {e}")
        return None


def get_sportsbook_odds_manual(home_team: str, away_team: str, game_date: str) -> Optional[Dict]:
    """
    Manual collection of sportsbook odds.
    
    Instructions:
    1. Visit a sportsbook website (DraftKings, FanDuel, BetMGM, etc.)
    2. Find the game: {away_team} @ {home_team} on {game_date}
    3. Record the moneyline odds for both teams
    4. Return as dict
    
    This is a placeholder - you'll need to manually collect odds for each game.
    """
    logger.info(f"Manual collection needed for: {away_team} @ {home_team} on {game_date}")
    logger.info("Visit a sportsbook website and record moneyline odds")
    
    # Return None to indicate manual collection needed
    return None


def extract_teams_from_polymarket_title(title: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract home and away teams from Polymarket event title.
    Uses your existing fuzzy matching logic.
    """
    from src.matching.fuzzy_match import match_teams, ALIAS_TABLE
    
    # List of all possible team combinations (home vs away)
    # Generate from your existing team abbreviations
    team_abbrs = ['atl', 'bos', 'bkn', 'cha', 'chi', 'cle', 'dal', 'den', 'det', 
                  'gs', 'hou', 'ind', 'lac', 'lal', 'mem', 'mia', 'mil', 'min',
                  'no', 'ny', 'okc', 'orl', 'phi', 'phx', 'por', 'sac', 'sa',
                  'tor', 'utah', 'was']
    
    # Generate all possible "team1 vs team2" combinations
    sb_event_list = []
    for t1 in team_abbrs:
        for t2 in team_abbrs:
            if t1 != t2:
                sb_event_list.append(f"{t1} vs {t2}")
                sb_event_list.append(f"{t2} vs {t1}")
    
    # Use your existing matching function
    matched_event, score = match_teams(title, sb_event_list)
    
    if score >= 90 and matched_event:
        # Parse "team1 vs team2" format
        parts = matched_event.split(" vs ")
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    
    # Fallback: Try to extract directly from title
    title_lower = title.lower()
    
    # Look for patterns like "Team A vs Team B" or "Team A @ Team B"
    import re
    
    # Pattern: "team1 vs team2" or "team1 @ team2"
    vs_pattern = r'(\w+)\s+(?:vs|@)\s+(\w+)'
    match = re.search(vs_pattern, title_lower)
    
    if match:
        team1 = match.group(1)
        team2 = match.group(2)
        
        # Try to match to known abbreviations
        for abbr, aliases in ALIAS_TABLE.items():
            if team1 in aliases or abbr in team1:
                team1_abbr = abbr
                break
        else:
            team1_abbr = None
            
        for abbr, aliases in ALIAS_TABLE.items():
            if team2 in aliases or abbr in team2:
                team2_abbr = abbr
                break
        else:
            team2_abbr = None
        
        if team1_abbr and team2_abbr:
            # Determine home/away (usually second team is home in "vs" format)
            return team2_abbr, team1_abbr
    
    logger.warning(f"Could not extract teams from title: {title}")
    return None, None


def collect_prospective_predictions():
    """
    Main function to collect prospective predictions.
    
    Workflow:
    1. Find active Polymarket NBA markets
    2. For each market, extract game info (teams, date)
    3. Get sportsbook odds for same game (API or manual)
    4. Extract T-minus 1 hour prices from both sources
    5. Store predictions for later evaluation
    """
    logger.info("="*70)
    logger.info("PROSPECTIVE PREDICTION COLLECTION")
    logger.info("="*70)
    
    # Step 1: Load active Polymarket markets (from CSV or fetch if needed)
    logger.info("\nStep 1: Loading active Polymarket NBA markets...")
    markets_path = Path('data/processed/active_nba_markets.csv')
    
    if markets_path.exists():
        active_markets = pd.read_csv(markets_path)
        logger.info(f"Loaded {len(active_markets)} markets from cache")
    else:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts.find_active_nba_markets import find_active_nba_markets
        active_markets = find_active_nba_markets()
    
    if active_markets.empty:
        logger.error("No active markets found. Cannot collect predictions.")
        return
    
    logger.info(f"Found {len(active_markets)} active markets")
    
    # Filter to markets that look like game matchups (contain "vs" or "@")
    game_pattern = active_markets['title'].str.contains(r'\bvs\.?\b|@', case=False, na=False)
    game_markets = active_markets[game_pattern].head(50)  # Process first 50 game-like markets
    if game_markets.empty:
        game_markets = active_markets.head(50)  # Fallback: first 50
    
    logger.info(f"Processing {len(game_markets)} game-like markets")
    
    # Step 2: For each market, collect predictions
    predictions = []
    
    for idx, market in game_markets.iterrows():
        event_id = market['event_id']
        title = market['title']
        game_date = market['game_date']
        clob_token = market['clob_token']
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing Market {idx+1}/{len(active_markets)}: Event {event_id}")
        logger.info(f"Title: {title}")
        logger.info(f"Game Date: {game_date}")
        
        # Extract teams from title (you may need to enhance this)
        home_team, away_team = extract_teams_from_polymarket_title(title)
        
        if not home_team or not away_team:
            logger.warning(f"Could not extract teams from title: {title}")
            logger.info("Skipping - manual team extraction needed")
            continue
        
        # Step 3: Get sportsbook odds
        logger.info(f"Getting sportsbook odds for: {away_team} @ {home_team}")
        
        # Try API first, fallback to manual
        sb_odds = get_sportsbook_odds_from_api(home_team, away_team, str(game_date) if pd.notna(game_date) else None)
        
        if not sb_odds:
            logger.info("API did not return odds. Marking for manual collection.")
            sb_odds = {
                'home_odds': None,
                'away_odds': None,
                'source': 'manual_collection_needed',
                'sportsbook_name': None,
                'collection_date': datetime.now().isoformat()
            }
        
        # Step 4: Extract T-minus 1 hour Polymarket price
        # Only do this if game is within 2 hours (to avoid extracting too early)
        if game_date and pd.notna(game_date):
            game_dt = pd.to_datetime(game_date, utc=True)
            now = pd.Timestamp.now(tz='UTC')
            
            # Only extract if game is within next 24 hours (or already passed)
            if (game_dt - now).total_seconds() < 86400:  # 24 hours
                logger.info("Extracting T-minus 1 hour Polymarket price...")
                poly_price = get_polymarket_t_minus_1_price(event_id, clob_token, game_dt)
                
                if poly_price is not None:
                    logger.info(f"✓ Polymarket T-minus 1 hour price: {poly_price:.4f}")
                else:
                    logger.warning("Could not extract Polymarket price (market may be too new)")
                    poly_price = None
            else:
                logger.info(f"Game is more than 24 hours away. Will extract closer to game time.")
                poly_price = None
        else:
            logger.warning("Game date not available. Cannot extract T-minus 1 hour price.")
            poly_price = None
        
        # Store prediction
        prediction = {
            'event_id': event_id,
            'polymarket_title': title,
            'home_team': home_team,
            'away_team': away_team,
            'game_date': game_date,
            'polymarket_t_minus_1_price': poly_price,
            'sportsbook_home_odds': sb_odds.get('home_odds'),
            'sportsbook_away_odds': sb_odds.get('away_odds'),
            'sportsbook_source': sb_odds.get('source'),
            'sportsbook_name': sb_odds.get('sportsbook_name'),
            'collection_timestamp': datetime.now().isoformat(),
            'status': 'pending'  # Will be updated after game completes
        }
        
        predictions.append(prediction)
        
        time.sleep(0.5)  # Rate limiting
    
    # Save predictions
    predictions_df = pd.DataFrame(predictions)
    
    output_path = Path('data/processed/prospective_predictions.csv')
    
    # Append to existing file if it exists
    if output_path.exists():
        existing_df = pd.read_csv(output_path)
        predictions_df = pd.concat([existing_df, predictions_df], ignore_index=True)
        predictions_df = predictions_df.drop_duplicates(subset=['event_id'], keep='last')
    
    predictions_df.to_csv(output_path, index=False)
    logger.info(f"\n✓ Saved {len(predictions)} predictions to {output_path}")
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("COLLECTION SUMMARY")
    logger.info("="*70)
    logger.info(f"Total predictions collected: {len(predictions)}")
    if not predictions_df.empty:
        logger.info(f"Polymarket prices extracted: {predictions_df['polymarket_t_minus_1_price'].notna().sum()}")
        logger.info(f"Sportsbook odds collected: {predictions_df['sportsbook_home_odds'].notna().sum()}")
        logger.info(f"Manual collection needed: {(predictions_df['sportsbook_source'] == 'manual_collection_needed').sum()}")
    
    logger.info("\nNext steps:")
    logger.info("1. Manually collect sportsbook odds for games marked 'manual_collection_needed'")
    logger.info("2. Extract T-minus 1 hour Polymarket prices closer to game time (if not done)")
    logger.info("3. After games complete, update with actual outcomes")
    logger.info("4. Run evaluation script to compare predictions")


if __name__ == "__main__":
    collect_prospective_predictions()
