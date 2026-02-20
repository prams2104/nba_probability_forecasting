# Quantitative Forecasting: Sportsbook Calibration & Prediction Market API Constraints

**ECE 143 — Programming and Data Analysis** **Group Project | Phase 1 Handoff**

---

## Project Title

**Quantitative Forecasting: Sportsbook Calibration & Prediction Market API Constraints**

---

## Executive Summary

This project evaluates how well **traditional sportsbooks** predict NBA game outcomes when their built-in profit margin (the "vig") is removed. The original goal was to compare these **centralized** sportsbook predictions with **decentralized** prediction market (Polymarket) probabilities at a fixed time—**T-minus 1 hour** before tip-off—using proper scoring rules (Brier Score, Log Loss) and calibration analysis.

We built a full pipeline that:

1. Loads and preprocesses **Kaggle NBA sportsbook odds** (2008–2025), computes **no-vig** implied probabilities, and defines a **T-minus 1 hour** snapshot.
2. Fetches **Polymarket** event data via the Gamma API and uses **fuzzy matching** (`rapidfuzz` + a 30-team alias dictionary) to align messy event strings with Kaggle’s format.
3. Uses **temporal synchronization** (`pd.merge_asof`) to align sportsbook and Polymarket data in time, yielding **512 matched historical NBA games**.

During extraction we discovered that **Polymarket’s API does not expose historical minute-by-minute order book data for closed markets** (data is purged), and that Polymarket does not list **individual NBA game** markets—only season-long futures. We therefore **pivoted to Option A: Sportsbook-Only Evaluation**. The pipeline now focuses on evaluating sportsbook accuracy (Brier Score, Log Loss, and a **Probability Calibration Curve**) on the 512 temporally synchronized games, while documenting the API constraints as a central engineering finding.

---

## The Pipeline & API Pivot

### Pipeline Overview

1. **Kaggle data** - Load `data/raw/nba_2008-2025.csv` (or equivalent).  
   - Derive `target_snapshot_time` = game time minus 1 hour.  
   - Build join key: `sportsbook_event_name` = `"home_team vs away_team"` (e.g. `"min vs okc"`).

2. **Polymarket (Gamma) extraction** - Paginated requests to `https://gamma-api.polymarket.com/events` (tag=NBA, closed=true).  
   - For each event: `event_id`, `poly_event_name`, `timestamp` (e.g. endDate), and terminal `outcomePrices` (not usable for pre-game probabilities).

3. **Fuzzy matching** - **rapidfuzz** with a **30-team alias dictionary** (e.g. "Timberwolves" → "minnesota timberwolves", "min" → "minnesota timberwolves").  
   - Match Polymarket event titles to `sportsbook_event_name`; keep matches above a **90% similarity** threshold.

4. **Temporal synchronization** - **`pd.merge_asof`** (direction=`"backward"`) so that, for each sportsbook row (keyed by `sportsbook_event_name` and `target_snapshot_time`), we attach the **latest** Polymarket row with the same event key and `timestamp <= target_snapshot_time`.  
   - This yields one row per game with sportsbook odds and a matched Polymarket event (for metadata only; we do not use Polymarket probabilities in the final evaluation).

5. **No-vig (quant) logic** - Convert American moneyline odds to implied probabilities; normalize by overround to get **fair_prob_home** and **fair_prob_away** (no-vig probabilities).

6. **Evaluation (Option A)** - **Sportsbook-only:** Use `fair_prob_home` and actual outcome (home win = 1, away win = 0).  
   - Compute **Brier Score** and **Log Loss**, and plot a **Probability Calibration Curve** (reliability diagram) plus a histogram of predicted confidence.  
   - Output: `data/processed/sportsbook_calibration.png` and a short terminal summary.

### Why We Pivoted: Polymarket API Limitation

- **Historical order book data:** Polymarket’s CLOB `/prices-history` endpoint returns **empty** `{"history": []}` for closed markets. Minute-by-minute (e.g. T-minus 1 hour) prices are not available for past games.  
- **Terminal prices only:** For closed events, Gamma API `outcomePrices` are **terminal** (0.0 or 1.0), not pre-game probabilities.  
- **No individual NBA games:** Among active events tagged "NBA", we found **no** individual NBA game markets (only season-long futures and other sports).  
- **Conclusion:** We cannot perform a fair, like-for-like comparison of **historical** T-minus 1 hour probabilities between sportsbooks and Polymarket. The project therefore evaluates **sportsbook calibration only**, and treats the Polymarket API constraints as a core **data availability / engineering** finding.

