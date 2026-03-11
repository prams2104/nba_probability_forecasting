"""
Quick test script to verify The Odds API is working with your API key.
"""

import requests
import json
from datetime import datetime, timedelta

API_KEY = "c570e219b316bd207fb09a90ff6f6d31"

def test_odds_api():
    """Test The Odds API connection and get sample NBA odds."""
    
    print("="*70)
    print("TESTING THE ODDS API")
    print("="*70)
    
    # Test 1: Get upcoming NBA games
    print("\n1. Fetching upcoming NBA games...")
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    params = {
        "apiKey": API_KEY,
        "regions": "us",
        "markets": "h2h",
        "dateFormat": "iso",
        "oddsFormat": "american"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        # Check API usage
        remaining_requests = response.headers.get('x-requests-remaining')
        used_requests = response.headers.get('x-requests-used')
        
        print(f"✓ API Connection successful!")
        print(f"  Requests used: {used_requests}")
        print(f"  Requests remaining: {remaining_requests}")
        
        games = response.json()
        print(f"\n2. Found {len(games)} upcoming NBA games")
        
        if games:
            print("\nSample games:")
            for i, game in enumerate(games[:5]):  # Show first 5
                home = game.get('home_team', 'Unknown')
                away = game.get('away_team', 'Unknown')
                commence = game.get('commence_time', 'Unknown')
                
                bookmakers = game.get('bookmakers', [])
                if bookmakers:
                    bm = bookmakers[0]
                    markets = bm.get('markets', [])
                    if markets:
                        outcomes = markets[0].get('outcomes', [])
                        odds_str = ", ".join([f"{o.get('name')}: {o.get('price')}" for o in outcomes])
                    else:
                        odds_str = "No odds available"
                else:
                    odds_str = "No bookmakers"
                
                print(f"\n  Game {i+1}:")
                print(f"    {away} @ {home}")
                print(f"    Time: {commence}")
                print(f"    Odds ({bm.get('title', 'Unknown')}): {odds_str}")
        
        print("\n" + "="*70)
        print("✓ API TEST SUCCESSFUL")
        print("="*70)
        print("\nYou can now use this API key in collect_prospective_predictions.py")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if response.status_code == 401:
            print("  API key is invalid. Please check your key.")
        elif response.status_code == 429:
            print("  Rate limit exceeded. Wait before trying again.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_odds_api()
