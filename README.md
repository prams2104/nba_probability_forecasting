# NBA Sportsbook Calibration Analysis

**ECE 143 — Programming and Data Analysis | Group Project**

---

## Overview

This project evaluates how accurately traditional sportsbooks predict NBA game outcomes by removing the built-in profit margin ("vig") and scoring the resulting probabilities against real outcomes.

The original goal was to compare sportsbook predictions with decentralized prediction market (Polymarket) probabilities at T-minus 1 hour before tip-off. During data collection, we discovered that **Polymarket’s API does not retain historical order-book data for closed markets** — minute-by-minute prices are purged, and only terminal (0 or 1) settlement prices are available. Individual NBA game markets were also absent; only season-long futures were listed. This became a core engineering finding, and the project pivoted to **sportsbook-only evaluation** on ~19,820 NBA games (2008–2022) from a Kaggle dataset.

**Key results:**

| Segment | Brier Score | N |
|---|---|---|
| Overall | 0.2024 [0.2000, 0.2047] (95% CI) | 19,820 |
| Regular Season | 0.2021 | 18,550 |
| Playoffs | 0.2062 | 1,257 |
| Strong favourite (≥65%) | 0.1717 | 11,291 |
| Moderate favourite (55–65%) | 0.2404 | 5,970 |
| Near coin-flip (<55%) | 0.2491 | 2,559 |

---

## Repository Structure

```
nba_probability_forecasting/
├── main.py                       # Full pipeline: Kaggle load → Polymarket fetch → fuzzy match → merge → no-vig
├── analysis.ipynb                # Main notebook: all EDA + calibration visualizations (pre-rendered)
├── requirements.txt              # Third-party dependencies
├── ECE143 Presentation.pdf       # Final presentation slides
│
├── data/
│   ├── raw/
│   │   └── nba_2008-2025.csv     # Kaggle NBA sportsbook odds (23,118 games, 2008–2025)
│   └── processed/
│       ├── master_events.csv         # 512 matched Polymarket/sportsbook games (methodology artifact)
│       ├── sportsbook_calibration.png
│       ├── segmented_by_game_type.png
│       ├── segmented_by_favorite.png
│       └── brier_by_season.png
│
├── src/
│   ├── extraction/
│   │   └── gamma_api.py          # Polymarket Gamma API: paginated fetch, caching, API-limit discovery
│   ├── matching/
│   │   └── fuzzy_match.py        # rapidfuzz + 30-team alias table; flags low-confidence matches
│   └── processing/
│       ├── quant_logic.py        # No-vig conversion: American odds → fair probabilities (vectorized)
│       ├── evaluation.py         # Brier Score, Log Loss, segmented calibration, seasonal trend (4 plots)
│       ├── metrics.py            # Pure metric functions: Brier, Log Loss, calibration bins, bootstrap CI
│       └── plots.py              # 5 visualization functions used by scripts/run_evaluation.py
│
├── scripts/
│   ├── audit_quant_logic.py      # 6-case no-vig audit against eGamingHQ ground truth; all pass
│   ├── diagnose_merge.py         # Pre-merge diagnostics (dtypes, date ranges, overlap)
│   ├── run_evaluation.py         # Phase 3 entry point: loads data, prints metrics, generates 5 plots
│   ├── test_pipeline.py          # Fuzzy match diagnostics against mock sportsbook/Polymarket data
│   └── phase3_analysis.ipynb     # Phase 3 step-by-step analysis notebook with embedded plots
│
└── archive/
    └── polymarket_research/      # Archived scripts from initial Polymarket API investigation
```

---

## How to Run

> Requires Python 3.10+. Install dependencies first:
> ```bash
> pip install -r requirements.txt
> ```
> The dataset `data/raw/nba_2008-2025.csv` is included. No download needed.

### 1. Sportsbook Evaluation (main entry point)

Runs calibration analysis on ~19,820 games. Does **not** require `main.py` to run first.

```bash
python -m src.processing.evaluation
```

Outputs four plots to `data/processed/`:
- `sportsbook_calibration.png` — overall reliability diagram
- `segmented_by_game_type.png` — Regular Season vs Playoffs
- `segmented_by_favorite.png` — confidence tiers (strong / moderate / coin-flip)
- `brier_by_season.png` — Brier Score per season with 95% bootstrap CI

### 2. Phase 3 Extended Evaluation

Runs the modular Phase 3 evaluation with 5 plots (includes Brier-by-bucket and confidence distribution):

```bash
python -m scripts.run_evaluation
```

Outputs five plots to `data/processed/`. The accompanying notebook is at `scripts/phase3_analysis.ipynb`.

### 3. Full Pipeline (Polymarket fetch + fuzzy match + merge)

Fetches Polymarket data, fuzzy-matches against Kaggle, and produces `master_events.csv`:

```bash
python main.py
```

Note: the Polymarket API no longer returns historical per-game data. This is expected — the merge output is retained for methodology documentation only.

### 4. No-Vig Math Audit

Validates `quant_logic.py` against 6 hand-checked test cases:

```bash
python scripts/audit_quant_logic.py
```

### 5. Analysis Notebook

Open `analysis.ipynb` in Jupyter or VS Code and run all cells. All outputs are pre-rendered so it can be viewed without re-running.

### 6. Diagnostics (optional)

```bash
python scripts/diagnose_merge.py    # merge_asof pre-flight check
python scripts/test_pipeline.py     # fuzzy match diagnostic on mock data
```

---

## Third-Party Dependencies

| Package | Purpose |
|---------|---------|
| `pandas` | Data loading, wrangling, temporal merge (`merge_asof`) |
| `numpy` | Vectorized math for no-vig conversion and metrics |
| `matplotlib` | All visualizations (calibration curves, bar charts) |
| `rapidfuzz` | Fuzzy string matching for Polymarket → sportsbook alignment |
| `requests` | Polymarket Gamma API HTTP requests |
| `pytz` | UTC timezone handling for temporal synchronization |

Minimum versions are pinned in `requirements.txt`. Install with `pip install -r requirements.txt`.

---

## Project Phases

**Phase 1 — Pipeline Foundation (Pramesh)**
Built the end-to-end data pipeline: Kaggle ingestion, Polymarket Gamma API extraction with local caching, 30-team fuzzy matching, `merge_asof` temporal synchronization, and the initial no-vig probability scaffold.

**Phase 2 — Data Validation & EDA (Priyansh & Karthik)**
Audited the no-vig math against 6 external ground-truth cases; characterized the dataset (vig distribution, probability distributions, season coverage); added zero-odds guard and NaN handling to `quant_logic.py`.

**Phase 3 — Calibration Analysis & Visualization (Zitian, Yu-Jung & Pramesh)**
Expanded evaluation to segmented calibration (game type, confidence tier), bootstrap confidence intervals, and seasonal Brier trend. Delivered all presentation visualizations and the final analysis notebook.

---

## Team

| Member | Role |
|--------|------|
| Pramesh | Extraction & pipeline setup, Phase 3 calibration |
| Priyansh | Data validation & EDA |
| Karthik | Data validation & EDA |
| Zitian | Phase 3 metrics, visualization, notebook |
| Yu-Jung | Phase 3 metrics, visualization, notebook |