---

## Team Handoff & Next Steps

Because the data extraction, time-merging, and math functions were highly interdependent, the base programmatic pipeline (Extraction, Merging, No-Vig Logic, and Baseline Evaluation) has been laid down in this repository. 

Here is the division of labor for the remainder of the project:

### Phase 1: Pipeline Foundation (Completed by Pramesh)
- **Data extraction & cleaning:** Polymarket API extraction (`gamma_api.py`) and Kaggle pre-processing.
- **Fuzzy matching:** 30-team alias table and `rapidfuzz` mapping (`fuzzy_match.py`).
- **Temporal synchronization:** `pd.merge_asof` integration (`main.py`).
- **Pipeline scaffolding:** Initial draft of `quant_logic.py` and `evaluation.py`. 

### Phase 2: Data Processing & Validation (Tasks for Priyansh & Karthik)
The base `quant_logic.py` and temporal merge are in the repo. Your goal is to take over the data validation and EDA:
1. **Audit the No-Vig Math:** Review `src/processing/quant_logic.py` to ensure the implied probability conversions are mathematically sound.
2. **Exploratory Data Analysis (EDA):** Dig into the Kaggle data and `master_events.csv`. Calculate the average sportsbook vig, check for any missing odds edge cases, and evaluate how much data is dropped at the T-minus 1 hour snapshot.

### Phase 3: Visualization, Scoring & Reporting (Tasks for Zitian & Yu-Jung)
A baseline `evaluation.py` script has been built that generates an initial Brier Score and Probability Calibration Curve `.png` as a starting point. Your turn to take over the Data Science and Storytelling:
1. **Expand the Data Science:** Modify `evaluation.py` to break down the calibration curves further (e.g., Playoffs vs. Regular season, or Heavy Favorites vs. Underdogs). Add confidence intervals to the Brier scores.
2. **Draft the Academic Report:** Write the final report explaining our methodology, Brier Score/Log Loss results, and calibration findings. 
3. **Create Presentation Slides:** Pull the visual insights into the final presentation. **Crucial:** Ensure we include a dedicated slide on the Polymarket API data-purging limitation as a core engineering finding.

---

## Repository Layout (Critical Path)

```
nba_probability_forecasting/
├── main.py                          # Pipeline entry: load Kaggle, Gamma, fuzzy match, merge_asof, no-vig, save master_events.csv
├── data/
│   ├── raw/                         # Kaggle CSV (e.g. nba_2008-2025.csv); raw Polymarket cache
│   └── processed/                   # master_events.csv, sportsbook_calibration.png, audit outputs
├── src/
│   ├── extraction/
│   │   └── gamma_api.py             # Polymarket Gamma API paginated fetch
│   ├── matching/
│   │   └── fuzzy_match.py           # rapidfuzz + alias table, audit_matches
│   ├── processing/
│   │   ├── quant_logic.py           # No-vig: American odds → fair probabilities
│   │   └── evaluation.py            # Sportsbook-only: Brier, Log Loss, calibration curve
│   └── archive_polymarket_research/  # Archived Polymarket scripts (see README there)
├── scripts/
│   └── diagnose_merge.py            # Pre-merge diagnostics for merge_asof
└── README.md                        # This handoff document
```

---

## Prerequisites

- Place the Kaggle NBA sportsbook CSV (e.g. `nba_2008-2025.csv`) in `data/raw/`.
- Run `pip install -r requirements.txt` to install dependencies (pandas, numpy, matplotlib, requests, rapidfuzz, pytz).

## How to Run

1. **Full pipeline (Kaggle + Polymarket fetch + match + merge + no-vig)**  
   ```bash
   python main.py
   ```  
   Produces `data/processed/master_events.csv`.

2. **Sportsbook-only evaluation (Brier, Log Loss, calibration plot)**  
   ```bash
   python -m src.processing.evaluation
   ```  
   Or from Python:
   ```python
   from src.processing.evaluation import run_evaluation
   df = run_evaluation()
   ```  
   Produces `data/processed/sportsbook_calibration.png` and prints metrics.

3. **Merge diagnostics (optional)**  
   ```bash
   python scripts/diagnose_merge.py
   ```

---

## Dependencies

Install with:

```bash
pip install -r requirements.txt
```

Typical needs: `pandas`, `numpy`, `matplotlib`, `requests`, `rapidfuzz`. See `requirements.txt` for versions.

---
