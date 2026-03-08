# Quantitative Forecasting: Sportsbook Calibration & Prediction Market API Constraints

**ECE 143 — Programming and Data Analysis** **Group Project**

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

## Project Phases

### Phase 1 — Pipeline Foundation (Pramesh)

Built the end-to-end data pipeline connecting all three data sources and processing steps:

- **Kaggle ingestion** (`main.py`) — loads `nba_2008-2025.csv`, standardizes team names, derives a T-minus 1 hour snapshot time, and builds a fuzzy-matchable event key per game.
- **Polymarket extraction** (`src/extraction/gamma_api.py`) — paginated fetch from the Gamma API (tag=NBA, closed=true) with local caching; discovers the API limitation (no historical order book data for closed markets).
- **Fuzzy matching** (`src/matching/fuzzy_match.py`) — 30-team alias dictionary + `rapidfuzz` to align Polymarket event strings with Kaggle's format; filters at 90% similarity and flags low-confidence matches for manual review.
- **Temporal merge** (`main.py`) — `pd.merge_asof` synchronizes sportsbook snapshots with the nearest Polymarket timestamp, producing `data/processed/master_events.csv` (512 matched games).
- **No-vig scaffold** (`src/processing/quant_logic.py`, `src/processing/evaluation.py`) — initial American-odds-to-fair-probability conversion and baseline Brier Score calculation.

### Phase 2 — Data Validation & EDA (Priyansh & Karthik)

Validated the no-vig math and characterized the dataset before evaluation:

- **Audit** (`scripts/audit_quant_logic.py`) — 6 test cases against an external no-vig calculator covering symmetric odds, favorites/underdogs, edge cases (zero odds, extreme lines). All pass within ±0.01 tolerance. A zero-odds guard and NaN handling were added to `quant_logic.py` as a result.
- **EDA** (`analysis.ipynb §2`) — vig distribution (mean 3.77%), fair home win probability distribution, and games-per-season coverage confirming 2008–2022 are fully covered (2023 partial, 2024–2025 no moneylines).
- **Data note** — ~19,820 of 23,118 total games (85.7%) have valid moneyline odds and are used for evaluation. The 512-game `master_events.csv` is retained for methodology context only.

### Phase 3 — Calibration Analysis & Visualization (Zitian, Yu-Jung & Pramesh)

Expanded the evaluation module into a full calibration analysis and produced all project visualizations:

- **Vectorized no-vig** (`quant_logic.py`) — rewrote `apply_no_vig_probabilities()` with NumPy vectorized operations (~20× faster); all 6 audit tests continue to pass.
- **Segmented calibration** (`evaluation.py`) — reliability diagrams broken down by game type (Regular Season vs Playoffs) and prediction confidence tier (strong favourite ≥65%, moderate 55–65%, near coin-flip <55%).
- **Bootstrap confidence intervals** (`evaluation.py`) — 1,000-resample bootstrap 95% CI on every Brier Score estimate.
- **Seasonal trend** (`evaluation.py`) — per-season Brier Score bar chart with CI error bars across 2008–2022.
- **Notebook** (`analysis.ipynb`) — single pre-rendered notebook containing all EDA and calibration visualizations.

#### Phase 3 Standalone Module (`phase3_evaluation/`)

A clean, self-contained evaluation package with separated concerns:

| File | Purpose |
|------|---------|
| `metrics.py` | Pure computation: Brier Score, Log Loss, calibration bins, bootstrap CI, Brier-by-bucket |
| `plots.py` | 5 visualization functions (no metric computation, imports from `metrics.py`) |
| `run_evaluation.py` | Entry point: loads data, computes metrics, prints summary, generates all plots |
| `Phase3_Analysis.ipynb` | Presentation-ready notebook with step-by-step analysis and embedded plots |
| `output/` | 5 generated PNG plots ready for slides |

Run with: `python -m phase3_evaluation.run_evaluation`

**Key results (19,820 games, 2008–2022):**

