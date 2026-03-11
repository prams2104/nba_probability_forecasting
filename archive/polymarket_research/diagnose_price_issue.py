"""
Diagnostic script to verify that Method 1 is returning terminal prices, not opening prices.

This confirms the issue: Polymarket's outcomePrices for closed markets are terminal (0.0/1.0),
not pre-game probabilities.
"""

import pandas as pd
import requests
import json

def check_if_terminal_prices():
    """Check if the prices from Method 1 are terminal (0.0/1.0) or actual probabilities."""
    
    # Load test results
    df = pd.read_csv('data/processed/alternative_methods_test_results.csv')
    
    print("="*70)
    print("DIAGNOSIS: Are Method 1 Prices Terminal or Opening?")
    print("="*70)
    
    # Analyze the distribution
    prices = df['method_1_opening'].dropna()
    
    print(f"\nTotal prices extracted: {len(prices)}")
    print(f"\nPrice Distribution:")
    print(f"  Mean: {prices.mean():.4f}")
    print(f"  Std:  {prices.std():.4f}")
    print(f"  Min:  {prices.min():.4f}")
    print(f"  Max:  {prices.max():.4f}")
    
    print(f"\nValue Counts:")
    value_counts = prices.value_counts().sort_index()
    for val, count in value_counts.items():
        print(f"  {val:.6f}: {count} events")
    
    # Check if values are binary (terminal)
    binary_values = prices[prices.isin([0.0, 1.0])]
    near_binary = prices[(prices < 0.01) | (prices > 0.99)]
    
    print(f"\n{'='*70}")
    print("ANALYSIS:")
    print(f"{'='*70}")
    print(f"Values exactly 0.0 or 1.0: {len(binary_values)}/{len(prices)} ({len(binary_values)/len(prices)*100:.1f}%)")
    print(f"Values near 0.0 or 1.0 (<0.01 or >0.99): {len(near_binary)}/{len(prices)} ({len(near_binary)/len(prices)*100:.1f}%)")
    
    if len(binary_values) / len(prices) > 0.8:
        print("\n❌ VERDICT: These are TERMINAL PRICES (final outcomes), not opening prices!")
        print("   - Polymarket stores terminal prices (0.0 for loser, 1.0 for winner) for closed markets")
        print("   - These cannot be used for pre-game prediction accuracy evaluation")
        print("   - You need to pivot to a different approach")
    elif len(near_binary) / len(prices) > 0.8:
        print("\n⚠️  VERDICT: These appear to be TERMINAL PRICES (very close to 0.0/1.0)")
        print("   - The values near 1.0 (0.999999...) are likely rounding artifacts")
        print("   - These represent final outcomes, not pre-game probabilities")
    else:
        print("\n✓ VERDICT: These might be actual probabilities!")
        print("   - However, given the context, they're likely still terminal prices")
        print("   - Need to verify by checking if they match game outcomes")
    
    # Check a specific event to verify
    print(f"\n{'='*70}")
    print("SAMPLE VERIFICATION:")
    print(f"{'='*70}")
    
    # Load master events to check outcomes
    try:
        master_df = pd.read_csv('data/processed/master_events.csv')
        
        # Merge test results with master events
        merged = df.merge(master_df[['event_id', 'home_team', 'away_team', 'score_home', 'score_away']], 
                         on='event_id', how='left')
        
        # Check if prices match outcomes
        merged['home_won'] = (merged['score_home'] > merged['score_away']).astype(int)
        merged['price_matches_outcome'] = (
            ((merged['method_1_opening'] == 1.0) & (merged['home_won'] == 1)) |
            ((merged['method_1_opening'] == 0.0) & (merged['home_won'] == 0))
        )
        
        matches = merged['price_matches_outcome'].sum()
        total = merged['price_matches_outcome'].notna().sum()
        
        print(f"\nPrice matches game outcome: {matches}/{total} ({matches/total*100:.1f}%)")
        
        if matches / total > 0.9:
            print("\n❌ CONFIRMED: Prices are TERMINAL (they match final outcomes)")
            print("   These cannot be used for prediction accuracy evaluation!")
        else:
            print("\n⚠️  Prices don't perfectly match outcomes, but still likely terminal")
            
        # Show examples
        print("\nExample events:")
        sample = merged[['event_id', 'home_team', 'away_team', 'method_1_opening', 'home_won']].head(5)
        for _, row in sample.iterrows():
            outcome = "Home won" if row['home_won'] == 1 else "Away won"
            price_type = "Terminal (1.0)" if row['method_1_opening'] == 1.0 else "Terminal (0.0)" if row['method_1_opening'] == 0.0 else f"Prob ({row['method_1_opening']:.4f})"
            print(f"  Event {row['event_id']}: {row['away_team']} @ {row['home_team']} | Price: {price_type} | Outcome: {outcome}")
            
    except FileNotFoundError:
        print("\n⚠️  Could not load master_events.csv for verification")
    
    print(f"\n{'='*70}")
    print("RECOMMENDATION:")
    print(f"{'='*70}")
    print("Since Method 1 returns terminal prices and Methods 2-4 failed:")
    print("  1. ❌ Cannot use T-minus 1 hour prices (data purged)")
    print("  2. ❌ Cannot use opening prices from outcomePrices (they're terminal)")
    print("  3. ✅ PIVOT REQUIRED: See docs/PIVOT_STRATEGY.md")
    print("\nBest options:")
    print("  Option A: Active Future Events (prospective data collection)")
    print("  Option B: Terminal Price Analysis (less interesting academically)")
    print("  Option C: Acknowledge limitation and use sportsbook-only analysis")

if __name__ == "__main__":
    check_if_terminal_prices()
