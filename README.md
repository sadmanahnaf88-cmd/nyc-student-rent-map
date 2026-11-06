# NYC Student Rent Affordability Map

**Question:** On a given monthly budget, where in NYC can a student live within a reasonable subway commute of campus, and what are the surprising trade-offs?

> **Headline** (home campus currently NYU as a placeholder, see `docs/INSIGHTS.md`): Students sharing a 2BR can save **$548/month ($6,576/year)** by living in **Chinatown-Two Bridges** instead of the **East Village**, with the same 22-minute commute.
>
> For Columbia: living in **University Heights (Bronx)** instead of the **Upper East Side** saves **$1,734/month**, and the commute is a minute *shorter*. There's no direct subway from the UES to Morningside Heights.

- **Campuses:** 17 NYC campuses (`data/reference/campuses.csv`); one is marked as home campus
- **Budgets (per person / month):** $1,000 · $1,500 · $2,000. At $1,000 almost nothing works: 0 NTAs within 45 min of NYU (D-012)
- **Commute limits (door to door, weekday AM peak):** 30 · **45** · 60 minutes
- **Housing:** studio, 1BR (alone), 2BR / 3BR+ split between roommates

## Status

| Phase | What | Status |
|---|---|---|
| 1 | Setup | ✅ |
| 2 | Rent data (StreetEasy) | ✅ snapshot 2026-11-05, window Nov 2025 – Oct 2026 |
| 3 | Geography (StreetEasy → NTA crosswalk) | ✅ 10 low-confidence links marked `REVIEW` |
| 4 | Commute times (GTFS subway graph) | ✅ validated against a straight-line baseline |
| 5 | Analysis | ✅ `docs/INSIGHTS.md` |
| 6 | Tableau export | ✅ `data/processed/`, see `docs/TABLEAU_GUIDE.md` |
| 7 | Survey comparison | ✅ code + questions ready; **waiting for responses** |

## Quick start (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # or requirements-lock.txt for exact versions
# 1. Download the 8 StreetEasy files: docs/DATA_DOWNLOAD.md
# 2. Run everything (about 90 seconds):
python src/run_all.py                    # add --skip-download to reuse NTA/GTFS files
```

If printing DuckDB results gives `UnicodeEncodeError: 'charmap'...`, run `$env:PYTHONIOENCODING = "utf-8"` once per PowerShell window (`run_all.py` sets it automatically).

**To use your own campus:** add a row to `data/reference/campuses.csv` (address + lat/lon), set `is_home_campus` to TRUE on it and FALSE on the rest, then re-run with `--skip-download`.

## Pipeline

| Step | Script | Language | Output |
|---|---|---|---|
| 2a | `src/p2a_load_rent.py` | pandas | wide StreetEasy files → tidy `rent_long.csv` |
| 2b | `src/p2b_rent_summary.py` + `sql/p2_rent_summary.sql` | DuckDB SQL | 12-month median rent, per person, reliability tier |
| 3a | `src/p3a_download_nta.py` | Python | NTA boundaries (NYC Open Data) |
| 3b | `src/p3b_build_crosswalk.py` | pandas, geopandas | StreetEasy ↔ NTA crosswalk (auto + `data/reference/se_nta_crosswalk_manual.csv`) |
| 3c | `src/p3c_rent_by_nta.py` + `sql/p3_rent_by_nta.sql` | DuckDB SQL | rent per NTA (listing-weighted when blended) |
| 4a | `src/p4a_download_gtfs.py` | Python | MTA subway GTFS |
| 4b | `src/p4b_commute_times.py` | networkx | commute minutes, lines, transfers: 17 campuses × 181 NTAs |
| 4c | `src/p4c_validate_commute.py` | pandas | campus access, spot checks, straight-line baseline comparison |
| 5 | `src/p5_analysis.py` + `sql/p5_analysis.sql` | DuckDB SQL | affordability, Pareto best value, swaps, scenarios, `docs/INSIGHTS.md` |
| 6 | `src/p6_tableau_export.py` | pandas, geopandas | `data/processed/tableau_*` |
| 7 | `src/p7_survey_compare.py` | pandas | survey vs public data (once responses exist) |

All settings (budgets, limits, walking speed, thresholds) are in `src/config.py`. Every judgment call is in **`DECISIONS.md`** (D-001 to D-027).

## Data sources

| Source | What | How | Where |
|---|---|---|---|
| StreetEasy Data Dashboard | Median asking rent + listing counts by neighborhood × bedrooms | Manual (no API): `docs/DATA_DOWNLOAD.md` | `data/raw/streeteasy/` |
| NYC Open Data (DCP) | 2020 Neighborhood Tabulation Areas | Script | `data/raw/nta/` |
| MTA | Subway GTFS (regular schedule) | Script | `data/raw/gtfs/` |
| NYC GeoSearch (DCP) | Campus coordinates | Looked up once, stored in `campuses.csv` | `data/reference/` |
| Wikipedia | Neighborhood coordinates/redirects as *evidence* for manual crosswalk rows | Looked up once, cited per row | `data/reference/` |
| Student survey | What students pay and how long they commute | Your form (`docs/SURVEY_QUESTIONS.md`) | `data/raw/survey/`, **never committed** |

Raw files have download dates and SHA-256 checksums in `docs/raw_data_manifest.csv` (D-013: StreetEasy revised its 1BR file within a single day).

## Project layout

```
data/
  raw/         original downloads (git-ignored)
  interim/     cleaned & joined files, CSV/.xlsx for Excel, DuckDB database (git-ignored, rebuildable)
  processed/   final Tableau files (committed)
  reference/   hand-made inputs: campus list, manual crosswalk, survey template (committed)
sql/           DuckDB queries, one per phase
src/           Python scripts; config.py = all settings; run_all.py = whole pipeline
docs/          download guide, data dictionary, Tableau guide, insights, survey questions, checks
DECISIONS.md   every judgment call and why
```

## Key methods

- **Rent:** median of monthly StreetEasy medians over 12 months; per person = unit ÷ bedrooms; low-volume medians are flagged, not dropped, because the gaps cluster in cheaper boroughs (D-005 to D-009).
- **Geography:** NTAs are the map unit. Rent comes from linked StreetEasy neighborhoods; 182 automatic and 43 evidence-documented manual links, with full coverage in both directions (D-014 to D-017).
- **Commute:** a GTFS-based subway graph: walk, wait half the headway, scheduled ride, transfers, walk. Trips needing more than 20 min of walking are flagged, not guessed (D-018 to D-020).
- **Analysis:** Pareto "best value", listing-volume popularity, swaps that add at most 15 min (D-021 to D-024).

## Limitations

- **Asking rents ≠ what tenants pay.** Listings over-represent new and market-rate units (D-011). The survey will measure the gap.
- **Subway only.** 27 NTAs (eastern Queens, Co-op City, Throgs Neck…) and two campuses (Queens College, St. John's) depend on buses or LIRR; those trips are flagged as unknown.
- **One point per NTA** for commutes, and scheduled (not real-time) service.
- **10 low-confidence crosswalk links** (mostly West Bronx areas StreetEasy doesn't list) use a neighbor's rent; they're flagged and never used as recommendations.
- **"Popular" = listing volume**, which skews toward large new buildings, not student preferences.
- Staten Island is out of scope (no StreetEasy neighborhoods, no subway).
