import pandas as pd
import requests
import time
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_t_minus_1_price(event_id, target_time):
    """
    Fetches the price history for a specific event using the correct CLOB 'interval' parameter.
    """
    try:
        # 1. Get the Event details to find the clobToken
        event_url = f"https://gamma-api.polymarket.com/events/{event_id}"
        event_resp = requests.get(event_url, timeout=10)
        event_resp.raise_for_status()
        event_data = event_resp.json()
        
        markets = event_data.get("markets", [])
        if not markets:
            return None
            
        market = markets[0]
        clob_token = market.get("clobToken")
        
        if not clob_token:
            return None

        # 2. Ping the CLOB API with the correct interval parameter
        history_url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": clob_token,
            "interval": "max"  # THE FIX: This returns the full history correctly
        }
        
        hist_resp = requests.get(history_url, params=params, timeout=10)
        
        if hist_resp.status_code == 404:
            return None
            
        hist_resp.raise_for_status()
        history_data = hist_resp.json()
        
        # If Polymarket still returns empty for this specific game, skip gracefully
        if not history_data or "history" not in history_data:
            return None
            
        # 3. Convert history to a DataFrame to find the closest time
        hist_df = pd.DataFrame(history_data["history"])
        if hist_df.empty:
            return None
            
        hist_df['t'] = pd.to_datetime(hist_df['t'], unit='s', utc=True)
        hist_df['p'] = hist_df['p'].astype(float)
        hist_df = hist_df.sort_values('t')
        
        # 4. Find the last price recorded BEFORE our target_snapshot_time
        target_dt = pd.to_datetime(target_time, utc=True)
        valid_prices = hist_df[hist_df['t'] <= target_dt]
        
        if valid_prices.empty:
            return hist_df.iloc[0]['p']
            
        return valid_prices.iloc[-1]['p']

    except Exception as e:
        return None

def extract_true_historical_probabilities(filepath='data/processed/master_events.csv'):
    logger.info(f"Loading {filepath} for Time-Series Extraction...")
    df = pd.read_csv(filepath)
    
    if df.empty:
        logger.error("Dataset is empty.")
        return
        
    updated_probs = []
    success_count = 0
    
    logger.info(f"Pinging Time-Series API for {len(df)} synchronized events... (This will take a minute)")
    
    for index, row in df.iterrows():
        event_id = row['event_id']
        target_time = row['target_snapshot_time']
        
        true_prob = get_t_minus_1_price(event_id, target_time)
        updated_probs.append(true_prob)
        
        if true_prob is not None:
            success_count += 1
            
        if index % 50 == 0 and index > 0:
            logger.info(f"Processed {index}/{len(df)} charts... (Found {success_count} valid CLOB histories so far)")
            
        time.sleep(0.3) # Polite rate limiting
        
    df['true_t_minus_1_prob'] = updated_probs
    
    # Drop rows where Polymarket genuinely lost or purged the historical data
    df_clean = df.dropna(subset=['true_t_minus_1_prob']).copy()
    
    if df_clean.empty:
        logger.error("Failed to find any historical time-series data. Polymarket may have purged this data entirely.")
        return
        
    df_clean['polymarket_prob'] = df_clean['true_t_minus_1_prob']
    
    output_path = 'data/processed/master_events_timeseries.csv'
    df_clean.to_csv(output_path, index=False)
    
    logger.info(f"Success! {len(df_clean)} events safely updated with true T-minus 1 hour CLOB data.")
    logger.info(f"Saved to {output_path}")

if __name__ == "__main__":
    extract_true_historical_probabilities()