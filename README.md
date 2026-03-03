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
3. Uses **temporal synchronization** (`pd.merge_asof`) to align sportsbook and Polymarket data in time, yielding **512 matched historical NBA games** in `master_events.csv`.

During extraction we discovered that **Polymarket’s API does not expose historical minute-by-minute order book data for closed markets** (data is purged), and that Polymarket does not list **individual NBA game** markets—only season-long futures. We therefore **pivoted to Option A: Sportsbook-Only Evaluation**. The pipeline now evaluates sportsbook accuracy (Brier Score, Log Loss, and a **Probability Calibration Curve**) on **~19,820 games** from the Kaggle dataset directly (games with moneyline odds). The `master_events.csv` merge output remains for methodology/story; the evaluation module uses Kaggle raw by default for statistically meaningful results. The Polymarket API constraints are documented as a central engineering finding.

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

6. **Evaluation (Option A)** - **Sportsbook-only:** Load Kaggle raw (`data/raw/nba_2008-2025.csv`), filter to rows with moneyline odds (~19,820 games), apply no-vig, then use `fair_prob_home` and actual outcome (home win = 1, away win = 0).  
   - Compute **Brier Score** and **Log Loss**, and plot a **Probability Calibration Curve** (reliability diagram) plus a histogram of predicted confidence.  
   - Output: `data/processed/sportsbook_calibration.png` and a short terminal summary.  
   - *Legacy:* `master_events.csv` (512 games, 17 with moneylines) can be used via `run_evaluation(source="master_events")` for methodology comparison.

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

### Phase 2: Data Processing & Validation (Completed — Priyansh & Karthik)
The base `quant_logic.py` and temporal merge are in the repo. Phase 2 covered data validation and EDA:

