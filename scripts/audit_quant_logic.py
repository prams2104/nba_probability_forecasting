import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add the project root to the Python path to allow importing from 'src'
sys.path.append(str(Path(__file__).parent.parent))

from src.processing.quant_logic import apply_no_vig_probabilities

# --- Main Audit Execution ---
if __name__ == "__main__":
    print("--- Starting Audit of src.processing.quant_logic.py ---")
    print("--- Using pre-calculated ground truth from online calculator ---")

    # 1. Build the dataset of known inputs and expected outputs.
    # The expected probabilities are hardcoded from the user-provided table.
    test_cases = pd.DataFrame([
        # Test Case 1: Standard Symmetric Odds (-110 / -110)
        {'test_name': 'Symmetric Odds', 'home_odds': -110, 'away_odds': -110, 'expected_home': 0.50, 'expected_away': 0.50},

        # Test Case 2: Clear Favorite vs. Underdog (-500 / +400)
        {'test_name': 'Favorite vs Underdog', 'home_odds': -500, 'away_odds': 400, 'expected_home': 0.81, 'expected_away': 0.19},
        
        # Test Case 3: Near-Even Money (-120 / +100)
        {'test_name': 'Near-Even Money', 'home_odds': -120, 'away_odds': 100, 'expected_home': 0.52, 'expected_away': 0.48},

        # Test Case 4: No Vig / Fair Odds (-400 / +400)
        # Note: The online calculator gives 80/20, but true fair odds are 80/20. Let's test the math.
        # Implied probabilities are 400/(400+100)=0.8 and 100/(400+100)=0.2. Overround is 1.0. So fair probs are 0.8 and 0.2.
        {'test_name': 'Fair Odds (No Vig)', 'home_odds': -400, 'away_odds': 400, 'expected_home': 0.80, 'expected_away': 0.20},
        
        # Test Case 5: Extreme Favorite (-2000 / +1500)
        {'test_name': 'Extreme Favorite', 'home_odds': -2000, 'away_odds': 1500, 'expected_home': 0.94, 'expected_away': 0.06},

        # Test Case 6: Invalid Zero Odds (Edge Case)
        # Tests robustness against corrupted or invalid '0' data.
        {'test_name': 'Invalid Zero Odds', 'home_odds': -200, 'away_odds': 0, 'expected_home': 1.0, 'expected_away': 0.0},
    ])
    print(f"Loaded {len(test_cases)} test cases.")

    # 2. Run the production function on the test data
    results_df = apply_no_vig_probabilities(test_cases.copy())

    # 3. Compare production results against the hardcoded ground truth
    print("\n--- Running Assertions ---")
    all_tests_passed = True
    for index, test in test_cases.iterrows():
        test_name = test['test_name']
        
        # Get the "ground truth" from our hardcoded table
        expected_home_prob = test['expected_home']
        expected_away_prob = test['expected_away']
        
        # Get the actual result from the production function
        actual_home_prob = results_df.loc[index, 'fair_prob_home']
        actual_away_prob = results_df.loc[index, 'fair_prob_away']
        
        # Check if the actual results are close enough to the expected results.
        # We use a tolerance (atol=0.01) to account for rounding differences in the online calculator.
        home_prob_ok = np.isclose(expected_home_prob, actual_home_prob, atol=0.01)
        away_prob_ok = np.isclose(expected_away_prob, actual_away_prob, atol=0.01)

        if home_prob_ok and away_prob_ok:
            print(f"✅ PASSED: '{test_name}'")
        else:
            all_tests_passed = False
            print(f"❌ FAILED: '{test_name}'")
            print(f"  Input Odds (H/A): {test['home_odds']} / {test['away_odds']}")
            print(f"  Expected (H/A): {expected_home_prob:.2f} / {expected_away_prob:.2f}")
            print(f"  Actual   (H/A): {actual_home_prob:.4f} / {actual_away_prob:.4f}\n")

    # --- Final Summary ---
    print("\n--- Audit Summary ---")
    if all_tests_passed:
        print("🎉 All test cases passed successfully!")
    else:
        print("🔥 Some test cases failed. Please review the output above.")
    print("-----------------------\n")
