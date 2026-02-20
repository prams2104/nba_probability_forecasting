"""
Extract opening prices from Polymarket events using event startDate + outcomePrices.

This script implements Pivot Option 1: Opening Line Comparison.
It extracts the opening price from Polymarket event metadata and aligns it with
sportsbook opening lines for fair comparison.
"""

import pandas as pd
import requests
import time
import logging
import json
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_event_opening_price(event_id: int) -> tuple[Optional[float], Optional[str]]:
    """
    Extract opening price and startDate from Polymarket event.
    
    Returns:
        (opening_price, start_date) or (None, None) if unavailable
    """
    try:
        url = f"https://gamma-api.polymarket.com/events/{event_id}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        event_data = resp.json()
        
        markets = event_data.get("markets", [])
        if not markets:
            return None, None
        
        market = markets[0]
        start_date = event_data.get("startDate") or market.get("startDate")
        outcome_prices = market.get("outcomePrices")
        
        if not outcome_prices:
            return None, None
        
        try:
            prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
            if prices and len(prices) > 0:
                opening_price = float(prices[0])
                return opening_price, start_date
        except (json.JSONDecodeError, ValueError, IndexError):
            pass
        
        return None, None
        
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {e}")
        return None, None


def extract_opening_prices_for_master_events(filepath='data/processed/master_events.csv'):
    """
    Extract opening prices for all events in master_events.csv.
    """
    logger.info(f"Loading {filepath}...")
    df = pd.read_csv(filepath)
    
    if df.empty:
        logger.error("Dataset is empty.")
        return
    
    logger.info(f"Extracting opening prices for {len(df)} events...")
    
    opening_prices = []
    start_dates = []
    success_count = 0
    
    for idx, row in df.iterrows():
        event_id = row['event_id']
        
        opening_price, start_date = get_event_opening_price(event_id)
        opening_prices.append(opening_price)
        start_dates.append(start_date)
        
        if opening_price is not None:
            success_count += 1
        
        if (idx + 1) % 50 == 0:
            logger.info(f"Processed {idx+1}/{len(df)} events... (Found {success_count} opening prices)")
        
        time.sleep(0.3)  # Rate limiting
    
    df['polymarket_opening_price'] = opening_prices
    df['polymarket_start_date'] = start_dates
    
    # Filter to events with valid opening prices
    df_clean = df.dropna(subset=['polymarket_opening_price']).copy()
    
    logger.info(f"\n{'='*70}")
    logger.info("OPENING PRICE EXTRACTION RESULTS")
    logger.info(f"{'='*70}")
    logger.info(f"Total events: {len(df)}")
    logger.info(f"Events with opening prices: {len(df_clean)} ({len(df_clean)/len(df)*100:.1f}%)")
    
    if df_clean.empty:
        logger.error("No opening prices found. Cannot proceed with pivot.")
        return
    
    # Save results
    output_path = 'data/processed/master_events_opening_prices.csv'
    df_clean.to_csv(output_path, index=False)
    logger.info(f"\nSaved to: {output_path}")
    
    # Summary statistics
    logger.info(f"\nOpening Price Statistics:")
    logger.info(f"  Mean: {df_clean['polymarket_opening_price'].mean():.4f}")
    logger.info(f"  Std:  {df_clean['polymarket_opening_price'].std():.4f}")
    logger.info(f"  Min:  {df_clean['polymarket_opening_price'].min():.4f}")
    logger.info(f"  Max:  {df_clean['polymarket_opening_price'].max():.4f}")
    
    return df_clean


def align_opening_prices_to_home_team(df: pd.DataFrame) -> pd.DataFrame:
    """
    Align Polymarket opening prices to home team (same logic as evaluation.py).
    """
    from src.processing.evaluation import align_polymarket_probability
    
    # Create a temporary column for alignment
    df_temp = df.copy()
    df_temp['polymarket_prob'] = df_temp['polymarket_opening_price']
    
    # Apply alignment function
    df_temp['aligned_poly_opening_home'] = df_temp.apply(
        align_polymarket_probability, axis=1
    )
    
    # Drop temporary column
    df_temp = df_temp.drop(columns=['polymarket_prob'])
    
    return df_temp


if __name__ == "__main__":
    # Extract opening prices
    df_with_opening = extract_opening_prices_for_master_events()
    
    if df_with_opening is not None and not df_with_opening.empty:
        # Align to home team
        logger.info("\nAligning opening prices to home team...")
        df_aligned = align_opening_prices_to_home_team(df_with_opening)
        
        # Save aligned version
        aligned_path = 'data/processed/master_events_opening_aligned.csv'
        df_aligned.to_csv(aligned_path, index=False)
        logger.info(f"Aligned opening prices saved to: {aligned_path}")
        
        logger.info("\n✓ Opening price extraction complete!")
        logger.info("  Next step: Update evaluation.py to use 'aligned_poly_opening_home' instead of T-minus 1 hour prices.")
