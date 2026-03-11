"""
Comprehensive test script for alternative Polymarket API methods to retrieve pre-game probabilities.

This script tests multiple approaches:
1. Opening price from event startDate + initial outcomePrices
2. Daily resolution interval="1d" on prices-history
3. Hourly resolution interval="1h" on prices-history  
4. Event metadata fields (startDate, creationDate) for timing
5. Multiple market outcomes to find the correct token
6. On-chain Polygon RPC queries (if available)

Run this BEFORE pivoting the project to see if any method yields usable data.
"""

import pandas as pd
import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_event_details(event_id: int) -> Optional[Dict]:
    """Fetch full event details from Gamma API."""
    try:
        url = f"https://gamma-api.polymarket.com/events/{event_id}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {e}")
        return None


def test_method_1_opening_price(event_id: int, target_time: str) -> Optional[float]:
    """
    Method 1: Use the opening price from event startDate.
    Assumption: The outcomePrices in the event details might represent an opening snapshot.
    """
    logger.info(f"[Method 1] Testing opening price for event {event_id}")
    event_data = get_event_details(event_id)
    if not event_data:
        return None
    
    markets = event_data.get("markets", [])
    if not markets:
        return None
    
    # Check if event has startDate that's before target_time
    start_date = event_data.get("startDate")
    if start_date:
        start_dt = pd.to_datetime(start_date, utc=True)
        target_dt = pd.to_datetime(target_time, utc=True)
        
        # Only use if startDate is before target_time (market was open)
        if start_dt < target_dt:
            market = markets[0]
            outcome_prices = market.get("outcomePrices")
            if outcome_prices:
                try:
                    prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
                    if prices and len(prices) > 0:
                        prob = float(prices[0])
                        logger.info(f"  Found opening price: {prob:.4f} (startDate: {start_date})")
                        return prob
                except (json.JSONDecodeError, ValueError, IndexError):
                    pass
    
    return None


def test_method_2_daily_interval(event_id: int, target_time: str) -> Optional[float]:
    """
    Method 2: Try daily resolution interval="1d" on prices-history.
    This might return daily snapshots even for closed markets.
    """
    logger.info(f"[Method 2] Testing daily interval for event {event_id}")
    event_data = get_event_details(event_id)
    if not event_data:
        return None
    
    markets = event_data.get("markets", [])
    if not markets:
        return None
    
    market = markets[0]
    clob_token = market.get("clobToken")
    if not clob_token:
        return None
    
    try:
        url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": clob_token,
            "interval": "1d"  # Daily resolution
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 404:
            return None
        
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
            logger.warning(f"  No prices before target_time, using earliest: {hist_df.iloc[0]['p']:.4f}")
            return float(hist_df.iloc[0]['p'])
        
        prob = float(valid_prices.iloc[-1]['p'])
        logger.info(f"  Found daily price: {prob:.4f} at {valid_prices.iloc[-1]['t']}")
        return prob
        
    except Exception as e:
        logger.error(f"  Error in daily interval method: {e}")
        return None


def test_method_3_hourly_interval(event_id: int, target_time: str) -> Optional[float]:
    """
    Method 3: Try hourly resolution interval="1h" on prices-history.
    """
    logger.info(f"[Method 3] Testing hourly interval for event {event_id}")
    event_data = get_event_details(event_id)
    if not event_data:
        return None
    
    markets = event_data.get("markets", [])
    if not markets:
        return None
    
    market = markets[0]
    clob_token = market.get("clobToken")
    if not clob_token:
        return None
    
    try:
        url = "https://clob.polymarket.com/prices-history"
        params = {
            "market": clob_token,
            "interval": "1h"  # Hourly resolution
        }
        
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 404:
            return None
        
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
        
        prob = float(valid_prices.iloc[-1]['p'])
        logger.info(f"  Found hourly price: {prob:.4f} at {valid_prices.iloc[-1]['t']}")
        return prob
        
    except Exception as e:
        logger.error(f"  Error in hourly interval method: {e}")
        return None


