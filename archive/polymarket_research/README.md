# Archive: Polymarket Research & Exploratory Scripts

This folder contains **archived** scripts from our exploratory work on Polymarket prediction markets. They are preserved as evidence of the data engineering challenges we encountered and the diagnostic work we performed.

## Why These Are Archived

- **Polymarket API Limitation:** The CLOB API purges minute-by-minute order book data for closed markets; historical T-minus 1 hour extraction is not possible.
- **No Individual NBA Games:** Polymarket's "NBA" tag returns season-long futures (champion, MVP, etc.) and other sports—not individual NBA game markets.
- **Project Pivot:** We pivoted to **Option A: Sportsbook-Only Evaluation** using our 512 matched historical games.

## Contents (Reference Only)

| Script | Purpose |
|--------|---------|
| `price_history.py` | Attempted T-minus 1 hour price extraction via CLOB `/prices-history` (returns empty for closed markets). |
| `verify_nba_game_markets.py` | Verified that Polymarket has 0 individual NBA game markets among active "NBA"-tagged events. |
| `test_alternative_polymarket_methods.py` | Tested opening prices, daily/hourly intervals; confirmed terminal prices only. |
| `extract_opening_prices.py` | Opening-price extraction attempt; Gamma `outcomePrices` are terminal (0/1) for closed markets. |
| `find_active_nba_markets.py` | Fetched active Polymarket events tagged NBA; found mixed content, no NBA games. |
| `collect_prospective_predictions.py` | Prospective collection design; no NBA game markets to match. |
| `collect_from_odds_api.py` | Fetched NBA games from The Odds API; no Polymarket matches. |
| `diagnose_price_issue.py` | Confirmed Method 1 "opening" prices are terminal (0.0/1.0). |
| `test_odds_api.py` | Validated The Odds API integration. |
| `update_outcomes.py` | Outcome-update logic for prospective predictions. |

## Running These Scripts

These scripts are **not** part of the main pipeline. Imports and paths may assume the previous layout; they are kept for documentation and reproducibility of our findings. The critical path lives in `src/` and `main.py`.
