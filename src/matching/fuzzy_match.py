import pandas as pd
import re
from rapidfuzz import fuzz, process

# Manual alias table for variations that defeat fuzzy matching 
ALIAS_TABLE = {
    "76ers": "philadelphia 76ers",
    "sixers": "philadelphia 76ers",
    "cavs": "cleveland cavaliers",
    "wolves": "minnesota timberwolves",
    "mavs": "dallas mavericks"
}

def clean_team_name(name):
    """Normalizes team names by lowercasing and removing punctuation/suffixes."""
    name = str(name).lower()
    # Remove standard punctuation
    name = re.sub(r'[^\w\s]', '', name)
    # Remove common irrelevant suffixes
    name = re.sub(r'\b(fc|city|team)\b', '', name)
    name = name.strip()
    
    # Apply manual alias table override
    for key, value in ALIAS_TABLE.items():
        if key in name:
            return value
    return name

def match_teams(poly_team, sportsbook_teams_list):
    """
    Uses RapidFuzz Token Sort Ratio to match teams. 
    Token Sort handles "LA Lakers" vs "Lakers LA" gracefully.
    """
    poly_clean = clean_team_name(poly_team)
    sportsbook_clean_list = [clean_team_name(t) for t in sportsbook_teams_list]
    
    # Extract the best match
    best_match = process.extractOne(
        poly_clean, 
        sportsbook_clean_list, 
        scorer=fuzz.token_sort_ratio
    )
    
    if best_match:
        matched_name, score, index = best_match
        original_sportsbook_name = sportsbook_teams_list[index]
        return original_sportsbook_name, score
    return None, 0

def audit_matches(df, score_col='matching_score'):
    """
    Generates the audit deliverables: 
    1. Flags 80-95% for manual review.
    2. Random 5% sample audit log to validate the >90% threshold[cite: 14, 19].
    """
    # Flag matches in the ambiguous 80-95% zone
    manual_review_df = df[(df[score_col] >= 80) & (df[score_col] < 95)]
    manual_review_df.to_csv('data/processed/manual_review_flagged.csv', index=False)
    
    # 5% random sample audit of all matched events [cite: 14]
    audit_sample = df.sample(frac=0.05, random_state=42)
    audit_sample.to_csv('data/processed/5_percent_audit_log.csv', index=False)
    
    return manual_review_df, audit_sample