def test_method_4_all_intervals(event_id: int, target_time: str) -> Optional[float]:
    """
    Method 4: Try all available intervals: "all", "max", "1d", "6h", "1h", "1m"
    """
    logger.info(f"[Method 4] Testing all intervals for event {event_id}")
    event_data = get_event_details(event_id)
    if not event_data:
        return None
    
    markets = event_data.get("markets", [])
    if not markets:
        return None
    
    market = markets[0]
    clob_token = market.get("clobToken")
    if not clob_token:
        return None
    
    intervals = ["all", "max", "1d", "6h", "1h", "1m"]
    target_dt = pd.to_datetime(target_time, utc=True)
    
    for interval in intervals:
        try:
            url = "https://clob.polymarket.com/prices-history"
            params = {"market": clob_token, "interval": interval}
            
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 404:
                continue
            
            resp.raise_for_status()
            data = resp.json()
            
            if not data or "history" not in data or not data["history"]:
                continue
            
            hist_df = pd.DataFrame(data["history"])
            if hist_df.empty:
                continue
            
            hist_df['t'] = pd.to_datetime(hist_df['t'], unit='s', utc=True)
            hist_df['p'] = hist_df['p'].astype(float)
            hist_df = hist_df.sort_values('t')
            
            valid_prices = hist_df[hist_df['t'] <= target_dt]
            
            if not valid_prices.empty:
                prob = float(valid_prices.iloc[-1]['p'])
                logger.info(f"  ✓ Found price with interval '{interval}': {prob:.4f}")
                return prob
                
        except Exception as e:
            continue
    
    return None


def test_method_5_event_metadata(event_id: int, target_time: str) -> Optional[Dict]:
    """
    Method 5: Extract all available timing metadata from event.
    Returns dict with startDate, endDate, creationDate, etc.
    """
    logger.info(f"[Method 5] Extracting event metadata for event {event_id}")
    event_data = get_event_details(event_id)
    if not event_data:
        return None
    
    metadata = {
        "startDate": event_data.get("startDate"),
        "endDate": event_data.get("endDate"),
        "createdAt": event_data.get("createdAt"),
        "hasMarkets": len(event_data.get("markets", [])) > 0,
    }
    
    if event_data.get("markets"):
        market = event_data["markets"][0]
        metadata["marketStartDate"] = market.get("startDate")
        metadata["marketEndDate"] = market.get("endDateIso")
        metadata["hasOutcomePrices"] = bool(market.get("outcomePrices"))
    
    return metadata


def test_all_methods(event_id: int, target_time: str) -> Dict:
    """
    Test all methods and return results.
    """
    results = {
        "event_id": event_id,
        "target_time": target_time,
        "method_1_opening": None,
        "method_2_daily": None,
        "method_3_hourly": None,
        "method_4_all_intervals": None,
        "method_5_metadata": None,
        "any_success": False
    }
    
    # Test each method
    results["method_1_opening"] = test_method_1_opening_price(event_id, target_time)
    time.sleep(0.2)  # Rate limiting
    
    results["method_2_daily"] = test_method_2_daily_interval(event_id, target_time)
    time.sleep(0.2)
    
    results["method_3_hourly"] = test_method_3_hourly_interval(event_id, target_time)
    time.sleep(0.2)
    
    results["method_4_all_intervals"] = test_method_4_all_intervals(event_id, target_time)
    time.sleep(0.2)
    
    results["method_5_metadata"] = test_method_5_event_metadata(event_id, target_time)
    
    # Check if any method succeeded
    results["any_success"] = any([
        results["method_1_opening"] is not None,
        results["method_2_daily"] is not None,
        results["method_3_hourly"] is not None,
        results["method_4_all_intervals"] is not None,
    ])
    
    return results


