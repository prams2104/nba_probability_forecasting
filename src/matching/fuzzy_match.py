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
    poly_clean = clean_event_name(poly_event)
    sportsbook_clean_list = [clean_event_name(t) for t in sportsbook_events_list]
    
    best_match = process.extractOne(poly_clean, sportsbook_clean_list, scorer=fuzz.token_sort_ratio)
    
    if best_match:
        matched_name, score, index = best_match
        return sportsbook_events_list[index], score
    return None, 0

def audit_matches(df, score_col='matching_score'):
    manual_review_df = df[(df[score_col] >= 80) & (df[score_col] < 95)]
    manual_review_df.to_csv('data/processed/manual_review_flagged.csv', index=False)
    audit_sample = df.sample(frac=0.05, random_state=42)
    audit_sample.to_csv('data/processed/5_percent_audit_log.csv', index=False)
    return manual_review_df, audit_sample