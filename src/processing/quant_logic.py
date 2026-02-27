import pandas as pd
    
def american_to_implied(odds):
    """Converts American Odds to raw implied probability."""
    # AUDIT NOTE (Karthik): No handling for NaN or 0 odds values.
    # NaN will silently propagate to fair_prob_home and corrupt Brier scores.
    # odds == 0 returns 0.0 which is not a valid moneyline value.
    #
    # SUGGESTED FIX (commented out — decision left to Pramesh or Phase 3 team):
    # if pd.isna(odds) or odds == 0:
    #     return None
    #
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def apply_no_vig_probabilities(df):
    """
    Calculates the 'Fair' probability by removing the sportsbook overround.
    Handles vectorized operations across the entire dataframe.
    """
    # 1. Convert American Odds to implied probability
    df['implied_prob_home'] = df['home_odds'].apply(american_to_implied)
    df['implied_prob_away'] = df['away_odds'].apply(american_to_implied)
    
    # 2. Calculate the "Vig" (overround)
    df['sportsbook_overround'] = df['implied_prob_home'] + df['implied_prob_away']
    
    # 3. Normalize to True Fair Probabilities (Sum to 1.0)
    df['fair_prob_home'] = df['implied_prob_home'] / df['sportsbook_overround']
    df['fair_prob_away'] = df['implied_prob_away'] / df['sportsbook_overround']
    
    return df