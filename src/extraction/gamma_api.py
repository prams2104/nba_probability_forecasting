import requests
import pandas as pd
import time
import logging
import json
import os

logger = logging.getLogger(__name__)

def fetch_polymarket_history_paginated(use_start_date_for_timestamp: bool = True):
    logger.info("Starting production Polymarket Gamma API extraction...")
    cache_path = 'data/raw/raw_poly_cache.json'
    
    if os.path.exists(cache_path):
        logger.info("Loading Polymarket data from local cache... (Skipping API wait!)")
        df = pd.read_json(cache_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        return df

    url = "https://gamma-api.polymarket.com/events"
    all_events = []
    limit = 100
    offset = 0
    MIN_YEAR = 2022

    while True:
        # 1. THE HARD FAILSAFE (Stops no matter what at 50,000)
        if offset >= 50000:
            logger.info("Reached absolute maximum limit of 50,000 offsets. Stopping extraction.")
            break

        try:
            params = {"limit": limit, "offset": offset, "tag": "NBA", "closed": "true"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break 

            # 2. THE SAFE "EARLY EXIT" FOR 2022
            valid_years_on_page = []
            
            for item in data:
                raw_date = item.get("endDate")
                if not raw_date:
                    continue
                
                event_date = pd.to_datetime(raw_date, utc=True)
                if event_date is None or pd.isna(event_date):
                    continue
                
                valid_years_on_page.append(event_date.year)
                
                if event_date.year >= MIN_YEAR:
                    markets = item.get("markets", [])
                    prob = 0.50 
                    if markets and "outcomePrices" in markets[0]:
                        try:
                            prices = json.loads(markets[0]["outcomePrices"])
                            prob = float(prices[0]) if prices else 0.50
                        except (json.JSONDecodeError, ValueError, IndexError):
                            pass

                    all_events.append({
                        "event_id": item.get("id"),
                        "poly_event_name": item.get("title"),
                        "timestamp": event_date,
                        "polymarket_prob": prob
                    })
            
            # If every single valid event on this page is older than 2022, STOP!
            if valid_years_on_page and max(valid_years_on_page) < MIN_YEAR:
                logger.info("Reached pre-2022 historical data. Stopping extraction.")
                break

            logger.info(f"Fetched offset {offset}...")
            offset += limit
            time.sleep(0.3) 
            
        except Exception as e:
            logger.error(f"Error at offset {offset}: {e}")
            offset += limit 
            time.sleep(1)
                
    df = pd.DataFrame(all_events)
    
    os.makedirs('data/raw', exist_ok=True)
    df.to_json(cache_path, orient='records', date_format='iso')
    logger.info(f"Saved {len(df)} targeted events to local cache.")
    
    return df