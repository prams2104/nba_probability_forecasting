# Phase 2 Audit Notes
**Author:** Karthik  
**Date:** 27/02/2026

## quant_logic.py — No-Vig Math Audit

**Verdict: PASS** — Math is correct.

Verified by hand using real game from master_events.csv:
DAL vs PHX, May 8 2022 — away_odds: -150, home_odds: +130

- implied_prob_home = 100 / (130 + 100) = 0.4348
- implied_prob_away = 150 / (150 + 100) = 0.6000
- overround = 0.4348 + 0.6000 = 1.0348
- fair_prob_home = 0.4348 / 1.0348 = 0.4202
- fair_prob_away = 0.6000 / 1.0348 = 0.5798
- sum = 0.4202 + 0.5798 = 1.0

Matches quant_logic.py output in master_events.csv exactly.

## Issue Flagged

No input validation in american_to_implied().

- NaN odds → silently produces NaN fair_prob_home → corrupts Brier Score
- odds == 0 → returns 0.0, not a valid moneyline value

Issue flagged as comment in quant_logic.py. Fix recommended but not 
implemented — decision left to Pramesh or Phase 3 team to uncomment.

## Recommendation for Phase 3

Filter out any rows where fair_prob_home is NaN before computing 
Brier Score and Log Loss. Otherwise those rows will silently corrupt 
the final evaluation numbers.