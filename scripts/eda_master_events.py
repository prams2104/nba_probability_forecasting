import pandas as pd
import numpy as np

def analyze_master_events(filepath):
    """
    Performs an EDA on the master_events.csv file.
    """
    print(f"--- Analyzing {filepath} ---")
    
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
        print("Please ensure the file is in the correct directory.")
        return

    # 2. Calculate the average sportsbook vig
    # The vig is the overround - 1. The result is a percentage.
    average_vig = (df['sportsbook_overround'] - 1).mean() * 100
    print("\n--- Sportsbook Vig Analysis ---")
    if pd.notna(average_vig):
        print(f"Average Sportsbook Vig: {average_vig:.2f}%")
    else:
        print("Could not calculate the average sportsbook vig. The 'sportsbook_overround' column may have issues.")

    # 3. Check for missing odds edge cases
    print("\n--- Missing Odds Analysis ---")
    missing_home_odds = df['home_odds'].isnull().sum()
    missing_away_odds = df['away_odds'].isnull().sum()
    zero_home_odds = (df['home_odds'] == 0).sum()
    zero_away_odds = (df['away_odds'] == 0).sum()

    print(f"Number of rows with missing 'home_odds': {missing_home_odds}")
    print(f"Number of rows with missing 'away_odds': {missing_away_odds}")
    print(f"Number of rows with 'home_odds' equal to 0: {zero_home_odds}")
    print(f"Number of rows with 'away_odds' equal to 0: {zero_away_odds}")
    
    # Check for cases where odds are present but probabilities are not
    probs_nan = df[(df['home_odds'].notna() & df['away_odds'].notna()) & (df['fair_prob_home'].isna() | df['fair_prob_away'].isna())]
    print(f"Number of rows with valid odds but missing fair probabilities: {len(probs_nan)}")
    if not probs_nan.empty:
        print("Example rows with missing probabilities:")
        print(probs_nan[['home_odds', 'away_odds', 'fair_prob_home', 'fair_prob_away']].head())

    print("\n--- EDA Summary ---")
    if missing_home_odds > 0 or missing_away_odds > 0 or zero_home_odds > 0 or zero_away_odds > 0 or len(probs_nan) > 0:
        print("Found some edge cases with missing or invalid odds. Please review the analysis above.")
    else:
        print("No major edge cases found regarding missing or invalid odds.")
    
    print("\nRegarding the dropped data at T-1 hour:")
    print("The raw Kaggle data file (e.g., nba_2008-2025.csv) is not available in the 'data/raw/' directory.")
    print("Therefore, I cannot evaluate how much data was dropped at the T-minus 1 hour snapshot.")


if __name__ == "__main__":
    analyze_master_events('data/processed/master_events.csv')
