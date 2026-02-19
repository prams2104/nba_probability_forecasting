# test_pipeline.py
import pandas as pd
from src.matching.fuzzy_match import match_teams, clean_team_name

def run_matching_diagnostics():
    print("--- STARTING FUZZY MATCH DIAGNOSTICS ---\n")
    
    # 1. Mock Sportsbook Data (The "Ground Truth" schema)
    sportsbook_teams = [
        "Los Angeles Lakers",
        "Philadelphia 76ers",
        "Minnesota Timberwolves",
        "Golden State Warriors",
        "New York Knicks"
    ]
    
    # 2. Mock Polymarket Data (The messy API schema)
    polymarket_teams = [
        "LA Lakers",           # Tests Token Sort Ratio
        "76ers",               # Tests the Manual Alias Table
        "Wolves",              # Tests the Manual Alias Table
        "GS Warriors",         # Tests partial string matching
        "NY Knicks"            # Tests partial string matching
    ]
    
    print("Target Threshold: >= 90.0%\n")
    
    # 3. Execution Loop
    results = []
    for poly_team in polymarket_teams:
        matched_sb, score = match_teams(poly_team, sportsbook_teams)
        
        # Check if it passes your strict proposal threshold
        status = "PASS" if score >= 90 else "FAIL (Manual Review Needed)"
        
        results.append({
            "Polymarket (Input)": poly_team,
            "Cleaned Internal": clean_team_name(poly_team),
            "Sportsbook (Matched)": matched_sb,
            "Score": round(score, 2),
            "Status": status
        })
    
    # 4. Display Results cleanly
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    print("\n--- DIAGNOSTICS COMPLETE ---")

if __name__ == "__main__":
    run_matching_diagnostics()