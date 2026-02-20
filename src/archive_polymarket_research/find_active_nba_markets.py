"""
Find currently active NBA markets on Polymarket for prospective data collection.

This implements Pivot Option 2: Active Future Events.
We can extract T-minus 1 hour prices for ACTIVE markets (data is available).
"""

import pandas as pd
import requests
import time
import logging
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def find_active_nba_markets():
    """
    Find all currently active NBA markets on Polymarket.
    """
    logger.info("Searching for active NBA markets on Polymarket...")
    
    url = "https://gamma-api.polymarket.com/events"
    all_events = []
    limit = 100
    offset = 0
    max_offset = 1000  # Reasonable limit
    
    while offset < max_offset:
        try:
            params = {
                "limit": limit,
                "offset": offset,
                "tag": "NBA",
                "active": "true",  # Only active markets
                "closed": "false"
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
            
            for item in data:
                event_id = item.get("id")
                title = item.get("title", "")
                end_date = item.get("endDate")
                start_date = item.get("startDate")
                
                markets = item.get("markets", [])
                if not markets:
                    continue
                
                market = markets[0]
                clob_token = market.get("clobToken")
                
                # Extract game date if possible
                game_date = None
                if end_date:
                    try:
                        game_date = pd.to_datetime(end_date, utc=True)
                    except:
                        pass
                
                all_events.append({
                    "event_id": event_id,
                    "title": title,
                    "start_date": start_date,
                    "end_date": end_date,
                    "game_date": game_date,
                    "clob_token": clob_token,
                    "market_active": market.get("active", False),
                })
            
            logger.info(f"Fetched offset {offset}... Found {len(all_events)} active events so far")
            
            if len(data) < limit:
                break  # Last page
            
            offset += limit
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error at offset {offset}: {e}")
            break
    
    df = pd.DataFrame(all_events)
    
    if df.empty:
        logger.warning("No active NBA markets found!")
        return df
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Found {len(df)} active NBA markets")
    logger.info(f"{'='*70}")
    
    # Show upcoming games
    if 'game_date' in df.columns:
        future_games = df[df['game_date'] > pd.Timestamp.now(tz='UTC')]
        logger.info(f"\nUpcoming games: {len(future_games)}")
        
        if len(future_games) > 0:
            logger.info("\nNext 10 upcoming games:")
            future_games_sorted = future_games.sort_values('game_date').head(10)
            for _, row in future_games_sorted.iterrows():
                game_date_str = row['game_date'].strftime('%Y-%m-%d %H:%M UTC') if pd.notna(row['game_date']) else "Unknown"
                logger.info(f"  [{row['event_id']}] {row['title'][:60]}... | Game: {game_date_str}")
    
    return df


def test_t_minus_1_extraction_for_active(event_id: int, clob_token: str, game_time: str):
    """
    Test if we can extract T-minus 1 hour price for an ACTIVE market.
    This should work since the market is still open!
    """
    try:
        target_time = pd.to_datetime(game_time, utc=True) - timedelta(hours=1)
        target_ts = int(target_time.timestamp())
        
        url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": clob_token,
            "interval": "max",
            "endTs": target_ts + 3600,  # 1 hour after target
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
            return None
        
        return float(valid_prices.iloc[-1]['p'])
        
    except Exception as e:
        logger.error(f"Error testing extraction for event {event_id}: {e}")
        return None


if __name__ == "__main__":
    # Find active markets
    active_df = find_active_nba_markets()
    
    if active_df.empty:
        logger.error("\n❌ No active NBA markets found.")
        logger.error("This means:")
        logger.error("  1. NBA season may be over")
        logger.error("  2. No upcoming games listed on Polymarket")
        logger.error("  3. Need to wait for new markets to open")
        logger.error("\nAlternative: Use Terminal Price Analysis (see docs/PIVOT_STRATEGY.md)")
    else:
        # Save results
        output_path = "data/processed/active_nba_markets.csv"
        active_df.to_csv(output_path, index=False)
        logger.info(f"\n✓ Active markets saved to: {output_path}")
        
        logger.info("\n" + "="*70)
        logger.info("NEXT STEPS FOR PROSPECTIVE DATA COLLECTION:")
        logger.info("="*70)
        logger.info("1. Monitor these active markets")
        logger.info("2. For each game, extract T-minus 1 hour price BEFORE tip-off")
        logger.info("3. Match to sportsbook odds (from public APIs or manual collection)")
        logger.info("4. After games complete, evaluate predictions")
        logger.info("\nYou can extract T-minus 1 hour prices for ACTIVE markets!")
        logger.info("The /prices-history API works for open markets (data not purged yet).")
        
        # Test extraction on one active market if possible
        if len(active_df) > 0:
            sample = active_df.iloc[0]
            if sample['clob_token'] and sample['game_date']:
                logger.info(f"\nTesting T-minus 1 hour extraction on sample event {sample['event_id']}...")
                test_price = test_t_minus_1_extraction_for_active(
                    sample['event_id'],
                    sample['clob_token'],
                    str(sample['game_date'])
                )
                if test_price is not None:
                    logger.info(f"✓ SUCCESS! Can extract price: {test_price:.4f}")
                    logger.info("  This confirms active markets have accessible price history!")
                else:
                    logger.warning("⚠️  Could not extract price (market might be too new or game time not set)")
