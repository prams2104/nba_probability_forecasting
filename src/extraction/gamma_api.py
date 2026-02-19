import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

def fetch_polymarket_nba_events():
    """Fetches NBA events from Polymarket Gamma API."""
    url = "https://gamma-api.polymarket.com/events"
    # Example parameters - you will need to adjust based on exact Gamma API specs for NBA filtering
    params = {"limit": 100, "active": "true", "tag": "NBA"} 
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    events = []
    for item in data:
        # Extracting required fields
        event_id = item.get("id")
        event_name = item.get("title")
        timestamp = item.get("endDate") # Or relevant timestamp field
        
        # In a real scenario, you'd iterate through the markets inside the event to get the exact team probabilities
        # Assuming we extract a representative market price here:
        prob = 0.50 # Placeholder for parsed probability
        
        events.append({
            "event_id": event_id,
            "event_name": event_name,
            "timestamp": timestamp,
            "polymarket_prob": prob
        })
        
    return pd.DataFrame(events)

def filter_t_minus_one_hour(df, timestamp_col='timestamp'):
    """Filters events to isolate the T-minus 1 hour snapshot."""
    # Convert string timestamps to datetime objects
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    
    # Calculate the snapshot target (1 hour before tip-off)
    df['target_snapshot'] = df[timestamp_col] - timedelta(hours=1)
    
    # In a full historical pipeline, you would query the API/DB closest to this 'target_snapshot' time.
    # For now, we return the annotated dataframe.
    return df

def load_and_standardize_sportsbook(filepath):
    """Loads Kaggle CSV and standardizes the schema."""
    # Load public historical moneyline datasets from Kaggle [cite: 9]
    df = pd.read_csv(filepath)
    
    # Standardize to match API output schema
    df = df.rename(columns={
        'Date': 'timestamp',
        'Home Team': 'home_team',
        'Away Team': 'away_team',
        'Home Odds': 'home_odds',
        'Away Odds': 'away_odds'
    })
    return df