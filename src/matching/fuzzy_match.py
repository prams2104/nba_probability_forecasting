"""
NBA team name normalization and fuzzy event matching.

Provides a 30-team alias table, cleaning utilities, and fuzzy matching
to align Polymarket event strings with Kaggle sportsbook event names.
"""

import pandas as pd
import re
from rapidfuzz import fuzz, process

# Comprehensive 30-Team NBA Alias Table (Now including all standalone nicknames)
ALIAS_TABLE = {
    "bos": "boston celtics", "celtics": "boston celtics",
    "bkn": "brooklyn nets", "nets": "brooklyn nets",
    "ny": "new york knicks", "nyk": "new york knicks", "knicks": "new york knicks",
    "phi": "philadelphia 76ers", "philly": "philadelphia 76ers", "sixers": "philadelphia 76ers", "76ers": "philadelphia 76ers",
    "tor": "toronto raptors", "raptors": "toronto raptors",
    "chi": "chicago bulls", "bulls": "chicago bulls",
    "cle": "cleveland cavaliers", "cavs": "cleveland cavaliers", "cavaliers": "cleveland cavaliers",
    "det": "detroit pistons", "pistons": "detroit pistons",
    "ind": "indiana pacers", "pacers": "indiana pacers",
    "mil": "milwaukee bucks", "bucks": "milwaukee bucks",
    "atl": "atlanta hawks", "hawks": "atlanta hawks",
    "cha": "charlotte hornets", "hornets": "charlotte hornets",
    "mia": "miami heat", "heat": "miami heat",
    "orl": "orlando magic", "magic": "orlando magic",
    "was": "washington wizards", "wsh": "washington wizards", "wizards": "washington wizards",
    "den": "denver nuggets", "nuggets": "denver nuggets",
    "min": "minnesota timberwolves", "wolves": "minnesota timberwolves", "t-wolves": "minnesota timberwolves", "timberwolves": "minnesota timberwolves",
    "okc": "oklahoma city thunder", "thunder": "oklahoma city thunder",
    "por": "portland trail blazers", "blazers": "portland trail blazers", "trail blazers": "portland trail blazers",
    "uta": "utah jazz", "jazz": "utah jazz",
    "gs": "golden state warriors", "gsw": "golden state warriors", "warriors": "golden state warriors",
    "la clippers": "los angeles clippers", "lac": "los angeles clippers", "clippers": "los angeles clippers",
    "la lakers": "los angeles lakers", "lal": "los angeles lakers", "lakers": "los angeles lakers",
    "phx": "phoenix suns", "suns": "phoenix suns",
    "sac": "sacramento kings", "kings": "sacramento kings",
    "dal": "dallas mavericks", "mavs": "dallas mavericks", "mavericks": "dallas mavericks",
    "hou": "houston rockets", "rockets": "houston rockets",
    "mem": "memphis grizzlies", "grizzlies": "memphis grizzlies",
    "no pelicans": "new orleans pelicans", "nop": "new orleans pelicans", "pelicans": "new orleans pelicans", "no": "new orleans pelicans",
    "sa spurs": "san antonio spurs", "sas": "san antonio spurs", "sa": "san antonio spurs", "spurs": "san antonio spurs"
}

def clean_team_name(name):
    """
    Normalize a raw team name string to a canonical full-name form.

    Lowercases, strips punctuation, removes common filler words (fc, city, team),
    then resolves the result against ALIAS_TABLE. If no alias matches, returns
    the cleaned string unchanged.

    Args:
        name: Raw team name (abbreviation, nickname, or full name).

    Returns:
        Canonical full team name (e.g. "min" -> "minnesota timberwolves").
    """
    name = str(name).lower()
    name = re.sub(r'[^\w\s]', '', name).strip()
    name = re.sub(r'\b(fc|city|team)\b', '', name).strip()
    if name in ALIAS_TABLE:
        return ALIAS_TABLE[name]
    for key, value in ALIAS_TABLE.items():
        if re.search(r'\b' + key + r'\b', name):
            return value
    return name

def clean_event_name(event_string):
    """
    Normalize a raw matchup string into a canonical, order-independent event key.

    Splits on ' vs ' or '-', cleans each team name via clean_team_name, then
    sorts the two names alphabetically so "A vs B" and "B vs A" produce the
    same key. Falls back to clean_team_name if no separator is found.

    Args:
        event_string: Raw event title (e.g. "Timberwolves vs. OKC Thunder").

    Returns:
        Canonical event key (e.g. "minnesota timberwolves vs oklahoma city thunder").
    """
    event_string = str(event_string).lower()
    
    # FIX: Normalize punctuation BEFORE splitting so "vs." becomes "vs"
    event_string = event_string.replace('vs.', 'vs')
    
    if ' vs ' in event_string:
        teams = event_string.split(' vs ')
    elif '-' in event_string:
        teams = event_string.split('-')
    else:
        return clean_team_name(event_string)
        
    if len(teams) == 2:
        team1 = clean_team_name(teams[0])
        team2 = clean_team_name(teams[1])
        sorted_teams = sorted([team1, team2])
        return f"{sorted_teams[0]} vs {sorted_teams[1]}"
    return event_string

def match_teams(poly_event, sportsbook_events_list):
    """
    Fuzzy-match a Polymarket event title to the closest sportsbook event name.

    Cleans both strings, then uses rapidfuzz token_sort_ratio to find the best
    match in sportsbook_events_list. Returns the original (uncleaned) sportsbook
    event name and its similarity score.

    Args:
        poly_event: Raw Polymarket event title string.
        sportsbook_events_list: List of raw sportsbook event name strings.

    Returns:
        Tuple of (matched_sportsbook_event, score). Returns (None, 0) if no
        match is found.
    """
    poly_clean = clean_event_name(poly_event)
    sportsbook_clean_list = [clean_event_name(t) for t in sportsbook_events_list]
    
    best_match = process.extractOne(poly_clean, sportsbook_clean_list, scorer=fuzz.token_sort_ratio)
    
    if best_match:
        matched_name, score, index = best_match
        return sportsbook_events_list[index], score
    return None, 0

def audit_matches(df, score_col='matching_score', output_dir='data/processed'):
    """
    Generate audit outputs for manual review of fuzzy match quality.

    Writes two CSV files to output_dir:
    - manual_review_flagged.csv: rows with score in [80, 95) — borderline matches
      that warrant human inspection.
    - 5_percent_audit_log.csv: a random 5% sample of all matches for spot-checking.

    Args:
        df: DataFrame containing match results with a similarity score column.
        score_col: Name of the column holding similarity scores (default 'matching_score').
        output_dir: Directory to write audit CSVs (default 'data/processed').

    Returns:
        Tuple of (manual_review_df, audit_sample_df).
    """
    manual_review_df = df[(df[score_col] >= 80) & (df[score_col] < 95)]
    manual_review_df.to_csv(f'{output_dir}/manual_review_flagged.csv', index=False)
    audit_sample = df.sample(frac=0.05, random_state=42)
    audit_sample.to_csv(f'{output_dir}/5_percent_audit_log.csv', index=False)
    return manual_review_df, audit_sample