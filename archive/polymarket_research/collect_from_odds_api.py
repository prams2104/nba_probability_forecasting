"""
Collect predictions starting from The Odds API (NBA games).

Since Polymarket's NBA tag returns mixed content, we:
1. Get upcoming NBA games from The Odds API (definitive source)
2. For each game, get sportsbook odds
3. Search Polymarket for matching NBA game market
4. Extract T-minus 1 hour Polymarket price if match found
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import requests
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_KEY = "c570e219b316bd207fb09a90ff6f6d31"

# Odds API team names -> standard abbreviations
TEAM_ABBR = {
    'Atlanta Hawks': 'atl', 'Boston Celtics': 'bos', 'Brooklyn Nets': 'bkn',
    'Charlotte Hornets': 'cha', 'Chicago Bulls': 'chi', 'Cleveland Cavaliers': 'cle',
    'Dallas Mavericks': 'dal', 'Denver Nuggets': 'den', 'Detroit Pistons': 'det',
    'Golden State Warriors': 'gs', 'Houston Rockets': 'hou', 'Indiana Pacers': 'ind',
    'LA Clippers': 'lac', 'Los Angeles Clippers': 'lac', 'Los Angeles Lakers': 'lal',
    'LA Lakers': 'lal', 'Memphis Grizzlies': 'mem', 'Miami Heat': 'mia',
    'Milwaukee Bucks': 'mil', 'Minnesota Timberwolves': 'min',
    'New Orleans Pelicans': 'no', 'New York Knicks': 'ny',
    'Oklahoma City Thunder': 'okc', 'Orlando Magic': 'orl',
    'Philadelphia 76ers': 'phi', 'Phoenix Suns': 'phx',
    'Portland Trail Blazers': 'por', 'Sacramento Kings': 'sac',
    'San Antonio Spurs': 'sa', 'Toronto Raptors': 'tor',
    'Utah Jazz': 'utah', 'Washington Wizards': 'was',
}


def fetch_nba_games_from_odds_api():
    """Fetch upcoming NBA games with odds from The Odds API."""
    logger.info("Fetching NBA games from The Odds API...")
    
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    games = response.json()
    
    remaining = response.headers.get('x-requests-remaining', '?')
    logger.info(f"API requests remaining: {remaining}")
    
    return games


def search_polymarket_for_nba_game(home_team: str, away_team: str):
    """Search Polymarket for an NBA game market matching the teams."""
    try:
        url = "https://gamma-api.polymarket.com/events"
        params = {
            "tag": "NBA",
            "active": "true",
            "limit": 50,
            "closed": "false",
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        events = response.json()
        
        # Keywords to match
        home_kw = home_team.lower().replace('76ers', 'sixers').split()
        away_kw = away_team.lower().replace('76ers', 'sixers').split()
        
        for event in events:
            title = event.get('title', '').lower()
            # Check if both teams appear in title (NBA game format)
            if 'nba' in title or 'basketball' in title or 'win' in title:
                home_match = any(kw in title for kw in home_kw if len(kw) > 2)
                away_match = any(kw in title for kw in away_kw if len(kw) > 2)
                if home_match and away_match:
                    markets = event.get('markets', [])
                    clob_token = markets[0].get('clobToken') if markets else None
                    return {
                        'event_id': event['id'],
                        'title': event['title'],
                        'clob_token': clob_token,
                        'end_date': event.get('endDate'),
                    }
        return None
    except Exception as e:
        logger.error(f"Polymarket search error: {e}")
        return None


def main():
    logger.info("="*70)
    logger.info("COLLECTING NBA PREDICTIONS (Odds API → Polymarket)")
    logger.info("="*70)
    
    games = fetch_nba_games_from_odds_api()
    
    if not games:
        logger.error("No NBA games found from Odds API")
        return
    
    logger.info(f"Found {len(games)} upcoming NBA games\n")
    
    predictions = []
    
    for game in games:
        home_name = game.get('home_team', '')
        away_name = game.get('away_team', '')
        commence = game.get('commence_time', '')
        
        home_abbr = TEAM_ABBR.get(home_name, home_name[:3].lower() if len(home_name) >= 3 else '')
        away_abbr = TEAM_ABBR.get(away_name, away_name[:3].lower() if len(away_name) >= 3 else '')
        
        # Get odds from first bookmaker
        bookmakers = game.get('bookmakers', [])
        if not bookmakers:
            logger.warning(f"No odds for {away_name} @ {home_name}")
            continue
            
        bm = bookmakers[0]
        markets = bm.get('markets', [])
        if not markets:
            continue
            
        outcomes = markets[0].get('outcomes', [])
        home_odds = away_odds = None
        
        for o in outcomes:
            name = o.get('name', '').lower()
            price = o.get('price')
            if home_name.lower() in name or (home_abbr and home_abbr in name):
                home_odds = price
            elif away_name.lower() in name or (away_abbr and away_abbr in name):
                away_odds = price
        
        if home_odds is None or away_odds is None:
            # Fallback: first outcome = away, second = home (typical order)
            if len(outcomes) >= 2:
                away_odds = outcomes[0].get('price')
                home_odds = outcomes[1].get('price')
        
        logger.info(f"Processing: {away_name} @ {home_name}")
        logger.info(f"  Odds: Home {home_odds}, Away {away_odds} ({bm.get('title', '')})")
        
        # Search Polymarket for matching market
        poly_match = search_polymarket_for_nba_game(home_name, away_name)
        poly_price = None
        poly_event_id = None
        
        if poly_match:
            logger.info(f"  ✓ Polymarket match: {poly_match['title'][:50]}...")
            # For active markets, we'd need to call prices-history at T-1hr
            # For now, we don't have T-1hr - would need to run closer to game time
            poly_event_id = poly_match['event_id']
        else:
            logger.info(f"  No Polymarket match found")
        
        predictions.append({
            'event_id': poly_event_id,
            'polymarket_title': poly_match['title'] if poly_match else None,
            'home_team': home_abbr or home_name,
            'away_team': away_abbr or away_name,
            'game_time': commence,
            'polymarket_t_minus_1_price': poly_price,
            'sportsbook_home_odds': home_odds,
            'sportsbook_away_odds': away_odds,
            'sportsbook_source': 'the_odds_api',
            'sportsbook_name': bm.get('title', ''),
            'collection_timestamp': datetime.now().isoformat(),
            'status': 'pending',
        })
        
        time.sleep(0.2)
    
    # Save
    df = pd.DataFrame(predictions)
    out_path = Path('data/processed/prospective_predictions.csv')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path)
            if not existing.empty and len(existing.columns) > 0:
                df = pd.concat([existing, df], ignore_index=True)
                df = df.drop_duplicates(subset=['home_team', 'away_team', 'game_time'], keep='last')
        except pd.errors.EmptyDataError:
            pass
    
    df.to_csv(out_path, index=False)
    
    logger.info("\n" + "="*70)
    logger.info("COLLECTION COMPLETE")
    logger.info("="*70)
    logger.info(f"Total predictions: {len(df)}")
    logger.info(f"With sportsbook odds: {df['sportsbook_home_odds'].notna().sum()}")
    logger.info(f"Polymarket matches: {df['event_id'].notna().sum()}")
    logger.info(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()