| Segment | Brier Score | N |
|---|---|---|
| Overall | 0.2024 [0.2000, 0.2047] | 19,820 |
| Regular Season | 0.2021 | 18,550 |
| Playoffs | 0.2062 | 1,257 |
| Strong fav (≥65%) | 0.1717 | 11,291 |
| Moderate fav (55–65%) | 0.2404 | 5,970 |
| Near coin-flip (<55%) | 0.2491 | 2,559 |

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
├── test_pipeline.py                 # Fuzzy match diagnostic test (optional)
├── analysis.ipynb                   # Single notebook: all EDA + calibration visualizations (pre-rendered)
├── requirements.txt                 # Pinned third-party dependencies
├── data/
│   ├── raw/                         # Kaggle CSV (nba_2008-2025.csv)
│   └── processed/                   # master_events.csv; 4 calibration PNGs; audit outputs
├── phase3_evaluation/               # Phase 3 standalone evaluation module (Zitian & Yu-Jung)
│   ├── __init__.py
│   ├── metrics.py                   # Core metrics: Brier Score, Log Loss, Calibration, Bootstrap CI
│   ├── plots.py                     # 5 visualization functions (calibration, buckets, segments, seasons)
│   ├── run_evaluation.py            # One-command entry point for full Phase 3 analysis
│   ├── Phase3_Analysis.ipynb        # Presentation-ready Jupyter notebook
│   └── output/                      # Generated plots (5 PNGs)
├── src/
│   ├── extraction/
│   │   └── gamma_api.py             # Polymarket Gamma API paginated fetch
│   ├── matching/
│   │   └── fuzzy_match.py           # rapidfuzz + 30-team alias table, audit_matches
│   ├── processing/
│   │   ├── quant_logic.py           # No-vig: American odds → fair probabilities (vectorized)
│   │   └── evaluation.py            # Brier CI, segmented calibration, seasonal trend (4 plots)
│   └── archive_polymarket_research/  # Archived Polymarket research scripts (see README there)
├── scripts/
│   ├── audit_quant_logic.py         # No-vig math audit (6 test cases vs. eGamingHQ ground truth)
│   └── diagnose_merge.py            # Pre-merge diagnostics for merge_asof
└── README.md
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

4. **Full analysis notebook** (all visualizations — EDA + calibration plots)
   Open `analysis.ipynb` in Jupyter/VS Code and run all cells.
   Expects `data/raw/nba_2008-2025.csv` to be present. All outputs are pre-rendered so the notebook can also be viewed without re-running.

5. **Phase 3 standalone evaluation** (clean self-contained module)
   ```bash
   python -m phase3_evaluation.run_evaluation
   ```
   Or open the notebook:
   ```bash
   jupyter notebook phase3_evaluation/Phase3_Analysis.ipynb
   ```
   Produces five plots in `phase3_evaluation/output/`:
   - `calibration_curve.png` — overall reliability diagram with confidence distribution
   - `brier_by_bucket.png` — Brier Score per probability bucket (with random baseline)
   - `segmented_by_game_type.png` — Regular Season vs Playoffs calibration
   - `segmented_by_confidence.png` — confidence tiers (strong / moderate / coin-flip)
   - `brier_by_season.png` — seasonal Brier trend with 95% bootstrap CI

6. **Merge diagnostics (optional)**
   ```bash
   python scripts/diagnose_merge.py
   ```

7. **Fuzzy match diagnostics (optional)**
   ```bash
   python test_pipeline.py
   ```

---

## Dependencies

Install with:

```bash
pip install -r requirements.txt
```

Third-party packages: `pandas`, `numpy`, `matplotlib`, `requests`, `rapidfuzz`, `pytz`. Minimum versions are pinned in `requirements.txt`. Tested with Python 3.10+.

---
## Team Roles
1. **(Extraction & Pipeline Setup): Pramesh**
2. **(Data Validation & EDA): Priyansh, Karthik**
3. **(Data Science, Visualization & Reporting): Zitian, Yu-Jung, Pramesh**