1. **Audit the No-Vig Math (✅ Completed):**
   - **`scripts/audit_quant_logic.py`** — Automated test suite that validates `quant_logic.py` against ground-truth values from an external no-vig calculator ([eGamingHQ No-Vig Calculator](https://www.egaminghq.com/no-vig-calculator/)). Tests 6 cases: symmetric odds, favorite/underdog, near-even, fair (no-vig), extreme favorite, and invalid zero odds. All pass with ≤0.01 tolerance.
   - **Bug fix in `quant_logic.py`:** Added `import numpy`, zero-odds guard (`odds == 0 → NaN`), and NaN post-processing in `apply_no_vig_probabilities()` to handle invalid/missing odds gracefully.

2. **Exploratory Data Analysis (✅ Completed):**
   - **`scripts/eda_phase2.ipynb`** — Jupyter notebook performing EDA on the raw Kaggle dataset (`data/raw/nba_2008-2025.csv`). Analyses include:
     - Dataset shape and null counts per column
     - Data drop rate: how many games have valid moneyline odds vs. total
     - Average, min, and max sportsbook vig across ~19,820 games
     - **Vig distribution histogram** (2008–2025)
     - **Home win probability distribution** (fair_prob_home after no-vig removal)
     - **Games per season** with valid moneylines (bar chart; confirms 2008–2022 fully covered, 2023 partial, 2024–2025 have no moneylines)
   - **Data note:** Kaggle has moneyline odds for ~19,820 games (2008–2022 fully, 2023 partial); seasons 2024–2025 have no moneylines. The evaluation module uses Kaggle directly for the main analysis; `master_events.csv` (512 games from the Polymarket merge) has only 17 with moneylines and is kept for methodology/story.

### Phase 3: Visualization, Scoring & Reporting (✅ Code Complete — Pramesh, Zitian & Yu-Jung)

The data science layer is fully implemented. `evaluation.py` and `quant_logic.py` were expanded and optimized:

1. **Expand the Data Science (✅ Completed):**
   - **`quant_logic.py`** — `apply_no_vig_probabilities()` refactored to use vectorized NumPy operations (~20× faster). `american_to_implied()` preserved unchanged for audit compatibility; all 6 audit tests still pass.
   - **`evaluation.py`** — Extended with four new analysis functions:
     - `bootstrap_brier_ci()` — 1,000-resample bootstrap 95% CI on any Brier Score.
     - `plot_segmented_calibration()` — side-by-side reliability diagrams for **Regular Season vs Playoffs**.
     - `plot_favorite_calibration()` — overlaid calibration curves for three **prediction-confidence tiers** (strong favorite ≥65%, moderate 55–65%, near coin-flip <55%).
     - `plot_brier_by_season()` — per-season Brier bar chart with 95% CI error bars showing calibration trend across 2008–2022.
   - Running `python -m src.processing.evaluation` now produces **four plots** and an expanded terminal summary including CI and segment breakdowns.

   **Key results (19,820 games, 2008–2022):**
   | Segment | Brier Score | N |
   |---|---|---|
   | Overall | 0.2024 [0.2000, 0.2047] | 19,820 |
   | Regular Season | 0.2021 | 18,550 |
   | Playoffs | 0.2062 | 1,257 |
   | Strong fav (≥65%) | 0.1717 | 11,291 |
   | Moderate fav (55–65%) | 0.2404 | 5,970 |
   | Near coin-flip (<55%) | 0.2491 | 2,559 |

2. **Draft the Academic Report:** Write the final report explaining our methodology, Brier Score/Log Loss results, and calibration findings. Use the four generated plots as figures.
3. **Create Presentation Slides:** Pull the visual insights into the final presentation. **Crucial:** Ensure we include a dedicated slide on the Polymarket API data-purging limitation as a core engineering finding.

---

## Data Flow (Two Paths)

| Path | Purpose | Output |
|------|---------|--------|
| **main.py** | Polymarket extraction + fuzzy match + merge | `master_events.csv` (512 games) — for methodology/story |
| **evaluation.py** | Sportsbook calibration | Loads **Kaggle raw** (~19,820 games with moneylines) by default — produces 4 plots |

- **Evaluation** does *not* require running `main.py` first. It reads `data/raw/nba_2008-2025.csv` directly.
- To use the legacy `master_events.csv` (17 games with moneylines): `run_evaluation(source="master_events")`.

---

## Repository Layout (Critical Path)

```
nba_probability_forecasting/
├── main.py                          # Pipeline entry: load Kaggle, Gamma, fuzzy match, merge_asof, no-vig, save master_events.csv
├── data/
│   ├── raw/                         # Kaggle CSV (e.g. nba_2008-2025.csv); raw Polymarket cache
│   └── processed/                   # master_events.csv; 4 calibration PNGs; audit outputs
├── src/
│   ├── extraction/
│   │   └── gamma_api.py             # Polymarket Gamma API paginated fetch
│   ├── matching/
│   │   └── fuzzy_match.py           # rapidfuzz + alias table, audit_matches
│   ├── processing/
│   │   ├── quant_logic.py           # No-vig: American odds → fair probabilities (vectorized)
│   │   └── evaluation.py            # Phase 3: Brier CI, segmented calibration, seasonal trend (4 plots)
│   └── archive_polymarket_research/  # Archived Polymarket scripts (see README there)
├── scripts/
│   ├── audit_quant_logic.py          # No-vig math audit (6 test cases vs. eGamingHQ ground truth)
│   ├── eda_phase2.ipynb             # Phase 2 EDA notebook (Kaggle raw: vig, missing odds, distributions)
│   └── diagnose_merge.py            # Pre-merge diagnostics for merge_asof
└── README.md                        # This handoff document
```

---

## Prerequisites

- The Kaggle NBA sportsbook CSV (`nba_2008-2025.csv`) is included in `data/raw/` in this repo. If cloning fresh, ensure it is present (or download from Kaggle and place it there).
- Run `pip install -r requirements.txt` to install dependencies (pandas, numpy, matplotlib, requests, rapidfuzz, pytz).

## How to Run

1. **Full pipeline (Kaggle + Polymarket fetch + match + merge + no-vig)**  
   ```bash
   python main.py
   ```  
   Produces `data/processed/master_events.csv`.

2. **Sportsbook-only evaluation (Brier, Log Loss, calibration plots)** — uses Kaggle raw (~19,820 games) by default
   ```bash
   python -m src.processing.evaluation
   ```
   Or from Python:
   ```python
   from src.processing.evaluation import run_evaluation
   df = run_evaluation()                         # Kaggle (default) — 4 plots
   df = run_evaluation(source="master_events")   # Legacy: 17 games from merge
   ```
   Produces four plots in `data/processed/`:
   - `sportsbook_calibration.png` — overall reliability diagram
   - `segmented_by_game_type.png` — Regular Season vs Playoffs
   - `segmented_by_favorite.png` — confidence tiers (strong / moderate / coin-flip)
   - `brier_by_season.png` — seasonal Brier trend with 95% bootstrap CI error bars

3. **No-vig math audit** (validates `quant_logic.py` against external calculator)  
   ```bash
   python scripts/audit_quant_logic.py
   ```

4. **Phase 2 EDA notebook** (vig distributions, missing odds, data coverage)  
   Open `scripts/eda_phase2.ipynb` in Jupyter/VS Code and run all cells.  
   Expects `data/raw/nba_2008-2025.csv` to be present.

5. **Merge diagnostics (optional)**  
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
## Team Roles
1. **(Extraction & Pipeline Setup): Pramesh**
2. **(Data Validation & EDA): Priyansh, Karthik**
3. **(Data Science, Visualization & Reporting): Zitian, Yu-Jung, Pramesh**