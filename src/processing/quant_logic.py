import pandas as pd
import numpy as np

def american_to_implied(odds):
    """Converts American Odds to raw implied probability."""
    # AUDIT NOTE (Karthik/Priyansh): No handling for NaN or 0 odds values.
    # NaN will silently propagate to fair_prob_home and corrupt Brier scores.
    # odds == 0 returns 0.0 which is not a valid moneyline value.
    # We will handle these edge cases in the apply_no_vig_probabilities function by checking for NaN after conversion and assigning probabilities accordingly.
    #
    if odds == 0:
        return np.nan
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

    # 4. Post-process to handle invalid odds (where one of the odds was 0)
    # If home implied probability is NaN, it means home_odds were invalid. Away team wins.
    home_nan_mask = df['implied_prob_home'].isna()
    df.loc[home_nan_mask, 'fair_prob_home'] = 0.0
    df.loc[home_nan_mask, 'fair_prob_away'] = 1.0

    # If away implied probability is NaN, it means away_odds were invalid. Home team wins.
    away_nan_mask = df['implied_prob_away'].isna()
    df.loc[away_nan_mask, 'fair_prob_home'] = 1.0
    df.loc[away_nan_mask, 'fair_prob_away'] = 0.0
    
    return df