def run_comprehensive_test(sample_size: int = 20):
    """
    Test all methods on a sample of events from master_events.csv.
    """
    logger.info("="*70)
    logger.info("COMPREHENSIVE POLYMARKET ALTERNATIVE METHODS TEST")
    logger.info("="*70)
    
    # Load master events
    master_path = "data/processed/master_events.csv"
    try:
        df = pd.read_csv(master_path)
        logger.info(f"Loaded {len(df)} events from {master_path}")
    except FileNotFoundError:
        logger.error(f"File not found: {master_path}")
        return
    
    if df.empty:
        logger.error("Master events file is empty!")
        return
    
    # Sample events (stratified by year if possible)
    sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)
    logger.info(f"Testing {len(sample_df)} sample events...\n")
    
    results_list = []
    
    for idx, row in sample_df.iterrows():
        event_id = row['event_id']
        target_time = row['target_snapshot_time']
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing Event {idx+1}/{len(sample_df)}: ID={event_id}")
        logger.info(f"Target Time: {target_time}")
        logger.info(f"Game: {row.get('home_team', '?')} vs {row.get('away_team', '?')}")
        logger.info(f"{'='*70}")
        
        result = test_all_methods(event_id, target_time)
        results_list.append(result)
        
        # Summary for this event
        if result["any_success"]:
            logger.info(f"✓ SUCCESS: At least one method returned a price")
            for method, value in result.items():
                if method.startswith("method_") and value is not None and method != "method_5_metadata":
                    logger.info(f"  - {method}: {value:.4f}")
        else:
            logger.warning(f"✗ FAILED: No method returned a price")
        
        time.sleep(0.5)  # Rate limiting between events
    
    # Aggregate results
    results_df = pd.DataFrame(results_list)
    
    logger.info("\n" + "="*70)
    logger.info("AGGREGATE RESULTS")
    logger.info("="*70)
    
    success_counts = {
        "Method 1 (Opening)": results_df["method_1_opening"].notna().sum(),
        "Method 2 (Daily)": results_df["method_2_daily"].notna().sum(),
        "Method 3 (Hourly)": results_df["method_3_hourly"].notna().sum(),
        "Method 4 (All Intervals)": results_df["method_4_all_intervals"].notna().sum(),
        "Any Method": results_df["any_success"].sum(),
    }
    
    for method, count in success_counts.items():
        pct = (count / len(results_df)) * 100
        logger.info(f"{method}: {count}/{len(results_df)} ({pct:.1f}%)")
    
    # Save detailed results
    output_path = "data/processed/alternative_methods_test_results.csv"
    results_df.to_csv(output_path, index=False)
    logger.info(f"\nDetailed results saved to: {output_path}")
    
    # Save summary
    summary_path = "data/processed/alternative_methods_summary.txt"
    with open(summary_path, 'w') as f:
        f.write("POLYMARKET ALTERNATIVE METHODS TEST SUMMARY\n")
        f.write("="*70 + "\n\n")
        f.write(f"Test Date: {datetime.now().isoformat()}\n")
        f.write(f"Sample Size: {len(results_df)}\n\n")
        f.write("Success Rates:\n")
        for method, count in success_counts.items():
            pct = (count / len(results_df)) * 100
            f.write(f"  {method}: {count}/{len(results_df)} ({pct:.1f}%)\n")
        f.write("\n" + "="*70 + "\n")
        f.write("RECOMMENDATION:\n")
        if success_counts["Any Method"] > len(results_df) * 0.5:
            f.write("✓ At least one method works for >50% of events.\n")
            f.write("  Consider using the best-performing method for the full dataset.\n")
        else:
            f.write("✗ No method works reliably (>50% success rate).\n")
            f.write("  Consider pivoting the project (see pivot_strategy.md).\n")
    
    logger.info(f"Summary saved to: {summary_path}")
    
    return results_df


if __name__ == "__main__":
    # Test on 20 sample events
    results = run_comprehensive_test(sample_size=20)
