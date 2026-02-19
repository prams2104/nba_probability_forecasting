import requests
import pandas as pd
import time
import logging
import json

logger = logging.getLogger(__name__)

def fetch_polymarket_history_paginated(use_start_date_for_timestamp: bool = True):
    """
    Fetches historical NBA data from the Gamma API while respecting rate limits.

    Args:
        use_start_date_for_timestamp: If True, use startDate (market open, before game)
            for temporal alignment with T-minus-1-hour snapshots. If False, use endDate
            (game start/close). startDate is required for merge_asof(direction='backward').
    """
    logger.info("Starting production Polymarket Gamma API extraction...")
    url = "https://gamma-api.polymarket.com/events"
    all_events = []
    limit = 100
    offset = 0

    MIN_YEAR = 2022

    while True:
        try:
            params = {"limit": limit, "offset": offset, "tag": "NBA", "closed": "true"}
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break 
                
            # Check the date of the first item on the page
            last_event_date = pd.to_datetime(data[-1].get("endDate"))
            
            # If the entire page is older than our target year, STOP.
            if last_event_date.year < MIN_YEAR:
                logger.info(f"Reached {last_event_date.year}. Stopping extraction as per 2022 boundary.")
                break

            for item in data:
                # Still check individual items to be safe
                event_date = pd.to_datetime(item.get("endDate"), utc=True)
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
            
            logger.info(f"Fetched offset {offset} (Date: {last_event_date.date()})")
            offset += limit
            time.sleep(0.3) # Slightly faster sleep since we're being targeted
            
        except Exception as e:
            logger.error(f"Error at offset {offset}: {e}")
            break
            
    return pd.DataFrame(all_events)